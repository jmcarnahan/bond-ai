"""Tests for the FastMCP server using in-process client.

In-process FastMCP clients don't have HTTP request context, so we mock
get_graph_token() directly instead of get_http_headers().
"""

import httpx
import pytest
import respx
from unittest.mock import patch

from ms_graph.graph_client import GRAPH_BASE_URL
from .conftest import (
    SAMPLE_USER_PROFILE,
    SAMPLE_MAILBOX_SETTINGS,
    SAMPLE_MESSAGE,
    SAMPLE_MESSAGE_2,
    SAMPLE_MESSAGES_RESPONSE,
    SAMPLE_TEAMS_RESPONSE,
    SAMPLE_CHANNELS_RESPONSE,
    SAMPLE_CHANNEL_MESSAGE,
    SAMPLE_CHANNEL_MESSAGE_USER,
    SAMPLE_CHANNEL_MESSAGE_BOT,
    SAMPLE_CHANNEL_MESSAGES_RESPONSE,
    SAMPLE_CHATS_RESPONSE,
    SAMPLE_CHAT_MESSAGES_RESPONSE,
    SAMPLE_CHAT_MESSAGE_SENT,
    SAMPLE_DRIVE_CHILDREN_RESPONSE,
    SAMPLE_DRIVE_ITEM_FILE,
    SAMPLE_DRIVE_ITEM_BINARY,
    SAMPLE_DRIVE_ITEM_LARGE_TEXT,
    SAMPLE_DRIVE_ITEM_FOLDER,
    SAMPLE_SEARCH_RESPONSE,
    SAMPLE_SEARCH_RESPONSE_EMPTY,
    SAMPLE_SITES_RESPONSE,
    GRAPH_ERROR_403,
    GRAPH_ERROR_404,
)


def _mock_token(token: str = "test-ms-token"):
    """Patch get_graph_token to return a test token."""
    return patch("ms_graph_mcp.get_graph_token", return_value=token)


def _get_text(result) -> str:
    """Extract text from FastMCP CallToolResult."""
    return result.content[0].text


@pytest.fixture
def mcp_server():
    """Import and return the MCP server instance."""
    from ms_graph_mcp import mcp
    return mcp


class TestMCPProfileTools:
    """Test user profile MCP tools via in-process FastMCP client."""

    @respx.mock
    async def test_get_user_profile_with_mailbox_address(self, mcp_server):
        respx.get(f"{GRAPH_BASE_URL}/me").mock(
            return_value=httpx.Response(200, json=SAMPLE_USER_PROFILE)
        )
        respx.get(f"{GRAPH_BASE_URL}/me/mailboxSettings").mock(
            return_value=httpx.Response(200, json=SAMPLE_MAILBOX_SETTINGS)
        )
        with _mock_token():
            from fastmcp import Client
            async with Client(mcp_server) as client:
                result = await client.call_tool("get_user_profile", {})

        text = _get_text(result)
        assert "John Carnahan" in text
        assert "jmcarny@gmail.com" in text
        assert "Mailbox Address" in text
        assert "jmcarny.sbel@outlook.com" in text

    @respx.mock
    async def test_get_user_profile_without_mailbox_scope(self, mcp_server):
        """When MailboxSettings.Read is not granted, profile still works without mailbox address."""
        respx.get(f"{GRAPH_BASE_URL}/me").mock(
            return_value=httpx.Response(200, json=SAMPLE_USER_PROFILE)
        )
        respx.get(f"{GRAPH_BASE_URL}/me/mailboxSettings").mock(
            return_value=httpx.Response(403, json={
                "error": {"code": "ErrorAccessDenied", "message": "Access denied"}
            })
        )
        with _mock_token():
            from fastmcp import Client
            async with Client(mcp_server) as client:
                result = await client.call_tool("get_user_profile", {})

        text = _get_text(result)
        assert "John Carnahan" in text
        assert "jmcarny@gmail.com" in text
        assert "Mailbox Address" not in text


