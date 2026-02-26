#!/usr/bin/env python3
"""
Atlassian CLI -- interact with Jira & Confluence using OAuth 2.0 authorization code flow.

Atlassian doesn't support device code flow, so we use authorization code flow
with a local HTTP server to catch the redirect (same approach as many OAuth CLIs).

Setup:
    1. Create an OAuth 2.0 app at https://developer.atlassian.com/console/myapps/
    2. Add callback URL: http://localhost:8789/callback
    3. Add scopes: read:jira-work, write:jira-work, read:confluence-content.all,
       write:confluence-content, read:me, offline_access
    4. Set env vars:
       export ATLASSIAN_CLIENT_ID=<your-client-id>
       export ATLASSIAN_CLIENT_SECRET=<your-client-secret>

Usage:
    atlassian-cli jira projects
    atlassian-cli jira search "project = PROJ AND status = Open"
    atlassian-cli jira count "project = PROJ"
    atlassian-cli jira get PROJ-123
    atlassian-cli jira create PROJ "Fix the login bug" --type Bug --priority High
    atlassian-cli jira comment PROJ-123 "Working on this now"
    atlassian-cli jira transition PROJ-123 "In Progress"

    atlassian-cli confluence spaces
    atlassian-cli confluence search 'type = page AND text ~ "release"'
    atlassian-cli confluence get 12345

    atlassian-cli user me

    atlassian-cli logout  # Clear cached tokens
"""

import argparse
import hashlib
import json
import os
import secrets
import sys
import threading
import time
import webbrowser
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlencode, urlparse, parse_qs

import httpx

from atlassian.atlassian_client import AtlassianClient, AtlassianError
from atlassian import jira as jira_ops
from atlassian import confluence as confluence_ops
from atlassian import user as user_ops

TOKEN_CACHE_PATH = Path.home() / ".atlassian_mcp_tokens.json"

CALLBACK_PORT = 8789
CALLBACK_PATH = "/callback"
REDIRECT_URI = f"http://localhost:{CALLBACK_PORT}{CALLBACK_PATH}"

# Atlassian OAuth 2.0 endpoints
AUTH_URL = "https://auth.atlassian.com/authorize"
TOKEN_URL = "https://auth.atlassian.com/oauth/token"  # nosec B105 — URL, not a password
RESOURCES_URL = "https://api.atlassian.com/oauth/token/accessible-resources"

# Scopes needed for Jira + Confluence + User
# These must match scopes configured in your Atlassian OAuth app's Permissions page.
# Classic scopes (coarse-grained):
#   read:jira-work, write:jira-work — Jira issue CRUD, search, projects
#   read:confluence-content.all, write:confluence-content — Confluence page CRUD, search
# Granular scopes (fine-grained):
#   read:jira-user — needed for /myself endpoint and user lookups in Jira
#   read:me — User Identity API (api.atlassian.com/me)
#   read:confluence-space.summary — needed for listing Confluence spaces
SCOPES = [
    "read:jira-work",
    "write:jira-work",
    "read:jira-user",
    "read:confluence-content.all",
    "write:confluence-content",
    "read:confluence-space.summary",
    "read:me",
    "offline_access",
]


# ---------------------------------------------------------------------------
# OAuth 2.0 Authorization Code Flow with PKCE
# ---------------------------------------------------------------------------

class _CallbackHandler(BaseHTTPRequestHandler):
    """HTTP handler that captures the OAuth callback."""

    auth_code = None
    state = None
    error = None

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path != CALLBACK_PATH:
            self.send_response(404)
            self.end_headers()
            return

        params = parse_qs(parsed.query)

        if "error" in params:
            _CallbackHandler.error = params["error"][0]
            body = f"<h2>Authentication failed</h2><p>{params.get('error_description', ['Unknown error'])[0]}</p>"
        elif "code" in params:
            _CallbackHandler.auth_code = params["code"][0]
            _CallbackHandler.state = params.get("state", [None])[0]
            body = "<h2>Authentication successful!</h2><p>You can close this tab and return to the terminal.</p>"
        else:
            _CallbackHandler.error = "no_code"
            body = "<h2>Authentication failed</h2><p>No authorization code received.</p>"

        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        self.wfile.write(f"<html><body>{body}</body></html>".encode())

    def log_message(self, format, *args):
        pass  # Suppress HTTP server log noise


