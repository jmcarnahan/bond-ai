# Troubleshooting Session Summary - Okta Authentication Timeout Issue

**Date:** September 25, 2025
**Issue:** Okta OAuth authentication timing out with connection errors
**Objective:** Fix external internet connectivity for App Runner service while maintaining VPC endpoints for AWS services

## Problem Statement

After implementing VPC networking fixes based on the working git stash configuration and VPC_NETWORKING_FIXES.md.txt blueprint, the deployment is failing with Okta authentication timeouts:

```
Connection to trial-9457917.okta.com timed out. (connect timeout=None)
HTTPSConnectionPool(host='trial-9457917.okta.com', port=443): Max retries exceeded with url: /oauth2/v1/token
```

## Current Infrastructure Analysis

### ✅ What IS Working Correctly

1. **VPC Endpoints for AWS Services** - All functioning perfectly:
   - S3 Gateway Endpoint (free)
   - Secrets Manager Interface Endpoint
   - Bedrock Interface Endpoint
   - CloudWatch Logs Interface Endpoint

2. **AWS Services Connectivity** (from backend logs):
   - ✅ Bedrock provider initialization successful
   - ✅ RDS database connectivity working
   - ✅ S3 bucket creation successful (`bond-bedrock-files-c66cca2be305447d938cd91d9d36f80e`)
   - ✅ All AWS authentication and service calls working

3. **Partial OAuth Flow**:
   - ✅ User redirect to Okta works (browser → Okta)
   - ✅ Okta callback works (Okta → App Runner with auth code)
   - ❌ Token exchange fails (App Runner → Okta timeout)

4. **Routing Configuration**:
   - App Runner subnets have proper route table associations:
     - `subnet-018084036d2aa635d` → `rtb-02f6af532c2d2f9fe` → Internet Gateway ✅
     - `subnet-08997a58c3a22aad2` → `rtb-02f6af532c2d2f9fe` → Internet Gateway ✅
     - `subnet-0374d7b91b2054239` → `rtb-03dfd8d37cf55f279` → NAT Gateway ✅

5. **Security Groups**:
   - App Runner SG allows all outbound traffic (`0.0.0.0/0` on all protocols) ✅
   - VPC endpoints SG allows HTTPS from App Runner ✅

### ❌ What is NOT Working

1. **External HTTPS Connectivity**:
   - App Runner cannot reach `trial-9457917.okta.com:443`
   - 4+ minute timeout suggests complete connectivity failure
   - Issue occurs during OAuth token exchange step

## Implementation History

### Working Configuration (Git Stash)

The working git stash (`stash@{0}`) contained:
- ✅ Backend memory/CPU increases (1GB memory, 0.5 vCPU)
- ✅ VPC endpoints security group
- ✅ Updated data sources with route table references
- ❌ **No VPC endpoints file** - used internet connectivity for AWS services

### Current Implementation

Based on VPC_NETWORKING_FIXES.md.txt blueprint:
- ✅ Created `vpc-endpoints.tf` with all AWS service endpoints
- ✅ Applied all changes from git stash
- ✅ VPC endpoints working perfectly for AWS services
- ❌ External connectivity broken

## Troubleshooting Attempts

### Attempt 1: Add Internet Route to Main Route Table
**Approach:** Add `0.0.0.0/0` route to main route table (`rtb-04dadabfd6cbede09`)
**Result:** ❌ Failed - Service Control Policy blocks `ec2:CreateRoute`
**Error:** `You are not authorized to perform: ec2:CreateRoute on resource: arn:aws:ec2:us-west-2:767397995923:route-table/rtb-04dadabfd6cbede09 with an explicit deny in a service control policy`

### Attempt 2: Create Custom Route Table for App Runner
**Approach:** Create new route table with internet connectivity and associate App Runner subnets
**Result:** ❌ Failed - Service Control Policy blocks `ec2:CreateRouteTable`
**Error:** `You are not authorized to perform: ec2:CreateRouteTable on resource: arn:aws:ec2:us-west-2:767397995923:vpc/vpc-08acfe7cf84c026c7 with an explicit deny in a service control policy`

