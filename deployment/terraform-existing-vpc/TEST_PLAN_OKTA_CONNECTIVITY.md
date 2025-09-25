# Test Plan - Okta Connectivity Issue Resolution

**Date:** September 25, 2025
**Objective:** Systematically test and resolve external internet connectivity for Okta authentication
**Current Issue:** App Runner can reach AWS services but cannot connect to `trial-9457917.okta.com:443`

## Test Execution Checklist

### Phase 1: Network ACL Investigation
**Goal:** Verify subnet-level network access controls aren't blocking external HTTPS

- [ ] **Test 1.1:** Check Network ACLs for App Runner subnets
  - [ ] List Network ACLs associated with App Runner subnets
  - [ ] Verify outbound rules allow port 443 (HTTPS)
  - [ ] Check for any explicit DENY rules for external traffic
  - [ ] Document findings in results section

- [ ] **Test 1.2:** Compare with working subnet Network ACLs
  - [ ] Check Network ACLs for subnets that have working internet access
  - [ ] Compare rules between working and App Runner subnets
  - [ ] Document any differences

**Expected Result:** Network ACLs should allow all outbound traffic (default configuration)
**If PASS:** Proceed to Phase 2
**If FAIL:** Document specific rules blocking traffic and investigate remediation

---

### Phase 2: DNS Resolution Testing
**Goal:** Determine if VPC endpoints are interfering with external DNS resolution

- [ ] **Test 2.1:** Test DNS resolution capability
  - [ ] Create a simple test endpoint in backend app to perform DNS lookups
  - [ ] Test resolving `trial-9457917.okta.com` from within App Runner
  - [ ] Test resolving other external domains (e.g., `google.com`, `github.com`)
  - [ ] Document DNS response times and results

- [ ] **Test 2.2:** Compare DNS with/without VPC endpoints
  - [ ] Check current DNS servers used by App Runner subnets
  - [ ] Verify if VPC endpoints are affecting DNS resolution
  - [ ] Test if `private_dns_enabled = false` setting is working correctly

**Expected Result:** DNS resolution should work for external domains
**If PASS:** DNS is working, issue is connectivity not resolution
**If FAIL:** VPC endpoints DNS configuration needs adjustment

---

### Phase 3: VPC Egress Mode Testing
**Goal:** Test if disabling VPC egress mode resolves external connectivity

- [ ] **Test 3.1:** Backup current configuration
  - [ ] Commit current working state to git branch
  - [ ] Create backup of terraform state
  - [ ] Document rollback procedure

- [ ] **Test 3.2:** Temporarily disable VPC egress mode
  - [ ] Modify App Runner configuration to remove VPC connector
  - [ ] Deploy changes using terraform
  - [ ] Test Okta authentication flow
  - [ ] Verify AWS services still work (should use public endpoints)

- [ ] **Test 3.3:** Test hybrid connectivity
  - [ ] Document if external connectivity works without VPC egress
  - [ ] Verify all application functionality
  - [ ] Check if AWS service calls still work through public endpoints

**Expected Result:** External connectivity should work without VPC egress mode
**If PASS:** Issue is with VPC egress configuration, proceed to Phase 4
**If FAIL:** Issue is deeper - check corporate network policies

---

### Phase 4: Selective VPC Endpoint Testing
**Goal:** Identify if specific VPC endpoints are causing connectivity issues

- [ ] **Test 4.1:** Re-enable VPC egress mode
  - [ ] Restore VPC egress configuration from backup
  - [ ] Test that issue reproduces (Okta timeout returns)

- [ ] **Test 4.2:** Remove Interface VPC Endpoints temporarily
  - [ ] Comment out Secrets Manager VPC endpoint
  - [ ] Comment out Bedrock VPC endpoint
  - [ ] Comment out CloudWatch Logs VPC endpoint
  - [ ] Keep S3 Gateway endpoint (less likely to cause DNS issues)
  - [ ] Deploy and test Okta connectivity

- [ ] **Test 4.3:** Systematic endpoint re-addition
  - [ ] Add back one VPC endpoint at a time
  - [ ] Test Okta connectivity after each addition
  - [ ] Identify which specific endpoint breaks connectivity

**Expected Result:** Identify specific VPC endpoint causing DNS/connectivity conflict
**If PASS:** Fix configuration of problematic endpoint
**If FAIL:** Issue is not with individual VPC endpoints

---

### Phase 5: Alternative Solutions Testing
**Goal:** Test workaround approaches if VPC egress mode cannot be fixed

- [ ] **Test 5.1:** Okta configuration alternatives
  - [ ] Test if using IP addresses instead of hostnames works
  - [ ] Investigate Okta custom domain options
  - [ ] Check if different OAuth flow patterns work

- [ ] **Test 5.2:** Hybrid architecture approach
  - [ ] Keep VPC egress for AWS services
  - [ ] Use public App Runner for OAuth endpoints only
  - [ ] Test service-to-service communication patterns

- [ ] **Test 5.3:** Network connectivity diagnostics
  - [ ] Add network diagnostic endpoints to backend
  - [ ] Test various external services and ports
  - [ ] Document connectivity patterns and failures

**Expected Result:** Find working alternative or identify specific blocking mechanism

---

## Test Environment Setup

### Prerequisites
- [ ] Backup current terraform state
- [ ] Create git branch for testing: `git checkout -b test-okta-connectivity`
- [ ] Ensure ability to rollback quickly
- [ ] Have CloudWatch logs access for monitoring

### Testing Tools Needed
- [ ] AWS CLI access for Network ACL checks
- [ ] Terraform for configuration changes
- [ ] Browser for testing OAuth flows
- [ ] Log monitoring setup

### Safety Measures
- [ ] All tests performed in dev environment only
- [ ] Rollback plan documented for each test
- [ ] No changes made to production systems

## Results Documentation

### Test Results Template
For each test, document:
- [ ] **Test ID:** (e.g., Test 1.1)
- [ ] **Date/Time:**
- [ ] **Result:** PASS/FAIL
- [ ] **Details:** What exactly was observed
- [ ] **Evidence:** Log entries, screenshots, CLI output
- [ ] **Next Action:** Based on result

### Final Recommendations Section
After completing tests:
- [ ] Root cause identified: [ YES / NO ]
- [ ] Recommended solution: ________________
- [ ] Implementation steps: ________________
- [ ] Risk assessment: ____________________

## Execution Notes

### Before Starting Tests
1. Review TROUBLESHOOTING_SESSION_SUMMARY.md for context
2. Ensure all stakeholders are aware of testing timeline
3. Set up monitoring for the testing period

### During Testing
1. Document everything in real-time
2. Take screenshots of error messages
3. Save all configuration changes made
4. Monitor logs continuously

### After Testing
1. Clean up any temporary resources created
2. Restore stable configuration
3. Update troubleshooting summary with findings
4. Plan implementation of solution

---

**Ready to Begin:** [ ] All prerequisites completed, test environment prepared
**Test Start Time:** _______________
**Expected Duration:** 2-4 hours depending on findings
**Test Lead:** _______________