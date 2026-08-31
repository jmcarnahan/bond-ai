# Bond AI Deployment Guide

## Overview
This directory contains everything needed to deploy Bond AI to AWS using Terraform and Docker.

## Current Deployment Status (August 31, 2026)
✅ **EKS consume mode on the shared `bond-platform-dev` cluster (us-west-2)**
- Single combined image (nginx + uvicorn) built by `build-stages.tf`, running as
  `kubernetes_deployment.backend` in namespace `bond-ai`
- Served at https://ai.southbayequity.cloud via the shared ALB (owned by the
  bond-mcps repo's cluster; this repo attaches WAF + ingress rules to it)
- App Runner and ECS Express are retired (`enable_apprunner = false`,
  `enable_ecs_express = false`); their terraform remains count-0
- Terraform state is remote: S3 + DynamoDB locking (see "Terraform state" below)

## Directory Structure

```
deployment/
├── terraform-existing-vpc/     # Deploy using existing VPC
│   ├── environments/          # Environment-specific configurations
│   └── *.tf                   # Terraform configuration files
├── terraform-create-vpc/       # Deploy creating new VPC
├── terraform/                  # Original deployment (us-east-1)
├── Dockerfile.backend          # Backend container configuration
├── Dockerfile.frontend         # Frontend container configuration
├── DEPLOYMENT_FIX_GUIDE.md     # Comprehensive deployment fixes
├── monitor-deployment.sh       # Real-time deployment monitoring
├── setup-vpc-for-region.sh     # Create VPC in new AWS account
└── test-vpc-availability.sh    # Test VPC configuration

```

## Quick Start

### Prerequisites
1. AWS CLI configured with appropriate credentials
2. Terraform installed (v1.0+)
3. Docker installed and running
4. Poetry installed (for Python dependencies)

## 🚀 Complete Deployment Process

When deploying to a new AWS account, follow these steps in order:

### Step 1: Verify or Create VPC

#### Option A: Use Existing VPC
```bash
# Test if you have an existing VPC that can be used
cd deployment
./test-vpc-availability.sh

# This will show:
# - Existing VPCs in your account
# - Available subnets
# - Whether you can create new VPCs (quota check)
```

#### Option B: Create New VPC
```bash
# Create a new VPC with proper configuration
cd deployment
./setup-vpc-for-region.sh us-west-2

# This creates:
# - VPC with CIDR 10.0.0.0/16
# - 2 public subnets
# - 2 private subnets
# - Internet Gateway
# - NAT Gateway
# - Route tables

# Save the VPC ID that's output - you'll need it for deployment
```

### Step 2: Clean Up Any Previous Deployment

If you've deployed before and want to start fresh:

```bash
cd deployment/terraform-existing-vpc

# Check if there's existing state
terraform state list

# If there is, destroy everything
terraform destroy -var-file=environments/us-west-2-existing-vpc.tfvars -auto-approve

# Clean up ECR repositories
aws ecr delete-repository --repository-name bond-ai-dev-backend --region us-west-2 --force
aws ecr delete-repository --repository-name bond-ai-dev-frontend --region us-west-2 --force

# Remove state files for fresh start
rm -f terraform.tfstate terraform.tfstate.backup
```

### Step 3: Configure and Deploy

#### For Existing VPC:
```bash
cd deployment/terraform-existing-vpc

# Copy the example configuration
cp environments/example.tfvars environments/my-deployment.tfvars

# Edit the configuration file
vi environments/my-deployment.tfvars
# Required changes:
#   - existing_vpc_id = "vpc-YOUR-VPC-ID-HERE"  # From Step 1
#   - aws_region = "your-region"
#   - okta_domain = "https://your-domain.okta.com"
#   - okta_client_id = "your-okta-client-id"

# Store Okta secret in AWS Secrets Manager
aws secretsmanager create-secret \
  --name bond-ai-dev-okta-secret \
  --secret-string '{"client_secret":"YOUR_OKTA_CLIENT_SECRET"}' \
  --region your-region

# Initialize Terraform
terraform init

# Deploy everything
terraform apply -var-file=environments/my-deployment.tfvars
```

