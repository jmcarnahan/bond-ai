# Bond AI Deployment Session Summary
**Date:** November 12, 2025
**Goal:** Deploy Bond AI to AWS account 019593708315 (agent-space) in us-west-2
**Status:** ✅ Phase 1 Complete (Local Testing) - Ready for Phase 2 (AWS Deployment)

---

## Session Overview

This session successfully configured and tested Bond AI locally using a new AWS account (agent-space, 019593708315). We discovered and documented the new IAM-based model access system for AWS Bedrock (replacing the old console UI approach). All prerequisites are now in place for AWS deployment.

---

## Key Discoveries

### 1. **Bedrock Model Access Has Changed (Critical!)**
- **Old Way (Pre-2025):** Required visiting AWS Console → Bedrock → "Manage model access" UI
- **New Way (2025+):** Completely IAM policy-based - no console UI needed
- **Impact:** Model access must be explicitly granted via IAM resource ARNs in policies

### 2. **Model ID Formats Matter**
- **Inference Profiles (Cross-region):** `us.anthropic.claude-sonnet-4-5-20250929-v1:0`
- **Direct Models:** `anthropic.claude-sonnet-4-5-20250929-v1:0`
- **Best Practice:** Include BOTH formats in IAM policies for compatibility

### 3. **IAM Role Requirements for Bedrock Agents**
Bedrock Agents require a specific IAM role with:
1. Trust policy allowing `bedrock.amazonaws.com` to assume role
2. Managed policies: `AmazonBedrockFullAccess`, `AmazonS3FullAccess`
3. **Critical:** Inline policy with explicit model ARN access
4. AWS Marketplace subscription permissions

---

## AWS Resources Created

All resources created in account **019593708315** (agent-space) in region **us-west-2**:

### 1. S3 Bucket
```bash
Name: bondable-bedrock-agent-space-019593708315
Region: us-west-2
Versioning: Enabled
Purpose: Bedrock file storage
```

### 2. IAM Role: BondAIBedrockAgentRole
```bash
ARN: arn:aws:iam::019593708315:role/BondAIBedrockAgentRole

Trust Policy:
- Service: bedrock.amazonaws.com

Attached Managed Policies:
- AmazonBedrockFullAccess
- AmazonS3FullAccess

Inline Policy (BedrockModelAccessPolicy):
- InvokeModel permissions for Claude Sonnet 4.5 and Haiku 4.5
- Bedrock Agent operations
- AWS Marketplace subscriptions
```

### 3. Secrets Manager Secret
```bash
Name: bond-ai-dev-okta-secret
ARN: arn:aws:secretsmanager:us-west-2:019593708315:secret:bond-ai-dev-okta-secret-kLetp5
Content: {"client_secret":"xhaKsvlah6K_6khDjshL0VquUqQtU132d5NWeEN4pcH3iHVzlHzPAgUD9YLq6yi4"}
```

### 4. VPC Information (Pre-existing)
```bash
VPC ID: vpc-0f15dee1f11b1bf06
CIDR: 10.4.231.0/24

Internal Subnets (for App Runner):
- subnet-0912fc7ffa04c9f5e (internal-green-az1, us-west-2a, 10.4.231.0/27)
- subnet-0a8d3f8ed7df1f24b (internal-green-az2, us-west-2b, 10.4.231.32/27)
```

---

## Files Created/Modified

### Configuration Files

#### 1. `.env` (Modified)
**Location:** `/Users/jcarnahan/projects/bond-ai/.env`

**Changes:**
- Added agent-space account configuration (active)
- Commented out mosaic-devqa configuration for easy switching
- Updated to use Claude Sonnet 4.5 with `us.` prefix
- Changed MCP server port from 5555 to 5554

