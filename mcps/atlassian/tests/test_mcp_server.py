"""Tests for the FastMCP server using in-process client.

In-process FastMCP clients don't have HTTP request context, so we mock
get_atlassian_token() and get_cloud_id() directly.
"""

import httpx
import pytest
import respx
from unittest.mock import patch

from .conftest import (
    CLOUD_ID,
    JIRA_BASE,
    CONFLUENCE_V1_BASE,
    CONFLUENCE_V2_BASE,
    SAMPLE_PROJECTS_RESPONSE,
    SAMPLE_SEARCH_RESPONSE,
    SAMPLE_SEARCH_RESPONSE_PAGINATED,
    SAMPLE_COUNT_RESPONSE,
    SAMPLE_ISSUE,
    SAMPLE_COMMENTS_RESPONSE,
    SAMPLE_CREATED_ISSUE,
    SAMPLE_CREATED_COMMENT,
    SAMPLE_TRANSITIONS,
    SAMPLE_SPACES_RESPONSE,
    SAMPLE_CONFLUENCE_SEARCH_RESPONSE,
    SAMPLE_PAGE,
    SAMPLE_CREATED_PAGE,
    SAMPLE_UPDATED_PAGE,
    SAMPLE_USER,
    ATLASSIAN_ERROR_401,
    ATLASSIAN_ERROR_404,
    ATLASSIAN_ERROR_400_JIRA,
    ATLASSIAN_ERROR_429,
)


def _mock_auth(token: str = "test-token", cloud_id: str = CLOUD_ID):
    """Context manager to mock both auth functions."""
    return _MultiPatch(token, cloud_id)


class _MultiPatch:
    """Helper to patch both get_atlassian_token and get_cloud_id."""

    def __init__(self, token, cloud_id):
        self._token_patch = patch("atlassian_mcp.get_atlassian_token", return_value=token)
        self._cloud_patch = patch("atlassian_mcp.get_cloud_id", return_value=cloud_id)

    def __enter__(self):
        self._token_patch.start()
        self._cloud_patch.start()
        return self

    def __exit__(self, *args):
        self._token_patch.stop()
        self._cloud_patch.stop()


def _get_text(result) -> str:
    """Extract text from FastMCP CallToolResult."""
    return result.content[0].text


@pytest.fixture
def mcp_server():
    """Import and return the MCP server instance."""
    from atlassian_mcp import mcp
    return mcp


# ---------------------------------------------------------------------------
# Jira: list_projects
# ---------------------------------------------------------------------------

class TestMCPJiraProjects:
    @respx.mock
    async def test_list_projects(self, mcp_server):
        respx.get(f"{JIRA_BASE}/project/search").mock(
            return_value=httpx.Response(200, json=SAMPLE_PROJECTS_RESPONSE)
        )
        with _mock_auth():
            from fastmcp import Client
            async with Client(mcp_server) as client:
                result = await client.call_tool("list_projects", {})

        text = _get_text(result)
        assert "2 project(s)" in text
        assert "PROJ" in text
        assert "HR" in text

    @respx.mock
    async def test_list_projects_empty(self, mcp_server):
        respx.get(f"{JIRA_BASE}/project/search").mock(
            return_value=httpx.Response(200, json={"values": [], "total": 0})
        )
        with _mock_auth():
            from fastmcp import Client
            async with Client(mcp_server) as client:
                result = await client.call_tool("list_projects", {})

        text = _get_text(result)
        assert "No Jira projects found" in text


# ---------------------------------------------------------------------------
# Jira: search_issues
# ---------------------------------------------------------------------------