def _generate_pkce():
    """Generate PKCE code_verifier and code_challenge."""
    verifier = secrets.token_urlsafe(64)
    challenge = hashlib.sha256(verifier.encode()).digest()
    import base64
    challenge_b64 = base64.urlsafe_b64encode(challenge).rstrip(b"=").decode()
    return verifier, challenge_b64


def _do_oauth_flow(client_id: str, client_secret: str) -> dict:
    """Run the full OAuth 2.0 authorization code flow with PKCE."""
    state = secrets.token_urlsafe(32)
    code_verifier, code_challenge = _generate_pkce()

    # Build authorization URL
    auth_params = {
        "audience": "api.atlassian.com",
        "client_id": client_id,
        "scope": " ".join(SCOPES),
        "redirect_uri": REDIRECT_URI,
        "state": state,
        "response_type": "code",
        "prompt": "consent",
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
    }
    auth_url = f"{AUTH_URL}?{urlencode(auth_params)}"

    # Start local callback server
    server = HTTPServer(("localhost", CALLBACK_PORT), _CallbackHandler)
    server_thread = threading.Thread(target=server.handle_request, daemon=True)
    server_thread.start()

    # Open browser
    print(f"\nOpening browser for Atlassian authentication...")
    print(f"If the browser doesn't open, visit:\n  {auth_url}\n")
    webbrowser.open(auth_url)

    print("Waiting for authentication...")

    # Wait for callback (up to 120 seconds)
    deadline = time.time() + 120
    while server_thread.is_alive() and time.time() < deadline:
        time.sleep(0.5)

    server.server_close()

    if _CallbackHandler.error:
        print(f"Authentication failed: {_CallbackHandler.error}", file=sys.stderr)
        sys.exit(1)

    if not _CallbackHandler.auth_code:
        print("Authentication timed out.", file=sys.stderr)
        sys.exit(1)

    if _CallbackHandler.state != state:
        print("Authentication failed: state mismatch (possible CSRF).", file=sys.stderr)
        sys.exit(1)

    # Exchange code for tokens
    with httpx.Client(timeout=30.0) as http:
        resp = http.post(
            TOKEN_URL,
            json={
                "grant_type": "authorization_code",
                "client_id": client_id,
                "client_secret": client_secret,
                "code": _CallbackHandler.auth_code,
                "redirect_uri": REDIRECT_URI,
                "code_verifier": code_verifier,
            },
        )
        if not resp.is_success:
            print(f"Token exchange failed: {resp.text}", file=sys.stderr)
            sys.exit(1)
        token_data = resp.json()

    # Reset handler state for next use
    _CallbackHandler.auth_code = None
    _CallbackHandler.state = None
    _CallbackHandler.error = None

    print("Authenticated successfully!\n")
    return token_data


def _get_accessible_resources(access_token: str) -> list:
    """Fetch the list of Atlassian cloud sites the user can access."""
    with httpx.Client(timeout=30.0) as http:
        resp = http.get(
            RESOURCES_URL,
            headers={"Authorization": f"Bearer {access_token}"},
        )
        resp.raise_for_status()
        return resp.json()


def _refresh_token(client_id: str, client_secret: str, refresh_token: str) -> dict:
    """Refresh an expired access token."""
    with httpx.Client(timeout=30.0) as http:
        resp = http.post(
            TOKEN_URL,
            json={
                "grant_type": "refresh_token",
                "client_id": client_id,
                "client_secret": client_secret,
                "refresh_token": refresh_token,
            },
        )
        if not resp.is_success:
            return None
        return resp.json()


