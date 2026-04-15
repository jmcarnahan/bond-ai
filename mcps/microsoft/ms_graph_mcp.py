#!/usr/bin/env python3
"""
Microsoft Graph MCP Server for Bond AI.

Provides email and Teams tools that use the user's Microsoft Graph OAuth token,
passed through by Bond AI's backend as an Authorization: Bearer header.

Run:
    fastmcp run ms_graph_mcp.py --transport streamable-http --port 5557
"""

import logging
import os
from contextlib import asynccontextmanager

from fastmcp import FastMCP

from ms_graph.auth import get_graph_token
from ms_graph.graph_client import AsyncGraphClient
from ms_graph import mail as mail_ops
from ms_graph import teams as teams_ops
from ms_graph import files as files_ops
from ms_graph.teams import TeamsNotAvailableError, extract_message_text, extract_message_sender

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def _lifespan(app):
    """Validate auth proxy is reachable when local auth is configured."""
    if os.environ.get("MS_CLIENT_ID"):
        from shared_auth import OAuthProxyClient
        proxy = OAuthProxyClient()
        proxy.check_proxy()
        logger.info("Auth proxy validated for local Microsoft auth")
    yield


mcp = FastMCP("Microsoft Graph MCP Server", lifespan=_lifespan)


# ---------------------------------------------------------------------------
# User profile tools
# ---------------------------------------------------------------------------

@mcp.tool()
async def get_user_profile() -> str:
    """
    Get the authenticated user's profile information.

    Returns the user's display name, email addresses, and account identifiers.
    Useful for discovering who you are sending email as.

    IMPORTANT: If a "Mailbox Address" is shown, use that as the from_address
    when sending email. This is the address that the mail server is authorized
    to send from, and avoids "via" warnings and spam filtering.
    """
    token = get_graph_token()
    async with AsyncGraphClient(token) as client:
        profile = await mail_ops.aget_profile(client)

    lines = [
        f"**Display Name:** {profile.get('displayName', '?')}",
        f"**Mail:** {profile.get('mail', '(not set)')}",
        f"**User Principal Name:** {profile.get('userPrincipalName', '?')}",
    ]
    mailbox_addr = profile.get("mailboxAddress")
    if mailbox_addr:
        lines.append(f"**Mailbox Address:** {mailbox_addr}")
    if profile.get("jobTitle"):
        lines.append(f"**Job Title:** {profile['jobTitle']}")
    lines.append(f"**ID:** `{profile.get('id', '?')}`")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Email tools
# ---------------------------------------------------------------------------

@mcp.tool()
async def list_emails(folder: str = "inbox", top: int = 10) -> str:
    """
    List recent emails from a mailbox folder.

    Args:
        folder: Mail folder to list (default: inbox).
        top: Maximum number of messages to return (default: 10).
    """
    token = get_graph_token()
    async with AsyncGraphClient(token) as client:
        messages = await mail_ops.alist_messages(client, folder=folder, top=top)

    if not messages:
        return "No messages found."

    lines = [f"Found {len(messages)} message(s):\n"]
    for i, msg in enumerate(messages, 1):
        sender = msg.get("from", {}).get("emailAddress", {})
        lines.append(
            f"{i}. **{msg.get('subject', '(no subject)')}**\n"
            f"   From: {sender.get('name', '?')} <{sender.get('address', '?')}>\n"
            f"   Date: {msg.get('receivedDateTime', '?')}\n"
            f"   ID: `{msg.get('id', '?')}`"
        )
    return "\n\n".join(lines)


@mcp.tool()
async def read_email(message_id: str) -> str:
    """
    Read a single email message by its ID.

    Args:
        message_id: The Graph API message ID (from list_emails output).
    """
    token = get_graph_token()
    async with AsyncGraphClient(token) as client:
        msg = await mail_ops.aget_message(client, message_id)

    sender = msg.get("from", {}).get("emailAddress", {})
    to_addrs = ", ".join(
        r.get("emailAddress", {}).get("address", "?")
        for r in msg.get("toRecipients", [])
    )
    body = msg.get("body", {})
    content = body.get("content", "")
    if body.get("contentType") != "text":
        content = f"[HTML content, {len(content)} chars]\n{content[:3000]}"

    return (
        f"**Subject:** {msg.get('subject', '(no subject)')}\n"
        f"**From:** {sender.get('name', '?')} <{sender.get('address', '?')}>\n"
        f"**To:** {to_addrs}\n"
        f"**Date:** {msg.get('receivedDateTime', '?')}\n\n"
        f"{content}"
    )


