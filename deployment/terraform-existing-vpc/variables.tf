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