def _save_cache(data: dict):
    """Save token data to cache file."""
    TOKEN_CACHE_PATH.write_text(json.dumps(data, indent=2))
    TOKEN_CACHE_PATH.chmod(0o600)


def _load_cache() -> dict | None:
    """Load token data from cache file."""
    if not TOKEN_CACHE_PATH.exists():
        return None
    try:
        return json.loads(TOKEN_CACHE_PATH.read_text())
    except (json.JSONDecodeError, OSError):
        return None


def _get_token_and_cloud_id() -> tuple[str, str]:
    """Get a valid access token and cloud_id, authenticating if needed."""
    client_id = os.environ.get("ATLASSIAN_CLIENT_ID", "")
    client_secret = os.environ.get("ATLASSIAN_CLIENT_SECRET", "")

    # Allow direct token override for testing
    direct_token = os.environ.get("ATLASSIAN_ACCESS_TOKEN", "")
    direct_cloud_id = os.environ.get("ATLASSIAN_CLOUD_ID", "")
    if direct_token and direct_cloud_id:
        return direct_token, direct_cloud_id

    if not client_id or not client_secret:
        print(
            "Error: ATLASSIAN_CLIENT_ID and ATLASSIAN_CLIENT_SECRET are required.\n"
            "\n"
            "Setup:\n"
            "  1. Create an OAuth 2.0 app at https://developer.atlassian.com/console/myapps/\n"
            "  2. Add callback URL: http://localhost:8789/callback\n"
            "  3. Set environment variables:\n"
            "     export ATLASSIAN_CLIENT_ID=<your-client-id>\n"
            "     export ATLASSIAN_CLIENT_SECRET=<your-client-secret>\n",
            file=sys.stderr,
        )
        sys.exit(1)

    # Try cached token
    cache = _load_cache()
    if cache:
        access_token = cache.get("access_token")
        cloud_id = cache.get("cloud_id")
        refresh_tok = cache.get("refresh_token")

        if access_token and cloud_id:
            # Quick validation — try a lightweight API call
            try:
                with AtlassianClient(access_token, cloud_id) as client:
                    user_ops.get_myself(client)
                return access_token, cloud_id
            except (AtlassianError, Exception):
                pass  # Token expired, try refresh

        # Try refresh
        if refresh_tok:
            token_data = _refresh_token(client_id, client_secret, refresh_tok)
            if token_data and "access_token" in token_data:
                access_token = token_data["access_token"]
                # Keep existing cloud_id, update tokens
                cache_data = {
                    "access_token": access_token,
                    "refresh_token": token_data.get("refresh_token", refresh_tok),
                    "cloud_id": cloud_id,
                }
                _save_cache(cache_data)
                print("Token refreshed.\n")
                return access_token, cloud_id

    # Full OAuth flow
    token_data = _do_oauth_flow(client_id, client_secret)
    access_token = token_data["access_token"]

    # Get accessible sites to find cloud_id
    resources = _get_accessible_resources(access_token)
    if not resources:
        print("Error: No accessible Atlassian sites found for your account.", file=sys.stderr)
        sys.exit(1)

    if len(resources) == 1:
        cloud_id = resources[0]["id"]
        site_name = resources[0].get("name", resources[0].get("url", "?"))
        print(f"Using site: {site_name} (cloud_id: {cloud_id})\n")
    else:
        print("Available Atlassian sites:\n")
        for i, r in enumerate(resources, 1):
            print(f"  [{i}] {r.get('name', '?')} ({r.get('url', '?')})")
            print(f"      Cloud ID: {r['id']}")
        print()
        choice = input(f"Select site (1-{len(resources)}): ").strip()
        try:
            idx = int(choice) - 1
            cloud_id = resources[idx]["id"]
        except (ValueError, IndexError):
            print("Invalid selection.", file=sys.stderr)
            sys.exit(1)

    # Cache everything
    cache_data = {
        "access_token": access_token,
        "refresh_token": token_data.get("refresh_token"),
        "cloud_id": cloud_id,
    }
    _save_cache(cache_data)

    return access_token, cloud_id


