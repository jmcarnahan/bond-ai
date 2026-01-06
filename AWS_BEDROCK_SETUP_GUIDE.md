# AWS Bedrock Setup Guide for Bond AI

**Purpose:** This guide documents the exact steps needed to configure AWS resources for Bond AI with Bedrock in a new AWS account.

**Date Created:** November 12, 2025
**Tested On:** Account 019593708315 (agent-space), Region: us-west-2

---

## Overview

This guide covers the AWS prerequisites needed before running Bond AI locally or deploying to AWS. The key insight is that **model access is now controlled entirely via IAM policies** - there is no longer a separate "Model Access" page in the Bedrock console.

---

## Prerequisites

- AWS CLI v2 installed and configured
- AWS account with Administrator access
- AWS profile configured (e.g., `agent-space`)

---

## Step 1: Create S3 Bucket for Bedrock Files

```bash
# Set your AWS profile and region
export AWS_PROFILE=agent-space
export AWS_REGION=us-west-2
export AWS_ACCOUNT_ID=019593708315  # Replace with your account ID

# Create bucket (name must be globally unique)
aws s3 mb s3://bondable-bedrock-agent-space-${AWS_ACCOUNT_ID} --region ${AWS_REGION}

# Enable versioning (recommended)
aws s3api put-bucket-versioning \
  --bucket bondable-bedrock-agent-space-${AWS_ACCOUNT_ID} \
  --versioning-configuration Status=Enabled \
  --region ${AWS_REGION}
```

---

## Step 2: Create IAM Role for Bedrock Agents

### 2.1 Create Trust Policy

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

### 2.2 Create IAM Role

```bash
aws iam create-role \
  --role-name BondAIBedrockAgentRole \
  --assume-role-policy-document file:///tmp/bedrock-trust-policy.json \
  --description "Role for Bond AI Bedrock Agents" \
  --region ${AWS_REGION}
```

### 2.3 Attach Managed Policies

```bash
# Attach AmazonBedrockFullAccess
aws iam attach-role-policy \
  --role-name BondAIBedrockAgentRole \
  --policy-arn arn:aws:iam::aws:policy/AmazonBedrockFullAccess

# Attach AmazonS3FullAccess
aws iam attach-role-policy \
  --role-name BondAIBedrockAgentRole \
  --policy-arn arn:aws:iam::aws:policy/AmazonS3FullAccess
```

### 2.4 Add Inline Policy for Specific Model Access

**CRITICAL:** This is the key step for new IAM-based model access control.

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

Apply the policy:
```bash
aws iam put-role-policy \
  --role-name BondAIBedrockAgentRole \
  --policy-name BedrockModelAccessPolicy \
  --policy-document file:///tmp/bedrock-model-access-policy.json
```

---

## Step 3: Create Okta Secret in Secrets Manager

```bash
# Replace with your actual Okta client secret
aws secretsmanager create-secret \
  --name bond-ai-dev-okta-secret \
  --secret-string '{"client_secret":"YOUR_OKTA_CLIENT_SECRET_HERE"}' \
  --region ${AWS_REGION}
```

---

## Step 4: Verify IAM Role Configuration

```bash
# Check trust policy
aws iam get-role --role-name BondAIBedrockAgentRole \
  --query 'Role.AssumeRolePolicyDocument'

# List attached managed policies
aws iam list-attached-role-policies --role-name BondAIBedrockAgentRole

# View inline policies
aws iam list-role-policies --role-name BondAIBedrockAgentRole

# Get inline policy details
aws iam get-role-policy \
  --role-name BondAIBedrockAgentRole \
  --policy-name BedrockModelAccessPolicy
```

---

## Step 5: Test Model Access

Create test script: `/tmp/test-bedrock-access.py`
```python
import boto3
import json
import os

# Set your AWS profile
os.environ['AWS_PROFILE'] = 'agent-space'

session = boto3.Session(profile_name='agent-space', region_name='us-west-2')
bedrock_runtime = session.client('bedrock-runtime')

print("Testing Bedrock model invocation...")
print("Model: us.anthropic.claude-sonnet-4-5-20250929-v1:0")

try:
    response = bedrock_runtime.invoke_model(
        modelId='us.anthropic.claude-sonnet-4-5-20250929-v1:0',
        body=json.dumps({
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 100,
            "messages": [{"role": "user", "content": "Say hello"}]
        })
    )
    result = json.loads(response['body'].read())
    print("\n✅ SUCCESS! Model invoked successfully")
    print(json.dumps(result, indent=2))
except Exception as e:
    print(f"\n❌ ERROR: {type(e).__name__}: {e}")
```

Run test:
```bash
python3 /tmp/test-bedrock-access.py
```

---

## Step 6: Configure Local Environment

