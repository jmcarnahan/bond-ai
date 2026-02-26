#!/usr/bin/env python3
"""
Atlassian MCP Server for Bond AI.

Provides Jira, Confluence, and user tools that use the user's Atlassian OAuth
token and cloud ID, passed through by Bond AI's backend as HTTP headers:
  - Authorization: Bearer {token}
  - X-Atlassian-Cloud-Id: {cloud_id}

Run:
    fastmcp run atlassian_mcp.py --transport streamable-http --port 9001
"""

import logging
from typing import Optional

from fastmcp import FastMCP

from atlassian.auth import get_atlassian_token, get_cloud_id
from atlassian.atlassian_client import AsyncAtlassianClient, AtlassianError
from atlassian import jira as jira_ops
from atlassian import confluence as confluence_ops
from atlassian import user as user_ops

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

mcp = FastMCP("Atlassian MCP Server")


def _friendly_error(err: AtlassianError, context: str = "") -> str:
    """Convert an AtlassianError into a user-friendly message."""
    code = err.error_code

    if code == "Unauthorized":
        return (
            "Atlassian authentication failed. Your session may have expired.\n"
            "Please reconnect your Atlassian account in Settings -> Connections."
        )
    if code == "Forbidden":
        resource = context if context else "this resource"
        return (
            f"You don't have permission to access {resource}. "
            "Check your Atlassian permissions."
        )
    if code == "NotFound":
        resource = context if context else "The requested resource"
        return f"{resource} was not found. Check the identifier and your access permissions."
    if code == "RateLimited":
        return f"Rate limited by Atlassian. Please wait and try again.\n({err})"
    if code == "BadRequest" or code == "InvalidTransition":
        return f"Atlassian rejected the request: {err}"
    if code == "Conflict":
        return f"Conflict — the resource may have been modified. Please refresh and try again.\n({err})"
    return f"Atlassian API error: {err}"


def _get_client() -> tuple:
    """Extract token and cloud_id, return (token, cloud_id)."""
    return get_atlassian_token(), get_cloud_id()


# ---------------------------------------------------------------------------
# Jira tools
# ---------------------------------------------------------------------------

@mcp.tool()
async def list_projects(max_results: int = 50) -> str:
    """
    List accessible Jira projects.

    Args:
        max_results: Maximum number of projects to return (default: 50).
    """
    token, cloud_id = _get_client()
    try:
        async with AsyncAtlassianClient(token, cloud_id) as client:
            projects = await jira_ops.alist_projects(client, max_results=max_results)
    except AtlassianError as e:
        return _friendly_error(e)

    if not projects:
        return "No Jira projects found."

    lines = [f"Found {len(projects)} project(s):\n"]
    for p in projects:
        ptype = p.get("projectTypeKey", "?")
        lines.append(f"- **{p.get('key', '?')}** — {p.get('name', '?')} ({ptype})")
    return "\n".join(lines)


@mcp.tool()
async def search_issues(
    jql: str,
    fields: str = "",
    max_results: int = 0,
) -> str:
    """
    Search for Jira issues using JQL (Jira Query Language).

    Automatically fetches ALL matching issues in batches. Returns minimal
    fields (key, summary, status, type) by default to keep responses compact.

    Args:
        jql: JQL query string (e.g., "project = PROJ AND status = Open", "assignee = currentUser() ORDER BY updated DESC").
        fields: Comma-separated field names to include (default: minimal). Use "extended" for summary,status,issuetype,assignee,priority,created,updated,labels.
        max_results: Maximum issues to return. 0 (default) means fetch ALL matching issues.
    """
    token, cloud_id = _get_client()

    # Resolve field set
    if fields == "extended":
        field_str = jira_ops._SEARCH_FIELDS_EXTENDED
    elif fields:
        field_str = fields
    else:
        field_str = jira_ops._SEARCH_FIELDS_MINIMAL

    try:
        async with AsyncAtlassianClient(token, cloud_id) as client:
            # Get count first so we can report total
            count = await jira_ops.acount_issues(client, jql=jql)

            # Fetch all (or up to max_results)
            cap = max_results if max_results > 0 else jira_ops._MAX_TOTAL_ISSUES
            issues = await jira_ops.asearch_all_issues(
                client, jql=jql, fields=field_str, max_total=cap,
            )
    except AtlassianError as e:
        return _friendly_error(e)

    if not issues:
        return f"No issues found matching: `{jql}`"

    fetched = len(issues)
    header = f"Fetched **{fetched}** of ~{count} issue(s) matching `{jql}`:\n"
    lines = [header]

    for issue in issues:
        f = issue.get("fields", {})
        key = issue.get("key", "?")
        summary = f.get("summary", "?")
        status = f.get("status", {}).get("name", "?")
        issue_type = f.get("issuetype", {}).get("name", "")

        # Only include extra fields if they were requested and present
        extras = []
        if f.get("assignee"):
            extras.append(f"Assignee: {f['assignee'].get('displayName', '?')}")
        if f.get("priority"):
            extras.append(f"Priority: {f['priority'].get('name', '?')}")
        if f.get("labels"):
            extras.append(f"Labels: {', '.join(f['labels'])}")

        type_str = f" ({issue_type})" if issue_type else ""
        extra_str = f"  {' | '.join(extras)}" if extras else ""
        lines.append(f"- **{key}** {summary} [{status}]{type_str}{extra_str}")

    if fetched < count:
        lines.append(
            f"\n*Showing {fetched} of ~{count} total. "
            "Set max_results or refine your JQL to see more.*"
        )

    return "\n".join(lines)


