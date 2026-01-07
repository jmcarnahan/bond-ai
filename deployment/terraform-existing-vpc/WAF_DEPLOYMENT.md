# AWS WAF Deployment Guide

## Overview

This document describes the AWS WAF (Web Application Firewall) configuration for the Bond AI deployment. The WAF protects all three App Runner services (backend, frontend, and MCP Atlassian) from common web exploits and attacks.

**Date Created**: December 27, 2025
**AWS Account**: 019593708315 (agent-space)
**Region**: us-west-2

## Architecture

### Protected Services

| Service | WAF Web ACL Name | App Runner URL |
|---------|------------------|----------------|
| Backend | bond-ai-dev-backend-waf | rqs8cicg8h.us-west-2.awsapprunner.com |
| Frontend | bond-ai-dev-frontend-waf | jid5jmztei.us-west-2.awsapprunner.com |
| MCP Atlassian | bond-ai-dev-mcp-atlassian-waf | fa3vbibtmu.us-west-2.awsapprunner.com |

### Rule Groups

Each WAF Web ACL contains three AWS Managed Rule Groups:

1. **AWSManagedRulesCommonRuleSet** (700 WCU)
   - Protects against common web exploits (SQL injection, XSS, LFI, RFI)
   - Provides baseline security for web applications
   - **SPECIAL CONFIG FOR BACKEND**: SizeRestrictions_BODY rule overridden to COUNT (see below)

2. **AWSManagedRulesKnownBadInputsRuleSet** (200 WCU)
   - Protects against known malicious request patterns
   - Includes patterns for Log4j, path traversal, and other CVEs
   - Blocks requests with signatures of known attacks

3. **AWSManagedRulesUnixRuleSet** (100 WCU)
   - Protects against Unix/Linux OS-level attacks
   - Blocks command injection, LFI, and shell-related exploits
   - Essential for container-based deployments

**Total WCU per WAF**: 1,000 (well under the 5,000 regional limit)

## Critical Configuration: File Upload Support

### The Problem

The `SizeRestrictions_BODY` rule in the CommonRuleSet blocks HTTP requests with large request bodies (default limit is 8KB). This caused file uploads to the `/files` endpoint to fail with a 403 Forbidden error.

**Error Observed**:
```
POST https://rqs8cicg8h.us-west-2.awsapprunner.com/files net::ERR_FAILED 403 (Forbidden)
WAF Rule: AWS#AWSManagedRulesCommonRuleSet#SizeRestrictions_BODY
Action: BLOCK
```

### The Solution

For the **backend WAF only**, we override the `SizeRestrictions_BODY` rule action from BLOCK to COUNT:

```hcl
rule_action_override {
  name = "SizeRestrictions_BODY"
  action_to_use {
    count {}
  }
}
```

**How This Works**:
- The rule still evaluates every request
- CloudWatch metrics are still collected
- The rule is counted but does NOT block requests
- File uploads of any size are allowed to the backend

**Why Only Backend**:
- Frontend serves static assets and doesn't handle file uploads
- MCP Atlassian doesn't have file upload requirements
- This minimizes the security exposure to only where needed

## Deployment Instructions

### Prerequisites

- AWS CLI configured with `agent-space` profile
- Terraform installed (version >= 1.0)
- Existing App Runner services deployed
- Existing WAF Web ACLs (if importing)

### Option 1: Import Existing WAFs (Recommended)

If you manually created WAFs in the AWS Console, use this approach to bring them under Terraform management without disruption.

#### Step 1: Get WAF IDs

The WAF IDs are the UUID portion of the WAF ARN:

```
arn:aws:wafv2:us-west-2:019593708315:regional/webacl/bond-ai-dev-backend-waf/0499b6b4-0f92-44bf-858c-4655452e0f75
                                                                             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
                                                                                        This is the ID
```

**Current WAF IDs**:
- Backend: `0499b6b4-0f92-44bf-858c-4655452e0f75`
- Frontend: `b9587353-ea84-4317-b3c4-720c78b39691`
- MCP Atlassian: `e950ad4c-56ad-4cee-917d-3c28aabd2209`

#### Step 2: Get App Runner ARNs

```bash
export AWS_PROFILE=agent-space

# Backend ARN
terraform state show aws_apprunner_service.backend | grep '^arn'

# Frontend ARN
terraform state show aws_apprunner_service.frontend | grep '^arn'

# MCP Atlassian ARN
terraform state show 'aws_apprunner_service.mcp_atlassian[0]' | grep '^arn'
```

#### Step 3: Import WAF Web ACLs

```bash
cd deployment/terraform-existing-vpc

# Import backend WAF
terraform import 'aws_wafv2_web_acl.backend[0]' \
  '0499b6b4-0f92-44bf-858c-4655452e0f75/bond-ai-dev-backend-waf/REGIONAL'

# Import frontend WAF
terraform import 'aws_wafv2_web_acl.frontend[0]' \
  'b9587353-ea84-4317-b3c4-720c78b39691/bond-ai-dev-frontend-waf/REGIONAL'

# Import MCP Atlassian WAF
terraform import 'aws_wafv2_web_acl.mcp_atlassian[0]' \
  'e950ad4c-56ad-4cee-917d-3c28aabd2209/bond-ai-dev-mcp-atlassian-waf/REGIONAL'
```