class TestMCPJiraSearch:
    @respx.mock
    async def test_search_issues(self, mcp_server):
        # count endpoint called first
        respx.post(f"{JIRA_BASE}/search/approximate-count").mock(
            return_value=httpx.Response(200, json={"count": 2})
        )
        respx.get(f"{JIRA_BASE}/search/jql").mock(
            return_value=httpx.Response(200, json=SAMPLE_SEARCH_RESPONSE)
        )
        with _mock_auth():
            from fastmcp import Client
            async with Client(mcp_server) as client:
                result = await client.call_tool("search_issues", {"jql": "project = PROJ"})

        text = _get_text(result)
        assert "2" in text
        assert "PROJ-42" in text
        assert "Fix login timeout bug" in text
        assert "In Progress" in text

    @respx.mock
    async def test_search_empty(self, mcp_server):
        respx.post(f"{JIRA_BASE}/search/approximate-count").mock(
            return_value=httpx.Response(200, json={"count": 0})
        )
        respx.get(f"{JIRA_BASE}/search/jql").mock(
            return_value=httpx.Response(200, json={"issues": [], "isLast": True})
        )
        with _mock_auth():
            from fastmcp import Client
            async with Client(mcp_server) as client:
                result = await client.call_tool("search_issues", {"jql": "project = NONE"})

        text = _get_text(result)
        assert "No issues found" in text

    @respx.mock
    async def test_search_paginated(self, mcp_server):
        """When count > fetched, output shows how many more exist."""
        respx.post(f"{JIRA_BASE}/search/approximate-count").mock(
            return_value=httpx.Response(200, json={"count": 500})
        )
        # First page returns 1 issue with isLast=False, second page returns isLast=True
        respx.get(f"{JIRA_BASE}/search/jql").mock(
            side_effect=[
                httpx.Response(200, json=SAMPLE_SEARCH_RESPONSE_PAGINATED),
                httpx.Response(200, json={"issues": [], "isLast": True}),
            ]
        )
        with _mock_auth():
            from fastmcp import Client
            async with Client(mcp_server) as client:
                result = await client.call_tool("search_issues", {"jql": "project = PROJ"})

        text = _get_text(result)
        assert "1" in text  # 1 issue fetched
        assert "500" in text  # of ~500 total

    @respx.mock
    async def test_search_with_extended_fields(self, mcp_server):
        """Extended fields parameter includes assignee and priority in output."""
        respx.post(f"{JIRA_BASE}/search/approximate-count").mock(
            return_value=httpx.Response(200, json={"count": 2})
        )
        respx.get(f"{JIRA_BASE}/search/jql").mock(
            return_value=httpx.Response(200, json=SAMPLE_SEARCH_RESPONSE)
        )
        with _mock_auth():
            from fastmcp import Client
            async with Client(mcp_server) as client:
                result = await client.call_tool(
                    "search_issues",
                    {"jql": "project = PROJ", "fields": "extended"},
                )

        text = _get_text(result)
        assert "PROJ-42" in text
        assert "Assignee:" in text or "Alice Smith" in text


# ---------------------------------------------------------------------------
# Jira: count_issues
# ---------------------------------------------------------------------------

class TestMCPJiraCount:
    @respx.mock
    async def test_count_issues(self, mcp_server):
        respx.post(f"{JIRA_BASE}/search/approximate-count").mock(
            return_value=httpx.Response(200, json=SAMPLE_COUNT_RESPONSE)
        )
        with _mock_auth():
            from fastmcp import Client
            async with Client(mcp_server) as client:
                result = await client.call_tool("count_issues", {"jql": "project = PROJ"})

        text = _get_text(result)
        assert "42" in text


# ---------------------------------------------------------------------------
# Jira: get_issue
# ---------------------------------------------------------------------------

class TestMCPJiraGetIssue:
    @respx.mock
    async def test_get_issue(self, mcp_server):
        respx.get(f"{JIRA_BASE}/issue/PROJ-42").mock(
            return_value=httpx.Response(200, json=SAMPLE_ISSUE)
        )
        respx.get(f"{JIRA_BASE}/issue/PROJ-42/comment").mock(
            return_value=httpx.Response(200, json=SAMPLE_COMMENTS_RESPONSE)
        )
        with _mock_auth():
            from fastmcp import Client
            async with Client(mcp_server) as client:
                result = await client.call_tool("get_issue", {"issue_key": "PROJ-42"})

        text = _get_text(result)
        assert "PROJ-42" in text
        assert "Fix login timeout bug" in text
        assert "In Progress" in text
        assert "Alice Smith" in text
        assert "Comments (2)" in text
        assert "I can reproduce" in text

    @respx.mock
    async def test_get_issue_comments_fail_gracefully(self, mcp_server):
        """Issue data returned even when comment fetch fails (M6)."""
        respx.get(f"{JIRA_BASE}/issue/PROJ-42").mock(
            return_value=httpx.Response(200, json=SAMPLE_ISSUE)
        )
        respx.get(f"{JIRA_BASE}/issue/PROJ-42/comment").mock(
            return_value=httpx.Response(403, json={
                "errorMessages": ["Forbidden"], "errors": {}
            })
        )
        with _mock_auth():
            from fastmcp import Client
            async with Client(mcp_server) as client:
                result = await client.call_tool("get_issue", {"issue_key": "PROJ-42"})

        text = _get_text(result)
        # Issue data should still be present
        assert "PROJ-42" in text
        assert "Fix login timeout bug" in text
        # No comments section
        assert "Comments" not in text