### Files Archived
- `networking-fixes.tf` → `archive/networking-fixes.tf`

## Root Cause Analysis

### Key Discovery: Routing is NOT the Issue

Investigation revealed that App Runner subnets **DO** have internet connectivity:
- Route tables properly configured with Internet Gateway and NAT Gateway routes
- Security groups allow all outbound traffic
- AWS services work perfectly (proving VPC connectivity is functional)

### Likely Root Causes

1. **VPC Endpoints DNS Interference**:
   - VPC endpoints may be affecting DNS resolution for external services
   - Private DNS settings could be causing conflicts

2. **Network ACLs** (not investigated yet):
   - Subnet-level network ACLs might block external HTTPS
   - Default ACLs usually allow all traffic

3. **Corporate Network Policies**:
   - Service Control Policies clearly restrict route modifications
   - May also restrict external connectivity patterns

4. **VPC Egress Mode Conflicts**:
   - App Runner in VPC egress mode may have different connectivity behavior
   - External connectivity may require specific configuration

## Current Configuration Status

### Files in Current State
- ✅ `vpc-endpoints.tf` - Working perfectly for AWS services
- ✅ `backend.tf` - Memory/CPU increases applied
- ✅ `data-sources.tf` - Route table data sources and subnet selection
- ✅ `security.tf` - VPC endpoints security group
- 📁 `archive/networking-fixes.tf` - Failed routing attempts

### Infrastructure State
- ✅ VPC endpoints deployed and functional
- ✅ App Runner service running with increased resources
- ✅ All AWS service connectivity working
- ❌ External internet connectivity failing for Okta

## Next Steps / Investigation Areas

### Option 1: Test Without VPC Egress Mode
- Temporarily disable VPC egress mode for App Runner
- Test if external connectivity works with public internet access
- This would confirm if VPC configuration is the issue

### Option 2: Investigate Network ACLs
- Check subnet-level Network ACLs for outbound HTTPS restrictions
- Verify default ACL settings allow port 443 outbound

### Option 3: DNS Resolution Investigation
- Test DNS resolution within App Runner environment
- Check if VPC endpoints are interfering with external DNS
- Investigate private DNS settings conflicts

### Option 4: VPC Endpoints Selective Removal
- Temporarily remove specific VPC endpoints to test isolation
- Test if removing interface endpoints resolves external connectivity
- Keep S3 gateway endpoint (free and less likely to cause issues)

### Option 5: Alternative Authentication Approach
- Consider using App Runner without VPC egress for OAuth flows
- Implement hybrid approach: public for auth, VPC for AWS services

## Key Lessons Learned

1. **SCP Restrictions**: Service Control Policies prevent any route table modifications
2. **VPC Endpoints Work**: AWS service connectivity is perfect through VPC endpoints
3. **Routing Not the Issue**: App Runner subnets have proper internet routes
4. **Partial OAuth Success**: Browser-based flows work, server-to-server fails
5. **Infrastructure Approach**: Need solution that doesn't require route modifications

## Log Evidence

**Successful AWS Operations:**
```
[2025-09-25 00:24:17,220] INFO - Initialized AWS clients in region us-west-2
[2025-09-25 00:24:17,641] INFO - Created all Bedrock metadata tables
[2025-09-25 00:24:18,326] INFO - Created S3 bucket: bond-bedrock-files-c66cca2be305447d938cd91d9d36f80e
```

**Failed External Connectivity:**
```
[2025-09-25 00:28:39,879] ERROR - Connection to trial-9457917.okta.com timed out. (connect timeout=None)
HTTPSConnectionPool(host='trial-9457917.okta.com', port=443): Max retries exceeded with url: /oauth2/v1/token
```

## Recommendations

1. **Priority 1**: Test without VPC egress mode to confirm external connectivity capability
2. **Priority 2**: Investigate Network ACLs as potential blocking mechanism
3. **Priority 3**: Consider selective VPC endpoint removal to isolate DNS conflicts
4. **Future**: Document any SCP exceptions needed for proper VPC management

This summary captures our complete investigation and provides clear next steps without repeating failed approaches.