**Key Values:**
```env
AWS_REGION="us-west-2"
AWS_PROFILE="agent-space"
BEDROCK_DEFAULT_MODEL="us.anthropic.claude-sonnet-4-5-20250929-v1:0"
BEDROCK_S3_BUCKET="bondable-bedrock-agent-space-019593708315"
BEDROCK_AGENT_ROLE_ARN="arn:aws:iam::019593708315:role/BondAIBedrockAgentRole"

OKTA_DOMAIN="https://trial-9457917.okta.com"
OKTA_CLIENT_ID="0oas1uz67oWaTK8iP697"
OKTA_CLIENT_SECRET="xhaKsvlah6K_6khDjshL0VquUqQtU132d5NWeEN4pcH3iHVzlHzPAgUD9YLq6yi4"

BOND_MCP_CONFIG='{"mcpServers":{"my_client":{"url":"http://127.0.0.1:5554/mcp","transport":"streamable-http"}}}'
```

#### 2. `flutterui/.env` (Unchanged)
**Location:** `/Users/jcarnahan/projects/bond-ai/flutterui/.env`
- API_BASE_URL=http://localhost:8000
- ENABLE_AGENTS=true

### Documentation Files Created

#### 3. `LOCAL_SETUP_AGENT_SPACE.md` (New)
**Location:** `/Users/jcarnahan/projects/bond-ai/LOCAL_SETUP_AGENT_SPACE.md`

**Purpose:** Comprehensive guide for running Bond AI locally with agent-space account

**Contents:**
- All AWS resources created and their ARNs
- Environment configuration details
- Commands to run three terminals (MCP, Backend, Frontend)
- Testing procedures
- VPC/subnet information for deployment
- Troubleshooting commands
- Instructions for switching back to mosaic-devqa

#### 4. `AWS_BEDROCK_SETUP_GUIDE.md` (New)
**Location:** `/Users/jcarnahan/projects/bond-ai/AWS_BEDROCK_SETUP_GUIDE.md`

**Purpose:** Step-by-step guide to replicate AWS setup in any new account

**Contents:**
- Complete bash commands for all AWS resources
- IAM policy JSON with explanations
- Model access verification tests
- Differences between old and new Bedrock access model
- Troubleshooting guide
- Terraform integration notes
- Summary checklist

### Terraform Configuration

#### 5. `deployment/terraform-existing-vpc/environments/agent-space.tfvars` (New)
**Location:** `/Users/jcarnahan/projects/bond-ai/deployment/terraform-existing-vpc/environments/agent-space.tfvars`

**Purpose:** Terraform variables for agent-space deployment

**Key Configuration:**
```hcl
aws_region   = "us-west-2"
environment  = "dev"
project_name = "bond-ai"

existing_vpc_id = "vpc-0f15dee1f11b1bf06"

okta_domain      = "https://trial-9457917.okta.com"
okta_client_id   = "0oas1uz67oWaTK8iP697"
okta_secret_name = "bond-ai-dev-okta-secret"

bedrock_default_model = "us.anthropic.claude-sonnet-4-5-20250929-v1:0"
bedrock_agent_role_name = "BondAIBedrockAgentRole"

db_instance_class    = "db.t3.micro"
db_allocated_storage = 20
```

---

## Local Testing Results

### ✅ Verified Working
1. **MCP Server** - Running on port 5554
2. **Backend API** - Running on port 8000, connected to AWS agent-space
3. **Frontend** - Running on port 5000, accessible in Chrome
4. **Okta Login** - Successfully authenticating users
5. **Agent Creation** - Can create agents in Bedrock
6. **Chat Functionality** - Successfully sending messages and receiving responses from Claude Sonnet 4.5
7. **Model Invocation Test** - Confirmed via Python boto3 script

### Testing Commands Used
```bash
# Terminal 1 - MCP Server
fastmcp run scripts/sample_mcp_server.py --transport streamable-http --port 5554

# Terminal 2 - Backend
uvicorn bondable.rest.main:app --reload --host 0.0.0.0 --port 8000

# Terminal 3 - Frontend
cd flutterui && flutter run -d chrome --web-port=5000 --target lib/main.dart
```

