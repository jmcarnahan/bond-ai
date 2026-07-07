"""
Unit tests for the structured card passthrough from MCP tool results (CRM-33).

An MCP tool can surface an in-chat card by including a "_bond_card" object in
its result — primary transport is MCP structuredContent, fallback is a
top-level key in the text JSON. bond-ai returns the text to the model exactly
as before and additionally emits a client-facing resource_card <_bondmessage>.
Results without an envelope must behave byte-identically to today.
"""

import json
import pytest
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, Mock, patch
from xml.sax.saxutils import escape as xml_escape

from botocore.exceptions import EventStreamError

from bondable.bond.providers.bedrock.BedrockMCP import (
    _extract_bond_card,
    _strip_bond_card_text,
    execute_mcp_tool,
)


SAMPLE_CARD = {
    "type": "proposal",
    "proposal_id": "p-1",
    "contact_id": "c-1",
    "title": "Proposal",
    "preview": "Hi & <b>there</b>",
}


def _make_agent():
    """Create a minimal BedrockAgent instance with mocked dependencies."""
    from bondable.bond.providers.bedrock.BedrockAgent import BedrockAgent

    agent = object.__new__(BedrockAgent)
    agent.bedrock_agent_id = "test-agent-id"
    agent.bedrock_agent_alias_id = "test-alias-id"
    agent.agent_id = "test-agent-record-id"
    agent.model = "test-model"
    agent.bond_provider = MagicMock()
    agent._current_user = None
    agent._jwt_token = None
    agent.mcp_tools = []
    agent.mcp_resources = []
    return agent


def _make_return_control_for_mcp(api_path="/b.aaa000.jira_search"):
    """Create a returnControl event for an MCP tool invocation."""
    return {
        "invocationId": "inv-123",
        "invocationInputs": [
            {
                "apiInvocationInput": {
                    "actionGroupName": "mcp-action-group",
                    "apiPath": api_path,
                    "httpMethod": "POST",
                    "parameters": [
                        {"name": "jql", "value": "project = TEST"}
                    ]
                }
            }
        ]
    }


def _drain(gen):
    """Exhaust a generator, returning (yielded_items, return_value)."""
    items = []
    while True:
        try:
            items.append(next(gen))
        except StopIteration as stop:
            return items, stop.value


class TestExtractBondCard:
    """Pure unit tests for the envelope extraction helper."""

    def test_structured_content_top_level(self):
        result = SimpleNamespace(structured_content={"_bond_card": SAMPLE_CARD, "proposal_id": "p-1"})
        assert _extract_bond_card(result, "") == SAMPLE_CARD

    def test_structured_content_wrapped_under_result(self):
        result = SimpleNamespace(structured_content={"result": {"_bond_card": SAMPLE_CARD}})
        assert _extract_bond_card(result, "") == SAMPLE_CARD

    def test_text_json_fallback(self):
        result = SimpleNamespace(structured_content=None)
        text = json.dumps({"proposal_id": "p-1", "_bond_card": SAMPLE_CARD})
        assert _extract_bond_card(result, text) == SAMPLE_CARD

    def test_plain_text_returns_none(self):
        result = SimpleNamespace(structured_content=None)
        assert _extract_bond_card(result, "hello") is None

    def test_json_without_key_returns_none(self):
        result = SimpleNamespace(structured_content=None)
        assert _extract_bond_card(result, json.dumps({"proposal_id": "p-1"})) is None

    def test_non_dict_card_returns_none(self):
        result = SimpleNamespace(structured_content={"_bond_card": "not-a-dict"})
        assert _extract_bond_card(result, json.dumps({"_bond_card": "not-a-dict"})) is None

    def test_no_structured_content_attr(self):
        assert _extract_bond_card(object(), "") is None


