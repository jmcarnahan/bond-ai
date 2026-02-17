"""
Unit tests for _handle_return_control tool result status codes.

Verifies that all tool results return httpStatusCode 200 to Bedrock so the LLM
can see errors and self-correct. Non-200 codes cause dependencyFailedException
in Bedrock, preventing the LLM from reading the error message.
"""

import json
import pytest
from unittest.mock import MagicMock, patch


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


def _make_return_control_for_admin(tool_name="list_agents"):
    """Create a returnControl event for an admin tool invocation."""
    return {
        "invocationId": "inv-456",
        "invocationInputs": [
            {
                "apiInvocationInput": {
                    "actionGroupName": "admin-action-group",
                    "apiPath": f"/b.ADMIN0.{tool_name}",
                    "httpMethod": "POST",
                    "parameters": []
                }
            }
        ]
    }


class TestMCPToolResultStatusCodes:
    """Tests that MCP tool results always use httpStatusCode 200."""

    @patch("bondable.bond.providers.bedrock.BedrockAgent._resolve_server_from_hash")
    @patch("bondable.bond.providers.bedrock.BedrockAgent.execute_mcp_tool_sync")
    @patch("bondable.bond.providers.bedrock.BedrockAgent.Config")
    def test_mcp_tool_success_returns_200(self, mock_config, mock_execute, mock_resolve):
        """Successful MCP tool execution should return 200."""
        agent = _make_agent()

        mock_config.config.return_value.get_mcp_config.return_value = {"mcpServers": {"atlassian": {}}}
        mock_resolve.return_value = "atlassian"
        mock_execute.return_value = {
            "success": True,
            "result": {"issues": [{"key": "TEST-1"}]}
        }

        return_control = _make_return_control_for_mcp()
        results = agent._handle_return_control(return_control)

        assert len(results) == 1
        api_result = results[0]["apiResult"]
        assert api_result["httpStatusCode"] == 200

    @patch("bondable.bond.providers.bedrock.BedrockAgent._resolve_server_from_hash")
    @patch("bondable.bond.providers.bedrock.BedrockAgent.execute_mcp_tool_sync")
    @patch("bondable.bond.providers.bedrock.BedrockAgent.Config")
    def test_mcp_tool_failure_returns_200_not_500(self, mock_config, mock_execute, mock_resolve):
        """Failed MCP tool execution should return 200 (not 500) so LLM can see the error."""
        agent = _make_agent()

        mock_config.config.return_value.get_mcp_config.return_value = {"mcpServers": {"atlassian": {}}}
        mock_resolve.return_value = "atlassian"
        mock_execute.return_value = {
            "success": False,
            "error": "Unbounded JQL queries are not allowed here."
        }

        return_control = _make_return_control_for_mcp()
        results = agent._handle_return_control(return_control)

        assert len(results) == 1
        api_result = results[0]["apiResult"]
        # Key assertion: should be 200 even though tool failed
        assert api_result["httpStatusCode"] == 200
        # Error message should be in the response body for the LLM to read
        body = json.loads(api_result["responseBody"]["application/json"]["body"])
        assert "Unbounded JQL" in body["result"]

    @patch("bondable.bond.providers.bedrock.BedrockAgent._resolve_server_from_hash")
    @patch("bondable.bond.providers.bedrock.BedrockAgent.execute_mcp_tool_sync")
    @patch("bondable.bond.providers.bedrock.BedrockAgent.Config")
    def test_mcp_tool_exception_returns_200_with_error(self, mock_config, mock_execute, mock_resolve):
        """When execute_mcp_tool_sync raises an exception, should return 200 so LLM sees the error."""
        agent = _make_agent()

        mock_config.config.return_value.get_mcp_config.return_value = {"mcpServers": {"atlassian": {}}}
        mock_resolve.return_value = "atlassian"
        mock_execute.side_effect = ConnectionError("MCP server unreachable")

        return_control = _make_return_control_for_mcp()
        results = agent._handle_return_control(return_control)

        assert len(results) == 1
        api_result = results[0]["apiResult"]
        assert api_result["httpStatusCode"] == 200

    @patch("bondable.bond.providers.bedrock.BedrockAgent.Config")
    def test_no_mcp_config_returns_200_with_error(self, mock_config):
        """When MCP config is not available, should return 200 so LLM sees the error."""
        agent = _make_agent()

        mock_config.config.return_value.get_mcp_config.return_value = None

        return_control = _make_return_control_for_mcp()
        results = agent._handle_return_control(return_control)

        assert len(results) == 1
        api_result = results[0]["apiResult"]
        assert api_result["httpStatusCode"] == 200

    def test_unrecognized_tool_path_returns_200_with_error(self):
        """Unrecognized tool path format should return 200 so LLM sees the error."""
        agent = _make_agent()

        return_control = {
            "invocationId": "inv-789",
            "invocationInputs": [
                {
                    "apiInvocationInput": {
                        "actionGroupName": "test-group",
                        "apiPath": "/some/unknown/path",
                        "httpMethod": "POST",
                        "parameters": []
                    }
                }
            ]
        }
        results = agent._handle_return_control(return_control)

        assert len(results) == 1
        api_result = results[0]["apiResult"]
        assert api_result["httpStatusCode"] == 200
        body = json.loads(api_result["responseBody"]["application/json"]["body"])
        assert "not recognized" in body["error"]


