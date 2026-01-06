variable "aws_region" {
  description = "AWS region"
  type        = string
}

variable "environment" {
  description = "Environment name (dev, staging, prod)"
  type        = string
}

variable "project_name" {
  description = "Project name"
  type        = string
  default     = "bond-ai"
}

# Existing VPC Configuration
variable "existing_vpc_id" {
  description = "ID of the existing VPC to use"
  type        = string
}

variable "app_runner_subnet_ids" {
  description = "List of subnet IDs for App Runner VPC connector (use internal-green subnets)"
  type        = list(string)
  default     = []
}

variable "mcp_atlassian_service_url" {
  description = "MCP Atlassian service URL (set after first deployment to avoid circular dependency)"
  type        = string
  default     = ""
}

variable "backend_service_url" {
  description = "Backend service URL (set after first deployment for OAuth redirect)"
  type        = string
  default     = ""
}

# Database
variable "db_instance_class" {
  description = "RDS instance type"
  type        = string
  default     = "db.t3.micro"
}

variable "db_allocated_storage" {
  description = "Storage in GB"
  type        = number
  default     = 20
}

# OAuth Configuration
variable "oauth2_providers" {
  description = "Comma-separated list of enabled OAuth2 providers"
  type        = string
  default     = "okta"
}

variable "okta_domain" {
  description = "Okta domain URL"
  type        = string
}

variable "okta_client_id" {
  description = "Okta OAuth client ID"
  type        = string
}

variable "okta_scopes" {
  description = "Okta OAuth scopes"
  type        = string
  default     = "openid,profile,email"
}

variable "okta_secret_name" {
  description = "Name of the AWS Secrets Manager secret containing Okta client secret"
  type        = string
}

variable "okta_redirect_uri" {
  description = "Okta OAuth redirect URI"
  type        = string
  default     = ""
}

variable "jwt_redirect_uri" {
  description = "Frontend redirect URI after successful authentication"
  type        = string
  default     = ""
}

variable "cors_allowed_origins" {
  description = "Comma-separated list of allowed CORS origins"
  type        = string
  default     = "http://localhost,http://localhost:3000,http://localhost:5000"
}

variable "bedrock_agent_role_name" {
  description = "Name of the Bedrock agent IAM role"
  type        = string
  default     = "BondAIBedrockAgentRole"
}

variable "bedrock_default_model" {
  description = "Default Bedrock model to use for operations like icon selection"
  type        = string
  default     = "us.anthropic.claude-sonnet-4-20250514-v1:0"
}

# Custom Domain Configuration
variable "domain_name" {
  description = "Base domain name for custom URLs (e.g., example.com). Leave empty to use default pattern: bondai.{account_id}.aws.internalzone.com"
  type        = string
  default     = ""
}

variable "frontend_subdomain" {
  description = "Subdomain for frontend application (e.g., 'app' for app.example.com). Only used if domain_name is explicitly set"
  type        = string
  default     = "app"
}

variable "create_hosted_zone" {
  description = "Whether to create a new Route 53 hosted zone for the domain"
  type        = bool
  default     = false
}

variable "existing_hosted_zone_id" {
  description = "ID of existing Route 53 hosted zone (optional, will auto-detect if not provided)"
  type        = string
  default     = ""
}

variable "use_private_zone" {
  description = "Whether to look for a private hosted zone (common in enterprise environments)"
  type        = bool
  default     = true
}

variable "custom_frontend_fqdn" {
  description = "Fully qualified domain name for frontend. Overrides all other domain settings if provided"
  type        = string
  default     = ""
}

# WAF Configuration
variable "waf_enabled" {
  description = "Enable WAF protection for App Runner services"
  type        = bool
  default     = true
}

variable "waf_cloudwatch_enabled" {
  description = "Enable CloudWatch metrics for WAF"
  type        = bool
  default     = true
}

variable "waf_sampled_requests_enabled" {
  description = "Enable sampled requests for WAF (useful for debugging blocked requests)"
  type        = bool
  default     = true
}