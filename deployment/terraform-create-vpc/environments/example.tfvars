# Example configuration for deploying Bond AI with NEW VPC creation
# Copy this file and customize for your deployment
# Usage: terraform apply -var-file=environments/your-config.tfvars

# ===== REQUIRED: Must be configured =====

# AWS Configuration
environment = "dev"         # Options: dev, staging, prod
aws_region  = "us-west-2"   # Your AWS region

# OAuth Configuration (REQUIRED - must be configured)
# You need to set up an Okta application first
okta_domain      = "https://your-domain.okta.com"  # Your Okta domain
okta_client_id   = "0oaXXXXXXXXXXXXXX"            # Your Okta app client ID
okta_secret_name = "bond-ai-dev-okta-secret"       # Name for AWS Secrets Manager secret
okta_scopes      = "openid,profile,email"

# ===== VPC Configuration (can use defaults) =====

# VPC CIDR and Subnets - defaults work for most cases
vpc_cidr = "10.0.0.0/16"

# Availability zones - update based on your region
availability_zones = ["us-west-2a", "us-west-2b"]  # Change for your region

# Subnet CIDRs - defaults provide good network segmentation
public_subnet_cidrs   = ["10.0.1.0/24", "10.0.2.0/24"]   # For NAT Gateways
private_subnet_cidrs  = ["10.0.10.0/24", "10.0.11.0/24"] # For App Runner
database_subnet_cidrs = ["10.0.20.0/24", "10.0.21.0/24"] # For RDS

# NAT Gateway Configuration
enable_nat_gateway = true   # Required for private subnet internet access
single_nat_gateway = true   # Use one NAT Gateway to save costs (dev/staging)
# single_nat_gateway = false  # Use for production (one per AZ)

# ===== Database Configuration =====

db_instance_class           = "db.t3.micro"  # Smallest for dev, increase for prod
db_allocated_storage        = 20             # Initial storage in GB
db_max_allocated_storage    = 100            # Max autoscaling storage
db_multi_az                 = false          # true for production
db_backup_retention_period  = 3              # Days to retain backups
db_deletion_protection      = false          # true for production

# ===== App Runner Configuration =====

# Backend Service
backend_cpu      = "0.25 vCPU"  # Minimum for dev
backend_memory   = "0.5 GB"      # Minimum for dev
backend_min_size = 1             # Minimum instances
backend_max_size = 2             # Max for autoscaling

# Frontend Service
frontend_cpu      = "0.25 vCPU"
frontend_memory   = "0.5 GB"
frontend_min_size = 1
frontend_max_size = 2

# ===== Bedrock Configuration =====

# Model varies by region - check AWS documentation
# us-west-2: Use Sonnet 4
bedrock_model = "us.anthropic.claude-sonnet-4-20250514-v1:0"
# us-east-1: Can use Haiku 3
# bedrock_model = "us.anthropic.claude-3-5-haiku-20241022-v1:0"

# ===== Monitoring and Logging =====

enable_detailed_monitoring = false  # true for production
log_retention_days        = 7       # Increase for production

# ===== Cost Optimization =====

enable_cost_optimization = true  # Applies dev/staging optimizations

# ===== Resource Tags =====

tags = {
  Environment  = "dev"
  Purpose      = "Development"
  ManagedBy    = "Terraform"
  Project      = "BondAI"
  AutoShutdown = "true"  # For automated shutdown scripts
  Owner        = "your-email@company.com"
}

# ===== BEFORE DEPLOYING =====
#
# 1. Check AWS Quotas:
#    - VPC limit (default: 5 per region)
#    - Elastic IP limit (default: 5, needed for NAT)
#    - RDS instance limit
#
# 2. Create Okta Application:
#    - Sign in to Okta Admin Console
#    - Create new OIDC Web Application
#    - Set redirect URI later (after backend deploys)
#    - Copy Client ID and Client Secret
#
# 3. Store Okta Secret in AWS:
#    aws secretsmanager create-secret \
#      --name bond-ai-dev-okta-secret \
#      --secret-string '{"client_secret":"YOUR_OKTA_CLIENT_SECRET"}' \
#      --region us-west-2
#
# 4. Deploy:
#    terraform init
#    terraform apply -var-file=environments/your-config.tfvars
#
# 5. After Deployment:
#    - Update Okta app redirect URI with backend URL from terraform output
#    - Test at frontend URL from terraform output
#
# ===== PRODUCTION RECOMMENDATIONS =====
#
# For production, change these settings:
# - single_nat_gateway = false  (HA with NAT per AZ)
# - db_multi_az = true           (Database high availability)
# - db_deletion_protection = true
# - db_backup_retention_period = 30
# - backend_min_size = 2         (Minimum redundancy)
# - enable_detailed_monitoring = true
# - log_retention_days = 90