class TestStripBondCardText:
    """The envelope is stripped from the model-facing text; other keys survive."""

    def test_strips_envelope_preserves_other_keys(self):
        text = json.dumps({"proposal_id": "p-1", "status": "draft", "_bond_card": SAMPLE_CARD})
        stripped = json.loads(_strip_bond_card_text(text))
        assert "_bond_card" not in stripped
        assert stripped == {"proposal_id": "p-1", "status": "draft"}

    def test_non_json_text_unchanged(self):
        assert _strip_bond_card_text("_bond_card mentioned in prose") == "_bond_card mentioned in prose"

    def test_text_without_key_unchanged(self):
        text = json.dumps({"proposal_id": "p-1"})
        assert _strip_bond_card_text(text) == text
        assert _strip_bond_card_text("") == ""


MCP_CONFIG = {
    "mcpServers": {
        "crm": {
            "url": "http://localhost:18004/mcp",
            "transport": "streamable-http",
        }
    }
}


def _fake_call_tool_result(payload: dict, structured: bool):
    """Fake fastmcp CallToolResult: text content always mirrors the payload;
    structured_content carries it only when structured=True."""
    result_obj = Mock()
    result_obj.content = [Mock(text=json.dumps(payload))]
    result_obj.structured_content = payload if structured else None
    return result_obj


async def _run_execute_mcp_tool(result_obj):
    """Drive the real execute_mcp_tool with a fake fastmcp client."""
    tool = Mock()
    tool.name = "render_proposal"
    tool.inputSchema = {}
    with patch("bondable.bond.providers.bedrock.BedrockMCP.StreamableHttpTransport"), \
         patch("bondable.bond.providers.bedrock.BedrockMCP.Client") as client_cls:
        client = AsyncMock()
        client.list_tools = AsyncMock(return_value=[tool])
        client.call_tool = AsyncMock(return_value=result_obj)
        client.__aenter__ = AsyncMock(return_value=client)
        client.__aexit__ = AsyncMock(return_value=None)
        client_cls.return_value = client
        return await execute_mcp_tool(
            MCP_CONFIG, "render_proposal", {"data_id": "d-1"}, target_server="crm"
        )


class TestExecuteMcpToolCardAttachment:
    """The real execute_mcp_tool attaches the card and strips it from the text.

    This is the only place the feature can silently die with every downstream
    test green (they all mock execute_mcp_tool_sync), so it must be covered.
    """

    @pytest.mark.asyncio
    async def test_structured_content_card_attached_and_text_stripped(self):
        payload = {"proposal_id": "p-1", "status": "draft", "_bond_card": SAMPLE_CARD}
        out = await _run_execute_mcp_tool(_fake_call_tool_result(payload, structured=True))

        assert out["success"] is True
        assert out["card"] == SAMPLE_CARD
        result_json = json.loads(out["result"])
        assert "_bond_card" not in result_json
        assert result_json["proposal_id"] == "p-1"
        assert result_json["status"] == "draft"

    @pytest.mark.asyncio
    async def test_text_fallback_card_attached(self):
        payload = {"proposal_id": "p-1", "_bond_card": SAMPLE_CARD}
        out = await _run_execute_mcp_tool(_fake_call_tool_result(payload, structured=False))

        assert out["card"] == SAMPLE_CARD
        assert "_bond_card" not in out["result"]

    @pytest.mark.asyncio
    async def test_no_envelope_no_card_key_text_untouched(self):
        payload = {"proposal_id": "p-1", "status": "draft"}
        out = await _run_execute_mcp_tool(_fake_call_tool_result(payload, structured=True))

        assert out == {"success": True, "result": json.dumps(payload)}


