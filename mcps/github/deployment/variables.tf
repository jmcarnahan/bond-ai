# ============================================================================
# Variables for GitHub MCP Server Deployment
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

# -----------------------------------------------------------------------------
# GitHub MCP-specific variables
# -----------------------------------------------------------------------------

variable "mcp_github_enabled" {
  description = "Enable GitHub MCP server deployment"
  type        = bool
  default     = true
}

variable "mcp_github_cpu" {
  description = "CPU allocation for GitHub MCP service"
  type        = string
  default     = "0.25 vCPU"
}

variable "mcp_github_memory" {
  description = "Memory allocation for GitHub MCP service"
  type        = string
  default     = "0.5 GB"
}

variable "mcp_github_min_instances" {
  description = "Minimum number of instances for auto scaling"
  type        = number
  default     = 1
}

variable "mcp_github_max_instances" {
  description = "Maximum number of instances for auto scaling"
  type        = number
  default     = 2
}

variable "force_rebuild" {
  description = "Set to a timestamp or unique string to force Docker image rebuild"
  type        = string
  default     = ""
}
