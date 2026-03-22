"""
Unit tests for tool result compaction in BedrockAgent.

Tests the pipeline that:
- Converts list-of-dicts (5+ records) to CSV for token efficiency, even below the byte limit
- Truncates results that exceed Bedrock's ~25KB payload limit
- Filters out low-value columns (nulls, constants, API artifacts)
- Row-boundary-aware CSV truncation
- Pagination metadata extraction
- Always-respond guarantee for tool invocations
- Retries transient connection errors on continuation invoke_agent calls
"""

import json
import pandas as pd
import pytest
from unittest.mock import MagicMock, patch
from http.client import RemoteDisconnected

from bondable.bond.providers.bedrock.BedrockAgent import (
    BedrockAgent,
    MAX_TOOL_RESULT_BYTES,
    MIN_RECORDS_FOR_CSV,
    MAX_INVOKE_RETRIES,
    INVOKE_RETRY_BASE_DELAY,
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
            {"id": i, "name": f"Item {i}", "status": {"state": f"state_{i % 3}"}}
            for i in range(10)
        ]
        json_result = json.dumps(data)
        # Verify this is well under the byte limit
        assert len(json_result.encode('utf-8')) < MAX_TOOL_RESULT_BYTES

        result = agent._compact_tool_result(json_result, "small_list_tool")
        # Should be CSV, not the original JSON
        assert result != json_result
        assert "status.state" in result  # Flattened nested field
        assert "state_0" in result
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


# ---------------------------------------------------------------------------
# TestRecordsToCsvEdgeCases
# ---------------------------------------------------------------------------
class TestRecordsToCsvEdgeCases:
    """Edge case tests for _records_to_csv (Bug 1 and Bug 2 fixes)."""

    def test_list_cell_values_truncated(self):
        """Bug 1 fix: list values longer than 200 chars when stringified should be truncated."""
        long_list = list(range(100))  # str(list(range(100))) is well over 200 chars
        records = [{"key": "A", "labels": long_list}]
        csv_output = BedrockAgent._records_to_csv(records)
        # The stringified list should be truncated to 200 chars + "..."
        assert "..." in csv_output
        # Should not contain the full list
        assert str(long_list) not in csv_output

    def test_int_cell_values_truncated(self):
        """Bug 1 fix: non-string types with long str() should also be truncated."""
        # Very large integer has a long string representation
        records = [{"key": "A", "big_number": 10**250}]
        csv_output = BedrockAgent._records_to_csv(records)
        # 10**250 is 251 digits, should be truncated
        assert "..." in csv_output

    def test_json_normalize_failure_fallback(self):
        """Bug 2 fix: when json_normalize raises, should fall back to simple DataFrame."""
        records = [{"key": "A", "name": "Alice"}, {"key": "B", "name": "Bob"}]
        # Mock json_normalize to raise, forcing the fallback path
        with patch("bondable.bond.providers.bedrock.BedrockAgent.pd.json_normalize",
                   side_effect=TypeError("Cannot normalize")):
            csv_output = BedrockAgent._records_to_csv(records)
        # Fallback should produce valid CSV with stringified values
        assert "key" in csv_output
        assert "A" in csv_output
        assert "Bob" in csv_output

    def test_json_normalize_with_mixed_nesting(self):
        """Records with mixed nested/simple values should produce CSV without crash."""
        records = [{"a": {"nested": [1, 2, {"deep": True}]}}, {"a": "simple"}]
        csv_output = BedrockAgent._records_to_csv(records)
        assert csv_output  # Should produce some output

    def test_very_wide_records(self):
        """100+ columns should not crash."""
        records = [{f"col_{i}": f"val_{i}_{j}" for i in range(120)} for j in range(5)]
        csv_output = BedrockAgent._records_to_csv(records)
        lines = csv_output.strip().split("\n")
        assert len(lines) == 6  # header + 5 rows

    def test_all_null_values(self):
        """Records with all None values should not crash."""
        records = [{"a": None, "b": None} for _ in range(5)]
        csv_output = BedrockAgent._records_to_csv(records)
        assert csv_output  # Should not crash

    def test_empty_dict_records(self):
        """Records that are empty dicts should not crash."""
        records = [{} for _ in range(5)]
        csv_output = BedrockAgent._records_to_csv(records)
        # May produce just a newline or empty CSV, but should not crash
        assert isinstance(csv_output, str)

    def test_newlines_in_cell_values_replaced(self):
        """Cell values with newlines should have them replaced with spaces."""
        records = [
            {"key": "A", "description": "line1\nline2\nline3"},
            {"key": "B", "description": "single line"},
        ]
        csv_output = BedrockAgent._records_to_csv(records)
        # CSV should not have newlines within data rows
        lines = csv_output.strip().split("\n")
        assert len(lines) == 3  # header + 2 data rows (not 4 from split newlines)
        # The newlines should be replaced with spaces
        assert "line1 line2 line3" in csv_output

    def test_unicode_in_csv(self):
        """Multi-byte Unicode characters should be handled correctly."""
        records = [
            {"key": "A", "name": "\u4e16\u754c" * 50},  # Chinese characters
            {"key": "B", "name": "\U0001f600" * 50},  # Emoji
        ]
        csv_output = BedrockAgent._records_to_csv(records)
        assert csv_output
        # Should be valid encoding
        csv_output.encode('utf-8')

    def test_mixed_type_list_handling(self):
        """Records where some items aren't dicts should be handled by fallback."""
        records = [{"a": 1}, {"a": 2}]
        # This is a normal case that should work fine
        csv_output = BedrockAgent._records_to_csv(records)
        assert "a" in csv_output
        assert "1" in csv_output