@mcp.tool()
async def count_issues(jql: str) -> str:
    """
    Count the number of issues matching a JQL query without fetching issue data.
    Returns an approximate count that is very close to exact.

    Args:
        jql: JQL query string (e.g., "project = PROJ AND status = Open").
    """
    token, cloud_id = _get_client()
    try:
        async with AsyncAtlassianClient(token, cloud_id) as client:
            count = await jira_ops.acount_issues(client, jql=jql)
    except AtlassianError as e:
        return _friendly_error(e)

    return f"Approximately **{count}** issue(s) match `{jql}`."


@mcp.tool()
async def get_issue(issue_key: str) -> str:
    """
    Get full details of a Jira issue including comments.

    Args:
        issue_key: The issue key (e.g., "PROJ-123").
    """
    token, cloud_id = _get_client()
    try:
        async with AsyncAtlassianClient(token, cloud_id) as client:
            issue = await jira_ops.aget_issue(client, issue_key)
            try:
                comments = await jira_ops.aget_issue_comments(client, issue_key)
            except AtlassianError:
                comments = []  # Degrade gracefully — show issue without comments
    except AtlassianError as e:
        return _friendly_error(e, context=issue_key)

    fields = issue.get("fields", {})
    rendered = issue.get("renderedFields", {})

    status = fields.get("status", {}).get("name", "?")
    priority = fields.get("priority", {}).get("name", "None") if fields.get("priority") else "None"
    issue_type = fields.get("issuetype", {}).get("name", "?")
    assignee = fields.get("assignee")
    assignee_str = assignee.get("displayName", "Unassigned") if assignee else "Unassigned"
    reporter = fields.get("reporter")
    reporter_str = reporter.get("displayName", "?") if reporter else "?"
    labels = ", ".join(fields.get("labels", []))
    created = fields.get("created", "?")
    updated = fields.get("updated", "?")

    lines = [
        f"**{issue.get('key', '?')} — {fields.get('summary', '?')}**",
        f"**Status:** {status}",
        f"**Type:** {issue_type} | **Priority:** {priority}",
        f"**Assignee:** {assignee_str} | **Reporter:** {reporter_str}",
        f"**Created:** {created} | **Updated:** {updated}",
    ]
    if labels:
        lines.append(f"**Labels:** {labels}")

    # Description — prefer rendered HTML, fall back to plain
    description = rendered.get("description") or ""
    if not description:
        desc_field = fields.get("description")
        if desc_field and isinstance(desc_field, dict):
            # ADF format — extract text nodes
            description = _extract_adf_text(desc_field)
        elif desc_field:
            description = str(desc_field)

    if description:
        lines.append(f"\n---\n**Description:**\n{description}")
    else:
        lines.append("\n---\n*(No description)*")

    # Comments
    if comments:
        lines.append(f"\n---\n**Comments ({len(comments)}):**\n")
        for c in comments:
            author = c.get("author", {}).get("displayName", "?")
            created_at = c.get("created", "?")
            body = ""
            body_field = c.get("body")
            if body_field and isinstance(body_field, dict):
                body = _extract_adf_text(body_field)
            elif body_field:
                body = str(body_field)
            lines.append(f"**{author}** ({created_at}):\n{body}\n")

    return "\n".join(lines)


@mcp.tool()
async def create_issue(
    project_key: str,
    summary: str,
    issue_type: str = "Task",
    description: str = "",
    assignee_id: str = "",
    priority: str = "",
    labels: str = "",
) -> str:
    """
    Create a new Jira issue.

    Args:
        project_key: Project key (e.g., "PROJ").
        summary: Issue title/summary.
        issue_type: Issue type name (default: "Task"). Common types: Task, Bug, Story, Epic.
        description: Issue description in plain text (optional).
        assignee_id: Atlassian account ID to assign (optional). Use get_myself to find your ID.
        priority: Priority name (optional). Common values: Highest, High, Medium, Low, Lowest.
        labels: Comma-separated label names (optional).
    """
    token, cloud_id = _get_client()
    label_list = [l.strip() for l in labels.split(",") if l.strip()] if labels else None

    try:
        async with AsyncAtlassianClient(token, cloud_id) as client:
            result = await jira_ops.acreate_issue(
                client,
                project_key=project_key,
                summary=summary,
                issue_type=issue_type,
                description=description or None,
                assignee_id=assignee_id or None,
                priority=priority or None,
                labels=label_list,
            )
    except AtlassianError as e:
        return _friendly_error(e)

    key = result.get("key", "?")
    return f"Issue created: **{key}** — {summary}"


