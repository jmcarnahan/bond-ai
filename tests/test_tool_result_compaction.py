"""
Unit tests for tool result compaction in BedrockAgent.

Tests the pipeline that:
- Converts list-of-dicts (5+ records) to CSV for token efficiency, even below the byte limit
- Truncates results that exceed Bedrock's ~25KB payload limit
- Retries transient connection errors on continuation invoke_agent calls
"""

import json
import pytest
from unittest.mock import MagicMock, patch
from http.client import RemoteDisconnected

from bondable.bond.providers.bedrock.BedrockAgent import (
    BedrockAgent,
    MAX_TOOL_RESULT_BYTES,
    MIN_RECORDS_FOR_CSV,
    MAX_CONTINUATION_RETRIES,
    CONTINUATION_RETRY_BASE_DELAY,
)


def _make_agent():
    """Create a minimal BedrockAgent instance with mocked dependencies."""
    agent = object.__new__(BedrockAgent)
    agent.bedrock_agent_id = "test-agent-id"
    agent.bedrock_agent_alias_id = "test-alias-id"
    agent.agent_id = "bond-agent-id"
    agent.model = "us.anthropic.claude-3-5-sonnet-20241022-v2:0"
    agent.bond_provider = MagicMock()
    agent._current_user = None
    agent._jwt_token = None
    agent.mcp_tools = []
    agent.mcp_resources = []
    return agent


def _make_jira_issues(count=50):
    """Generate a realistic Jira-style search result with the given number of issues."""
    issues = []
    for i in range(count):
        issues.append({
            "id": str(4800000 + i),
            "key": f"EIN-{10000 + i}",
            "summary": f"Issue summary for ticket {i} - this is a moderately long description of the issue",
            "status": {"name": "Done", "id": str(1000 + i)},
            "priority": {"name": "Medium", "id": "3"},
            "assignee": {"displayName": f"User {i}", "accountId": f"acc-{i:04d}"},
            "created": f"2026-01-{(i % 28) + 1:02d}T10:00:00.000+0000",
            "updated": f"2026-02-{(i % 28) + 1:02d}T15:30:00.000+0000",
            "labels": ["backend", "sprint-42"],
            "description": f"Detailed description for issue {i}. " * 5,
        })
    return {
        "total": count,
        "start_at": 0,
        "max_results": 50,
        "issues": issues,
    }


