"""
Unit tests for tool-call depth handling in BedrockAgent (CRM-22).

Covers the env-configurable depth limit, the graceful resumable stop at the
limit, and the near-limit warn-band nudge injected into the last tool result.

NOTE on overriding the tunables: BEDROCK_MAX_TOOL_CALL_DEPTH and
BEDROCK_TOOL_DEPTH_WARN_MARGIN are read from the environment once at module
import, so monkeypatch.setenv after import is a no-op. Tests must override the
module constants directly, e.g.:

    monkeypatch.setattr(bedrock_agent_module, 'MAX_TOOL_CALL_DEPTH', 5)

The guard and injection code read the module globals at call time, so this
works and monkeypatch restores the values automatically. The env-var pathway
itself is exercised by manual smoke testing, not unit tests.
"""

import copy
import json
import os
import pytest
from unittest.mock import MagicMock, patch

from bondable.bond.providers.bedrock import BedrockAgent as bedrock_agent_module

# Tests asserting the shipped defaults are meaningless (and would fail
# spuriously) when a developer has the env overrides exported.
_env_override_active = bool(
    os.environ.get('BEDROCK_MAX_TOOL_CALL_DEPTH')
    or os.environ.get('BEDROCK_TOOL_DEPTH_WARN_MARGIN')
)
skip_if_env_override = pytest.mark.skipif(
    _env_override_active,
    reason="BEDROCK_MAX_TOOL_CALL_DEPTH / BEDROCK_TOOL_DEPTH_WARN_MARGIN set in env"
)


def _make_agent():
    """Create a minimal BedrockAgent instance with mocked dependencies."""
    from bondable.bond.providers.bedrock.BedrockAgent import BedrockAgent

    agent = object.__new__(BedrockAgent)
    agent.bedrock_agent_id = "test-agent-id"
    agent.bedrock_agent_alias_id = "test-alias-id"
    agent.bond_provider = MagicMock()
    agent._current_user = None
    agent._jwt_token = None
    return agent


def _make_return_control(invocation_id="inv-123"):
    """Create a minimal returnControl event."""
    return {
        "invocationId": invocation_id,
        "invocationInputs": [
            {
                "apiInvocationInput": {
                    "actionGroupName": "test-action-group",
                    "apiPath": "/b.abc123.jira_search",
                    "httpMethod": "POST",
                    "parameters": [
                        {"name": "jql", "value": "project = TEST"}
                    ]
                }
            }
        ]
    }


def _make_tool_results():
    """Create tool results as _handle_return_control would return."""
    return [
        {
            "apiResult": {
                "actionGroup": "test-action-group",
                "apiPath": "/b.abc123.jira_search",
                "httpMethod": "POST",
                "httpStatusCode": 200,
                "responseBody": {
                    "application/json": {
                        "body": json.dumps({"result": "some data"})
                    }
                }
            }
        }
    ]


def _make_two_tool_results():
    """Two real tool results, to verify the nudge only touches the last one."""
    results = _make_tool_results()
    second = copy.deepcopy(results[0])
    second["apiResult"]["apiPath"] = "/b.abc123.jira_get"
    second["apiResult"]["responseBody"]["application/json"]["body"] = json.dumps(
        {"result": "other data"}
    )
    return results + [second]


def _chunk_stream(**_kwargs):
    """Fresh single-chunk completion stream per invoke_agent call."""
    return {"completion": iter([{"chunk": {"bytes": b"Done."}}])}


def _run_continuation(agent, depth, tool_results=None, session_id="test-session"):
    """Run _handle_continuation_response with mocked tool exec + Bedrock stream."""
    agent.bond_provider.bedrock_agent_runtime_client.invoke_agent = MagicMock(
        side_effect=_chunk_stream
    )
    with patch.object(
        agent, "_handle_return_control",
        return_value=tool_results if tool_results is not None else _make_tool_results()
    ) as mock_hrc:
        items = list(agent._handle_continuation_response(
            return_control=_make_return_control(),
            session_id=session_id,
            thread_id="test-thread",
            seen_file_hashes=set(),
            depth=depth
        ))
    return items, mock_hrc, agent.bond_provider.bedrock_agent_runtime_client.invoke_agent


def _sent_results(mock_invoke):
    """Extract the returnControlInvocationResults sent to Bedrock."""
    kwargs = mock_invoke.call_args.kwargs
    return kwargs["sessionState"]["returnControlInvocationResults"]


def _body_of(result):
    inner = result.get("apiResult", result)
    return json.loads(inner["responseBody"]["application/json"]["body"])


