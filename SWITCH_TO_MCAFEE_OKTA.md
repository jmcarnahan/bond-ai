# Switch Bond AI from Trial Okta to McAfee Okta

**Purpose:** Switch the agent-space deployment from Trial Okta to McAfee Okta authentication
**Created:** November 12, 2025
**AWS Account:** 019593708315 (agent-space)
**Status:** Ready to Execute

---

## Overview

The Bond AI application in agent-space (019593708315) is currently using Trial Okta for authentication. This guide switches it to use the McAfee Okta instance that is already working in the mosaic-devqa deployment.

### Current Configuration (Trial Okta)
```
Domain:     https://trial-9457917.okta.com
Client ID:  0oas1uz67oWaTK8iP697
Secret:     xhaKsvlah6K_6khDjshL... (in Secrets Manager)
Status:     Working but needs to be replaced
```

### Target Configuration (McAfee Okta)
```
Domain:     https://mcafee.okta.com
Client ID:  0oaqobsogrUx7ywt55d7
Secret:     JIhf_a_... (from mosaic-devqa)
Status:     Already working in mosaic-devqa deployment
```

---

## Prerequisites

Before starting, verify you have:

- [ ] AWS CLI access to both accounts:
  - `agent-space` profile (019593708315)
  - `mosaic-devqa` profile (767397995923)
- [ ] Terraform installed and initialized
- [ ] Access to McAfee Okta admin console
- [ ] Current backend URL: `https://rqs8cicg8h.us-west-2.awsapprunner.com`
- [ ] Current frontend URL: `https://jid5jmztei.us-west-2.awsapprunner.com`

### Verify Access
```bash
# Verify AWS access
AWS_PROFILE=agent-space aws sts get-caller-identity
AWS_PROFILE=mosaic-devqa aws sts get-caller-identity

# Verify Terraform workspace
cd /Users/jcarnahan/projects/bond-ai/deployment/terraform-existing-vpc
terraform workspace list
# Should show: agent-space (with asterisk if selected)
```

---

## Step-by-Step Instructions

### Step 1: Get McAfee Okta Client Secret from mosaic-devqa

```bash
# Get the full McAfee Okta secret from mosaic-devqa Secrets Manager
AWS_PROFILE=mosaic-devqa aws secretsmanager get-secret-value \
  --secret-id bond-ai-dev-okta-secret \
  --region us-west-2 \
  --query SecretString \
  --output text | jq

# This will output something like:
# {
#   "client_secret": "JIhf_a_oidavlIPmyN4f..."
# }

# Copy the entire client_secret value (you'll need it in Step 2)
```

**Save the client_secret value somewhere secure - you'll need it in the next step.**

---

### Step 2: Update Secrets Manager in agent-space

Update the existing secret in agent-space with the McAfee Okta client secret:

```bash
# Replace YOUR_MCAFEE_CLIENT_SECRET with the value from Step 1
AWS_PROFILE=agent-space aws secretsmanager update-secret \
  --secret-id bond-ai-dev-okta-secret \
  --secret-string '{"client_secret":"YOUR_MCAFEE_CLIENT_SECRET"}' \
  --region us-west-2

# Verify the update
AWS_PROFILE=agent-space aws secretsmanager get-secret-value \
  --secret-id bond-ai-dev-okta-secret \
  --region us-west-2 \
  --query SecretString \
  --output text | jq
```

**Expected Output:**
```json
{
  "client_secret": "JIhf_a_oidavlIPmyN4f..."
}
```

---

### Step 3: Update Terraform Configuration File

**File to Edit:** `deployment/terraform-existing-vpc/environments/agent-space.tfvars`

**Lines to Change:** 19-20

**Current Values:**
```hcl
# Okta Trial Configuration
okta_domain      = "https://trial-9457917.okta.com"
okta_client_id   = "0oas1uz67oWaTK8iP697"
okta_secret_name = "bond-ai-dev-okta-secret"  # Already created in Secrets Manager
```

**New Values:**
```hcl
# McAfee Okta Configuration
okta_domain      = "https://mcafee.okta.com"
okta_client_id   = "0oaqobsogrUx7ywt55d7"
okta_secret_name = "bond-ai-dev-okta-secret"  # Already updated in Step 2
```

**Complete Updated Section (lines 16-21):**
```hcl
# ===== REQUIRED: OAuth Configuration =====

# McAfee Okta Configuration
okta_domain      = "https://mcafee.okta.com"
okta_client_id   = "0oaqobsogrUx7ywt55d7"
okta_secret_name = "bond-ai-dev-okta-secret"  # Already updated in Step 2
```

---

### Step 4: Review Terraform Plan

