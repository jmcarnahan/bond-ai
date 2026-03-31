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

variable "rds_subnet_ids" {
  description = "List of subnet IDs for RDS/Aurora databases. Defaults to auto-detection if not specified."
  type        = list(string)
  default     = []
}

variable "create_s3_vpc_endpoint" {
  description = "Whether to create S3 VPC endpoint. Set to false if your VPC already has an S3 endpoint configured."
  type        = bool
  default     = true
}

variable "mcp_atlassian_service_url" {
  description = "MCP Atlassian service URL (set after first deployment to avoid circular dependency)"
  type        = string
  default     = ""
}

# Database
variable "db_username" {
  description = "Database master username"
  type        = string
  default     = "bondadmin"
}

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

# Main Database Aurora Configuration
# Separate from Knowledge Base Aurora (defined in knowledge-base.tf)
variable "deletion_protection" {
  description = "Enable deletion protection on databases. Set to false for teardown."
  type        = bool
  default     = true
}

variable "use_aurora" {
  description = "Use Aurora Serverless v2 instead of RDS for main database"
  type        = bool
  default     = true
}

variable "aurora_main_min_capacity" {
  description = "Minimum Aurora Serverless v2 capacity for main database (ACUs)"
  type        = number
  default     = 0.5
}

variable "aurora_main_max_capacity" {
  description = "Maximum Aurora Serverless v2 capacity for main database (ACUs)"
  type        = number
  default     = 2
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

# SA-16 NOTE: Cognito is an optional/alternative OAuth provider. No Cognito resources
# are provisioned by this Terraform. These variables are only used if explicitly configured
# in environment tfvars. Primary auth is Okta. If security policy prohibits Cognito,
# these variables and their backend.tf references can be safely removed.
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
  default     = "http://localhost,http://localhost:3000"
}