Update your `.env` file:
```env
# ===== YOUR ACCOUNT CONFIGURATION =====
AWS_REGION="us-west-2"
AWS_PROFILE="agent-space"
BEDROCK_DEFAULT_MODEL="us.anthropic.claude-sonnet-4-5-20250929-v1:0"
BEDROCK_S3_BUCKET="bondable-bedrock-agent-space-019593708315"
BEDROCK_AGENT_ROLE_ARN="arn:aws:iam::019593708315:role/BondAIBedrockAgentRole"

# Okta Configuration
OAUTH2_ENABLED_PROVIDERS=okta
OKTA_DOMAIN="https://trial-9457917.okta.com"
OKTA_CLIENT_ID="0oas1uz67oWaTK8iP697"
OKTA_CLIENT_SECRET="YOUR_OKTA_CLIENT_SECRET"
OKTA_REDIRECT_URI="http://localhost:8000/auth/okta/callback"
OKTA_SCOPES="openid,profile,email"

# JWT Secret
JWT_SECRET_KEY="YOUR_JWT_SECRET_KEY"

# MCP Configuration
BOND_MCP_CONFIG='{
  "mcpServers": {
    "my_client": {
      "url": "http://127.0.0.1:5554/mcp",
      "transport": "streamable-http"
    }
  }
}'
```

---

## Key Differences from Old Bedrock Setup

### Old Way (Before 2025)
- Required visiting Bedrock console UI
- Clicking "Manage model access" button
- Requesting access per model via UI
- Waiting for approval

### New Way (2025+)
- ✅ **Fully IAM-based** - no console UI needed
- ✅ Model access controlled via IAM resource ARNs
- ✅ Can be automated in Terraform/CloudFormation
- ✅ Supports both inference profiles (`us.anthropic.*`) and direct models (`anthropic.*`)

---

## Important Notes

1. **Model ID Formats:**
   - Inference Profile (cross-region): `us.anthropic.claude-sonnet-4-5-20250929-v1:0`
   - Direct Model: `anthropic.claude-sonnet-4-5-20250929-v1:0`
   - Include BOTH in IAM policies for compatibility

2. **Required IAM Permissions:**
   - `bedrock:InvokeModel` - For direct model invocation
   - `bedrock:InvokeModelWithResponseStream` - For streaming responses
   - `bedrock:*Agent*` - For Bedrock Agents operations
   - `aws-marketplace:*` - For marketplace model subscriptions

3. **Resource ARN Format:**
   ```
   arn:aws:bedrock:{region}::foundation-model/{model-id}
   ```
   Note: The account ID slot is empty (::) for foundation models

4. **Wildcard Support:**
   - `arn:aws:bedrock:*::foundation-model/anthropic.*` - All Anthropic models
   - `arn:aws:bedrock:*::foundation-model/us.anthropic.*` - All inference profiles

---

## Troubleshooting

### Error: "accessDeniedException when calling Bedrock"

**Cause:** IAM role lacks proper model access permissions

**Solution:**
1. Verify inline policy includes specific model ARNs
2. Check both `us.anthropic.*` and `anthropic.*` prefixes are included
3. Ensure managed policy `AmazonBedrockFullAccess` is attached

### Error: "Model access is denied due to IAM user or service role..."

**Cause:** Missing Marketplace permissions

**Solution:** Add Marketplace permissions to IAM policy:
```json
{
  "Effect": "Allow",
  "Action": [
    "aws-marketplace:ViewSubscriptions",
    "aws-marketplace:Subscribe",
    "aws-marketplace:Unsubscribe"
  ],
  "Resource": "*"
}
```

### Testing Model Access

Use this Python snippet to test:
```python
import boto3, json
client = boto3.Session(profile_name='YOUR_PROFILE', region_name='us-west-2').client('bedrock-runtime')
response = client.invoke_model(
    modelId='us.anthropic.claude-sonnet-4-5-20250929-v1:0',
    body=json.dumps({
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": 100,
        "messages": [{"role": "user", "content": "test"}]
    })
)
print(json.loads(response['body'].read()))
```

---

## For Terraform Deployment

When creating this role in Terraform, see: `deployment/terraform-existing-vpc/iam.tf`

The key resource is:
```hcl
resource "aws_iam_role" "bedrock_agent_role" {
  name = "${var.project_name}-${var.environment}-bedrock-agent-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Principal = { Service = "bedrock.amazonaws.com" }
      Action = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy" "bedrock_model_access" {
  name = "BedrockModelAccessPolicy"
  role = aws_iam_role.bedrock_agent_role.id

  policy = jsonencode({
    # Use the policy from Step 2.4 above
  })
}
```

---

## Summary Checklist

- [ ] S3 bucket created with versioning enabled
- [ ] BondAIBedrockAgentRole created with proper trust policy
- [ ] AmazonBedrockFullAccess managed policy attached
- [ ] AmazonS3FullAccess managed policy attached
- [ ] BedrockModelAccessPolicy inline policy added with specific model ARNs
- [ ] Okta secret created in Secrets Manager
- [ ] Model access tested successfully with Python script
- [ ] `.env` file configured with correct values

---

**Reference Documentation:**
- AWS Bedrock IAM Policies: https://docs.aws.amazon.com/bedrock/latest/userguide/security_iam_id-based-policy-examples.html
- Foundation Model IDs: List via `aws bedrock list-foundation-models --region us-west-2`
