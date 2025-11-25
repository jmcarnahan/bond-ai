# Bond AI - MCP Integration Guide

**Complete guide for integrating OAuth 2.0 MCP servers with Bond AI**

---

## Table of Contents

1. [Overview](#overview)
2. [Architecture](#architecture)
3. [Prerequisites](#prerequisites)
4. [General OAuth MCP Integration](#general-oauth-mcp-integration)
5. [Atlassian MCP Recipe](#atlassian-mcp-recipe)
6. [Testing](#testing)
7. [Production Deployment](#production-deployment)
8. [Troubleshooting](#troubleshooting)
9. [Advanced Topics](#advanced-topics)

---

## Overview

Bond AI supports integration with external MCP (Model Context Protocol) servers to extend agent capabilities. This guide covers:

- **OAuth 2.0 MCP Servers**: Third-party MCP servers that use OAuth for authentication
- **User Token Management**: Each Bond user authorizes their own connections
- **Automatic Token Refresh**: Expired tokens are refreshed automatically using refresh tokens
- **Multi-Server Support**: Multiple MCP servers can be configured simultaneously

### Supported MCP Servers

1. **mcp-atlassian** (sooperset/mcp-atlassian) - Jira & Confluence integration
2. **Custom OAuth MCP servers** - Any MCP server using OAuth 2.0 with PKCE

---

## Architecture

### Components

```
┌─────────────┐      ┌─────────────┐      ┌──────────────────┐
│ Bond UI     │─────▶│ Bond API    │─────▶│ MCP Server       │
│ (Flutter)   │      │ (FastAPI)   │      │ (Docker/Remote)  │
└─────────────┘      └─────────────┘      └──────────────────┘
                            │                       │
                            │                       │
                            ▼                       ▼
                     ┌─────────────┐      ┌──────────────────┐
                     │ Token Cache │      │ OAuth Provider   │
                     │ (Database)  │      │ (e.g. Atlassian) │
                     └─────────────┘      └──────────────────┘
```

### OAuth Flow

1. **User Authorization**: User clicks "Connect" in UI
2. **OAuth Redirect**: Bond redirects to OAuth provider (e.g., Atlassian)
3. **User Consent**: User authorizes access to their resources
4. **Token Exchange**: Bond exchanges authorization code for access + refresh tokens
5. **Token Storage**: Tokens encrypted and stored in database
6. **Tool Execution**: When agent uses MCP tool, Bond passes user's access token
7. **Auto-Refresh**: Expired tokens refreshed automatically using refresh token

### Key Features

- ✅ **Per-User Authentication**: Each user authorizes their own connections
- ✅ **Token Encryption**: Tokens encrypted at rest using JWT secret
- ✅ **Automatic Refresh**: Expired tokens refreshed transparently
- ✅ **Multi-Server**: Support for multiple MCP servers simultaneously
- ✅ **Secure**: OAuth 2.0 with PKCE, no shared credentials

---

## Prerequisites

### For Development

1. **Bond AI backend** running locally:
   ```bash
   poetry run uvicorn bondable.rest.main:app --reload --port 8000
   ```

2. **Bond AI frontend** running locally:
   ```bash
   cd flutterui
   flutter run -d chrome --web-port 3000
   ```

3. **Docker** installed for running MCP servers

4. **OAuth App** registered with the service provider (e.g., Atlassian)

### For Production

1. **Deployed Bond Backend** with HTTPS
2. **Deployed Bond Frontend** with HTTPS
3. **OAuth App** with production redirect URIs
4. **MCP Server** deployed (Docker, AWS ECS, etc.)

---

## General OAuth MCP Integration

Follow these steps to integrate any OAuth 2.0 MCP server with Bond AI.

### Step 1: Register OAuth Application

1. Go to the service provider's developer portal
2. Create a new OAuth 2.0 application
3. Configure redirect URI: `https://your-backend/connections/{connection_name}/callback`
4. Request necessary scopes (include `offline_access` for refresh tokens)
5. Note down:
   - `client_id`
   - `client_secret`
   - `authorize_url`
   - `token_url`
   - Required scopes

### Step 2: Deploy MCP Server

If using a Docker-based MCP server:

```bash
# Create environment file with OAuth app credentials
cat > mcp-server.env <<EOF
# OAuth App Credentials
OAUTH_CLIENT_ID=your_client_id
OAUTH_CLIENT_SECRET=your_client_secret
OAUTH_REDIRECT_URI=https://your-backend/connections/server_name/callback
OAUTH_SCOPE=scope1 scope2 offline_access

# Service-specific configuration
SERVICE_URL=https://api.service.com
EOF

# Run MCP server
docker run -d \
  --name mcp-server \
  -p 9000:8000 \
  --env-file mcp-server.env \
  your/mcp-server:latest \
  --transport streamable-http --port 8000
```

### Step 3: Configure Bond Backend

Add MCP server configuration to your `.env` file:

```bash
BOND_MCP_CONFIG='{
  "mcpServers": {
    "server_name": {
      "url": "http://localhost:9000/mcp",
      "auth_type": "oauth2",
      "transport": "streamable-http",
      "display_name": "Service Name",
      "description": "Connect to Service",
      "oauth_config": {
        "provider": "service_name",
        "client_id": "your_client_id",
        "client_secret": "your_client_secret",
        "authorize_url": "https://auth.service.com/authorize",
        "token_url": "https://auth.service.com/oauth/token",
        "scopes": "scope1 scope2 offline_access",
        "redirect_uri": "http://localhost:8000/connections/server_name/callback"
      }
    }
  }
}'
```

**Important Configuration Notes:**

- `auth_type`: Must be `"oauth2"` for OAuth-based MCP servers
- `transport`: Use `"streamable-http"` for most MCP servers
- `scopes`: **Always include `offline_access`** to get refresh tokens
- `redirect_uri`: Must match exactly what's registered in OAuth app
- `client_secret`: Extracted automatically during token exchange

### Step 4: Test Connection

1. **Restart Backend**: Restart to load new configuration
   ```bash
   poetry run uvicorn bondable.rest.main:app --reload --port 8000
   ```

2. **Authorize via UI**:
   - Navigate to Connections page: `http://localhost:3000/connections`
   - Click "Connect" for your new service
   - Complete OAuth authorization
   - Verify connection shows as "Active"

3. **Test Tool Discovery**:
   ```bash
   poetry run pytest tests/test_mcp_tools_fetching.py -v -s
   ```

4. **Test End-to-End**:
   ```bash
   # Modify test_mcp_atlassian_e2e.py for your service
   poetry run pytest tests/test_mcp_atlassian_e2e.py -v -s
   ```

---

## Atlassian MCP Recipe

Complete step-by-step guide for integrating Atlassian (Jira & Confluence).

### 1. Register Atlassian OAuth App

1. **Go to**: https://developer.atlassian.com/console/myapps/
2. **Create OAuth 2.0 integration**:
   - Click "Create" → "OAuth 2.0 integration"
   - Name: "Bond AI Integration"
   - Description: "MCP integration for Jira and Confluence"

3. **Configure Permissions**:
   - Click "Permissions" → "Add" → "Jira API"
   - Add scopes:
     - `read:jira-user` (required for user profile)
     - `read:jira-work`
     - `write:jira-work`
   - Click "Permissions" → "Add" → "Confluence API"
   - Add scopes:
     - `read:confluence-space.summary`
     - `write:confluence-content`
   - **Important**: Add `offline_access` scope for refresh tokens

4. **Configure Authorization**:
   - Click "Authorization" → "Add"
   - Callback URL: `http://localhost:8000/connections/atlassian/callback` (for development)
   - For production: `https://your-backend.com/connections/atlassian/callback`

5. **Get Credentials**:
   - Click "Settings"
   - Copy **Client ID**
   - Copy **Secret** (client_secret)

6. **Get Cloud ID**:
   ```bash
   # Get accessible resources (requires a temporary token)
   curl -H "Authorization: Bearer YOUR_TEMP_TOKEN" \
     https://api.atlassian.com/oauth/token/accessible-resources

   # Response contains cloud ID:
   # [{"id": "ec8ace41-7cde-4e66-aaf1-6fca83a00c53", ...}]
   ```

### 2. Deploy mcp-atlassian Docker Container

#### Create Environment File

```bash
cat > mcp-atlassian.env <<EOF
# Atlassian URLs - MUST use cloud API format for OAuth 2.0 (3LO) tokens
# Format: https://api.atlassian.com/ex/{product}/{cloud-id}
JIRA_URL=https://api.atlassian.com/ex/jira/YOUR_CLOUD_ID
CONFLUENCE_URL=https://api.atlassian.com/ex/confluence/YOUR_CLOUD_ID

# OAuth App Credentials (from developer.atlassian.com)
ATLASSIAN_OAUTH_CLIENT_ID=YOUR_CLIENT_ID
ATLASSIAN_OAUTH_CLIENT_SECRET=YOUR_CLIENT_SECRET
ATLASSIAN_OAUTH_REDIRECT_URI=http://localhost:8000/connections/atlassian/callback
ATLASSIAN_OAUTH_SCOPE=read:jira-user read:jira-work write:jira-work read:confluence-space.summary write:confluence-content offline_access
ATLASSIAN_OAUTH_CLOUD_ID=YOUR_CLOUD_ID

# Logging
MCP_LOGGING_LEVEL=INFO
EOF
```

**Critical Configuration Notes:**

- ✅ **URL Format**: Use `https://api.atlassian.com/ex/jira/{cloud-id}` (NOT `https://your-site.atlassian.net`)
- ✅ **Scopes**: Must include `read:jira-user` for `/myself` endpoint
- ✅ **offline_access**: Required for refresh tokens
- ✅ **Cloud ID**: Must match your Atlassian site

#### Run Docker Container

```bash
docker run --rm -d \
  --name mcp-atlassian \
  -p 9000:8000 \
  --env-file mcp-atlassian.env \
  ghcr.io/sooperset/mcp-atlassian:latest \
  --transport streamable-http --port 8000 -vv
```

**Verify it's running:**

```bash
# Check container status
docker ps | grep mcp-atlassian

# Check logs
docker logs mcp-atlassian

# Expected output:
# INFO - Starting MCP server 'Atlassian MCP' with transport 'streamable-http'
```

### 3. Configure Bond Backend

Add to `.env` file:

```bash
BOND_MCP_CONFIG='{
  "mcpServers": {
    "my_client": {
      "url": "http://127.0.0.1:5555/mcp",
      "transport": "streamable-http"
    },
    "atlassian": {
      "url": "http://localhost:9000/mcp",
      "auth_type": "oauth2",
      "transport": "streamable-http",
      "display_name": "Atlassian",
      "description": "Connect to Atlassian Jira and Confluence",
      "oauth_config": {
        "provider": "atlassian",
        "client_id": "YOUR_CLIENT_ID",
        "client_secret": "YOUR_CLIENT_SECRET",
        "authorize_url": "https://auth.atlassian.com/authorize",
        "token_url": "https://auth.atlassian.com/oauth/token",
        "scopes": "read:jira-user read:jira-work write:jira-work read:confluence-space.summary write:confluence-content offline_access",
        "redirect_uri": "http://localhost:8000/connections/atlassian/callback"
      },
      "site_url": "https://your-site.atlassian.net",
      "cloud_id": "YOUR_CLOUD_ID"
    }
  }
}'
```

**Replace**:
- `YOUR_CLIENT_ID` - From Atlassian developer console
- `YOUR_CLIENT_SECRET` - From Atlassian developer console
- `YOUR_CLOUD_ID` - Your Atlassian cloud ID
- `your-site` - Your Atlassian site name

### 4. Restart Backend

```bash
# Stop current backend (Ctrl+C)

# Restart with new config
poetry run uvicorn bondable.rest.main:app --reload --port 8000
```

### 5. Authorize Connection

1. **Open UI**: http://localhost:3000/connections
2. **Click "Connect"** on Atlassian connection
3. **Authorize**: You'll be redirected to Atlassian
4. **Grant Access**: Accept permissions
5. **Verify**: Connection shows as "Active" with green status

### 6. Test Integration

#### Test 1: Verify Tools Are Discovered

```bash
poetry run pytest tests/test_mcp_tools_fetching.py::TestOAuth2Server::test_atlassian_tools_present -v -s
```

**Expected**: 42 Atlassian tools discovered (35 Jira + 7 Confluence)

#### Test 2: End-to-End Integration

```bash
poetry run pytest tests/test_mcp_atlassian_e2e.py::TestE2EAtlassianIntegration::test_complete_jira_integration_flow -v -s
```

**Expected**: Agent created, Jira tool called successfully, real data returned

#### Test 3: Token Refresh

```bash
poetry run python tests/test_token_refresh.py
```

**Expected**: Expired token automatically refreshed, new token works

---

## Testing

### Unit Tests

```bash
# Test MCP configuration
poetry run pytest tests/test_mcp_tools_fetching.py::TestMcpConfiguration -v -s

# Test server connectivity
poetry run pytest tests/test_mcp_tools_fetching.py::TestMcpServersRunning -v -s

# Test tool discovery
poetry run pytest tests/test_mcp_tools_fetching.py::TestMcpToolsEndpoint -v -s
```

### Integration Tests

```bash
# Test OAuth token flow
poetry run pytest tests/test_mcp_tools_fetching.py::TestOAuth2Server -v -s

# Test multi-server discovery
poetry run pytest tests/test_mcp_tools_fetching.py::TestMultiServerDiscovery -v -s
```

### End-to-End Tests

```bash
# Test complete flow with agent
poetry run pytest tests/test_mcp_atlassian_e2e.py -v -s
```

### Manual Testing

1. **Create Agent with MCP Tools**:
   - Go to http://localhost:3000/agents
   - Click "Create Agent"
   - In "MCP Tools" section, select Jira tools (e.g., `jira_get_issue`)
   - Click "Create"

2. **Test Agent**:
   - Go to Chat
   - Select your agent
   - Ask: "Tell me about Jira issue PROJECT-123"
   - Verify: Agent calls tool and returns real issue data

3. **Verify Logs**:
   ```bash
   # Backend logs should show:
   # [MCP Execute] Found tool 'jira_get_issue' on server 'atlassian'
   # [MCP Execute] Executing tool 'jira_get_issue' with parameters: ['issue_key']
   ```

---

## Production Deployment

### 1. Update OAuth App

1. **Add Production Redirect URI**:
   - `https://api.yourdomain.com/connections/atlassian/callback`

2. **Verify Scopes** include `offline_access`

### 2. Deploy MCP Server

#### Option A: Docker on EC2/ECS

```bash
# Create production environment file
cat > mcp-atlassian-prod.env <<EOF
JIRA_URL=https://api.atlassian.com/ex/jira/YOUR_CLOUD_ID
CONFLUENCE_URL=https://api.atlassian.com/ex/confluence/YOUR_CLOUD_ID
ATLASSIAN_OAUTH_CLIENT_ID=YOUR_PROD_CLIENT_ID
ATLASSIAN_OAUTH_CLIENT_SECRET=YOUR_PROD_CLIENT_SECRET
ATLASSIAN_OAUTH_REDIRECT_URI=https://api.yourdomain.com/connections/atlassian/callback
ATLASSIAN_OAUTH_SCOPE=read:jira-user read:jira-work write:jira-work read:confluence-space.summary write:confluence-content offline_access
ATLASSIAN_OAUTH_CLOUD_ID=YOUR_CLOUD_ID
MCP_LOGGING_LEVEL=INFO
EOF

# Deploy to ECS or EC2
docker run -d \
  --name mcp-atlassian \
  -p 9000:8000 \
  --restart unless-stopped \
  --env-file mcp-atlassian-prod.env \
  ghcr.io/sooperset/mcp-atlassian:latest \
  --transport streamable-http --port 8000
```

#### Option B: AWS App Runner / ECS Fargate

Use the Docker image with environment variables from Secrets Manager.

### 3. Update Bond Backend Config

Update production `.env` or environment variables:

```bash
BOND_MCP_CONFIG='{
  "mcpServers": {
    "atlassian": {
      "url": "https://mcp-atlassian.yourdomain.com/mcp",
      "auth_type": "oauth2",
      "transport": "streamable-http",
      "display_name": "Atlassian",
      "description": "Connect to Atlassian Jira and Confluence",
      "oauth_config": {
        "provider": "atlassian",
        "client_id": "PROD_CLIENT_ID",
        "client_secret": "PROD_CLIENT_SECRET",
        "authorize_url": "https://auth.atlassian.com/authorize",
        "token_url": "https://auth.atlassian.com/oauth/token",
        "scopes": "read:jira-user read:jira-work write:jira-work read:confluence-space.summary write:confluence-content offline_access",
        "redirect_uri": "https://api.yourdomain.com/connections/atlassian/callback"
      },
      "cloud_id": "YOUR_CLOUD_ID"
    }
  }
}'
```

### 4. Security Considerations

- ✅ **HTTPS Only**: Use HTTPS for all production endpoints
- ✅ **Secrets Management**: Store secrets in AWS Secrets Manager or similar
- ✅ **Token Encryption**: Tokens encrypted at rest using JWT secret
- ✅ **Network Security**: Restrict MCP server access to Bond backend only
- ✅ **Audit Logging**: Enable logging for token refresh and tool execution

---

## Troubleshooting

### Issue 1: OAuth Flow Fails with "Unauthorized"

**Symptoms:**
```
[Connections] Token exchange failed: {"error":"access_denied","error_description":"Unauthorized"}
```

**Causes & Solutions:**

1. **Missing client_secret**:
   - **Fix**: Ensure `client_secret` is in `oauth_config` in `.env`
   - **Verify**: Check `bondable/rest/routers/connections.py` line 148-172

2. **Redirect URI Mismatch**:
   - **Fix**: Ensure redirect URI in OAuth app matches exactly:
     - `.env`: `http://localhost:8000/connections/atlassian/callback`
     - OAuth App: `http://localhost:8000/connections/atlassian/callback`
   - **Note**: HTTPS vs HTTP, trailing slash, port number must all match

3. **Invalid Client Credentials**:
   - **Fix**: Re-copy client_id and client_secret from OAuth app
   - **Verify**: No extra spaces or characters

### Issue 2: Tools Not Appearing in UI

**Symptoms:**
- Connection shows as "Active"
- No tools visible in agent create/edit page
- Backend logs show: `[MCP Tools] Server 'atlassian': 0 tools`

**Causes & Solutions:**

1. **mcp-atlassian Not Configured**:
   - **Check**: `docker logs mcp-atlassian`
   - **Fix**: Ensure `mcp-atlassian.env` has OAuth app credentials
   - **Restart**: `docker restart mcp-atlassian`

2. **Wrong URL Format**:
   - **Wrong**: `JIRA_URL=https://yoursite.atlassian.net`
   - **Correct**: `JIRA_URL=https://api.atlassian.com/ex/jira/CLOUD_ID`
   - **Why**: OAuth 2.0 tokens only work with cloud API format

3. **Token Missing Scopes**:
   - **Check**: `poetry run python tests/inspect_atlassian_token.py`
   - **Fix**: Re-authorize with updated scopes including `read:jira-user`

### Issue 3: Tool Execution Fails with 401 Unauthorized

**Symptoms:**
```
[MCP Execute] Error on server 'atlassian': Error calling tool 'get_issue'
ValueError: Invalid user Jira token or configuration: Unauthorized (401)
```

**Causes & Solutions:**

1. **Token Expired**:
   - **Check**: `poetry run python tests/test_atlassian_token_status.py`
   - **Fix**: Token should auto-refresh if `offline_access` scope present
   - **Manual Fix**: Re-authorize via UI

2. **Missing read:jira-user Scope**:
   - **Check**: Token scopes in database
   - **Fix**: Add `read:jira-user` to scopes in `.env` and mcp-atlassian.env
   - **Re-authorize**: Required to get new token with updated scopes

3. **mcp-atlassian Using Wrong URL**:
   - **Check**: `docker exec mcp-atlassian env | grep JIRA_URL`
   - **Fix**: Update to cloud API format, restart container

### Issue 4: "Tool not found on any configured MCP server"

**Symptoms:**
```
[MCP Execute] Tool 'jira_get_issue' not found on any configured MCP server
```

**Causes & Solutions:**

1. **Tool Name Mismatch**:
   - **Check**: List available tools:
     ```bash
     poetry run pytest tests/test_mcp_tools_fetching.py::TestOAuth2Server::test_atlassian_tools_present -v -s
     ```
   - **Fix**: Use exact tool name from output (e.g., `jira_get_issue`, not `get_issue`)

2. **MCP Server Not Running**:
   - **Check**: `docker ps | grep mcp-atlassian`
   - **Fix**: `docker start mcp-atlassian` or re-run docker run command

3. **Token Cache Issue**:
   - **Check**: Backend logs for auth errors
   - **Fix**: Restart backend to reload config

### Issue 5: Token Refresh Fails

**Symptoms:**
```
[REFRESH_TOKEN] Token refresh failed with status 400
```

**Causes & Solutions:**

1. **No offline_access Scope**:
   - **Fix**: Add `offline_access` to scopes in both `.env` and `mcp-atlassian.env`
   - **Re-authorize**: Get new token with refresh token

2. **Refresh Token Revoked**:
   - **Cause**: User revoked access or token expired (30 days for Atlassian)
   - **Fix**: User must re-authorize via UI

3. **Invalid Client Credentials**:
   - **Check**: client_id and client_secret match OAuth app
   - **Fix**: Update credentials, restart backend

### Issue 6: Connection Shows as Active But Doesn't Work

**Symptoms:**
- UI shows "Active" with green status
- Tools discovered correctly
- Tool execution fails

**Debug Steps:**

1. **Check Token Status**:
   ```bash
   poetry run python tests/test_atlassian_token_status.py
   ```

2. **Test Token Directly**:
   ```bash
   poetry run python tests/test_atlassian_token_direct.py
   ```

3. **Check MCP Server Logs**:
   ```bash
   docker logs mcp-atlassian --tail 50
   ```

4. **Test Cloud API URLs**:
   ```bash
   poetry run python tests/test_cloud_api_urls.py
   ```

---

## Advanced Topics

### Custom MCP Servers

To add a custom OAuth MCP server:

1. **Implement OAuth 2.0 in MCP Server**:
   - Accept user tokens via `Authorization: Bearer {token}` header
   - Configure with OAuth app credentials
   - Support user-specific data isolation

2. **Configure in Bond**:
   ```json
   "your_service": {
     "url": "http://localhost:PORT/mcp",
     "auth_type": "oauth2",
     "transport": "streamable-http",
     "oauth_config": {
       "provider": "your_service",
       "client_id": "...",
       "client_secret": "...",
       "authorize_url": "https://auth.your-service.com/authorize",
       "token_url": "https://auth.your-service.com/token",
       "scopes": "scope1 scope2 offline_access",
       "redirect_uri": "http://localhost:8000/connections/your_service/callback"
     }
   }
   ```

3. **Test Integration**: Follow testing steps above

### Token Encryption

Tokens are encrypted at rest using the JWT secret key:

```python
# From bondable/bond/auth/token_encryption.py
from cryptography.fernet import Fernet
import hashlib
from bondable.bond.config import Config

def get_encryption_key() -> bytes:
    """Derive encryption key from JWT secret."""
    jwt_secret = Config.config().get_jwt_config().JWT_SECRET_KEY
    key_material = hashlib.sha256(jwt_secret.encode()).digest()
    return base64.urlsafe_b64encode(key_material)

def encrypt_token(token: str) -> str:
    """Encrypt a token for database storage."""
    fernet = Fernet(get_encryption_key())
    return fernet.encrypt(token.encode()).decode()

def decrypt_token(encrypted: str) -> str:
    """Decrypt a token from database."""
    fernet = Fernet(get_encryption_key())
    return fernet.decrypt(encrypted.encode()).decode()
```

### Automatic Token Refresh

Tokens are automatically refreshed when expired:

```python
# From bondable/bond/auth/mcp_token_cache.py
def get_token(self, user_id: str, connection_name: str, auto_refresh: bool = True):
    """Get token, auto-refreshing if expired."""
    token_data = self._load_from_database(user_id, connection_name)

    if token_data.is_expired() and auto_refresh and token_data.refresh_token:
        # Automatically refresh
        refreshed = self._refresh_token(user_id, connection_name, token_data)
        return refreshed

    return token_data
```

**Refresh Process**:
1. Detect token expired (5-minute buffer before actual expiration)
2. Use refresh token to request new access token
3. Save new token to database
4. Return refreshed token transparently

**Testing Refresh**:
```bash
poetry run python tests/test_token_refresh.py
```

### Multi-Server Discovery

Tools from all configured servers are aggregated:

```python
# From bondable/bond/providers/bedrock/BedrockMCP.py
async def _get_mcp_tool_definitions(mcp_config, tool_names, user_id):
    """Get tool definitions from ALL configured MCP servers."""
    servers = mcp_config.get('mcpServers', {})
    tool_definitions = []

    for server_name, server_config in servers.items():
        # Authenticate based on auth_type
        headers = _get_auth_headers_for_server(server_name, server_config, user)

        # Connect and list tools
        async with Client(transport) as client:
            tools = await client.list_tools()
            tool_definitions.extend(tools)

    return tool_definitions
```

---

## Quick Reference

### Environment Variables

| Variable | Purpose | Example |
|----------|---------|---------|
| `BOND_MCP_CONFIG` | MCP server configuration | JSON config |
| `JWT_SECRET_KEY` | Token encryption key | 64-char hex string |
| `CORS_ALLOWED_ORIGINS` | Frontend CORS | `http://localhost:3000` |

### Docker Commands

```bash
# Run mcp-atlassian
docker run -d --name mcp-atlassian -p 9000:8000 \
  --env-file mcp-atlassian.env \
  ghcr.io/sooperset/mcp-atlassian:latest \
  --transport streamable-http --port 8000 -vv

# View logs
docker logs mcp-atlassian -f

# Restart
docker restart mcp-atlassian

# Stop and remove
docker stop mcp-atlassian && docker rm mcp-atlassian
```

### API Endpoints

| Endpoint | Purpose |
|----------|---------|
| `GET /connections/configs` | List available connections |
| `GET /connections/atlassian/authorize` | Start OAuth flow |
| `GET /connections/atlassian/callback` | OAuth callback |
| `DELETE /connections/atlassian/disconnect` | Revoke connection |
| `GET /mcp/tools` | List all MCP tools |

### Test Files

| File | Purpose |
|------|---------|
| `tests/test_mcp_tools_fetching.py` | Test tool discovery |
| `tests/test_mcp_atlassian_e2e.py` | Test complete flow |
| `tests/test_token_refresh.py` | Test auto-refresh |
| `tests/test_atlassian_token_status.py` | Check token status |
| `tests/inspect_atlassian_token.py` | View token details |

---

## Support

For issues or questions:

1. **Check Logs**:
   - Backend: Terminal running uvicorn
   - MCP Server: `docker logs mcp-atlassian`
   - Frontend: Browser console

2. **Run Tests**:
   ```bash
   poetry run pytest tests/test_mcp_tools_fetching.py -v -s
   ```

3. **Debug Tools**:
   - `tests/test_atlassian_token_status.py` - Token status
   - `tests/inspect_atlassian_token.py` - Token contents
   - `tests/test_cloud_api_urls.py` - API connectivity

---

**Last Updated**: November 2025
**Version**: 1.0