@mcp.tool()
async def update_issue(
    issue_key: str,
    summary: str = "",
    description: str = "",
    assignee_id: str = "",
    priority: str = "",
    labels: str = "",
) -> str:
    """
    Update an existing Jira issue.

    Args:
        issue_key: The issue key (e.g., "PROJ-123").
        summary: New summary (leave empty to keep current).
        description: New description in plain text (leave empty to keep current).
        assignee_id: New assignee account ID (leave empty to keep current).
        priority: New priority name (leave empty to keep current).
        labels: Comma-separated label names to set (leave empty to keep current).
    """
    token, cloud_id = _get_client()
    label_list = [l.strip() for l in labels.split(",") if l.strip()] if labels else None

    try:
        async with AsyncAtlassianClient(token, cloud_id) as client:
            await jira_ops.aupdate_issue(
                client,
                issue_key=issue_key,
                summary=summary or None,
                description=description or None,
                assignee_id=assignee_id or None,
                priority=priority or None,
                labels=label_list,
            )
    except AtlassianError as e:
        return _friendly_error(e, context=issue_key)

    return f"Issue **{issue_key}** updated successfully."


@mcp.tool()
async def add_issue_comment(issue_key: str, body: str) -> str:
    """
    Add a comment to a Jira issue.

    Args:
        issue_key: The issue key (e.g., "PROJ-123").
        body: Comment text.
    """
    token, cloud_id = _get_client()
    try:
        async with AsyncAtlassianClient(token, cloud_id) as client:
            result = await jira_ops.aadd_issue_comment(client, issue_key, body)
    except AtlassianError as e:
        return _friendly_error(e, context=issue_key)

    comment_id = result.get("id", "?") if result else "?"
    return f"Comment added to **{issue_key}** (comment ID: {comment_id})."


@mcp.tool()
async def transition_issue(issue_key: str, transition_name: str) -> str:
    """
    Move a Jira issue through its workflow (e.g., "In Progress", "Done", "To Do").

    Args:
        issue_key: The issue key (e.g., "PROJ-123").
        transition_name: The transition name (case-insensitive). If unsure, try common names like "In Progress", "Done", "To Do".
    """
    token, cloud_id = _get_client()
    try:
        async with AsyncAtlassianClient(token, cloud_id) as client:
            matched_name = await jira_ops.atransition_issue(client, issue_key, transition_name)
    except AtlassianError as e:
        return _friendly_error(e, context=issue_key)

    return f"Issue **{issue_key}** transitioned to **{matched_name}**."


# ---------------------------------------------------------------------------
# Confluence tools
# ---------------------------------------------------------------------------

@mcp.tool()
async def list_spaces(max_results: int = 25) -> str:
    """
    List accessible Confluence spaces.

    Args:
        max_results: Maximum number of spaces to return (default: 25).
    """
    token, cloud_id = _get_client()
    try:
        async with AsyncAtlassianClient(token, cloud_id) as client:
            spaces = await confluence_ops.alist_spaces(client, max_results=max_results)
    except AtlassianError as e:
        return _friendly_error(e)

    if not spaces:
        return "No Confluence spaces found."

    lines = [f"Found {len(spaces)} space(s):\n"]
    for s in spaces:
        stype = s.get("type", "?")
        status = s.get("status", "?")
        lines.append(f"- **{s.get('key', '?')}** — {s.get('name', '?')} ({stype}, {status})")
    return "\n".join(lines)


@mcp.tool()
async def search_content(query: str, max_results: int = 25) -> str:
    """
    Search Confluence pages and blogs using CQL (Confluence Query Language).

    Args:
        query: CQL query string (e.g., 'type = page AND text ~ "release notes"', 'space = DEV AND title ~ "architecture"').
        max_results: Maximum number of results (default: 25).
    """
    token, cloud_id = _get_client()
    try:
        async with AsyncAtlassianClient(token, cloud_id) as client:
            results = await confluence_ops.asearch_content(client, query=query, max_results=max_results)
    except AtlassianError as e:
        return _friendly_error(e)

    if not results:
        return f"No content found matching: `{query}`"

    lines = [f"Found {len(results)} result(s) for `{query}`:\n"]
    for r in results:
        content = r.get("content", {})
        title = content.get("title", r.get("title", "?"))
        content_type = content.get("type", r.get("type", "?"))
        space = content.get("space", {})
        space_name = space.get("name", "") if space else ""

        excerpt = r.get("excerpt", "")
        if len(excerpt) > 200:
            excerpt = excerpt[:200] + "..."

        space_str = f" in **{space_name}**" if space_name else ""
        lines.append(f"- **{title}** ({content_type}){space_str}\n  {excerpt}")

    return "\n\n".join(lines)


