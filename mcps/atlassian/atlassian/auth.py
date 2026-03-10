"""
Bearer token and cloud ID extraction for MCP server.

The MCP server does NOT manage OAuth. Bond AI's backend handles authorization,
token exchange, and storage. The MCP server receives the user's Atlassian OAuth
access token as an Authorization: Bearer header and the cloud ID as an
X-Atlassian-Cloud-Id header, then uses them directly.
"""

from fastmcp.server.dependencies import get_http_headers


def get_atlassian_token() -> str:
    """
    Extract Atlassian OAuth token from Authorization: Bearer header.

    Returns:
        The raw access token string.

    Raises:
        PermissionError: If no valid Bearer token is present.
    """
    headers = get_http_headers(include={"authorization"})
    auth = headers.get("authorization")
    if not auth or not auth.startswith("Bearer "):
        raise PermissionError(
            "Authorization required. Please connect your Atlassian account in Bond AI Settings -> Connections."
        )
    return auth[7:]


def get_cloud_id() -> str:
    """
    Extract Atlassian cloud ID from X-Atlassian-Cloud-Id header.

    Returns:
        The cloud ID string.

    Raises:
        PermissionError: If no cloud ID header is present.
    """
    headers = get_http_headers(include={"x-atlassian-cloud-id"})
    cloud_id = headers.get("x-atlassian-cloud-id")
    if not cloud_id:
        raise PermissionError(
            "Atlassian Cloud ID required. Please ensure your Atlassian connection "
            "is configured with a cloud_id in Bond AI Settings -> Connections."
        )
    return cloud_id
