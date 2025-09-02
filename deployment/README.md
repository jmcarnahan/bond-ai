# Bond AI Complete Deployment Guide

This directory contains **everything** needed to deploy Bond AI to AWS, including:
- Docker configurations for containerization
- Terraform infrastructure-as-code
- Deployment automation with Makefile
- Security policies and scripts
- Complete deployment documentation

## Current Status (as of 2025-09-02)

✅ **Fully Deployed and Operational**  
✅ **Phase 1 Complete**: Infrastructure (VPC, RDS, S3, ECR, IAM)  
✅ **Phase 2 Complete**: Backend API deployed to App Runner  
✅ **Phase 3 Complete**: Frontend deployed with backend URL  
✅ **Phase 4 Complete**: Post-deployment configuration (CORS, redirects)  
✅ **OAuth Working**: Okta authentication configured and tested  
✅ **Phased Deployment**: Single `make deploy` command works (with timeouts handled)  

## Quick Reference

### Common Commands

| Command | Description |
|---------|-------------|
| `make help` | Show all available commands |
| `make init` | Initialize Terraform (first time) |
| `make deploy` | Deploy everything |
| `make deploy-backend` | Deploy backend only |
| `make deploy-frontend` | Deploy frontend only |
| `make rebuild` | Force rebuild Docker images |
| `make test` | Run tests |
| `make logs-backend` | Tail backend logs |
| `make logs-frontend` | Tail frontend logs |
| `make status` | Check deployment status |
| `make destroy` | Destroy all infrastructure |

### Environment Selection

```bash
# Use different environments
make use-dev deploy     # Development
make use-staging deploy # Staging
make use-prod deploy    # Production
```

## 📚 Deployment Documentation

**[See DEPLOYMENT_GUIDE.md for complete deployment instructions](./DEPLOYMENT_GUIDE.md)**

The deployment now uses a phased approach to ensure proper ordering:
1. **Phase 1**: Infrastructure (VPC, RDS, S3, ECR, IAM)
2. **Phase 2**: Backend Service (Docker build + deployment)
3. **Phase 3**: Frontend Service (Docker build with backend URL + deployment)
4. **Phase 4**: Post-deployment configuration (CORS, redirects)

## Quick Start

### ⚠️ Important: Manual Okta Configuration Required

