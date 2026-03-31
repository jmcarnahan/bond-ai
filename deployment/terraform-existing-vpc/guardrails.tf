# AWS Bedrock Guardrail Infrastructure
# Content safety guardrail for agent invocations and converse() calls.
#
# Version management:
#   - Terraform auto-publishes a version on first deploy (aws_bedrock_guardrail_version)
#   - For existing environments, set bedrock_guardrail_version in tfvars to pin
#     a specific version (avoids forcing re-migration of agents on config changes)
#   - If bedrock_guardrail_version is empty, the auto-published version is used
#
# To update guardrail config on an existing environment:
#   1. Change config in this file
#   2. terraform apply (updates DRAFT + publishes new version)
#   3. Update bedrock_guardrail_version in tfvars to the new version number
#   4. Re-deploy + re-migrate agents to pick up the new version

# =============================================================================
# Variables
# =============================================================================

variable "enable_guardrails" {
  description = "Whether to create Bedrock Guardrails infrastructure"
  type        = bool
  default     = true
}

variable "guardrail_prompt_attack_strength" {
  description = "Prompt attack filter input strength (NONE, LOW, MEDIUM, HIGH). LOW recommended to avoid false positives on agent instructions."
  type        = string
  default     = "LOW"

  validation {
    condition     = contains(["NONE", "LOW", "MEDIUM", "HIGH"], var.guardrail_prompt_attack_strength)
    error_message = "guardrail_prompt_attack_strength must be one of: NONE, LOW, MEDIUM, HIGH"
  }
}

# =============================================================================
# Guardrail Resource
# =============================================================================

resource "aws_bedrock_guardrail" "main" {
  count = var.enable_guardrails ? 1 : 0

  name                      = "${var.project_name}-${var.environment}-guardrail"
  description               = "Content safety guardrail for ${var.project_name}"
  blocked_input_messaging   = "Your message was flagged by our content safety policy. Please rephrase and try again."
  blocked_outputs_messaging = "The response was blocked by our content safety policy."

  content_policy_config {
    filters_config {
      type            = "VIOLENCE"
      input_strength  = "LOW"
      output_strength = "LOW"
    }
    filters_config {
      type            = "PROMPT_ATTACK"
      input_strength  = var.guardrail_prompt_attack_strength
      output_strength = "NONE"
    }
    filters_config {
      type            = "MISCONDUCT"
      input_strength  = "LOW"
      output_strength = "LOW"
    }
    filters_config {
      type            = "HATE"
      input_strength  = "LOW"
      output_strength = "LOW"
    }
    filters_config {
      type            = "SEXUAL"
      input_strength  = "LOW"
      output_strength = "LOW"
    }
    filters_config {
      type            = "INSULTS"
      input_strength  = "LOW"
      output_strength = "LOW"
    }
  }

  sensitive_information_policy_config {
    pii_entities_config {
      type   = "US_SOCIAL_SECURITY_NUMBER"
      action = "ANONYMIZE"
    }
    pii_entities_config {
      type   = "CREDIT_DEBIT_CARD_NUMBER"
      action = "ANONYMIZE"
    }
    pii_entities_config {
      type   = "CREDIT_DEBIT_CARD_CVV"
      action = "ANONYMIZE"
    }
    pii_entities_config {
      type   = "AWS_ACCESS_KEY"
      action = "BLOCK"
    }
    pii_entities_config {
      type   = "AWS_SECRET_KEY"
      action = "BLOCK"
    }
    pii_entities_config {
      type   = "EMAIL"
      action = "ANONYMIZE"
    }
    pii_entities_config {
      type   = "PHONE"
      action = "ANONYMIZE"
    }
    pii_entities_config {
      type   = "US_BANK_ACCOUNT_NUMBER"
      action = "ANONYMIZE"
    }
    pii_entities_config {
      type   = "US_BANK_ROUTING_NUMBER"
      action = "ANONYMIZE"
    }
  }

  word_policy_config {
    managed_word_lists_config {
      type = "PROFANITY"
    }
  }

  tags = {
    Name = "${var.project_name}-${var.environment}-guardrail"
  }
}

# Publish a version from DRAFT so the app can reference a stable version number.
# Automatically recreated when the guardrail config changes, so new agents
# always get the latest published version.
resource "aws_bedrock_guardrail_version" "main" {
  count = var.enable_guardrails ? 1 : 0

  guardrail_arn = aws_bedrock_guardrail.main[0].guardrail_arn
  description   = "Managed by Terraform"

  lifecycle {
    replace_triggered_by = [aws_bedrock_guardrail.main[0]]
  }
}

# =============================================================================
# Outputs
# =============================================================================

output "guardrail_id" {
  description = "Bedrock Guardrail ID"
  value       = var.enable_guardrails ? aws_bedrock_guardrail.main[0].guardrail_id : ""
}

output "guardrail_version" {
  description = "Active guardrail version used by the application"
  value       = var.enable_guardrails ? (var.bedrock_guardrail_version != "" ? var.bedrock_guardrail_version : aws_bedrock_guardrail_version.main[0].version) : ""
}

output "guardrail_published_version" {
  description = "Latest Terraform-published guardrail version"
  value       = var.enable_guardrails ? aws_bedrock_guardrail_version.main[0].version : ""
}

output "guardrail_migration_instructions" {
  description = "Instructions for migrating existing agents to the latest guardrail version"
  value = var.enable_guardrails ? join("\n", [
    "",
    "Guardrail deployed: ${aws_bedrock_guardrail.main[0].guardrail_id} (version ${aws_bedrock_guardrail_version.main[0].version})",
    "",
    "New agents will automatically use version ${var.bedrock_guardrail_version != "" ? var.bedrock_guardrail_version : aws_bedrock_guardrail_version.main[0].version}.",
    "",
    "To migrate EXISTING agents to the latest version, run:",
    "  BEDROCK_GUARDRAIL_ID=${aws_bedrock_guardrail.main[0].guardrail_id} \\",
    "  BEDROCK_GUARDRAIL_VERSION=${aws_bedrock_guardrail_version.main[0].version} \\",
    "  poetry run python scripts/migrate_guardrails.py --dry-run",
    "",
    "Then run without --dry-run to apply:",
    "  BEDROCK_GUARDRAIL_ID=${aws_bedrock_guardrail.main[0].guardrail_id} \\",
    "  BEDROCK_GUARDRAIL_VERSION=${aws_bedrock_guardrail_version.main[0].version} \\",
    "  poetry run python scripts/migrate_guardrails.py --batch-size 5 --delay 10",
    "",
  ]) : ""
}