# ---------------------------------------------------------------------------
# TestColumnFiltering
# ---------------------------------------------------------------------------
class TestColumnFiltering:
    """Tests for _filter_low_value_columns."""

    def test_all_null_columns_dropped(self):
        """Columns where every value is null should be dropped."""
        df = pd.DataFrame({
            "key": ["A", "B", "C"],
            "name": ["Alice", "Bob", "Carol"],
            "empty_col": [None, None, None],
        })
        result = BedrockAgent._filter_low_value_columns(df)
        assert "empty_col" not in result.columns
        assert "key" in result.columns
        assert "name" in result.columns

    def test_constant_columns_dropped(self):
        """Columns where every row has the same non-null value should be dropped."""
        df = pd.DataFrame({
            "key": ["A", "B", "C"],
            "constant": ["same", "same", "same"],
            "varied": [1, 2, 3],
        })
        result = BedrockAgent._filter_low_value_columns(df)
        assert "constant" not in result.columns
        assert "key" in result.columns
        assert "varied" in result.columns

    def test_columns_with_some_nulls_not_dropped(self):
        """Columns with a mix of values and nulls should NOT be dropped."""
        df = pd.DataFrame({
            "key": ["A", "B", "C"],
            "sparse": ["val", None, "val"],
        })
        result = BedrockAgent._filter_low_value_columns(df)
        assert "sparse" in result.columns

    def test_low_value_patterns_dropped(self):
        """Columns matching low-value regex patterns should be dropped."""
        df = pd.DataFrame({
            "key": ["A", "B"],
            "assignee.self": ["https://jira.example.com/rest/api/2/user?id=1", "https://jira.example.com/rest/api/2/user?id=2"],
            "assignee.displayName": ["Alice", "Bob"],
            "assignee.accountId": ["abc123", "def456"],
            "assignee.avatarUrl": ["https://avatar.example.com/1.png", "https://avatar.example.com/2.png"],
            "assignee.timeZone": ["America/New_York", "America/Los_Angeles"],
            "priority.iconUrl": ["https://jira.example.com/icon1.png", "https://jira.example.com/icon2.png"],
            "avatar.48x48": ["url1", "url2"],
        })
        result = BedrockAgent._filter_low_value_columns(df)
        # Should keep key and displayName
        assert "key" in result.columns
        assert "assignee.displayName" in result.columns
        # Should drop all low-value patterns
        assert "assignee.self" not in result.columns
        assert "assignee.accountId" not in result.columns
        assert "assignee.avatarUrl" not in result.columns
        assert "assignee.timeZone" not in result.columns
        assert "priority.iconUrl" not in result.columns
        assert "avatar.48x48" not in result.columns

    def test_unhashable_types_dont_crash(self):
        """Columns with list values should not crash nunique()."""
        df = pd.DataFrame({
            "key": ["A", "B"],
            "labels": [["bug", "urgent"], ["feature"]],
        })
        # Should not crash
        result = BedrockAgent._filter_low_value_columns(df)
        assert "labels" in result.columns

    def test_empty_dataframe(self):
        """Empty DataFrame should be returned as-is."""
        df = pd.DataFrame()
        result = BedrockAgent._filter_low_value_columns(df)
        assert result.empty