# ---------------------------------------------------------------------------
# TestExtractRecords
# ---------------------------------------------------------------------------
class TestExtractRecords:
    """Tests for _extract_records static method."""

    def test_direct_list_of_dicts(self):
        data = [{"key": "A"}, {"key": "B"}]
        result = BedrockAgent._extract_records(data)
        assert result == data

    def test_wrapped_in_issues_key(self):
        data = {"total": 2, "issues": [{"key": "A"}, {"key": "B"}]}
        result = BedrockAgent._extract_records(data)
        assert len(result) == 2
        assert result[0]["key"] == "A"

    def test_wrapped_in_results_key(self):
        data = {"results": [{"id": 1}, {"id": 2}]}
        result = BedrockAgent._extract_records(data)
        assert len(result) == 2

    def test_wrapped_in_items_key(self):
        data = {"items": [{"name": "x"}], "count": 1}
        result = BedrockAgent._extract_records(data)
        assert len(result) == 1

    def test_nested_data_issues(self):
        data = {"data": {"issues": [{"key": "X"}]}}
        result = BedrockAgent._extract_records(data)
        assert result == [{"key": "X"}]

    def test_fallback_largest_list(self):
        """When no common key matches, picks the largest list-of-dicts."""
        data = {
            "metadata": "ignored",
            "tickets": [{"id": 1}, {"id": 2}, {"id": 3}],
            "small": [{"id": 1}],
        }
        result = BedrockAgent._extract_records(data)
        assert len(result) == 3

    def test_returns_none_for_scalar(self):
        assert BedrockAgent._extract_records("hello") is None

    def test_returns_none_for_number(self):
        assert BedrockAgent._extract_records(42) is None

    def test_returns_none_for_empty_list(self):
        assert BedrockAgent._extract_records([]) is None

    def test_returns_none_for_list_of_scalars(self):
        assert BedrockAgent._extract_records([1, 2, 3]) is None

    def test_returns_none_for_empty_dict(self):
        assert BedrockAgent._extract_records({}) is None

    def test_returns_none_for_dict_without_lists(self):
        data = {"name": "test", "count": 5}
        assert BedrockAgent._extract_records(data) is None

    def test_wrapped_in_rows_key(self):
        """Databricks-style result with 'rows' key."""
        data = {"row_count": 2, "rows": [{"id": 1, "name": "A"}, {"id": 2, "name": "B"}]}
        result = BedrockAgent._extract_records(data)
        assert len(result) == 2

    def test_wrapped_in_result_key(self):
        """Single 'result' (not 'results') wrapper."""
        data = {"status": "ok", "result": [{"id": 1}, {"id": 2}]}
        result = BedrockAgent._extract_records(data)
        assert len(result) == 2

    def test_nested_result_rows(self):
        """Databricks-style: {"result": {"rows": [...]}}."""
        data = {
            "statement_id": "abc-123",
            "status": {"state": "SUCCEEDED"},
            "result": {
                "row_count": 2,
                "rows": [{"id": 1, "name": "Alice"}, {"id": 2, "name": "Bob"}]
            }
        }
        result = BedrockAgent._extract_records(data)
        assert len(result) == 2
        assert result[0]["name"] == "Alice"

    def test_recursive_fallback_deeply_nested(self):
        """Records buried 3+ levels deep with non-candidate key names."""
        data = {
            "response": {
                "query_output": {
                    "table_data": [
                        {"col1": "a", "col2": "b"},
                        {"col1": "c", "col2": "d"},
                        {"col1": "e", "col2": "f"},
                    ]
                }
            }
        }
        result = BedrockAgent._extract_records(data)
        assert result is not None
        assert len(result) == 3
        assert result[0]["col1"] == "a"

    def test_recursive_fallback_picks_largest_list(self):
        """When multiple lists exist at different depths, picks the largest."""
        data = {
            "meta": {"tags": [{"id": 1}]},
            "payload": {
                "output": {
                    "records": [{"id": i} for i in range(10)]
                }
            }
        }
        result = BedrockAgent._extract_records(data)
        assert len(result) == 10

    def test_recursive_depth_limit(self):
        """Deeply nested beyond limit should still not crash."""
        # Build a structure 10 levels deep (exceeds the 5-level safety limit)
        data = {"level": [{"id": 1}]}
        for _ in range(10):
            data = {"wrapper": data}
        # Should return None (the list is too deep to find) or the list if within limit
        result = BedrockAgent._extract_records(data)
        # At 10 levels of wrapping, the list is at depth 11 - beyond the limit
        assert result is None


# ---------------------------------------------------------------------------
# TestRecordsToCsv
# ---------------------------------------------------------------------------
class TestRecordsToCsv:
    """Tests for _records_to_csv static method."""

    def test_simple_records(self):
        records = [
            {"id": "1", "name": "Alice"},
            {"id": "2", "name": "Bob"},
        ]
        csv_output = BedrockAgent._records_to_csv(records)
        lines = csv_output.strip().splitlines()
        assert lines[0] == "id,name"
        assert lines[1] == "1,Alice"
        assert lines[2] == "2,Bob"

    def test_nested_dict_flattening(self):
        records = [
            {"key": "X", "status": {"name": "Done", "id": "100"}},
        ]
        csv_output = BedrockAgent._records_to_csv(records)
        lines = csv_output.strip().split("\n")
        header = lines[0]
        assert "status.name" in header
        assert "status.id" in header

    def test_list_values_become_json(self):
        records = [
            {"key": "X", "labels": ["bug", "urgent"]},
        ]
        csv_output = BedrockAgent._records_to_csv(records)
        # CSV quoting may escape the JSON; check for the content
        assert "bug" in csv_output and "urgent" in csv_output

    def test_cell_value_truncation(self):
        long_value = "x" * 300
        records = [{"key": "A", "description": long_value}]
        csv_output = BedrockAgent._records_to_csv(records)
        # Cell should be truncated to 200 chars + "..."
        assert "..." in csv_output
        # Should not contain the full 300 chars
        assert long_value not in csv_output

    def test_heterogeneous_records(self):
        """Records with different key sets should still produce valid CSV."""
        records = [
            {"id": "1", "name": "Alice"},
            {"id": "2", "email": "bob@test.com"},
        ]
        csv_output = BedrockAgent._records_to_csv(records)
        lines = csv_output.strip().split("\n")
        assert "id" in lines[0]
        assert "name" in lines[0]
        assert "email" in lines[0]
        assert len(lines) == 3  # header + 2 rows

    def test_empty_records(self):
        assert BedrockAgent._records_to_csv([]) == ""

    def test_none_values(self):
        records = [{"key": "A", "value": None}]
        csv_output = BedrockAgent._records_to_csv(records)
        lines = csv_output.strip().split("\n")
        assert len(lines) == 2  # Should not crash

    def test_deep_nested_flattening(self):
        """Multi-level nesting should be fully flattened with dot notation."""
        records = [
            {"id": 1, "user": {"name": "Alice", "address": {"city": "NYC", "zip": "10001"}}},
            {"id": 2, "user": {"name": "Bob", "address": {"city": "LA", "zip": "90001"}}},
        ]
        csv_output = BedrockAgent._records_to_csv(records)
        header = csv_output.strip().split("\n")[0]
        # pandas json_normalize should flatten all levels
        assert "user.address.city" in header
        assert "user.address.zip" in header
        assert "user.name" in header
        # Values should be present in the output
        assert "NYC" in csv_output
        assert "LA" in csv_output

    def test_three_levels_deep(self):
        """Three levels of nesting should produce dot-separated column names."""
        records = [
            {"a": {"b": {"c": {"d": "deep_value"}}}},
        ]
        csv_output = BedrockAgent._records_to_csv(records)
        header = csv_output.strip().split("\n")[0]
        assert "a.b.c.d" in header
        assert "deep_value" in csv_output

    def test_mixed_flat_and_nested(self):
        """Records with both flat and nested fields should work correctly."""
        records = [
            {
                "key": "CCS-1",
                "summary": "Fix bug",
                "status": {"name": "Done", "id": "100"},
                "priority": {"name": "High"},
                "assignee": {"displayName": "Alice", "team": {"name": "Backend", "lead": "Bob"}},
            }
        ]
        csv_output = BedrockAgent._records_to_csv(records)
        header = csv_output.strip().split("\n")[0]
        assert "key" in header
        assert "summary" in header
        assert "status.name" in header
        assert "assignee.team.name" in header
        assert "assignee.team.lead" in header
        assert "Bob" in csv_output


