# ============================================================================
# AWS WAF Web ACL for the combined Bond AI service (EKS)
# ============================================================================
# One Web ACL with maintenance-mode support, attached to the shared
# bond-platform ALB via the Ingress annotation (see the attachment note at
# the bottom of this file). Rule changes here affect ALL traffic on that ALB,
# including bond-mcps services.
#
# Several managed rules are overridden to COUNT for documented false
# positives (file uploads, agent instructions, OAuth loopback redirect URIs,
# UA-less Microsoft Graph webhooks) — see the comments on each override.
#
# Managed Rule Groups Used:
# 1. AWSManagedRulesCommonRuleSet (700 WCU) - Protection against common threats
# 2. AWSManagedRulesKnownBadInputsRuleSet (200 WCU) - Known malicious patterns
# 3. AWSManagedRulesUnixRuleSet (100 WCU) - Unix/Linux specific attack protection
#
# Total WCU: ~1100 (well under the 5000 limit)
# ============================================================================

# -----------------------------------------------------------------------------
# Backend WAF Web ACL (serves combined frontend + backend)
# -----------------------------------------------------------------------------
# Protects the combined service with maintenance mode support and special
# handling for file uploads and agent updates. SizeRestrictions_BODY and
# CrossSiteScripting_BODY are overridden to COUNT to allow file uploads.
# UNIXShellCommandsVariables_BODY is overridden to COUNT because agent
# instructions contain Unix-like patterns (paths, variables) that are
# text prompts, not executed code.
# -----------------------------------------------------------------------------

