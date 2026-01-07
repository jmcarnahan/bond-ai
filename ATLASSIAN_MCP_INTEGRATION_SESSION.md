# Atlassian MCP Integration - Debugging Session

**Date:** December 2, 2025
**Goal:** Get Atlassian MCP service working with multi-user OAuth authentication

---

## Summary

Working on integrating the Atlassian MCP server (https://github.com/sooperset/mcp-atlassian) with a multi-user Bond AI system. The integration requires:
1. Multi-user OAuth 2.0 authentication (each user has their own Atlassian token)
2. Backend service connecting to MCP Atlassian service via streamable-http transport
3. Passing user-specific OAuth tokens per-request (not global environment variables)

---

## Architecture

### Services
- **Backend Service**: `bond-ai-dev-backend` (App Runner) - Main API that users connect to
- **MCP Atlassian Service**: `bond-ai-dev-mcp-atlassian` (App Runner) - MCP server providing Atlassian tools
- **Database**: PostgreSQL RDS - Stores user OAuth tokens

### OAuth Flow
1. User authorizes via `/connections/atlassian/authorize` endpoint
2. OAuth callback receives authorization code
3. Backend exchanges code for access/refresh tokens with Atlassian
4. Tokens stored in database via `MCPTokenCache`
5. Backend retrieves tokens and passes to MCP service per-request

---

## Issues Encountered & Solutions

### 1. ✅ FIXED: OAuth Token Exchange Failing (401 Unauthorized)

**Problem:**
```
Token exchange response status: 401
Response: {"error":"access_denied","error_description":"Unauthorized"}
```

**Root Cause:**
Missing `client_secret` in token exchange request to Atlassian.

**Solution:**
Modified `deployment/terraform-existing-vpc/backend.tf` to inject `client_secret` into `BOND_MCP_CONFIG`:

```terraform
BOND_MCP_CONFIG = var.mcp_atlassian_service_url != "" && var.mcp_atlassian_oauth_secret_name != "" ? jsonencode({
  mcpServers = {
    atlassian = {
      ...
      oauth_config = {
        ...
        client_secret = jsondecode(data.aws_secretsmanager_secret_version.mcp_atlassian_oauth[0].secret_string)["client_secret"]
      }
    }
  }
}) : "{}"
```

**Files Changed:**
- `deployment/terraform-existing-vpc/backend.tf` (line 80)

**Result:** OAuth token exchange now succeeds with 200 status.

---

### 2. ✅ FIXED: MCP Service Not Accessible (DNS Error)

**Problem:**
```
Error listing tools from 'atlassian': Client failed to connect: [Errno -5] No address associated with hostname
```

**Root Cause:**
MCP Atlassian service was configured with `is_publicly_accessible = false`, which means:
- No public DNS hostname assigned
- Not accessible from other App Runner services

**Solution:**
Modified `deployment/terraform-existing-vpc/mcp-atlassian.tf`:

```terraform
network_configuration {
  ingress_configuration {
    is_publicly_accessible = true  # Changed from false
  }
}
```

**Files Changed:**
- `deployment/terraform-existing-vpc/mcp-atlassian.tf` (line 363)

**Result:** MCP service now has public URL and is accessible.

**Note for Future:** Research AWS PrivateLink or VPC endpoints for private service-to-service communication.

---

### 3. ✅ FIXED: Missing Cloud ID Header (400 Bad Request)

**Problem:**
```
Client error '400 Bad Request' for url 'https://fa3vbibtmu.us-west-2.awsapprunner.com/mcp/'
```

**Root Cause:**
Atlassian MCP server requires `X-Atlassian-Cloud-Id` header to know which Atlassian instance to use. Backend was not sending this header.

**How Atlassian MCP Works:**
- Accepts Bearer token via `Authorization` header
- Accepts Cloud ID via `X-Atlassian-Cloud-Id` header (optional in middleware, line 242)
- Both are per-request (supports multi-tenancy)
- Does NOT require OAuth setup wizard for BYOT (Bring Your Own Token) mode

**Solution:**
Modified `bondable/bond/providers/bedrock/BedrockMCP.py` to add Cloud ID header:

```python
# Add X-Atlassian-Cloud-Id header if cloud_id is present in config
cloud_id = server_config.get('cloud_id')
if cloud_id:
    headers['X-Atlassian-Cloud-Id'] = cloud_id
    LOGGER.debug(f"[MCP Auth] Added X-Atlassian-Cloud-Id header: {cloud_id}")
else:
    LOGGER.warning(f"[MCP Auth] No cloud_id found in config for OAuth2 server '{server_name}'...")
```

**Files Changed:**
- `bondable/bond/providers/bedrock/BedrockMCP.py` (lines 350-358)

**TODO Added:**
Make cloud_id header configurable via `oauth_config.cloud_id_header_name` to support different MCP servers.

**Result:** Backend now sends `X-Atlassian-Cloud-Id` header (confirmed in logs).

---

### 4. ✅ FIXED: Header Name Casing Conflict (400 Bad Request)

**Problem:**
Still getting 400 Bad Request despite Cloud ID header being sent and Accept header being added to our headers dict.

**Investigation:**
Used curl to test MCP endpoint directly:

```bash
# WITHOUT Accept header:
curl -X POST https://fa3vbibtmu.us-west-2.awsapprunner.com/mcp/ \
  -H "Authorization: Bearer test-token" \
  -H "X-Atlassian-Cloud-Id: 55de5903-f98d-499f-967a-32673b683dc8"

Response: {"error":"Not Acceptable: Client must accept both application/json and text/event-stream"}

# WITH Accept header:
curl -X POST https://fa3vbibtmu.us-west-2.awsapprunner.com/mcp/ \
  -H "Accept: application/json, text/event-stream" \
  -H "Authorization: Bearer test-token" \
  -H "X-Atlassian-Cloud-Id: 55de5903-f98d-499f-967a-32673b683dc8"

Response: {"serverInfo":{"name":"Atlassian MCP","version":"1.9.4"}}  ✅ SUCCESS
```

**Root Cause Discovery:**

After adding detailed logging, confirmed that our capitalized `Accept` header WAS being added to the headers dict:
```
[MCP Tools] Final headers being sent: ['User-Agent', 'Authorization', 'X-Atlassian-Cloud-Id', 'Accept']
```

But still got 400 Bad Request. Investigation of the MCP Python SDK source code revealed:

**The Real Root Cause:** Header name casing conflict!

The MCP SDK's `StreamableHttpTransport` sets default headers using **lowercase** keys:
```python
# From mcp/client/streamable_http.py
ACCEPT = "accept"  # lowercase!
CONTENT_TYPE = "content-type"  # lowercase!

self.request_headers = {
    ACCEPT: f"{JSON}, {SSE}",  # "accept": "application/json, text/event-stream"
    CONTENT_TYPE: JSON,  # "content-type": "application/json"
    **self.headers,  # Our custom headers merged here
}
```

We were setting capitalized headers:
- `Accept` (capitalized)
- `Content-Type` (capitalized)

When merging with `**self.headers`, Python dict treats `"accept"` and `"Accept"` as DIFFERENT keys, resulting in:
- `"accept": "application/json, text/event-stream"` (from SDK)
- `"Accept": "application/json, text/event-stream"` (from our code)

This created duplicate headers, which could confuse the HTTP client or server!

**Solution:**
Remove our custom Accept/Content-Type header additions entirely. The SDK already sets them correctly with lowercase keys. We were accidentally creating duplicates by using different casing.

**Files Changed (Round 3 - FINAL FIX):**
- `bondable/rest/routers/mcp.py` (lines 146-150): Removed Accept header override, added explanatory comment
- `bondable/rest/routers/mcp.py` (lines 352-354): Removed Accept header override in resources endpoint
- `bondable/bond/providers/bedrock/BedrockMCP.py` (lines 218-220): Removed Accept header override in tool defs
- `bondable/bond/providers/bedrock/BedrockMCP.py` (lines 439-441): Removed Accept header override in execute

**Key Lesson:**
When working with HTTP libraries, always check the exact casing of header constants. HTTP headers are case-insensitive in the protocol, but Python dicts are case-sensitive!

**Result:**
Removed duplicate headers, but still getting 400 Bad Request.

---

### 5. ✅ FIXED: Outdated MCP SDK Version (400 Bad Request)

**Problem:**
Even after fixing the header casing conflict, still getting 400 Bad Request.

**Root Cause Discovery:**
Checked versions:
- **Our version**: `mcp = "^1.9.1"` (from October/November 2024)
- **Latest version**: `1.23.1` (December 2024)
- **Gap**: 14 versions behind!

**Key Fix Found in Changelog:**
Version **1.20.0** includes: **"Relax Accept header requirement for JSON-only responses"**

This suggests v1.9.1 had a bug with Accept header handling that was causing our 400 errors!

**Solution:**
Updated pyproject.toml:
```toml
mcp = {extras = ["cli"], version = "^1.23.1"}  # Was: ^1.9.1
fastmcp = "^2.13.2"  # Was: >=2.13.0 (pinned for consistency)
```

**Files Changed:**
- `pyproject.toml` (line 28-29)

**Key Lesson:**
Always check if you're using the latest SDK version before debugging obscure protocol issues!

**Result:**
Ready to deploy with updated MCP SDK.

---

### 6. ✅ FIXED: Transport Compatibility Issue

**Problem:**
After upgrading MCP SDK, got error:
```
Could not infer a valid transport from: <mcp.client.streamable_http.StreamableHTTPTransport object>
```

**Root Cause:**
We were trying to use the base MCP SDK's `StreamableHTTPTransport` directly with `fastmcp.Client`:
```python
from mcp.client.streamable_http import StreamableHTTPTransport  # Base SDK
transport = StreamableHTTPTransport(server_url, headers=headers_with_ua)
async with Client(transport) as client:  # fastmcp.Client expects fastmcp transport!
```

The `fastmcp.Client` expects fastmcp's own transport wrappers, not the raw base SDK transports.

**Solution:**
Use fastmcp's `StreamableHttpTransport` wrapper instead:
```python
from fastmcp.client import StreamableHttpTransport  # Use fastmcp's wrapper
transport = StreamableHttpTransport(server_url, headers=headers_with_ua)
async with Client(transport) as client:  # Now compatible!
```

**Files Changed:**
- `bondable/rest/routers/mcp.py` (line 86, 167)
- `bondable/bond/providers/bedrock/BedrockMCP.py` (line 18)

**Key Lesson:**
When using a wrapper library (fastmcp), stick to its components throughout. Don't mix base SDK components with wrapper components.

**Result:**
Transport now compatible with fastmcp.Client. Headers should work correctly since fastmcp 2.13.2 is built on top of the fixed mcp 1.23.1 SDK.

---

## Current Status (as of 5:16 PM Dec 2, 2025)

### What's Working ✅
1. OAuth authorization flow with Atlassian
2. Token exchange (client_secret now included)
3. Token storage in database
4. MCP service is publicly accessible
5. Backend sends Authorization header with Bearer token
6. Backend sends X-Atlassian-Cloud-Id header
7. MCP SDK upgraded to 1.23.1 (with Accept header fixes)
8. fastmcp upgraded to 2.13.2
9. Headers confirmed present in logs: `['User-Agent', 'Authorization', 'X-Atlassian-Cloud-Id', 'accept', 'content-type']`
10. Transport compatibility fixed (using fastmcp's StreamableHttpTransport)

### Latest Issue (FIXED in code, pending deploy)
**Error**: `Could not infer a valid transport from: <mcp.client.streamable_http.StreamableHTTPTransport object>`

**Root Cause**: Was mixing base MCP SDK transport (`mcp.client.streamable_http.StreamableHTTPTransport`) with fastmcp Client.

**Fix Applied**: Changed to use fastmcp's `StreamableHttpTransport` wrapper throughout.

### Deployment at 5:35 PM - Still 400 Error

**Results**: Transport compatibility fixed, but still getting 400 Bad Request.

**New Error Clue**:
```
Attempted to access streaming response content, without having called `read()`.
```

**Hypothesis**: We may be explicitly setting headers that conflict with the SDK's defaults. The SDK's `StreamableHttpTransport` should set `accept` and `content-type` automatically.

**Next Fix**: Remove explicit `accept` and `content-type` header setting, let SDK manage them.

---

### 7. ✅ FIXED: Missing Trailing Slash in URL (THE ROOT CAUSE!)

**Problem:**
Even after all fixes, still getting 400 Bad Request. Created standalone test script to debug outside deployment.

**Discovery using test script:**
```
HTTP Request: POST https://fa3vbibtmu.us-west-2.awsapprunner.com/mcp "HTTP/1.1 307 Temporary Redirect"
location: http://fa3vbibtmu.us-west-2.awsapprunner.com/mcp/  (note: http not https!)
HTTP Request: POST http://fa3vbibtmu.us-west-2.awsapprunner.com/mcp/ "HTTP/1.1 301 Moved Permanently"
location: https://fa3vbibtmu.us-west-2.awsapprunner.com:443/mcp/
HTTP Request: GET https://fa3vbibtmu.us-west-2.awsapprunner.com/mcp/ "HTTP/1.1 400 Bad Request"
```

**Root Cause:**
URL without trailing slash (`/mcp`) triggers:
1. 307 redirect to HTTP (downgrades from HTTPS!)
2. 301 redirect back to HTTPS
3. Final request is **GET instead of POST** after redirects
4. MCP protocol requires POST → 400 Bad Request

**Solution:**
Add trailing slash to URL: `/mcp/`

With trailing slash, request goes directly to the endpoint with POST method - **works perfectly!**

**Files Changed:**
- `deployment/terraform-existing-vpc/backend.tf` (line 73): Changed `${var.mcp_atlassian_service_url}/mcp` to `${var.mcp_atlassian_service_url}/mcp/`
- `test_mcp_direct.py`: Created standalone test script that revealed the issue

**Test Results:**
```
✅ SUCCESS! Found 42 tools (all Jira and Confluence tools listed)
```

**Key Lesson:**
Always test with trailing slashes on API endpoints. HTTP redirects can change request methods (POST → GET) which breaks protocol requirements.

---

## Resolution Summary

The 400 Bad Request error was caused by a **missing trailing slash** in the MCP service URL. This caused HTTP redirect chains that changed the POST request to GET, which violates the MCP protocol.

All other fixes were valuable (SDK upgrade, transport compatibility, header management), but the URL issue was the blocker.

### Next Steps
1. **TODO**: Deploy with trailing slash URL fix
2. **TODO**: Test MCP tools listing endpoint in production
3. **TODO**: Test MCP resources endpoint
4. **TODO**: Verify tools are returned successfully
5. **TODO**: Test end-to-end with Bedrock Agent
6. **TODO**: Document lessons learned

---

## Technical Details

### MCP Atlassian Server Details
- **Repository:** https://github.com/sooperset/mcp-atlassian
- **Version:** 1.9.4
- **Authentication Modes:**
  - API Token (username + token)
  - Personal Access Token (PAT)
  - OAuth 2.0 Standard Flow (with setup wizard)
  - OAuth 2.0 BYOT (Bring Your Own Token) ← **Using this mode**

### BYOT Mode Requirements (from mcp-atlassian README)
- Accepts Bearer token via `Authorization` header per-request
- Accepts `X-Atlassian-Cloud-Id` header per-request
- Does NOT require OAuth setup wizard
- Does NOT handle token refresh (external system's responsibility)
- Supports multi-tenancy (different token per request)

### Middleware Code (from mcp-atlassian source)
Location: `/tmp/mcp-atlassian/src/mcp_atlassian/servers/main.py` lines 210-324

Key behaviors:
- Checks for `Authorization: Bearer <token>` header (line 271)
- Checks for `X-Atlassian-Cloud-Id` header (line 242)
- Requires `Accept: application/json, text/event-stream` for streamable-http

---

## Environment Configuration

### Backend Service Environment Variables
```
BOND_MCP_CONFIG = {
  "mcpServers": {
    "atlassian": {
      "url": "https://fa3vbibtmu.us-west-2.awsapprunner.com/mcp",
      "transport": "streamable-http",
      "auth_type": "oauth2",
      "display_name": "Atlassian",
      "description": "Connect to Atlassian Jira and Confluence",
      "oauth_config": {
        "provider": "atlassian",
        "client_id": "CSio9UBBGirs72QdZOZKY71Dw057DfT7",
        "client_secret": "REDACTED",
        "authorize_url": "https://auth.atlassian.com/authorize",
        "token_url": "https://auth.atlassian.com/oauth/token",
        "scopes": "read:jira-user read:jira-work write:jira-work read:confluence-space.summary write:confluence-content offline_access",
        "redirect_uri": "https://rqs8cicg8h.us-west-2.awsapprunner.com/connections/atlassian/callback"
      },
      "site_url": "https://api.atlassian.com",
      "cloud_id": "55de5903-f98d-499f-967a-32673b683dc8"
    }
  }
}
```

### MCP Atlassian Service Environment Variables
```
ATLASSIAN_OAUTH_CLIENT_ID
ATLASSIAN_OAUTH_CLIENT_SECRET
ATLASSIAN_OAUTH_REDIRECT_URI
ATLASSIAN_OAUTH_SCOPE
ATLASSIAN_OAUTH_CLOUD_ID
CONFLUENCE_URL
JIRA_URL
MCP_LOGGING_LEVEL=INFO
```

---

## Code Changes Summary

### Files Modified

1. **deployment/terraform-existing-vpc/backend.tf**
   - Added client_secret to BOND_MCP_CONFIG
   - Added condition check for mcp_atlassian_oauth_secret_name

2. **deployment/terraform-existing-vpc/mcp-atlassian.tf**
   - Changed is_publicly_accessible from false to true

3. **bondable/bond/providers/bedrock/BedrockMCP.py**
   - Added X-Atlassian-Cloud-Id header for OAuth2 auth (lines 350-358)
   - Added Accept header for streamable-http transport (2 places)
   - Added TODO for making cloud_id header configurable

4. **bondable/rest/routers/mcp.py**
   - Added Accept header for streamable-http in list_mcp_tools
   - Added Accept header for streamable-http in list_mcp_resources

---

## Logs Analysis

### Latest Backend Logs (Before Restart - 11:54:05 AM)
```
✅ [MCP Tools] Server 'atlassian' authenticated, headers: ['Authorization', 'X-Atlassian-Cloud-Id']
✅ [MCP Tools] Creating streamable-http transport for 'atlassian' at https://fa3vbibtmu.us-west-2.awsapprunner.com/mcp
❌ [MCP Tools] Error listing tools from 'atlassian': Client error '400 Bad Request'
```

**IMPORTANT**: These logs are from BEFORE we added the "Final headers being sent" logging. After restart, look for this new log line showing whether Accept is in the headers dict.

### Expected New Logs (After Restart)
Look for this pattern:
```
[MCP Tools] Server 'atlassian' authenticated, headers: ['Authorization', 'X-Atlassian-Cloud-Id']
[MCP Tools] Creating streamable-http transport for 'atlassian' at https://fa3vbibtmu.us-west-2.awsapprunner.com/mcp
[MCP Tools] Final headers being sent: ['User-Agent', 'Authorization', 'X-Atlassian-Cloud-Id', 'Accept']  ← NEW LOG
```

If Accept is present in this list but still getting 400, the problem is in the MCP SDK.
If Accept is NOT present in this list, there's a code logic issue.

### MCP Atlassian Service Logs
Only showing keyring warnings (non-critical):
```
WARNING - mcp-atlassian.oauth - Failed to load tokens from keyring... Trying file fallback.
```

No actual HTTP request logs or error details from MCP service side.

---

## Dependencies

### Python Packages (from pyproject.toml)
```toml
mcp = {extras = ["cli"], version = "^1.9.1"}
fastmcp = ">=2.13.0"
```

---

## Testing Commands

### Test OAuth Flow
```bash
# Get authorization URL
GET /connections/atlassian/authorize

# Complete OAuth callback
GET /connections/atlassian/callback?code=xxx&state=xxx
```

### Test MCP Endpoint Directly ✅ VERIFIED WORKING

**Verified on Dec 2, 2025 at 5:20 PM** - Direct curl calls to the MCP Atlassian endpoint work successfully:

```bash
curl -X POST https://fa3vbibtmu.us-west-2.awsapprunner.com/mcp/ \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -H "Authorization: Bearer {USER_TOKEN}" \
  -H "X-Atlassian-Cloud-Id: 55de5903-f98d-499f-967a-32673b683dc8" \
  -H "User-Agent: Bond-AI-MCP-Client/1.0" \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"test","version":"1.0"}}}'
```

**Response (SUCCESS):**
```
event: message
data: {"jsonrpc":"2.0","id":1,"result":{"protocolVersion":"2024-11-05","capabilities":{"experimental":{},"prompts":{"listChanged":false},"resources":{"subscribe":false,"listChanged":false},"tools":{"listChanged":false}},"serverInfo":{"name":"Atlassian MCP","version":"1.9.4"}}}
```

**Key findings:**
- ✅ MCP Atlassian service is accessible at the URL
- ✅ OAuth Bearer token authentication works
- ✅ X-Atlassian-Cloud-Id header is accepted
- ✅ Accept header `application/json, text/event-stream` is accepted
- ✅ Server responds with valid MCP protocol messages

This confirms the MCP Atlassian service itself is working correctly. The issue was in how our Python code was constructing the transport/client connection.

### Check Service Status
```bash
AWS_PROFILE=agent-space aws apprunner describe-service \
  --service-arn arn:aws:apprunner:us-west-2:019593708315:service/bond-ai-dev-backend/d8d6e8e3d61e45db9882c6c5fd24245c \
  --region us-west-2 \
  --query 'Service.Status'
```

---

## Outstanding Questions

1. **Why is Accept header not working?**
   - Is the MCP SDK overriding headers we set?
   - Do we need to configure StreamableHttpTransport differently?
   - Should we use raw httpx.AsyncClient instead?

2. **Is there a version mismatch?**
   - Using mcp ^1.9.1 and fastmcp >=2.13.0
   - Is there a known bug in these versions?

3. **Are headers actually being sent?**
   - Need to add request logging to see actual HTTP headers
   - MCP service logs don't show incoming requests

---

## References

- Atlassian MCP Server: https://github.com/sooperset/mcp-atlassian
- Atlassian OAuth Docs: https://developer.atlassian.com/cloud/confluence/oauth-2-3lo-apps/
- MCP Protocol Spec: https://modelcontextprotocol.io/
- FastMCP Docs: https://github.com/jlowin/fastmcp
