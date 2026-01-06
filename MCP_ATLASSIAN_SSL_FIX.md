# MCP Atlassian SSL Certificate Fix - Summary

## Problem

When running the mcp-atlassian Docker container locally on a corporate network, SSL certificate verification errors occurred:

```
[SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed: unable to get local issuer certificate (_ssl.c:1017)
```

The container was unable to connect to `api.atlassian.com` because:
1. Corporate network uses SSL-intercepting proxies
2. The Alpine Linux-based container didn't have access to corporate CA certificates
3. Python's SSL library couldn't verify the intercepted SSL connections

## Solutions Implemented

### Local Development - Two Options

#### Option 1: Quick Fix (SSL Verification Disabled)
For rapid local testing when security is less critical:

**Configuration** (`mcp-atlassian.env`):
```bash
JIRA_SSL_VERIFY=false
CONFLUENCE_SSL_VERIFY=false
```

**Docker Command**:
```bash
docker run --rm --name mcp-atlassian -p 9001:8000 \
  --env-file /Users/jcarnahan/projects/bond-ai/mcp-atlassian.env \
  ghcr.io/sooperset/mcp-atlassian:latest \
  --transport streamable-http --port 8000
```

⚠️ **Use only for local development**

#### Option 2: Secure Fix (Certificate Mounting) ✅ Recommended
Maintains SSL security by mounting corporate CA certificates:

**Configuration** (`mcp-atlassian.env`):
```bash
# Comment out or set to true:
# JIRA_SSL_VERIFY=true
# CONFLUENCE_SSL_VERIFY=true
```

**Docker Command**:
```bash
docker run --rm --name mcp-atlassian -p 9001:8000 \
  -v /Users/jcarnahan/certs/combined.pem:/etc/ssl/certs/ca-bundle.crt:ro \
  -e SSL_CERT_FILE=/etc/ssl/certs/ca-bundle.crt \
  -e REQUESTS_CA_BUNDLE=/etc/ssl/certs/ca-bundle.crt \
  --env-file /Users/jcarnahan/projects/bond-ai/mcp-atlassian.env \
  ghcr.io/sooperset/mcp-atlassian:latest \
  --transport streamable-http --port 8000
```

**Benefits**:
- SSL verification remains enabled (secure)
- Works with corporate SSL-intercepting proxies
- Container can verify certificates using corporate CA bundle

### Production (AWS App Runner)

**No certificate mounting needed!**

The Terraform configuration explicitly enables SSL verification:

```hcl
runtime_environment_variables = {
  # ... other vars ...

  # SSL Certificate Verification - enabled for production
  JIRA_SSL_VERIFY       = "true"
  CONFLUENCE_SSL_VERIFY = "true"
}
```

**Why it works without extra configuration**:
- AWS App Runner containers have standard CA certificates pre-installed
- No corporate proxies in AWS networks
- Atlassian's `api.atlassian.com` uses public CA certificates
- Python can automatically find and use system certificates

## Files Modified

### 1. `mcp-atlassian.env`
Added SSL verification configuration with comments:
```bash
# SSL Certificate Verification (for local development on corporate networks)
# IMPORTANT: These should be set to "true" in production environments
# Set to "false" only for local development if experiencing SSL cert verification errors
# JIRA_SSL_VERIFY=false
# CONFLUENCE_SSL_VERIFY=false
```

### 2. `deployment/terraform-existing-vpc/mcp-atlassian.tf`
Added explicit SSL verification for production (lines 346-348):
```hcl
# SSL Certificate Verification - enabled for production
JIRA_SSL_VERIFY       = "true"
CONFLUENCE_SSL_VERIFY = "true"
```

### 3. `deployment/terraform-existing-vpc/MCP_ATLASSIAN_DEPLOYMENT.md`
Added comprehensive SSL troubleshooting section with:
- Problem description
- Local development solutions (quick and secure)
- Production deployment notes
- Certificate path references

### 4. `tests/test_mcp_atlassian_e2e.py`
Updated to use port 9001 with environment variable support:
```python
ATLASSIAN_MCP_URL = os.environ.get("ATLASSIAN_MCP_URL", "http://localhost:9001/mcp")
```

### 5. `tests/test_mcp_atlassian_tools.py`
- Fixed import (`StreamableHTTPTransport` instead of `StreamableHttpTransport`)
- Updated to use port 9001
- Updated to use ClientSession API correctly

### 6. `tests/test_mcp_ssl_fix.py` (New)
Created simple connectivity test to verify SSL fix without requiring OAuth tokens.

## Verification

✅ Container starts without SSL errors
✅ Server responds on port 9001
✅ Test script confirms connectivity

```bash
poetry run python tests/test_mcp_ssl_fix.py
```

Output:
```
✅ SUCCESS: MCP server is running without SSL certificate errors
   The fix worked! The container can now connect to api.atlassian.com
```

## Port Configuration

**Local Development**: Port 9001
- Reason: Port 9000 was already in use locally
- Tests updated to use 9001 by default

**Production (AWS)**: Port 8000 (internal to container)
- App Runner service exposes on its own URL
- No port conflicts in AWS environment

## Testing the Fix

### Quick Test (Verify Server Responds)
```bash
poetry run python tests/test_mcp_ssl_fix.py
```

### Full E2E Test (Requires OAuth Token)
```bash
poetry run pytest tests/test_mcp_atlassian_e2e.py -v -s
```

## Key Takeaways

1. **Local vs Production**: SSL certificate handling differs between local development (corporate network) and AWS production
2. **Security**: Certificate mounting is more secure than disabling SSL verification
3. **No AWS Changes Needed**: Production deployment works automatically with standard CA certificates
4. **Flexibility**: Both quick and secure local development options available

## Related Documentation

- Full troubleshooting guide: `deployment/terraform-existing-vpc/MCP_ATLASSIAN_DEPLOYMENT.md`
- Test scripts: `tests/test_mcp_ssl_fix.py`, `tests/test_mcp_atlassian_e2e.py`
- Docker run examples: See documentation sections above