#### Step 4: Import WAF Associations

**Important**: The association import format is: `<AppRunnerARN>,<WAF_ARN>`

```bash
# Example (replace with your actual ARNs):
terraform import 'aws_wafv2_web_acl_association.backend[0]' \
  'arn:aws:apprunner:us-west-2:019593708315:service/bond-ai-dev-backend/SERVICE_ID,arn:aws:wafv2:us-west-2:019593708315:regional/webacl/bond-ai-dev-backend-waf/0499b6b4-0f92-44bf-858c-4655452e0f75'
```

#### Step 5: Plan and Apply

```bash
# Review changes
terraform plan -var-file=environments/agent-space.tfvars

# Expected: Rule updates (adding SizeRestrictions_BODY override), no resource recreation
# Apply changes
terraform apply -var-file=environments/agent-space.tfvars
```

### Option 2: Recreate WAFs from Scratch

If you want a clean slate or are deploying for the first time:

#### Step 1: Delete Existing WAFs (if any)

```bash
# Via AWS Console: WAF & Shield > Web ACLs > Delete each WAF
# OR via AWS CLI:
aws wafv2 disassociate-web-acl \
  --resource-arn arn:aws:apprunner:... \
  --region us-west-2 \
  --profile agent-space

aws wafv2 delete-web-acl \
  --name bond-ai-dev-backend-waf \
  --scope REGIONAL \
  --id WAF_ID \
  --lock-token LOCK_TOKEN \
  --region us-west-2 \
  --profile agent-space
```

#### Step 2: Deploy with Terraform

```bash
cd deployment/terraform-existing-vpc

# Plan
terraform plan -var-file=environments/agent-space.tfvars

# Apply
terraform apply -var-file=environments/agent-space.tfvars
```

## Verification

### 1. Check WAF Status

```bash
export AWS_PROFILE=agent-space

# List all WAFs
aws wafv2 list-web-acls --scope REGIONAL --region us-west-2

# Get specific WAF details
aws wafv2 get-web-acl \
  --scope REGIONAL \
  --region us-west-2 \
  --id 0499b6b4-0f92-44bf-858c-4655452e0f75 \
  --name bond-ai-dev-backend-waf
```

### 2. Test File Upload

```bash
# Test file upload endpoint (requires authentication)
curl -X POST https://rqs8cicg8h.us-west-2.awsapprunner.com/files \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -F "file=@test_file.pdf"

# Expected: 200 OK or 201 Created
# Should NOT see: 403 Forbidden from WAF
```

### 3. Check WAF Logs

WAF logs are stored in CloudWatch Logs:

```bash
# View recent WAF logs
aws logs tail aws-waf-logs-bondai \
  --region us-west-2 \
  --profile agent-space \
  --since 1h \
  --follow

# Filter for blocked requests
aws logs filter-log-events \
  --log-group-name aws-waf-logs-bondai \
  --region us-west-2 \
  --profile agent-space \
  --filter-pattern '"action":"BLOCK"' \
  --start-time $(date -u -d '1 hour ago' +%s)000
```

### 4. Check CloudWatch Metrics

View WAF metrics in CloudWatch:

1. Open CloudWatch Console
2. Navigate to Metrics > All metrics > WAFv2
3. View metrics for each Web ACL:
   - `AllowedRequests` - Requests that passed
   - `BlockedRequests` - Requests blocked by rules
   - `CountedRequests` - Requests counted but not blocked (file uploads should be here)

## Troubleshooting

### File Uploads Still Failing

**Problem**: File uploads to `/files` endpoint return 403 Forbidden

**Possible Causes**:

1. **WAF rule not overridden**: Check that SizeRestrictions_BODY is set to COUNT
   ```bash
   aws wafv2 get-web-acl \
     --scope REGIONAL \
     --id 0499b6b4-0f92-44bf-858c-4655452e0f75 \
     --name bond-ai-dev-backend-waf \
     --region us-west-2 \
     --profile agent-space \
     | jq '.WebACL.Rules[] | select(.Name == "AWS-AWSManagedRulesCommonRuleSet")'
   ```

2. **Wrong WAF associated**: Verify the correct WAF is associated with backend
   ```bash
   aws wafv2 get-web-acl-for-resource \
     --resource-arn arn:aws:apprunner:us-west-2:019593708315:service/bond-ai-dev-backend/SERVICE_ID \
     --region us-west-2 \
     --profile agent-space
   ```

3. **Authentication issue**: The 403 might be from the backend application, not WAF
   - Check backend logs for authentication errors
   - Verify auth token is valid