```bash
# Navigate to Terraform directory
cd /Users/jcarnahan/projects/bond-ai/deployment/terraform-existing-vpc

# Ensure you're in the agent-space workspace
terraform workspace select agent-space

# Generate plan to see what will change
AWS_PROFILE=agent-space terraform plan \
  -var-file=environments/agent-space.tfvars \
  -out=tfplan

# Review the output carefully
# Expected changes: Backend App Runner environment variables (OKTA_DOMAIN, OKTA_CLIENT_ID)
```

**Expected Plan Output:**
```
Terraform will perform the following actions:

  # aws_apprunner_service.backend will be updated in-place
  ~ resource "aws_apprunner_service" "backend" {
      ~ source_configuration {
          ~ image_repository {
              ~ image_configuration {
                  ~ runtime_environment_variables = {
                      ~ "OKTA_CLIENT_ID" = "0oas1uz67oWaTK8iP697" -> "0oaqobsogrUx7ywt55d7"
                      ~ "OKTA_DOMAIN"    = "https://trial-9457917.okta.com" -> "https://mcafee.okta.com"
                      ~ "OKTA_CLIENT_SECRET" = (sensitive value)
                    }
                }
            }
        }
    }

Plan: 0 to add, 1 to change, 0 to destroy.
```

**Important:** If the plan shows any resources being destroyed or recreated (not just updated), STOP and investigate before proceeding.

---

### Step 5: Apply Terraform Changes

```bash
# Apply the plan (backend will restart with new Okta config)
AWS_PROFILE=agent-space terraform apply tfplan

# This will take approximately 3-5 minutes
# The backend App Runner service will restart with new environment variables
```

**Expected Output:**
```
aws_apprunner_service.backend: Modifying... [id=...]
aws_apprunner_service.backend: Still modifying... [10s elapsed]
...
aws_apprunner_service.backend: Modifications complete after 3m24s [id=...]

Apply complete! Resources: 0 added, 1 changed, 0 destroyed.
```

---

### Step 6: Verify Backend Health

Wait for the backend to finish restarting, then test:

```bash
# Check backend health endpoint
curl https://rqs8cicg8h.us-west-2.awsapprunner.com/health

# Expected response:
# {"status":"healthy","database":"connected","bedrock":"available"}

# If you get connection errors, wait 1-2 minutes for the service to fully restart
```

**Check App Runner Service Status:**
```bash
# List App Runner services to verify status
AWS_PROFILE=agent-space aws apprunner list-services \
  --region us-west-2 \
  --query 'ServiceSummaryList[?contains(ServiceName, `backend`)]'

# Service should show Status: "RUNNING"
```

---

### Step 7: Update McAfee Okta Application

You need to add the backend callback URL to the McAfee Okta application configuration.

**Okta Admin Console Access:**
- URL: https://mcafee.okta.com (admin console)
- Application: Bond AI (Client ID: 0oaqobsogrUx7ywt55d7)

**Steps:**
1. Login to McAfee Okta admin console
2. Navigate to: **Applications** → **Applications**
3. Find and click on the Bond AI application
4. Click **Edit** in the "General Settings" section
5. Find **Sign-in redirect URIs** field
6. Add the new callback URL:
   ```
   https://rqs8cicg8h.us-west-2.awsapprunner.com/auth/okta/callback
   ```