---

## Phase 2: Deployment Plan

### Prerequisites (Already Complete)
- ✅ AWS resources created (S3, IAM role, Secrets Manager)
- ✅ Terraform configuration file created
- ✅ Local testing successful
- ✅ Model access verified

### Deployment Steps

#### Step 1: Review and Update Terraform Configuration
**File:** `deployment/terraform-existing-vpc/environments/agent-space.tfvars`

**Verify:**
- VPC ID is correct
- Subnet IDs are appropriate
- Okta configuration matches
- Model ID is correct
- All ARNs reference account 019593708315

#### Step 2: Initialize Terraform
```bash
cd deployment/terraform-existing-vpc

# Initialize Terraform (first time only)
terraform init

# Optionally configure backend for state management
# (Recommended for production, optional for testing)
```

#### Step 3: Review Terraform Plan
```bash
# Review what will be created
terraform plan -var-file=environments/agent-space.tfvars

# Expected resources to be created:
# - RDS PostgreSQL database (db.t3.micro)
# - ECR repositories (backend, frontend)
# - App Runner services (backend, frontend)
# - VPC connector for App Runner
# - Security groups
# - IAM roles for App Runner
# - Database secret in Secrets Manager
# - S3 bucket for uploads (separate from Bedrock bucket)
```

#### Step 4: Deploy Infrastructure
```bash
# Apply Terraform configuration
terraform apply -var-file=environments/agent-space.tfvars -auto-approve

# Deployment will take ~30-45 minutes:
# - RDS Database: ~7 minutes
# - Backend Docker build: ~2 minutes
# - Backend App Runner: ~3 minutes
# - Frontend Docker build: ~12 minutes
# - Frontend App Runner: ~3 minutes
# - Post-deployment updates: ~2 minutes
```

#### Step 5: Capture Deployment Outputs
```bash
# Get deployment outputs
terraform output

# Important outputs to save:
# - backend_url: Backend App Runner service URL
# - frontend_url: Frontend App Runner service URL
# - database_endpoint: RDS endpoint
# - s3_bucket: Uploads S3 bucket
```

#### Step 6: Post-Deployment Configuration

**A. Update Okta Application**
1. Go to Okta Admin Console: https://trial-9457917.okta.com/admin/app/oidc_client/instance/0oas1uz67oWaTK8iP697#tab-general
2. Add backend callback URL to "Sign-in redirect URIs":
   ```
   https://<BACKEND_URL>/auth/okta/callback
   ```
3. Save changes in Okta

**B. Test Deployed Application**
```bash
# Test backend health
curl https://<BACKEND_URL>/health

# Test frontend access
curl https://<FRONTEND_URL>

# Check App Runner service status
aws apprunner list-services --region us-west-2 --query 'ServiceSummaryList[?contains(ServiceName, `bond-ai`)]'
```

#### Step 7: Verification
1. Access frontend URL in browser
2. Login with Okta
3. Create a test agent
4. Send test message
5. Verify response from Claude Sonnet 4.5

---

## Important Notes for Deployment

### IAM Considerations
1. **BondAIBedrockAgentRole must exist** before Terraform runs (already created manually)
2. Terraform will create additional App Runner instance roles
3. App Runner roles need to be able to pass BondAIBedrockAgentRole to Bedrock

### Database Considerations
1. Initial RDS deployment takes ~7 minutes
2. Database credentials stored in Secrets Manager
3. Backend auto-migrates database schema on first run
4. Database uses private subnets only (no public access)

### Network Considerations
1. App Runner uses VPC connector for private subnet access
2. Backend needs access to:
   - RDS database (private subnet)
   - S3 buckets (via VPC endpoint or NAT)
   - Bedrock service (via VPC endpoint or NAT)
   - Secrets Manager (via VPC endpoint or NAT)
