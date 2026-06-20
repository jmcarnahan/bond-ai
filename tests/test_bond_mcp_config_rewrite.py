"""Unit tests for the BOND_FRONT_DOOR_URL rewrite in `get_mcp_config`.

The rewrite lets combined-mode local dev (nginx on :8080) reuse the developer's
normal split-mode BOND_MCP_CONFIG: any oauth_config.redirect_uri pointing at
http://localhost:8000 or http://127.0.0.1:8000 is rewritten to use the front
door. Production URLs (https://, other hosts) are left alone.
"""
import copy
import json
import os
from unittest.mock import patch

import pytest

from bondable.bond.config import _rewrite_redirect_uris_for_front_door, Config


SPLIT_MODE_CONFIG = {
    "mcpServers": {
        "atlassian": {
            "url": "http://localhost:9000/mcp",
            "auth_type": "oauth2",
            "transport": "streamable-http",
            "oauth_config": {
                "provider": "atlassian",
                "client_id": "x",
                "client_secret": "y",
                "redirect_uri": "http://localhost:8000/connections/atlassian/callback",
            },
        },
        "github": {
            "url": "http://localhost:9001/mcp",
            "auth_type": "oauth2",
            "transport": "streamable-http",
            "oauth_config": {
                "provider": "github",
                "redirect_uri": "http://127.0.0.1:8000/connections/github/callback",
            },
        },
        "prod_service": {
            "url": "https://prod-mcp.example.com/mcp",
            "auth_type": "oauth2",
            "oauth_config": {
                "provider": "prod",
                "redirect_uri": "https://api.example.com/connections/prod_service/callback",
            },
        },
        "plain_server": {
            "url": "http://127.0.0.1:5555/mcp",
            "transport": "streamable-http",
        },
    }
}


def test_no_env_var_returns_config_unchanged():
    cfg = copy.deepcopy(SPLIT_MODE_CONFIG)
    with patch.dict(os.environ, {}, clear=False):
        os.environ.pop("BOND_FRONT_DOOR_URL", None)
        result = _rewrite_redirect_uris_for_front_door(cfg)
    assert result is cfg
    assert result["mcpServers"]["atlassian"]["oauth_config"]["redirect_uri"] == (
        "http://localhost:8000/connections/atlassian/callback"
    )


def test_rewrites_localhost_8000_oauth_redirect():
    cfg = copy.deepcopy(SPLIT_MODE_CONFIG)
    with patch.dict(os.environ, {"BOND_FRONT_DOOR_URL": "http://localhost:8080"}):
        result = _rewrite_redirect_uris_for_front_door(cfg)
    assert result["mcpServers"]["atlassian"]["oauth_config"]["redirect_uri"] == (
        "http://localhost:8080/connections/atlassian/callback"
    )


def test_rewrites_127_0_0_1_8000_oauth_redirect():
    cfg = copy.deepcopy(SPLIT_MODE_CONFIG)
    with patch.dict(os.environ, {"BOND_FRONT_DOOR_URL": "http://localhost:8080"}):
        result = _rewrite_redirect_uris_for_front_door(cfg)
    assert result["mcpServers"]["github"]["oauth_config"]["redirect_uri"] == (
        "http://localhost:8080/connections/github/callback"
    )


def test_leaves_production_https_urls_untouched():
    cfg = copy.deepcopy(SPLIT_MODE_CONFIG)
    with patch.dict(os.environ, {"BOND_FRONT_DOOR_URL": "http://localhost:8080"}):
        result = _rewrite_redirect_uris_for_front_door(cfg)
    assert result["mcpServers"]["prod_service"]["oauth_config"]["redirect_uri"] == (
        "https://api.example.com/connections/prod_service/callback"
    )


def test_leaves_servers_without_oauth_config_untouched():
    cfg = copy.deepcopy(SPLIT_MODE_CONFIG)
    with patch.dict(os.environ, {"BOND_FRONT_DOOR_URL": "http://localhost:8080"}):
        result = _rewrite_redirect_uris_for_front_door(cfg)
    plain = result["mcpServers"]["plain_server"]
    assert "oauth_config" not in plain
    assert plain["url"] == "http://127.0.0.1:5555/mcp"


