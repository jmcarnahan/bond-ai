"""
Token resolution for MCP server.

Path 1: Bearer header (Bond AI backend) -- always preferred
Path 2: Local MSAL auth (Claude Code / standalone) -- if MS_CLIENT_ID set
Path 3: PermissionError
"""

import os


def get_graph_token() -> str:
    """
    Resolve a Microsoft Graph OAuth token.

    Resolution order:
    1. Authorization: Bearer header (from Bond AI backend)
    2. Local MSAL auth (when MS_CLIENT_ID env var is set)
    3. Raise PermissionError

    Returns:
        The raw access token string.

    Raises:
        PermissionError: If no valid token can be obtained.
    """
    # Path 1: Try Bearer header (works when running behind Bond AI)
    try:
        from fastmcp.server.dependencies import get_http_headers
        headers = get_http_headers(include={"authorization"})
        auth = headers.get("authorization")
        if auth and auth.startswith("Bearer "):
            return auth[7:]
    except Exception:  # nosec B110
        pass  # Outside HTTP request context (e.g., stdio transport)

    # Path 2: Local MSAL auth
    if os.environ.get("MS_CLIENT_ID"):
        from ms_graph.local_auth import get_local_token
        return get_local_token()

    # Path 3: No auth available
    raise PermissionError(
        "Authorization required. Either connect your Microsoft account "
        "in Bond AI Settings -> Connections, or set MS_CLIENT_ID for local auth."
    )
