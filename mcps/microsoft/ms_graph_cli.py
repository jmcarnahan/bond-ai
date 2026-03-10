#!/usr/bin/env python3
"""
Microsoft Graph CLI -- read email and interact with Teams using device code flow.

Usage:
    export MS_CLIENT_ID=<your-azure-app-client-id>

    python ms_graph_cli.py list [--folder inbox] [--top 10]
    python ms_graph_cli.py read <message_id>
    python ms_graph_cli.py send <to> <subject> <body>
    python ms_graph_cli.py search <query> [--top 10]

    python ms_graph_cli.py teams list
    python ms_graph_cli.py teams channels <team_id>
    python ms_graph_cli.py teams send <team_id> <channel_id> <message>
"""

import argparse
import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
import msal

load_dotenv()

from ms_graph.graph_client import GraphClient
from ms_graph import mail, teams, files

TOKEN_CACHE_PATH = Path.home() / ".ms_graph_tokens.json"

MAIL_SCOPES = [
    "Mail.Read",
    "Mail.ReadWrite",
    "Mail.Send",
    "MailboxSettings.Read",
    "User.Read",
]

TEAMS_SCOPES = [
    "Team.ReadBasic.All",
    "Channel.ReadBasic.All",
    "ChannelMessage.Send",
]

FILES_SCOPES = [
    "Files.Read.All",
]

# Sites.Read.All and Teams scopes only work with organizational (M365) accounts
SITES_SCOPES = [
    "Sites.Read.All",
]

SCOPES = MAIL_SCOPES + FILES_SCOPES + (
    SITES_SCOPES + TEAMS_SCOPES if os.environ.get("MS_TENANT_ID") else []
)


def _get_msal_app() -> msal.PublicClientApplication:
    client_id = os.environ.get("MS_CLIENT_ID")
    if not client_id:
        print("Error: MS_CLIENT_ID environment variable is required.", file=sys.stderr)
        sys.exit(1)

    cache = msal.SerializableTokenCache()
    if TOKEN_CACHE_PATH.exists():
        cache.deserialize(TOKEN_CACHE_PATH.read_text())

    app = msal.PublicClientApplication(
        client_id,
        authority=f"https://login.microsoftonline.com/{os.environ.get('MS_TENANT_ID', 'consumers')}",
        token_cache=cache,
    )
    return app, cache


def _get_token() -> str:
    app, cache = _get_msal_app()

    accounts = app.get_accounts()
    result = None
    if accounts:
        result = app.acquire_token_silent(SCOPES, account=accounts[0])

    if not result:
        flow = app.initiate_device_flow(scopes=SCOPES)
        if "user_code" not in flow:
            print(f"Device flow failed: {json.dumps(flow, indent=2)}", file=sys.stderr)
            sys.exit(1)

        print(flow["message"])
        result = app.acquire_token_by_device_flow(flow)

    if "access_token" not in result:
        print(f"Authentication failed: {result.get('error_description', result)}", file=sys.stderr)
        sys.exit(1)

    # Persist cache
    if cache.has_state_changed:
        TOKEN_CACHE_PATH.write_text(cache.serialize())

    # Debug: show granted scopes and decoded token claims
    if os.environ.get("MS_DEBUG"):
        import base64
        print(f"[DEBUG] Scopes granted: {result.get('scope', 'N/A')}", file=sys.stderr)
        print(f"[DEBUG] Token type: {result.get('token_type', 'N/A')}", file=sys.stderr)
        token = result["access_token"]
        # Decode JWT payload (middle segment)
        try:
            parts = token.split(".")
            if len(parts) == 3:
                payload_b64 = parts[1]
                payload_b64 += "=" * (4 - len(payload_b64) % 4)  # pad
                claims = json.loads(base64.b64decode(payload_b64))
                print(f"[DEBUG] aud: {claims.get('aud')}", file=sys.stderr)
                print(f"[DEBUG] iss: {claims.get('iss')}", file=sys.stderr)
                print(f"[DEBUG] scp: {claims.get('scp')}", file=sys.stderr)
                print(f"[DEBUG] ver: {claims.get('ver')}", file=sys.stderr)
            else:
                print(f"[DEBUG] Opaque token (consumer account)", file=sys.stderr)
        except Exception as e:
            print(f"[DEBUG] Could not decode token: {e}", file=sys.stderr)

    return result["access_token"]