class TestMCPEmailTools:
    """Test email MCP tools via in-process FastMCP client."""

    @respx.mock
    async def test_list_emails(self, mcp_server):
        respx.get(f"{GRAPH_BASE_URL}/me/mailFolders/inbox/messages").mock(
            return_value=httpx.Response(200, json=SAMPLE_MESSAGES_RESPONSE)
        )
        with _mock_token():
            from fastmcp import Client
            async with Client(mcp_server) as client:
                result = await client.call_tool("list_emails", {"top": 10})

        text = _get_text(result)
        assert "Weekly Report" in text
        assert "2 message(s)" in text

    @respx.mock
    async def test_read_email(self, mcp_server):
        msg_id = "AAMkAGI2TG93AAA="
        respx.get(f"{GRAPH_BASE_URL}/me/messages/{msg_id}").mock(
            return_value=httpx.Response(200, json=SAMPLE_MESSAGE)
        )
        with _mock_token():
            from fastmcp import Client
            async with Client(mcp_server) as client:
                result = await client.call_tool("read_email", {"message_id": msg_id})

        text = _get_text(result)
        assert "Weekly Report" in text
        assert "Alice Smith" in text
        assert "Here is the weekly report" in text

    @respx.mock
    async def test_send_email(self, mcp_server):
        route = respx.post(f"{GRAPH_BASE_URL}/me/sendMail").mock(
            return_value=httpx.Response(202)
        )
        with _mock_token():
            from fastmcp import Client
            async with Client(mcp_server) as client:
                result = await client.call_tool(
                    "send_email",
                    {"to": "alice@example.com", "subject": "Hi", "body": "Hello!"},
                )

        text = _get_text(result)
        assert "sent" in text.lower()
        assert route.called

    @respx.mock
    async def test_search_emails(self, mcp_server):
        respx.get(f"{GRAPH_BASE_URL}/me/messages").mock(
            return_value=httpx.Response(200, json={"value": [SAMPLE_MESSAGE]})
        )
        with _mock_token():
            from fastmcp import Client
            async with Client(mcp_server) as client:
                result = await client.call_tool("search_emails", {"query": "weekly"})

        text = _get_text(result)
        assert "1 result(s)" in text
        assert "Weekly Report" in text

    @respx.mock
    async def test_search_no_results(self, mcp_server):
        respx.get(f"{GRAPH_BASE_URL}/me/messages").mock(
            return_value=httpx.Response(200, json={"value": []})
        )
        with _mock_token():
            from fastmcp import Client
            async with Client(mcp_server) as client:
                result = await client.call_tool("search_emails", {"query": "nonexistent"})

        text = _get_text(result)
        assert "No messages found" in text

    @respx.mock
    async def test_list_emails_empty(self, mcp_server):
        respx.get(f"{GRAPH_BASE_URL}/me/mailFolders/inbox/messages").mock(
            return_value=httpx.Response(200, json={"value": []})
        )
        with _mock_token():
            from fastmcp import Client
            async with Client(mcp_server) as client:
                result = await client.call_tool("list_emails", {})

        text = _get_text(result)
        assert "No messages found" in text

    @respx.mock
    async def test_list_emails_custom_folder(self, mcp_server):
        respx.get(f"{GRAPH_BASE_URL}/me/mailFolders/sentitems/messages").mock(
            return_value=httpx.Response(200, json=SAMPLE_MESSAGES_RESPONSE)
        )
        with _mock_token():
            from fastmcp import Client
            async with Client(mcp_server) as client:
                result = await client.call_tool("list_emails", {"folder": "sentitems"})

        text = _get_text(result)
        assert "Weekly Report" in text

    @respx.mock
    async def test_read_email_html_body(self, mcp_server):
        respx.get(f"{GRAPH_BASE_URL}/me/messages/{SAMPLE_MESSAGE_2['id']}").mock(
            return_value=httpx.Response(200, json=SAMPLE_MESSAGE_2)
        )
        with _mock_token():
            from fastmcp import Client
            async with Client(mcp_server) as client:
                result = await client.call_tool("read_email", {"message_id": SAMPLE_MESSAGE_2["id"]})

        text = _get_text(result)
        assert "HTML content" in text
        assert "Charlie Brown" in text

    @respx.mock
    async def test_send_email_with_cc(self, mcp_server):
        route = respx.post(f"{GRAPH_BASE_URL}/me/sendMail").mock(
            return_value=httpx.Response(202)
        )
        with _mock_token():
            from fastmcp import Client
            async with Client(mcp_server) as client:
                result = await client.call_tool(
                    "send_email",
                    {"to": "alice@example.com", "subject": "Hi", "body": "Hello!", "cc": "bob@example.com"},
                )

        text = _get_text(result)
        assert "sent" in text.lower()
        assert "CC" in text
        import json
        body = json.loads(route.calls[0].request.content)
        assert len(body["message"]["ccRecipients"]) == 1
        assert body["message"]["ccRecipients"][0]["emailAddress"]["address"] == "bob@example.com"

    @respx.mock
    async def test_send_email_no_from_by_default(self, mcp_server):
        """Without from_address, no from field in payload (uses account default)."""
        route = respx.post(f"{GRAPH_BASE_URL}/me/sendMail").mock(
            return_value=httpx.Response(202)
        )
        with _mock_token():
            from fastmcp import Client
            async with Client(mcp_server) as client:
                result = await client.call_tool(
                    "send_email",
                    {"to": "alice@example.com", "subject": "Hi", "body": "Hello!"},
                )

        import json
        body = json.loads(route.calls[0].request.content)
        assert "from" not in body["message"]

    @respx.mock
    async def test_send_email_with_from_address(self, mcp_server):
        route = respx.post(f"{GRAPH_BASE_URL}/me/sendMail").mock(
            return_value=httpx.Response(202)
        )
        with _mock_token():
            from fastmcp import Client
            async with Client(mcp_server) as client:
                result = await client.call_tool(
                    "send_email",
                    {
                        "to": "alice@example.com",
                        "subject": "Hi",
                        "body": "Hello!",
                        "from_address": "jmcarny.sbel@outlook.com",
                    },
                )

        text = _get_text(result)
        assert "sent" in text.lower()
        import json
        body = json.loads(route.calls[0].request.content)
        assert body["message"]["from"]["emailAddress"]["address"] == "jmcarny.sbel@outlook.com"

    @respx.mock
    async def test_send_email_multiple_recipients(self, mcp_server):
        route = respx.post(f"{GRAPH_BASE_URL}/me/sendMail").mock(
            return_value=httpx.Response(202)
        )
        with _mock_token():
            from fastmcp import Client
            async with Client(mcp_server) as client:
                result = await client.call_tool(
                    "send_email",
                    {"to": "alice@example.com, bob@example.com", "subject": "Hi", "body": "Hello!"},
                )

        text = _get_text(result)
        assert "sent" in text.lower()
        import json
        body = json.loads(route.calls[0].request.content)
        assert len(body["message"]["toRecipients"]) == 2

    @respx.mock
    async def test_graph_error_propagates_from_email_tool(self, mcp_server):
        from fastmcp.exceptions import ToolError

        respx.get(f"{GRAPH_BASE_URL}/me/mailFolders/inbox/messages").mock(
            return_value=httpx.Response(401, json={"error": {"code": "InvalidAuthenticationToken", "message": "Token expired"}})
        )
        with _mock_token():
            from fastmcp import Client
            async with Client(mcp_server) as client:
                with pytest.raises(ToolError, match="InvalidAuthenticationToken"):
                    await client.call_tool("list_emails", {})