@mcp.tool()
async def send_email(to: str, subject: str, body: str, cc: str = "", from_address: str = "") -> str:
    """
    Send an email message.

    Args:
        to: Recipient email address (comma-separated for multiple).
        subject: Email subject line.
        body: Plain text email body.
        cc: CC recipients (comma-separated, optional).
        from_address: Sender email address (optional). Use to send from a specific
            alias (e.g., your Outlook address instead of the account login address).
    """
    token = get_graph_token()
    to_list = [addr.strip() for addr in to.split(",") if addr.strip()]
    cc_list = [addr.strip() for addr in cc.split(",") if addr.strip()] if cc else None

    async with AsyncGraphClient(token) as client:
        await mail_ops.asend_message(
            client, to=to_list, subject=subject, body=body,
            cc=cc_list, from_address=from_address or None,
        )

    cc_note = f" (CC: {cc})" if cc else ""
    return f"Email sent to {to}{cc_note}."


@mcp.tool()
async def search_emails(query: str, top: int = 10) -> str:
    """
    Search email messages using a keyword query.

    Args:
        query: Search query (e.g., "from:john budget report").
        top: Maximum number of results (default: 10).
    """
    token = get_graph_token()
    async with AsyncGraphClient(token) as client:
        messages = await mail_ops.asearch_messages(client, query=query, top=top)

    if not messages:
        return f'No messages found matching "{query}".'

    lines = [f'Found {len(messages)} result(s) for "{query}":\n']
    for i, msg in enumerate(messages, 1):
        sender = msg.get("from", {}).get("emailAddress", {})
        lines.append(
            f"{i}. **{msg.get('subject', '(no subject)')}**\n"
            f"   From: {sender.get('name', '?')} <{sender.get('address', '?')}>\n"
            f"   Date: {msg.get('receivedDateTime', '?')}\n"
            f"   ID: `{msg.get('id', '?')}`"
        )
    return "\n\n".join(lines)


# ---------------------------------------------------------------------------
# Teams tools
# ---------------------------------------------------------------------------

@mcp.tool()
async def list_teams() -> str:
    """List Microsoft Teams that the user has joined."""
    token = get_graph_token()
    try:
        async with AsyncGraphClient(token) as client:
            team_list = await teams_ops.alist_joined_teams(client)
    except TeamsNotAvailableError:
        return "Microsoft Teams is not available for this account. A Microsoft 365 license is required."

    if not team_list:
        return "No teams found."

    lines = [f"Joined {len(team_list)} team(s):\n"]
    for t in team_list:
        lines.append(f"- **{t.get('displayName', '?')}** (ID: `{t.get('id', '?')}`)")
    return "\n".join(lines)


@mcp.tool()
async def list_team_channels(team_id: str) -> str:
    """
    List channels in a Microsoft Teams team.

    Args:
        team_id: The team ID (from list_teams output).
    """
    token = get_graph_token()
    try:
        async with AsyncGraphClient(token) as client:
            channels = await teams_ops.alist_channels(client, team_id)
    except TeamsNotAvailableError:
        return "Microsoft Teams is not available for this account."

    if not channels:
        return "No channels found."

    lines = [f"Found {len(channels)} channel(s):\n"]
    for ch in channels:
        lines.append(f"- **{ch.get('displayName', '?')}** (ID: `{ch.get('id', '?')}`)")
    return "\n".join(lines)


@mcp.tool()
async def send_teams_message(team_id: str, channel_id: str, message: str) -> str:
    """
    Send a message to a Microsoft Teams channel.

    Args:
        team_id: The team ID.
        channel_id: The channel ID.
        message: Message content to send.
    """
    token = get_graph_token()
    try:
        async with AsyncGraphClient(token) as client:
            await teams_ops.asend_channel_message(client, team_id, channel_id, message)
    except TeamsNotAvailableError:
        return "Microsoft Teams is not available for this account."

    return "Message sent to Teams channel."