7. Keep any existing redirect URIs (don't remove them)
8. Click **Save**

**Important:** The redirect URI must match exactly (no trailing slash).

---

### Step 8: Test Authentication Flow

**Browser Testing:**

1. **Open Frontend:**
   ```
   https://jid5jmztei.us-west-2.awsapprunner.com
   ```

2. **Click Login Button**
   - Should redirect to: `https://mcafee.okta.com`
   - NOT to: `https://trial-9457917.okta.com`

3. **Login with McAfee Credentials**
   - Use your McAfee Okta username and password

4. **Verify Successful Authentication**
   - Should redirect back to frontend
   - Should show user dashboard/home page
   - No errors in browser console

**Expected Flow:**
```
Frontend (jid5jmztei...)
  ↓ Click Login
McAfee Okta (mcafee.okta.com)
  ↓ Enter credentials
Backend Callback (rqs8cicg8h.../auth/okta/callback)
  ↓ JWT token issued
Frontend (jid5jmztei...) - User logged in
```

---

### Step 9: Test Agent Creation and Chat

After successful login, verify full functionality:

1. **Navigate to Agents Section**
2. **Create Test Agent:**
   - Name: "Test McAfee Okta Agent"
   - Model: Claude Sonnet 4.5
   - Instructions: "You are a helpful assistant"
3. **Start Conversation:**
   - Send message: "Hello, this is a test after switching to McAfee Okta"
   - Verify response received
4. **Check Conversation History:**
   - Verify messages are saved
   - Refresh page and verify persistence

---

## Step 10 (Optional): Update Local Development Environment

If you want to test locally with McAfee Okta:

**File:** `/Users/jcarnahan/projects/bond-ai/.env`

**Lines to Update:** 42-44

**Change:**
```env
# FROM (Trial Okta):
OKTA_DOMAIN="https://trial-9457917.okta.com"
OKTA_CLIENT_ID="0oas1uz67oWaTK8iP697"
OKTA_CLIENT_SECRET="xhaKsvlah6K_6khDjshL0VquUqQtU132d5NWeEN4pcH3iHVzlHzPAgUD9YLq6yi4"

# TO (McAfee Okta):
OKTA_DOMAIN="https://mcafee.okta.com"
OKTA_CLIENT_ID="0oaqobsogrUx7ywt55d7"
OKTA_CLIENT_SECRET="<paste the client_secret from Step 1>"
```

**Also Update McAfee Okta Application:**
Add localhost callback URL in McAfee Okta admin:
```
http://localhost:8000/auth/okta/callback
```

**Restart Local Services:**
```bash
# Kill any running services
lsof -ti:8000 | xargs kill -9
lsof -ti:5000 | xargs kill -9
lsof -ti:5554 | xargs kill -9

# Restart (in 3 separate terminals)
# Terminal 1 - MCP Server
fastmcp run scripts/sample_mcp_server.py --transport streamable-http --port 5554

# Terminal 2 - Backend
uvicorn bondable.rest.main:app --reload --host 0.0.0.0 --port 8000

# Terminal 3 - Frontend
cd flutterui && flutter run -d chrome --web-port=5000 --target lib/main.dart
```

---

## Verification Checklist

After completing all steps, verify:

- [ ] Backend health endpoint responds (Step 6)
- [ ] Login redirects to https://mcafee.okta.com (not trial-9457917)
- [ ] Can successfully login with McAfee credentials
- [ ] User dashboard loads after login
- [ ] Can create agents
- [ ] Can send messages and receive responses
- [ ] Conversation history persists
- [ ] No errors in CloudWatch logs

---

## Troubleshooting

### Issue 1: Login Still Redirects to Trial Okta

**Symptoms:**
- Login button redirects to https://trial-9457917.okta.com

**Diagnosis:**
```bash
# Check backend environment variables
AWS_PROFILE=agent-space aws apprunner describe-service \
  --service-arn <backend-service-arn> \
  --query 'Service.SourceConfiguration.ImageRepository.ImageConfiguration.RuntimeEnvironmentVariables' \
  | jq '.OKTA_DOMAIN'

# Should return: "https://mcafee.okta.com"
```

**Solution:**
- Verify Step 5 (Terraform apply) completed successfully
- Force backend restart:
  ```bash
  AWS_PROFILE=agent-space aws apprunner start-deployment \
    --service-arn <backend-service-arn>
  ```

### Issue 2: "Invalid Redirect URI" Error

**Symptoms:**
- After McAfee Okta login, error: "redirect_uri_mismatch"

**Cause:**
- Backend callback URL not added to McAfee Okta application

**Solution:**
- Complete Step 7 (Update McAfee Okta Application)
- Ensure callback URL exactly matches (no trailing slash):
  ```
  https://rqs8cicg8h.us-west-2.awsapprunner.com/auth/okta/callback
  ```

### Issue 3: "Invalid Client" Error

**Symptoms:**
- Error: "invalid_client" or "client authentication failed"

**Cause:**
- Client secret in Secrets Manager doesn't match McAfee Okta

**Solution:**
- Verify Step 2 completed correctly
- Re-check client secret:
  ```bash
  # Get from mosaic-devqa (correct value)
  AWS_PROFILE=mosaic-devqa aws secretsmanager get-secret-value \
    --secret-id bond-ai-dev-okta-secret \
    --region us-west-2 --query SecretString --output text | jq -r '.client_secret'

  # Get from agent-space (current value)
  AWS_PROFILE=agent-space aws secretsmanager get-secret-value \
    --secret-id bond-ai-dev-okta-secret \
    --region us-west-2 --query SecretString --output text | jq -r '.client_secret'

  # They should match
  ```

### Issue 4: Backend Won't Start After Update

**Symptoms:**
- Backend service shows "OPERATION_FAILED"
- Health endpoint unreachable

**Diagnosis:**
```bash
# Check service status
AWS_PROFILE=agent-space aws apprunner describe-service \
  --service-arn <backend-service-arn> \
  --query 'Service.Status'

# Check CloudWatch logs
AWS_PROFILE=agent-space aws logs tail \
  /aws/apprunner/bond-ai-dev-backend/service \
  --follow
```

**Solution:**
- Check CloudWatch logs for specific error
- Verify all environment variables are set correctly
- If needed, rollback to trial Okta (see Rollback section)

---

## Rollback Plan

If you encounter issues and need to revert to Trial Okta:

### Quick Rollback

```bash
cd /Users/jcarnahan/projects/bond-ai/deployment/terraform-existing-vpc

# 1. Restore trial Okta client secret
AWS_PROFILE=agent-space aws secretsmanager update-secret \
  --secret-id bond-ai-dev-okta-secret \
  --secret-string '{"client_secret":"xhaKsvlah6K_6khDjshL0VquUqQtU132d5NWeEN4pcH3iHVzlHzPAgUD9YLq6yi4"}' \
  --region us-west-2

# 2. Edit agent-space.tfvars - change back to:
# okta_domain      = "https://trial-9457917.okta.com"
# okta_client_id   = "0oas1uz67oWaTK8iP697"

# 3. Re-apply Terraform
terraform workspace select agent-space
terraform plan -var-file=environments/agent-space.tfvars -out=tfplan
terraform apply tfplan

# 4. Verify health
curl https://rqs8cicg8h.us-west-2.awsapprunner.com/health
```

---

## CloudWatch Logs

Monitor the backend during and after the switch:

```bash
# Tail backend logs in real-time
AWS_PROFILE=agent-space aws logs tail \
  /aws/apprunner/bond-ai-dev-backend/service \
  --region us-west-2 \
  --follow

# Look for:
# - "Starting application" (after restart)
# - Okta configuration messages
# - Any authentication errors
```

---

## Post-Switch Actions

After successful switch:

1. **Update Documentation:**
   - Update `MCAFEEAGENTICSTUDIO-DEV-DEPLOYMENT.md`
   - Change Okta references from trial to McAfee

2. **Notify Team:**
   - Inform users that Trial Okta accounts no longer work
   - Users must use McAfee Okta credentials

3. **Test Thoroughly:**
   - Test with multiple McAfee users
   - Verify all features (agents, chat, file uploads)
   - Monitor CloudWatch logs for errors

4. **Archive Trial Okta:**
   - Consider deactivating Trial Okta application
   - Keep credentials documented for reference

---

## Reference Information

### Current Deployment Details

**AWS Account:** 019593708315 (agent-space)
**Region:** us-west-2
**Terraform Workspace:** agent-space

**Services:**
- Backend: https://rqs8cicg8h.us-west-2.awsapprunner.com
- Frontend: https://jid5jmztei.us-west-2.awsapprunner.com
- Database: bond-ai-dev-db.cb4kk2sa2lrb.us-west-2.rds.amazonaws.com:5432

**Secrets Manager:**
- Okta Secret: bond-ai-dev-okta-secret
- Database Secret: bond-ai-dev-db-20251112200642294900000001

### McAfee Okta Details

**Domain:** https://mcafee.okta.com
**Client ID:** 0oaqobsogrUx7ywt55d7
**Secret Location:** mosaic-devqa Secrets Manager → bond-ai-dev-okta-secret

**Required Redirect URIs:**
```
https://rqs8cicg8h.us-west-2.awsapprunner.com/auth/okta/callback  (Production)
http://localhost:8000/auth/okta/callback                           (Local Dev)
```

### Trial Okta Details (for reference)

**Domain:** https://trial-9457917.okta.com
**Client ID:** 0oas1uz67oWaTK8iP697
**Secret:** xhaKsvlah6K_6khDjshL0VquUqQtU132d5NWeEN4pcH3iHVzlHzPAgUD9YLq6yi4

---

## Estimated Time

- Step 1-3: 5 minutes (AWS CLI commands and file edit)
- Step 4-5: 3 minutes (Terraform plan and apply)
- Step 6: 2 minutes (Wait for service restart)
- Step 7: 5 minutes (Update Okta admin console)
- Step 8-9: 5 minutes (Testing)
- **Total: ~20 minutes**

---

## Success Criteria

The switch is successful when:

✅ Login redirects to https://mcafee.okta.com
✅ Can authenticate with McAfee credentials
✅ User dashboard loads after login
✅ Can create agents and chat
✅ No errors in CloudWatch logs
✅ Backend health check passes

---

## Notes

- The frontend does NOT need to be redeployed (it's agnostic to Okta provider)
- Only the backend App Runner service restarts
- Database and other services are not affected
- The switch is reversible (see Rollback Plan)
- No data loss occurs during the switch

---

**Document Status:** Ready to Execute
**Created:** November 12, 2025
**Last Updated:** November 12, 2025
**Next Review:** After successful switch
