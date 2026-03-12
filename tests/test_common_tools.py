"""
Tests for CommonToolsMCP - web tools available to all users.
"""

import json
from unittest.mock import patch, MagicMock


# =============================================================================
# CommonToolsMCP Unit Tests
# =============================================================================

class TestCommonToolsMCPPublicAPI:
    """Tests for CommonToolsMCP public functions."""

    def test_get_common_tool_definitions_structure(self):
        from bondable.bond.providers.bedrock.CommonToolsMCP import get_common_tool_definitions

        defs = get_common_tool_definitions()
        assert isinstance(defs, list)
        assert len(defs) == 2

        names = {d['name'] for d in defs}
        assert names == {"fetch_urls", "web_search"}

        for d in defs:
            assert 'name' in d
            assert 'description' in d
            assert 'inputSchema' in d
            schema = d['inputSchema']
            assert schema['type'] == 'object'
            assert 'properties' in schema
            assert 'required' in schema

    def test_is_common_tool(self):
        from bondable.bond.providers.bedrock.CommonToolsMCP import is_common_tool

        assert is_common_tool("fetch_urls") is True
        assert is_common_tool("web_search") is True
        assert is_common_tool("unknown_tool") is False
        assert is_common_tool("get_usage_stats") is False

    def test_build_common_tool_path(self):
        from bondable.bond.providers.bedrock.CommonToolsMCP import build_common_tool_path

        assert build_common_tool_path("fetch_urls") == "/b.COMN00.fetch_urls"
        assert build_common_tool_path("web_search") == "/b.COMN00.web_search"

    def test_execute_common_tool_unknown_tool(self):
        from bondable.bond.providers.bedrock.CommonToolsMCP import execute_common_tool

        result = execute_common_tool("nonexistent_tool", {})
        assert result["success"] is False
        assert "Unknown common tool" in result["error"]


# =============================================================================
# fetch_urls Handler Tests
# =============================================================================

