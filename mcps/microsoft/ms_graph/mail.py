"""
Mail operations using the Microsoft Graph API.

All functions accept a GraphClient or AsyncGraphClient and return parsed dicts.
"""

from typing import Any, Dict, List, Optional

from .graph_client import GraphClient, AsyncGraphClient


# ---------------------------------------------------------------------------
# Synchronous
# ---------------------------------------------------------------------------

def list_messages(
    client: GraphClient,
    folder: str = "inbox",
    top: int = 10,
) -> List[Dict[str, Any]]:
    """List recent messages in a mail folder."""
    data = client.get(
        f"/me/mailFolders/{folder}/messages",
        params={"$top": top, "$orderby": "receivedDateTime desc"},
    )
    return data.get("value", [])


def get_message(client: GraphClient, message_id: str) -> Dict[str, Any]:
    """Get a single message by ID."""
    return client.get(f"/me/messages/{message_id}")


def send_message(
    client: GraphClient,
    to: List[str],
    subject: str,
    body: str,
    cc: Optional[List[str]] = None,
) -> None:
    """Send an email message."""
    to_recipients = [{"emailAddress": {"address": addr}} for addr in to]
    cc_recipients = [{"emailAddress": {"address": addr}} for addr in (cc or [])]

    payload: Dict[str, Any] = {
        "message": {
            "subject": subject,
            "body": {"contentType": "Text", "content": body},
            "toRecipients": to_recipients,
        },
        "saveToSentItems": True,
    }
    if cc_recipients:
        payload["message"]["ccRecipients"] = cc_recipients

    client.post("/me/sendMail", json_data=payload)


def search_messages(
    client: GraphClient,
    query: str,
    top: int = 10,
) -> List[Dict[str, Any]]:
    """Search messages using KQL query syntax."""
    data = client.get(
        "/me/messages",
        params={"$search": f'"{query}"', "$top": top},
    )
    return data.get("value", [])


# ---------------------------------------------------------------------------
# Asynchronous
# ---------------------------------------------------------------------------

async def alist_messages(
    client: AsyncGraphClient,
    folder: str = "inbox",
    top: int = 10,
) -> List[Dict[str, Any]]:
    """List recent messages in a mail folder (async)."""
    data = await client.get(
        f"/me/mailFolders/{folder}/messages",
        params={"$top": top, "$orderby": "receivedDateTime desc"},
    )
    return data.get("value", [])


async def aget_message(client: AsyncGraphClient, message_id: str) -> Dict[str, Any]:
    """Get a single message by ID (async)."""
    return await client.get(f"/me/messages/{message_id}")


async def asend_message(
    client: AsyncGraphClient,
    to: List[str],
    subject: str,
    body: str,
    cc: Optional[List[str]] = None,
) -> None:
    """Send an email message (async)."""
    to_recipients = [{"emailAddress": {"address": addr}} for addr in to]
    cc_recipients = [{"emailAddress": {"address": addr}} for addr in (cc or [])]

    payload: Dict[str, Any] = {
        "message": {
            "subject": subject,
            "body": {"contentType": "Text", "content": body},
            "toRecipients": to_recipients,
        },
        "saveToSentItems": True,
    }
    if cc_recipients:
        payload["message"]["ccRecipients"] = cc_recipients

    await client.post("/me/sendMail", json_data=payload)


async def asearch_messages(
    client: AsyncGraphClient,
    query: str,
    top: int = 10,
) -> List[Dict[str, Any]]:
    """Search messages using KQL query syntax (async)."""
    data = await client.get(
        "/me/messages",
        params={"$search": f'"{query}"', "$top": top},
    )
    return data.get("value", [])