@mcp.tool()
async def get_page(page_id: str) -> str:
    """
    Get a Confluence page with its full content.

    Args:
        page_id: The page ID (numeric string).
    """
    token, cloud_id = _get_client()
    try:
        async with AsyncAtlassianClient(token, cloud_id) as client:
            page = await confluence_ops.aget_page(client, page_id)
    except AtlassianError as e:
        return _friendly_error(e, context=f"page {page_id}")

    title = page.get("title", "?")
    status = page.get("status", "?")
    version = page.get("version", {}).get("number", "?")
    space_id = page.get("spaceId", "?")
    created = page.get("createdAt", "?")

    body_content = ""
    body = page.get("body", {})
    if body:
        storage = body.get("storage", {})
        body_content = storage.get("value", "")

    lines = [
        f"**{title}**",
        f"**Page ID:** {page_id} | **Space ID:** {space_id}",
        f"**Status:** {status} | **Version:** {version}",
        f"**Created:** {created}",
    ]

    if body_content:
        lines.append(f"\n---\n{body_content}")
    else:
        lines.append("\n---\n*(No content)*")

    return "\n".join(lines)


@mcp.tool()
async def create_page(
    space_id: str,
    title: str,
    body: str,
    parent_id: str = "",
) -> str:
    """
    Create a new Confluence page.

    Args:
        space_id: The space ID to create the page in.
        title: Page title.
        body: Page body in Confluence storage format (XHTML). For simple text, wrap in <p>tags</p>.
        parent_id: Parent page ID to nest under (optional).
    """
    token, cloud_id = _get_client()
    try:
        async with AsyncAtlassianClient(token, cloud_id) as client:
            result = await confluence_ops.acreate_page(
                client,
                space_id=space_id,
                title=title,
                body=body,
                parent_id=parent_id or None,
            )
    except AtlassianError as e:
        return _friendly_error(e)

    page_id = result.get("id", "?")
    return f"Page created: **{title}** (ID: {page_id})"


@mcp.tool()
async def update_page(
    page_id: str,
    title: str,
    body: str,
    version_number: int,
) -> str:
    """
    Update an existing Confluence page.

    Args:
        page_id: The page ID to update.
        title: New page title.
        body: New page body in Confluence storage format (XHTML).
        version_number: New version number (must be current version + 1). Get current version from get_page.
    """
    token, cloud_id = _get_client()
    try:
        async with AsyncAtlassianClient(token, cloud_id) as client:
            result = await confluence_ops.aupdate_page(
                client,
                page_id=page_id,
                title=title,
                body=body,
                version_number=version_number,
            )
    except AtlassianError as e:
        return _friendly_error(e, context=f"page {page_id}")

    return f"Page **{title}** (ID: {page_id}) updated to version {version_number}."


# ---------------------------------------------------------------------------
# User tools
# ---------------------------------------------------------------------------

@mcp.tool()
async def get_myself() -> str:
    """Get information about the currently authenticated Atlassian user."""
    token, cloud_id = _get_client()
    try:
        async with AsyncAtlassianClient(token, cloud_id) as client:
            user = await user_ops.aget_myself(client)
    except AtlassianError as e:
        return _friendly_error(e)

    lines = [
        f"**{user.get('displayName', '?')}**",
        f"**Account ID:** {user.get('accountId', '?')}",
        f"**Email:** {user.get('emailAddress', 'Not available')}",
        f"**Active:** {user.get('active', '?')}",
        f"**Time Zone:** {user.get('timeZone', '?')}",
    ]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _extract_adf_text(adf: dict) -> str:
    """Recursively extract plain text from Atlassian Document Format."""
    if adf.get("type") == "text":
        return adf.get("text", "")

    children = adf.get("content", [])
    child_texts = [_extract_adf_text(c) for c in children]

    # Block-level elements (paragraph, heading, etc.) get newlines between them
    node_type = adf.get("type", "")
    if node_type in ("doc", "table", "tableRow", "bulletList", "orderedList"):
        return "\n".join(t for t in child_texts if t)

    # Block-level containers get a trailing newline
    if node_type in ("paragraph", "heading", "listItem", "blockquote",
                      "codeBlock", "tableCell", "tableHeader"):
        return "".join(child_texts)

    return "".join(child_texts)


if __name__ == "__main__":
    mcp.run()
