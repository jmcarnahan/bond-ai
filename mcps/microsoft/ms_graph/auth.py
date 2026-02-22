"""
Bearer token extraction for MCP server.

The MCP server does NOT manage OAuth. Bond AI's backend handles authorization,
token exchange, and refresh. The MCP server receives the user's Microsoft Graph
access token as an Authorization: Bearer header and uses it directly.
"""

from fastmcp.server.dependencies import get_http_headers


def get_graph_token() -> str:
    """
    Extract Microsoft Graph OAuth token from Authorization: Bearer header.

    Returns:
        The raw access token string.

    Raises:
        PermissionError: If no valid Bearer token is present.
    """
    headers = get_http_headers()
    auth = headers.get("authorization") or headers.get("Authorization")
    if not auth or not auth.startswith("Bearer "):
        raise PermissionError(
            "Authorization required. Please connect your Microsoft account in Bond AI Settings -> Connections."
        )
    return auth[7:]