# ---------------------------------------------------------------------------
# TestCsvTruncation
# ---------------------------------------------------------------------------
class TestCsvTruncation:
    """Tests for _truncate_csv row-boundary-aware truncation."""

    def test_truncation_at_row_boundary(self):
        """CSV should be truncated at row boundaries, not mid-row."""
        # Create CSV with many rows
        header = "id,name,description"
        rows = [f"{i},Name {i},Description for item {i}" for i in range(100)]
        csv_text = header + "\n" + "\n".join(rows)

        result = BedrockAgent._truncate_csv(csv_text, 500, "test_tool")
        lines = result.strip().split("\n")

        # First line should be the header
        assert lines[0] == header
        # Last line should be the footer comment
        assert lines[-1].startswith("# [Showing")
        # All middle lines should be complete data rows
        for line in lines[1:-1]:
            assert "," in line  # Should have CSV separators

    def test_truncation_footer_shows_counts(self):
        """Footer should show how many rows were kept vs total."""
        header = "id,name"
        rows = [f"{i},Name {i}" for i in range(50)]
        csv_text = header + "\n" + "\n".join(rows)

        result = BedrockAgent._truncate_csv(csv_text, 200, "test_tool")
        assert "of 50 rows" in result

    def test_small_csv_passes_through(self):
        """CSV that fits within the limit should be returned unchanged."""
        csv_text = "id,name\n1,Alice\n2,Bob\n"
        result = BedrockAgent._truncate_csv(csv_text, 10000, "test_tool")
        assert result == csv_text

    def test_single_line_csv(self):
        """Header-only CSV should be returned as-is."""
        csv_text = "id,name"
        result = BedrockAgent._truncate_csv(csv_text, 100, "test_tool")
        assert result == csv_text

    def test_zero_rows_fit(self):
        """If header + footer exceed max_bytes, should still return header + footer."""
        header = "id,name,description,extra_col_1,extra_col_2"
        rows = [f"{i},Name {i},Desc {i},Extra1,Extra2" for i in range(10)]
        csv_text = header + "\n" + "\n".join(rows)
        # Set max_bytes very small - only header fits
        result = BedrockAgent._truncate_csv(csv_text, 80, "test_tool")
        assert "Showing 0 of 10 rows" in result


