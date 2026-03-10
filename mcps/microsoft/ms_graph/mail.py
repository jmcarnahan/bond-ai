"""
Mail operations using the Microsoft Graph API.

All functions accept a GraphClient or AsyncGraphClient and return parsed dicts.
"""

import logging
import re
from typing import Any, Dict, List, Optional
from urllib.parse import unquote

from .graph_client import GraphClient, AsyncGraphClient, GraphError

logger = logging.getLogger(__name__)


def _extract_mailbox_address(odata_context: str) -> Optional[str]:
    """Extract the mailbox email from an @odata.context URL.

    For consumer accounts, the /me/mailboxSettings @odata.context contains the
    real mailbox address (e.g. ``user@outlook.com``) even when /me returns the
    external login email (e.g. ``user@gmail.com``).
    """
    match = re.search(r"users\('([^']+)'\)", odata_context)
    if match:
        return unquote(match.group(1))
    return None


# ---------------------------------------------------------------------------
# User profile
# ---------------------------------------------------------------------------

def get_profile(client: GraphClient) -> Dict[str, Any]:
    """Get the authenticated user's profile from /me.

    Also attempts to fetch /me/mailboxSettings to discover the real mailbox
    address (important for consumer accounts where /me returns the login email).
    If MailboxSettings.Read scope is available, adds a ``mailboxAddress`` field.
    """
    profile = client.get("/me")
    try:
        settings = client.get("/me/mailboxSettings")
        context = settings.get("@odata.context", "")
        mailbox_addr = _extract_mailbox_address(context)
        if mailbox_addr:
            profile["mailboxAddress"] = mailbox_addr
    except GraphError:
        logger.debug("Could not fetch mailboxSettings (scope may not be granted)")
    return profile


async def aget_profile(client: AsyncGraphClient) -> Dict[str, Any]:
    """Get the authenticated user's profile from /me (async).

    Also attempts to fetch /me/mailboxSettings to discover the real mailbox
    address (important for consumer accounts where /me returns the login email).
    If MailboxSettings.Read scope is available, adds a ``mailboxAddress`` field.
    """
    profile = await client.get("/me")
    try:
        settings = await client.get("/me/mailboxSettings")
        context = settings.get("@odata.context", "")
        mailbox_addr = _extract_mailbox_address(context)
        if mailbox_addr:
            profile["mailboxAddress"] = mailbox_addr
    except GraphError:
        logger.debug("Could not fetch mailboxSettings (scope may not be granted)")
    return profile


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
    from_address: Optional[str] = None,
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
    if from_address:
        payload["message"]["from"] = {"emailAddress": {"address": from_address}}

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
    from_address: Optional[str] = None,
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
    if from_address:
        payload["message"]["from"] = {"emailAddress": {"address": from_address}}

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