def _get_client() -> AtlassianClient:
    """Get an authenticated AtlassianClient."""
    token, cloud_id = _get_token_and_cloud_id()
    return AtlassianClient(token, cloud_id)


def _pp(data):
    """Pretty-print JSON data."""
    print(json.dumps(data, indent=2, default=str))


# ---------------------------------------------------------------------------
# Jira commands
# ---------------------------------------------------------------------------

def cmd_jira_projects(args):
    with _get_client() as client:
        projects = jira_ops.list_projects(client, max_results=args.max_results)
    if not projects:
        print("No projects found.")
        return
    print(f"Projects ({len(projects)}):\n")
    for p in projects:
        print(f"  {p.get('key', '?'):10s} {p.get('name', '?')} ({p.get('projectTypeKey', '?')})")


def cmd_jira_search(args):
    # Resolve field set
    if args.fields == "extended":
        field_str = jira_ops._SEARCH_FIELDS_EXTENDED
    elif args.fields:
        field_str = args.fields
    else:
        field_str = jira_ops._SEARCH_FIELDS_MINIMAL

    with _get_client() as client:
        # Count first
        count = jira_ops.count_issues(client, jql=args.jql)
        print(f"~{count} issue(s) match. Fetching...\n")

        # Fetch all or up to max_results
        cap = args.max_results if args.max_results > 0 else jira_ops._MAX_TOTAL_ISSUES
        issues = jira_ops.search_all_issues(
            client, jql=args.jql, fields=field_str, max_total=cap,
        )

    if not issues:
        print("No issues found.")
        return

    print(f"Issues ({len(issues)} of ~{count}):\n")
    for issue in issues:
        f = issue.get("fields", {})
        key = issue.get("key", "?")
        summary = f.get("summary", "?")
        status = f.get("status", {}).get("name", "?")

        extras = []
        if f.get("assignee"):
            extras.append(f.get("assignee", {}).get("displayName", "?"))
        if f.get("priority"):
            extras.append(f.get("priority", {}).get("name", "?"))

        extra_str = f"  ({', '.join(extras)})" if extras else ""
        print(f"  {key:12s} [{status:15s}] {summary}{extra_str}")

    if len(issues) < count:
        print(f"\n  (Showing {len(issues)} of ~{count}. Use --max-results or refine JQL.)")


def cmd_jira_count(args):
    with _get_client() as client:
        count = jira_ops.count_issues(client, jql=args.jql)
    print(f"Approximate count: {count}")


def cmd_jira_get(args):
    with _get_client() as client:
        issue = jira_ops.get_issue(client, args.issue_key)
    fields = issue.get("fields", {})
    print(f"\n{issue.get('key', '?')} — {fields.get('summary', '?')}")
    print(f"  Status: {fields.get('status', {}).get('name', '?')}")
    print(f"  Type: {fields.get('issuetype', {}).get('name', '?')}")
    priority = fields.get("priority")
    print(f"  Priority: {priority.get('name', '?') if priority else 'None'}")
    assignee = fields.get("assignee")
    print(f"  Assignee: {assignee.get('displayName', '?') if assignee else 'Unassigned'}")
    reporter = fields.get("reporter")
    print(f"  Reporter: {reporter.get('displayName', '?') if reporter else '?'}")
    print(f"  Created: {fields.get('created', '?')}")
    print(f"  Updated: {fields.get('updated', '?')}")
    labels = fields.get("labels", [])
    if labels:
        print(f"  Labels: {', '.join(labels)}")
    desc = issue.get("renderedFields", {}).get("description", "")
    if desc:
        truncated = desc[:500] + ("... (truncated)" if len(desc) > 500 else "")
        print(f"\n  Description:\n  {truncated}")