# ---------------------------------------------------------------------------
# TestTruncateResult
# ---------------------------------------------------------------------------
class TestTruncateResult:
    """Tests for _truncate_result static method."""

    def test_small_text_returned_as_is(self):
        text = "Hello world"
        result = BedrockAgent._truncate_result(text, 1000)
        assert result == text

    def test_large_text_truncated_with_suffix(self):
        text = "x" * 5000
        result = BedrockAgent._truncate_result(text, 1000)
        assert len(result.encode('utf-8')) <= 1000
        assert "[TRUNCATED" in result

    def test_utf8_boundary_safety(self):
        """Multi-byte characters should not be split during truncation."""
        # Create text with multi-byte chars (each is 3 bytes in UTF-8)
        text = "\u4e16\u754c" * 5000  # Chinese characters
        result = BedrockAgent._truncate_result(text, 2000)
        # Should be valid UTF-8 (no decode errors)
        result.encode('utf-8')
        assert "[TRUNCATED" in result

    def test_very_small_limit(self):
        """When max_bytes is too small even for the suffix, return minimal message."""
        result = BedrockAgent._truncate_result("x" * 1000, 10)
        assert "refine" in result.lower()


# ---------------------------------------------------------------------------
# TestCompactToolResult
# ---------------------------------------------------------------------------
class TestCompactToolResult:
    """Tests for _compact_tool_result method."""

    def test_small_scalar_result_passes_through_unchanged(self):
        agent = _make_agent()
        small_result = json.dumps({"key": "value"})
        result = agent._compact_tool_result(small_result, "test_tool")
        assert result == small_result

    def test_small_list_below_threshold_passes_through_unchanged(self):
        """Lists with fewer than MIN_RECORDS_FOR_CSV records stay as JSON."""
        agent = _make_agent()
        data = {"issues": [{"key": f"T-{i}"} for i in range(MIN_RECORDS_FOR_CSV - 1)]}
        small_result = json.dumps(data)
        result = agent._compact_tool_result(small_result, "test_tool")
        assert result == small_result

    def test_list_at_threshold_converts_to_csv(self):
        """Lists with exactly MIN_RECORDS_FOR_CSV records get CSV conversion."""
        agent = _make_agent()
        data = {"issues": [
            {"key": f"T-{i}", "summary": f"Issue {i}", "status": {"name": "Open"}}
            for i in range(MIN_RECORDS_FOR_CSV)
        ]}
        json_result = json.dumps(data)
        result = agent._compact_tool_result(json_result, "test_tool")
        # Should be CSV, not JSON
        assert result != json_result
        assert "key" in result.split("\n")[0]  # CSV header
        assert "T-0" in result

    def test_small_list_with_10_records_converts_to_csv(self):
        """A small (well under byte limit) list with 10 records should still become CSV."""
        agent = _make_agent()
        data = [
            {"id": i, "name": f"Item {i}", "status": {"state": "active"}}
            for i in range(10)
        ]
        json_result = json.dumps(data)
        # Verify this is well under the byte limit
        assert len(json_result.encode('utf-8')) < MAX_TOOL_RESULT_BYTES

        result = agent._compact_tool_result(json_result, "small_list_tool")
        # Should be CSV, not the original JSON
        assert result != json_result
        assert "status.state" in result  # Flattened nested field
        assert "active" in result
        # CSV should be smaller than JSON
        assert len(result.encode('utf-8')) < len(json_result.encode('utf-8'))

    def test_large_json_list_of_dicts_converts_to_csv(self):
        agent = _make_agent()
        data = _make_jira_issues(50)
        large_result = json.dumps(data)

        # Verify it's actually over the limit
        assert len(large_result.encode('utf-8')) > MAX_TOOL_RESULT_BYTES

        compacted = agent._compact_tool_result(large_result, "jira_search")

        # Should be significantly smaller
        assert len(compacted.encode('utf-8')) < len(large_result.encode('utf-8'))
        # Should contain CSV-like content (commas, headers)
        assert "EIN-" in compacted

    def test_large_json_wrapped_in_issues_key(self):
        """Jira-style {"issues": [...]} structure should be detected and converted."""
        agent = _make_agent()
        data = _make_jira_issues(50)
        large_result = json.dumps(data)
        compacted = agent._compact_tool_result(large_result, "jira_search")
        assert len(compacted.encode('utf-8')) <= MAX_TOOL_RESULT_BYTES

    def test_non_json_result_truncated(self):
        agent = _make_agent()
        large_text = "This is plain text. " * 2000
        assert len(large_text.encode('utf-8')) > MAX_TOOL_RESULT_BYTES

        result = agent._compact_tool_result(large_text, "text_tool")
        assert len(result.encode('utf-8')) <= MAX_TOOL_RESULT_BYTES
        assert "[TRUNCATED" in result

    def test_json_non_list_result_uses_compact_or_truncate(self):
        """Large JSON object that isn't a list-of-dicts should be compacted or truncated."""
        agent = _make_agent()
        data = {f"key_{i}": "x" * 500 for i in range(100)}
        large_result = json.dumps(data)
        assert len(large_result.encode('utf-8')) > MAX_TOOL_RESULT_BYTES

        result = agent._compact_tool_result(large_result, "big_dict_tool")
        assert len(result.encode('utf-8')) <= MAX_TOOL_RESULT_BYTES

    def test_csv_still_too_large_gets_truncated(self):
        """If CSV conversion is still over limit, result should be truncated."""
        agent = _make_agent()
        # Create many records with long values that won't compress much in CSV
        issues = []
        for i in range(200):
            issues.append({
                "id": str(i),
                "key": f"KEY-{i}",
                "summary": f"Summary text that is quite long for issue number {i}",
                "description": f"Description " * 20,
            })
        data = {"issues": issues}
        large_result = json.dumps(data)
        assert len(large_result.encode('utf-8')) > MAX_TOOL_RESULT_BYTES

        result = agent._compact_tool_result(large_result, "huge_result")
        assert len(result.encode('utf-8')) <= MAX_TOOL_RESULT_BYTES

    def test_compaction_ratio_for_jira_data(self):
        """CSV compaction should achieve significant reduction for typical Jira data."""
        agent = _make_agent()
        issues = []
        for i in range(40):
            issues.append({
                "id": str(i),
                "key": f"EIN-{i}",
                "summary": f"Issue {i}",
                "status": {"name": "Done"},
                "priority": {"name": "Medium"},
            })
        data = {"issues": issues}
        json_result = json.dumps(data)
        json_size = len(json_result.encode('utf-8'))

        compacted = agent._compact_tool_result(json_result, "jira_search")
        compacted_size = len(compacted.encode('utf-8'))

        # 40 records >= MIN_RECORDS_FOR_CSV, so should always convert to CSV
        assert compacted != json_result
        # CSV should be smaller than JSON
        assert compacted_size < json_size
        # Should still be within byte limit
        assert compacted_size <= MAX_TOOL_RESULT_BYTES


