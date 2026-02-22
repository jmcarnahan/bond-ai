"""
Teams operations using the Microsoft Graph API.

All functions accept a GraphClient or AsyncGraphClient and return parsed dicts.
"""

from typing import Any, Dict, List

from .graph_client import GraphClient, AsyncGraphClient, GraphError


class TeamsNotAvailableError(Exception):
    """Raised when Teams operations fail because the account lacks a Teams license."""

    def __init__(self) -> None:
        super().__init__(
            "Microsoft Teams is not available for this account. "
            "Teams requires a Microsoft 365 business or developer license."
        )


def _check_teams_access(e: GraphError) -> None:
    """Raise TeamsNotAvailableError for 403 responses on Teams endpoints."""
    if e.status_code == 403:
        raise TeamsNotAvailableError() from e
    raise e


# ---------------------------------------------------------------------------
# Synchronous
# ---------------------------------------------------------------------------

def list_joined_teams(client: GraphClient) -> List[Dict[str, Any]]:
    """List teams the current user has joined."""
    try:
        data = client.get("/me/joinedTeams")
    except GraphError as e:
        _check_teams_access(e)
    return data.get("value", [])


def list_channels(client: GraphClient, team_id: str) -> List[Dict[str, Any]]:
    """List channels in a team."""
    try:
        data = client.get(f"/teams/{team_id}/channels")
    except GraphError as e:
        _check_teams_access(e)
    return data.get("value", [])


def send_channel_message(
    client: GraphClient,
    team_id: str,
    channel_id: str,
    content: str,
) -> Dict[str, Any]:
    """Send a message to a Teams channel."""
    try:
        result = client.post(
            f"/teams/{team_id}/channels/{channel_id}/messages",
            json_data={"body": {"content": content}},
        )
    except GraphError as e:
        _check_teams_access(e)
    return result or {}


# ---------------------------------------------------------------------------
# Asynchronous
# ---------------------------------------------------------------------------

async def alist_joined_teams(client: AsyncGraphClient) -> List[Dict[str, Any]]:
    """List teams the current user has joined (async)."""
    try:
        data = await client.get("/me/joinedTeams")
    except GraphError as e:
        _check_teams_access(e)
    return data.get("value", [])


async def alist_channels(client: AsyncGraphClient, team_id: str) -> List[Dict[str, Any]]:
    """List channels in a team (async)."""
    try:
        data = await client.get(f"/teams/{team_id}/channels")
    except GraphError as e:
        _check_teams_access(e)
    return data.get("value", [])


async def asend_channel_message(
    client: AsyncGraphClient,
    team_id: str,
    channel_id: str,
    content: str,
) -> Dict[str, Any]:
    """Send a message to a Teams channel (async)."""
    try:
        result = await client.post(
            f"/teams/{team_id}/channels/{channel_id}/messages",
            json_data={"body": {"content": content}},
        )
    except GraphError as e:
        _check_teams_access(e)
    return result or {}