@patch("bondable.bond.providers.bedrock.BedrockAgent._resolve_server_from_hash")
@patch("bondable.bond.providers.bedrock.BedrockAgent.execute_mcp_tool_sync")
@patch("bondable.bond.providers.bedrock.BedrockAgent.Config")
class TestReturnControlCardSideChannel:
    """Cards ride the side channel, never the Bedrock tool results."""

    def _setup(self, mock_config, mock_resolve):
        mock_config.config.return_value.get_mcp_config.return_value = {"mcpServers": {"atlassian": {}}}
        mock_resolve.return_value = "atlassian"

    def test_card_captured_and_absent_from_bedrock_results(self, mock_config, mock_execute, mock_resolve):
        self._setup(mock_config, mock_resolve)
        mock_execute.return_value = {
            "success": True,
            "result": json.dumps({"proposal_id": "p-1"}),
            "card": SAMPLE_CARD,
        }
        agent = _make_agent()

        results = agent._handle_return_control(_make_return_control_for_mcp())

        assert len(results) == 1
        api_result = results[0]["apiResult"]
        assert api_result["httpStatusCode"] == 200
        # Text result still reaches the model
        body = json.loads(api_result["responseBody"]["application/json"]["body"])
        assert "p-1" in body["result"]
        # The card never enters what is sent to Bedrock
        assert "_bond_card" not in json.dumps(results)
        assert "card" not in api_result
        assert agent._pending_tool_cards == [SAMPLE_CARD]

    def test_no_card_key_leaves_results_unchanged(self, mock_config, mock_execute, mock_resolve):
        self._setup(mock_config, mock_resolve)
        mock_execute.return_value = {
            "success": True,
            "result": json.dumps({"proposal_id": "p-1"}),
        }
        agent = _make_agent()

        baseline = agent._handle_return_control(_make_return_control_for_mcp())
        assert agent._pending_tool_cards == []

        mock_execute.return_value = {
            "success": True,
            "result": json.dumps({"proposal_id": "p-1"}),
            "card": SAMPLE_CARD,
        }
        with_card = agent._handle_return_control(_make_return_control_for_mcp())

        # Bedrock-bound results are deep-equal with or without the envelope
        assert json.dumps(with_card, sort_keys=True) == json.dumps(baseline, sort_keys=True)

    def test_stale_cards_reset_between_invocations(self, mock_config, mock_execute, mock_resolve):
        self._setup(mock_config, mock_resolve)
        mock_execute.return_value = {"success": True, "result": "{}", "card": SAMPLE_CARD}
        agent = _make_agent()
        agent._handle_return_control(_make_return_control_for_mcp())
        assert agent._pending_tool_cards == [SAMPLE_CARD]

        mock_execute.return_value = {"success": True, "result": "{}"}
        agent._handle_return_control(_make_return_control_for_mcp())
        assert agent._pending_tool_cards == []


@patch("bondable.bond.providers.bedrock.BedrockAgent._resolve_server_from_hash")
@patch("bondable.bond.providers.bedrock.BedrockAgent.execute_mcp_tool_sync")
@patch("bondable.bond.providers.bedrock.BedrockAgent.Config")
class TestContinuationCardEmission:
    """_handle_continuation_response yields card_event dicts for the client."""

    def _setup(self, mock_config, mock_resolve):
        mock_config.config.return_value.get_mcp_config.return_value = {"mcpServers": {"atlassian": {}}}
        mock_resolve.return_value = "atlassian"

    def _run(self, agent):
        agent.bond_provider.bedrock_agent_runtime_client.invoke_agent = MagicMock(
            side_effect=lambda **kwargs: {"completion": iter([{"chunk": {"bytes": b"Done."}}])}
        )
        return list(agent._handle_continuation_response(
            return_control=_make_return_control_for_mcp(),
            session_id="test-session",
            thread_id="test-thread",
            seen_file_hashes=set(),
            depth=0
        ))

    def test_card_event_yielded_before_text(self, mock_config, mock_execute, mock_resolve):
        self._setup(mock_config, mock_resolve)
        mock_execute.return_value = {"success": True, "result": "{}", "card": SAMPLE_CARD}
        agent = _make_agent()

        items = self._run(agent)

        card_events = [i for i in items if isinstance(i, dict) and 'card_event' in i]
        assert card_events == [{'card_event': SAMPLE_CARD}]
        card_idx = items.index(card_events[0])
        text_idx = next(i for i, item in enumerate(items)
                        if isinstance(item, str) and "Done." in item)
        assert card_idx < text_idx  # card streams as soon as the tool ran

    def test_no_envelope_yields_identical_sequence(self, mock_config, mock_execute, mock_resolve):
        self._setup(mock_config, mock_resolve)
        mock_execute.return_value = {"success": True, "result": "{}"}

        baseline = self._run(_make_agent())
        repeat = self._run(_make_agent())

        assert baseline == repeat  # deterministic without an envelope
        assert not any(isinstance(i, dict) and 'card_event' in i for i in baseline)