# ---------------------------------------------------------------------------
# Jira: create_issue
# ---------------------------------------------------------------------------

class TestMCPJiraCreateIssue:
    @respx.mock
    async def test_create_issue(self, mcp_server):
        respx.post(f"{JIRA_BASE}/issue").mock(
            return_value=httpx.Response(201, json=SAMPLE_CREATED_ISSUE)
        )
        with _mock_auth():
            from fastmcp import Client
            async with Client(mcp_server) as client:
                result = await client.call_tool(
                    "create_issue",
                    {"project_key": "PROJ", "summary": "New bug report"},
                )

        text = _get_text(result)
        assert "PROJ-100" in text
        assert "created" in text.lower()


# ---------------------------------------------------------------------------
# Jira: update_issue
# ---------------------------------------------------------------------------

class TestMCPJiraUpdateIssue:
    @respx.mock
    async def test_update_issue(self, mcp_server):
        respx.put(f"{JIRA_BASE}/issue/PROJ-42").mock(
            return_value=httpx.Response(204)
        )
        with _mock_auth():
            from fastmcp import Client
            async with Client(mcp_server) as client:
                result = await client.call_tool(
                    "update_issue",
                    {"issue_key": "PROJ-42", "summary": "Updated title"},
                )

        text = _get_text(result)
        assert "PROJ-42" in text
        assert "updated" in text.lower()


# ---------------------------------------------------------------------------
# Jira: add_issue_comment
# ---------------------------------------------------------------------------

class TestMCPJiraComment:
    @respx.mock
    async def test_add_comment(self, mcp_server):
        respx.post(f"{JIRA_BASE}/issue/PROJ-42/comment").mock(
            return_value=httpx.Response(201, json=SAMPLE_CREATED_COMMENT)
        )
        with _mock_auth():
            from fastmcp import Client
            async with Client(mcp_server) as client:
                result = await client.call_tool(
                    "add_issue_comment",
                    {"issue_key": "PROJ-42", "body": "Great work!"},
                )

        text = _get_text(result)
        assert "Comment added" in text
        assert "PROJ-42" in text


# ---------------------------------------------------------------------------
# Jira: transition_issue
# ---------------------------------------------------------------------------

class TestMCPJiraTransition:
    @respx.mock
    async def test_transition_issue(self, mcp_server):
        respx.get(f"{JIRA_BASE}/issue/PROJ-42/transitions").mock(
            return_value=httpx.Response(200, json=SAMPLE_TRANSITIONS)
        )
        respx.post(f"{JIRA_BASE}/issue/PROJ-42/transitions").mock(
            return_value=httpx.Response(204)
        )
        with _mock_auth():
            from fastmcp import Client
            async with Client(mcp_server) as client:
                result = await client.call_tool(
                    "transition_issue",
                    {"issue_key": "PROJ-42", "transition_name": "Done"},
                )

        text = _get_text(result)
        assert "PROJ-42" in text
        assert "Done" in text
        assert "transitioned" in text.lower()

    @respx.mock
    async def test_transition_invalid(self, mcp_server):
        respx.get(f"{JIRA_BASE}/issue/PROJ-42/transitions").mock(
            return_value=httpx.Response(200, json=SAMPLE_TRANSITIONS)
        )
        with _mock_auth():
            from fastmcp import Client
            async with Client(mcp_server) as client:
                result = await client.call_tool(
                    "transition_issue",
                    {"issue_key": "PROJ-42", "transition_name": "Invalid"},
                )

        text = _get_text(result)
        assert "not available" in text.lower() or "rejected" in text.lower()