3. Frontend is publicly accessible but backend is internal

### Cost Estimate (Monthly)
```
RDS PostgreSQL (db.t3.micro):    ~$15-16
Backend App Runner (0.25 vCPU):  ~$15-20
Frontend App Runner (0.25 vCPU): ~$15-20
NAT Gateway:                     ~$45
S3 & ECR:                        <$2
Bedrock API usage:               Variable (pay per token)
-------------------------------------------
Total Infrastructure:            ~$90-100/month
```

---

## Troubleshooting Guide

### Common Issues During Deployment

#### Issue 1: Terraform Backend State
**Symptom:** Terraform state file grows large or gets corrupted
**Solution:** Configure S3 backend for state management (see `deployment/terraform-existing-vpc/backend.tf`)

#### Issue 2: ECR Image Build Fails
**Symptom:** Docker build timeout or permission denied
**Solution:**
- Ensure Docker is running
- Check AWS credentials are valid
- Increase timeout in Terraform if needed

#### Issue 3: App Runner Service Won't Start
**Symptom:** Service status shows "CREATE_FAILED"
**Solution:**
- Check CloudWatch logs for the service
- Verify environment variables are set correctly
- Ensure IAM role has required permissions
- Check database connection (security groups)

#### Issue 4: Bedrock Access Denied in Deployed App
**Symptom:** Same as we saw locally - "accessDeniedException"
**Solution:**
- Verify BondAIBedrockAgentRole exists and has correct policies
- Check App Runner instance role can pass BondAIBedrockAgentRole
- Ensure model ARNs in IAM policy match model being used

#### Issue 5: Frontend Can't Reach Backend
**Symptom:** CORS errors or network timeouts
**Solution:**
- Check CORS configuration in backend includes frontend URL
- Verify App Runner services are in same VPC
- Check security groups allow communication

---

## Key Commands Reference

### AWS CLI Commands
```bash
# Check AWS credentials
AWS_PROFILE=agent-space aws sts get-caller-identity

# List Bedrock models
AWS_PROFILE=agent-space aws bedrock list-foundation-models --region us-west-2 --by-provider anthropic

# Test Bedrock access
AWS_PROFILE=agent-space aws bedrock-runtime invoke-model \
  --model-id us.anthropic.claude-sonnet-4-5-20250929-v1:0 \
  --body '{"anthropic_version":"bedrock-2023-05-31","max_tokens":100,"messages":[{"role":"user","content":"test"}]}' \
  /tmp/output.json

# Check App Runner services
AWS_PROFILE=agent-space aws apprunner list-services --region us-west-2

# View CloudWatch logs
AWS_PROFILE=agent-space aws logs tail /aws/apprunner/<service-name> --follow

# Check RDS status
AWS_PROFILE=agent-space aws rds describe-db-instances --region us-west-2

# List secrets
AWS_PROFILE=agent-space aws secretsmanager list-secrets --region us-west-2
```

### Terraform Commands
```bash
cd deployment/terraform-existing-vpc

# Initialize
terraform init

# Validate configuration
terraform validate

# Plan deployment
terraform plan -var-file=environments/agent-space.tfvars

# Apply deployment
terraform apply -var-file=environments/agent-space.tfvars -auto-approve

# Show outputs
terraform output

# Show specific output
terraform output backend_url

# Destroy everything (CAREFUL!)
terraform destroy -var-file=environments/agent-space.tfvars -auto-approve
```

### Local Testing Commands
```bash
# Start MCP Server
fastmcp run scripts/sample_mcp_server.py --transport streamable-http --port 5554

# Start Backend
uvicorn bondable.rest.main:app --reload --host 0.0.0.0 --port 8000

# Start Frontend
cd flutterui && flutter run -d chrome --web-port=5000 --target lib/main.dart

# Kill port processes
lsof -ti:5554 | xargs kill -9
lsof -ti:8000 | xargs kill -9
lsof -ti:5000 | xargs kill -9
```