def cmd_jira_create(args):
    labels = [l.strip() for l in args.labels.split(",") if l.strip()] if args.labels else None
    with _get_client() as client:
        result = jira_ops.create_issue(
            client,
            project_key=args.project_key,
            summary=args.summary,
            issue_type=args.type,
            description=args.description or None,
            priority=args.priority or None,
            labels=labels,
        )
    print(f"Created: {result.get('key', '?')}")


def cmd_jira_update(args):
    kwargs = {}
    if args.summary:
        kwargs["summary"] = args.summary
    if args.description:
        kwargs["description"] = args.description
    if args.priority:
        kwargs["priority"] = args.priority
    if args.labels:
        kwargs["labels"] = [l.strip() for l in args.labels.split(",") if l.strip()]
    if args.assignee:
        kwargs["assignee_id"] = args.assignee
    if not kwargs:
        print("Nothing to update — provide at least one of --summary, --description, --priority, --labels, --assignee")
        return
    with _get_client() as client:
        jira_ops.update_issue(client, args.issue_key, **kwargs)
    print(f"Updated {args.issue_key}")


def cmd_jira_comment(args):
    with _get_client() as client:
        result = jira_ops.add_issue_comment(client, args.issue_key, args.body)
    print(f"Comment added (ID: {result.get('id', '?')})")


def cmd_jira_transition(args):
    with _get_client() as client:
        matched = jira_ops.transition_issue(client, args.issue_key, args.transition_name)
    print(f"Transitioned {args.issue_key} to '{matched}'")


# ---------------------------------------------------------------------------
# Confluence commands
# ---------------------------------------------------------------------------

def cmd_confluence_spaces(args):
    with _get_client() as client:
        spaces = confluence_ops.list_spaces(client, max_results=args.max_results)
    if not spaces:
        print("No spaces found.")
        return
    print(f"Spaces ({len(spaces)}):\n")
    for s in spaces:
        print(f"  {s.get('key', '?'):10s} {s.get('name', '?')} ({s.get('type', '?')})")


def cmd_confluence_search(args):
    with _get_client() as client:
        results = confluence_ops.search_content(client, query=args.query, max_results=args.max_results)
    if not results:
        print("No results found.")
        return
    print(f"Results ({len(results)}):\n")
    for r in results:
        content = r.get("content", {})
        title = content.get("title", r.get("title", "?"))
        ctype = content.get("type", "?")
        print(f"  [{ctype:8s}] {title}")


def cmd_confluence_get(args):
    with _get_client() as client:
        page = confluence_ops.get_page(client, args.page_id)
    print(f"\n{page.get('title', '?')}")
    print(f"  Page ID: {page.get('id', '?')}")
    print(f"  Space ID: {page.get('spaceId', '?')}")
    print(f"  Version: {page.get('version', {}).get('number', '?')}")
    print(f"  Status: {page.get('status', '?')}")
    body = page.get("body", {}).get("storage", {}).get("value", "")
    if body:
        print(f"\n  Content:\n  {body[:1000]}")


# ---------------------------------------------------------------------------
# User commands
# ---------------------------------------------------------------------------

def cmd_user_me(args):
    with _get_client() as client:
        user = user_ops.get_myself(client)
    print(f"\n{user.get('displayName', '?')}")
    print(f"  Account ID: {user.get('accountId', '?')}")
    print(f"  Email: {user.get('emailAddress', 'Not available')}")
    print(f"  Active: {user.get('active', '?')}")
    print(f"  Time Zone: {user.get('timeZone', '?')}")


# ---------------------------------------------------------------------------
# Logout
# ---------------------------------------------------------------------------

def cmd_logout(args):
    if TOKEN_CACHE_PATH.exists():
        TOKEN_CACHE_PATH.unlink()
        print("Logged out. Cached tokens removed.")
    else:
        print("No cached tokens found.")


