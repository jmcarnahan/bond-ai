# Getting Started with Bond AI - AWS Bedrock Provider

This guide will walk you through setting up Bond AI with the AWS Bedrock provider, including AWS configuration, environment setup, and running all components of the application.

## Table of Contents
- [Prerequisites](#prerequisites)
- [AWS Account Setup](#aws-account-setup)
- [Environment Configuration](#environment-configuration)
- [Running the Application](#running-the-application)
- [Troubleshooting](#troubleshooting)

## Prerequisites

Before you begin, ensure you have the following installed:

- Python 3.9 or higher
- Node.js and npm (for MCP server)
- Flutter SDK (for the frontend)
- AWS CLI (optional, but helpful)
- Git

## AWS Account Setup

### 1. Create an AWS Account
If you don't have an AWS account, create one at [aws.amazon.com](https://aws.amazon.com).

### 2. Enable Bedrock Models

1. Sign in to the AWS Console
2. Navigate to **Amazon Bedrock** service
3. Go to **Model access** in the left sidebar
4. Click **Edit** or **Manage model access**
5. Request access to the following models:
   - **Anthropic Claude Models:**
     - Claude 3 Opus
     - Claude 3 Sonnet
     - Claude 3 Haiku
     - Claude 3.5 Sonnet
   - **Meta Llama Models (optional):**
     - Llama 3 8B Instruct
     - Llama 3 70B Instruct
6. Click **Save changes** and wait for approval (usually instant for most models)

### 3. Create IAM User and Permissions

1. Go to **IAM** service in AWS Console
2. Create a new IAM user:
   - Click **Users** → **Create user**
   - Username: `bond-ai-bedrock`
   - Select **Programmatic access**
3. Create a new policy:
   - Click **Policies** → **Create policy**
   - Use the JSON editor and paste:

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
        "bedrock:CreateAgentAlias",
        "bedrock:UpdateAgentAlias",
        "bedrock:GetAgentAlias",
        "bedrock:ListAgentAliases",
        "bedrock:DeleteAgentAlias",
        "bedrock:PrepareAgent"
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
    },
    {
      "Sid": "IAMPassRole",
      "Effect": "Allow",
      "Action": "iam:PassRole",
      "Resource": "arn:aws:iam::*:role/BondAIBedrockAgentRole"
    }
  ]
}
```

4. Name the policy `BondAIBedrockPolicy` and create it
5. Attach the policy to your IAM user
6. Save the access key and secret key securely

### 4. Create IAM Role for Bedrock Agents

1. In IAM, click **Roles** → **Create role**
2. Select **Custom trust policy** and paste:

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

3. Name the role `BondAIBedrockAgentRole`
4. Attach the `AmazonBedrockAgentBedrockFoundationModelPolicy` policy
5. Note the Role ARN (e.g., `arn:aws:iam::123456789012:role/BondAIBedrockAgentRole`)

### 5. Create S3 Bucket for File Storage

Using AWS CLI:
```bash
aws s3 mb s3://bond-bedrock-files-YOUR_ACCOUNT_ID --region us-east-1
```

Or in the AWS Console:
1. Go to S3 service
2. Click **Create bucket**
3. Name: `bond-bedrock-files-YOUR_ACCOUNT_ID` (replace with your account ID)
4. Region: Choose your preferred region
5. Leave other settings as default
6. Click **Create bucket**

## Environment Configuration

### 1. Clone the Repository
```bash
git clone https://github.com/your-org/bond-ai.git
cd bond-ai
```

### 2. Install Python Dependencies
```bash
pip install -r requirements.txt
```

### 3. Install Flutter Dependencies
```bash
cd flutterui
flutter pub get
cd ..
```

### 4. Configure Environment Variables
1. Copy the example environment file:
   ```bash
   cp .env.example .env
   ```

2. Edit `.env` and fill in your values:
   ```bash
   # Provider Selection
   BOND_PROVIDER_CLASS="bondable.bond.providers.bedrock.BedrockProvider.BedrockProvider"

   # AWS Configuration
   AWS_ACCESS_KEY_ID="your_access_key_from_step_3"
   AWS_SECRET_ACCESS_KEY="your_secret_key_from_step_3"
   AWS_REGION="us-east-1"  # or your preferred region

   # Bedrock Configuration
   BEDROCK_DEFAULT_MODEL="us.anthropic.claude-3-5-sonnet-20241022-v2:0"
   BEDROCK_S3_BUCKET="bond-bedrock-files-YOUR_ACCOUNT_ID"
   BEDROCK_AGENT_ROLE_ARN="arn:aws:iam::YOUR_ACCOUNT_ID:role/BondAIBedrockAgentRole"

   # Authentication (generate a secure key)
   JWT_SECRET_KEY="$(openssl rand -hex 32)"

   # Configure other settings as needed...
   ```

### 5. Set Up Google OAuth (Optional but Recommended)

1. Go to [Google Cloud Console](https://console.cloud.google.com)
2. Create a new project or select existing
3. Enable Google OAuth2 API
4. Create OAuth 2.0 credentials:
   - Application type: Web application
   - Authorized redirect URIs: `http://localhost:8000/auth/google/callback`
5. Copy the client ID and secret to your `.env` file

## Running the Application

Bond AI consists of three main components that need to run simultaneously:

### Terminal 1: MCP Server
The Model Context Protocol server provides additional tools and capabilities to the AI agents.

```bash
# From the project root directory
fastmcp run scripts/my_server.py --transport streamable-http --port 5555
```

You should see:
```
INFO:     Started server process
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://127.0.0.1:5555
```

### Terminal 2: Backend REST API
The backend provides the REST API for the frontend to communicate with the AI providers.

```bash
# From the project root directory
uvicorn bondable.rest.main:app --reload --host 0.0.0.0 --port 8000
```

You should see:
```
INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
INFO:     Started reloader process
INFO:     Started server process
INFO:     Waiting for application startup.
INFO:     Application startup complete.
```

### Terminal 3: Flutter Frontend
The web-based user interface for interacting with Bond AI.

```bash
# From the project root directory
cd flutterui
flutter run -d chrome --web-port=5000 --target lib/main.dart
```

You should see Flutter compile and launch Chrome with the Bond AI interface.

### Accessing the Application

Once all three components are running:
1. Open your browser to `http://localhost:5000`
2. Click on "Sign in with Google" (or your configured auth provider)
3. After authentication, you'll be redirected to the main Bond AI interface
4. Create a new agent and start chatting!

## Verifying Your Setup

### 1. Test AWS Credentials
```bash
aws bedrock list-foundation-models --region us-east-1
```

You should see a list of available models.

### 2. Test Bedrock Access
Run the test script:
```bash
python tests/test_bedrock_provider_integration.py
```

### 3. Check MCP Server
```bash
curl http://localhost:5555/health
```

Should return a success response.

### 4. Check Backend API
```bash
curl http://localhost:8000/health
```

Should return `{"status": "healthy"}`

## Troubleshooting

### Common Issues

1. **"Model access denied" error**
   - Ensure you've requested and received access to Bedrock models
   - Check that your AWS region matches where you enabled models

2. **"Invalid credentials" error**
   - Verify AWS credentials in `.env` file
   - Ensure no extra spaces or quotes around credentials

3. **"Bucket not found" error**
   - Create the S3 bucket with exact name from `.env`
   - Ensure bucket is in the same region as your Bedrock access

4. **Frontend won't connect to backend**
   - Check that backend is running on port 8000
   - Verify no firewall blocking local connections
   - Check browser console for CORS errors

5. **MCP tools not working**
   - Ensure MCP server is running on port 5555
   - Check `BOND_MCP_CONFIG` in `.env` is valid JSON

### Debug Mode

For more detailed logging:
```bash
# Backend with debug logging
LOG_LEVEL=DEBUG uvicorn bondable.rest.main:app --reload --host 0.0.0.0 --port 8000

# Run specific test with verbose output
pytest tests/test_bedrock_provider_integration.py -v -s
```

## Cost Considerations

AWS Bedrock charges per token processed:
- **Claude 3 Haiku**: ~$0.25/$1.25 per million tokens (input/output)
- **Claude 3 Sonnet**: ~$3/$15 per million tokens
- **Claude 3.5 Sonnet**: ~$3/$15 per million tokens
- **Claude 3 Opus**: ~$15/$75 per million tokens

S3 storage costs are minimal for typical usage.

## Security Best Practices

1. **Never commit `.env` to version control** - ensure it's in `.gitignore`
2. **Use IAM roles in production** instead of access keys when possible
3. **Rotate access keys regularly**
4. **Enable MFA** on your AWS account
5. **Use least privilege principle** for IAM permissions
6. **Monitor AWS CloudTrail** for API usage
7. **Set up billing alerts** in AWS to avoid surprises

## Next Steps

- Explore the Bond AI interface and create different types of agents
- Try different Bedrock models to compare performance
- Set up additional MCP tools for extended functionality
- Configure vector stores for knowledge base functionality
- Deploy to production using AWS ECS or EC2

## Support

For issues or questions:
- Check the [GitHub Issues](https://github.com/your-org/bond-ai/issues)
- Review AWS Bedrock documentation
- Contact the Bond AI team

Happy coding with Bond AI and AWS Bedrock! 🚀