class TestMCPTeamsTools:
    """Test Teams MCP tools via in-process FastMCP client."""

    @respx.mock
    async def test_list_teams(self, mcp_server):
        respx.get(f"{GRAPH_BASE_URL}/me/joinedTeams").mock(
            return_value=httpx.Response(200, json=SAMPLE_TEAMS_RESPONSE)
        )
        with _mock_token():
            from fastmcp import Client
            async with Client(mcp_server) as client:
                result = await client.call_tool("list_teams", {})

        text = _get_text(result)
        assert "Engineering" in text
        assert "Marketing" in text

    @respx.mock
    async def test_list_team_channels(self, mcp_server):
        respx.get(f"{GRAPH_BASE_URL}/teams/team-id-001/channels").mock(
            return_value=httpx.Response(200, json=SAMPLE_CHANNELS_RESPONSE)
        )
        with _mock_token():
            from fastmcp import Client
            async with Client(mcp_server) as client:
                result = await client.call_tool(
                    "list_team_channels", {"team_id": "team-id-001"}
                )

        text = _get_text(result)
        assert "General" in text
        assert "Random" in text

    @respx.mock
    async def test_send_teams_message(self, mcp_server):
        respx.post(f"{GRAPH_BASE_URL}/teams/t1/channels/c1/messages").mock(
            return_value=httpx.Response(201, json=SAMPLE_CHANNEL_MESSAGE)
        )
        with _mock_token():
            from fastmcp import Client
            async with Client(mcp_server) as client:
                result = await client.call_tool(
                    "send_teams_message",
                    {"team_id": "t1", "channel_id": "c1", "message": "Hello!"},
                )

        text = _get_text(result)
        assert "sent" in text.lower()

    @respx.mock
    async def test_teams_not_available(self, mcp_server):
        respx.get(f"{GRAPH_BASE_URL}/me/joinedTeams").mock(
            return_value=httpx.Response(403, json=GRAPH_ERROR_403)
        )
        with _mock_token():
            from fastmcp import Client
            async with Client(mcp_server) as client:
                result = await client.call_tool("list_teams", {})

        text = _get_text(result)
        assert "not available" in text.lower()

    @respx.mock
    async def test_list_teams_empty(self, mcp_server):
        respx.get(f"{GRAPH_BASE_URL}/me/joinedTeams").mock(
            return_value=httpx.Response(200, json={"value": []})
        )
        with _mock_token():
            from fastmcp import Client
            async with Client(mcp_server) as client:
                result = await client.call_tool("list_teams", {})

        text = _get_text(result)
        assert "No teams found" in text

    @respx.mock
    async def test_list_team_channels_403(self, mcp_server):
        respx.get(f"{GRAPH_BASE_URL}/teams/t1/channels").mock(
            return_value=httpx.Response(403, json=GRAPH_ERROR_403)
        )
        with _mock_token():
            from fastmcp import Client
            async with Client(mcp_server) as client:
                result = await client.call_tool("list_team_channels", {"team_id": "t1"})

        text = _get_text(result)
        assert "not available" in text.lower()

    @respx.mock
    async def test_send_teams_message_403(self, mcp_server):
        respx.post(f"{GRAPH_BASE_URL}/teams/t1/channels/c1/messages").mock(
            return_value=httpx.Response(403, json=GRAPH_ERROR_403)
        )
        with _mock_token():
            from fastmcp import Client
            async with Client(mcp_server) as client:
                result = await client.call_tool(
                    "send_teams_message",
                    {"team_id": "t1", "channel_id": "c1", "message": "Hello!"},
                )

        text = _get_text(result)
        assert "not available" in text.lower()

    @respx.mock
    async def test_read_channel_messages(self, mcp_server):
        respx.get(f"{GRAPH_BASE_URL}/teams/t1/channels/c1/messages").mock(
            return_value=httpx.Response(200, json=SAMPLE_CHANNEL_MESSAGES_RESPONSE)
        )
        with _mock_token():
            from fastmcp import Client
            async with Client(mcp_server) as client:
                result = await client.call_tool(
                    "read_channel_messages",
                    {"team_id": "t1", "channel_id": "c1"},
                )

        text = _get_text(result)
        assert "Alice Smith" in text
        assert "Hello team!" in text
        assert "Power Automate" in text
        assert "Build completed successfully" in text

    @respx.mock
    async def test_read_channel_messages_empty(self, mcp_server):
        respx.get(f"{GRAPH_BASE_URL}/teams/t1/channels/c1/messages").mock(
            return_value=httpx.Response(200, json={"value": []})
        )
        with _mock_token():
            from fastmcp import Client
            async with Client(mcp_server) as client:
                result = await client.call_tool(
                    "read_channel_messages",
                    {"team_id": "t1", "channel_id": "c1"},
                )

        text = _get_text(result)
        assert "No messages" in text

    @respx.mock
    async def test_read_channel_messages_403(self, mcp_server):
        respx.get(f"{GRAPH_BASE_URL}/teams/t1/channels/c1/messages").mock(
            return_value=httpx.Response(403, json=GRAPH_ERROR_403)
        )
        with _mock_token():
            from fastmcp import Client
            async with Client(mcp_server) as client:
                result = await client.call_tool(
                    "read_channel_messages",
                    {"team_id": "t1", "channel_id": "c1"},
                )

        text = _get_text(result)
        assert "not available" in text.lower()

    @respx.mock
    async def test_list_chats(self, mcp_server):
        respx.get(f"{GRAPH_BASE_URL}/me/chats").mock(
            return_value=httpx.Response(200, json=SAMPLE_CHATS_RESPONSE)
        )
        with _mock_token():
            from fastmcp import Client
            async with Client(mcp_server) as client:
                result = await client.call_tool("list_chats", {})

        text = _get_text(result)
        assert "3 chat(s)" in text
        assert "oneOnOne" in text
        assert "Project Standup" in text
        assert "Sprint Review" in text

    @respx.mock
    async def test_list_chats_empty(self, mcp_server):
        respx.get(f"{GRAPH_BASE_URL}/me/chats").mock(
            return_value=httpx.Response(200, json={"value": []})
        )
        with _mock_token():
            from fastmcp import Client
            async with Client(mcp_server) as client:
                result = await client.call_tool("list_chats", {})

        text = _get_text(result)
        assert "No chats found" in text

    async def test_list_chats_invalid_type(self, mcp_server):
        # Should reject without hitting Graph API
        with _mock_token():
            from fastmcp import Client
            async with Client(mcp_server) as client:
                result = await client.call_tool("list_chats", {"chat_type": "bogus"})

        text = _get_text(result)
        assert "Invalid chat_type" in text

    @respx.mock
    async def test_list_chats_403(self, mcp_server):
        respx.get(f"{GRAPH_BASE_URL}/me/chats").mock(
            return_value=httpx.Response(403, json=GRAPH_ERROR_403)
        )
        with _mock_token():
            from fastmcp import Client
            async with Client(mcp_server) as client:
                result = await client.call_tool("list_chats", {})

        text = _get_text(result)
        assert "not available" in text.lower()

    @respx.mock
    async def test_read_chat_messages(self, mcp_server):
        respx.get(f"{GRAPH_BASE_URL}/me/chats/chat-1/messages").mock(
            return_value=httpx.Response(200, json=SAMPLE_CHAT_MESSAGES_RESPONSE)
        )
        with _mock_token():
            from fastmcp import Client
            async with Client(mcp_server) as client:
                result = await client.call_tool(
                    "read_chat_messages", {"chat_id": "chat-1"},
                )

        text = _get_text(result)
        assert "Alice Smith" in text
        assert "Hello team!" in text

    @respx.mock
    async def test_read_chat_messages_empty(self, mcp_server):
        respx.get(f"{GRAPH_BASE_URL}/me/chats/chat-1/messages").mock(
            return_value=httpx.Response(200, json={"value": []})
        )
        with _mock_token():
            from fastmcp import Client
            async with Client(mcp_server) as client:
                result = await client.call_tool(
                    "read_chat_messages", {"chat_id": "chat-1"},
                )

        text = _get_text(result)
        assert "No messages" in text

    @respx.mock
    async def test_read_chat_messages_403(self, mcp_server):
        respx.get(f"{GRAPH_BASE_URL}/me/chats/c1/messages").mock(
            return_value=httpx.Response(403, json=GRAPH_ERROR_403)
        )
        with _mock_token():
            from fastmcp import Client
            async with Client(mcp_server) as client:
                result = await client.call_tool(
                    "read_chat_messages", {"chat_id": "c1"},
                )

        text = _get_text(result)
        assert "not available" in text.lower()

    @respx.mock
    async def test_send_chat_message(self, mcp_server):
        respx.post(f"{GRAPH_BASE_URL}/me/chats/chat-1/messages").mock(
            return_value=httpx.Response(201, json=SAMPLE_CHAT_MESSAGE_SENT)
        )
        with _mock_token():
            from fastmcp import Client
            async with Client(mcp_server) as client:
                result = await client.call_tool(
                    "send_chat_message",
                    {"chat_id": "chat-1", "message": "Hello!"},
                )

        text = _get_text(result)
        assert "sent" in text.lower()

    @respx.mock
    async def test_send_chat_message_403(self, mcp_server):
        respx.post(f"{GRAPH_BASE_URL}/me/chats/c1/messages").mock(
            return_value=httpx.Response(403, json=GRAPH_ERROR_403)
        )
        with _mock_token():
            from fastmcp import Client
            async with Client(mcp_server) as client:
                result = await client.call_tool(
                    "send_chat_message",
                    {"chat_id": "c1", "message": "Hello!"},
                )

        text = _get_text(result)
        assert "not available" in text.lower()

    @respx.mock
    async def test_get_teams_activity(self, mcp_server):
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc)
        recent_ts = now.isoformat()

        respx.get(f"{GRAPH_BASE_URL}/me/joinedTeams").mock(
            return_value=httpx.Response(200, json={"value": [
                {"id": "t1", "displayName": "TestTeam"}
            ]})
        )
        respx.get(f"{GRAPH_BASE_URL}/me/chats").mock(
            return_value=httpx.Response(200, json={"value": [
                {
                    "id": "chat-1", "chatType": "oneOnOne", "topic": None,
                    "members": [{"displayName": "Alice"}],
                    "lastMessagePreview": {
                        "createdDateTime": recent_ts,
                        "body": {"content": "Hey!"},
                        "from": {"user": {"displayName": "Alice"}},
                    },
                }
            ]})
        )
        respx.get(f"{GRAPH_BASE_URL}/teams/t1/channels").mock(
            return_value=httpx.Response(200, json={"value": [
                {"id": "c1", "displayName": "General"}
            ]})
        )
        respx.get(f"{GRAPH_BASE_URL}/teams/t1/channels/c1/messages").mock(
            return_value=httpx.Response(200, json={"value": [
                {
                    "id": "m1", "createdDateTime": recent_ts,
                    "from": {"user": {"displayName": "Bob"}, "application": None},
                    "body": {"contentType": "text", "content": "Update"},
                    "attachments": [],
                }
            ]})
        )

        with _mock_token():
            from fastmcp import Client
            async with Client(mcp_server) as client:
                result = await client.call_tool("get_teams_activity", {"hours": 24})

        text = _get_text(result)
        assert "Activity in the last 24 hours" in text
        assert "source,source_name,sender,timestamp,preview" in text
        assert "channel" in text
        assert "chat" in text

    @respx.mock
    async def test_get_teams_activity_empty(self, mcp_server):
        respx.get(f"{GRAPH_BASE_URL}/me/joinedTeams").mock(
            return_value=httpx.Response(200, json={"value": []})
        )
        respx.get(f"{GRAPH_BASE_URL}/me/chats").mock(
            return_value=httpx.Response(200, json={"value": []})
        )

        with _mock_token():
            from fastmcp import Client
            async with Client(mcp_server) as client:
                result = await client.call_tool("get_teams_activity", {"hours": 24})

        text = _get_text(result)
        assert "No Teams activity" in text