@mcp.tool()
async def read_channel_messages(team_id: str, channel_id: str, top: int = 20) -> str:
    """
    Read recent messages from a Teams channel.

    Args:
        team_id: The team ID (from list_teams output).
        channel_id: The channel ID (from list_team_channels output).
        top: Maximum number of messages to return (default: 20).
    """
    token = get_graph_token()
    try:
        async with AsyncGraphClient(token) as client:
            messages = await teams_ops.alist_channel_messages(
                client, team_id, channel_id, top=top,
            )
    except TeamsNotAvailableError:
        return "Microsoft Teams is not available for this account."

    if not messages:
        return "No messages found in this channel."

    lines = [f"Found {len(messages)} message(s):\n"]
    for i, msg in enumerate(messages, 1):
        sender = extract_message_sender(msg)
        content = extract_message_text(msg)
        lines.append(
            f"{i}. **{sender}** ({msg.get('createdDateTime', '?')})\n"
            f"   {content or '(empty)'}\n"
            f"   ID: `{msg.get('id', '?')}`"
        )
    return "\n\n".join(lines)


@mcp.tool()
async def list_chats(chat_type: str = "", top: int = 20) -> str:
    """
    List Teams chats (1:1, group, meeting) with last message preview.

    Args:
        chat_type: Filter by type: oneOnOne, group, or meeting. Empty for all.
        top: Maximum number of chats to return (default: 20).
    """
    valid_types = {"", "oneOnOne", "group", "meeting"}
    if chat_type not in valid_types:
        return f"Invalid chat_type: {chat_type}. Must be one of: oneOnOne, group, meeting (or empty for all)."

    token = get_graph_token()
    try:
        async with AsyncGraphClient(token) as client:
            chats = await teams_ops.alist_chats(client, chat_type=chat_type, top=top)
    except TeamsNotAvailableError:
        return "Microsoft Teams is not available for this account."

    if not chats:
        return "No chats found."

    lines = [f"Found {len(chats)} chat(s):\n"]
    for i, chat in enumerate(chats, 1):
        ct = chat.get("chatType", "?")
        topic = chat.get("topic")
        members = chat.get("members") or []
        member_names = [m.get("displayName", "?") for m in members if m.get("displayName")]
        members_str = ", ".join(member_names[:5])
        if len(member_names) > 5:
            members_str += f" (+{len(member_names) - 5} more)"

        preview = chat.get("lastMessagePreview") or {}
        preview_text = (preview.get("body") or {}).get("content", "")
        preview_sender = ((preview.get("from") or {}).get("user") or {}).get("displayName", "")
        preview_date = preview.get("createdDateTime", "")

        label = topic or members_str or "(unnamed)"
        lines.append(
            f"{i}. **{label}** (type: {ct})\n"
            f"   Members: {members_str or '(unknown)'}\n"
            f"   Last: {preview_sender}: {preview_text[:100]}" + (f" ({preview_date})" if preview_date else "") + "\n"
            f"   ID: `{chat.get('id', '?')}`"
        )
    return "\n\n".join(lines)


@mcp.tool()
async def read_chat_messages(chat_id: str, top: int = 20) -> str:
    """
    Read recent messages from a Teams chat (1:1, group, or meeting).

    Args:
        chat_id: The chat ID (from list_chats output).
        top: Maximum number of messages to return (default: 20).
    """
    token = get_graph_token()
    try:
        async with AsyncGraphClient(token) as client:
            messages = await teams_ops.alist_chat_messages(client, chat_id, top=top)
    except TeamsNotAvailableError:
        return "Microsoft Teams is not available for this account."

    if not messages:
        return "No messages found in this chat."

    lines = [f"Found {len(messages)} message(s):\n"]
    for i, msg in enumerate(messages, 1):
        sender = extract_message_sender(msg)
        content = extract_message_text(msg)
        lines.append(
            f"{i}. **{sender}** ({msg.get('createdDateTime', '?')})\n"
            f"   {content or '(empty)'}\n"
            f"   ID: `{msg.get('id', '?')}`"
        )
    return "\n\n".join(lines)


@mcp.tool()
async def send_chat_message(chat_id: str, message: str) -> str:
    """
    Send a message to a Teams chat (1:1, group, or meeting).

    Args:
        chat_id: The chat ID (from list_chats output).
        message: Message content to send.
    """
    token = get_graph_token()
    try:
        async with AsyncGraphClient(token) as client:
            await teams_ops.asend_chat_message(client, chat_id, message)
    except TeamsNotAvailableError:
        return "Microsoft Teams is not available for this account."

    return "Message sent to Teams chat."


