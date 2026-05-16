# ============================================================================
# Variables for Atlassian MCP Server Deployment
# ============================================================================

# -----------------------------------------------------------------------------
# Shared variables (provided via main tfvars file)
# -----------------------------------------------------------------------------

variable "aws_region" {
  description = "AWS region for deployment"
  type        = string
}

variable "environment" {
  description = "Deployment environment (dev, staging, prod)"
  type        = string
}

variable "project_name" {
  description = "Project name used for resource naming"
  type        = string
  default     = "bond-ai"
}

variable "existing_vpc_id" {
  description = "ID of the existing VPC to deploy into"
  type        = string
}

variable "app_runner_subnet_ids" {
  description = "Explicit subnet IDs for App Runner VPC connector. Must be private subnets with NAT gateway routes for internet access. If empty, auto-detects (may pick wrong subnets in VPCs with infrastructure subnets)."
  type        = list(string)
  default     = []
}

# -----------------------------------------------------------------------------
# Atlassian MCP-specific variables
# -----------------------------------------------------------------------------

variable "mcp_atlassian_v2_enabled" {
  description = "Enable Atlassian MCP v2 server deployment"
  type        = bool
  default     = true
}

variable "mcp_atlassian_cpu" {
  description = "CPU allocation for Atlassian MCP service"
  type        = string
  default     = "0.25 vCPU"
}

variable "mcp_atlassian_memory" {
  description = "Memory allocation for Atlassian MCP service"
  type        = string
  default     = "0.5 GB"
}

variable "mcp_atlassian_min_instances" {
  description = "Minimum number of instances for auto scaling"
  type        = number
  default     = 1
}

variable "mcp_atlassian_max_instances" {
  description = "Maximum number of instances for auto scaling"
  type        = number
  default     = 2
}

variable "mcp_atlassian_is_private" {
  description = "Deploy as private App Runner service (VPC-only). Requires apprunner.requests VPC endpoint to exist."
  type        = bool
  default     = false
}

variable "force_rebuild" {
  description = "Set to a timestamp or unique string to force Docker image rebuild"
  type        = string
  default     = ""
}

# -----------------------------------------------------------------------------
# Atlassian OAuth / Secrets
# -----------------------------------------------------------------------------

variable "atlassian_oauth_cloud_id" {
  description = "Atlassian Cloud ID for OAuth"
  type        = string
  default     = "55de5903-f98d-499f-967a-32673b683dc8"
}

variable "atlassian_oauth_redirect_uri" {
  description = "OAuth redirect URI for the Atlassian MCP service"
  type        = string
  default     = "https://fa3vbibtmu.us-west-2.awsapprunner.com/connections/atlassian/callback"
}

variable "atlassian_oauth_scope" {
  description = "OAuth scopes for Atlassian access"
  type        = string
  default     = "read:jira-user read:jira-work write:jira-work read:confluence-space.summary write:confluence-content offline_access"
}

variable "atlassian_oauth_secret_arn" {
  description = "ARN of the Secrets Manager secret containing Atlassian OAuth credentials"
  type        = string
  default     = "arn:aws:secretsmanager:us-west-2:019593708315:secret:bond-ai-dev-atlassian-mcp-secret-gKEcvc"
}