class TestMCPFileTools:
    """Test file/OneDrive/SharePoint MCP tools via in-process FastMCP client."""

    @respx.mock
    async def test_list_onedrive_files(self, mcp_server):
        respx.get(f"{GRAPH_BASE_URL}/me/drive/root/children").mock(
            return_value=httpx.Response(200, json=SAMPLE_DRIVE_CHILDREN_RESPONSE)
        )
        with _mock_token():
            from fastmcp import Client
            async with Client(mcp_server) as client:
                result = await client.call_tool("list_onedrive_files", {})

        text = _get_text(result)
        assert "3 item(s)" in text
        assert "Documents/" in text
        assert "report.csv" in text

    @respx.mock
    async def test_list_onedrive_files_subfolder(self, mcp_server):
        respx.get(f"{GRAPH_BASE_URL}/me/drive/root:/Documents:/children").mock(
            return_value=httpx.Response(200, json={"value": [SAMPLE_DRIVE_ITEM_FILE]})
        )
        with _mock_token():
            from fastmcp import Client
            async with Client(mcp_server) as client:
                result = await client.call_tool("list_onedrive_files", {"folder_path": "Documents"})

        text = _get_text(result)
        assert "1 item(s)" in text
        assert "report.csv" in text

    @respx.mock
    async def test_list_onedrive_files_empty(self, mcp_server):
        respx.get(f"{GRAPH_BASE_URL}/me/drive/root/children").mock(
            return_value=httpx.Response(200, json={"value": []})
        )
        with _mock_token():
            from fastmcp import Client
            async with Client(mcp_server) as client:
                result = await client.call_tool("list_onedrive_files", {})

        text = _get_text(result)
        assert "No files found" in text

    @respx.mock
    async def test_get_file_info(self, mcp_server):
        respx.get(f"{GRAPH_BASE_URL}/me/drive/items/file-id-001").mock(
            return_value=httpx.Response(200, json=SAMPLE_DRIVE_ITEM_FILE)
        )
        with _mock_token():
            from fastmcp import Client
            async with Client(mcp_server) as client:
                result = await client.call_tool("get_file_info", {"item_id": "file-id-001"})

        text = _get_text(result)
        assert "report.csv" in text
        assert "text/csv" in text
        assert "1.0 KB" in text

    @respx.mock
    async def test_read_file_content_text(self, mcp_server):
        csv_content = b"col1,col2\nval1,val2\n"
        respx.get(f"{GRAPH_BASE_URL}/me/drive/items/file-id-001").mock(
            return_value=httpx.Response(200, json=SAMPLE_DRIVE_ITEM_FILE)
        )
        respx.get(f"{GRAPH_BASE_URL}/me/drive/items/file-id-001/content").mock(
            return_value=httpx.Response(200, content=csv_content)
        )
        with _mock_token():
            from fastmcp import Client
            async with Client(mcp_server) as client:
                result = await client.call_tool("read_file_content", {"item_id": "file-id-001"})

        text = _get_text(result)
        assert "report.csv" in text
        assert "col1,col2" in text
        assert "val1,val2" in text

    @respx.mock
    async def test_read_file_content_binary(self, mcp_server):
        # Use a small binary file so the "binary" path (not "too large") is hit
        small_binary = dict(SAMPLE_DRIVE_ITEM_BINARY, size=50_000)
        respx.get(f"{GRAPH_BASE_URL}/me/drive/items/file-id-002").mock(
            return_value=httpx.Response(200, json=small_binary)
        )
        with _mock_token():
            from fastmcp import Client
            async with Client(mcp_server) as client:
                result = await client.call_tool("read_file_content", {"item_id": "file-id-002"})

        text = _get_text(result)
        assert "presentation.pptx" in text
        assert "binary file" in text
        assert "Open in browser" in text

    @respx.mock
    async def test_read_file_content_too_large(self, mcp_server):
        respx.get(f"{GRAPH_BASE_URL}/me/drive/items/file-id-003").mock(
            return_value=httpx.Response(200, json=SAMPLE_DRIVE_ITEM_LARGE_TEXT)
        )
        with _mock_token():
            from fastmcp import Client
            async with Client(mcp_server) as client:
                result = await client.call_tool("read_file_content", {"item_id": "file-id-003"})

        text = _get_text(result)
        assert "huge-log.txt" in text
        assert "too large" in text
        assert "512 KB" in text

    @respx.mock
    async def test_read_file_content_folder(self, mcp_server):
        respx.get(f"{GRAPH_BASE_URL}/me/drive/items/folder-id-001").mock(
            return_value=httpx.Response(200, json=SAMPLE_DRIVE_ITEM_FOLDER)
        )
        with _mock_token():
            from fastmcp import Client
            async with Client(mcp_server) as client:
                result = await client.call_tool("read_file_content", {"item_id": "folder-id-001"})

        text = _get_text(result)
        assert "Documents" in text
        assert "folder" in text.lower()

    @respx.mock
    async def test_search_files(self, mcp_server):
        respx.post(f"{GRAPH_BASE_URL}/search/query").mock(
            return_value=httpx.Response(200, json=SAMPLE_SEARCH_RESPONSE)
        )
        with _mock_token():
            from fastmcp import Client
            async with Client(mcp_server) as client:
                result = await client.call_tool("search_files", {"query": "budget"})

        text = _get_text(result)
        assert "2 result(s)" in text
        assert "Q4-budget.xlsx" in text
        assert "budget-notes.md" in text

    @respx.mock
    async def test_search_files_empty(self, mcp_server):
        respx.post(f"{GRAPH_BASE_URL}/search/query").mock(
            return_value=httpx.Response(200, json=SAMPLE_SEARCH_RESPONSE_EMPTY)
        )
        with _mock_token():
            from fastmcp import Client
            async with Client(mcp_server) as client:
                result = await client.call_tool("search_files", {"query": "nonexistent"})

        text = _get_text(result)
        assert "No files found" in text

    @respx.mock
    async def test_list_sharepoint_sites(self, mcp_server):
        respx.get(f"{GRAPH_BASE_URL}/sites").mock(
            return_value=httpx.Response(200, json=SAMPLE_SITES_RESPONSE)
        )
        with _mock_token():
            from fastmcp import Client
            async with Client(mcp_server) as client:
                result = await client.call_tool("list_sharepoint_sites", {"query": "engineering"})

        text = _get_text(result)
        assert "Engineering Hub" in text
        assert "Marketing Portal" in text

    @respx.mock
    async def test_list_sharepoint_sites_empty(self, mcp_server):
        respx.get(f"{GRAPH_BASE_URL}/me/followedSites").mock(
            return_value=httpx.Response(200, json={"value": []})
        )
        with _mock_token():
            from fastmcp import Client
            async with Client(mcp_server) as client:
                result = await client.call_tool("list_sharepoint_sites", {})

        text = _get_text(result)
        assert "No followed SharePoint sites" in text

    @respx.mock
    async def test_list_site_files(self, mcp_server):
        respx.get(f"{GRAPH_BASE_URL}/sites/site-id-001/drive/root/children").mock(
            return_value=httpx.Response(200, json=SAMPLE_DRIVE_CHILDREN_RESPONSE)
        )
        with _mock_token():
            from fastmcp import Client
            async with Client(mcp_server) as client:
                result = await client.call_tool("list_site_files", {"site_id": "site-id-001"})

        text = _get_text(result)
        assert "3 item(s)" in text
        assert "report.csv" in text

    @respx.mock
    async def test_list_site_files_empty(self, mcp_server):
        respx.get(f"{GRAPH_BASE_URL}/sites/site-id-001/drive/root/children").mock(
            return_value=httpx.Response(200, json={"value": []})
        )
        with _mock_token():
            from fastmcp import Client
            async with Client(mcp_server) as client:
                result = await client.call_tool("list_site_files", {"site_id": "site-id-001"})

        text = _get_text(result)
        assert "No files found" in text

    @respx.mock
    async def test_graph_error_propagates_from_file_tool(self, mcp_server):
        from fastmcp.exceptions import ToolError

        respx.get(f"{GRAPH_BASE_URL}/me/drive/root/children").mock(
            return_value=httpx.Response(401, json={"error": {"code": "InvalidAuthenticationToken", "message": "Token expired"}})
        )
        with _mock_token():
            from fastmcp import Client
            async with Client(mcp_server) as client:
                with pytest.raises(ToolError, match="InvalidAuthenticationToken"):
                    await client.call_tool("list_onedrive_files", {})