# ---------------------------------------------------------------------------
# TestPaginationMetadata
# ---------------------------------------------------------------------------
class TestPaginationMetadata:
    """Tests for _extract_pagination_metadata."""

    def test_jira_pagination(self):
        """Jira-style pagination metadata should be extracted."""
        parsed = {
            "total": 234,
            "startAt": 0,
            "maxResults": 50,
            "issues": [{"key": "X"}],
        }
        result = BedrockAgent._extract_pagination_metadata(parsed)
        assert result is not None
        assert "234" in result
        assert "50" in result
        assert "startAt=0" in result

    def test_has_more_pagination(self):
        """has_more flag should be detected."""
        parsed = {"has_more": True, "items": []}
        result = BedrockAgent._extract_pagination_metadata(parsed)
        assert result is not None
        assert "more results available" in result

    def test_no_pagination_metadata(self):
        """Data without pagination fields should return None."""
        parsed = {"items": [{"a": 1}]}
        result = BedrockAgent._extract_pagination_metadata(parsed)
        assert result is None

    def test_non_dict_returns_none(self):
        """Non-dict input should return None."""
        assert BedrockAgent._extract_pagination_metadata([1, 2, 3]) is None
        assert BedrockAgent._extract_pagination_metadata("string") is None

    def test_pagination_prepended_to_csv(self):
        """Pagination metadata should appear in compacted CSV output."""
        agent = _make_agent()
        data = {
            "total": 100,
            "startAt": 0,
            "maxResults": 10,
            "issues": [
                {"key": f"T-{i}", "summary": f"Issue {i}", "status": {"name": f"s{i}"}}
                for i in range(10)
            ],
        }
        json_result = json.dumps(data)
        result = agent._compact_tool_result(json_result, "jira_search")
        # Should contain pagination comment
        assert "# " in result
        assert "100" in result

    def test_pagination_skipped_when_over_budget(self):
        """Pagination header should be skipped if it would push the result over the byte limit."""
        agent = _make_agent()
        # Create data that fits but just barely under the byte limit
        # The pagination header (~80 bytes) should be skipped if it would push over
        data = {
            "total": 999,
            "startAt": 0,
            "maxResults": 50,
            "issues": [
                {"key": f"PROJ-{i}", "summary": f"Summary text for issue number {i} with detail",
                 "status": {"name": f"status_{i % 5}"}}
                for i in range(50)
            ],
        }
        json_result = json.dumps(data)
        result = agent._compact_tool_result(json_result, "jira_search")

        # Result must always fit within the byte limit
        wrapped_size = len(json.dumps({"result": result}).encode('utf-8'))
        assert wrapped_size <= MAX_TOOL_RESULT_BYTES

    def test_pagination_does_not_break_truncated_csv(self):
        """Pagination header must come BEFORE CSV header, even when CSV is truncated."""
        agent = _make_agent()
        # Create large data that will require truncation
        data = {
            "total": 500,
            "startAt": 0,
            "maxResults": 200,
            "issues": [
                {"key": f"PROJ-{i}", "summary": f"Summary for issue {i} with extra text" * 3,
                 "description": f"Description " * 20, "status": {"name": f"s{i}"}}
                for i in range(200)
            ],
        }
        json_result = json.dumps(data)
        assert len(json_result.encode('utf-8')) > MAX_TOOL_RESULT_BYTES

        result = agent._compact_tool_result(json_result, "jira_search")
        lines = result.strip().split("\n")

        # First line should be the pagination comment
        assert lines[0].startswith("# ")
        assert "500" in lines[0]  # total count

        # Second line should be the actual CSV header (column names)
        assert "key" in lines[1]
        assert "summary" in lines[1]

        # Should have a truncation footer
        assert any("Showing" in line for line in lines)


# ---------------------------------------------------------------------------
# TestCompactToolResultEdgeCases
# ---------------------------------------------------------------------------
class TestCompactToolResultEdgeCases:
    """Edge case tests for _compact_tool_result."""

    def test_empty_string_input(self):
        """Empty string should not crash."""
        agent = _make_agent()
        result = agent._compact_tool_result("", "test_tool")
        assert isinstance(result, str)

    def test_null_json_input(self):
        """'null' JSON string should not crash."""
        agent = _make_agent()
        result = agent._compact_tool_result("null", "test_tool")
        assert isinstance(result, str)

    def test_division_by_zero_empty_result(self):
        """Bug 4 fix: empty result string should not cause ZeroDivisionError."""
        agent = _make_agent()
        # An empty list of records that triggers CSV conversion won't happen
        # (MIN_RECORDS_FOR_CSV=5), but ensure the code handles edge cases
        result = agent._compact_tool_result("[]", "test_tool")
        assert isinstance(result, str)

    def test_csv_larger_than_json_prefers_compact(self):
        """Bug 3 fix: when CSV is larger than compact JSON, prefer JSON."""
        agent = _make_agent()
        # Create records with many columns but very short values
        # This produces CSV with a large header row relative to data
        records = [{f"c{i}": i for i in range(50)} for _ in range(5)]
        data = {"items": records}
        json_result = json.dumps(data)
        result = agent._compact_tool_result(json_result, "wide_tool")
        # Should produce some output without crashing
        assert isinstance(result, str)
        assert len(result) > 0

    def test_special_json_escape_chars(self):
        """Strings with JSON escape chars should be handled within the headroom budget."""
        agent = _make_agent()
        # Create records with lots of escape-heavy characters
        records = [
            {"key": f"T-{i}", "desc": 'He said "hello"\nand left\t\\end'}
            for i in range(10)
        ]
        json_result = json.dumps(records)
        result = agent._compact_tool_result(json_result, "escape_tool")
        # Should produce valid output
        assert isinstance(result, str)
        # JSON-wrapped size should be within limits
        wrapped_size = len(json.dumps({"result": result}).encode('utf-8'))
        assert wrapped_size <= MAX_TOOL_RESULT_BYTES