def _format_message_summary(msg: dict) -> str:
    sender = msg.get("from", {}).get("emailAddress", {})
    return (
        f"  ID: {msg.get('id', '?')[:20]}...\n"
        f"  From: {sender.get('name', '?')} <{sender.get('address', '?')}>\n"
        f"  Subject: {msg.get('subject', '(no subject)')}\n"
        f"  Date: {msg.get('receivedDateTime', '?')}\n"
        f"  Read: {msg.get('isRead', '?')}"
    )


def cmd_list(args: argparse.Namespace) -> None:
    token = _get_token()
    with GraphClient(token) as client:
        messages = mail.list_messages(client, folder=args.folder, top=args.top)

    if not messages:
        print("No messages found.")
        return

    print(f"Recent messages ({len(messages)}):\n")
    for i, msg in enumerate(messages, 1):
        print(f"[{i}]")
        print(_format_message_summary(msg))
        print()


def cmd_read(args: argparse.Namespace) -> None:
    token = _get_token()
    with GraphClient(token) as client:
        msg = mail.get_message(client, args.message_id)

    sender = msg.get("from", {}).get("emailAddress", {})
    print(f"From: {sender.get('name', '?')} <{sender.get('address', '?')}>")
    print(f"Subject: {msg.get('subject', '(no subject)')}")
    print(f"Date: {msg.get('receivedDateTime', '?')}")
    print(f"To: {', '.join(r.get('emailAddress', {}).get('address', '?') for r in msg.get('toRecipients', []))}")
    print()

    body = msg.get("body", {})
    if body.get("contentType") == "text":
        print(body.get("content", ""))
    else:
        print(f"[HTML body -- {len(body.get('content', ''))} chars]")
        print(body.get("content", "")[:2000])


def cmd_whoami(args: argparse.Namespace) -> None:
    token = _get_token()
    with GraphClient(token) as client:
        profile = mail.get_profile(client)

    print(f"Display Name: {profile.get('displayName', '?')}")
    print(f"Mail: {profile.get('mail', '(not set)')}")
    print(f"User Principal Name: {profile.get('userPrincipalName', '?')}")
    mailbox_addr = profile.get("mailboxAddress")
    if mailbox_addr:
        print(f"Mailbox Address: {mailbox_addr}")
    if profile.get("jobTitle"):
        print(f"Job Title: {profile['jobTitle']}")
    print(f"ID: {profile.get('id', '?')}")


def cmd_send(args: argparse.Namespace) -> None:
    token = _get_token()
    from_addr = getattr(args, "from_address", None) or os.environ.get("MS_DEFAULT_FROM_ADDRESS") or None
    with GraphClient(token) as client:
        mail.send_message(
            client, to=[args.to], subject=args.subject, body=args.body,
            from_address=from_addr,
        )
    print(f"Email sent to {args.to}.")


def cmd_search(args: argparse.Namespace) -> None:
    token = _get_token()
    with GraphClient(token) as client:
        messages = mail.search_messages(client, query=args.query, top=args.top)

    if not messages:
        print("No messages found.")
        return

    print(f"Search results ({len(messages)}):\n")
    for i, msg in enumerate(messages, 1):
        print(f"[{i}]")
        print(_format_message_summary(msg))
        print()


def cmd_teams_list(args: argparse.Namespace) -> None:
    token = _get_token()
    with GraphClient(token) as client:
        team_list = teams.list_joined_teams(client)

    if not team_list:
        print("No teams found.")
        return

    print(f"Joined teams ({len(team_list)}):\n")
    for t in team_list:
        print(f"  {t.get('displayName', '?')}  (id: {t.get('id', '?')})")


def cmd_teams_channels(args: argparse.Namespace) -> None:
    token = _get_token()
    with GraphClient(token) as client:
        channels = teams.list_channels(client, args.team_id)

    if not channels:
        print("No channels found.")
        return

    print(f"Channels ({len(channels)}):\n")
    for ch in channels:
        print(f"  {ch.get('displayName', '?')}  (id: {ch.get('id', '?')})")