def test_leaves_mcp_server_url_field_untouched():
    """The `url` field (server endpoint, server-to-server) is NOT routed
    through nginx — only the browser-facing oauth_config.redirect_uri is."""
    cfg = copy.deepcopy(SPLIT_MODE_CONFIG)
    with patch.dict(os.environ, {"BOND_FRONT_DOOR_URL": "http://localhost:8080"}):
        result = _rewrite_redirect_uris_for_front_door(cfg)
    assert result["mcpServers"]["atlassian"]["url"] == "http://localhost:9000/mcp"


def test_trailing_slash_on_front_door_url_is_normalized():
    cfg = copy.deepcopy(SPLIT_MODE_CONFIG)
    with patch.dict(os.environ, {"BOND_FRONT_DOOR_URL": "http://localhost:8080/"}):
        result = _rewrite_redirect_uris_for_front_door(cfg)
    assert result["mcpServers"]["atlassian"]["oauth_config"]["redirect_uri"] == (
        "http://localhost:8080/connections/atlassian/callback"
    )


def test_https_front_door_url_works():
    cfg = copy.deepcopy(SPLIT_MODE_CONFIG)
    with patch.dict(os.environ, {"BOND_FRONT_DOOR_URL": "https://app.example.com"}):
        result = _rewrite_redirect_uris_for_front_door(cfg)
    assert result["mcpServers"]["atlassian"]["oauth_config"]["redirect_uri"] == (
        "https://app.example.com/connections/atlassian/callback"
    )


def test_empty_string_env_var_treated_as_unset():
    cfg = copy.deepcopy(SPLIT_MODE_CONFIG)
    with patch.dict(os.environ, {"BOND_FRONT_DOOR_URL": "  "}):
        result = _rewrite_redirect_uris_for_front_door(cfg)
    assert result["mcpServers"]["atlassian"]["oauth_config"]["redirect_uri"] == (
        "http://localhost:8000/connections/atlassian/callback"
    )


def test_empty_mcp_servers_dict_does_not_error():
    cfg = {"mcpServers": {}}
    with patch.dict(os.environ, {"BOND_FRONT_DOOR_URL": "http://localhost:8080"}):
        result = _rewrite_redirect_uris_for_front_door(cfg)
    assert result == {"mcpServers": {}}


def test_logs_rewrite_count():
    cfg = copy.deepcopy(SPLIT_MODE_CONFIG)
    with patch.dict(os.environ, {"BOND_FRONT_DOOR_URL": "http://localhost:8080"}):
        with patch("bondable.bond.config.LOGGER") as mock_logger:
            _rewrite_redirect_uris_for_front_door(cfg)
    info_calls = [c.args[0] for c in mock_logger.info.call_args_list]
    assert any(
        "Rewrote 2 MCP redirect URI(s)" in msg and "http://localhost:8080" in msg
        for msg in info_calls
    ), f"expected rewrite log line, got info calls: {info_calls}"


def test_no_log_line_when_env_var_unset():
    cfg = copy.deepcopy(SPLIT_MODE_CONFIG)
    with patch.dict(os.environ, {}, clear=False):
        os.environ.pop("BOND_FRONT_DOOR_URL", None)
        with patch("bondable.bond.config.LOGGER") as mock_logger:
            _rewrite_redirect_uris_for_front_door(cfg)
    info_calls = [c.args[0] for c in mock_logger.info.call_args_list]
    assert not any("Rewrote" in msg and "MCP redirect URI" in msg for msg in info_calls)


def test_get_mcp_config_env_path_applies_rewrite():
    env_json = json.dumps(
        {
            "mcpServers": {
                "atlassian": {
                    "url": "http://localhost:9000/mcp",
                    "oauth_config": {
                        "provider": "atlassian",
                        "redirect_uri": "http://localhost:8000/connections/atlassian/callback",
                    },
                }
            }
        }
    )
    with patch.dict(
        os.environ,
        {"BOND_MCP_CONFIG": env_json, "BOND_FRONT_DOOR_URL": "http://localhost:8080"},
    ):
        cfg_instance = Config.__new__(Config)
        cfg_instance.__init__()
        try:
            mcp_config = cfg_instance.get_mcp_config()
        finally:
            cfg_instance.__del__()
    assert mcp_config["mcpServers"]["atlassian"]["oauth_config"]["redirect_uri"] == (
        "http://localhost:8080/connections/atlassian/callback"
    )
