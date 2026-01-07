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
  description = "Backend service URL (e.g., https://xxx.us-west-2.awsapprunner.com). Set after first deployment. Used by frontend build to configure API endpoint."
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

# AWS Cognito Configuration
variable "cognito_domain" {
  description = "AWS Cognito user pool domain (e.g., https://your-domain.auth.us-west-2.amazoncognito.com)"
  type        = string
  default     = ""
}

variable "cognito_client_id" {
  description = "AWS Cognito app client ID"
  type        = string
  default     = ""
}

variable "cognito_secret_name" {
  description = "AWS Secrets Manager secret name for Cognito client secret (optional for public clients)"
  type        = string
  default     = ""
}

variable "cognito_redirect_uri" {
  description = "Cognito OAuth redirect URI"
  type        = string
  default     = ""
}

variable "cognito_scopes" {
  description = "Cognito OAuth scopes"
  type        = string
  default     = "openid,email,phone"
}

variable "cognito_region" {
  description = "AWS region where Cognito user pool is located"
  type        = string
  default     = "us-west-2"
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

variable "bond_mcp_config" {
  description = "JSON configuration for MCP servers"
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

variable "admin_email" {
  description = "Admin email for privileged operations (SQL endpoint, user management)"
  type        = string
  default     = ""
}

# Build Configuration
variable "force_rebuild" {
  description = "Force rebuild of all Docker images regardless of source changes. Set to current timestamp to trigger: -var='force_rebuild=$(date +%s)'"
  type        = string
  default     = ""
}