@patch("bondable.bond.providers.bedrock.BedrockAgent._resolve_server_from_hash")
@patch("bondable.bond.providers.bedrock.BedrockAgent.execute_mcp_tool_sync")
@patch("bondable.bond.providers.bedrock.BedrockAgent.Config")
class TestNestedCardForwarding:
    """card_event dicts from nested tool rounds are forwarded to depth 0."""

    def test_nested_card_reaches_depth_zero_output(self, mock_config, mock_execute, mock_resolve):
        mock_config.config.return_value.get_mcp_config.return_value = {"mcpServers": {"atlassian": {}}}
        mock_resolve.return_value = "atlassian"
        # Outer tool round: no card. Nested round: carries the card.
        mock_execute.side_effect = [
            {"success": True, "result": "{}"},
            {"success": True, "result": "{}", "card": SAMPLE_CARD},
        ]
        agent = _make_agent()

        nested_return_control = _make_return_control_for_mcp("/b.aaa000.jira_get")
        depth0_events = [
            {"chunk": {"bytes": b"first "}},
            {"returnControl": nested_return_control},
        ]
        invoke_calls = [0]

        def mock_invoke_agent(**kwargs):
            invoke_calls[0] += 1
            if invoke_calls[0] == 1:
                return {"completion": iter(depth0_events)}
            return {"completion": iter([{"chunk": {"bytes": b"done"}}])}

        agent.bond_provider.bedrock_agent_runtime_client.invoke_agent.side_effect = mock_invoke_agent

        items = list(agent._handle_continuation_response(
            return_control=_make_return_control_for_mcp(),
            session_id="test-session",
            thread_id="test-thread",
            seen_file_hashes=set(),
            depth=0
        ))

        card_events = [i for i in items if isinstance(i, dict) and 'card_event' in i]
        assert card_events == [{'card_event': SAMPLE_CARD}]
        # Text from both rounds still streams
        text = "".join(i for i in items if isinstance(i, str))
        assert "done" in text


@patch("bondable.bond.providers.bedrock.BedrockAgent._resolve_server_from_hash")
@patch("bondable.bond.providers.bedrock.BedrockAgent.execute_mcp_tool_sync")
@patch("bondable.bond.providers.bedrock.BedrockAgent.Config")
class TestMultiCardRound:
    """A round with parallel tool invocations can emit multiple cards."""

    def test_two_cards_from_one_round(self, mock_config, mock_execute, mock_resolve):
        mock_config.config.return_value.get_mcp_config.return_value = {"mcpServers": {"atlassian": {}}}
        mock_resolve.return_value = "atlassian"
        card_b = dict(SAMPLE_CARD, proposal_id="p-2", title="Second")
        mock_execute.side_effect = [
            {"success": True, "result": "{}", "card": SAMPLE_CARD},
            {"success": True, "result": "{}", "card": card_b},
        ]
        agent = _make_agent()
        agent.bond_provider.bedrock_agent_runtime_client.invoke_agent = MagicMock(
            side_effect=lambda **kwargs: {"completion": iter([{"chunk": {"bytes": b"Done."}}])}
        )

        return_control = _make_return_control_for_mcp()
        second_input = json.loads(json.dumps(return_control["invocationInputs"][0]))
        second_input["apiInvocationInput"]["apiPath"] = "/b.aaa000.jira_get"
        return_control["invocationInputs"].append(second_input)

        items = list(agent._handle_continuation_response(
            return_control=return_control,
            session_id="test-session",
            thread_id="test-thread",
            seen_file_hashes=set(),
            depth=0
        ))

        card_events = [i for i in items if isinstance(i, dict) and 'card_event' in i]
        assert card_events == [{'card_event': SAMPLE_CARD}, {'card_event': card_b}]


