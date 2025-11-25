# MCP Authentication Guide

## Overview

Bond AI now supports authenticated MCP (Model Context Protocol) calls, allowing MCP servers to receive and validate user authentication information. This enables MCP tools to perform user-specific operations and enforce access control.

## Features

### Authentication Methods Supported

1. **JWT Token Validation** - MCP servers can validate JWT tokens issued by Bond AI
2. **User Context Parameters** - User information is passed as parameters to MCP tools
3. **Okta Metadata** - Full Okta user profile information is available

### Information Passed to MCP Servers

When an authenticated user triggers an MCP tool call, the following information is automatically included:

#### JWT Token
- `_jwt_token` - The raw JWT token for validation

#### User Context
- `_user_email` - User's email address
- `_user_id` - Bond AI database user ID
- `_user_name` - User's full name
- `_provider` - Authentication provider (e.g., "okta")

#### Okta-Specific Metadata
- `_okta_sub` - Okta unique identifier
- `_given_name` - User's first name
- `_family_name` - User's last name
- `_locale` - User's locale setting

## Architecture

### Authentication Flow

```
User Login (Okta)
    ↓
JWT Token Created (with Okta metadata)
    ↓
User Makes Chat Request
    ↓
JWT Token Extracted
    ↓
Agent Invokes MCP Tool
    ↓
Auth Info Added to MCP Tool Call
    ↓
MCP Server Receives:
    - JWT Token (for validation)
    - User Context (parameters)
    ↓
MCP Tool Executes with User Context
```

### Code Flow

1. **REST API Layer** (`bondable/rest/routers/chat.py`)
   - Extracts JWT token and user info from request
   - Passes to BedrockAgent

2. **Agent Layer** (`bondable/bond/providers/bedrock/BedrockAgent.py`)
   - Receives and stores auth context
   - Passes to MCP tool execution

3. **MCP Layer** (`bondable/bond/providers/bedrock/BedrockMCP.py`)
   - Injects auth info into tool parameters
   - Executes MCP tool with authentication

## Creating an Authenticated MCP Server

### Basic Example

```python
from fastmcp import FastMCP
from typing import Optional, Dict, Any
from jose import jwt, JWTError
import logging

logger = logging.getLogger(__name__)
mcp = FastMCP("Authenticated MCP Server")

# JWT Configuration (must match Bond AI settings)
JWT_SECRET_KEY = "your-secret-key-here"
JWT_ALGORITHM = "HS256"

def validate_jwt_token(token: str) -> Optional[Dict[str, Any]]:
    """Validate JWT token and return payload."""
    try:
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        return payload
    except JWTError as e:
        logger.error(f"JWT validation failed: {e}")
        return None

def require_auth(**kwargs):
    """Extract and validate authentication from kwargs."""
    # Try JWT validation first
    jwt_token = kwargs.get('_jwt_token')
    if jwt_token:
        payload = validate_jwt_token(jwt_token)
        if payload:
            return payload

    # Fall back to user context parameters
    user_email = kwargs.get('_user_email')
    if not user_email:
        raise PermissionError("Authentication required")

    return {
        'email': user_email,
        'user_id': kwargs.get('_user_id'),
        'name': kwargs.get('_user_name'),
        'provider': kwargs.get('_provider')
    }

# Public tool (no auth required)
@mcp.tool()
def public_tool(query: str, **kwargs) -> str:
    """Public tool accessible to all."""
    return f"Result for: {query}"

# Protected tool (auth required)
@mcp.tool(description="Get user-specific data")
def get_user_data(query: str, **kwargs) -> Dict[str, Any]:
    """Protected tool that requires authentication."""
    auth = require_auth(**kwargs)

    return {
        "user_email": auth['email'],
        "query": query,
        "data": f"User-specific data for {auth['email']}"
    }

if __name__ == "__main__":
    mcp.run()
```

### Advanced Example with Full Auth Context

```python
from fastmcp import FastMCP
from typing import Optional
import logging

logger = logging.getLogger(__name__)
mcp = FastMCP("Advanced Auth Server")

class AuthContext:
    """Extract full authentication context."""

    def __init__(self, **kwargs):
        self.authenticated = False
        self.user_email = kwargs.get('_user_email')
        self.user_id = kwargs.get('_user_id')
        self.user_name = kwargs.get('_user_name')
        self.provider = kwargs.get('_provider')
        self.okta_sub = kwargs.get('_okta_sub')
        self.given_name = kwargs.get('_given_name')
        self.family_name = kwargs.get('_family_name')

        # Mark as authenticated if we have user info
        if self.user_email or self.user_id:
            self.authenticated = True

    def require_auth(self):
        """Raise exception if not authenticated."""
        if not self.authenticated:
            raise PermissionError("Authentication required")

@mcp.tool(description="Create user resource")
def create_resource(
    resource_name: str,
    resource_type: str,
    **kwargs
) -> Dict[str, Any]:
    """Create a resource for the authenticated user."""
    auth = AuthContext(**kwargs)
    auth.require_auth()

    logger.info(f"Creating {resource_type} '{resource_name}' for {auth.user_email}")

    return {
        "success": True,
        "resource_name": resource_name,
        "resource_type": resource_type,
        "owner": auth.user_email,
        "owner_id": auth.user_id,
        "owner_given_name": auth.given_name,
        "owner_family_name": auth.family_name
    }

if __name__ == "__main__":
    mcp.run()
```

## Configuration

### Bond AI MCP Configuration

Set the `BOND_MCP_CONFIG` environment variable to configure MCP servers:

```json
{
  "mcpServers": {
    "my-auth-server": {
      "url": "http://localhost:8000/mcp/sse"
    }
  }
}
```

### MCP Server JWT Configuration

