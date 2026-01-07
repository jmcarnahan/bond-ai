# MCP Atlassian Service: Private Configuration Guide

## Overview

This guide provides step-by-step instructions for configuring the MCP Atlassian service to use private endpoints instead of public access. This improves security by restricting access to only services within your VPC.

**Current State**: MCP service is publicly accessible
**Target State**: MCP service accessible only via VPC PrivateLink
**Impact**: Backend service will continue to work; external access will be blocked

---

## Table of Contents

1. [Why Make This Change](#why-make-this-change)
2. [Network Architecture](#network-architecture)
3. [AWS Console Configuration](#aws-console-configuration)
4. [Verification Steps](#verification-steps)
5. [Terraform Code Changes](#terraform-code-changes)
6. [Rollback Procedures](#rollback-procedures)
7. [Troubleshooting](#troubleshooting)

---

## Why Make This Change

### Security Benefits

**Current Risk (Public Access)**:
- MCP endpoint accessible from internet
- Larger attack surface
- Relies solely on OAuth token security
- Discoverable via port scanning

**After Private Configuration**:
- Network-level isolation (VPC only)
- Defense in depth: VPC + Security Groups + OAuth
- Not discoverable from internet
- Meets enterprise security compliance requirements

### No Breaking Changes

The backend service will continue to work because:
- Both backend and MCP services share the same VPC connector (`bond-ai-dev-connector`)
- App Runner PrivateLink allows services in the same VPC to communicate
- The public DNS name remains the same, but resolves to a private IP when accessed from within VPC

---

## Network Architecture

### Current State (Public)

```
┌─────────────────┐
│   Internet      │
└────────┬────────┘
         │
    ┌────┴────┐
    │         │
    ▼         ▼
┌─────────┐ ┌──────────────┐
│ Backend │ │ MCP Atlassian│
│  PUBLIC │ │    PUBLIC    │
└────┬────┘ └──────┬───────┘
     │             │
     │  VPC Egress │
     └──────┬──────┘
            ▼
     ┌──────────────┐
     │     VPC      │
     │ 10.4.231.0/24│
     └──────────────┘
```

Backend reaches MCP via: **Internet (public URL)**

### Target State (Private)

```
┌─────────────────┐
│   Internet      │
└────────┬────────┘
         │
         ▼
    ┌─────────┐
    │ Backend │
    │  PUBLIC │
    └────┬────┘
         │
         │ VPC Egress
         ▼
  ┌──────────────┐
  │     VPC      │
  │ 10.4.231.0/24│
  │              │
  │ PrivateLink  │
  │      ↓       │
  │ ┌──────────┐ │
  │ │   MCP    │ │
  │ │ PRIVATE  │ │
  │ └──────────┘ │
  └──────────────┘
```

Backend reaches MCP via: **VPC Connector → VPC → PrivateLink → MCP (private endpoint)**

### Traffic Flow After Change

1. Backend container makes HTTPS request to `https://fa3vbibtmu.us-west-2.awsapprunner.com/mcp/`
2. App Runner VPC Connector routes request through VPC subnets
3. AWS PrivateLink resolves MCP service's private endpoint
4. MCP service receives request on private interface (VPC only)
5. Response flows back through same path

---

## AWS Console Configuration

### Prerequisites

Before starting, verify:
- AWS Profile: `agent-space`
- AWS Region: `us-west-2`
- Backend service: `bond-ai-dev-backend` (running and healthy)
- MCP service: `bond-ai-dev-mcp-atlassian` (running and healthy)
- VPC Connector: `bond-ai-dev-connector` (active)

### Step-by-Step Instructions

#### Step 1: Navigate to App Runner Service

1. Open **AWS Console** in your browser
2. Go to **Services** → **App Runner**
3. Verify region selector shows: **US West (Oregon) us-west-2**
4. In the services list, find: **bond-ai-dev-mcp-atlassian**
5. Click on the service name to open details

#### Step 2: Open Network Configuration

1. Click the **"Configuration"** tab (near the top)
2. Scroll down to the **"Networking"** section
3. You should see two subsections:
   - **Incoming traffic**
   - **Outgoing traffic**
4. In the **"Incoming traffic"** subsection, click the **"Edit"** button

#### Step 3: Change to Private Endpoint

In the "Edit incoming network traffic" page:

1. Under **"Incoming network traffic"** section:
   - Current setting: ✅ **Public endpoint**
     - Description: "Accessible from the public internet"
   - Change to: ✅ **Private endpoint**
     - Description: "Only accessible from your VPC"

2. Verify VPC settings are correct (should auto-populate):
   - **VPC connector**: `bond-ai-dev-connector`
   - **ARN**: `arn:aws:apprunner:us-west-2:019593708315:vpcconnector/bond-ai-dev-connector/1/...`

3. Review the change summary at the bottom:
   ```
   Changes to be applied:
   - Incoming traffic: Public endpoint → Private endpoint
   ```

#### Step 4: Save and Deploy

1. Click **"Save changes"** button (bottom right)
2. You'll see a banner: "Updating service configuration..."
3. The service status will change to: **"Operation in progress"**
4. Wait **2-5 minutes** for the deployment to complete
5. The status will change to: **"Operation completed"**
6. Service health should remain: **"Healthy"**

#### Step 5: Verify Configuration

After deployment completes:

1. In the **Configuration** tab, verify:
   - **Incoming traffic** shows: "Private endpoint"
   - **VPC connector**: bond-ai-dev-connector
2. Note the **Service URL** (should be unchanged):
   - `https://fa3vbibtmu.us-west-2.awsapprunner.com`

---

## Verification Steps

Run these tests to confirm the configuration is working correctly.

### Test 1: Backend Can Still Reach MCP Service

**Purpose**: Verify backend service can reach MCP via VPC

**Command**:
```bash
# From your local machine
curl -v https://rqs8cicg8h.us-west-2.awsapprunner.com/mcp/status
```

**Expected Result**:
```json
{
  "servers_configured": 1,
  "client_initialized": true,
  "server_details": ["atlassian"]
}
```

**What This Tests**: Backend acts as a proxy, confirming it can reach the private MCP service through the VPC connector.

### Test 2: Direct Public Access is Blocked

**Purpose**: Verify MCP service is no longer accessible from internet

**Command**:
```bash
# From your local machine (outside VPC)
curl -v --max-time 10 https://fa3vbibtmu.us-west-2.awsapprunner.com/mcp/
```

**Expected Result**:
- Connection timeout, OR
- `403 Forbidden`, OR
- `Connection refused`

**What This Tests**: Confirms the service is not accessible from public internet.

### Test 3: Check Backend Logs for Errors

**Purpose**: Verify backend is not experiencing connection errors

**Command**:
```bash
AWS_PROFILE=agent-space aws logs tail /aws/apprunner/bond-ai-dev-backend/service \
  --region us-west-2 \
  --since 10m \
  --filter-pattern "MCP"
```

**Expected Result**:
- ✅ Look for: `[MCP Tools] Server 'atlassian' authenticated`
- ✅ Look for: `[MCP Execute] Found tool 'X' on server 'atlassian'`
- ❌ Should NOT see: `Connection refused`, `Timeout`, `Name resolution failed`

### Test 4: Test MCP Tools Endpoint

**Purpose**: Verify MCP tools are accessible via backend

**Command**:
```bash
# Get JWT token from browser dev tools after logging in
TOKEN="<your-jwt-token>"

curl -H "Authorization: Bearer $TOKEN" \
     https://rqs8cicg8h.us-west-2.awsapprunner.com/mcp/tools
```

**Expected Result**:
```json
{
  "tools": [
    {
      "name": "atlassian__search",
      "server": "atlassian",
      "description": "Search Jira and Confluence using Rovo Search"
    },
    // ... more tools
  ]
}
```

### Test 5: End-to-End OAuth Flow

**Purpose**: Verify Atlassian OAuth still works

**Steps**:
1. Open frontend: `https://jid5jmztei.us-west-2.awsapprunner.com`
2. Navigate to MCP connections page
3. Click "Connect" for Atlassian
4. Complete OAuth flow on Atlassian site
5. Verify you're redirected back with "Connected" status

**Expected Result**: OAuth flow completes successfully, connection shows as active.

### Test 6: VPC Connector Health

**Purpose**: Verify VPC connector is active

**Command**:
```bash
AWS_PROFILE=agent-space aws apprunner describe-vpc-connector \
  --vpc-connector-arn "arn:aws:apprunner:us-west-2:019593708315:vpcconnector/bond-ai-dev-connector/1/XXX" \
  --region us-west-2 \
  --query "VpcConnector.Status"
```

**Expected Result**: `"ACTIVE"`

---

## Terraform Code Changes

After verifying the console configuration works, update Terraform to match.

### Files to Modify

#### 1. Update MCP Service Configuration

**File**: `deployment/terraform-existing-vpc/mcp-atlassian.tf`

**Change at Line 363**:

```hcl
# BEFORE (Current)
network_configuration {
  ingress_configuration {
    is_publicly_accessible = true  # ← Change this to false
  }

  egress_configuration {
    egress_type       = "VPC"
    vpc_connector_arn = aws_apprunner_vpc_connector.backend.arn
  }
}
```

```hcl
# AFTER (Target)
network_configuration {
  ingress_configuration {
    is_publicly_accessible = false  # ← Changed from true
  }

  egress_configuration {
    egress_type       = "VPC"
    vpc_connector_arn = aws_apprunner_vpc_connector.backend.arn
  }
}
```

**Explanation**: This single boolean flag controls whether the App Runner service is accessible from the public internet or only via VPC PrivateLink.

#### 2. Update Documentation (Optional)

**File**: `deployment/terraform-existing-vpc/MCP_ATLASSIAN_DEPLOYMENT.md`

**Current State**: Already correctly documents the service as private (line 163)

**No change needed** - documentation is already correct.

### Terraform Commands to Run

After making the code change:

```bash
# Navigate to Terraform directory
cd deployment/terraform-existing-vpc

# Initialize Terraform (if needed)
terraform init

# Verify the change matches console state
terraform plan -var-file=environments/agent-space.tfvars

# Expected output:
# "No changes. Your infrastructure matches the configuration."

# If Terraform shows it wants to make changes, run:
terraform refresh -var-file=environments/agent-space.tfvars

# Then plan again
terraform plan -var-file=environments/agent-space.tfvars

# Apply to sync Terraform state (should be no-op if console is already configured)
terraform apply -var-file=environments/agent-space.tfvars
```

### Expected Terraform Plan Output

If you've already made the console change, Terraform plan should show:

```
No changes. Your infrastructure matches the configuration.

Your infrastructure matches the configuration.

Terraform has compared your real infrastructure against your configuration
and found no differences, so no changes are needed.
```

If Terraform shows it wants to make changes, it means the console change hasn't been applied yet.

### Git Commit Message

After verifying Terraform matches:

```bash
git add deployment/terraform-existing-vpc/mcp-atlassian.tf
git commit -m "Configure MCP Atlassian service as private (VPC-only access)

- Change is_publicly_accessible from true to false
- Service now only accessible via VPC PrivateLink
- Backend service can still reach MCP via shared VPC connector
- Improves security by removing public internet exposure
- Reduces attack surface and meets compliance requirements"
```

---

## Rollback Procedures

If issues occur after making the service private, you can easily rollback.

### Immediate Rollback (AWS Console)

**Time to Complete**: 2-5 minutes

1. Open **AWS Console** → **App Runner**
2. Select region: **us-west-2**
3. Click on service: **bond-ai-dev-mcp-atlassian**
4. Go to **Configuration** tab
5. In **Networking** section, click **"Edit"** for "Incoming traffic"
6. Change selection:
   - From: ✅ **Private endpoint**
   - To: ✅ **Public endpoint**
7. Click **"Save changes"**
8. Wait 2-5 minutes for deployment
9. Verify service health is **"Healthy"**

### Rollback Terraform Changes

If you've committed the Terraform change and need to revert:

```bash
# Option 1: Revert the commit
git revert <commit-hash>
git push

# Option 2: Manual revert
# Edit deployment/terraform-existing-vpc/mcp-atlassian.tf
# Change line 363: is_publicly_accessible = false → true

# Apply the change
cd deployment/terraform-existing-vpc
terraform apply -var-file=environments/agent-space.tfvars
```

---

## Troubleshooting

### Issue 1: Backend Cannot Reach MCP Service

**Symptoms**:
- Backend logs show: `Connection refused` or `Timeout`
- `/mcp/tools` returns empty list
- `/mcp/status` shows "No MCP servers configured"

**Diagnosis Steps**:

1. **Check VPC Connector Status**:
```bash
AWS_PROFILE=agent-space aws apprunner describe-vpc-connector \
  --vpc-connector-arn "arn:aws:apprunner:us-west-2:019593708315:vpcconnector/bond-ai-dev-connector/1/XXX" \
  --region us-west-2
```

Expected: `"Status": "ACTIVE"`

2. **Verify Both Services Use Same VPC Connector**:
```bash
# Check backend service
AWS_PROFILE=agent-space aws apprunner describe-service \
  --service-arn "arn:aws:apprunner:us-west-2:019593708315:service/bond-ai-dev-backend" \
  --region us-west-2 \
  --query "Service.NetworkConfiguration.EgressConfiguration.VpcConnectorArn"

# Check MCP service
AWS_PROFILE=agent-space aws apprunner describe-service \
  --service-arn "arn:aws:apprunner:us-west-2:019593708315:service/bond-ai-dev-mcp-atlassian" \
  --region us-west-2 \
  --query "Service.NetworkConfiguration.EgressConfiguration.VpcConnectorArn"
```

Both should return the same ARN.

3. **Check Security Group Rules**:
```bash
AWS_PROFILE=agent-space aws ec2 describe-security-groups \
  --filters "Name=group-name,Values=bond-ai-dev-apprunner-sg" \
  --region us-west-2 \
  --query "SecurityGroups[0].IpPermissionsEgress"
```

Should allow all outbound traffic (0.0.0.0/0).

**Solution**:
- Verify VPC connector ARN matches in both services
- Ensure security group allows outbound traffic
- Check CloudWatch logs for specific error messages
- If issue persists, rollback to public endpoint

### Issue 2: DNS Resolution Fails

**Symptoms**:
- Backend logs: `Name or service not known`
- Connection attempts fail with DNS errors

**Diagnosis**:

1. **Check VPC DNS Settings**:
```bash
AWS_PROFILE=agent-space aws ec2 describe-vpc-attribute \
  --vpc-id vpc-0f15dee1f11b1bf06 \
  --attribute enableDnsHostnames \
  --region us-west-2

AWS_PROFILE=agent-space aws ec2 describe-vpc-attribute \
  --vpc-id vpc-0f15dee1f11b1bf06 \
  --attribute enableDnsSupport \
  --region us-west-2
```

Both should return: `"Value": true`

2. **Verify VPC Endpoints**:
```bash
AWS_PROFILE=agent-space aws ec2 describe-vpc-endpoints \
  --region us-west-2 \
  --filters "Name=vpc-id,Values=vpc-0f15dee1f11b1bf06"
```

**Solution**:
- Enable DNS hostnames on VPC if disabled
- Enable DNS resolution on VPC if disabled
- Verify Route 53 resolver is working

### Issue 3: OAuth Callback Fails

**Symptoms**:
- Atlassian OAuth redirects to backend but returns error
- Backend logs show: `Invalid state parameter`

**Analysis**:
This should NOT occur because OAuth callback goes to the **backend** service (which is still public), not the MCP service.

OAuth flow:
1. User clicks "Connect Atlassian" on frontend
2. Redirects to Atlassian OAuth page
3. Atlassian redirects to: `https://rqs8cicg8h.us-west-2.awsapprunner.com/connections/atlassian/callback`
4. Backend receives callback, stores tokens in database
5. Backend uses tokens to authenticate with MCP service

**Solution**:
- Verify backend service is still publicly accessible
- Check backend logs for OAuth-related errors
- Verify callback URL in Atlassian OAuth app settings

### Issue 4: Terraform Shows Drift

**Symptoms**:
- After console change, `terraform plan` shows it wants to revert to public
- Terraform state doesn't match AWS reality

**Solution**:

1. **Refresh Terraform State**:
```bash
cd deployment/terraform-existing-vpc
terraform refresh -var-file=environments/agent-space.tfvars
```

2. **If still shows drift, update code first**:
```bash
# Edit mcp-atlassian.tf line 363: change true to false
terraform plan -var-file=environments/agent-space.tfvars
# Should now show: No changes
```

3. **If Terraform insists on reverting**:
```bash
# Import current state
terraform import -var-file=environments/agent-space.tfvars \
  aws_apprunner_service.mcp_atlassian \
  "arn:aws:apprunner:us-west-2:019593708315:service/bond-ai-dev-mcp-atlassian"
```

---

## Monitoring and Alerts

### CloudWatch Metrics to Monitor

After making the change, monitor these metrics for 24-48 hours:

1. **MCP Service Health**:
   - Metric: `HealthChecksPassed`
   - Service: bond-ai-dev-mcp-atlassian
   - Alert if: < 1 for 5 minutes

2. **Backend Request Errors**:
   - Metric: `4xxStatusResponses`
   - Service: bond-ai-dev-backend
   - Alert if: Rate > 10 per minute

3. **MCP Service Request Count**:
   - Metric: `RequestCount`
   - Service: bond-ai-dev-mcp-atlassian
   - Alert if: 0 requests for 10 minutes (during business hours)

### Log Patterns to Watch

```bash
# Monitor for connection errors
AWS_PROFILE=agent-space aws logs tail /aws/apprunner/bond-ai-dev-backend/service \
  --region us-west-2 \
  --follow \
  --filter-pattern "Connection refused"

# Monitor for MCP errors
AWS_PROFILE=agent-space aws logs tail /aws/apprunner/bond-ai-dev-backend/service \
  --region us-west-2 \
  --follow \
  --filter-pattern "[MCP Execute] Error"
```

---

## Cost Impact

Making the service private has **NO cost impact**:
- App Runner pricing is the same for public and private endpoints
- VPC connector cost remains unchanged (already in use for egress)
- No additional data transfer charges (traffic stays within AWS network)
- May reduce egress costs slightly (traffic doesn't leave AWS network)

---

## Security Improvements

### Before (Public)

| Layer | Protection |
|-------|------------|
| Network | None - accessible from internet |
| Application | OAuth tokens only |
| Transport | HTTPS/TLS |

### After (Private)

| Layer | Protection |
|-------|------------|
| Network | **VPC isolation - not accessible from internet** |
| VPC | **Security groups control traffic** |
| Application | OAuth tokens |
| Transport | HTTPS/TLS |

**Defense in Depth**: Multiple layers of security make it much harder for attackers to reach the service.

---

## Summary Checklist

Use this checklist to track your progress:

### Phase 1: AWS Console Configuration
- [ ] Logged into AWS Console (region: us-west-2)
- [ ] Navigated to App Runner → bond-ai-dev-mcp-atlassian
- [ ] Changed incoming traffic from Public to Private endpoint
- [ ] Saved changes and waited for deployment (2-5 minutes)
- [ ] Verified service status is "Running" and "Healthy"

### Phase 2: Verification
- [ ] Test 1: Backend can reach MCP (`/mcp/status` works)
- [ ] Test 2: Direct public access is blocked (curl times out)
- [ ] Test 3: No connection errors in backend logs
- [ ] Test 4: MCP tools endpoint returns list of tools
- [ ] Test 5: OAuth flow completes successfully
- [ ] Test 6: VPC connector status is ACTIVE

### Phase 3: Terraform Update
- [ ] Updated `mcp-atlassian.tf` line 363: `is_publicly_accessible = false`
- [ ] Ran `terraform plan` and verified no changes needed
- [ ] Committed change with descriptive message
- [ ] Pushed to repository

### Phase 4: Monitoring
- [ ] Monitored CloudWatch logs for 24-48 hours
- [ ] No connection errors observed
- [ ] All MCP functionality working normally
- [ ] Configuration considered stable

---

## Questions or Issues?

If you encounter any issues not covered in this guide:

1. Check the [Troubleshooting](#troubleshooting) section
2. Review CloudWatch logs for specific error messages
3. Consider rolling back to public endpoint if issues persist
4. Document the issue and consult AWS support if needed

---

**Document Version**: 1.0
**Last Updated**: 2025-12-09
**Author**: Claude Code Analysis
