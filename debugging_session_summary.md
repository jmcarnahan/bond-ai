# Bond AI Agent Creation Debugging Session Summary

## Session Date: 2025-09-03

### Objective
Investigate why the Bond AI REST API agent creation fails while the direct AWS Bedrock agent creation succeeds, despite using the same AWS credentials.

## Key Findings

### ✅ What Works
1. **Direct Bedrock Script (`bedrock-agent-test.py`)**:
   - Successfully authenticates with AWS 
   - Can list existing agents
   - **Successfully creates agents** when using simple parameters
   - Uses: `boto3.client('bedrock-agent', region_name='us-east-1')`

2. **REST API Infrastructure**:
   - Server starts successfully on port 8000
   - JWT authentication works correctly
   - Can retrieve 70 available models via `/agents/models`
   - Can list agents via `/agents`
   - User identity correctly resolved: `test_user_test (test@example.com)`

### ❌ What Fails
**REST API Agent Creation** fails with:
```
Failed to create Bedrock Agent: User: arn:aws:sts::767397995923:assumed-role/AAD_Admin/john_carnahan@mcafee.com is not authorized to perform: bedrock:CreateAgent
```

### 🔍 Root Cause Identified

**The critical difference**: 

1. **Direct bedrock script** calls:
   ```python
   client.create_agent(
       agentName=agent_name,
       foundationModel='us.anthropic.claude-3-7-sonnet-20250219-v1:0',
       description='Test agent from Python - delete immediately',
       idleSessionTTLInSeconds=300
   )
   ```

2. **Bond AI REST API** calls (via `BedrockCRUD.py:71`):
   ```python
   bedrock_agent_client.create_agent(
       agentName=bedrock_agent_name,
       agentResourceRoleArn=agent_role_arn,  # 🚨 KEY DIFFERENCE
       instruction=instructions,
       foundationModel=agent_def.model,
       description=agent_def.description,
       idleSessionTTLInSeconds=3600,
   )
   ```

**The Issue**: The REST API requires `agentResourceRoleArn` parameter from environment variable `BEDROCK_AGENT_ROLE_ARN`.

### 🔧 Environment Configuration Discovery

**Current `.env` configuration**:
```bash
AWS_REGION="us-east-1"
AWS_PROFILE="mosaic-devqa"
BEDROCK_AGENT_ROLE_ARN="arn:aws:iam::767397995923:role/BondAIBedrockAgentRole"  # Updated during session
```

**User Context**:
- Current User ARN: `arn:aws:sts::767397995923:assumed-role/AAD_Admin/john_carnahan@mcafee.com`
- Account: `767397995923`

**Original Issue**: The `.env` file initially had:
```bash
BEDROCK_AGENT_ROLE_ARN="arn:aws:iam::832851589928:role/BondAIBedrockAgentRole"
```

This was a **cross-account role** (`832851589928` vs `767397995923`) which our user couldn't assume.

## Scripts Created

### 1. `rest-agent-test.py`
- **Status**: ✅ Complete and functional
- **Purpose**: Mirror of `bedrock-agent-test.py` but using Bond AI REST API
- **Features**:
  - JWT authentication
  - Health checks
  - Model discovery (70 models retrieved)
  - Agent creation/deletion via REST API
  - Comprehensive error reporting
  - Interactive prompts (dry/yes/no)

### 2. `bedrock-agent-test.py` 
- **Status**: ✅ Working (provided script)
- **Verified**: Successfully creates/deletes agents with simple parameters

## Current Status

### ✅ Completed Tasks
1. ✅ Run bedrock-agent-test.py with poetry - **SUCCESSFUL**
2. ✅ Start Bond AI REST API server - **RUNNING on port 8000**
3. ✅ Create rest-agent-test.py script - **COMPLETE**
4. ✅ Test REST API agent creation - **IDENTIFIED FAILURE**
5. ✅ Compare approaches and identify root cause - **FOUND**

### 🔄 In Progress
- Debug the specific difference causing REST API to fail
- **Status**: Root cause identified - missing IAM role permissions

## Next Steps

### Priority 1: Verify Role Permissions
1. **Test if the updated role ARN works**:
   ```bash
   poetry run python rest-agent-test.py
   ```
   (with updated `BEDROCK_AGENT_ROLE_ARN="arn:aws:iam::767397995923:role/BondAIBedrockAgentRole"`)

2. **Create enhanced bedrock test script** that uses the same `agentResourceRoleArn` parameter:
   ```python
   # New test in bedrock-agent-test.py
   client.create_agent(
       agentName=agent_name,
       agentResourceRoleArn="arn:aws:iam::767397995923:role/BondAIBedrockAgentRole",
       foundationModel='us.anthropic.claude-3-7-sonnet-20250219-v1:0',
       description='Test agent with role ARN',
       idleSessionTTLInSeconds=300
   )
   ```

### Priority 2: Role Configuration
1. **Verify the IAM role exists**:
   ```bash
   aws iam get-role --role-name BondAIBedrockAgentRole
   ```

2. **Check role permissions** - ensure it has necessary Bedrock agent permissions

3. **Verify assume role permissions** for current user

### Priority 3: Testing Matrix
Create comprehensive test to verify:
- [ ] Direct bedrock (simple params) ✅ **WORKS**
- [ ] Direct bedrock (with roleArn) ❓ **TO TEST**
- [ ] REST API (with correct roleArn) ❓ **TO TEST**

## Server Status
- **REST API Server**: Running on `http://localhost:8000`
- **Background Process ID**: `bash_1`
- **Health Check**: ✅ `{"status":"healthy"}`
- **Authentication**: ✅ JWT working
- **AWS Integration**: ✅ Models endpoint working (70 models)

## Files Created/Modified
- ✅ `rest-agent-test.py` - New comprehensive REST API test script
- ✅ `.env` - Updated `BEDROCK_AGENT_ROLE_ARN` to correct account
- ✅ `debugging_session_summary.md` - This summary

## Key Commands for Resume
```bash
# Check server status
curl http://localhost:8000/health

# Test REST API with updated role
poetry run python rest-agent-test.py

# Test direct bedrock with role parameter
# (need to create enhanced version)

# Check role exists
aws iam get-role --role-name BondAIBedrockAgentRole

# Check server logs
# (use BashOutput tool with bash_1)
```

## Technical Notes
- **Same AWS Credentials**: Both approaches use identical AWS credentials and user context
- **Same Region**: Both use `us-east-1`
- **Same Foundation Model**: Both use `us.anthropic.claude-3-7-sonnet-20250219-v1:0`
- **Critical Difference**: REST API requires `agentResourceRoleArn`, direct script doesn't

---

*Session paused at: Role ARN updated in .env, need to test if this resolves the issue*