### Terraform Import Fails

**Error**: `Error: Cannot import non-existent remote object`

**Solution**: Verify the resource exists and the ID format is correct
```bash
# List WAFs to confirm they exist
aws wafv2 list-web-acls --scope REGIONAL --region us-west-2 --profile agent-space

# Import format: ID/NAME/SCOPE
terraform import 'aws_wafv2_web_acl.backend[0]' '<ID>/<NAME>/REGIONAL'
```

### WAF Blocking Legitimate Traffic

**Problem**: WAF is blocking valid requests

**Diagnosis**:
1. Check WAF logs for the terminating rule:
   ```bash
   aws logs tail aws-waf-logs-bondai --region us-west-2 --profile agent-space --since 1h | grep BLOCK
   ```

2. Identify the rule causing the block

**Solutions**:
- **Option A**: Override the specific rule to COUNT (like SizeRestrictions_BODY)
- **Option B**: Add a scope-down statement to exclude specific paths
- **Option C**: Create a custom rule with lower priority to allow the request

### High WAF Costs

**Problem**: WAF costs are higher than expected

**Cost Breakdown**:
- Web ACL: $5/month per ACL
- Rules: $1/month per rule
- Requests: $0.60 per 1 million requests
- **Total base**: ~$24/month for 3 WAFs with 9 rules

**Optimization Options**:
1. Disable WAF for development environments: `waf_enabled = false` in tfvars
2. Use fewer managed rule groups (remove UnixRuleSet if not needed)
3. Consolidate services behind a single WAF using ALB (major architectural change)

## Maintenance

### Adding New Rules

To add a new managed rule group:

1. Edit `waf.tf`
2. Add a new `rule` block with higher priority number
3. Apply changes: `terraform apply -var-file=environments/agent-space.tfvars`

Example:
```hcl
rule {
  name     = "AWS-AWSManagedRulesAmazonIpReputationList"
  priority = 3  # Next available priority

  override_action {
    none {}
  }

  statement {
    managed_rule_group_statement {
      vendor_name = "AWS"
      name        = "AWSManagedRulesAmazonIpReputationList"
    }
  }

  visibility_config {
    cloudwatch_metrics_enabled = true
    metric_name                = "IPReputationListMetric"
    sampled_requests_enabled   = true
  }
}
```

### Disabling WAF

To temporarily disable WAF protection:

1. Edit `environments/agent-space.tfvars`
2. Set `waf_enabled = false`
3. Apply: `terraform apply -var-file=environments/agent-space.tfvars`

This will remove WAF associations but keep the Web ACLs (due to count = 0).

### Updating to New AWS Managed Rules

AWS updates managed rule groups automatically. To get the latest:

1. Monitor AWS Security Bulletins
2. Test in non-production first
3. Review CloudWatch metrics for new blocks
4. No Terraform changes needed (managed by AWS)

## Security Considerations

### Why Override SizeRestrictions_BODY?

**Risk**: Allowing large request bodies could enable:
- Denial of Service (DoS) attacks
- Buffer overflow attempts
- Excessive resource consumption

**Mitigation**:
- Backend application has its own file size limits
- App Runner has request size limits (default 10MB)
- File uploads require authentication
- Other WAF rules still active (XSS, SQL injection, etc.)
- CloudWatch metrics track all large requests

**Alternative Considered**: Use scope-down statement to exclude only `/files` endpoint
- More complex configuration
- Harder to maintain
- COUNT approach provides better visibility

### Monitoring Recommendations

1. **Set CloudWatch Alarms** for:
   - Blocked requests exceeding threshold
   - Sudden spike in counted requests
   - WAF errors

2. **Regular Review**:
   - Weekly review of blocked requests
   - Monthly cost analysis
   - Quarterly rule effectiveness assessment

3. **Log Retention**:
   - WAF logs retained for 30 days (CloudWatch default)
   - Consider exporting to S3 for longer retention

## References

- [AWS WAF Documentation](https://docs.aws.amazon.com/waf/)
- [AWS Managed Rules for AWS WAF](https://docs.aws.amazon.com/waf/latest/developerguide/aws-managed-rule-groups.html)
- [WAF Terraform Provider](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/wafv2_web_acl)
- [App Runner WAF Integration](https://docs.aws.amazon.com/apprunner/latest/dg/network-waf.html)

## Related Documentation

- `MCP_ATLASSIAN_DEPLOYMENT.md` - MCP Atlassian service deployment
- `S3_CONNECTIVITY_FIX.md` - S3 connectivity troubleshooting
- `TROUBLESHOOTING_SESSION_SUMMARY.md` - General troubleshooting guide

## Change Log

| Date | Change | Author |
|------|--------|--------|
| 2025-12-27 | Initial WAF Terraform configuration created | Claude Code |
| 2025-12-27 | Added SizeRestrictions_BODY override for file uploads | Claude Code |
| 2025-12-27 | Documented import procedure for existing WAFs | Claude Code |