# ---------------------------------------------------------------------------
# Confluence: list_spaces
# ---------------------------------------------------------------------------

class TestMCPConfluenceSpaces:
    @respx.mock
    async def test_list_spaces(self, mcp_server):
        respx.get(f"{CONFLUENCE_V2_BASE}/spaces").mock(
            return_value=httpx.Response(200, json=SAMPLE_SPACES_RESPONSE)
        )
        with _mock_auth():
            from fastmcp import Client
            async with Client(mcp_server) as client:
                result = await client.call_tool("list_spaces", {})

        text = _get_text(result)
        assert "2 space(s)" in text
        assert "DEV" in text
        assert "HR" in text

    @respx.mock
    async def test_list_spaces_empty(self, mcp_server):
        respx.get(f"{CONFLUENCE_V2_BASE}/spaces").mock(
            return_value=httpx.Response(200, json={"results": []})
        )
        with _mock_auth():
            from fastmcp import Client
            async with Client(mcp_server) as client:
                result = await client.call_tool("list_spaces", {})

        text = _get_text(result)
        assert "No Confluence spaces found" in text


# ---------------------------------------------------------------------------
# Confluence: search_content
# ---------------------------------------------------------------------------

class TestMCPConfluenceSearch:
    @respx.mock
    async def test_search_content(self, mcp_server):
        respx.get(f"{CONFLUENCE_V1_BASE}/search").mock(
            return_value=httpx.Response(200, json=SAMPLE_CONFLUENCE_SEARCH_RESPONSE)
        )
        with _mock_auth():
            from fastmcp import Client
            async with Client(mcp_server) as client:
                result = await client.call_tool(
                    "search_content",
                    {"query": 'type = page AND text ~ "architecture"'},
                )

        text = _get_text(result)
        assert "2 result(s)" in text
        assert "Architecture Overview" in text
        assert "Q4 Release Notes" in text

    @respx.mock
    async def test_search_empty(self, mcp_server):
        respx.get(f"{CONFLUENCE_V1_BASE}/search").mock(
            return_value=httpx.Response(200, json={"results": []})
        )
        with _mock_auth():
            from fastmcp import Client
            async with Client(mcp_server) as client:
                result = await client.call_tool("search_content", {"query": "nonexistent"})

        text = _get_text(result)
        assert "No content found" in text


# ---------------------------------------------------------------------------
# Confluence: get_page
# ---------------------------------------------------------------------------

class TestMCPConfluenceGetPage:
    @respx.mock
    async def test_get_page(self, mcp_server):
        respx.get(f"{CONFLUENCE_V2_BASE}/pages/12345").mock(
            return_value=httpx.Response(200, json=SAMPLE_PAGE)
        )
        with _mock_auth():
            from fastmcp import Client
            async with Client(mcp_server) as client:
                result = await client.call_tool("get_page", {"page_id": "12345"})

        text = _get_text(result)
        assert "Architecture Overview" in text
        assert "microservices" in text


# ---------------------------------------------------------------------------
# Confluence: create_page
# ---------------------------------------------------------------------------

class TestMCPConfluenceCreatePage:
    @respx.mock
    async def test_create_page(self, mcp_server):
        respx.post(f"{CONFLUENCE_V2_BASE}/pages").mock(
            return_value=httpx.Response(200, json=SAMPLE_CREATED_PAGE)
        )
        with _mock_auth():
            from fastmcp import Client
            async with Client(mcp_server) as client:
                result = await client.call_tool(
                    "create_page",
                    {"space_id": "65536", "title": "New Page", "body": "<p>Hello</p>"},
                )

        text = _get_text(result)
        assert "New Page" in text
        assert "12400" in text


# ---------------------------------------------------------------------------
# Confluence: update_page
# ---------------------------------------------------------------------------

class TestMCPConfluenceUpdatePage:
    @respx.mock
    async def test_update_page(self, mcp_server):
        respx.put(f"{CONFLUENCE_V2_BASE}/pages/12345").mock(
            return_value=httpx.Response(200, json=SAMPLE_UPDATED_PAGE)
        )
        with _mock_auth():
            from fastmcp import Client
            async with Client(mcp_server) as client:
                result = await client.call_tool(
                    "update_page",
                    {
                        "page_id": "12345",
                        "title": "Architecture Overview v2",
                        "body": "<h1>Updated</h1>",
                        "version_number": 4,
                    },
                )

        text = _get_text(result)
        assert "Architecture Overview v2" in text
        assert "version 4" in text