def cmd_teams_send(args: argparse.Namespace) -> None:
    token = _get_token()
    with GraphClient(token) as client:
        teams.send_channel_message(client, args.team_id, args.channel_id, args.message)
    print("Message sent.")


# ---------------------------------------------------------------------------
# Files commands
# ---------------------------------------------------------------------------

def _format_drive_item_cli(item: dict) -> str:
    """Format a driveItem for CLI output."""
    name = item.get("name", "?")
    item_id = item.get("id", "?")
    if "folder" in item:
        child_count = item["folder"].get("childCount", "?")
        return f"  {name}/  ({child_count} items)  [id: {item_id}]"
    mime = item.get("file", {}).get("mimeType", "")
    size = item.get("size", 0)
    if size < 1024:
        size_str = f"{size} B"
    elif size < 1024 * 1024:
        size_str = f"{size / 1024:.1f} KB"
    else:
        size_str = f"{size / (1024 * 1024):.1f} MB"
    return f"  {name}  ({mime}, {size_str})  [id: {item_id}]"


def cmd_files_list(args: argparse.Namespace) -> None:
    token = _get_token()
    with GraphClient(token) as client:
        items = files.list_drive_children(client, folder_path=args.path, top=args.top)

    if not items:
        print("No files found.")
        return

    loc = f'"{args.path}"' if args.path else "root"
    print(f"Files in {loc} ({len(items)}):\n")
    for item in items:
        print(_format_drive_item_cli(item))


def cmd_files_info(args: argparse.Namespace) -> None:
    token = _get_token()
    with GraphClient(token) as client:
        item = files.get_drive_item(client, args.item_id)

    name = item.get("name", "?")
    print(f"Name: {name}")
    if "folder" in item:
        print(f"Type: Folder ({item['folder'].get('childCount', '?')} items)")
    else:
        print(f"Type: {item.get('file', {}).get('mimeType', '?')}")
        print(f"Size: {item.get('size', 0)} bytes")
    print(f"Modified: {item.get('lastModifiedDateTime', '?')}")
    print(f"ID: {item.get('id', '?')}")
    web_url = item.get("webUrl", "")
    if web_url:
        print(f"URL: {web_url}")


def cmd_files_read(args: argparse.Namespace) -> None:
    token = _get_token()
    with GraphClient(token) as client:
        item, content = files.get_drive_item_content(client, args.item_id)

    name = item.get("name", "?")
    if content is not None:
        print(f"--- {name} ---\n")
        print(content)
    else:
        print(f"{name}: binary or too large to display.")
        web_url = item.get("webUrl", "")
        if web_url:
            print(f"Open in browser: {web_url}")


def cmd_files_search(args: argparse.Namespace) -> None:
    token = _get_token()
    with GraphClient(token) as client:
        results = files.search_files_unified(client, query=args.query, top=args.top)

    if not results:
        print("No files found.")
        return

    print(f"Search results ({len(results)}):\n")
    for i, item in enumerate(results, 1):
        print(f"[{i}]")
        print(f"  Name: {item.get('name', '?')}")
        print(f"  ID: {item.get('id', '?')}")
        summary = item.get("_searchSummary", "")
        if summary:
            print(f"  Summary: {summary}")
        web_url = item.get("webUrl", "")
        if web_url:
            print(f"  URL: {web_url}")
        print()


# ---------------------------------------------------------------------------
# Sites commands
# ---------------------------------------------------------------------------

def cmd_sites_list(args: argparse.Namespace) -> None:
    token = _get_token()
    with GraphClient(token) as client:
        sites = files.list_sites(client, query=args.query, top=args.top)

    if not sites:
        print("No sites found.")
        return

    print(f"SharePoint sites ({len(sites)}):\n")
    for site in sites:
        name = site.get("displayName", site.get("name", "?"))
        print(f"  {name}  (id: {site.get('id', '?')})")
        web_url = site.get("webUrl", "")
        if web_url:
            print(f"    {web_url}")


