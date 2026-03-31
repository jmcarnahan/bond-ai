# =============================================================================
# EKS Custom Domain + TLS Certificate (Optional)
#
# Three-tier TLS strategy:
# 1. eks_acm_certificate_arn provided → use it directly (downstream/bring-your-own)
# 2. eks_custom_domain_name provided → create ACM cert + Route53 records (upstream)
# 3. Neither → HTTP-only on port 80 (VPN encrypts the tunnel; acceptable for private)
#
# All resources gated by var.enable_eks (default: false)
# =============================================================================

locals {
  # Whether TLS is available on the NLB
  eks_has_tls = var.eks_acm_certificate_arn != "" || var.eks_custom_domain_name != ""

  # Resolved certificate ARN (bring-your-own takes precedence)
  eks_cert_arn = var.eks_acm_certificate_arn != "" ? var.eks_acm_certificate_arn : (
    var.enable_eks && var.eks_custom_domain_name != "" ? aws_acm_certificate.eks[0].arn : ""
  )

  # The URL for the EKS service (custom domain or NLB hostname)
  eks_service_url = var.enable_eks ? (
    var.eks_custom_domain_name != "" ? var.eks_custom_domain_name : (
      try(kubernetes_service.backend[0].status[0].load_balancer[0].ingress[0].hostname, "pending")
    )
  ) : ""

  # Protocol based on TLS availability
  eks_service_protocol = local.eks_has_tls ? "https" : "http"

  # EKS OAuth base URL — used for redirect URIs in the K8s configmap.
  # Precedence: custom domain > eks_oauth_base_url > empty (wildcard fallback)
  # This avoids a dependency cycle (can't reference NLB hostname in configmap).
  eks_oauth_base_url = (
    var.eks_custom_domain_name != "" ? "https://${var.eks_custom_domain_name}" :
    var.eks_oauth_base_url != "" ? var.eks_oauth_base_url :
    ""
  )
}

# =============================================================================
# ACM Certificate (only when custom domain is set and no cert ARN provided)
# =============================================================================

resource "aws_acm_certificate" "eks" {
  count = var.enable_eks && var.eks_custom_domain_name != "" && var.eks_acm_certificate_arn == "" ? 1 : 0

  domain_name       = var.eks_custom_domain_name
  validation_method = "DNS"

  tags = {
    Name = "${var.project_name}-${var.environment}-eks-cert"
  }

  lifecycle {
    create_before_destroy = true
  }
}

# =============================================================================
# Route53 DNS Validation Records (for ACM cert)
# =============================================================================

resource "aws_route53_record" "eks_cert_validation" {
  for_each = var.enable_eks && var.eks_custom_domain_name != "" && var.eks_acm_certificate_arn == "" && var.eks_hosted_zone_id != "" ? {
    for dvo in aws_acm_certificate.eks[0].domain_validation_options : dvo.domain_name => {
      name   = dvo.resource_record_name
      record = dvo.resource_record_value
      type   = dvo.resource_record_type
    }
  } : {}

  allow_overwrite = true
  name            = each.value.name
  records         = [each.value.record]
  ttl             = 60
  type            = each.value.type
  zone_id         = var.eks_hosted_zone_id
}

resource "aws_acm_certificate_validation" "eks" {
  count = var.enable_eks && var.eks_custom_domain_name != "" && var.eks_acm_certificate_arn == "" && var.eks_hosted_zone_id != "" ? 1 : 0

  certificate_arn         = aws_acm_certificate.eks[0].arn
  validation_record_fqdns = [for record in aws_route53_record.eks_cert_validation : record.fqdn]
}

# =============================================================================
# Route53 Alias Record (points custom domain to NLB)
# =============================================================================

data "aws_lb" "eks_nlb" {
  count = var.enable_eks && var.eks_custom_domain_name != "" && var.eks_hosted_zone_id != "" ? 1 : 0

  tags = {
    "kubernetes.io/cluster/${local.eks_cluster_name}" = "owned"
  }

  depends_on = [kubernetes_service.backend]
}

resource "aws_route53_record" "eks_alias" {
  count = var.enable_eks && var.eks_custom_domain_name != "" && var.eks_hosted_zone_id != "" ? 1 : 0

  zone_id = var.eks_hosted_zone_id
  name    = var.eks_custom_domain_name
  type    = "A"

  alias {
    name                   = data.aws_lb.eks_nlb[0].dns_name
    zone_id                = data.aws_lb.eks_nlb[0].zone_id
    evaluate_target_health = true
  }
}
