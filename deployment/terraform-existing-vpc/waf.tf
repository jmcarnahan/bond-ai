# ============================================================================
# AWS WAF Web ACLs for App Runner Services
# ============================================================================
# This file manages AWS WAF (Web Application Firewall) protection for the
# Bond AI App Runner services (backend, frontend, and MCP Atlassian).
#
# IMPORTANT: File Upload Fix
# The backend WAF has a special configuration to allow file uploads to the
# /files endpoint. The SizeRestrictions_BODY rule is set to COUNT instead
# of BLOCK to prevent legitimate file uploads from being rejected.
#
# Architecture:
# - Each App Runner service has its own WAF Web ACL
# - All WAFs use the same AWS Managed Rule Groups for consistency
# - WAF associations link the Web ACLs to App Runner services
# - CloudWatch metrics enabled for monitoring and debugging
#
# Managed Rule Groups Used:
# 1. AWSManagedRulesCommonRuleSet (700 WCU) - Protection against common threats
# 2. AWSManagedRulesKnownBadInputsRuleSet (200 WCU) - Known malicious patterns
# 3. AWSManagedRulesUnixRuleSet (100 WCU) - Unix/Linux specific attack protection
#
# Total WCU per WAF: 1000 (well under the 5000 limit)
# ============================================================================

# -----------------------------------------------------------------------------
# Backend WAF Web ACL
# -----------------------------------------------------------------------------
# Protects the backend API service with special handling for file uploads.
# The SizeRestrictions_BODY rule is overridden to COUNT (not BLOCK) to allow
# large file uploads to the /files endpoint.
# -----------------------------------------------------------------------------

resource "aws_wafv2_web_acl" "backend" {
  count = var.waf_enabled ? 1 : 0

  name  = "${var.project_name}-${var.environment}-backend-waf"
  scope = "REGIONAL"

  description = "WAF for backend App Runner service with file upload support"

  # Default action: Allow all requests that don't match any blocking rules
  default_action {
    allow {}
  }

  # ---------------------------------------------------------------------------
  # Rule 1: AWS Managed Common Rule Set
  # ---------------------------------------------------------------------------
  # Protects against common web exploits like SQL injection, XSS, and more.
  #
  # CRITICAL: SizeRestrictions_BODY is overridden to COUNT (not BLOCK)
  # This prevents the WAF from blocking legitimate file uploads to /files
  # endpoint while still collecting metrics on large request bodies.
  # ---------------------------------------------------------------------------
  rule {
    name     = "AWS-AWSManagedRulesCommonRuleSet"
    priority = 0

    # Override action must be set to "none" for managed rule groups
    # This allows individual rules within the group to take their actions
    override_action {
      none {}
    }

    statement {
      managed_rule_group_statement {
        vendor_name = "AWS"
        name        = "AWSManagedRulesCommonRuleSet"

        # Override the SizeRestrictions_BODY rule action
        # Changes from BLOCK to COUNT to allow file uploads
        # The rule still evaluates and metrics are collected, but requests
        # are not blocked regardless of body size
        rule_action_override {
          name = "SizeRestrictions_BODY"
          action_to_use {
            count {}
          }
        }
      }
    }

    # CloudWatch metrics for monitoring rule group activity
    visibility_config {
      cloudwatch_metrics_enabled = var.waf_cloudwatch_enabled
      metric_name                = "BackendCommonRuleSetMetric"
      sampled_requests_enabled   = var.waf_sampled_requests_enabled
    }
  }

  # ---------------------------------------------------------------------------
  # Rule 2: AWS Managed Known Bad Inputs Rule Set
  # ---------------------------------------------------------------------------
  # Protects against known malicious request patterns that are commonly
  # associated with vulnerabilities like Log4j, path traversal, etc.
  # ---------------------------------------------------------------------------
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
      metric_name                = "BackendKnownBadInputsRuleSetMetric"
      sampled_requests_enabled   = var.waf_sampled_requests_enabled
    }
  }

  # ---------------------------------------------------------------------------
  # Rule 3: AWS Managed Unix Rule Set
  # ---------------------------------------------------------------------------
  # Protects against attacks that target Unix/Linux systems, such as
  # LFI (Local File Inclusion), command injection, and other OS-level exploits.
  # ---------------------------------------------------------------------------
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
# Frontend WAF Web ACL
# -----------------------------------------------------------------------------
# Protects the frontend application service with standard rule configuration.
# No special overrides needed as frontend doesn't handle file uploads.
# -----------------------------------------------------------------------------

resource "aws_wafv2_web_acl" "frontend" {
  count = var.waf_enabled ? 1 : 0

  name  = "${var.project_name}-${var.environment}-frontend-waf"
  scope = "REGIONAL"

  description = "WAF for frontend App Runner service"

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
      metric_name                = "FrontendCommonRuleSetMetric"
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
      metric_name                = "FrontendKnownBadInputsRuleSetMetric"
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
      metric_name                = "FrontendUnixRuleSetMetric"
      sampled_requests_enabled   = var.waf_sampled_requests_enabled
    }
  }

  visibility_config {
    cloudwatch_metrics_enabled = var.waf_cloudwatch_enabled
    metric_name                = "${var.project_name}-${var.environment}-frontend-waf"
    sampled_requests_enabled   = var.waf_sampled_requests_enabled
  }

  tags = {
    Name = "${var.project_name}-${var.environment}-frontend-waf"
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
# These resources link the WAF Web ACLs to the App Runner services.
# Each service can only be associated with one WAF at a time.
# -----------------------------------------------------------------------------

resource "aws_wafv2_web_acl_association" "backend" {
  count        = var.waf_enabled ? 1 : 0
  resource_arn = aws_apprunner_service.backend.arn
  web_acl_arn  = aws_wafv2_web_acl.backend[0].arn

  # Wait for backend service to finish deploying before associating WAF
  depends_on = [null_resource.wait_for_backend_ready]
}

resource "aws_wafv2_web_acl_association" "frontend" {
  count        = var.waf_enabled ? 1 : 0
  resource_arn = aws_apprunner_service.frontend.arn
  web_acl_arn  = aws_wafv2_web_acl.frontend[0].arn
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

output "frontend_waf_arn" {
  value       = var.waf_enabled ? aws_wafv2_web_acl.frontend[0].arn : ""
  description = "ARN of the frontend WAF Web ACL"
}

output "frontend_waf_id" {
  value       = var.waf_enabled ? aws_wafv2_web_acl.frontend[0].id : ""
  description = "ID of the frontend WAF Web ACL"
}

output "mcp_atlassian_waf_arn" {
  value       = var.waf_enabled && local.mcp_atlassian_can_deploy ? aws_wafv2_web_acl.mcp_atlassian[0].arn : ""
  description = "ARN of the MCP Atlassian WAF Web ACL"
}

output "mcp_atlassian_waf_id" {
  value       = var.waf_enabled && local.mcp_atlassian_can_deploy ? aws_wafv2_web_acl.mcp_atlassian[0].id : ""
  description = "ID of the MCP Atlassian WAF Web ACL"
}
