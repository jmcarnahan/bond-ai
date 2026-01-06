# Simplified Variables - Just the essentials

variable "aws_region" {
  description = "AWS region"
  type        = string
  default     = "us-east-2"
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

# Network
variable "vpc_cidr" {
  description = "VPC CIDR block"
  type        = string
  default     = "10.0.0.0/16"
}

variable "availability_zones" {
  description = "Availability zones (need 2 minimum)"
  type        = list(string)
  default     = ["us-east-2a", "us-east-2b"]
}

variable "public_subnet_cidrs" {
  description = "Public subnet CIDRs"
  type        = list(string)
  default     = ["10.0.1.0/24", "10.0.2.0/24"]
}

variable "database_subnet_cidrs" {
  description = "Database subnet CIDRs"
  type        = list(string)
  default     = ["10.0.20.0/24", "10.0.21.0/24"]
}

# Database
variable "db_instance_class" {
  description = "RDS instance type"
  type        = string
  default     = "db.t3.micro"  # Smallest for testing
}

variable "db_allocated_storage" {
  description = "Storage in GB"
  type        = number
  default     = 20  # Minimum for RDS
}

# OAuth Configuration Variables
variable "oauth2_providers" {
  description = "Comma-separated list of enabled OAuth2 providers (e.g., 'okta', 'google,okta')"
  type        = string
  default     = "okta"
}

variable "okta_domain" {
  description = "Okta domain URL (e.g., https://trial-9457917.okta.com)"
  type        = string
  default     = "https://trial-9457917.okta.com"
}

variable "okta_client_id" {
  description = "Okta OAuth client ID"
  type        = string
  default     = "0oas1uz67oWaTK8iP697"
}

variable "okta_scopes" {
  description = "Okta OAuth scopes"
  type        = string
  default     = "openid,profile,email"
}

variable "okta_secret_name" {
  description = "Name of the AWS Secrets Manager secret containing Okta client secret"
  type        = string
  default     = "bond-ai-dev-okta-secret"
}

variable "okta_redirect_uri" {
  description = "Okta OAuth redirect URI (leave empty to use Host header dynamically)"
  type        = string
  default     = ""
}

variable "jwt_redirect_uri" {
  description = "Frontend redirect URI after successful authentication (where JWT token is sent)"
  type        = string
  default     = ""
}


variable "cors_allowed_origins" {
  description = "Comma-separated list of allowed CORS origins"
  type        = string
  default     = "http://localhost,http://localhost:3000,http://localhost:5000"
}
