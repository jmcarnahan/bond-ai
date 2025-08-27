# AWS Credentials Setup for Bedrock Provider

## Prerequisites

1. **AWS Account**: You need an AWS account with Bedrock access enabled
2. **Bedrock Model Access**: Request access to the models you want to use in the AWS Console
3. **IAM Permissions**: Your AWS user/role needs specific permissions

## Step 1: Enable Bedrock Models

1. Go to the [AWS Bedrock Console](https://console.aws.amazon.com/bedrock/)
2. Click on "Model access" in the left sidebar
3. Click "Manage model access"
4. Select the models you want to use:
   - Anthropic Claude models (Claude 3 Opus, Sonnet, Haiku)
   - Meta Llama models (if desired)
   - Mistral models (if desired)
5. Click "Request model access" and wait for approval (usually instant for most models)

## Step 2: Create IAM User or Use Existing Credentials

### Option A: Create a new IAM user

1. Go to [IAM Console](https://console.aws.amazon.com/iam/)
2. Click "Users" → "Create user"
3. Username: `bond-bedrock-user`
4. Select "Programmatic access"
5. Create and save the Access Key ID and Secret Access Key

### Option B: Use existing AWS credentials

If you already have AWS CLI configured, you can use those credentials.

## Step 3: Set Up IAM Permissions

Create a policy with these permissions:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "BedrockAccess",
      "Effect": "Allow",
      "Action": [
        "bedrock:InvokeModel",
        "bedrock:InvokeModelWithResponseStream",
        "bedrock:ListFoundationModels",
        "bedrock:GetFoundationModel"
      ],
      "Resource": "*"
    },
    {
      "Sid": "BedrockAgentAccess",
      "Effect": "Allow",
      "Action": [
        "bedrock:CreateAgent",
        "bedrock:UpdateAgent",
        "bedrock:GetAgent",
        "bedrock:ListAgents",
        "bedrock:DeleteAgent",
        "bedrock:CreateKnowledgeBase",
        "bedrock:UpdateKnowledgeBase",
        "bedrock:GetKnowledgeBase",
        "bedrock:ListKnowledgeBases",
        "bedrock:DeleteKnowledgeBase"
      ],
      "Resource": "*"
    },
    {
      "Sid": "BedrockAgentRuntimeAccess",
      "Effect": "Allow",
      "Action": [
        "bedrock-agent-runtime:InvokeAgent",
        "bedrock-agent-runtime:Retrieve",
        "bedrock-agent-runtime:RetrieveAndGenerate"
      ],
      "Resource": "*"
    },
    {
      "Sid": "S3AccessForFiles",
      "Effect": "Allow",
      "Action": [
        "s3:CreateBucket",
        "s3:ListBucket",
        "s3:GetBucketLocation",
        "s3:PutObject",
        "s3:GetObject",
        "s3:DeleteObject",
        "s3:PutObjectAcl",
        "s3:GetObjectAcl"
      ],
      "Resource": [
        "arn:aws:s3:::bond-bedrock-*",
        "arn:aws:s3:::bond-bedrock-*/*"
      ]
    }
  ]
}
```

## Step 4: Configure Credentials

### Option 1: Environment Variables (Recommended for development)

Create a `.env` file in your project root:

```bash
# AWS Credentials
AWS_ACCESS_KEY_ID=your_access_key_here
AWS_SECRET_ACCESS_KEY=your_secret_key_here
AWS_REGION=us-east-1  # or your preferred region

# Bedrock Configuration
BEDROCK_DEFAULT_MODEL=anthropic.claude-3-haiku-20240307-v1:0
BEDROCK_S3_BUCKET=bond-bedrock-files-YOUR_ACCOUNT_ID

# Use Bedrock Provider
BOND_PROVIDER_CLASS=bondable.bond.providers.bedrock.BedrockProvider.BedrockProvider
```

### Option 2: AWS CLI Configuration

```bash
aws configure
# Enter your Access Key ID
# Enter your Secret Access Key
# Enter your default region (e.g., us-east-1)
# Enter output format (json)
```

### Option 3: IAM Role (For EC2/ECS/Lambda)

If running on AWS infrastructure, use IAM roles instead of credentials.

## Step 5: Create S3 Bucket for File Storage

```bash
# Replace YOUR_ACCOUNT_ID with your AWS account ID
aws s3 mb s3://bond-bedrock-files-YOUR_ACCOUNT_ID --region us-east-1
```

Or create via console:
1. Go to [S3 Console](https://console.aws.amazon.com/s3/)
2. Click "Create bucket"
3. Name: `bond-bedrock-files-YOUR_ACCOUNT_ID`
4. Region: Same as your Bedrock region
5. Leave other settings as default
6. Click "Create bucket"

## Step 6: Test Your Setup

Run this test script to verify everything is working:

```python
import boto3
import os
from botocore.exceptions import ClientError

def test_bedrock_access():
    try:
        # Test Bedrock access
        client = boto3.client('bedrock', region_name=os.getenv('AWS_REGION', 'us-east-1'))
        response = client.list_foundation_models()
        print(f"✓ Successfully connected to Bedrock")
        print(f"✓ Found {len(response['modelSummaries'])} available models")
        
        # Test S3 access
        s3_client = boto3.client('s3')
        bucket_name = os.getenv('BEDROCK_S3_BUCKET')
        if bucket_name:
            try:
                s3_client.head_bucket(Bucket=bucket_name)
                print(f"✓ S3 bucket '{bucket_name}' is accessible")
            except ClientError as e:
                print(f"✗ S3 bucket error: {e}")
        else:
            print("⚠ BEDROCK_S3_BUCKET not configured")
            
    except ClientError as e:
        print(f"✗ AWS Error: {e}")
        print("\nTroubleshooting:")
        print("1. Check your AWS credentials are correct")
        print("2. Verify you have the required permissions")
        print("3. Ensure Bedrock is available in your region")
        print("4. Confirm you have requested model access")

if __name__ == "__main__":
    test_bedrock_access()
```

## Supported Regions

Bedrock is not available in all AWS regions. As of 2024, it's available in:
- US East (N. Virginia) - `us-east-1` ✓ Recommended
- US West (Oregon) - `us-west-2`
- EU (Frankfurt) - `eu-central-1`
- EU (Ireland) - `eu-west-1`
- EU (London) - `eu-west-2`
- EU (Paris) - `eu-west-3`
- Asia Pacific (Tokyo) - `ap-northeast-1`
- Asia Pacific (Singapore) - `ap-southeast-1`
- Asia Pacific (Sydney) - `ap-southeast-2`

## Cost Considerations

Bedrock charges per token for model usage:
- **Claude 3 Haiku**: ~$0.25/$1.25 per million input/output tokens
- **Claude 3 Sonnet**: ~$3/$15 per million input/output tokens
- **Claude 3 Opus**: ~$15/$75 per million input/output tokens

S3 charges for storage and requests are minimal for typical usage.

## Next Steps

Once credentials are configured:

1. Test with the script above
2. Run the Phase 1 tests with credentials:
   ```bash
   poetry run python tests/test_bedrock_phase1.py
   ```
3. You should see model listing work and no credential errors

## Security Best Practices

1. **Never commit credentials** to git
2. Add `.env` to `.gitignore`
3. Use IAM roles when deploying to production
4. Follow principle of least privilege
5. Rotate access keys regularly
6. Use AWS Secrets Manager for production