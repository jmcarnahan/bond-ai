"""Tests for mail operations (sync and async)."""

import httpx
import pytest
import respx

from ms_graph.graph_client import GRAPH_BASE_URL, AsyncGraphClient, GraphClient
from ms_graph import mail
from .conftest import (
    SAMPLE_MESSAGE, SAMPLE_MESSAGES_RESPONSE, SAMPLE_USER_PROFILE,
    SAMPLE_MAILBOX_SETTINGS,
)


class TestProfileSync:
    """Synchronous profile operation tests."""

    @respx.mock
    def test_get_profile_with_mailbox_settings(self):
        respx.get(f"{GRAPH_BASE_URL}/me").mock(
            return_value=httpx.Response(200, json=SAMPLE_USER_PROFILE)
        )
        respx.get(f"{GRAPH_BASE_URL}/me/mailboxSettings").mock(
            return_value=httpx.Response(200, json=SAMPLE_MAILBOX_SETTINGS)
        )
        with GraphClient("tok") as client:
            profile = mail.get_profile(client)

        assert profile["displayName"] == "John Carnahan"
        assert profile["mail"] == "jmcarny@gmail.com"
        assert profile["mailboxAddress"] == "jmcarny.sbel@outlook.com"

    @respx.mock
    def test_get_profile_without_mailbox_settings_scope(self):
        """When MailboxSettings.Read scope is not granted, mailboxAddress is absent."""
        respx.get(f"{GRAPH_BASE_URL}/me").mock(
            return_value=httpx.Response(200, json=SAMPLE_USER_PROFILE)
        )
        respx.get(f"{GRAPH_BASE_URL}/me/mailboxSettings").mock(
            return_value=httpx.Response(403, json={
                "error": {"code": "ErrorAccessDenied", "message": "Access denied"}
            })
        )
        with GraphClient("tok") as client:
            profile = mail.get_profile(client)

        assert profile["displayName"] == "John Carnahan"
        assert "mailboxAddress" not in profile


class TestProfileAsync:
    """Async profile operation tests."""

    @respx.mock
    async def test_aget_profile_with_mailbox_settings(self):
        respx.get(f"{GRAPH_BASE_URL}/me").mock(
            return_value=httpx.Response(200, json=SAMPLE_USER_PROFILE)
        )
        respx.get(f"{GRAPH_BASE_URL}/me/mailboxSettings").mock(
            return_value=httpx.Response(200, json=SAMPLE_MAILBOX_SETTINGS)
        )
        async with AsyncGraphClient("tok") as client:
            profile = await mail.aget_profile(client)

        assert profile["displayName"] == "John Carnahan"
        assert profile["mailboxAddress"] == "jmcarny.sbel@outlook.com"

    @respx.mock
    async def test_aget_profile_without_mailbox_settings_scope(self):
        """When MailboxSettings.Read scope is not granted, mailboxAddress is absent."""
        respx.get(f"{GRAPH_BASE_URL}/me").mock(
            return_value=httpx.Response(200, json=SAMPLE_USER_PROFILE)
        )
        respx.get(f"{GRAPH_BASE_URL}/me/mailboxSettings").mock(
            return_value=httpx.Response(403, json={
                "error": {"code": "ErrorAccessDenied", "message": "Access denied"}
            })
        )
        async with AsyncGraphClient("tok") as client:
            profile = await mail.aget_profile(client)

        assert profile["displayName"] == "John Carnahan"
        assert "mailboxAddress" not in profile