class TestFetchUrls:
    """Tests for the fetch_urls handler."""

    @patch("trafilatura.extract")
    @patch("trafilatura.fetch_url")
    def test_fetch_single_url(self, mock_fetch, mock_extract):
        from bondable.bond.providers.bedrock.CommonToolsMCP import execute_common_tool

        mock_fetch.return_value = "<html><body>Hello World</body></html>"
        mock_extract.return_value = "# Hello World\n\nSome content here."

        result = execute_common_tool("fetch_urls", {"urls": "https://example.com"})

        assert result["success"] is True
        assert "Hello World" in result["result"]
        assert "example.com" in result["result"]
        mock_fetch.assert_called_once()
        assert mock_fetch.call_args[0][0] == "https://example.com"

    @patch("trafilatura.extract")
    @patch("trafilatura.fetch_url")
    def test_fetch_comma_separated_urls(self, mock_fetch, mock_extract):
        from bondable.bond.providers.bedrock.CommonToolsMCP import execute_common_tool

        mock_fetch.return_value = "<html>test</html>"
        mock_extract.return_value = "content"

        result = execute_common_tool("fetch_urls", {"urls": "https://a.com, https://b.com"})

        assert result["success"] is True
        assert mock_fetch.call_count == 2

    @patch("trafilatura.extract")
    @patch("trafilatura.fetch_url")
    def test_fetch_json_array_urls(self, mock_fetch, mock_extract):
        from bondable.bond.providers.bedrock.CommonToolsMCP import execute_common_tool

        mock_fetch.return_value = "<html>test</html>"
        mock_extract.return_value = "content"

        urls = json.dumps(["https://a.com", "https://b.com"])
        result = execute_common_tool("fetch_urls", {"urls": urls})

        assert result["success"] is True
        assert mock_fetch.call_count == 2

    def test_fetch_invalid_url_rejected(self):
        from bondable.bond.providers.bedrock.CommonToolsMCP import execute_common_tool

        result = execute_common_tool("fetch_urls", {"urls": "ftp://example.com"})
        assert result["success"] is False
        assert "http" in result["error"].lower()

    def test_fetch_ssrf_localhost_blocked(self):
        from bondable.bond.providers.bedrock.CommonToolsMCP import execute_common_tool

        result = execute_common_tool("fetch_urls", {"urls": "http://localhost/admin"})
        assert result["success"] is False

    def test_fetch_ssrf_private_ip_blocked(self):
        from bondable.bond.providers.bedrock.CommonToolsMCP import execute_common_tool

        result = execute_common_tool("fetch_urls", {"urls": "http://10.0.0.1/secret"})
        assert result["success"] is False

    def test_fetch_ssrf_metadata_blocked(self):
        from bondable.bond.providers.bedrock.CommonToolsMCP import execute_common_tool

        result = execute_common_tool("fetch_urls", {"urls": "http://169.254.169.254/latest/meta-data/"})
        assert result["success"] is False

    def test_fetch_ssrf_127_blocked(self):
        from bondable.bond.providers.bedrock.CommonToolsMCP import execute_common_tool

        result = execute_common_tool("fetch_urls", {"urls": "http://127.0.0.1:8080/internal"})
        assert result["success"] is False

    def test_fetch_ssrf_192_168_blocked(self):
        from bondable.bond.providers.bedrock.CommonToolsMCP import execute_common_tool

        result = execute_common_tool("fetch_urls", {"urls": "http://192.168.1.1/"})
        assert result["success"] is False

    @patch("trafilatura.extract")
    @patch("trafilatura.fetch_url")
    def test_fetch_max_5_urls(self, mock_fetch, mock_extract):
        from bondable.bond.providers.bedrock.CommonToolsMCP import execute_common_tool

        mock_fetch.return_value = "<html>test</html>"
        mock_extract.return_value = "content"

        urls = ",".join([f"https://example{i}.com" for i in range(8)])
        result = execute_common_tool("fetch_urls", {"urls": urls})

        assert result["success"] is True
        assert mock_fetch.call_count == 5
        assert "first 5" in result["result"].lower()

    @patch("trafilatura.extract")
    @patch("trafilatura.fetch_url")
    def test_fetch_network_error_per_url(self, mock_fetch, mock_extract):
        from bondable.bond.providers.bedrock.CommonToolsMCP import execute_common_tool

        # First URL fails (returns None), second succeeds
        mock_fetch.side_effect = [None, "<html>ok</html>"]
        mock_extract.return_value = "good content"

        result = execute_common_tool("fetch_urls", {"urls": "https://bad.com, https://good.com"})

        assert result["success"] is True
        assert "Could not fetch" in result["result"]
        assert "good content" in result["result"]

    @patch("trafilatura.extract")
    @patch("trafilatura.fetch_url")
    def test_fetch_empty_extraction(self, mock_fetch, mock_extract):
        from bondable.bond.providers.bedrock.CommonToolsMCP import execute_common_tool

        mock_fetch.return_value = "<html>test</html>"
        mock_extract.return_value = None

        result = execute_common_tool("fetch_urls", {"urls": "https://example.com"})

        assert result["success"] is True
        assert "No extractable content" in result["result"]

    @patch("trafilatura.extract")
    @patch("trafilatura.fetch_url")
    def test_fetch_content_truncation(self, mock_fetch, mock_extract):
        from bondable.bond.providers.bedrock.CommonToolsMCP import execute_common_tool

        mock_fetch.return_value = "<html>test</html>"
        mock_extract.return_value = "x" * 20000  # Exceeds MAX_CONTENT_PER_URL

        result = execute_common_tool("fetch_urls", {"urls": "https://example.com"})

        assert result["success"] is True
        assert "truncated" in result["result"].lower()
        # Content should be truncated to ~10000 chars + header + truncation notice
        assert len(result["result"]) < 15000

    @patch("trafilatura.extract")
    @patch("trafilatura.fetch_url")
    def test_fetch_extract_exception(self, mock_fetch, mock_extract):
        """P3-4: Test that an exception during trafilatura.extract() is handled gracefully."""
        from bondable.bond.providers.bedrock.CommonToolsMCP import execute_common_tool

        mock_fetch.return_value = "<html>test</html>"
        mock_extract.side_effect = Exception("Extraction failed unexpectedly")

        result = execute_common_tool("fetch_urls", {"urls": "https://example.com"})

        assert result["success"] is True
        assert "Error fetching URL" in result["result"]

    def test_fetch_no_urls_provided(self):
        from bondable.bond.providers.bedrock.CommonToolsMCP import execute_common_tool

        result = execute_common_tool("fetch_urls", {"urls": ""})
        assert result["success"] is False
        assert "No URLs" in result["error"]


