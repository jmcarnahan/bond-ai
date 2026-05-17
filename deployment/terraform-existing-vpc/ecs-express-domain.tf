# =============================================================================
# ECS Express Custom Domain + TLS Certificate (Optional)
#
# Follows the eks-domain.tf pattern:
# 1. custom_domain_name provided + primary_platform=ecs_express → create ACM cert + Route53 alias
# 2. No custom domain → use raw ALB DNS endpoint (auto-provisioned by ECS Express)
#
# All resources gated by var.enable_ecs_express (default: false)
# =============================================================================

locals {
  ecs_express_custom_domain_enabled = (
    var.enable_ecs_express &&
    var.custom_domain_name != "" &&
    !var.backend_is_private &&
    var.primary_platform == "ecs_express" &&
    var.ecs_express_configure_alb
  )

  # Resolved service URL: custom domain > ALB endpoint
  ecs_express_service_url = var.enable_ecs_express ? (
    local.ecs_express_custom_domain_enabled ? var.custom_domain_name : local.ecs_express_backend_url
  ) : ""
}

# =============================================================================
# ACM Certificate for ALB TLS
# App Runner managed its own certs; ECS Express ALB needs a standard ACM cert.
# =============================================================================

resource "aws_acm_certificate" "ecs_express" {
  count = local.ecs_express_custom_domain_enabled ? 1 : 0

  domain_name               = var.custom_domain_name
  subject_alternative_names = var.enable_www_subdomain ? ["www.${var.custom_domain_name}"] : []
  validation_method         = "DNS"

  tags = {
    Name = "${var.project_name}-${var.environment}-ecs-express-cert"
  }

  lifecycle {
    create_before_destroy = true
  }
}

# =============================================================================
# Route53 DNS Validation Records (for ACM cert)
# Uses the same hosted zone as App Runner custom domain
# =============================================================================