# ---------------------------------------------------------------------------
# CLI setup
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Atlassian CLI — Jira & Confluence with OAuth 2.0 login"
    )
    subparsers = parser.add_subparsers(dest="service", required=True)

    # --- Jira ---
    jira_parser = subparsers.add_parser("jira", help="Jira operations")
    jira_sub = jira_parser.add_subparsers(dest="command", required=True)

    p = jira_sub.add_parser("projects", help="List projects")
    p.add_argument("--max-results", type=int, default=50)
    p.set_defaults(func=cmd_jira_projects)

    p = jira_sub.add_parser("search", help="Search issues with JQL")
    p.add_argument("jql", help="JQL query string")
    p.add_argument("--max-results", type=int, default=0,
                   help="Max issues to return (0 = all, default: all)")
    p.add_argument("--fields", default="",
                   help='Fields to include. "extended" for full set, or comma-separated list (default: minimal)')
    p.set_defaults(func=cmd_jira_search)

    p = jira_sub.add_parser("count", help="Count issues matching JQL")
    p.add_argument("jql", help="JQL query string")
    p.set_defaults(func=cmd_jira_count)

    p = jira_sub.add_parser("get", help="Get issue details")
    p.add_argument("issue_key", help="Issue key (e.g., PROJ-123)")
    p.set_defaults(func=cmd_jira_get)

    p = jira_sub.add_parser("create", help="Create an issue")
    p.add_argument("project_key", help="Project key (e.g., PROJ)")
    p.add_argument("summary", help="Issue summary")
    p.add_argument("--type", default="Task", help="Issue type (default: Task)")
    p.add_argument("--description", default="", help="Issue description")
    p.add_argument("--priority", default="", help="Priority name")
    p.add_argument("--labels", default="", help="Comma-separated labels")
    p.set_defaults(func=cmd_jira_create)

    p = jira_sub.add_parser("update", help="Update an issue")
    p.add_argument("issue_key", help="Issue key (e.g., PROJ-123)")
    p.add_argument("--summary", default="", help="New summary")
    p.add_argument("--description", default="", help="New description")
    p.add_argument("--priority", default="", help="New priority name")
    p.add_argument("--labels", default="", help="Comma-separated labels")
    p.add_argument("--assignee", default="", help="Assignee account ID")
    p.set_defaults(func=cmd_jira_update)

    p = jira_sub.add_parser("comment", help="Add comment to issue")
    p.add_argument("issue_key", help="Issue key (e.g., PROJ-123)")
    p.add_argument("body", help="Comment text")
    p.set_defaults(func=cmd_jira_comment)

    p = jira_sub.add_parser("transition", help="Transition an issue")
    p.add_argument("issue_key", help="Issue key (e.g., PROJ-123)")
    p.add_argument("transition_name", help="Transition name (e.g., 'In Progress')")
    p.set_defaults(func=cmd_jira_transition)

    # --- Confluence ---
    conf_parser = subparsers.add_parser("confluence", help="Confluence operations")
    conf_sub = conf_parser.add_subparsers(dest="command", required=True)

    p = conf_sub.add_parser("spaces", help="List spaces")
    p.add_argument("--max-results", type=int, default=25)
    p.set_defaults(func=cmd_confluence_spaces)

    p = conf_sub.add_parser("search", help="Search content with CQL")
    p.add_argument("query", help="CQL query string")
    p.add_argument("--max-results", type=int, default=25)
    p.set_defaults(func=cmd_confluence_search)

    p = conf_sub.add_parser("get", help="Get page details")
    p.add_argument("page_id", help="Page ID")
    p.set_defaults(func=cmd_confluence_get)

    # --- User ---
    user_parser = subparsers.add_parser("user", help="User operations")
    user_sub = user_parser.add_subparsers(dest="command", required=True)

    p = user_sub.add_parser("me", help="Get current user info")
    p.set_defaults(func=cmd_user_me)

    # --- Logout ---
    logout_parser = subparsers.add_parser("logout", help="Clear cached tokens")
    logout_parser.set_defaults(func=cmd_logout)

    args = parser.parse_args()

    try:
        args.func(args)
    except AtlassianError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except KeyboardInterrupt:
        print("\nCancelled.")


if __name__ == "__main__":
    main()