#### For New VPC:
```bash
cd deployment/terraform-create-vpc

# Copy the example configuration
cp environments/example.tfvars environments/my-deployment.tfvars

# Edit the configuration file
vi environments/my-deployment.tfvars
# Required changes:
#   - aws_region = "your-region"
#   - availability_zones = ["your-region-a", "your-region-b"]
#   - okta_domain = "https://your-domain.okta.com"
#   - okta_client_id = "your-okta-client-id"

# Store Okta secret (same as above)
aws secretsmanager create-secret \
  --name bond-ai-dev-okta-secret \
  --secret-string '{"client_secret":"YOUR_OKTA_CLIENT_SECRET"}' \
  --region your-region

# Initialize Terraform
terraform init

# Deploy everything
terraform apply -var-file=environments/my-deployment.tfvars
```

### Deployment Timeline
- Initial deployment: ~30 minutes total
- Code updates: 5-20 minutes depending on what changed

## 🚀 Deploying Code Changes

Deploys are driven from the **repo root Makefile**. `terraform apply` is still
the engine underneath, but never run it by hand for a routine release — the
make targets add the guards that keep what ships equal to what was reviewed:

```bash
make deploy-plan    # guards, then terraform plan saved to tmp/ — READ IT
make deploy         # applies exactly that saved plan (never re-plans)
make deploy-status  # terraform's image tag vs what the cluster is running
make deploy-smoke   # post-deploy contract check against the live EKS service
```

### How It Works

`build-stages.tf` computes a 12-character content hash over everything
`Dockerfile.combined` ships (`bondable/**/*.py`, `flutterui/lib`,
`packages/bond_chat_ui/lib`, `requirements.txt`, `pubspec.lock`, the
nginx/supervisord/entrypoint templates). If ECR doesn't already have that tag,
apply runs `flutter build web` on the host, builds the combined image with
`docker buildx` (linux/amd64), pushes it, and rolls
`kubernetes_deployment.backend` in namespace `bond-ai` onto the new tag.
Backend and frontend ship together — it's one image.

### Why the guards exist

**The working tree is the build input.** The content hash reads files on disk,
not a git ref — a dirty tree or a feature branch would ship to dev silently.
`make deploy-check` (run automatically by `deploy-plan` and `deploy`) refuses
unless the tree is clean, you're on `main`, and `HEAD == origin/main`.
`DEPLOY_UNSAFE=1` skips only the git checks, never the tooling ones.
`make deploy` additionally refuses if `HEAD` moved since the plan was saved.

Reading the plan matters: for a code release the only expected changes are
`null_resource.build_combined_image` (replaced) and
`kubernetes_deployment.backend[0]` (in-place). **Aurora, EKS, KMS, Secrets
Manager, ACM or WAF appearing means stop and investigate** — WAF rules ride
the shared bond-platform ALB, so WAF changes hit bond-mcps traffic too.

Known guard boundary: the live tfvars file is gitignored, so variable changes
are invisible to `git status`. The saved plan embeds the resolved values —
what you read in the plan is exactly what applies.

Escape hatch: content the hash can't see (theme assets, base-image updates,
`pyproject.toml`-only changes) ships via `force_rebuild` — set
`force_rebuild = "<any new value>"` in the tfvars for one deploy.

## Terraform state

State is remote — do not keep or re-add a local `terraform.tfstate` in
`terraform-existing-vpc/`:

- Bucket: `s3://bond-ai-tfstate-119684128788`, key
  `bond-ai/existing-vpc/dev/terraform.tfstate` (versioned, KMS-encrypted,
  public-access-blocked; no lifecycle rule — version history is the DR story)