@patch("bondable.bond.providers.bedrock.BedrockAgent._resolve_server_from_hash")
@patch("bondable.bond.providers.bedrock.BedrockAgent.execute_mcp_tool_sync")
@patch("bondable.bond.providers.bedrock.BedrockAgent.Config")
class TestCardNotDuplicatedByStreamRetry:
    """Cards are emitted before the continuation invoke, so a stream retry
    (EventStreamError on the first attempt) must not re-emit them."""

    @patch("bondable.bond.providers.bedrock.BedrockAgent.time.sleep")
    def test_stream_retry_emits_card_once(self, mock_sleep, mock_config, mock_execute, mock_resolve):
        mock_config.config.return_value.get_mcp_config.return_value = {"mcpServers": {"atlassian": {}}}
        mock_resolve.return_value = "atlassian"
        mock_execute.return_value = {"success": True, "result": "{}", "card": SAMPLE_CARD}
        agent = _make_agent()

        failing_stream = MagicMock()
        failing_stream.__iter__ = MagicMock(side_effect=EventStreamError(
            {"Error": {"Code": "dependencyFailedException", "Message": "boom"}},
            "InvokeAgent"
        ))
        invoke_calls = [0]

        def mock_invoke_agent(**kwargs):
            invoke_calls[0] += 1
            if invoke_calls[0] == 1:
                return {"completion": failing_stream}
            return {"completion": iter([{"chunk": {"bytes": b"Done."}}])}

        agent.bond_provider.bedrock_agent_runtime_client.invoke_agent.side_effect = mock_invoke_agent

        items = list(agent._handle_continuation_response(
            return_control=_make_return_control_for_mcp(),
            session_id="test-session",
            thread_id="test-thread",
            seen_file_hashes=set(),
            depth=0
        ))

        assert invoke_calls[0] == 2  # retry happened
        card_events = [i for i in items if isinstance(i, dict) and 'card_event' in i]
        assert card_events == [{'card_event': SAMPLE_CARD}]
        assert any("Done." in i for i in items if isinstance(i, str))


class TestTopLevelCardWiring:
    """_process_bedrock_invocation routes card_event dicts to the card helper.

    Guards the elif ordering at the top-level continuation loop: if the generic
    dict branch ever precedes the card_event branch, cards vanish silently.
    """

    def _make_full_agent(self):
        """Agent with the attrs _process_bedrock_invocation touches (mirrors
        tests/test_bedrock_connection_resilience.py)."""
        agent = _make_agent()
        agent.name = "Test Agent"
        agent.introduction = "Hi"
        agent.reminder = ""
        agent.owner_user_id = "user-1"
        agent.bond_provider.threads.add_message = MagicMock(return_value="card-msg-id")
        return agent

    def test_card_event_from_continuation_streams_resource_card(self):
        agent = self._make_full_agent()
        agent.bond_provider.bedrock_agent_runtime_client.invoke_agent = MagicMock(
            return_value={"completion": iter([{"returnControl": _make_return_control_for_mcp()}])}
        )

        # Keyword-only signature pinned to the call site in
        # _process_bedrock_invocation: a renamed/removed kwarg there fails here.
        def fake_continuation(*, return_control, session_id, thread_id,
                              seen_file_hashes, attachments):
            yield {'card_event': SAMPLE_CARD}
            yield "after card"

        with patch.object(agent, "_handle_continuation_response", side_effect=fake_continuation):
            stream = "".join(
                item for item in agent._process_bedrock_invocation(
                    prompt="Hello",
                    thread_id="test-thread",
                    session_id="test-session",
                    session_state={},
                    files=None,
                    attachments=None,
                    hidden=False,
                    user_id="user-1",
                )
                if isinstance(item, str)
            )

        assert 'type="resource_card"' in stream
        assert xml_escape(json.dumps(SAMPLE_CARD)) in stream
        assert "after card" in stream
        card_calls = [
            c for c in agent.bond_provider.threads.add_message.call_args_list
            if c.kwargs.get("message_type") == "resource_card"
        ]
        assert len(card_calls) == 1
        assert card_calls[0].kwargs["content"] == json.dumps(SAMPLE_CARD)

    def test_two_card_events_stream_two_cards(self):
        """Consecutive cards chain response_id/full_content correctly."""
        agent = self._make_full_agent()
        agent.bond_provider.bedrock_agent_runtime_client.invoke_agent = MagicMock(
            return_value={"completion": iter([{"returnControl": _make_return_control_for_mcp()}])}
        )
        card_b = dict(SAMPLE_CARD, proposal_id="p-2", title="Second")

        def fake_continuation(*, return_control, session_id, thread_id,
                              seen_file_hashes, attachments):
            yield {'card_event': SAMPLE_CARD}
            yield "between cards"
            yield {'card_event': card_b}

        with patch.object(agent, "_handle_continuation_response", side_effect=fake_continuation):
            stream = "".join(
                item for item in agent._process_bedrock_invocation(
                    prompt="Hello",
                    thread_id="test-thread",
                    session_id="test-session",
                    session_state={},
                    files=None,
                    attachments=None,
                    hidden=False,
                    user_id="user-1",
                )
                if isinstance(item, str)
            )

        assert xml_escape(json.dumps(SAMPLE_CARD)) in stream
        assert xml_escape(json.dumps(card_b)) in stream
        card_calls = [
            c for c in agent.bond_provider.threads.add_message.call_args_list
            if c.kwargs.get("message_type") == "resource_card"
        ]
        assert [json.loads(c.kwargs["content"]) for c in card_calls] == [SAMPLE_CARD, card_b]
        # The text between the cards was persisted under the post-first-card id
        text_calls = [
            c for c in agent.bond_provider.threads.add_message.call_args_list
            if c.kwargs.get("message_type") == "text" and "between cards" in c.kwargs.get("content", "")
        ]
        assert len(text_calls) == 1