# ---------------------------------------------------------------------------
# User: get_myself
# ---------------------------------------------------------------------------

class TestMCPUser:
    @respx.mock
    async def test_get_myself(self, mcp_server):
        respx.get(f"{JIRA_BASE}/myself").mock(
            return_value=httpx.Response(200, json=SAMPLE_USER)
        )
        with _mock_auth():
            from fastmcp import Client
            async with Client(mcp_server) as client:
                result = await client.call_tool("get_myself", {})

        text = _get_text(result)
        assert "Alice Smith" in text
        assert "alice@example.com" in text


# ---------------------------------------------------------------------------
# Auth error handling
# ---------------------------------------------------------------------------

class TestMCPAuth:
    async def test_missing_token_raises_error(self, mcp_server):
        from fastmcp import Client
        from fastmcp.exceptions import ToolError

        with patch("atlassian_mcp.get_atlassian_token", side_effect=PermissionError("Authorization required.")):
            with patch("atlassian_mcp.get_cloud_id", return_value=CLOUD_ID):
                async with Client(mcp_server) as client:
                    with pytest.raises(ToolError, match="Authorization required"):
                        await client.call_tool("list_projects", {})

    async def test_missing_cloud_id_raises_error(self, mcp_server):
        from fastmcp import Client
        from fastmcp.exceptions import ToolError

        with patch("atlassian_mcp.get_atlassian_token", return_value="token"):
            with patch("atlassian_mcp.get_cloud_id", side_effect=PermissionError("Cloud ID required.")):
                async with Client(mcp_server) as client:
                    with pytest.raises(ToolError, match="Cloud ID required"):
                        await client.call_tool("list_projects", {})


# ---------------------------------------------------------------------------
# API error handling
# ---------------------------------------------------------------------------

class TestMCPErrorHandling:
    @respx.mock
    async def test_401_friendly_message(self, mcp_server):
        respx.get(f"{JIRA_BASE}/project/search").mock(
            return_value=httpx.Response(401, json=ATLASSIAN_ERROR_401)
        )
        with _mock_auth():
            from fastmcp import Client
            async with Client(mcp_server) as client:
                result = await client.call_tool("list_projects", {})

        text = _get_text(result)
        assert "authentication failed" in text.lower()
        assert "reconnect" in text.lower()

    @respx.mock
    async def test_404_friendly_message(self, mcp_server):
        respx.get(f"{JIRA_BASE}/issue/BAD-999").mock(
            return_value=httpx.Response(404, json=ATLASSIAN_ERROR_404)
        )
        respx.get(f"{JIRA_BASE}/issue/BAD-999/comment").mock(
            return_value=httpx.Response(404, json=ATLASSIAN_ERROR_404)
        )
        with _mock_auth():
            from fastmcp import Client
            async with Client(mcp_server) as client:
                result = await client.call_tool("get_issue", {"issue_key": "BAD-999"})

        text = _get_text(result)
        assert "not found" in text.lower()

    @respx.mock
    async def test_400_shows_validation_errors(self, mcp_server):
        respx.post(f"{JIRA_BASE}/issue").mock(
            return_value=httpx.Response(400, json=ATLASSIAN_ERROR_400_JIRA)
        )
        with _mock_auth():
            from fastmcp import Client
            async with Client(mcp_server) as client:
                result = await client.call_tool(
                    "create_issue",
                    {"project_key": "BAD", "summary": ""},
                )

        text = _get_text(result)
        assert "rejected" in text.lower()

    @respx.mock
    async def test_429_rate_limit(self, mcp_server):
        respx.get(f"{JIRA_BASE}/project/search").mock(
            return_value=httpx.Response(
                429,
                json=ATLASSIAN_ERROR_429,
                headers={"retry-after": "60"},
            )
        )
        with _mock_auth():
            from fastmcp import Client
            async with Client(mcp_server) as client:
                result = await client.call_tool("list_projects", {})

        text = _get_text(result)
        assert "rate limit" in text.lower()