class TestDepthLimitConfig:

    @skip_if_env_override
    def test_default_limit_is_25_and_margin_3(self):
        """Guard the chosen production defaults (CI has no env override)."""
        assert bedrock_agent_module.MAX_TOOL_CALL_DEPTH == 25
        assert bedrock_agent_module.TOOL_DEPTH_WARN_MARGIN == 3

    def test_limit_configurable_stops_at_5(self, monkeypatch):
        monkeypatch.setattr(bedrock_agent_module, "MAX_TOOL_CALL_DEPTH", 5)
        agent = _make_agent()

        items, mock_hrc, mock_invoke = _run_continuation(agent, depth=5)

        text = [i for i in items if isinstance(i, str)]
        assert any("continue" in t.lower() for t in text)
        mock_invoke.assert_not_called()
        mock_hrc.assert_not_called()  # tools at the cap must not execute

    def test_below_limit_proceeds(self, monkeypatch):
        monkeypatch.setattr(bedrock_agent_module, "MAX_TOOL_CALL_DEPTH", 5)
        agent = _make_agent()

        items, mock_hrc, mock_invoke = _run_continuation(agent, depth=4)

        assert mock_invoke.call_count == 1
        mock_hrc.assert_called_once()
        assert any("Done." in i for i in items if isinstance(i, str))


class TestGracefulStop:

    def test_graceful_stop_text(self):
        agent = _make_agent()
        items = list(agent._handle_continuation_response(
            return_control=_make_return_control(),
            session_id="test-session",
            thread_id="test-thread",
            seen_file_hashes=set(),
            depth=bedrock_agent_module.MAX_TOOL_CALL_DEPTH
        ))

        text = [i for i in items if isinstance(i, str)]
        assert len(text) > 0
        assert any("continue" in t.lower() for t in text)
        assert not any("[Error:" in t for t in text)
        assert not any("is_error" in t for t in text)

    def test_resume_uses_same_session_at_depth_zero(self, monkeypatch):
        """After a stop, a fresh depth-0 call continues on the same session."""
        monkeypatch.setattr(bedrock_agent_module, "MAX_TOOL_CALL_DEPTH", 5)
        agent = _make_agent()

        _run_continuation(agent, depth=5)  # hits the cap, invoke_agent unused

        # Fresh top-level call, as _process_bedrock_invocation would make it
        items, _, mock_invoke = _run_continuation(agent, depth=0, session_id="test-session")

        kwargs = mock_invoke.call_args.kwargs
        assert kwargs["sessionId"] == "test-session"
        assert "returnControlInvocationResults" in kwargs["sessionState"]


