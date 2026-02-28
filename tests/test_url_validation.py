"""Tests for bondable.utils.url_validation module."""

import os
import pytest
from unittest.mock import patch

from bondable.utils.url_validation import (
    is_safe_redirect_url,
    validate_redirect_url_or_raise,
    get_allowed_redirect_domains,
    DEFAULT_LOCALHOST_DOMAINS,
)


class TestDefaultLocalhostDomains:
    """Verify the hardcoded domain allow-list."""

    def test_localhost_allowed(self):
        assert 'localhost' in DEFAULT_LOCALHOST_DOMAINS

    def test_ipv4_loopback_allowed(self):
        assert '127.0.0.1' in DEFAULT_LOCALHOST_DOMAINS

    def test_ipv6_loopback_allowed(self):
        assert '::1' in DEFAULT_LOCALHOST_DOMAINS

    def test_0000_not_allowed(self):
        """0.0.0.0 is deliberately excluded — it binds all interfaces."""
        assert '0.0.0.0' not in DEFAULT_LOCALHOST_DOMAINS


class TestIsSafeRedirectUrl:
    """Tests for is_safe_redirect_url()."""

    # --- Allowed: localhost variants ---

    def test_localhost_http(self):
        assert is_safe_redirect_url("http://localhost/callback") is True

    def test_localhost_https(self):
        assert is_safe_redirect_url("https://localhost/callback") is True

    def test_localhost_with_port(self):
        assert is_safe_redirect_url("http://localhost:3000/callback") is True

    def test_127_0_0_1(self):
        assert is_safe_redirect_url("http://127.0.0.1/callback") is True

    def test_127_0_0_1_with_port(self):
        assert is_safe_redirect_url("http://127.0.0.1:8080/callback") is True

    def test_ipv6_loopback(self):
        assert is_safe_redirect_url("http://[::1]/callback") is True

    # --- Rejected: 0.0.0.0 ---

    def test_0000_rejected(self):
        assert is_safe_redirect_url("http://0.0.0.0/callback") is False

    def test_0000_with_port_rejected(self):
        assert is_safe_redirect_url("http://0.0.0.0:8080/callback") is False

    # --- Allowed: App Runner suffix ---

    def test_apprunner_domain(self):
        assert is_safe_redirect_url("https://abc123.us-west-2.awsapprunner.com/callback") is True

    def test_apprunner_no_path(self):
        assert is_safe_redirect_url("https://abc123.us-west-2.awsapprunner.com") is True

    # --- Allowed: relative URLs ---

    def test_relative_path(self):
        assert is_safe_redirect_url("/callback") is True

    def test_relative_path_with_query(self):
        assert is_safe_redirect_url("/callback?code=abc") is True

    # --- Rejected: protocol-relative ---

    def test_protocol_relative_rejected(self):
        assert is_safe_redirect_url("//evil.com/callback") is False

    # --- Rejected: bad schemes ---

    def test_javascript_scheme_rejected(self):
        assert is_safe_redirect_url("javascript:alert(1)") is False

    def test_ftp_scheme_rejected(self):
        assert is_safe_redirect_url("ftp://evil.com/file") is False

    def test_data_scheme_rejected(self):
        assert is_safe_redirect_url("data:text/html,<h1>x</h1>") is False

    # --- Rejected: external domains ---

    def test_external_domain_rejected(self):
        assert is_safe_redirect_url("https://evil.com/callback") is False

    def test_external_with_localhost_substring_rejected(self):
        """Ensure 'localhost' substring in a different domain doesn't match."""
        assert is_safe_redirect_url("https://notlocalhost.com/callback") is False

    # --- Rejected: empty / None-like ---

    def test_empty_string_rejected(self):
        assert is_safe_redirect_url("") is False

    def test_none_rejected(self):
        assert is_safe_redirect_url(None) is False

    # --- Subdomain matching ---

    def test_subdomain_of_localhost_allowed(self):
        assert is_safe_redirect_url("http://app.localhost/callback") is True

    # --- Environment variable override ---

    @patch.dict(os.environ, {"ALLOWED_REDIRECT_DOMAINS": "myapp.internal,staging.myapp.internal"})
    def test_env_var_domain_allowed(self):
        assert is_safe_redirect_url("https://myapp.internal/callback") is True

    @patch.dict(os.environ, {"ALLOWED_REDIRECT_DOMAINS": "myapp.internal"})
    def test_env_var_subdomain_allowed(self):
        assert is_safe_redirect_url("https://api.myapp.internal/callback") is True

    @patch.dict(os.environ, {"ALLOWED_REDIRECT_DOMAINS": "myapp.internal"})
    def test_env_var_different_domain_rejected(self):
        assert is_safe_redirect_url("https://evil.com/callback") is False


class TestValidateRedirectUrlOrRaise:
    """Tests for validate_redirect_url_or_raise()."""

    def test_valid_url_returned(self):
        url = "http://localhost/callback"
        assert validate_redirect_url_or_raise(url) == url

    def test_invalid_url_raises(self):
        with pytest.raises(ValueError, match="domain not in allowed list"):
            validate_redirect_url_or_raise("https://evil.com/callback")

    def test_custom_context_in_error(self):
        with pytest.raises(ValueError, match="Invalid oauth"):
            validate_redirect_url_or_raise("https://evil.com", context="oauth")


class TestGetAllowedRedirectDomains:
    """Tests for get_allowed_redirect_domains()."""

    def test_defaults_include_localhost(self):
        domains = get_allowed_redirect_domains()
        assert 'localhost' in domains
        assert '127.0.0.1' in domains

    def test_defaults_exclude_0000(self):
        domains = get_allowed_redirect_domains()
        assert '0.0.0.0' not in domains

    @patch.dict(os.environ, {"ALLOWED_REDIRECT_DOMAINS": " MyApp.INTERNAL , foo.bar "})
    def test_env_var_trimmed_and_lowered(self):
        domains = get_allowed_redirect_domains()
        assert 'myapp.internal' in domains
        assert 'foo.bar' in domains

    @patch.dict(os.environ, {"ALLOWED_REDIRECT_DOMAINS": ""})
    def test_empty_env_var(self):
        domains = get_allowed_redirect_domains()
        # Should just be the defaults
        assert domains == {'localhost', '127.0.0.1', '::1'}
