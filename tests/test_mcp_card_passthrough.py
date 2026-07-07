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
from unittest.mock import MagicMock, patch
from xml.sax.saxutils import escape as xml_escape

from bondable.bond.providers.bedrock.BedrockMCP import _extract_bond_card


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
            full_content="accumulated text"
        )
        _drain(gen)

        calls = agent.bond_provider.threads.add_message.call_args_list
        assert len(calls) == 2
        first_kwargs = calls[0].kwargs
        assert first_kwargs["message_type"] == "text"
        assert first_kwargs["message_id"] == "resp-1"
        assert first_kwargs["content"] == "accumulated text"
        assert calls[1].kwargs["message_type"] == "resource_card"