class TestMCPAuth:
    """Test authentication behavior."""

    async def test_missing_token_raises_error(self, mcp_server):
        from fastmcp import Client
        from fastmcp.exceptions import ToolError

        with patch("ms_graph_mcp.get_graph_token", side_effect=PermissionError("Authorization required.")):
            async with Client(mcp_server) as client:
                with pytest.raises(ToolError, match="Authorization required"):
                    await client.call_tool("list_emails", {})

    async def test_all_tools_require_auth(self, mcp_server):
        """Verify every tool rejects unauthenticated requests."""
        from fastmcp import Client
        from fastmcp.exceptions import ToolError

        tool_calls = [
            ("get_user_profile", {}),
            ("list_emails", {}),
            ("read_email", {"message_id": "fake-id"}),
            ("send_email", {"to": "a@b.com", "subject": "S", "body": "B"}),
            ("search_emails", {"query": "test"}),
            ("list_teams", {}),
            ("list_team_channels", {"team_id": "t1"}),
            ("send_teams_message", {"team_id": "t1", "channel_id": "c1", "message": "Hi"}),
            ("read_channel_messages", {"team_id": "t1", "channel_id": "c1"}),
            ("list_chats", {}),
            ("read_chat_messages", {"chat_id": "c1"}),
            ("send_chat_message", {"chat_id": "c1", "message": "Hi"}),
            ("get_teams_activity", {}),
            ("list_onedrive_files", {}),
            ("get_file_info", {"item_id": "x"}),
            ("read_file_content", {"item_id": "x"}),
            ("search_files", {"query": "test"}),
            ("list_sharepoint_sites", {}),
            ("list_site_files", {"site_id": "s1"}),
        ]
        with patch("ms_graph_mcp.get_graph_token", side_effect=PermissionError("Authorization required.")):
            async with Client(mcp_server) as client:
                for tool_name, args in tool_calls:
                    with pytest.raises(ToolError, match="Authorization required"):
                        await client.call_tool(tool_name, args)