class TestWarnBandInjection:

    def test_warn_band_injection_fires_at_band(self, monkeypatch):
        monkeypatch.setattr(bedrock_agent_module, "MAX_TOOL_CALL_DEPTH", 5)
        monkeypatch.setattr(bedrock_agent_module, "TOOL_DEPTH_WARN_MARGIN", 2)
        agent = _make_agent()

        _, _, mock_invoke = _run_continuation(agent, depth=3)

        sent = _sent_results(mock_invoke)
        assert len(sent) == 1  # count-preserving: no synthetic entry
        body = _body_of(sent[-1])
        assert "ask the user whether they would like" in body["system_notice"]

    @pytest.mark.parametrize("depth", [0, 1, 2, 4])
    def test_warn_band_not_fired_outside_band(self, monkeypatch, depth):
        monkeypatch.setattr(bedrock_agent_module, "MAX_TOOL_CALL_DEPTH", 5)
        monkeypatch.setattr(bedrock_agent_module, "TOOL_DEPTH_WARN_MARGIN", 2)
        agent = _make_agent()

        _, _, mock_invoke = _run_continuation(agent, depth=depth)

        for result in _sent_results(mock_invoke):
            assert "system_notice" not in _body_of(result)

    def test_warn_band_preserves_real_responses(self, monkeypatch):
        """The nudge only adds a key to the last result; nothing dropped/reordered."""
        monkeypatch.setattr(bedrock_agent_module, "MAX_TOOL_CALL_DEPTH", 5)
        monkeypatch.setattr(bedrock_agent_module, "TOOL_DEPTH_WARN_MARGIN", 2)

        agent = _make_agent()
        _, _, mock_invoke = _run_continuation(
            agent, depth=0, tool_results=_make_two_tool_results())
        baseline = _sent_results(mock_invoke)

        agent = _make_agent()
        _, _, mock_invoke = _run_continuation(
            agent, depth=3, tool_results=_make_two_tool_results())
        warned = _sent_results(mock_invoke)

        assert len(warned) == len(baseline) == 2
        # First result untouched, byte-identical
        assert json.dumps(warned[0], sort_keys=True) == json.dumps(baseline[0], sort_keys=True)
        # Last result differs ONLY by the added system_notice key in its body
        warned_body = _body_of(warned[1])
        baseline_body = _body_of(baseline[1])
        assert warned_body.pop("system_notice")
        assert warned_body == baseline_body
        # All non-body fields identical
        stripped = copy.deepcopy(warned[1])
        stripped["apiResult"]["responseBody"]["application/json"]["body"] = \
            baseline[1]["apiResult"]["responseBody"]["application/json"]["body"]
        assert json.dumps(stripped, sort_keys=True) == json.dumps(baseline[1], sort_keys=True)

    @skip_if_env_override
    def test_below_band_byte_identical_at_defaults(self):
        """Short flows (depth 0 at default 25/3) send tool results unmodified."""
        agent = _make_agent()
        _, _, mock_invoke = _run_continuation(agent, depth=0)

        sent = _sent_results(mock_invoke)
        assert json.dumps(sent, sort_keys=True) == \
            json.dumps(_make_tool_results(), sort_keys=True)

    def test_warn_band_with_real_return_control(self, monkeypatch):
        """The notice survives the REAL _handle_return_control response shape.

        The other warn-band tests use hand-built fixtures; if the real
        _make_tool_response shape drifted, _inject_depth_warning's blanket
        except would swallow the mismatch silently. This composes the real
        pair, mocking only the external tool executor.
        """
        monkeypatch.setattr(bedrock_agent_module, "MAX_TOOL_CALL_DEPTH", 5)
        monkeypatch.setattr(bedrock_agent_module, "TOOL_DEPTH_WARN_MARGIN", 2)
        agent = _make_agent()
        agent.agent_id = "test-agent-record-id"
        agent.mcp_tools = []
        agent.mcp_resources = []
        agent.bond_provider.bedrock_agent_runtime_client.invoke_agent = MagicMock(
            side_effect=_chunk_stream
        )

        mcp_return_control = {
            "invocationId": "inv-123",
            "invocationInputs": [
                {
                    "apiInvocationInput": {
                        "actionGroupName": "mcp-action-group",
                        "apiPath": "/b.aaa000.jira_search",
                        "httpMethod": "POST",
                        "parameters": [{"name": "jql", "value": "project = TEST"}]
                    }
                }
            ]
        }
        with patch("bondable.bond.providers.bedrock.BedrockAgent.Config") as mock_config, \
             patch("bondable.bond.providers.bedrock.BedrockAgent.execute_mcp_tool_sync") as mock_execute, \
             patch("bondable.bond.providers.bedrock.BedrockAgent._resolve_server_from_hash") as mock_resolve:
            mock_config.config.return_value.get_mcp_config.return_value = {"mcpServers": {"atlassian": {}}}
            mock_resolve.return_value = "atlassian"
            mock_execute.return_value = {"success": True, "result": "tool output"}

            list(agent._handle_continuation_response(
                return_control=mcp_return_control,
                session_id="test-session",
                thread_id="test-thread",
                seen_file_hashes=set(),
                depth=3
            ))

        sent = _sent_results(agent.bond_provider.bedrock_agent_runtime_client.invoke_agent)
        assert len(sent) == 1
        body = _body_of(sent[-1])
        assert "ask the user whether they would like" in body["system_notice"]
        assert "tool output" in body["result"]

    def test_malformed_last_result_degrades_to_no_notice(self, monkeypatch):
        """A last result without responseBody must not break the continuation."""
        monkeypatch.setattr(bedrock_agent_module, "MAX_TOOL_CALL_DEPTH", 5)
        monkeypatch.setattr(bedrock_agent_module, "TOOL_DEPTH_WARN_MARGIN", 2)
        agent = _make_agent()

        malformed = [{"apiResult": {"actionGroup": "x", "apiPath": "/y", "httpStatusCode": 200}}]
        items, _, mock_invoke = _run_continuation(
            agent, depth=3, tool_results=copy.deepcopy(malformed))

        # No exception; the continuation proceeded with the results unmodified
        assert any("Done." in i for i in items if isinstance(i, str))
        sent = _sent_results(mock_invoke)
        assert json.dumps(sent, sort_keys=True) == json.dumps(malformed, sort_keys=True)

    def test_empty_results_fallback_gets_notice(self, monkeypatch):
        """The fallback error result built for empty tool_results carries the nudge."""
        monkeypatch.setattr(bedrock_agent_module, "MAX_TOOL_CALL_DEPTH", 5)
        monkeypatch.setattr(bedrock_agent_module, "TOOL_DEPTH_WARN_MARGIN", 2)
        agent = _make_agent()

        _, _, mock_invoke = _run_continuation(agent, depth=3, tool_results=[])

        sent = _sent_results(mock_invoke)
        assert len(sent) == 1
        body = _body_of(sent[0])
        assert "error" in body  # still the fallback error payload
        assert "system_notice" in body

    def test_margin_zero_disables_warning(self, monkeypatch):
        monkeypatch.setattr(bedrock_agent_module, "MAX_TOOL_CALL_DEPTH", 5)
        monkeypatch.setattr(bedrock_agent_module, "TOOL_DEPTH_WARN_MARGIN", 0)
        agent = _make_agent()

        _, _, mock_invoke = _run_continuation(agent, depth=4)
        for result in _sent_results(mock_invoke):
            assert "system_notice" not in _body_of(result)

        items, _, mock_invoke = _run_continuation(agent, depth=5)
        assert any("continue" in i.lower() for i in items if isinstance(i, str))
        mock_invoke.assert_not_called()