# =============================================================================
# web_search Handler Tests
# =============================================================================

class TestWebSearch:
    """Tests for the web_search handler."""

    @patch("duckduckgo_search.DDGS")
    def test_search_basic(self, mock_ddgs_cls):
        from bondable.bond.providers.bedrock.CommonToolsMCP import execute_common_tool

        mock_ddgs = MagicMock()
        mock_ddgs_cls.return_value = mock_ddgs
        mock_ddgs.text.return_value = [
            {"title": "Result 1", "body": "Body 1", "href": "https://r1.com"},
            {"title": "Result 2", "body": "Body 2", "href": "https://r2.com"},
        ]

        result = execute_common_tool("web_search", {"query": "test query"})

        assert result["success"] is True
        assert "Result 1" in result["result"]
        assert "Result 2" in result["result"]
        assert "https://r1.com" in result["result"]
        mock_ddgs.text.assert_called_once_with("test query", max_results=5)

    @patch("duckduckgo_search.DDGS")
    def test_search_max_results_clamped(self, mock_ddgs_cls):
        from bondable.bond.providers.bedrock.CommonToolsMCP import execute_common_tool

        mock_ddgs = MagicMock()
        mock_ddgs_cls.return_value = mock_ddgs
        mock_ddgs.text.return_value = []

        execute_common_tool("web_search", {"query": "test", "max_results": 50})
        mock_ddgs.text.assert_called_once_with("test", max_results=10)

    @patch("duckduckgo_search.DDGS")
    def test_search_empty_results(self, mock_ddgs_cls):
        from bondable.bond.providers.bedrock.CommonToolsMCP import execute_common_tool

        mock_ddgs = MagicMock()
        mock_ddgs_cls.return_value = mock_ddgs
        mock_ddgs.text.return_value = []

        result = execute_common_tool("web_search", {"query": "obscure query"})

        assert result["success"] is True
        assert "No search results" in result["result"]

    @patch("duckduckgo_search.DDGS")
    def test_search_rate_limit_error(self, mock_ddgs_cls):
        from bondable.bond.providers.bedrock.CommonToolsMCP import execute_common_tool
        from duckduckgo_search.exceptions import RatelimitException

        mock_ddgs = MagicMock()
        mock_ddgs_cls.return_value = mock_ddgs
        mock_ddgs.text.side_effect = RatelimitException()

        result = execute_common_tool("web_search", {"query": "test"})

        assert result["success"] is False
        assert "rate limit" in result["error"].lower()

    @patch("duckduckgo_search.DDGS")
    def test_search_network_error(self, mock_ddgs_cls):
        from bondable.bond.providers.bedrock.CommonToolsMCP import execute_common_tool

        mock_ddgs = MagicMock()
        mock_ddgs_cls.return_value = mock_ddgs
        mock_ddgs.text.side_effect = ConnectionError("Network failure")

        result = execute_common_tool("web_search", {"query": "test"})

        assert result["success"] is False
        assert "failed" in result["error"].lower()

    def test_search_missing_query(self):
        from bondable.bond.providers.bedrock.CommonToolsMCP import execute_common_tool

        result = execute_common_tool("web_search", {"query": ""})
        assert result["success"] is False
        assert "required" in result["error"].lower()


# =============================================================================
# BedrockMCP Integration Tests
# =============================================================================

