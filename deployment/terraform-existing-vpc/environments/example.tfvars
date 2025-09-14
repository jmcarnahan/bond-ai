# Example configuration for deploying Bond AI to an existing VPC
# Copy this file and customize for your deployment
# Usage: terraform apply -var-file=environments/your-config.tfvars

# ===== REQUIRED: Must be changed =====

# AWS Configuration
aws_region   = "us-west-2"  # Change to your AWS region
environment  = "dev"         # Options: dev, staging, prod
project_name = "bond-ai"     # Used for naming resources

# Existing VPC Configuration (REQUIRED - must be changed)
existing_vpc_id = "vpc-XXXXXXXXXXXXXXXXX"  # Replace with your VPC ID from Step 1

# OAuth Configuration (REQUIRED - must be configured)
# You need to set up an Okta application first
okta_domain      = "https://your-domain.okta.com"  # Your Okta domain
okta_client_id   = "0oaXXXXXXXXXXXXXX"            # Your Okta app client ID
okta_secret_name = "bond-ai-dev-okta-secret"       # Name for AWS Secrets Manager secret

# ===== OPTIONAL: Can use defaults =====

# Database Configuration
db_instance_class    = "db.t3.micro"  # Smallest RDS instance for dev
db_allocated_storage = 20              # GB of storage

# OAuth Scopes
okta_scopes = "openid,profile,email"

# These are set automatically during deployment - leave empty
okta_redirect_uri = ""  # Will be set to backend URL/auth/okta/callback
jwt_redirect_uri  = ""  # Will be set to frontend URL

# CORS Configuration (localhost for development)
cors_allowed_origins = "http://localhost,http://localhost:3000,http://localhost:5000"

# Bedrock Configuration
bedrock_agent_role_name = "BondAIBedrockAgentRole"

# Default Bedrock model - varies by region
# us-west-2: Use Sonnet 4
bedrock_default_model = "us.anthropic.claude-sonnet-4-20250514-v1:0"
# us-east-1: Can use Haiku 3
# bedrock_default_model = "us.anthropic.claude-3-5-haiku-20241022-v1:0"

# ===== BEFORE DEPLOYING =====
#
# 1. Create Okta Application:
#    - Sign in to Okta Admin Console
#    - Create new OIDC Web Application
#    - Set redirect URI later (after backend deploys)
#    - Copy Client ID and Client Secret
#
# 2. Store Okta Secret in AWS:
#    aws secretsmanager create-secret \
#      --name bond-ai-dev-okta-secret \
#      --secret-string '{"client_secret":"YOUR_OKTA_CLIENT_SECRET"}' \
#      --region us-west-2
#
# 3. Verify VPC:
#    - Ensure VPC has at least 2 private subnets
#    - Ensure NAT Gateway or NAT Instance is configured
#    - Security groups will be created automatically
#
# 4. Deploy:
#    terraform init
#    terraform apply -var-file=environments/your-config.tfvars
#
# 5. After Deployment:
#    - Update Okta app redirect URI with backend URL from terraform output
#    - Test at frontend URL from terraform output