variable "allowed_redirect_domains" {
  description = "Comma-separated list of allowed redirect domains for OAuth callbacks. Localhost and *.awsapprunner.com are always allowed by default. Add your custom domains here (e.g., 'example.com,api.example.com')"
  type        = string
  default     = ""
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

variable "bedrock_selectable_models" {
  description = "Comma-separated list of Bedrock model IDs available for selection in UI. If empty, all models are available."
  type        = string
  default     = "us.anthropic.claude-opus-4-5-20251101-v1:0,us.anthropic.claude-sonnet-4-5-20250929-v1:0,us.anthropic.claude-haiku-4-5-20251001-v1:0,us.anthropic.claude-sonnet-4-20250514-v1:0"
}

variable "bedrock_guardrail_version" {
  description = "Pin a specific published guardrail version. Leave empty to use the Terraform-managed version (recommended for new environments)."
  type        = string
  default     = ""
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

variable "waf_maintenance_mode" {
  description = "Enable WAF-based maintenance mode for frontend (blocks all traffic with maintenance page)"
  type        = bool
  default     = false
}

variable "admin_users" {
  description = "Comma-separated list of admin user emails for privileged operations (SQL endpoint, user management, etc.)"
  type        = string
  default     = ""
}

variable "admin_email" {
  description = "DEPRECATED: Use admin_users instead. Single admin email for backward compatibility."
  type        = string
  default     = ""
}

variable "allow_all_emails" {
  description = "Allow all authenticated IdP users to log in when valid_emails is empty. Set to 'true' when relying on IdP app assignment for access control."
  type        = string
  default     = "true"
}

# CloudTrail (T34)
variable "enable_cloudtrail" {
  description = "Enable AWS CloudTrail for API audit logging (T34). Creates S3 bucket, CloudWatch Logs group, and trail."
  type        = bool
  default     = false
}

# Build Configuration
variable "force_rebuild" {
  description = "Force rebuild of all Docker images regardless of source changes. Set to current timestamp to trigger: -var='force_rebuild=$(date +%s)'"
  type        = string
  default     = ""
}

# Maintenance Mode
variable "maintenance_mode" {
  description = "Enable maintenance mode to show under construction page instead of the app"
  type        = bool
  default     = false
}

variable "maintenance_message" {
  description = "Custom message to display on maintenance page"
  type        = string
  default     = "We're performing scheduled maintenance. Please check back soon."
}

variable "theme_config_path" {
  description = "Path to theme config JSON file (relative to flutterui/)"
  type        = string
  default     = "theme_configs/bondai_config.json"
}

# Custom Domain Configuration
variable "custom_domain_name" {
  description = "Custom domain name for frontend (e.g., ai.mydomain.cloud or mydomain.cloud). Leave empty to skip custom domain setup."
  type        = string
  default     = ""
}

variable "hosted_zone_name" {
  description = "Route 53 hosted zone name. Required when using a subdomain (e.g., 'mydomain.cloud' for 'ai.mydomain.cloud'). Leave empty to use custom_domain_name as the zone."
  type        = string
  default     = ""
}

variable "enable_www_subdomain" {
  description = "Also configure www subdomain (e.g., www.mydomain.cloud)"
  type        = bool
  default     = false
}

# CMK Migration Snapshot Identifiers
# Set these during CMK migration to restore from snapshot, then clear after apply.
variable "aurora_main_snapshot_identifier" {
  description = "Snapshot identifier to restore main Aurora cluster from during CMK migration. Leave empty for normal operation."
  type        = string
  default     = ""
}

variable "aurora_kb_snapshot_identifier" {
  description = "Snapshot identifier to restore KB Aurora cluster from during CMK migration. Leave empty for normal operation."
  type        = string
  default     = ""
}

# Private App Runner Configuration
variable "backend_is_private" {
  description = "Make the backend App Runner service private (VPC-only access via VPN)."
  type        = bool
  default     = false
}

variable "has_private_mcp_services" {
  description = "Set to true if any standalone MCP services are deployed as private App Runner services. Keeps the shared apprunner.requests VPC endpoint alive even when backend/frontend are public."
  type        = bool
  default     = false
}

# =============================================================================
# Compute Platform Toggles
# =============================================================================

variable "enable_apprunner" {
  description = "Deploy on App Runner. Disable to remove App Runner resources (requires enable_eks = true)."
  type        = bool
  default     = true
}

variable "enable_eks" {
  description = "Deploy on EKS (private-only, VPN access). Can run alongside App Runner."
  type        = bool
  default     = false
}

# =============================================================================
# EKS Configuration
# =============================================================================

variable "eks_node_instance_type" {
  description = "EC2 instance type for EKS managed node group"
  type        = string
  default     = "t3.medium"
}

variable "eks_node_desired_count" {
  description = "Desired number of EKS worker nodes"
  type        = number
  default     = 2
}

variable "eks_node_min_count" {
  description = "Minimum number of EKS worker nodes"
  type        = number
  default     = 1
}

variable "eks_node_max_count" {
  description = "Maximum number of EKS worker nodes"
  type        = number
  default     = 3
}

variable "eks_custom_ami_id" {
  description = "Company-certified AMI ID for EKS nodes. Empty string uses EKS-optimized default. May be mandatory in environments with SCP restrictions on Amazon-owned AMIs."
  type        = string
  default     = ""
}

variable "eks_kubernetes_version" {
  description = "Kubernetes version for EKS cluster"
  type        = string
  default     = "1.31"
}

variable "eks_node_tags" {
  description = "Additional tags for EKS node group EC2 instances. Required by some organizations for SCP/tag policy compliance."
  type        = map(string)
  default     = {}
}

variable "eks_additional_ingress_cidrs" {
  description = "Additional CIDRs allowed to reach EKS nodes (e.g., corporate VPN ranges outside VPC CIDR). Not needed for Tailscale subnet router (traffic arrives from within VPC)."
  type        = list(string)
  default     = []
}

variable "eks_cluster_endpoint_public_access_cidrs" {
  description = "CIDRs allowed to reach EKS cluster API public endpoint (kubectl/Terraform). Default allows all. Restrict to office/VPN CIDRs for defense-in-depth. Note: the app NLB is always private regardless of this setting."
  type        = list(string)
  default     = ["0.0.0.0/0"]

  validation {
    condition     = length(var.eks_cluster_endpoint_public_access_cidrs) > 0
    error_message = "At least one CIDR must be provided. Use [\"0.0.0.0/0\"] for unrestricted access."
  }
}

# EKS TLS/Domain Configuration (flexible for upstream vs downstream)
variable "eks_custom_domain_name" {
  description = "Custom domain for EKS service (e.g., 'eks.ai.mydomain.cloud'). Creates ACM cert + Route53 record. Leave empty to skip."
  type        = string
  default     = ""
}

variable "eks_acm_certificate_arn" {
  description = "Pre-existing ACM certificate ARN for EKS NLB TLS. Takes precedence over eks_custom_domain_name cert creation."
  type        = string
  default     = ""
}

variable "eks_hosted_zone_id" {
  description = "Route53 hosted zone ID for EKS custom domain DNS validation and alias record. Required when eks_custom_domain_name is set."
  type        = string
  default     = ""
}

variable "eks_oauth_base_url" {
  description = "Base URL for EKS OAuth redirects (e.g., 'https://my-nlb.elb.amazonaws.com'). Used when eks_custom_domain_name is not set. Ignored if eks_custom_domain_name is provided (custom domain takes precedence)."
  type        = string
  default     = ""
}