@mcp.tool()
async def get_teams_activity(hours: int = 24) -> str:
    """
    Get recent Teams activity across all channels and chats as a CSV digest.

    Scans joined teams' channels and recent chats for messages within the
    specified time window. Ideal for catching up on what you missed.

    Args:
        hours: Look back this many hours (default: 24).
    """
    import csv
    import io

    token = get_graph_token()
    try:
        async with AsyncGraphClient(token) as client:
            activity = await teams_ops.aget_teams_activity(client, hours=hours)
    except TeamsNotAvailableError:
        return "Microsoft Teams is not available for this account."

    if not activity:
        return f"No Teams activity in the last {hours} hours."

    # Count unique sources
    sources = {row["source_name"] for row in activity}

    output = io.StringIO()
    output.write(
        f"Activity in the last {hours} hours: "
        f"{len(activity)} messages across {len(sources)} sources\n\n"
    )

    writer = csv.writer(output)
    writer.writerow(["source", "source_name", "sender", "timestamp", "preview"])
    for row in activity:
        writer.writerow([
            row["source"],
            row["source_name"],
            row["sender"],
            row["timestamp"],
            row["preview"],
        ])

    return output.getvalue()


# ---------------------------------------------------------------------------
# File / OneDrive / SharePoint tools
# ---------------------------------------------------------------------------

def _format_size(size_bytes: int) -> str:
    """Format a file size in bytes to a human-readable string."""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f} MB"
    return f"{size_bytes / (1024 * 1024 * 1024):.1f} GB"


def _format_drive_item(item: dict) -> str:
    """Format a driveItem as a single markdown line."""
    name = item.get("name", "?")
    item_id = item.get("id", "?")
    if "folder" in item:
        child_count = item["folder"].get("childCount", "?")
        return f"- **{name}/** ({child_count} items) — ID: `{item_id}`"
    mime = item.get("file", {}).get("mimeType", "")
    size = _format_size(item.get("size", 0))
    return f"- **{name}** ({mime}, {size}) — ID: `{item_id}`"


@mcp.tool()
async def list_onedrive_files(folder_path: str = "", top: int = 20) -> str:
    """
    List files and folders in the user's OneDrive.

    Args:
        folder_path: Path within OneDrive (e.g., "Documents/Reports"). Empty for root.
        top: Maximum number of items to return (default: 20).
    """
    token = get_graph_token()
    async with AsyncGraphClient(token) as client:
        items = await files_ops.alist_drive_children(client, folder_path=folder_path, top=top)

    if not items:
        loc = f' in "{folder_path}"' if folder_path else " in root"
        return f"No files found{loc}."

    loc = f'"{folder_path}"' if folder_path else "root"
    lines = [f"Found {len(items)} item(s) in {loc}:\n"]
    for item in items:
        lines.append(_format_drive_item(item))
    return "\n".join(lines)


@mcp.tool()
async def get_file_info(item_id: str, site_id: str = "") -> str:
    """
    Get detailed metadata for a file or folder.

    Args:
        item_id: The drive item ID (from list_onedrive_files or search_files output).
        site_id: SharePoint site ID. Leave empty for OneDrive.
    """
    token = get_graph_token()
    async with AsyncGraphClient(token) as client:
        item = await files_ops.aget_drive_item(client, item_id, site_id=site_id)

    name = item.get("name", "?")
    modified = item.get("lastModifiedDateTime", "?")
    modified_by = item.get("lastModifiedBy", {}).get("user", {}).get("displayName", "?")
    web_url = item.get("webUrl", "")

    lines = [f"**Name:** {name}"]
    if "folder" in item:
        lines.append(f"**Type:** Folder ({item['folder'].get('childCount', '?')} items)")
    else:
        mime = item.get("file", {}).get("mimeType", "unknown")
        size = _format_size(item.get("size", 0))
        lines.append(f"**Type:** {mime}")
        lines.append(f"**Size:** {size}")
    lines.append(f"**Modified:** {modified} by {modified_by}")
    lines.append(f"**ID:** `{item.get('id', '?')}`")
    if web_url:
        lines.append(f"**URL:** {web_url}")
    return "\n".join(lines)