def cmd_sites_files(args: argparse.Namespace) -> None:
    token = _get_token()
    with GraphClient(token) as client:
        items = files.list_drive_children(client, folder_path=args.path, site_id=args.site_id, top=args.top)

    if not items:
        print("No files found.")
        return

    loc = f'"{args.path}"' if args.path else "root"
    print(f"Files in {loc} ({len(items)}):\n")
    for item in items:
        print(_format_drive_item_cli(item))


def main() -> None:
    parser = argparse.ArgumentParser(description="Microsoft Graph CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    # whoami
    p_whoami = sub.add_parser("whoami", help="Show authenticated user profile")
    p_whoami.set_defaults(func=cmd_whoami)

    # list
    p_list = sub.add_parser("list", help="List recent emails")
    p_list.add_argument("--folder", default="inbox")
    p_list.add_argument("--top", type=int, default=10)
    p_list.set_defaults(func=cmd_list)

    # read
    p_read = sub.add_parser("read", help="Read a single email")
    p_read.add_argument("message_id")
    p_read.set_defaults(func=cmd_read)

    # send
    p_send = sub.add_parser("send", help="Send an email")
    p_send.add_argument("to")
    p_send.add_argument("subject")
    p_send.add_argument("body")
    p_send.add_argument("--from", dest="from_address", default=None,
                         help="Sender email address (alias to send from)")
    p_send.set_defaults(func=cmd_send)

    # search
    p_search = sub.add_parser("search", help="Search emails")
    p_search.add_argument("query")
    p_search.add_argument("--top", type=int, default=10)
    p_search.set_defaults(func=cmd_search)

    # teams
    p_teams = sub.add_parser("teams", help="Teams operations")
    teams_sub = p_teams.add_subparsers(dest="teams_command", required=True)

    p_tlist = teams_sub.add_parser("list", help="List joined teams")
    p_tlist.set_defaults(func=cmd_teams_list)

    p_tch = teams_sub.add_parser("channels", help="List channels in a team")
    p_tch.add_argument("team_id")
    p_tch.set_defaults(func=cmd_teams_channels)

    p_tsend = teams_sub.add_parser("send", help="Send a Teams channel message")
    p_tsend.add_argument("team_id")
    p_tsend.add_argument("channel_id")
    p_tsend.add_argument("message")
    p_tsend.set_defaults(func=cmd_teams_send)

    # files
    p_files = sub.add_parser("files", help="OneDrive file operations")
    files_sub = p_files.add_subparsers(dest="files_command", required=True)

    p_flist = files_sub.add_parser("list", help="List files in OneDrive")
    p_flist.add_argument("--path", default="", help="Folder path (e.g., Documents/Reports)")
    p_flist.add_argument("--top", type=int, default=20)
    p_flist.set_defaults(func=cmd_files_list)

    p_finfo = files_sub.add_parser("info", help="Get file/folder metadata")
    p_finfo.add_argument("item_id")
    p_finfo.set_defaults(func=cmd_files_info)

    p_fread = files_sub.add_parser("read", help="Read a text file's content")
    p_fread.add_argument("item_id")
    p_fread.set_defaults(func=cmd_files_read)

    p_fsearch = files_sub.add_parser("search", help="Search files across OneDrive and SharePoint")
    p_fsearch.add_argument("query")
    p_fsearch.add_argument("--top", type=int, default=10)
    p_fsearch.set_defaults(func=cmd_files_search)

    # sites
    p_sites = sub.add_parser("sites", help="SharePoint site operations")
    sites_sub = p_sites.add_subparsers(dest="sites_command", required=True)

    p_slist = sites_sub.add_parser("list", help="List or search SharePoint sites")
    p_slist.add_argument("--query", default="", help="Search query (empty = followed sites)")
    p_slist.add_argument("--top", type=int, default=10)
    p_slist.set_defaults(func=cmd_sites_list)

    p_sfiles = sites_sub.add_parser("files", help="List files in a SharePoint site")
    p_sfiles.add_argument("site_id")
    p_sfiles.add_argument("--path", default="", help="Folder path within the document library")
    p_sfiles.add_argument("--top", type=int, default=20)
    p_sfiles.set_defaults(func=cmd_sites_files)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