class TestCardEventStreamingHelper:
    """_handle_card_event_streaming persists and streams the card message."""

    def test_yield_sequence_and_persistence(self):
        agent = _make_agent()
        agent.bond_provider.threads.add_message = MagicMock(return_value="card-msg-id")

        gen = agent._handle_card_event_streaming(
            card=SAMPLE_CARD,
            thread_id="test-thread",
            user_id="user-1",
            current_response_id="resp-1",
            full_content=""
        )
        items, new_response_id = _drain(gen)

        card_json = json.dumps(SAMPLE_CARD)
        assert items[0] == '</_bondmessage>'
        assert 'type="resource_card"' in items[1]
        assert 'id="card-msg-id"' in items[1]
        assert 'is_error="false"' in items[1]
        assert items[2] == xml_escape(card_json)
        assert "&amp;" in items[2]  # preview ampersand escaped on the stream
        assert items[3] == '</_bondmessage>'
        assert 'type="text"' in items[4]

        # Persisted unescaped, with the resource_card type
        agent.bond_provider.threads.add_message.assert_called_once()
        kwargs = agent.bond_provider.threads.add_message.call_args.kwargs
        assert kwargs["message_type"] == "resource_card"
        assert kwargs["content"] == card_json

        assert new_response_id and new_response_id != "resp-1"
        assert f'id="{new_response_id}"' in items[4]

    def test_accumulated_text_persisted_first(self):
        agent = _make_agent()
        agent.bond_provider.threads.add_message = MagicMock(side_effect=["text-msg-id", "card-msg-id"])

        gen = agent._handle_card_event_streaming(
            card=SAMPLE_CARD,
            thread_id="test-thread",
            user_id="user-1",
            current_response_id="resp-1",
            full_content="A &amp; B"  # stream-escaped, as accumulated text is
        )
        _drain(gen)

        calls = agent.bond_provider.threads.add_message.call_args_list
        assert len(calls) == 2
        first_kwargs = calls[0].kwargs
        assert first_kwargs["message_type"] == "text"
        assert first_kwargs["message_id"] == "resp-1"
        assert first_kwargs["content"] == "A & B"  # persisted unescaped
        assert calls[1].kwargs["message_type"] == "resource_card"
