# ============================================================================
# AWS WAF Web ACLs for App Runner Services
# ============================================================================
# This file manages AWS WAF (Web Application Firewall) protection for the
# Bond AI App Runner services (combined backend+frontend, and MCP Atlassian).
#
# IMPORTANT: File Upload Fix
# The backend WAF has a special configuration to allow file uploads to the
# /files endpoint. The SizeRestrictions_BODY rule is set to COUNT instead
# of BLOCK to prevent legitimate file uploads from being rejected.
#
# Architecture:
# - The combined service has a single WAF Web ACL with maintenance mode support
# - MCP Atlassian has its own WAF Web ACL (when deployed)
# - WAF associations link the Web ACLs to App Runner services
# - CloudWatch metrics enabled for monitoring and debugging
#
# Managed Rule Groups Used:
# 1. AWSManagedRulesCommonRuleSet (700 WCU) - Protection against common threats
# 2. AWSManagedRulesKnownBadInputsRuleSet (200 WCU) - Known malicious patterns
# 3. AWSManagedRulesUnixRuleSet (100 WCU) - Unix/Linux specific attack protection
#
# Total WCU per WAF: ~1100 (well under the 5000 limit)
# ============================================================================

# -----------------------------------------------------------------------------
# Backend WAF Web ACL (serves combined frontend + backend)
# -----------------------------------------------------------------------------
# Protects the combined service with maintenance mode support and special
# handling for file uploads. The SizeRestrictions_BODY and CrossSiteScripting_BODY
# rules are overridden to COUNT (not BLOCK) to allow file uploads.
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
# MCP Atlassian WAF Web ACL
# -----------------------------------------------------------------------------
# Protects the MCP Atlassian service with standard rule configuration.
# Only created when MCP Atlassian is deployed.
# -----------------------------------------------------------------------------

resource "aws_wafv2_web_acl" "mcp_atlassian" {
  count = var.waf_enabled && local.mcp_atlassian_can_deploy ? 1 : 0

  name  = "${var.project_name}-${var.environment}-mcp-atlassian-waf"
  scope = "REGIONAL"

  description = "WAF for MCP Atlassian App Runner service"

  default_action {
    allow {}
  }

  # Rule 1: Common Rule Set (standard configuration)
  rule {
    name     = "AWS-AWSManagedRulesCommonRuleSet"
    priority = 0

    override_action {
      none {}
    }

    statement {
      managed_rule_group_statement {
        vendor_name = "AWS"
        name        = "AWSManagedRulesCommonRuleSet"
      }
    }

    visibility_config {
      cloudwatch_metrics_enabled = var.waf_cloudwatch_enabled
      metric_name                = "MCPCommonRuleSetMetric"
      sampled_requests_enabled   = var.waf_sampled_requests_enabled
    }
  }

  # Rule 2: Known Bad Inputs Rule Set
  rule {
    name     = "AWS-AWSManagedRulesKnownBadInputsRuleSet"
    priority = 1

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
      metric_name                = "MCPKnownBadInputsRuleSetMetric"
      sampled_requests_enabled   = var.waf_sampled_requests_enabled
    }
  }

  # Rule 3: Unix Rule Set
  rule {
    name     = "AWS-AWSManagedRulesUnixRuleSet"
    priority = 2

    override_action {
      none {}
    }

    statement {
      managed_rule_group_statement {
        vendor_name = "AWS"
        name        = "AWSManagedRulesUnixRuleSet"
      }
    }

    visibility_config {
      cloudwatch_metrics_enabled = var.waf_cloudwatch_enabled
      metric_name                = "MCPUnixRuleSetMetric"
      sampled_requests_enabled   = var.waf_sampled_requests_enabled
    }
  }

  visibility_config {
    cloudwatch_metrics_enabled = var.waf_cloudwatch_enabled
    metric_name                = "${var.project_name}-${var.environment}-mcp-atlassian-waf"
    sampled_requests_enabled   = var.waf_sampled_requests_enabled
  }

  tags = {
    Name = "${var.project_name}-${var.environment}-mcp-atlassian-waf"
  }
}

# -----------------------------------------------------------------------------
# WAF Web ACL Associations
# -----------------------------------------------------------------------------

resource "aws_wafv2_web_acl_association" "backend" {
  count        = var.waf_enabled ? 1 : 0
  resource_arn = aws_apprunner_service.backend.arn
  web_acl_arn  = aws_wafv2_web_acl.backend[0].arn

  # Wait for backend service to finish deploying before associating WAF
  depends_on = [null_resource.wait_for_backend_ready]
}

resource "aws_wafv2_web_acl_association" "mcp_atlassian" {
  count        = var.waf_enabled && local.mcp_atlassian_can_deploy ? 1 : 0
  resource_arn = aws_apprunner_service.mcp_atlassian[0].arn
  web_acl_arn  = aws_wafv2_web_acl.mcp_atlassian[0].arn
}

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

output "mcp_atlassian_waf_arn" {
  value       = var.waf_enabled && local.mcp_atlassian_can_deploy ? aws_wafv2_web_acl.mcp_atlassian[0].arn : ""
  description = "ARN of the MCP Atlassian WAF Web ACL"
}

output "mcp_atlassian_waf_id" {
  value       = var.waf_enabled && local.mcp_atlassian_can_deploy ? aws_wafv2_web_acl.mcp_atlassian[0].id : ""
  description = "ID of the MCP Atlassian WAF Web ACL"
}