class TestAdminToolResultStatusCodes:
    """Tests that admin tool results always use httpStatusCode 200."""

    @patch("bondable.bond.providers.bedrock.BedrockAgent.execute_admin_tool")
    @patch("bondable.bond.providers.bedrock.BedrockAgent.Config")
    def test_admin_tool_success_returns_200(self, mock_config, mock_execute_admin):
        """Successful admin tool execution should return 200."""
        agent = _make_agent()

        # Set up admin user
        mock_user = MagicMock()
        mock_user.email = "admin@example.com"
        agent._current_user = mock_user
        mock_config.config.return_value.is_admin_user.return_value = True

        mock_execute_admin.return_value = {
            "success": True,
            "result": {"agents": []}
        }

        return_control = _make_return_control_for_admin()
        results = agent._handle_return_control(return_control)

        assert len(results) == 1
        api_result = results[0]["apiResult"]
        assert api_result["httpStatusCode"] == 200

    @patch("bondable.bond.providers.bedrock.BedrockAgent.execute_admin_tool")
    @patch("bondable.bond.providers.bedrock.BedrockAgent.Config")
    def test_admin_tool_failure_returns_200_not_500(self, mock_config, mock_execute_admin):
        """Failed admin tool execution should return 200 so LLM can relay the error."""
        agent = _make_agent()

        mock_user = MagicMock()
        mock_user.email = "admin@example.com"
        agent._current_user = mock_user
        mock_config.config.return_value.is_admin_user.return_value = True

        mock_execute_admin.return_value = {
            "success": False,
            "error": "Agent not found"
        }

        return_control = _make_return_control_for_admin()
        results = agent._handle_return_control(return_control)

        assert len(results) == 1
        api_result = results[0]["apiResult"]
        # Key assertion: should be 200 even though tool failed
        assert api_result["httpStatusCode"] == 200
        body = json.loads(api_result["responseBody"]["application/json"]["body"])
        assert "Agent not found" in body["result"]

    @patch("bondable.bond.providers.bedrock.BedrockAgent.Config")
    def test_admin_tool_non_admin_user_returns_200(self, mock_config):
        """Non-admin user attempting admin tool should return 200 with error for LLM."""
        agent = _make_agent()

        mock_user = MagicMock()
        mock_user.email = "user@example.com"
        agent._current_user = mock_user
        mock_config.config.return_value.is_admin_user.return_value = False

        return_control = _make_return_control_for_admin()
        results = agent._handle_return_control(return_control)

        assert len(results) == 1
        api_result = results[0]["apiResult"]
        assert api_result["httpStatusCode"] == 200
        body = json.loads(api_result["responseBody"]["application/json"]["body"])
        assert "Admin access required" in body["result"]


class TestToolResultLLMSelfCorrection:
    """Integration-style tests verifying the LLM can self-correct after tool errors."""

    @patch("bondable.bond.providers.bedrock.BedrockAgent._resolve_server_from_hash")
    @patch("bondable.bond.providers.bedrock.BedrockAgent.execute_mcp_tool_sync")
    @patch("bondable.bond.providers.bedrock.BedrockAgent.Config")
    def test_tool_error_then_retry_succeeds(self, mock_config, mock_execute, mock_resolve):
        """Simulates the real scenario: first call fails, LLM retries with better params."""
        agent = _make_agent()

        mock_config.config.return_value.get_mcp_config.return_value = {"mcpServers": {"atlassian": {}}}
        mock_resolve.return_value = "atlassian"

        # First call fails, second succeeds
        mock_execute.side_effect = [
            {"success": False, "error": "Unbounded JQL queries are not allowed"},
            {"success": True, "result": {"issues": [{"key": "CCS-6", "summary": "Test"}]}}
        ]

        # First call - tool fails
        return_control_1 = _make_return_control_for_mcp()
        results_1 = agent._handle_return_control(return_control_1)
        api_result_1 = results_1[0]["apiResult"]
        assert api_result_1["httpStatusCode"] == 200  # LLM will see this
        body_1 = json.loads(api_result_1["responseBody"]["application/json"]["body"])
        assert "Unbounded" in body_1["result"]  # Error is readable by LLM

        # Second call - LLM retries with better JQL (simulated)
        return_control_2 = _make_return_control_for_mcp()
        results_2 = agent._handle_return_control(return_control_2)
        api_result_2 = results_2[0]["apiResult"]
        assert api_result_2["httpStatusCode"] == 200
        body_2 = json.loads(api_result_2["responseBody"]["application/json"]["body"])
        result_data = json.loads(body_2["result"]) if isinstance(body_2["result"], str) else body_2["result"]
        assert "issues" in result_data