# ---------------------------------------------------------------------------
# TestContinuationRetryLogic
# ---------------------------------------------------------------------------
class TestContinuationRetryLogic:
    """Tests for retry logic in _handle_continuation_response."""

    def _make_return_control(self):
        return {
            "invocationId": "inv-123",
            "invocationInputs": [
                {
                    "apiInvocationInput": {
                        "actionGroupName": "MCPTools",
                        "apiPath": "/b.abc123.jira_search",
                        "httpMethod": "POST",
                        "parameters": [{"name": "jql", "value": "project = TEST"}],
                    }
                }
            ],
        }

    def _make_tool_results(self):
        return [
            {
                "apiResult": {
                    "actionGroup": "MCPTools",
                    "apiPath": "/b.abc123.jira_search",
                    "httpMethod": "POST",
                    "httpStatusCode": 200,
                    "responseBody": {
                        "application/json": {
                            "body": json.dumps({"result": "some data"})
                        }
                    },
                }
            }
        ]

    @patch("bondable.bond.providers.bedrock.BedrockAgent.time.sleep")
    def test_transient_error_retried_then_succeeds(self, mock_sleep):
        """RemoteDisconnected on first attempt should be retried and succeed."""
        agent = _make_agent()
        agent._handle_return_control = MagicMock(return_value=self._make_tool_results())

        # First call raises RemoteDisconnected, second succeeds
        mock_stream = MagicMock()
        mock_stream.__iter__ = MagicMock(return_value=iter([
            {"chunk": {"bytes": b"Hello from retry"}}
        ]))
        agent.bond_provider.bedrock_agent_runtime_client.invoke_agent.side_effect = [
            RemoteDisconnected("Remote end closed connection"),
            {"completion": mock_stream},
        ]

        gen = agent._handle_continuation_response(
            return_control=self._make_return_control(),
            session_id="sess-1",
            thread_id="thread-1",
            seen_file_hashes=set(),
        )
        chunks = [item for item in gen if isinstance(item, str)]

        # Should have retried and gotten the successful response
        assert any("Hello from retry" in c for c in chunks)
        assert mock_sleep.call_count == 1  # Slept once before retry

    @patch("bondable.bond.providers.bedrock.BedrockAgent.time.sleep")
    def test_all_retries_exhausted_yields_specific_error(self, mock_sleep):
        """When all retry attempts fail, should yield a specific error about payload size."""
        agent = _make_agent()
        agent._handle_return_control = MagicMock(return_value=self._make_tool_results())

        # All attempts raise RemoteDisconnected
        agent.bond_provider.bedrock_agent_runtime_client.invoke_agent.side_effect = (
            RemoteDisconnected("Connection closed")
        )

        gen = agent._handle_continuation_response(
            return_control=self._make_return_control(),
            session_id="sess-1",
            thread_id="thread-1",
            seen_file_hashes=set(),
        )
        chunks = [item for item in gen if isinstance(item, str)]

        # Should mention the payload was too large
        error_text = "".join(chunks)
        assert "too large" in error_text or "bytes" in error_text

    def test_non_retryable_error_fails_immediately(self):
        """Non-connection errors (e.g., ClientError) should fail immediately without retrying."""
        from botocore.exceptions import ClientError

        agent = _make_agent()
        agent._handle_return_control = MagicMock(return_value=self._make_tool_results())

        agent.bond_provider.bedrock_agent_runtime_client.invoke_agent.side_effect = (
            ClientError(
                {"Error": {"Code": "ValidationException", "Message": "Bad request"}},
                "InvokeAgent",
            )
        )

        gen = agent._handle_continuation_response(
            return_control=self._make_return_control(),
            session_id="sess-1",
            thread_id="thread-1",
            seen_file_hashes=set(),
        )
        chunks = [item for item in gen if isinstance(item, str)]

        # Should yield error with error type
        error_text = "".join(chunks)
        assert "ClientError" in error_text

        # Should NOT have retried - only 1 call
        assert agent.bond_provider.bedrock_agent_runtime_client.invoke_agent.call_count == 1


# ---------------------------------------------------------------------------
# TestCompactionIntegration
# ---------------------------------------------------------------------------
class TestCompactionIntegration:
    """Integration tests for compaction within _handle_return_control."""

    def test_large_mcp_result_gets_compacted(self):
        """A large MCP tool result should be compacted before being sent to Bedrock."""
        agent = _make_agent()

        # Generate a large Jira result
        large_result = json.dumps(_make_jira_issues(50))
        assert len(large_result.encode('utf-8')) > MAX_TOOL_RESULT_BYTES

        # Test _compact_tool_result directly on the large result
        compacted = agent._compact_tool_result(large_result, "jira_search")

        # Wrap as response_body like _handle_return_control does
        response_body = json.dumps({"result": compacted})

        # The response body should fit within the limit (with some tolerance for wrapper)
        assert len(response_body.encode('utf-8')) <= MAX_TOOL_RESULT_BYTES + 100