class TestBedrockMCPCommonToolIntegration:
    """Tests for common tool integration in BedrockMCP."""

    def test_parse_tool_path_common_hash(self):
        from bondable.bond.providers.bedrock.BedrockMCP import _parse_tool_path

        server_hash, tool_name = _parse_tool_path("/b.COMN00.fetch_urls")
        assert server_hash == "COMN00"
        assert tool_name == "fetch_urls"

        server_hash, tool_name = _parse_tool_path("/b.COMN00.web_search")
        assert server_hash == "COMN00"
        assert tool_name == "web_search"

    def test_common_tool_path_building(self):
        from bondable.bond.providers.bedrock.BedrockMCP import _build_common_tool_path

        assert _build_common_tool_path("fetch_urls") == "/b.COMN00.fetch_urls"
        assert _build_common_tool_path("web_search") == "/b.COMN00.web_search"

    def test_parse_tool_path_still_works_for_admin(self):
        """Ensure the regex update didn't break admin tool parsing."""
        from bondable.bond.providers.bedrock.BedrockMCP import _parse_tool_path

        server_hash, tool_name = _parse_tool_path("/b.ADMIN0.get_usage_stats")
        assert server_hash == "ADMIN0"
        assert tool_name == "get_usage_stats"

    def test_parse_tool_path_still_works_for_hex(self):
        """Ensure the regex update didn't break regular MCP tool parsing."""
        from bondable.bond.providers.bedrock.BedrockMCP import _parse_tool_path

        server_hash, tool_name = _parse_tool_path("/b.a1b2c3.my_tool")
        assert server_hash == "a1b2c3"
        assert tool_name == "my_tool"


# =============================================================================
# BedrockAgent Integration Tests
# =============================================================================

class TestBedrockAgentCommonToolRouting:
    """Tests for common tool routing in BedrockAgent."""

    @patch("bondable.bond.providers.bedrock.BedrockAgent.execute_common_tool")
    def test_route_common_tool_via_hash(self, mock_execute):
        """Test that COMN00 hash routes to execute_common_tool."""
        from bondable.bond.providers.bedrock.BedrockMCP import _parse_tool_path

        # Verify parsing works
        server_hash, tool_name = _parse_tool_path("/b.COMN00.web_search")
        assert server_hash == "COMN00"
        assert tool_name == "web_search"

        # Verify the constant matches
        from bondable.bond.providers.bedrock.CommonToolsMCP import COMMON_SERVER_HASH
        assert server_hash == COMMON_SERVER_HASH

    def test_common_tool_no_admin_check(self):
        """Verify common tools don't reference admin user checking."""
        from bondable.bond.providers.bedrock.CommonToolsMCP import execute_common_tool

        # execute_common_tool doesn't take current_user or db_session params
        import inspect
        sig = inspect.signature(execute_common_tool)
        param_names = list(sig.parameters.keys())
        assert "current_user" not in param_names
        assert "db_session_factory" not in param_names
        assert param_names == ["tool_name", "parameters"]


# =============================================================================
# MCP Router Tests
# =============================================================================

class TestMCPRouterCommonTools:
    """Tests for common tools in mcp.py router."""

    def test_common_tools_definitions_available(self):
        """Verify common tool definitions can be loaded for the router."""
        from bondable.bond.providers.bedrock.CommonToolsMCP import (
            COMMON_SERVER_NAME, COMMON_DISPLAY_NAME, COMMON_DESCRIPTION,
            get_common_tool_definitions
        )

        assert COMMON_SERVER_NAME == "common_tools"
        assert COMMON_DISPLAY_NAME == "Common Tools"
        assert len(COMMON_DESCRIPTION) > 0

        defs = get_common_tool_definitions()
        assert len(defs) == 2
        assert all('name' in d and 'description' in d and 'inputSchema' in d for d in defs)

    def test_common_tools_constants(self):
        """Verify common tool constants are properly set."""
        from bondable.bond.providers.bedrock.CommonToolsMCP import (
            COMMON_SERVER_HASH, COMMON_TOOL_NAMES
        )

        assert COMMON_SERVER_HASH == "COMN00"
        assert COMMON_TOOL_NAMES == {"fetch_urls", "web_search"}


# =============================================================================
# URL Parsing Tests
# =============================================================================