resource "aws_wafv2_web_acl" "backend" {
  count = var.waf_enabled ? 1 : 0

  name  = "${var.project_name}-${var.environment}-backend-waf"
  scope = "REGIONAL"

  description = "WAF for combined App Runner service with file upload support and maintenance mode"

  # Default action: Allow all requests that don't match any blocking rules
  default_action {
    allow {}
  }

  # ---------------------------------------------------------------------------
  # Custom Response Body for Maintenance Page
  # ---------------------------------------------------------------------------
  custom_response_body {
    key          = "maintenance-page"
    content_type = "TEXT_HTML"
    content      = <<-HTML
<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Maintenance</title>
  <style>
    body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;display:flex;justify-content:center;align-items:center;height:100vh;margin:0;background:#f5f5f5;}
    .container{text-align:center;padding:40px;background:white;border-radius:10px;box-shadow:0 2px 10px rgba(0,0,0,0.1);max-width:500px;margin:20px;}
    h1{color:#333;margin-bottom:1rem;font-size:1.75rem;}
    p{color:#666;line-height:1.6;margin:0.5rem 0;}
    .icon{font-size:3rem;margin-bottom:1rem;}
    .footer{font-size:0.875rem;color:#999;margin-top:2rem;}
  </style>
</head>
<body>
  <div class="container">
    <div class="icon">🔧</div>
    <h1>Under Maintenance</h1>
    <p>We're deploying updates to improve your experience.</p>
    <p>Please check back in a few minutes.</p>
    <p class="footer">We appreciate your patience.</p>
  </div>
</body>
</html>
HTML
  }

  # ---------------------------------------------------------------------------
  # Rule 0: Maintenance Mode
  # ---------------------------------------------------------------------------
  # When waf_maintenance_mode=true, blocks ALL traffic and returns the
  # maintenance page with a 503 status code.
  # When waf_maintenance_mode=false, the rule counts (logs) but allows traffic.
  # ---------------------------------------------------------------------------
  rule {
    name     = "maintenance-mode"
    priority = 0

    action {
      dynamic "count" {
        for_each = var.waf_maintenance_mode ? [] : [1]
        content {}
      }
      dynamic "block" {
        for_each = var.waf_maintenance_mode ? [1] : []
        content {
          custom_response {
            response_code            = 503
            custom_response_body_key = "maintenance-page"
            response_header {
              name  = "Cache-Control"
              value = "no-cache, no-store, must-revalidate"
            }
            response_header {
              name  = "Retry-After"
              value = "300"
            }
          }
        }
      }
    }

    statement {
      # Match ALL requests by checking if URI starts with "/" (always true)
      byte_match_statement {
        positional_constraint = "STARTS_WITH"
        search_string         = "/"
        field_to_match {
          uri_path {}
        }
        text_transformation {
          priority = 0
          type     = "NONE"
        }
      }
    }

    visibility_config {
      cloudwatch_metrics_enabled = var.waf_cloudwatch_enabled
      metric_name                = "MaintenanceModeRule"
      sampled_requests_enabled   = var.waf_sampled_requests_enabled
    }
  }

  # ---------------------------------------------------------------------------
  # Rule 1: AWS Managed Common Rule Set
  # ---------------------------------------------------------------------------
  # Protects against common web exploits like SQL injection, XSS, and more.
  #
  # CRITICAL: SizeRestrictions_BODY and CrossSiteScripting_BODY are overridden
  # to COUNT (not BLOCK) to allow file uploads through the /rest/files endpoint.
  # ---------------------------------------------------------------------------
  rule {
    name     = "AWS-AWSManagedRulesCommonRuleSet"
    priority = 1

    override_action {
      none {}
    }

    statement {
      managed_rule_group_statement {
        vendor_name = "AWS"
        name        = "AWSManagedRulesCommonRuleSet"

        rule_action_override {
          name = "SizeRestrictions_BODY"
          action_to_use {
            count {}
          }
        }

        rule_action_override {
          name = "CrossSiteScripting_BODY"
          action_to_use {
            count {}
          }
        }

        # The bond-platform ALB shares this ACL, so the bond-mcps
        # Authorization Server sits behind it too. Native-app OAuth (RFC
        # 8252) uses loopback redirect URIs — http://127.0.0.1:<port>/… in
        # /oauth/authorize query strings and in /oauth/register (DCR) JSON
        # bodies — which BOTH the EC2-metadata SSRF rules AND the generic
        # RFI rules match as attacks (the RFI blocks were masked behind the
        # SSRF blocks until the latter were counted; verified via WAF
        # sampled requests 2026-08-31). Blocking them breaks every
        # desktop/CLI sign-in (bond-desktop's static client AND Claude
        # Code's dynamic registration). Counted, not blocked: the app tier
        # never fetches or includes URLs taken from request parameters, so
        # neither metadata SSRF nor remote file inclusion applies here.
        rule_action_override {
          name = "EC2MetaDataSSRF_QUERYARGUMENTS"
          action_to_use {
            count {}
          }
        }

        rule_action_override {
          name = "EC2MetaDataSSRF_BODY"
          action_to_use {
            count {}
          }
        }

        rule_action_override {
          name = "GenericRFI_QUERYARGUMENTS"
          action_to_use {
            count {}
          }
        }

        rule_action_override {
          name = "GenericRFI_BODY"
          action_to_use {
            count {}
          }
        }

        # Microsoft Graph webhook validation + change notifications (sbel-crm
        # email intelligence, /webhooks/msgraph on the shared ALB) send NO
        # User-Agent header and were blocked with 403 before ever reaching
        # the pod. Count instead of block — the webhook has its own auth
        # (per-subscription clientState). Applied live via CLI 2026-07-27,
        # but that fix never merged, so a later terraform apply reverted it
        # and the webhooks were being blocked again (WAF sampled requests
        # 2026-08-31). This keeps terraform in sync so applies preserve it.
        rule_action_override {
          name = "NoUserAgent_HEADER"
          action_to_use {
            count {}
          }
        }
      }
    }

    visibility_config {
      cloudwatch_metrics_enabled = var.waf_cloudwatch_enabled
      metric_name                = "BackendCommonRuleSetMetric"
      sampled_requests_enabled   = var.waf_sampled_requests_enabled
    }
  }

  # ---------------------------------------------------------------------------
  # Rule 2: AWS Managed Known Bad Inputs Rule Set
  # ---------------------------------------------------------------------------
  rule {
    name     = "AWS-AWSManagedRulesKnownBadInputsRuleSet"
    priority = 2

    override_action {
      none {}
    }

    statement {
      managed_rule_group_statement {
        vendor_name = "AWS"
        name        = "AWSManagedRulesKnownBadInputsRuleSet"
      }
    }

    visibility_config {
      cloudwatch_metrics_enabled = var.waf_cloudwatch_enabled
      metric_name                = "BackendKnownBadInputsRuleSetMetric"
      sampled_requests_enabled   = var.waf_sampled_requests_enabled
    }
  }

  # ---------------------------------------------------------------------------
  # Rule 3: AWS Managed Unix Rule Set
  # ---------------------------------------------------------------------------
  rule {
    name     = "AWS-AWSManagedRulesUnixRuleSet"
    priority = 3

    override_action {
      none {}
    }

    statement {
      managed_rule_group_statement {
        vendor_name = "AWS"
        name        = "AWSManagedRulesUnixRuleSet"

        # Override: Agent instructions may contain Unix-like patterns
        # (shell variables, paths, backticks) that trigger false positives
        # on PUT /rest/agents endpoints. These are text prompts, not executed code.
        rule_action_override {
          name = "UNIXShellCommandsVariables_BODY"
          action_to_use {
            count {}
          }
        }
      }
    }

    visibility_config {
      cloudwatch_metrics_enabled = var.waf_cloudwatch_enabled
      metric_name                = "BackendUnixRuleSetMetric"
      sampled_requests_enabled   = var.waf_sampled_requests_enabled
    }
  }

  # Overall WAF visibility configuration
  visibility_config {
    cloudwatch_metrics_enabled = var.waf_cloudwatch_enabled
    metric_name                = "${var.project_name}-${var.environment}-backend-waf"
    sampled_requests_enabled   = var.waf_sampled_requests_enabled
  }

  tags = {
    Name = "${var.project_name}-${var.environment}-backend-waf"
  }
}

# -----------------------------------------------------------------------------
# WAF attachment
# -----------------------------------------------------------------------------
# This ACL attaches to the shared bond-platform ALB via the Ingress annotation
# alb.ingress.kubernetes.io/wafv2-acl-arn (eks-ingress.tf) — the AWS Load
# Balancer Controller, not Terraform, performs the attach. There is no
# aws_wafv2_web_acl_association resource; rule changes here affect all traffic
# on that ALB, including bond-mcps services.

# -----------------------------------------------------------------------------
# Outputs
# -----------------------------------------------------------------------------

output "backend_waf_arn" {
  value       = var.waf_enabled ? aws_wafv2_web_acl.backend[0].arn : ""
  description = "ARN of the backend WAF Web ACL"
}

output "backend_waf_id" {
  value       = var.waf_enabled ? aws_wafv2_web_acl.backend[0].id : ""
  description = "ID of the backend WAF Web ACL"
}