Ensure your MCP server uses the same JWT secret as Bond AI:

```python
import os

JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "your-secret-key-here")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
```

## Testing

### Running the Test Suite

A comprehensive test suite is provided to verify MCP authentication:

```bash
poetry run python scripts/test_mcp_auth.py
```

This test script:
1. Starts the authenticated MCP server
2. Tests public tools (no auth required)
3. Tests protected tools (auth required)
4. Verifies JWT token validation
5. Tests authentication rejection for unauthenticated requests

### Manual Testing

1. **Start the MCP Server**
   ```bash
   export JWT_SECRET_KEY="your-secret-key-here"
   poetry run python scripts/sample_mcp_server.py
   ```

2. **Configure Bond AI**
   ```bash
   export BOND_MCP_CONFIG='{"mcpServers":{"test":{"url":"http://localhost:8000/mcp/sse"}}}'
   ```

3. **Use the Chat API**
   Make authenticated requests to `/chat` endpoint. MCP tools will automatically receive authentication information.

## Security Considerations

### JWT Secret Management

- **Never commit JWT secrets to version control**
- Use environment variables or secret management services
- Rotate secrets regularly
- Use strong, randomly generated secrets

### Token Validation

- Always validate JWT tokens on the MCP server side
- Check token expiration
- Verify token signature
- Validate required claims (sub, user_id, provider)

### Authentication vs Authorization

- **Authentication** - Verifies who the user is (handled by JWT)
- **Authorization** - Determines what the user can do (implement in your MCP tools)

Example authorization check:

```python
@mcp.tool()
def admin_only_tool(**kwargs) -> str:
    """Tool that requires admin privileges."""
    auth = require_auth(**kwargs)

    # Check if user is admin (example)
    if auth['email'] not in ADMIN_EMAILS:
        raise PermissionError("Admin access required")

    return "Admin operation completed"
```

## Troubleshooting

### Common Issues

#### 1. JWT Validation Fails

**Symptom**: MCP server rejects valid tokens

**Solutions**:
- Verify JWT_SECRET_KEY matches between Bond AI and MCP server
- Check JWT_ALGORITHM is consistent (default: HS256)
- Ensure python-jose is installed: `pip install python-jose`

#### 2. No Authentication Info Received

**Symptom**: MCP tools don't receive `_user_email` or `_jwt_token`

**Solutions**:
- Verify user is authenticated (logged in via Okta)
- Check chat endpoint is passing `current_user` and `jwt_token`
- Review logs for authentication flow

#### 3. Protected Tools Accessible Without Auth

**Symptom**: Protected tools execute without authentication

**Solutions**:
- Ensure `require_auth()` is called in tool implementation
- Verify authentication check raises exception on failure
- Check tool implementation doesn't have try/except swallowing auth errors

### Debug Logging

Enable debug logging to trace authentication flow:

```python
import logging

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)
```

## Examples

### Sample MCP Server

See `scripts/sample_mcp_server.py` for a complete example with:
- JWT token validation
- User context extraction
- Public tools (no auth)
- Protected tools (auth required)
- Full authentication examples

### Available Tools in Sample Server

| Tool | Auth Required | Description |
|------|--------------|-------------|
| `greet` | No | Simple greeting tool |
| `current_time` | No | Returns current time |
| `fetch_data` | No | Returns sample data |
| `get_user_profile` | Yes | Returns authenticated user's profile |
| `fetch_protected_data` | Yes | Returns user-specific data |
| `create_user_resource` | Yes | Creates resource for user |
| `validate_auth` | Yes | Validates and returns auth status |

## Integration with External Services

### Atlassian MCP Server

When connecting to external MCP servers like Atlassian, authentication is automatically passed:

```python
# MCP Config for Atlassian
{
  "mcpServers": {
    "atlassian": {
      "url": "https://your-atlassian-mcp-server.com/mcp"
    }
  }
}
```

The Atlassian MCP server will receive:
- Bond AI JWT token (for user identification)
- User email and context
- Can use this to map to Atlassian user accounts

## API Reference

### User Model

```python
class User(BaseModel):
    email: str
    name: Optional[str] = None
    provider: str
    user_id: str
    okta_sub: Optional[str] = None
    given_name: Optional[str] = None
    family_name: Optional[str] = None
    locale: Optional[str] = None
```

### MCP Tool Parameters

When your MCP tool is called, the following parameters are automatically added:

```python
@mcp.tool()
def my_tool(
    regular_param: str,  # Your normal parameters
    **kwargs  # Automatically includes auth parameters
) -> str:
    # kwargs contains:
    # - _jwt_token: str
    # - _user_email: str
    # - _user_id: str
    # - _user_name: str
    # - _provider: str
    # - _okta_sub: str
    # - _given_name: str
    # - _family_name: str
    pass
```

## Future Enhancements

Potential improvements for future versions:

1. **Custom Headers Support** - Pass auth in HTTP headers for HTTP-based MCP servers
2. **Multiple Auth Providers** - Support for Google, GitHub, etc.
3. **Token Refresh** - Automatic token refresh mechanism
4. **Role-Based Access** - Include user roles in JWT for RBAC
5. **Audit Logging** - Log all MCP tool calls with user context

## Support

For issues or questions:
- Check the troubleshooting section above
- Review logs for authentication errors
- Run the test suite to verify setup
- Check GitHub issues for known problems

## Related Documentation

- [MCP Protocol Authorization](https://modelcontextprotocol.io/docs/tutorials/security/authorization)
- [FastMCP Documentation](https://github.com/jlowin/fastmcp)
- [Okta OAuth2 Setup](bondable/bond/auth/okta_oauth2.py)
- [Bond AI CLAUDE.md](CLAUDE.md)
