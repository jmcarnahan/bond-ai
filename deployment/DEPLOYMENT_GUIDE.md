# Bond AI Complete Deployment Guide

## Overview

Bond AI uses a phased deployment approach to ensure proper dependency ordering and eliminate race conditions. The deployment process is fully automated through Terraform and Make commands.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     Phase 1: Infrastructure                   │
├─────────────────────────────────────────────────────────────┤
│ • VPC, Subnets, Security Groups                              │
│ • RDS PostgreSQL Database                                    │
│ • S3 Bucket for uploads                                      │
│ • ECR Repositories for Docker images                         │
│ • IAM Roles and Policies                                     │
│ • Secrets (Database, JWT, Okta)                             │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│                    Phase 2: Backend Service                   │
├─────────────────────────────────────────────────────────────┤
│ • Build Backend Docker Image                                 │
│ • Push to ECR Repository                                     │
│ • Deploy App Runner Backend Service                          │
│ • Outputs: Backend URL                                       │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│                   Phase 3: Frontend Service                   │
├─────────────────────────────────────────────────────────────┤
│ • Build Frontend Docker Image (with Backend URL)             │
│ • Push to ECR Repository                                     │
│ • Deploy App Runner Frontend Service                         │
│ • Outputs: Frontend URL                                      │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│                 Phase 4: Post-Deployment Config               │
├─────────────────────────────────────────────────────────────┤
│ • Update Backend CORS with Frontend URL                      │
│ • Update Okta Redirect URIs                                  │
│ • Configure JWT Redirect                                     │
│ • Backend Service Restarts with New Config                   │
└─────────────────────────────────────────────────────────────┘
```

## Prerequisites

### 1. AWS Account Setup
```bash
# Configure AWS CLI
aws configure
# Enter: AWS Access Key ID, Secret Access Key, Region (us-east-2)
```

### 2. Create Okta Secret
```bash
# Create the Okta client secret in AWS Secrets Manager
aws secretsmanager create-secret \
  --name bond-ai-dev-okta-secret \
  --secret-string '{"client_secret":"YOUR_OKTA_CLIENT_SECRET"}' \
  --region us-east-2
```

### 3. Install Required Tools
- Terraform (v1.5+)
- Docker with buildx support
- AWS CLI (v2)
- Make

## Deployment Process

### Quick Deploy (Recommended)

```bash
cd deployment

# Initialize Terraform (first time only)
make init

# Deploy everything in proper order
make deploy
```

This will automatically:
1. Deploy all infrastructure
2. Build and deploy the backend
3. Build and deploy the frontend with the backend URL
4. Configure CORS and redirects

### Phased Deploy (For Troubleshooting)

If you need to deploy phases individually:

```bash
# Phase 1: Infrastructure
make deploy-phase1
make validate-phase1

# Phase 2: Backend
make deploy-phase2
make validate-phase2

# Phase 3: Frontend  
make deploy-phase3
make validate-phase3

# Phase 4: Post-deployment configuration
make deploy-phase4

# Validate everything
make validate
```

## Configuration

### Environment Variables File

The deployment uses `terraform/environments/minimal-us-east-2.tfvars`:

```hcl
environment = "dev"
aws_region  = "us-east-2"

# Database
db_instance_class    = "db.t3.micro"
db_allocated_storage = 20

# Okta OAuth
oauth2_providers = "okta"
okta_domain      = "https://trial-9457917.okta.com"
okta_client_id   = "0oas1uz67oWaTK8iP697"
okta_scopes      = "openid,profile,email"
okta_secret_name = "bond-ai-dev-okta-secret"