- Locking: DynamoDB table `bond-ai-tfstate-lock`
- If you see *"Backend initialization required"*, run `terraform init` once in
  `deployment/terraform-existing-vpc/` (`make deploy-plan` does this for you)

## 🚧 Maintenance Mode

Maintenance mode deploys a lightweight static "under construction" page instead of the full Flutter app. This is useful for:
- Database migrations
- Major upgrades
- Scheduled maintenance windows

### Enable Maintenance Mode

```bash
cd deployment/terraform-existing-vpc

# Basic maintenance mode with default message
terraform apply -var-file=environments/us-west-2-existing-vpc.tfvars \
  -var="maintenance_mode=true"

# With custom message
terraform apply -var-file=environments/us-west-2-existing-vpc.tfvars \
  -var="maintenance_mode=true" \
  -var="maintenance_message=We're upgrading our systems. Back online at 5pm PST."

# With custom theme (for white-label deployments)
terraform apply -var-file=environments/us-west-2-existing-vpc.tfvars \
  -var="maintenance_mode=true" \
  -var="maintenance_message=Scheduled maintenance in progress" \
  -var="theme_config_path=theme_configs/mytheme_config.json"
```

### Disable Maintenance Mode

```bash
cd deployment/terraform-existing-vpc

# Return to normal operation
terraform apply -var-file=environments/us-west-2-existing-vpc.tfvars
```

### Maintenance Mode Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `maintenance_mode` | Enable/disable maintenance page | `false` |
| `maintenance_message` | Custom message displayed to users | `"We're performing scheduled maintenance. Please check back soon."` |
| `theme_config_path` | Theme config for branding (relative to `flutterui/`) | `theme_configs/bondai_config.json` |

### Available Themes

Theme configs are located in `flutterui/theme_configs/`:
- `bondai_config.json` - Default Bond AI branding
- `mydomain.json` - my domain branding

### How It Works

When `maintenance_mode=true`:
1. A lightweight nginx container is built (takes seconds vs minutes for Flutter)
2. The maintenance page uses CSS generated from the theme config
3. Custom message is injected at build time
4. The backend remains fully operational (only frontend shows maintenance page)

The maintenance page includes:
- Themed styling matching your application
- Custom maintenance message
- Logo from the theme config
- "Under Construction" heading with construction icon

## Monitoring Deployment

Run the monitoring script in a separate terminal:

```bash
./monitor-deployment.sh
```

This shows real-time status of:
- Terraform state
- AWS resources
- Service health checks

## Configuration Files

### For Existing VPC (us-west-2)
`terraform-existing-vpc/environments/us-west-2-existing-vpc.tfvars`:
- VPC ID: vpc-0a10b710daf789382
- Region: us-west-2
- Bedrock Model: us.anthropic.claude-sonnet-4-20250514-v1:0

### For New VPC Creation
`terraform-create-vpc/environments/dev.tfvars`:
- Creates new VPC with proper subnets
- Configures NAT Gateway for private subnets
- Sets up security groups

## Key Components

### Infrastructure
- **RDS PostgreSQL**: Database with encrypted storage
- **App Runner**: Serverless container hosting for backend/frontend
- **ECR**: Docker image repositories
- **S3**: File uploads bucket
- **VPC**: Network isolation with private subnets

### Security
- **IAM Roles**: Least-privilege access
- **Secrets Manager**: Database and OAuth credentials
- **Security Groups**: Network access control
- **Bedrock Agent Role**: AI model access
- **URL Redirect Validation**: OAuth callback redirect protection

### Authentication
- **Okta OAuth2**: SSO authentication
- **JWT**: Token-based API authentication

## Deployment Timeline

### Initial Deployment (from scratch)
Typical deployment takes ~30 minutes:
1. RDS Database: ~7 minutes
2. Backend Docker build: ~2 minutes
3. Backend App Runner: ~3 minutes
4. Frontend Docker build: ~12 minutes (waits for backend)
5. Frontend App Runner: ~3 minutes
6. Post-deployment updates: ~2 minutes

