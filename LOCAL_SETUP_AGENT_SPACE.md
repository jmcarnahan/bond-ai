# Bond AI Local Setup - Agent-Space Account (019593708315)

**Created:** November 12, 2025
**AWS Account:** 019593708315
**AWS Profile:** agent-space
**Region:** us-west-2

## Prerequisites Completed

### AWS Resources Created
- ✅ **S3 Bucket:** `bondable-bedrock-agent-space-019593708315`
  - Location: us-west-2
  - Versioning: Enabled

- ✅ **IAM Role:** `BondAIBedrockAgentRole`
  - ARN: `arn:aws:iam::019593708315:role/BondAIBedrockAgentRole`
  - Permissions: Bedrock model invocation, S3 access

- ✅ **Secrets Manager Secret:** `bond-ai-dev-okta-secret`
  - ARN: `arn:aws:secretsmanager:us-west-2:019593708315:secret:bond-ai-dev-okta-secret-kLetp5`
  - Contains Okta client secret

### Environment Configuration

The `.env` file has been updated with agent-space configuration:
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
```

**Note:** The previous mosaic-devqa configuration has been commented out for easy switching.

## Available Bedrock Models in us-west-2

The following Claude models are available in the agent-space account:
- `us.anthropic.claude-sonnet-4-5-20250929-v1:0` ⭐ **(Selected)**
- `anthropic.claude-sonnet-4-20250514-v1:0`
- `anthropic.claude-haiku-4-5-20251001-v1:0`
- `anthropic.claude-opus-4-1-20250805-v1:0`
- `anthropic.claude-3-7-sonnet-20250219-v1:0`
- `anthropic.claude-3-5-sonnet-20241022-v2:0`
- `anthropic.claude-3-5-haiku-20241022-v1:0`

## Running Locally

You need **three separate terminal windows** to run the full application:

### Terminal 1: MCP Server
```bash
cd /Users/jcarnahan/projects/bond-ai
fastmcp run scripts/sample_mcp_server.py --transport streamable-http --port 5554
```

**Expected Output:**
- Server starts on port 5554
- Logs show "MCP server listening..."

### Terminal 2: Backend API
```bash
cd /Users/jcarnahan/projects/bond-ai
uvicorn bondable.rest.main:app --reload --host 0.0.0.0 --port 8000
```

**Expected Output:**
- FastAPI server starts on port 8000
- Database connection established
- Swagger docs available at http://localhost:8000/docs

**Important:** Make sure the AWS_PROFILE environment is set correctly. The backend will use the `agent-space` profile from `.env`.

### Terminal 3: Frontend (Flutter)
```bash
cd /Users/jcarnahan/projects/bond-ai/flutterui
flutter run -d chrome --web-port=5000 --target lib/main.dart
```

**Expected Output:**
- Flutter builds web application
- Chrome opens automatically
- Application loads at http://localhost:5000

## Testing Steps

1. **Access Application:** Open http://localhost:5000
2. **Test Okta Login:**
   - Click login button
   - Redirects to https://trial-9457917.okta.com
   - Login with Okta trial credentials
   - Redirects back to http://localhost:8000/auth/okta/callback
   - Receives JWT token
3. **Create Test Agent:**
   - Navigate to Agents section
   - Create new agent
   - Verify it appears in list
4. **Test Chat:**
   - Select agent
   - Start new conversation
   - Send test message
   - Verify response from Claude Sonnet 4.5
5. **Test MCP Integration:**
   - Use agent with MCP tools
   - Verify tool calls work

## VPC Information (for deployment)

**VPC ID:** `vpc-0f15dee1f11b1bf06`
**CIDR:** `10.4.231.0/24`

### Subnets (10 total across 2 AZs)

**Internal Subnets (for App Runner):**
- `subnet-0912fc7ffa04c9f5e` - internal-green-az1 (us-west-2a, 10.4.231.0/27)
- `subnet-0a8d3f8ed7df1f24b` - internal-green-az2 (us-west-2b, 10.4.231.32/27)

**VPC Endpoints Subnets:**
- `subnet-0f893419cd7e7b171` - vpc-endpoints-az1 (us-west-2a, 10.4.231.64/27)
- `subnet-018381bcb27398121` - vpc-endpoints-az2 (us-west-2b, 10.4.231.96/27)

**Routing Subnets:**
- TGW: subnet-0ef09d5e95b0ba8d2 (az1), subnet-0620dc61a08223bfb (az2)
- NAT: subnet-01bbfaa5f79dfc865 (az1), subnet-02f099014748d7757 (az2)
- Network Firewall: subnet-06967c170d3022793 (az1), subnet-0efd9986979b161ce (az2)

## Troubleshooting

### Backend Connection Issues
```bash
# Verify AWS credentials
AWS_PROFILE=agent-space aws sts get-caller-identity

# Check Bedrock access
AWS_PROFILE=agent-space aws bedrock list-foundation-models --region us-west-2 --by-provider anthropic

# Verify S3 bucket
AWS_PROFILE=agent-space aws s3 ls s3://bondable-bedrock-agent-space-019593708315 --region us-west-2
```

### Port Already in Use
```bash
# Kill process on port 8000
lsof -ti:8000 | xargs kill -9

# Kill process on port 5554 (MCP Server)
lsof -ti:5554 | xargs kill -9

# Kill process on port 5000
lsof -ti:5000 | xargs kill -9
```

### Okta Redirect Issues
- Verify `OKTA_REDIRECT_URI` matches callback URL in `.env`
- Check Okta application settings include `http://localhost:8000/auth/okta/callback` as allowed redirect URI

## Next Steps

After successful local testing:
1. Document any issues encountered and solutions
2. Create Terraform configuration file: `deployment/terraform-existing-vpc/environments/agent-space.tfvars`
3. Deploy to AWS using existing VPC
4. Update Okta application with deployed backend URL

## Switching Back to Mosaic-DevQA

To switch back to the mosaic-devqa account:
1. Comment out the AGENT-SPACE section in `.env`
2. Uncomment the MOSAIC-DEVQA section in `.env`
3. Restart backend server