# These will be automatically updated during deployment
okta_redirect_uri = "https://BACKEND_URL/auth/okta/callback"
jwt_redirect_uri = "https://FRONTEND_URL"
cors_allowed_origins = "http://localhost,http://localhost:3000,http://localhost:5000"
```

### ⚠️ IMPORTANT: Post-Deployment Manual Steps

#### Configure Okta Application (REQUIRED)

**This step MUST be done manually after deployment for OAuth login to work!**

After deployment completes, you need to add the backend callback URL to your Okta application:

1. The deployment will show you the exact URL to add. Look for the "MANUAL STEP REQUIRED" section at the end of deployment.

2. Get the backend URL:
   ```bash
   make outputs
   ```

3. Go to Okta Admin Console:
   ```
   https://YOUR_OKTA_DOMAIN/admin/app/oidc_client/instance/YOUR_CLIENT_ID#tab-general
   ```
   (For this deployment: https://trial-9457917.okta.com/admin/app/oidc_client/instance/0oas1uz67oWaTK8iP697#tab-general)

4. Add to "Sign-in redirect URIs":
   ```
   https://YOUR_BACKEND_URL/auth/okta/callback
   ```
   (The exact URL will be displayed after deployment)

5. Click "Save" in Okta

**Note:** Without this step, users will get a "redirect_uri parameter must be a Login redirect URI" error when trying to log in.

## Validation

### Check Service Status
```bash
make status
```

### Test Backend Health
```bash
make validate-phase2
```

### Test Frontend Access
```bash
make validate-phase3
```

### Test CORS Configuration
```bash
make test-cors
```

### View Logs
```bash
make logs-backend
make logs-frontend
```

## Troubleshooting

### Frontend Fails to Deploy

**Problem**: Frontend AppRunner service shows CREATE_FAILED with "ECR image doesn't exist"

**Solution**: This happens when the frontend service tries to deploy before the Docker image is built. The phased deployment fixes this by:
1. Building the backend first (Phase 2)
2. Building the frontend with the backend URL (Phase 3)
3. Ensuring proper dependencies in Terraform

### CORS Errors

**Problem**: Frontend can't communicate with backend due to CORS

**Solution**: Phase 4 automatically updates the backend with the frontend URL for CORS. You can manually trigger this:
```bash
make deploy-phase4
```

### Okta Login Fails

**Problem**: "redirect_uri parameter must be a Login redirect URI"

**Solution**: Add the backend callback URL to your Okta application settings (see Post-Deployment Manual Steps above)

### Backend Can't Connect to Database

**Problem**: Connection timeout or refused

**Solution**: Check that:
1. VPC and NAT Gateway are created (Phase 1)
2. Database is running: `aws rds describe-db-instances --region us-east-2`
3. Security groups allow connection

## Clean Up

To destroy all resources:
```bash
make destroy
```

## Technical Details

### Dependency Chain

1. **Infrastructure Dependencies**:
   - ECR repositories must exist before Docker builds
   - Database must be running before backend starts
   - VPC/Subnets must exist for App Runner VPC connector

2. **Service Dependencies**:
   - Backend Docker image must exist before backend service
   - Backend service must be running to get URL for frontend build
   - Frontend Docker image (with backend URL) must exist before frontend service

3. **Configuration Dependencies**:
   - Both services must be running before updating CORS
   - Frontend URL needed for backend CORS configuration
   - Backend URL needed for Okta redirect configuration

### Files Modified from Standard Deployment

1. **terraform/build-stages.tf** - Separates Docker builds into proper stages
2. **terraform/post-deployment-updates.tf** - Handles CORS and redirect updates
3. **terraform/frontend.tf** - Added dependency on Docker image build
4. **terraform/main.tf** - Backend depends on Docker image build
5. **deployment/Makefile** - Phased deployment targets

## Cost Estimate

Monthly costs (us-east-2):
- RDS PostgreSQL (db.t3.micro): ~$15-16
- Backend App Runner (0.25 vCPU): ~$15-20  
- Frontend App Runner (0.25 vCPU): ~$15-20
- NAT Gateway: ~$45
- S3 & ECR: <$2
- **Total: ~$90-100/month**

## Support

For issues or questions:
1. Check the troubleshooting section above
2. Review logs: `make logs-backend` or `make logs-frontend`
3. Validate deployment: `make validate`
4. Check service status: `make status`