After deployment, you MUST manually add the backend callback URL to your Okta application:
- The exact URL will be displayed at the end of deployment
- Without this step, OAuth login will not work
- See [DEPLOYMENT_GUIDE.md](./DEPLOYMENT_GUIDE.md#-important-post-deployment-manual-steps) for details

### Directory Organization

All deployment-related files are consolidated here, separate from application code:
- **Docker files**: Container definitions at deployment root
- **Terraform**: Infrastructure code in `terraform/` subdirectory
- **Makefile**: Simplified commands at deployment root
- **Documentation**: Deployment-specific docs in `docs/`
- **Scripts & Policies**: Supporting files in their own directories

## Prerequisites

1. **AWS CLI configured**
   ```bash
   aws configure
   # Enter your AWS Access Key ID, Secret, and region (us-east-1)
   ```

2. **AWS IAM Permissions**
   Apply the policy in `terraform-admin-policy.json` to your AWS user:
   ```bash
   aws iam put-user-policy --user-name YOUR_USERNAME \
     --policy-name TerraformAdminPolicy \
     --policy-document file://terraform-admin-policy.json
   ```

3. **Terraform installed** (version 1.5+ recommended)
   ```bash
   terraform version
   ```

4. **Docker installed** (for building images)
   ```bash
   docker --version
   ```

5. **ECR login configured**
   ```bash
   aws ecr get-login-password --region us-east-1 | \
     docker login --username AWS --password-stdin \
     119684128788.dkr.ecr.us-east-1.amazonaws.com
   ```

6. **Okta OAuth Secret** (for authentication)
   ```bash
   # Create the secret in AWS Secrets Manager
   aws secretsmanager create-secret \
     --name bond-ai-dev-okta-secret \
     --secret-string '{"client_secret":"YOUR_OKTA_CLIENT_SECRET"}' \
     --region us-east-1
   ```

### Deploy Everything (Simplified)

```bash
# From deployment directory
cd deployment

# Initialize (first time only)
make init

# Deploy everything with one command
make deploy
```

This single command will:
1. Create all AWS resources (VPC, RDS, App Runner, ECR, etc.)
2. Build and push backend Docker image
3. Build and push frontend Docker image with backend URL
4. Update backend with frontend URL for CORS
5. Start both applications

### Deploy Backend Only

```bash
# From deployment directory
make deploy-backend
```

### Deploy Frontend Only

```bash
# From deployment directory
make deploy-frontend
```

### Force Rebuild Docker Images

```bash
# From deployment directory
make rebuild
```

### Update Configuration Only

```bash
# From deployment directory
make update-config
```

## Infrastructure Components

### Deployed Resources

| Component | Resource | Details |
|-----------|----------|---------|
| **Networking** | VPC | 10.0.0.0/16 CIDR block |
| | Public Subnets | 2 subnets for App Runner |
| | Database Subnets | 2 subnets for RDS |
| | VPC Connector | Enables App Runner → RDS access |
| **Database** | RDS PostgreSQL | db.t3.micro, 20GB storage |
| | Secrets Manager | Database credentials |
| **Backend** | App Runner | Auto-scaling container service |
| | ECR Repository | Docker image registry |
| | S3 Bucket | File uploads storage |
| **Security** | IAM Roles | App Runner instance & ECR access |
| | Security Groups | Network access control |
| | JWT Secret | Authentication key in Secrets Manager |

### Service URLs (Current Deployment - us-east-2)

- **Frontend Application**: https://qqbpevxfxs.us-east-2.awsapprunner.com
- **Backend API**: https://aqyrw7q9i8.us-east-2.awsapprunner.com
- **Health Check**: https://aqyrw7q9i8.us-east-2.awsapprunner.com/health
- **Okta Login**: https://aqyrw7q9i8.us-east-2.awsapprunner.com/login/okta
- **API Documentation**: https://aqyrw7q9i8.us-east-2.awsapprunner.com/docs

## Configuration Files

### `main.tf`
Main infrastructure definition containing all AWS resources.

### `variables.tf`
Variable definitions with defaults.

### `outputs.tf`
Output values like URLs, ARNs, and resource IDs.

### `environments/minimal-us-east-2.tfvars`
Current deployment environment configuration:
```hcl
environment = "dev"
aws_region  = "us-east-2"  # Using us-east-2 region

# Database
db_instance_class    = "db.t3.micro"  # Free tier eligible
db_allocated_storage = 20              # Minimum RDS storage

# Okta OAuth Configuration
oauth2_providers = "okta"
okta_domain      = "https://trial-9457917.okta.com"
okta_client_id   = "0oas1uz67oWaTK8iP697"
okta_scopes      = "openid,profile,email"
okta_secret_name = "bond-ai-dev-okta-secret"

# These are dynamically updated during deployment
okta_redirect_uri = "https://BACKEND_URL/auth/okta/callback"
jwt_redirect_uri = "https://FRONTEND_URL"

# Bedrock Agent Configuration
bedrock_agent_role_name = "BondAIBedrockAgentRole"

# CORS Configuration - dynamically updated in Phase 4
cors_allowed_origins = "http://localhost,http://localhost:3000,http://localhost:5000"
```

### Deployment Directory Structure

```
deployment/
├── README.md                # This file
├── Makefile                 # Simplified deployment commands
├── Dockerfile.backend       # Backend container configuration
├── Dockerfile.frontend      # Frontend container configuration
├── terraform/               # Infrastructure as Code
│   ├── main.tf             # Core AWS resources
│   ├── frontend.tf         # Frontend-specific resources
│   ├── backend.tf          # Terraform state configuration
│   ├── post-deployment-config.tf  # Automated builds and updates
│   ├── variables.tf        # Input variables
│   ├── versions.tf         # Terraform version requirements
│   ├── environments/       # Environment-specific configurations
│   │   ├── minimal.tfvars  # Minimal dev environment
│   │   ├── dev.tfvars      # Development environment
│   │   ├── staging.tfvars  # Staging environment
│   │   └── prod.tfvars     # Production environment
│   └── modules/            # Reusable Terraform modules
├── scripts/                 # Deployment scripts
│   └── deploy_backend.sh   # Legacy deployment script
├── policies/                # Security policies
│   ├── terraform-admin-policy.json  # IAM policy for Terraform
│   └── add-terraform-policy.sh      # Script to apply IAM policy
└── docs/                    # Deployment documentation
    ├── AWS_DEPLOYMENT_PLAN.md       # Architecture and phases
    └── DEPLOYMENT_STATUS.md         # Current deployment status
```

### `terraform-admin-policy.json`
IAM policy for Terraform administration with permissions for:
- EC2 & VPC management
- RDS database operations
- Secrets Manager access
- S3 bucket operations
- ECR registry access
- App Runner management
- IAM role and policy management
- CloudWatch logs
- KMS key management

## Environment Variables

The following environment variables are configured in App Runner:

```bash
# Database connection (password from Secrets Manager)
DATABASE_SECRET_ARN=${database_secret_arn}

# JWT authentication (from Secrets Manager)
JWT_SECRET_KEY=${jwt_secret}
JWT_REDIRECT_URI=${jwt_redirect_uri}

# AWS configuration
AWS_REGION=us-east-1
S3_BUCKET_NAME=${s3_bucket_name}
BEDROCK_AGENT_ROLE_ARN=${bedrock_agent_role_arn}

# AI Provider
BOND_PROVIDER_CLASS=bondable.bond.providers.bedrock.BedrockProvider.BedrockProvider

# OAuth Configuration
OAUTH2_PROVIDERS=${oauth2_providers}
OKTA_DOMAIN=${okta_domain}
OKTA_CLIENT_ID=${okta_client_id}
OKTA_SCOPES=${okta_scopes}
OKTA_SECRET_NAME=${okta_secret_name}
OKTA_REDIRECT_URI=${okta_redirect_uri}

# CORS Configuration
CORS_ALLOWED_ORIGINS=${cors_allowed_origins}
```

## Common Operations

### View Infrastructure Status
```bash
# List all resources
terraform state list

# Show specific resource details
terraform state show aws_apprunner_service.backend

# Get outputs
terraform output
terraform output -json | jq
```

### Update Configuration
```bash
# Modify environments/minimal.tfvars then:
terraform plan -var-file=environments/minimal.tfvars
terraform apply -var-file=environments/minimal.tfvars
```

### Access Secrets
```bash
# Database password
aws secretsmanager get-secret-value \
  --secret-id $(terraform output -raw database_secret_name) \
  --query SecretString --output text | jq

# JWT secret
aws secretsmanager get-secret-value \
  --secret-id bond-ai-dev-jwt-20250827043014065200000002 \
  --query SecretString --output text
```

### Monitor Services
```bash
# Check App Runner status
aws apprunner describe-service \
  --service-arn $(terraform output -raw app_runner_service_arn) \
  --query "Service.Status"

# View App Runner logs (in AWS Console)
# Navigate to: App Runner > bond-ai-dev-backend > Logs
```

### Destroy Infrastructure (CAREFUL!)
```bash
# Review what will be destroyed
terraform plan -destroy -var-file=environments/minimal.tfvars

# Destroy all resources
terraform destroy -var-file=environments/minimal.tfvars
```

## Configuration Strategy

### Environment Variables vs Dynamic Discovery

We use **environment variables** for all configuration instead of dynamic service discovery (previously used S3 config bucket). This approach:
- Eliminates circular dependencies between services
- Simplifies local development
- Follows cloud-native best practices
- Makes debugging easier

### How It Works

1. **Initial Deploy**: Services are created with placeholder configurations
2. **Build Phase**: Docker images are built automatically by Terraform
3. **Update Phase**: Backend runtime variables are updated with frontend URL for CORS
4. **Final State**: Both services have correct cross-references

### Local Development

For local development, the app uses `.env` files:

**Backend** (`/bondable/.env`):
```env
CORS_ALLOWED_ORIGINS=http://localhost,http://localhost:3000,http://localhost:5000
JWT_REDIRECT_URI=http://localhost:3000
```

**Frontend** (`/flutterui/.env`):
```env
API_BASE_URL=http://localhost:8000
ENABLE_AGENTS=true
```

## Docker Build Process

### Automated Build Process

Docker builds are now automated within Terraform using `null_resource` provisioners:
1. **Backend Build**: Automatically builds when Terraform runs
2. **Frontend Build**: Builds with backend URL as build argument
3. **Multi-arch Support**: Builds for both AMD64 and ARM64
4. **ECR Push**: Automatically pushes to ECR repository

### Build Requirements

- **Multi-architecture**: Must build for both AMD64 (AWS) and ARM64 (Mac M1/M2)
- **ECR Login**: Must authenticate to push images
- **Docker Buildx**: Required for multi-platform builds
- **Build Context**: Must run from project root where Dockerfile.backend exists

### Build Process Flow

1. **First Deployment**:
   - Terraform creates ECR repository
   - Build and push Docker image
   - Terraform deploys App Runner with image

2. **Updates**:
   - Modify backend code
   - Rebuild and push new image (same tag)
   - Use Terraform `-replace` to force new deployment

## Troubleshooting

### App Runner Deployment Failed
1. Check logs in AWS Console: App Runner > Service > Logs
2. Verify Docker image exists in ECR
3. Check environment variables are set correctly
4. Ensure IAM roles have necessary permissions

### Database Connection Issues
1. Verify VPC connector is attached to App Runner
2. Check security group allows port 5432
3. Confirm database is in available state
4. Validate connection string format

### Docker Build Issues
```bash
# Clean up Docker resources
docker system prune -a --volumes

# Recreate buildx builder
docker buildx rm multiarch0
docker buildx create --name multiarch0 --use
```

### Terraform State Issues
```bash
# Refresh state
terraform refresh -var-file=environments/minimal.tfvars

# Force recreation of specific resource
terraform apply -replace="aws_apprunner_service.backend" -var-file=environments/minimal.tfvars
```

## Cost Optimization

Current monthly costs (dev environment):
- RDS PostgreSQL (db.t3.micro): ~$15-16
- Backend App Runner (0.25 vCPU, 0.5GB): ~$15-20
- Frontend App Runner (0.25 vCPU, 0.5GB): ~$15-20
- NAT Gateway (if running): ~$45
- S3 & ECR: <$2
- **Total**: ~$45-60/month (without NAT: ~$100/month with NAT)

To reduce costs:
1. Stop App Runner service when not in use
2. Use RDS stop/start for development
3. Clean up old ECR images regularly
4. Review and delete unused S3 objects

## Security Best Practices

1. **Never commit secrets** - Use Secrets Manager
2. **Rotate credentials regularly** - Update JWT secret periodically
3. **Use least privilege IAM** - Grant only necessary permissions
4. **Enable logging** - Monitor access and errors
5. **Keep infrastructure updated** - Apply security patches

## Known Issues & Solutions

### Deployment Timeouts
- **Issue**: `make deploy` may timeout during App Runner service creation (10+ minutes)
- **Solution**: Continue with remaining phases manually:
  ```bash
  make deploy-phase3  # If Phase 2 timed out
  make deploy-phase4  # After Phase 3 completes
  ```

### Manual Okta Configuration Required
- **Issue**: Okta redirect URI must be manually configured after deployment
- **Solution**: The deployment output shows the exact URL to add to your Okta app settings

## Next Steps

### Production Readiness
1. Enable RDS Multi-AZ for high availability
2. Configure auto-scaling policies
3. Set up CloudWatch monitoring and alarms
4. Implement backup strategies
5. Create disaster recovery plan
6. Add custom domain names for services
7. Implement CI/CD pipeline for automated deployments

## Support

For issues or questions:
- Review `AWS_DEPLOYMENT_PLAN.md` for architecture details
- Check `DEPLOYMENT_STATUS.md` for current status
- See `CLAUDE.md` for AI assistant context

---
*Last updated: 2025-09-02*
*Status: Fully deployed and operational in us-east-2*