### Code Updates (existing infrastructure)
Much faster - only rebuilds and redeploys changed services:
- Backend only update: ~5-7 minutes
- Frontend only update: ~15 minutes (includes build time)
- Both services: ~20 minutes

## Troubleshooting

### Common Issues

1. **Frontend service not created**: Fixed in latest version - proper dependency chain
2. **Backend URL changes**: Fixed - post-deployment update no longer recreates service
3. **CORS errors**: Backend starts with wildcard CORS, updated post-deployment
4. **VPC limits**: Use existing VPC or request limit increase

### Verification Commands

```bash
# Check service status
aws apprunner list-services --region us-west-2 \
  --query 'ServiceSummaryList[?contains(ServiceName, `bond-ai`)]'

# Test backend health
curl https://[backend-url]/health

# Check Terraform state
terraform state list

# View deployment outputs
terraform output
```

## Clean Up / Destroy Everything

To destroy all resources and start fresh:

```bash
cd deployment/terraform-existing-vpc

# Destroy all Terraform-managed infrastructure
terraform destroy -var-file=environments/us-west-2-existing-vpc.tfvars -auto-approve

# Force delete ECR repositories (they may contain images)
aws ecr delete-repository --repository-name bond-ai-dev-backend --region us-west-2 --force
aws ecr delete-repository --repository-name bond-ai-dev-frontend --region us-west-2 --force

# Optional: Clean up state files for a completely fresh start
rm -f terraform.tfstate terraform.tfstate.backup
```

### What Gets Destroyed
- App Runner services (backend & frontend)
- RDS database
- S3 uploads bucket
- IAM roles and policies
- Security groups
- VPC connector
- Secrets in Secrets Manager

### What Remains
- The existing VPC (not managed by this Terraform)
- Okta secret (if created outside Terraform)

### Redeploy After Destroy
After destroying, you can redeploy fresh:
```bash
terraform init  # If you removed state files
terraform apply -var-file=environments/us-west-2-existing-vpc.tfvars
```

## Security Configuration

### URL Redirect Domain Allowlist

The `allowed_redirect_domains` variable controls which domains are allowed for OAuth redirect callbacks. This prevents open redirect vulnerabilities.

**Default Behavior (no configuration needed):**
- `localhost`, `127.0.0.1`, `0.0.0.0` - Always allowed for development

**Custom Domains:**
If you're using a custom domain (e.g., `myapp.example.com`), add it to the allowlist:

```hcl
# In your .tfvars file
allowed_redirect_domains = "example.com,myapp.example.com"
```

**Environment Variable:**
The backend uses `ALLOWED_REDIRECT_DOMAINS` environment variable. Subdomains of allowed domains are automatically permitted.

| Variable | Description | Default |
|----------|-------------|---------|
| `allowed_redirect_domains` | Comma-separated list of additional allowed domains | `""` (empty - uses defaults only) |

## Important Notes

1. **Never commit secrets** - Use AWS Secrets Manager
2. **Always specify region** - Services are region-specific
3. **Monitor costs** - App Runner and RDS incur ongoing charges
4. **Backup database** - Before major changes
5. **Test locally first** - Use poetry for local development

## Related Documentation

- [DEPLOYMENT_FIX_GUIDE.md](./DEPLOYMENT_FIX_GUIDE.md) - Detailed fixes applied
- [DEPLOYMENT_GUIDE.md](./DEPLOYMENT_GUIDE.md) - Original deployment guide
- [../CLAUDE.md](../CLAUDE.md) - AI assistant context

## Support

For issues or questions:
1. Check the monitoring script output
2. Review CloudWatch logs
3. Consult DEPLOYMENT_FIX_GUIDE.md
4. Check AWS service limits and quotas