@mcp.tool()
async def read_file_content(item_id: str, site_id: str = "") -> str:
    """
    Read the content of a text file from OneDrive or SharePoint.

    Returns the file content for text files (up to 512 KB). For binary files,
    returns metadata and a link to open in the browser.

    Args:
        item_id: The drive item ID.
        site_id: SharePoint site ID. Leave empty for OneDrive.
    """
    token = get_graph_token()
    async with AsyncGraphClient(token) as client:
        item, content = await files_ops.aget_drive_item_content(client, item_id, site_id=site_id)

    name = item.get("name", "?")
    mime = item.get("file", {}).get("mimeType", "unknown")
    size = _format_size(item.get("size", 0))
    modified = item.get("lastModifiedDateTime", "?")
    modified_by = item.get("lastModifiedBy", {}).get("user", {}).get("displayName", "?")
    web_url = item.get("webUrl", "")

    header = (
        f"**File:** {name} ({mime}, {size})\n"
        f"**Modified:** {modified} by {modified_by}\n"
        f"**ID:** `{item.get('id', '?')}`"
    )

    if content is not None:
        return f"{header}\n\n---\n{content}"

    if "folder" in item:
        msg = "This is a folder, not a file. Use list_onedrive_files or list_site_files to browse its contents."
    elif item.get("size", 0) > files_ops.MAX_TEXT_DOWNLOAD_BYTES:
        msg = "This file is too large to display as text (limit: 512 KB)."
    else:
        msg = "This is a binary file and cannot be displayed as text."
    if web_url:
        msg += f"\nOpen in browser: {web_url}"
    return f"{header}\n\n{msg}"


@mcp.tool()
async def search_files(query: str, top: int = 10) -> str:
    """
    Search for files across OneDrive and SharePoint.

    Uses the Microsoft Search API to find files across all connected drives.

    Args:
        query: Search query (e.g., "Q4 budget", "project plan").
        top: Maximum number of results (default: 10).
    """
    token = get_graph_token()
    async with AsyncGraphClient(token) as client:
        results = await files_ops.asearch_files_unified(client, query=query, top=top)

    if not results:
        return f'No files found matching "{query}".'

    lines = [f'Found {len(results)} result(s) for "{query}":\n']
    for i, item in enumerate(results, 1):
        name = item.get("name", "?")
        web_url = item.get("webUrl", "")
        summary = item.get("_searchSummary", "")
        size = _format_size(item.get("size", 0))
        lines.append(
            f"{i}. **{name}** ({size})\n"
            f"   ID: `{item.get('id', '?')}`"
        )
        if summary:
            lines.append(f"   Summary: {summary}")
        if web_url:
            lines.append(f"   URL: {web_url}")
    return "\n\n".join(lines)


@mcp.tool()
async def list_sharepoint_sites(query: str = "", top: int = 10) -> str:
    """
    Search for SharePoint sites, or list followed sites.

    Args:
        query: Search query to find sites (e.g., "engineering"). Leave empty to list followed sites.
        top: Maximum number of results (default: 10).
    """
    token = get_graph_token()
    async with AsyncGraphClient(token) as client:
        sites = await files_ops.alist_sites(client, query=query, top=top)

    if not sites:
        if query:
            return f'No SharePoint sites found matching "{query}".'
        return "No followed SharePoint sites found."

    desc = f'matching "{query}"' if query else "followed"
    lines = [f"Found {len(sites)} {desc} site(s):\n"]
    for site in sites:
        name = site.get("displayName", site.get("name", "?"))
        site_id = site.get("id", "?")
        web_url = site.get("webUrl", "")
        lines.append(f"- **{name}** (ID: `{site_id}`)")
        if web_url:
            lines.append(f"  {web_url}")
    return "\n".join(lines)


@mcp.tool()
async def list_site_files(site_id: str, folder_path: str = "", top: int = 20) -> str:
    """
    List files and folders in a SharePoint site's document library.

    Args:
        site_id: The SharePoint site ID (from list_sharepoint_sites output).
        folder_path: Path within the document library (e.g., "Shared Documents/Reports"). Empty for root.
        top: Maximum number of items to return (default: 20).
    """
    token = get_graph_token()
    async with AsyncGraphClient(token) as client:
        items = await files_ops.alist_drive_children(
            client, folder_path=folder_path, site_id=site_id, top=top
        )

    if not items:
        loc = f' in "{folder_path}"' if folder_path else " in root"
        return f"No files found{loc}."

    loc = f'"{folder_path}"' if folder_path else "root"
    lines = [f"Found {len(items)} item(s) in {loc}:\n"]
    for item in items:
        lines.append(_format_drive_item(item))
    return "\n".join(lines)


if __name__ == "__main__":
    mcp.run()