class TestMailSync:
    """Synchronous mail operation tests."""

    @respx.mock
    def test_list_messages(self):
        respx.get(f"{GRAPH_BASE_URL}/me/mailFolders/inbox/messages").mock(
            return_value=httpx.Response(200, json=SAMPLE_MESSAGES_RESPONSE)
        )
        with GraphClient("tok") as client:
            messages = mail.list_messages(client)

        assert len(messages) == 2
        assert messages[0]["subject"] == "Weekly Report"

    @respx.mock
    def test_list_messages_custom_folder(self):
        route = respx.get(f"{GRAPH_BASE_URL}/me/mailFolders/sentitems/messages").mock(
            return_value=httpx.Response(200, json={"value": []})
        )
        with GraphClient("tok") as client:
            messages = mail.list_messages(client, folder="sentitems", top=5)

        assert messages == []
        assert "top=5" in str(route.calls[0].request.url)

    @respx.mock
    def test_get_message(self):
        msg_id = "AAMkAGI2TG93AAA="
        respx.get(f"{GRAPH_BASE_URL}/me/messages/{msg_id}").mock(
            return_value=httpx.Response(200, json=SAMPLE_MESSAGE)
        )
        with GraphClient("tok") as client:
            msg = mail.get_message(client, msg_id)

        assert msg["subject"] == "Weekly Report"
        assert msg["body"]["content"].startswith("Here is")

    @respx.mock
    def test_send_message(self):
        route = respx.post(f"{GRAPH_BASE_URL}/me/sendMail").mock(
            return_value=httpx.Response(202)
        )
        with GraphClient("tok") as client:
            mail.send_message(
                client,
                to=["alice@example.com"],
                subject="Hello",
                body="Hi Alice!",
            )

        assert route.called
        import json
        body = json.loads(route.calls[0].request.content)
        assert body["message"]["subject"] == "Hello"
        assert len(body["message"]["toRecipients"]) == 1
        assert body["message"]["toRecipients"][0]["emailAddress"]["address"] == "alice@example.com"

    @respx.mock
    def test_send_message_with_cc(self):
        route = respx.post(f"{GRAPH_BASE_URL}/me/sendMail").mock(
            return_value=httpx.Response(202)
        )
        with GraphClient("tok") as client:
            mail.send_message(
                client,
                to=["alice@example.com"],
                subject="Hello",
                body="Hi!",
                cc=["bob@example.com"],
            )

        import json
        body = json.loads(route.calls[0].request.content)
        assert len(body["message"]["ccRecipients"]) == 1
        assert body["message"]["ccRecipients"][0]["emailAddress"]["address"] == "bob@example.com"

    @respx.mock
    def test_send_message_with_from_address(self):
        route = respx.post(f"{GRAPH_BASE_URL}/me/sendMail").mock(
            return_value=httpx.Response(202)
        )
        with GraphClient("tok") as client:
            mail.send_message(
                client,
                to=["alice@example.com"],
                subject="Hello",
                body="Hi!",
                from_address="jmcarny.sbel@outlook.com",
            )

        import json
        body = json.loads(route.calls[0].request.content)
        assert body["message"]["from"]["emailAddress"]["address"] == "jmcarny.sbel@outlook.com"

    @respx.mock
    def test_send_message_without_from_address(self):
        route = respx.post(f"{GRAPH_BASE_URL}/me/sendMail").mock(
            return_value=httpx.Response(202)
        )
        with GraphClient("tok") as client:
            mail.send_message(
                client,
                to=["alice@example.com"],
                subject="Hello",
                body="Hi!",
            )

        import json
        body = json.loads(route.calls[0].request.content)
        assert "from" not in body["message"]

    @respx.mock
    def test_search_messages(self):
        respx.get(f"{GRAPH_BASE_URL}/me/messages").mock(
            return_value=httpx.Response(200, json=SAMPLE_MESSAGES_RESPONSE)
        )
        with GraphClient("tok") as client:
            results = mail.search_messages(client, "weekly report")

        assert len(results) == 2


class TestMailAsync:
    """Async mail operation tests."""

    @respx.mock
    async def test_alist_messages(self):
        respx.get(f"{GRAPH_BASE_URL}/me/mailFolders/inbox/messages").mock(
            return_value=httpx.Response(200, json=SAMPLE_MESSAGES_RESPONSE)
        )
        async with AsyncGraphClient("tok") as client:
            messages = await mail.alist_messages(client)

        assert len(messages) == 2

    @respx.mock
    async def test_aget_message(self):
        msg_id = "AAMkAGI2TG93AAA="
        respx.get(f"{GRAPH_BASE_URL}/me/messages/{msg_id}").mock(
            return_value=httpx.Response(200, json=SAMPLE_MESSAGE)
        )
        async with AsyncGraphClient("tok") as client:
            msg = await mail.aget_message(client, msg_id)

        assert msg["subject"] == "Weekly Report"

    @respx.mock
    async def test_asend_message(self):
        route = respx.post(f"{GRAPH_BASE_URL}/me/sendMail").mock(
            return_value=httpx.Response(202)
        )
        async with AsyncGraphClient("tok") as client:
            await mail.asend_message(
                client,
                to=["alice@example.com"],
                subject="Async Hello",
                body="Async body",
            )

        assert route.called

    @respx.mock
    async def test_asend_message_with_from_address(self):
        route = respx.post(f"{GRAPH_BASE_URL}/me/sendMail").mock(
            return_value=httpx.Response(202)
        )
        async with AsyncGraphClient("tok") as client:
            await mail.asend_message(
                client,
                to=["alice@example.com"],
                subject="Async Hello",
                body="Async body",
                from_address="jmcarny.sbel@outlook.com",
            )

        import json
        body = json.loads(route.calls[0].request.content)
        assert body["message"]["from"]["emailAddress"]["address"] == "jmcarny.sbel@outlook.com"

    @respx.mock
    async def test_asearch_messages(self):
        respx.get(f"{GRAPH_BASE_URL}/me/messages").mock(
            return_value=httpx.Response(200, json={"value": [SAMPLE_MESSAGE]})
        )
        async with AsyncGraphClient("tok") as client:
            results = await mail.asearch_messages(client, "report")

        assert len(results) == 1
