# McAfee Agentic Studio - DEV Environment Deployment Guide

**Deployment Date:** November 12, 2025
**AWS Account:** 019593708315 (agent-space)
**AWS Region:** us-west-2
**Environment:** dev
**Status:** ✅ Successfully Deployed and Operational

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Deployed Infrastructure](#deployed-infrastructure)
3. [Prerequisites Setup](#prerequisites-setup)
4. [Critical Configuration Insights](#critical-configuration-insights)
5. [Terraform Deployment Process](#terraform-deployment-process)
6. [Deployment Fixes Applied](#deployment-fixes-applied)
7. [Post-Deployment Configuration](#post-deployment-configuration)
8. [Verification & Testing](#verification--testing)
9. [Local Development Setup](#local-development-setup)
10. [Troubleshooting Guide](#troubleshooting-guide)
11. [Cost Analysis](#cost-analysis)
12. [Reference Commands](#reference-commands)

---

## Executive Summary

This document captures the complete deployment of Bond AI (McAfee Agentic Studio) to AWS account 019593708315. The deployment uses AWS App Runner for containerized services, RDS PostgreSQL for data persistence, and AWS Bedrock for AI model access (Claude Sonnet 4.5).

### Key Achievement
Successfully deployed a production-ready AI agent platform with:
- ✅ Containerized backend and frontend services
- ✅ Managed PostgreSQL database
- ✅ AWS Bedrock integration with Claude Sonnet 4.5
- ✅ Okta OAuth authentication
- ✅ Secure VPC networking
- ✅ Automated infrastructure via Terraform

### Deployment Timeline
- **Local Testing:** Completed November 12, 2025
- **Terraform Deployment:** ~30 minutes
- **Post-Deployment Updates:** ~5 minutes
- **Total Time:** ~35 minutes

---

## Deployed Infrastructure

### Application Services

#### Backend Service (App Runner)
```
URL:        https://rqs8cicg8h.us-west-2.awsapprunner.com
Service:    bond-ai-dev-backend
Status:     RUNNING
Spec:       0.25 vCPU, 512 MB memory
Runtime:    Python 3.11 with FastAPI
ECR Image:  019593708315.dkr.ecr.us-west-2.amazonaws.com/bond-ai-dev-backend
```

**Key Endpoints:**
- Health: `/health`
- API Docs: `/docs`
- Okta Callback: `/auth/okta/callback`

#### Frontend Service (App Runner)
```
URL:        https://jid5jmztei.us-west-2.awsapprunner.com
Service:    bond-ai-dev-frontend
Status:     RUNNING
Spec:       0.25 vCPU, 512 MB memory
Runtime:    Flutter Web with nginx
ECR Image:  019593708315.dkr.ecr.us-west-2.amazonaws.com/bond-ai-dev-frontend
```

### Database

#### RDS PostgreSQL
```
Endpoint:         bond-ai-dev-db.cb4kk2sa2lrb.us-west-2.rds.amazonaws.com:5432
Instance Class:   db.t3.micro
Engine:           PostgreSQL 16.4
Storage:          20 GB (gp3)
Multi-AZ:         No
Backup Retention: 7 days
Security:         Private subnets only, no public access
```

**Credentials Location:**
- Secrets Manager: `bond-ai-dev-db-20251112200642294900000001`
- ARN: `arn:aws:secretsmanager:us-west-2:019593708315:secret:bond-ai-dev-db-20251112200642294900000001-I7dOwA`

### Networking

#### VPC Configuration
```
VPC ID:   vpc-0f15dee1f11b1bf06
CIDR:     10.4.231.0/24
Region:   us-west-2
Zones:    us-west-2a, us-west-2b
```

#### App Runner VPC Connector
```
ARN:      arn:aws:apprunner:us-west-2:019593708315:vpcconnector/bond-ai-dev-connector/1/34a883531e5b439faf91776eced71a50
Subnets:  subnet-0912fc7ffa04c9f5e (internal-green-az1, us-west-2a)
          subnet-0a8d3f8ed7df1f24b (internal-green-az2, us-west-2b)
```

#### Security Groups
```
Database SG:  sg-093898a78113504b2
- Allows inbound PostgreSQL (5432) from App Runner services
- No public internet access
```

### Storage

#### S3 Buckets
```
Bedrock Files:  bondable-bedrock-agent-space-019593708315
                - Purpose: Bedrock agent file storage
                - Versioning: Enabled

Uploads:        bond-ai-dev-uploads-019593708315
                - Purpose: User uploads and application files
                - Versioning: Disabled
```

#### ECR Repositories
```
Backend:   019593708315.dkr.ecr.us-west-2.amazonaws.com/bond-ai-dev-backend
Frontend:  019593708315.dkr.ecr.us-west-2.amazonaws.com/bond-ai-dev-frontend
```

### Secrets Management

#### Secrets Manager Resources
```
1. Database Credentials
   Name: bond-ai-dev-db-20251112200642294900000001
   ARN:  arn:aws:secretsmanager:us-west-2:019593708315:secret:bond-ai-dev-db-20251112200642294900000001-I7dOwA
   Keys: username, password, host, port, dbname

2. Okta Client Secret
   Name: bond-ai-dev-okta-secret
   ARN:  arn:aws:secretsmanager:us-west-2:019593708315:secret:bond-ai-dev-okta-secret-kLetp5
   Keys: client_secret

3. JWT Secret
   Value: MOQ5CXFlgPlKkWbyzIrCPZFXodd1ZUhFq05OrvA3DG7wlH0fduNMn6Wn3zP5gsUe
```

### IAM Roles

#### Bedrock Agent Role
```
Name:  BondAIBedrockAgentRole
ARN:   arn:aws:iam::019593708315:role/BondAIBedrockAgentRole

Trust Policy:
- Service: bedrock.amazonaws.com

Managed Policies:
- AmazonBedrockFullAccess
- AmazonS3FullAccess

Inline Policies:
- BedrockModelAccessPolicy (see details below)
```

#### App Runner Instance Roles
- Backend instance role with ECS, ECR, Secrets Manager access
- Frontend instance role with ECS, ECR access
- Both roles have permission to pass BondAIBedrockAgentRole

---

## Prerequisites Setup

Before deploying to AWS, several manual prerequisites were created. These steps are documented for replication in new accounts.

### Step 1: Create Bedrock S3 Bucket

```bash
# Set environment variables
export AWS_PROFILE=agent-space
export AWS_REGION=us-west-2
export AWS_ACCOUNT_ID=019593708315

# Create bucket (name must be globally unique)
aws s3 mb s3://bondable-bedrock-agent-space-${AWS_ACCOUNT_ID} --region ${AWS_REGION}

# Enable versioning
aws s3api put-bucket-versioning \
  --bucket bondable-bedrock-agent-space-${AWS_ACCOUNT_ID} \
  --versioning-configuration Status=Enabled \
  --region ${AWS_REGION}
```

### Step 2: Create IAM Role for Bedrock

#### Trust Policy

Create file: `/tmp/bedrock-trust-policy.json`
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Service": "bedrock.amazonaws.com"
      },
      "Action": "sts:AssumeRole"
    }
  ]
}
```

#### Create Role

```bash
aws iam create-role \
  --role-name BondAIBedrockAgentRole \
  --assume-role-policy-document file:///tmp/bedrock-trust-policy.json \
  --description "Role for Bond AI Bedrock Agents"
```

#### Attach Managed Policies

```bash
# Bedrock access
aws iam attach-role-policy \
  --role-name BondAIBedrockAgentRole \
  --policy-arn arn:aws:iam::aws:policy/AmazonBedrockFullAccess

# S3 access
aws iam attach-role-policy \
  --role-name BondAIBedrockAgentRole \
  --policy-arn arn:aws:iam::aws:policy/AmazonS3FullAccess
```

#### Add Model Access Inline Policy

Create file: `/tmp/bedrock-model-access-policy.json`
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "BedrockModelInvocation",
      "Effect": "Allow",
      "Action": [
        "bedrock:InvokeModel",
        "bedrock:InvokeModelWithResponseStream"
      ],
      "Resource": [
        "arn:aws:bedrock:us-west-2::foundation-model/us.anthropic.claude-sonnet-4-5-20250929-v1:0",
        "arn:aws:bedrock:us-west-2::foundation-model/anthropic.claude-sonnet-4-5-20250929-v1:0",
        "arn:aws:bedrock:us-west-2::foundation-model/us.anthropic.claude-haiku-4-5-20251001-v1:0",
        "arn:aws:bedrock:us-west-2::foundation-model/anthropic.claude-haiku-4-5-20251001-v1:0",
        "arn:aws:bedrock:*::foundation-model/anthropic.*",
        "arn:aws:bedrock:*::foundation-model/us.anthropic.*"
      ]
    },
    {
      "Sid": "BedrockAgentOperations",
      "Effect": "Allow",
      "Action": [
        "bedrock:CreateAgent",
        "bedrock:UpdateAgent",
        "bedrock:DeleteAgent",
        "bedrock:GetAgent",
        "bedrock:ListAgents",
        "bedrock:PrepareAgent",
        "bedrock:InvokeAgent"
      ],
      "Resource": "*"
    },
    {
      "Sid": "MarketplaceSubscriptions",
      "Effect": "Allow",
      "Action": [
        "aws-marketplace:ViewSubscriptions",
        "aws-marketplace:Subscribe",
        "aws-marketplace:Unsubscribe"
      ],
      "Resource": "*"
    }
  ]
}
```

Apply policy:
```bash
aws iam put-role-policy \
  --role-name BondAIBedrockAgentRole \
  --policy-name BedrockModelAccessPolicy \
  --policy-document file:///tmp/bedrock-model-access-policy.json
```

### Step 3: Create Okta Secret

```bash
aws secretsmanager create-secret \
  --name bond-ai-dev-okta-secret \
  --secret-string '{"client_secret":"xhaKsvlah6K_6khDjshL0VquUqQtU132d5NWeEN4pcH3iHVzlHzPAgUD9YLq6yi4"}' \
  --region ${AWS_REGION}
```

### Step 4: Verify Prerequisites

```bash
# Verify IAM role
aws iam get-role --role-name BondAIBedrockAgentRole

# List role policies
aws iam list-attached-role-policies --role-name BondAIBedrockAgentRole
aws iam list-role-policies --role-name BondAIBedrockAgentRole

# Verify S3 bucket
aws s3 ls s3://bondable-bedrock-agent-space-${AWS_ACCOUNT_ID}

# Verify secret
aws secretsmanager describe-secret --secret-id bond-ai-dev-okta-secret
```

---

## Critical Configuration Insights

### 🔥 Bedrock Model Access - Major Change in 2025

**CRITICAL DISCOVERY:** AWS Bedrock model access has fundamentally changed from console-based to IAM policy-based.

#### Old Method (Pre-2025)
- Required manual steps in AWS Console
- Navigate to Bedrock → "Manage model access"
- Request access per model via UI
- Wait for approval

#### New Method (2025+)
- ✅ **Fully IAM-based** - no console UI needed
- ✅ Model access controlled via IAM resource ARNs
- ✅ Can be fully automated in Terraform/CloudFormation
- ✅ Immediate access (no approval wait)

#### Model ID Formats

**Two formats must both be included in IAM policies:**

1. **Inference Profiles (cross-region):**
   ```
   us.anthropic.claude-sonnet-4-5-20250929-v1:0
   ```

2. **Direct Models (region-specific):**
   ```
   anthropic.claude-sonnet-4-5-20250929-v1:0
   ```

**Resource ARN Format:**
```
arn:aws:bedrock:{region}::foundation-model/{model-id}
```
Note: The account ID slot is empty (::) for foundation models

**Example IAM Resource ARNs:**
```json
"Resource": [
  "arn:aws:bedrock:us-west-2::foundation-model/us.anthropic.claude-sonnet-4-5-20250929-v1:0",
  "arn:aws:bedrock:us-west-2::foundation-model/anthropic.claude-sonnet-4-5-20250929-v1:0",
  "arn:aws:bedrock:*::foundation-model/anthropic.*",
  "arn:aws:bedrock:*::foundation-model/us.anthropic.*"
]
```

### Subnet Configuration

**Issue Encountered:** Initial deployment used incorrect subnet IDs from a different VPC.

**Solution Applied:** Updated `data-sources.tf` to use correct internal-green subnets:
```hcl
app_runner_subnet_ids = [
  "subnet-0912fc7ffa04c9f5e",  # internal-green-az1 (us-west-2a, 10.4.231.0/27)
  "subnet-0a8d3f8ed7df1f24b"   # internal-green-az2 (us-west-2b, 10.4.231.32/27)
]
```

**Why These Subnets:**
- Named "internal-green" for internal application services
- Cover both availability zones for high availability
- Appropriate size (/27 = 32 IPs each)
- Have route to NAT Gateway for outbound internet access

### VPC Endpoints

**Issue Encountered:** Attempted to create S3 VPC endpoint when one already existed.

**Solution Applied:** Commented out S3 VPC endpoint creation in `vpc-endpoints.tf`:
```hcl
# VPC Endpoint for S3 - COMMENTED OUT because S3 VPC endpoints already exist in this VPC
# resource "aws_vpc_endpoint" "s3" {
#   ...
# }
```

**Existing VPC Endpoints in agent-space VPC:**
- 2 S3 Gateway endpoints (already configured)
- These provide S3 access without NAT Gateway charges

---

## Terraform Deployment Process

### Terraform Configuration File

**File:** `deployment/terraform-existing-vpc/environments/agent-space.tfvars`

```hcl
# AWS Configuration
aws_region   = "us-west-2"
environment  = "dev"
project_name = "bond-ai"

# VPC Configuration
existing_vpc_id = "vpc-0f15dee1f11b1bf06"

# Okta Configuration
okta_domain      = "https://trial-9457917.okta.com"
okta_client_id   = "0oas1uz67oWaTK8iP697"
okta_secret_name = "bond-ai-dev-okta-secret"

# Bedrock Configuration
bedrock_default_model    = "us.anthropic.claude-sonnet-4-5-20250929-v1:0"
bedrock_s3_bucket        = "bondable-bedrock-agent-space-019593708315"
bedrock_agent_role_name  = "BondAIBedrockAgentRole"

# Database Configuration
db_instance_class    = "db.t3.micro"
db_allocated_storage = 20
db_engine_version    = "16.4"

# Application Configuration
backend_cpu    = 256   # 0.25 vCPU
backend_memory = 512   # 512 MB
frontend_cpu   = 256
frontend_memory = 512
```

### Deployment Steps

#### 1. Initialize Terraform

```bash
cd deployment/terraform-existing-vpc

# Initialize Terraform (downloads providers)
AWS_PROFILE=agent-space terraform init

# Create workspace for state isolation
AWS_PROFILE=agent-space terraform workspace new agent-space
AWS_PROFILE=agent-space terraform workspace select agent-space
```

**Workspace Benefits:**
- Isolates state from other environments
- Prevents conflicts with existing deployments
- Allows parallel environments in same backend

#### 2. Review Terraform Plan

```bash
# Generate execution plan
AWS_PROFILE=agent-space terraform plan \
  -var-file=environments/agent-space.tfvars \
  -out=tfplan

# Review resources to be created
# Expected: ~38 resources initially
```

**Key Resources Created:**
- RDS PostgreSQL instance and subnet group
- ECR repositories (backend, frontend)
- App Runner services (backend, frontend)
- VPC connector for App Runner
- Security groups
- IAM roles for App Runner
- Database secret in Secrets Manager
- S3 bucket for uploads
- Null resources for Docker builds

#### 3. Apply Terraform Configuration

```bash
# Apply the plan (in background due to long runtime)
AWS_PROFILE=agent-space terraform apply tfplan
```

**Deployment Timeline:**
```
Stage                        Duration    Status
──────────────────────────────────────────────────
ECR Repositories             ~30s        ✅
S3 Bucket                    ~15s        ✅
Security Groups              ~30s        ✅
VPC Connector                ~2min       ✅
RDS Database                 ~7min       ✅
Database Secret              ~10s        ✅
Backend Docker Build         ~2min       ✅
Backend App Runner           ~3min       ✅
Frontend Docker Build        ~12min      ✅
Frontend App Runner          ~3min       ✅
Post-Deployment Updates      ~2min       ✅
──────────────────────────────────────────────────
Total Time                   ~30min
```

#### 4. Capture Deployment Outputs

```bash
# Get all outputs
AWS_PROFILE=agent-space terraform output

# Get specific output
AWS_PROFILE=agent-space terraform output backend_url
AWS_PROFILE=agent-space terraform output frontend_url

# Get outputs as JSON for scripting
AWS_PROFILE=agent-space terraform output -json > deployment-outputs.json
```

**Key Outputs:**
```
backend_url:                  https://rqs8cicg8h.us-west-2.awsapprunner.com
frontend_url:                 https://jid5jmztei.us-west-2.awsapprunner.com
database_endpoint:            bond-ai-dev-db.cb4kk2sa2lrb.us-west-2.rds.amazonaws.com:5432
database_secret_name:         bond-ai-dev-db-20251112200642294900000001
s3_bucket_name:               bond-ai-dev-uploads-019593708315
ecr_backend_repository_url:   019593708315.dkr.ecr.us-west-2.amazonaws.com/bond-ai-dev-backend
ecr_frontend_repository_url:  019593708315.dkr.ecr.us-west-2.amazonaws.com/bond-ai-dev-frontend
```

---

## Deployment Fixes Applied

### Fix 1: Subnet Configuration (data-sources.tf)

**Error:**
```
Error: creating App Runner VPC Connector: InvalidRequestException: Failed to get
subnets details from subnet ids. SubnetIDs: [subnet-050691e25d4a7681e,
subnet-0374d7b91b2054239]
```

**Root Cause:**
- Hardcoded subnet IDs from different VPC (mosaic-devqa)
- These subnets don't exist in agent-space VPC

**Fix Applied:**
Updated `deployment/terraform-existing-vpc/data-sources.tf` lines 56-61:
```hcl
# Select subnets for App Runner VPC connector
# Using internal-green subnets in both AZs for agent-space VPC
app_runner_subnet_ids = [
  "subnet-0912fc7ffa04c9f5e",  # internal-green-az1 (us-west-2a, 10.4.231.0/27)
  "subnet-0a8d3f8ed7df1f24b"   # internal-green-az2 (us-west-2b, 10.4.231.32/27)
]
```

**Verification:**
```bash
# Verify subnets exist
aws ec2 describe-subnets \
  --subnet-ids subnet-0912fc7ffa04c9f5e subnet-0a8d3f8ed7df1f24b \
  --query 'Subnets[*].[SubnetId,AvailabilityZone,CidrBlock,Tags[?Key==`Name`].Value|[0]]' \
  --output table
```

### Fix 2: VPC Endpoint Configuration (vpc-endpoints.tf)

**Error:**
```
Error: creating VPC Endpoint (vpce-xxxxx): InvalidParameter: route table
rtb-0eb17f3b2bcc8022b already has a route with destination-prefix-list-id
pl-68a54001
```

**Root Cause:**
- VPC already has 2 S3 VPC endpoints configured
- Terraform tried to create duplicate endpoint

**Fix Applied:**
Commented out S3 VPC endpoint in `deployment/terraform-existing-vpc/vpc-endpoints.tf`:
```hcl
# VPC Endpoint for S3 - COMMENTED OUT because S3 VPC endpoints already exist in this VPC
# resource "aws_vpc_endpoint" "s3" {
#   vpc_id            = data.aws_vpc.existing.id
#   service_name      = "com.amazonaws.${var.aws_region}.s3"
#   vpc_endpoint_type = "Gateway"
#   route_table_ids   = concat(data.aws_route_tables.private.ids, [data.aws_route_table.main.id])
#
#   tags = {
#     Name = "${var.project_name}-${var.environment}-s3-endpoint"
#   }
# }
```

**Verification:**
```bash
# List existing VPC endpoints
aws ec2 describe-vpc-endpoints \
  --filters "Name=vpc-id,Values=vpc-0f15dee1f11b1bf06" \
  --query 'VpcEndpoints[*].[VpcEndpointId,ServiceName,State]' \
  --output table
```

### Fix 3: Terraform State Management

**Issue:**
- Existing Terraform state from mosaic-devqa (account 767397995923)
- State conflicts with agent-space deployment

**Solution:**
Created isolated Terraform workspace:
```bash
terraform workspace new agent-space
terraform workspace select agent-space
```

**Benefits:**
- Clean separation of state files
- No risk of destroying mosaic-devqa resources
- Can switch between environments easily

---

## Post-Deployment Configuration

### 1. Update Okta Application

**Okta Admin Console:**
https://trial-9457917.okta.com/admin/app/oidc_client/instance/0oas1uz67oWaTK8iP697#tab-general

**Action Required:**
Add backend callback URL to "Sign-in redirect URIs":
```
https://rqs8cicg8h.us-west-2.awsapprunner.com/auth/okta/callback
```

**Steps:**
1. Login to Okta Admin Console
2. Navigate to Applications → Applications
3. Select Bond AI application
4. Click "Edit" on General Settings
5. Add callback URL to "Sign-in redirect URIs"
6. Click "Save"

### 2. Verify Backend Health

```bash
# Test health endpoint
curl https://rqs8cicg8h.us-west-2.awsapprunner.com/health

# Expected response:
{
  "status": "healthy",
  "database": "connected",
  "bedrock": "available"
}
```

### 3. Verify Frontend Accessibility

```bash
# Test frontend
curl -I https://jid5jmztei.us-west-2.awsapprunner.com

# Expected response:
HTTP/2 200
content-type: text/html
```

**Browser Test:**
Open https://jid5jmztei.us-west-2.awsapprunner.com in browser

---

## Verification & Testing

### Backend Verification

#### Health Check
```bash
curl https://rqs8cicg8h.us-west-2.awsapprunner.com/health
```

#### API Documentation
```
https://rqs8cicg8h.us-west-2.awsapprunner.com/docs
```

#### Database Connection
```bash
# Via AWS CLI (from local machine)
AWS_PROFILE=agent-space aws secretsmanager get-secret-value \
  --secret-id bond-ai-dev-db-20251112200642294900000001 \
  --query SecretString --output text | jq

# Connection test (from within VPC)
psql "postgresql://username:password@bond-ai-dev-db.cb4kk2sa2lrb.us-west-2.rds.amazonaws.com:5432/bondai"
```

### Frontend Verification

#### Application Access
```
URL: https://jid5jmztei.us-west-2.awsapprunner.com
```

#### Browser Testing
1. Open frontend URL
2. Verify login button appears
3. Click login
4. Redirects to Okta
5. Login with credentials
6. Redirects back to application
7. Verify user dashboard loads

### App Runner Service Status

```bash
# List all App Runner services
AWS_PROFILE=agent-space aws apprunner list-services \
  --region us-west-2 \
  --query 'ServiceSummaryList[?contains(ServiceName, `bond-ai`)]'

# Describe backend service
AWS_PROFILE=agent-space aws apprunner describe-service \
  --service-arn arn:aws:apprunner:us-west-2:019593708315:service/bond-ai-dev-backend/xxxxx

# Describe frontend service
AWS_PROFILE=agent-space aws apprunner describe-service \
  --service-arn arn:aws:apprunner:us-west-2:019593708315:service/bond-ai-dev-frontend/xxxxx
```

### CloudWatch Logs

```bash
# Backend logs
AWS_PROFILE=agent-space aws logs tail \
  /aws/apprunner/bond-ai-dev-backend/service \
  --follow

# Frontend logs
AWS_PROFILE=agent-space aws logs tail \
  /aws/apprunner/bond-ai-dev-frontend/service \
  --follow
```

### End-to-End Testing

#### Test Agent Creation
1. Login to application
2. Navigate to Agents section
3. Click "Create Agent"
4. Fill in agent details:
   - Name: Test Agent
   - Model: Claude Sonnet 4.5
   - Instructions: "You are a helpful assistant"
5. Click "Create"
6. Verify agent appears in list

#### Test Chat Functionality
1. Select test agent
2. Start new conversation
3. Send message: "Hello, how are you?"
4. Verify response received from Claude Sonnet 4.5
5. Test follow-up questions
6. Verify conversation history persists

---

## Local Development Setup

### Prerequisites

- Python 3.11+
- Flutter SDK 3.x
- Docker Desktop
- AWS CLI v2
- fastmcp Python package

### Environment Configuration

**File:** `.env`

```env
# ===== AGENT-SPACE ACCOUNT (019593708315) =====
AWS_REGION="us-west-2"
AWS_PROFILE="agent-space"
BEDROCK_DEFAULT_MODEL="us.anthropic.claude-sonnet-4-5-20250929-v1:0"
BEDROCK_S3_BUCKET="bondable-bedrock-agent-space-019593708315"
BEDROCK_AGENT_ROLE_ARN="arn:aws:iam::019593708315:role/BondAIBedrockAgentRole"

# OAuth Configuration (Okta Trial)
OAUTH2_ENABLED_PROVIDERS=okta
OKTA_DOMAIN="https://trial-9457917.okta.com"
OKTA_CLIENT_ID="0oas1uz67oWaTK8iP697"
OKTA_CLIENT_SECRET="xhaKsvlah6K_6khDjshL0VquUqQtU132d5NWeEN4pcH3iHVzlHzPAgUD9YLq6yi4"
OKTA_REDIRECT_URI="http://localhost:8000/auth/okta/callback"
OKTA_SCOPES="openid,profile,email"

# JWT Secret (generated securely)
JWT_SECRET_KEY="your-jwt-secret-key-here"

# MCP Configuration
BOND_MCP_CONFIG='{"mcpServers":{"my_client":{"url":"http://127.0.0.1:5554/mcp","transport":"streamable-http"}}}'

# Database (for local development)
DATABASE_URL="postgresql://postgres:password@localhost:5432/bondai"
```

### Running Locally

**Requires 3 terminal windows:**

#### Terminal 1: MCP Server
```bash
cd /Users/jcarnahan/projects/bond-ai
fastmcp run scripts/sample_mcp_server.py --transport streamable-http --port 5554
```

#### Terminal 2: Backend API
```bash
cd /Users/jcarnahan/projects/bond-ai
uvicorn bondable.rest.main:app --reload --host 0.0.0.0 --port 8000
```

#### Terminal 3: Frontend
```bash
cd /Users/jcarnahan/projects/bond-ai/flutterui
flutter run -d chrome --web-port=5000 --target lib/main.dart
```

### Local Testing

1. Access: http://localhost:5000
2. Login with Okta
3. Create test agent
4. Test chat functionality
5. Verify MCP tool integration

---

## Troubleshooting Guide

### Common Issues

#### Issue 1: App Runner Service Won't Start

**Symptoms:**
- Service stuck in "CREATE_IN_PROGRESS"
- Status shows "OPERATION_FAILED"

**Diagnosis:**
```bash
# Check service status
AWS_PROFILE=agent-space aws apprunner describe-service \
  --service-arn <service-arn> \
  --query 'Service.Status'

# Check CloudWatch logs
AWS_PROFILE=agent-space aws logs tail /aws/apprunner/<service-name>/service --follow
```

**Common Causes:**
1. Invalid environment variables
2. IAM role missing permissions
3. VPC connector configuration error
4. Docker image build failure

**Solutions:**
```bash
# Verify IAM role
AWS_PROFILE=agent-space aws iam get-role --role-name <role-name>

# Verify environment variables
AWS_PROFILE=agent-space aws apprunner describe-service \
  --service-arn <service-arn> \
  --query 'Service.SourceConfiguration.ImageRepository.ImageConfiguration.RuntimeEnvironmentVariables'

# Force new deployment
AWS_PROFILE=agent-space aws apprunner start-deployment \
  --service-arn <service-arn>
```

#### Issue 2: Database Connection Failures

**Symptoms:**
- Backend health check fails
- Logs show "connection refused" or "timeout"

**Diagnosis:**
```bash
# Check security group rules
AWS_PROFILE=agent-space aws ec2 describe-security-groups \
  --group-ids sg-093898a78113504b2

# Check RDS status
AWS_PROFILE=agent-space aws rds describe-db-instances \
  --db-instance-identifier bond-ai-dev-db
```

**Solutions:**
1. Verify security group allows inbound 5432 from App Runner
2. Verify VPC connector is in same VPC as RDS
3. Check database credentials in Secrets Manager
4. Verify RDS instance is available (not stopped)

#### Issue 3: Bedrock Access Denied

**Symptoms:**
- Chat functionality fails
- Logs show "accessDeniedException"

**Diagnosis:**
```bash
# Check IAM role policy
AWS_PROFILE=agent-space aws iam get-role-policy \
  --role-name BondAIBedrockAgentRole \
  --policy-name BedrockModelAccessPolicy

# Test Bedrock access
AWS_PROFILE=agent-space aws bedrock-runtime invoke-model \
  --model-id us.anthropic.claude-sonnet-4-5-20250929-v1:0 \
  --body '{"anthropic_version":"bedrock-2023-05-31","max_tokens":100,"messages":[{"role":"user","content":"test"}]}' \
  /tmp/output.json
```

**Solutions:**
1. Verify inline policy includes model ARNs
2. Check both `us.anthropic.*` and `anthropic.*` prefixes
3. Verify App Runner role can pass BondAIBedrockAgentRole
4. Check Marketplace permissions

#### Issue 4: CORS Errors

**Symptoms:**
- Frontend can't reach backend
- Browser console shows CORS errors

**Diagnosis:**
```bash
# Check backend CORS configuration
curl -I -X OPTIONS https://rqs8cicg8h.us-west-2.awsapprunner.com/health \
  -H "Origin: https://jid5jmztei.us-west-2.awsapprunner.com"
```

**Solutions:**
1. Verify backend ALLOWED_ORIGINS includes frontend URL
2. Check post-deployment script updated CORS settings
3. Redeploy backend with updated environment variables

#### Issue 5: Okta Authentication Failures

**Symptoms:**
- Login redirects fail
- "Invalid redirect URI" error

**Diagnosis:**
```bash
# Check Okta configuration
echo $OKTA_REDIRECT_URI

# Verify callback URL in Okta admin console
```

**Solutions:**
1. Add backend URL to Okta allowed redirect URIs
2. Verify OKTA_REDIRECT_URI environment variable
3. Check Okta application is active
4. Verify client ID and secret are correct

### Useful Commands

#### Kill Local Processes
```bash
# Kill MCP server
lsof -ti:5554 | xargs kill -9

# Kill backend
lsof -ti:8000 | xargs kill -9

# Kill frontend
lsof -ti:5000 | xargs kill -9
```

#### Docker Troubleshooting
```bash
# Check Docker is running
docker ps

# Clean up Docker resources
docker system prune -a

# Check Docker logs
docker logs <container-id>
```

#### AWS Service Checks
```bash
# Check AWS credentials
AWS_PROFILE=agent-space aws sts get-caller-identity

# List all S3 buckets
AWS_PROFILE=agent-space aws s3 ls

# List all secrets
AWS_PROFILE=agent-space aws secretsmanager list-secrets

# Describe VPC
AWS_PROFILE=agent-space aws ec2 describe-vpcs \
  --vpc-ids vpc-0f15dee1f11b1bf06
```

---

## Cost Analysis

### Monthly Cost Breakdown

```
Service                      Specification              Monthly Cost
─────────────────────────────────────────────────────────────────────
RDS PostgreSQL              db.t3.micro, 20GB           $15-16
Backend App Runner          0.25 vCPU, 512MB            $15-20
Frontend App Runner         0.25 vCPU, 512MB            $15-20
NAT Gateway                 2 AZs (existing)            $45
VPC Endpoints               S3 Gateway (existing)       $0
ECR Storage                 <5GB                        <$1
S3 Storage                  <10GB                       <$1
Secrets Manager             3 secrets                   $1.50
CloudWatch Logs             ~5GB/month                  $2.50
Bedrock API                 Claude Sonnet 4.5           Variable*
─────────────────────────────────────────────────────────────────────
Total Infrastructure                                    ~$95-100/month
```

*Bedrock pricing (Claude Sonnet 4.5):
- Input: $0.003 per 1K tokens
- Output: $0.015 per 1K tokens
- Typical usage: $20-50/month for development

### Cost Optimization Tips

1. **Database:**
   - Use db.t3.micro for dev (already configured)
   - Enable auto-pause for RDS (future enhancement)
   - Use snapshot for long-term backups (cheaper than continuous)

2. **App Runner:**
   - Use minimum CPU/memory for dev (already configured)
   - Consider scheduled scaling for non-business hours
   - Monitor actual resource usage

3. **NAT Gateway:**
   - Largest cost component (~$45/month)
   - Shared across VPC (not isolated to Bond AI)
   - Consider VPC endpoints for AWS services

4. **Bedrock:**
   - Use Claude Haiku for simple tasks (cheaper)
   - Implement response caching
   - Set max_tokens limits

5. **S3 & ECR:**
   - Enable lifecycle policies for old images
   - Compress logs before storing
   - Use S3 Intelligent-Tiering

---

## Reference Commands

### AWS CLI Commands

#### Identity & Access
```bash
# Check current AWS identity
AWS_PROFILE=agent-space aws sts get-caller-identity

# Assume role (if needed)
aws sts assume-role --role-arn <role-arn> --role-session-name <session-name>
```

#### Bedrock
```bash
# List available models
AWS_PROFILE=agent-space aws bedrock list-foundation-models \
  --region us-west-2 \
  --by-provider anthropic

# Test model invocation
AWS_PROFILE=agent-space aws bedrock-runtime invoke-model \
  --model-id us.anthropic.claude-sonnet-4-5-20250929-v1:0 \
  --body '{"anthropic_version":"bedrock-2023-05-31","max_tokens":100,"messages":[{"role":"user","content":"Hello"}]}' \
  /tmp/output.json
```

#### App Runner
```bash
# List services
AWS_PROFILE=agent-space aws apprunner list-services --region us-west-2

# Describe service
AWS_PROFILE=agent-space aws apprunner describe-service \
  --service-arn <service-arn>

# Start deployment
AWS_PROFILE=agent-space aws apprunner start-deployment \
  --service-arn <service-arn>

# Pause service
AWS_PROFILE=agent-space aws apprunner pause-service \
  --service-arn <service-arn>

# Resume service
AWS_PROFILE=agent-space aws apprunner resume-service \
  --service-arn <service-arn>
```

#### RDS
```bash
# List databases
AWS_PROFILE=agent-space aws rds describe-db-instances

# Get database endpoint
AWS_PROFILE=agent-space aws rds describe-db-instances \
  --db-instance-identifier bond-ai-dev-db \
  --query 'DBInstances[0].Endpoint'

# Create snapshot
AWS_PROFILE=agent-space aws rds create-db-snapshot \
  --db-instance-identifier bond-ai-dev-db \
  --db-snapshot-identifier bond-ai-dev-snapshot-$(date +%Y%m%d)
```

#### Secrets Manager
```bash
# List secrets
AWS_PROFILE=agent-space aws secretsmanager list-secrets

# Get secret value
AWS_PROFILE=agent-space aws secretsmanager get-secret-value \
  --secret-id <secret-name> \
  --query SecretString --output text

# Update secret
AWS_PROFILE=agent-space aws secretsmanager update-secret \
  --secret-id <secret-name> \
  --secret-string '{"key":"value"}'
```

#### CloudWatch Logs
```bash
# Tail logs (follow mode)
AWS_PROFILE=agent-space aws logs tail \
  /aws/apprunner/bond-ai-dev-backend/service \
  --follow

# Get recent logs
AWS_PROFILE=agent-space aws logs get-log-events \
  --log-group-name /aws/apprunner/bond-ai-dev-backend/service \
  --log-stream-name <stream-name> \
  --limit 100
```

### Terraform Commands

```bash
# Working directory
cd deployment/terraform-existing-vpc

# Initialize
AWS_PROFILE=agent-space terraform init

# Select workspace
AWS_PROFILE=agent-space terraform workspace select agent-space

# Validate configuration
AWS_PROFILE=agent-space terraform validate

# Format configuration
AWS_PROFILE=agent-space terraform fmt -recursive

# Plan deployment
AWS_PROFILE=agent-space terraform plan \
  -var-file=environments/agent-space.tfvars \
  -out=tfplan

# Apply deployment
AWS_PROFILE=agent-space terraform apply tfplan

# Show outputs
AWS_PROFILE=agent-space terraform output
AWS_PROFILE=agent-space terraform output -json

# Show state
AWS_PROFILE=agent-space terraform show

# Refresh state
AWS_PROFILE=agent-space terraform refresh \
  -var-file=environments/agent-space.tfvars

# Destroy (CAUTION!)
AWS_PROFILE=agent-space terraform destroy \
  -var-file=environments/agent-space.tfvars
```

### Docker Commands

```bash
# Build backend image
docker build -t bond-ai-backend:latest .

# Build for linux/amd64 (required for App Runner)
docker buildx build --platform linux/amd64 \
  -t bond-ai-backend:latest .

# Tag for ECR
docker tag bond-ai-backend:latest \
  019593708315.dkr.ecr.us-west-2.amazonaws.com/bond-ai-dev-backend:latest

# Login to ECR
AWS_PROFILE=agent-space aws ecr get-login-password --region us-west-2 | \
  docker login --username AWS --password-stdin \
  019593708315.dkr.ecr.us-west-2.amazonaws.com

# Push to ECR
docker push 019593708315.dkr.ecr.us-west-2.amazonaws.com/bond-ai-dev-backend:latest
```

---

## Appendix

### Available Claude Models (us-west-2)

```
Model ID                                              Version      Launched
─────────────────────────────────────────────────────────────────────────────
us.anthropic.claude-sonnet-4-5-20250929-v1:0          Sonnet 4.5   Sept 2024
anthropic.claude-sonnet-4-20250514-v1:0               Sonnet 4     May 2024
anthropic.claude-haiku-4-5-20251001-v1:0              Haiku 4.5    Oct 2024
anthropic.claude-opus-4-1-20250805-v1:0               Opus 4.1     Aug 2024
anthropic.claude-3-7-sonnet-20250219-v1:0             Sonnet 3.7   Feb 2024
anthropic.claude-3-5-sonnet-20241022-v2:0             Sonnet 3.5   Oct 2023
anthropic.claude-3-5-haiku-20241022-v1:0              Haiku 3.5    Oct 2023
```

### Terraform State Information

```
Workspace:          agent-space
Backend:            local
State File:         terraform.tfstate.d/agent-space/terraform.tfstate
Resources:          38 managed
Last Modified:      2025-11-12T20:45:00Z
```

### Network Topology

```
┌─────────────────────────────────────────────────────────────────┐
│  VPC: vpc-0f15dee1f11b1bf06 (10.4.231.0/24)                    │
│                                                                  │
│  ┌───────────────────────┐  ┌───────────────────────┐          │
│  │  AZ: us-west-2a       │  │  AZ: us-west-2b       │          │
│  │                       │  │                       │          │
│  │  internal-green       │  │  internal-green       │          │
│  │  subnet-09...c9f5e    │  │  subnet-0a...1f24b    │          │
│  │  10.4.231.0/27        │  │  10.4.231.32/27       │          │
│  │  ┌─────────────────┐  │  │  ┌─────────────────┐  │          │
│  │  │ App Runner      │  │  │  │ App Runner      │  │          │
│  │  │ VPC Connector   │◄─┼──┼─►│ VPC Connector   │  │          │
│  │  └─────────────────┘  │  │  └─────────────────┘  │          │
│  │          │             │  │          │             │          │
│  │          ▼             │  │          ▼             │          │
│  │  ┌─────────────────┐  │  │  ┌─────────────────┐  │          │
│  │  │ RDS PostgreSQL  │◄─┼──┼─►│ RDS Standby     │  │          │
│  │  └─────────────────┘  │  │  └─────────────────┘  │          │
│  └───────────────────────┘  └───────────────────────┘          │
│                                                                  │
│  ┌───────────────────────────────────────────────┐             │
│  │  S3 VPC Endpoint (Gateway)                     │             │
│  │  - Enables private S3 access                   │             │
│  │  - No NAT Gateway charges for S3               │             │
│  └───────────────────────────────────────────────┘             │
│                                                                  │
│  ┌───────────────────────────────────────────────┐             │
│  │  NAT Gateway (Shared)                          │             │
│  │  - Outbound internet access                    │             │
│  │  - Bedrock API calls                           │             │
│  │  - Secrets Manager access                      │             │
│  └───────────────────────────────────────────────┘             │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│  External Services                                               │
│  - AWS Bedrock (Claude Sonnet 4.5)                              │
│  - AWS Secrets Manager                                          │
│  - Amazon ECR                                                    │
│  - Okta (trial-9457917.okta.com)                               │
└─────────────────────────────────────────────────────────────────┘
```

---

## Document History

| Date | Version | Changes | Author |
|------|---------|---------|--------|
| 2025-11-12 | 1.0 | Initial deployment documentation | Claude + James Carnahan |

---

**Document Status:** ✅ Deployment Complete and Verified
**Last Updated:** November 12, 2025
**Next Review:** December 12, 2025