---

## Environment Switching

### To Switch to Agent-Space (Current)
In `.env`, ensure these lines are active:
```env
# ===== AGENT-SPACE ACCOUNT (019593708315) =====
AWS_REGION="us-west-2"
AWS_PROFILE="agent-space"
BEDROCK_DEFAULT_MODEL="us.anthropic.claude-sonnet-4-5-20250929-v1:0"
BEDROCK_S3_BUCKET="bondable-bedrock-agent-space-019593708315"
BEDROCK_AGENT_ROLE_ARN="arn:aws:iam::019593708315:role/BondAIBedrockAgentRole"
```

### To Switch Back to Mosaic-DevQA
In `.env`, comment out agent-space section and uncomment:
```env
# ===== MOSAIC-DEVQA ACCOUNT (767397995923) - COMMENTED OUT =====
# AWS_REGION="us-west-2"
# AWS_PROFILE="mosaic-devqa"
# BEDROCK_DEFAULT_MODEL="us.anthropic.claude-3-7-sonnet-20250219-v1:0"
# BEDROCK_S3_BUCKET="bondable-bedrock-mosaic-dev"
# BEDROCK_AGENT_ROLE_ARN="arn:aws:iam::767397995923:role/BondAIBedrockAgentRole"
```

---

## Next Session Checklist

Before starting deployment in new session:

- [ ] Review this document completely
- [ ] Verify AWS CLI is configured with agent-space profile
- [ ] Confirm Terraform is installed (v1.0+)
- [ ] Check Docker is running
- [ ] Verify you have access to account 019593708315
- [ ] Have Okta admin credentials ready for post-deployment config
- [ ] Review `deployment/terraform-existing-vpc/environments/agent-space.tfvars`
- [ ] Read `AWS_BEDROCK_SETUP_GUIDE.md` for IAM details
- [ ] Optionally: Set up Terraform S3 backend for state management

---

## Success Criteria

### Phase 1: Local Testing (✅ COMPLETE)
- [x] Can login with Okta
- [x] Can create agents
- [x] Can send messages to agents
- [x] Receive responses from Claude Sonnet 4.5
- [x] MCP server integration works

### Phase 2: AWS Deployment (Next Session)
- [ ] Terraform apply completes successfully
- [ ] Backend App Runner service is running and healthy
- [ ] Frontend App Runner service is running and accessible
- [ ] RDS database is created and accessible from backend
- [ ] Can login to deployed frontend with Okta
- [ ] Can create agents in deployed environment
- [ ] Can send messages and receive responses
- [ ] All CloudWatch logs show healthy operation

---

## Related Documentation Files

1. **LOCAL_SETUP_AGENT_SPACE.md** - Local development guide
2. **AWS_BEDROCK_SETUP_GUIDE.md** - AWS resource setup (for replication)
3. **deployment/README.md** - General deployment documentation
4. **deployment/DEPLOYMENT_GUIDE.md** - Original deployment guide
5. **deployment/terraform-existing-vpc/environments/agent-space.tfvars** - Terraform config

---

## Session Summary

**What We Accomplished:**
1. ✅ Discovered and documented new IAM-based Bedrock model access
2. ✅ Created all AWS prerequisites (S3, IAM, Secrets Manager)
3. ✅ Configured local environment for agent-space account
4. ✅ Successfully tested locally (MCP + Backend + Frontend)
5. ✅ Verified Bedrock model invocation
6. ✅ Created Terraform configuration for deployment
7. ✅ Documented everything for replication

**Ready For:**
- AWS deployment via Terraform
- Can be replicated in any new AWS account using the guides

**Estimated Time for Phase 2:**
- Terraform deployment: ~45 minutes
- Testing and verification: ~15 minutes
- **Total: ~1 hour**

---

**End of Session Summary**
