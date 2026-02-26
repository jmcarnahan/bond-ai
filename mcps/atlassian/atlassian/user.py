"""
User operations — sync and async pairs.

Uses Jira REST API v3 /myself endpoint via the Atlassian cloud gateway.
"""

from typing import Any, Dict

from .atlassian_client import AtlassianClient, AsyncAtlassianClient


def get_myself(client: AtlassianClient) -> Dict[str, Any]:
    """Get the current authenticated user's info."""
    return client.get(f"{client.jira_base}/myself")


async def aget_myself(client: AsyncAtlassianClient) -> Dict[str, Any]:
    """Get the current authenticated user's info (async)."""
    return await client.get(f"{client.jira_base}/myself")