class TestURLParsing:
    """Tests for the _parse_urls helper."""

    def test_parse_single_url(self):
        from bondable.bond.providers.bedrock.CommonToolsMCP import _parse_urls

        assert _parse_urls("https://example.com") == ["https://example.com"]

    def test_parse_comma_separated(self):
        from bondable.bond.providers.bedrock.CommonToolsMCP import _parse_urls

        result = _parse_urls("https://a.com, https://b.com, https://c.com")
        assert result == ["https://a.com", "https://b.com", "https://c.com"]

    def test_parse_json_array(self):
        from bondable.bond.providers.bedrock.CommonToolsMCP import _parse_urls

        result = _parse_urls('["https://a.com", "https://b.com"]')
        assert result == ["https://a.com", "https://b.com"]

    def test_parse_empty(self):
        from bondable.bond.providers.bedrock.CommonToolsMCP import _parse_urls

        assert _parse_urls("") == []
        assert _parse_urls("   ") == []

    def test_parse_whitespace_handling(self):
        from bondable.bond.providers.bedrock.CommonToolsMCP import _parse_urls

        result = _parse_urls("  https://a.com ,  https://b.com  ")
        assert result == ["https://a.com", "https://b.com"]


# =============================================================================
# SSRF Protection Tests
# =============================================================================

class TestSSRFProtection:
    """Tests for _is_internal_url SSRF protection."""

    def test_public_url_allowed(self):
        from bondable.bond.providers.bedrock.CommonToolsMCP import _is_internal_url

        assert _is_internal_url("https://example.com") is False
        assert _is_internal_url("https://docs.python.org/3/") is False

    def test_localhost_blocked(self):
        from bondable.bond.providers.bedrock.CommonToolsMCP import _is_internal_url

        assert _is_internal_url("http://localhost/") is True
        assert _is_internal_url("http://localhost:8080/admin") is True

    def test_loopback_ip_blocked(self):
        from bondable.bond.providers.bedrock.CommonToolsMCP import _is_internal_url

        assert _is_internal_url("http://127.0.0.1/") is True
        assert _is_internal_url("http://127.0.0.1:9200/") is True

    def test_private_10_range_blocked(self):
        from bondable.bond.providers.bedrock.CommonToolsMCP import _is_internal_url

        assert _is_internal_url("http://10.0.0.1/") is True
        assert _is_internal_url("http://10.255.255.255/") is True

    def test_private_172_range_blocked(self):
        from bondable.bond.providers.bedrock.CommonToolsMCP import _is_internal_url

        assert _is_internal_url("http://172.16.0.1/") is True
        assert _is_internal_url("http://172.31.255.255/") is True

    def test_private_192_168_blocked(self):
        from bondable.bond.providers.bedrock.CommonToolsMCP import _is_internal_url

        assert _is_internal_url("http://192.168.0.1/") is True
        assert _is_internal_url("http://192.168.1.100/") is True

    def test_aws_metadata_blocked(self):
        from bondable.bond.providers.bedrock.CommonToolsMCP import _is_internal_url

        assert _is_internal_url("http://169.254.169.254/latest/meta-data/") is True

    def test_zero_ip_blocked(self):
        from bondable.bond.providers.bedrock.CommonToolsMCP import _is_internal_url

        assert _is_internal_url("http://0.0.0.0/") is True

    def test_blocked_hostnames_from_env(self):
        """Verify SSRF_BLOCKED_HOSTNAMES env var overrides defaults."""
        from bondable.bond.providers.bedrock import CommonToolsMCP as mod

        with patch.dict("os.environ", {"SSRF_BLOCKED_HOSTNAMES": "evil.com,badhost"}):
            reloaded = mod._load_blocked_hostnames()
            assert reloaded == {"evil.com", "badhost"}

    def test_blocked_hostnames_default_when_unset(self):
        """Verify defaults are used when env var is not set."""
        from bondable.bond.providers.bedrock import CommonToolsMCP as mod

        with patch.dict("os.environ", {}, clear=True):
            reloaded = mod._load_blocked_hostnames()
            assert "localhost" in reloaded
            assert "127.0.0.1" in reloaded
            assert "metadata.google.internal" in reloaded