resource "aws_route53_record" "ecs_express_cert_validation" {
  for_each = local.ecs_express_custom_domain_enabled ? {
    for dvo in aws_acm_certificate.ecs_express[0].domain_validation_options : dvo.domain_name => {
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
  zone_id         = data.aws_route53_zone.frontend[0].zone_id
}

resource "aws_acm_certificate_validation" "ecs_express" {
  count = local.ecs_express_custom_domain_enabled ? 1 : 0

  certificate_arn         = aws_acm_certificate.ecs_express[0].arn
  validation_record_fqdns = [for record in aws_route53_record.ecs_express_cert_validation : record.fqdn]
}

# =============================================================================
# Route53 Alias Record (points custom domain to ALB)
# =============================================================================

# A alias record pointing to the public ALB (internet-facing).
resource "aws_route53_record" "ecs_express_alias" {
  count = local.ecs_express_custom_domain_enabled ? 1 : 0

  zone_id = data.aws_route53_zone.frontend[0].zone_id
  name    = var.custom_domain_name
  type    = "A"

  alias {
    name                   = local.ecs_express_alb_dns_name
    zone_id                = local.ecs_express_alb_zone_id
    evaluate_target_health = true
  }

  depends_on = [aws_acm_certificate_validation.ecs_express]
}

# Optional: www subdomain A alias
resource "aws_route53_record" "ecs_express_www_alias" {
  count = local.ecs_express_custom_domain_enabled && var.enable_www_subdomain ? 1 : 0

  zone_id = data.aws_route53_zone.frontend[0].zone_id
  name    = "www.${var.custom_domain_name}"
  type    = "A"

  alias {
    name                   = local.ecs_express_alb_dns_name
    zone_id                = local.ecs_express_alb_zone_id
    evaluate_target_health = true
  }

  depends_on = [aws_acm_certificate_validation.ecs_express]
}

# =============================================================================
# Configure ALB for Custom Domain
#
# ECS Express ALB uses host-header routing — it only forwards requests for
# the *.ecs.*.on.aws endpoint. We need to:
# 1. Add our ACM cert to the HTTPS listener
# 2. Add a listener rule forwarding our custom domain to the same target group
# =============================================================================

resource "null_resource" "ecs_express_alb_custom_domain" {
  count = local.ecs_express_custom_domain_enabled ? 1 : 0

  triggers = {
    # Re-run on every apply to sync target groups after blue-green deployments
    always_run = timestamp()
    domain     = var.custom_domain_name
    alb_arn    = local.ecs_express_alb_arn
    region     = var.aws_region
    cert_arn   = aws_acm_certificate.ecs_express[0].arn
  }

  provisioner "local-exec" {
    command = <<-EOT
      set -e
      REGION="${var.aws_region}"
      ALB_ARN="${local.ecs_express_alb_arn}"
      CERT_ARN="${aws_acm_certificate.ecs_express[0].arn}"
      CUSTOM_DOMAIN="${var.custom_domain_name}"

      echo "Configuring ALB for custom domain: $CUSTOM_DOMAIN"

      # 1. Find the HTTPS listener
      LISTENER_ARN=$(aws elbv2 describe-listeners \
        --load-balancer-arn "$ALB_ARN" \
        --region "$REGION" \
        --query "Listeners[?Port==\`443\`].ListenerArn | [0]" \
        --output text)

      if [ -z "$LISTENER_ARN" ] || [ "$LISTENER_ARN" = "None" ]; then
        echo "ERROR: No HTTPS listener found on ALB"
        exit 1
      fi
      echo "HTTPS Listener: $LISTENER_ARN"

      # 2. Add ACM certificate to listener
      echo "Adding ACM certificate..."
      aws elbv2 add-listener-certificates \
        --listener-arn "$LISTENER_ARN" \
        --certificates CertificateArn="$CERT_ARN" \
        --region "$REGION" \
        --output text 2>/dev/null || echo "Certificate may already be attached"

      # 3. Find THIS service's forward config by matching the *.on.aws endpoint rule.
      # CRITICAL: On a shared ALB, multiple services have rules. We must match
      # our specific endpoint, not just the first rule (which could be another service).
      # Strip protocol prefix if present (ingress_paths may include https://)
      SERVICE_ENDPOINT=$(echo "${local.ecs_express_backend_url}" | sed 's|^https\?://||')
      echo "Service Endpoint: $SERVICE_ENDPOINT"

      FORWARD_CONFIG=$(aws elbv2 describe-rules \
        --listener-arn "$LISTENER_ARN" \
        --region "$REGION" \
        --output json | jq -c --arg ep "$SERVICE_ENDPOINT" \
        '[.Rules[] | select(.Conditions[]? | .Values[]? == $ep) | .Actions[0].ForwardConfig] | first // empty')

      if [ -z "$FORWARD_CONFIG" ] || [ "$FORWARD_CONFIG" = "null" ]; then
        echo "ERROR: Could not find listener rule for endpoint $SERVICE_ENDPOINT"
        exit 1
      fi

      echo "Forward config: $FORWARD_CONFIG"

      # 5. Check if a rule for our custom domain already exists
      EXISTING_RULE=$(aws elbv2 describe-rules \
        --listener-arn "$LISTENER_ARN" \
        --region "$REGION" \
        --output json | jq -r --arg domain "$CUSTOM_DOMAIN" \
        '[.Rules[] | select(.Conditions[]? | .Field == "host-header" and (.Values[]? == $domain)) | .RuleArn] | first // empty')

      if [ -n "$EXISTING_RULE" ]; then
        echo "Updating existing listener rule for $CUSTOM_DOMAIN..."
        # Build the actions JSON with the full forward config (both target groups)
        ACTIONS_JSON=$(echo "$FORWARD_CONFIG" | jq -c '{Type: "forward", ForwardConfig: .}')
        aws elbv2 modify-rule \
          --rule-arn "$EXISTING_RULE" \
          --actions "$ACTIONS_JSON" \
          --region "$REGION" \
          --output text
        echo "Listener rule updated with current target groups"
      else
        echo "Creating listener rule for $CUSTOM_DOMAIN..."
        # Find next available priority (shared ALB may have other services' rules)
        USED_PRIORITIES=$(aws elbv2 describe-rules \
          --listener-arn "$LISTENER_ARN" \
          --region "$REGION" \
          --output json | jq -r '[.Rules[].Priority | select(. != "default") | tonumber] | sort | last // 0')
        NEXT_PRIORITY=$((USED_PRIORITIES + 1))
        echo "Using priority: $NEXT_PRIORITY"

        ACTIONS_JSON=$(echo "$FORWARD_CONFIG" | jq -c '{Type: "forward", ForwardConfig: .}')
        aws elbv2 create-rule \
          --listener-arn "$LISTENER_ARN" \
          --priority "$NEXT_PRIORITY" \
          --conditions Field=host-header,Values="$CUSTOM_DOMAIN" \
          --actions "$ACTIONS_JSON" \
          --region "$REGION" \
          --output text
        echo "Listener rule created"
      fi

      echo "Custom domain ALB configuration complete"
    EOT
  }

  # Clean up the listener rule and certificate when this resource is destroyed
  provisioner "local-exec" {
    when    = destroy
    command = <<-EOT
      set -e
      REGION="${self.triggers.region}"
      ALB_ARN="${self.triggers.alb_arn}"
      CUSTOM_DOMAIN="${self.triggers.domain}"

      echo "Cleaning up ALB custom domain config for: $CUSTOM_DOMAIN"

      LISTENER_ARN=$(aws elbv2 describe-listeners \
        --load-balancer-arn "$ALB_ARN" \
        --region "$REGION" \
        --query "Listeners[?Port==\`443\`].ListenerArn | [0]" \
        --output text 2>/dev/null || echo "None")

      if [ -z "$LISTENER_ARN" ] || [ "$LISTENER_ARN" = "None" ]; then
        echo "No HTTPS listener found — nothing to clean up"
        exit 0
      fi

      # Find and delete the listener rule for our custom domain
      RULE_ARN=$(aws elbv2 describe-rules \
        --listener-arn "$LISTENER_ARN" \
        --region "$REGION" \
        --output json 2>/dev/null | jq -r --arg domain "$CUSTOM_DOMAIN" \
        '[.Rules[] | select(.Conditions[]? | .Field == "host-header" and (.Values[]? | contains($domain))) | .RuleArn] | first // empty')

      if [ -n "$RULE_ARN" ]; then
        echo "Deleting listener rule: $RULE_ARN"
        aws elbv2 delete-rule --rule-arn "$RULE_ARN" --region "$REGION" || echo "Warning: could not delete rule"
      else
        echo "No listener rule found for $CUSTOM_DOMAIN"
      fi

      # Remove the certificate from the listener
      CERT_ARN="${self.triggers.cert_arn}"
      if [ -n "$CERT_ARN" ]; then
        echo "Removing certificate from listener..."
        aws elbv2 remove-listener-certificates \
          --listener-arn "$LISTENER_ARN" \
          --certificates CertificateArn="$CERT_ARN" \
          --region "$REGION" 2>/dev/null || echo "Warning: could not remove certificate"
      fi

      echo "ALB custom domain cleanup complete"
    EOT
  }

  depends_on = [
    aws_acm_certificate_validation.ecs_express,
    aws_ecs_express_gateway_service.backend
  ]
}