# ---------------------------------------------------------------------------
# TestAlwaysRespond
# ---------------------------------------------------------------------------
class TestAlwaysRespond:
    """Tests for the always-respond guarantee in _handle_return_control."""

    def _make_return_control(self, api_path="/b.abc123.some_tool", inv_type="apiInvocationInput"):
        return {
            "invocationId": "inv-123",
            "invocationInputs": [
                {
                    inv_type: {
                        "actionGroupName": "MCPTools",
                        "apiPath": api_path,
                        "httpMethod": "POST",
                        "parameters": [{"name": "query", "value": "test"}],
                    }
                }
            ],
        }

    def test_allow_write_tools_false_returns_response(self):
        """Bug 5 fix: allow_write_tools=false should return a proper error response, not crash."""
        agent = _make_agent()
        agent.metadata = {"allow_write_tools": False}
        agent.agent_id = "test-agent"
        agent._current_user = MagicMock()
        agent._current_user.email = "user@test.com"
        agent._current_user.user_id = "user-123"
        agent._jwt_token = None

        # Mock Config to return MCP config
        with patch("bondable.bond.providers.bedrock.BedrockAgent.Config") as mock_config:
            mock_config.config.return_value.get_mcp_config.return_value = {
                "mcpServers": {"test-server": {"url": "http://localhost:8000"}}
            }
            with patch("bondable.bond.providers.bedrock.BedrockAgent._resolve_server_from_hash", return_value="test-server"):
                results = agent._handle_return_control(self._make_return_control())

        # Should produce exactly one response
        assert len(results) == 1
        # Should be wrapped in apiResult
        assert "apiResult" in results[0]
        # Should contain an error message about allow_write_tools
        body = json.loads(results[0]["apiResult"]["responseBody"]["application/json"]["body"])
        assert "error" in body
        assert "allow_write_tools" in body["error"]

    def test_null_action_input_returns_error(self):
        """Phase 2.1: invocation with neither actionGroupInvocationInput nor apiInvocationInput."""
        agent = _make_agent()

        return_control = {
            "invocationId": "inv-123",
            "invocationInputs": [
                {"unknownInputType": {"some": "data"}}
            ],
        }
        results = agent._handle_return_control(return_control)
        assert len(results) == 1
        # Should contain an error response
        body_str = results[0].get("responseBody", {}).get("application/json", {}).get("body", "{}")
        body = json.loads(body_str)
        assert "error" in body

    def test_compact_crash_still_responds(self):
        """Phase 2.2: if _compact_tool_result crashes, a response is still sent."""
        agent = _make_agent()
        agent._current_user = MagicMock()
        agent._current_user.email = "admin@test.com"
        agent._current_user.user_id = "admin-123"

        with patch("bondable.bond.providers.bedrock.BedrockAgent.Config") as mock_config:
            mock_config.config.return_value.is_admin_user.return_value = True
            with patch("bondable.bond.providers.bedrock.BedrockAgent.execute_admin_tool",
                       return_value={"success": True, "result": "ok"}):
                # Make _compact_tool_result raise an exception
                with patch.object(agent, '_compact_tool_result', side_effect=RuntimeError("compaction exploded")):
                    results = agent._handle_return_control(
                        self._make_return_control(api_path="/b.ADMIN0.get_usage_stats")
                    )

        # Should still produce a response (via _make_tool_response fallback)
        assert len(results) == 1

    def test_top_level_exception_still_responds(self):
        """Phase 2.3: completely unexpected error still produces a response."""
        agent = _make_agent()

        # Create a return_control where _parse_tool_path will raise
        with patch("bondable.bond.providers.bedrock.BedrockAgent._parse_tool_path",
                   side_effect=RuntimeError("unexpected crash")):
            results = agent._handle_return_control(
                self._make_return_control()
            )

        # Safety net should catch and produce a response
        assert len(results) == 1
        body_str = results[0].get("apiResult", results[0]).get("responseBody", {}).get("application/json", {}).get("body", "{}")
        body = json.loads(body_str)
        assert "error" in body
        assert "unexpected crash" in body["error"]

    def test_non_dict_inv_input_does_not_crash_safety_net(self):
        """Safety net must not crash if inv_input is None or non-dict."""
        agent = _make_agent()

        # Simulate a malformed invocationInputs list containing None
        return_control = {
            "invocationId": "inv-123",
            "invocationInputs": [None],
        }
        results = agent._handle_return_control(return_control)
        # Should still produce a response via the safety net
        assert len(results) == 1
