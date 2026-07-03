# =============================================================================
# Shared-ALB Ingress (bond-platform IngressGroup)
#
# Used in consume mode (or when var.eks_use_ingress is set): instead of a
# self-managed NLB, bond-ai joins the shared, bond-mcps-owned ALB by declaring
# an Ingress in the "bond-platform" IngressGroup. The AWS Load Balancer
# Controller (owned by bond-mcps in consume mode) reconciles all Ingresses in
# the group onto a single ALB. bond-ai's group.order is 20 per the platform
# contract (auth-server = 1, per-MCP services = 10). See docs/PLATFORM-CONTRACT.md.
#
# Annotation set mirrors bond-mcps's helm chart ingress.yaml so the group is
# consistent. Deliberately NO `tags` or `subnets` annotations (subnets are
# discovered from tags; tags are owned by the cluster creator). listen-ports is
# HTTPS:443 only here; ssl-redirect works because bond-mcps contributes the
# HTTP:80 listener to the same IngressGroup. idle_timeout is set group-wide from
# this Ingress (300s, required for SSE — the /chat stream).
# =============================================================================

resource "kubernetes_ingress_v1" "backend" {
  count = local.eks_use_ingress ? 1 : 0

  metadata {
    name      = "bond-ai-backend"
    namespace = kubernetes_namespace.bond_ai[0].metadata[0].name

    annotations = merge(
      {
        "alb.ingress.kubernetes.io/group.name"               = var.eks_ingress_group_name
        "alb.ingress.kubernetes.io/group.order"              = var.eks_ingress_group_order
        "alb.ingress.kubernetes.io/scheme"                   = "internet-facing"
        "alb.ingress.kubernetes.io/target-type"              = "ip"
        "alb.ingress.kubernetes.io/listen-ports"             = "[{\"HTTPS\":443}]"
        "alb.ingress.kubernetes.io/ssl-redirect"             = "443"
        "alb.ingress.kubernetes.io/certificate-arn"          = local.eks_cert_arn
        "alb.ingress.kubernetes.io/healthcheck-path"         = "/health"
        "alb.ingress.kubernetes.io/success-codes"            = "200"
        "alb.ingress.kubernetes.io/load-balancer-attributes" = "idle_timeout.timeout_seconds=300"
      },
      var.waf_enabled ? {
        "alb.ingress.kubernetes.io/wafv2-acl-arn" = aws_wafv2_web_acl.backend[0].arn
      } : {}
    )
  }

  spec {
    ingress_class_name = "alb"

    rule {
      host = var.eks_custom_domain_name

      http {
        path {
          path      = "/"
          path_type = "Prefix"

          backend {
            service {
              name = kubernetes_service.backend[0].metadata[0].name
              port {
                number = 8080
              }
            }
          }
        }
      }
    }
  }

  depends_on = [kubernetes_service.backend]
}
