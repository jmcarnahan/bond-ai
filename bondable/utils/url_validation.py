"""
URL validation utilities for security-sensitive redirect operations.

This module provides validation for redirect URLs to prevent open redirect
vulnerabilities. It uses a combination of default allowed domains and an
optional environment variable for additional domains.

Default Allowed Domains:
- localhost, 127.0.0.1, 0.0.0.0 (development)
- *.awsapprunner.com (AWS App Runner deployments)

Environment Variable:
- ALLOWED_REDIRECT_DOMAINS: Comma-separated list of additional allowed domains
  Example: "example.com,api.example.com,staging.example.com"

Usage:
    from bondable.utils.url_validation import is_safe_redirect_url, validate_redirect_url_or_raise

    # Check if URL is safe
    if is_safe_redirect_url(url):
        return RedirectResponse(url=url)

    # Or validate and raise if invalid
    validated_url = validate_redirect_url_or_raise(url)
"""

import logging
import os
from urllib.parse import urlparse
from typing import Set

LOGGER = logging.getLogger(__name__)

# Default localhost-like domains always allowed for development
DEFAULT_LOCALHOST_DOMAINS = frozenset({
    'localhost',
    '127.0.0.1',
    '0.0.0.0',
    '[::1]',  # IPv6 localhost
})

# Default domain suffixes always allowed
DEFAULT_ALLOWED_SUFFIXES = frozenset({
    '.awsapprunner.com',  # AWS App Runner deployments
})


def get_allowed_redirect_domains() -> Set[str]:
    """
    Get the set of allowed redirect domains from environment configuration.

    Combines default localhost domains with any additional domains specified
    in the ALLOWED_REDIRECT_DOMAINS environment variable.

    Returns:
        Set of allowed domain strings (lowercase)
    """
    # Start with default localhost domains
    allowed = set(DEFAULT_LOCALHOST_DOMAINS)

    # Add any domains from environment variable
    allowed_domains_str = os.getenv('ALLOWED_REDIRECT_DOMAINS', '')
    if allowed_domains_str:
        for domain in allowed_domains_str.split(','):
            domain = domain.strip().lower()
            if domain:
                allowed.add(domain)

    return allowed


def is_safe_redirect_url(url: str) -> bool:
    """
    Validate that a redirect URL is safe to use.

    A URL is considered safe if:
    - It's a relative URL starting with '/' (but not '//')
    - It has http/https scheme AND hostname matches one of:
      - A localhost-like domain (localhost, 127.0.0.1, 0.0.0.0, [::1])
      - An AWS App Runner domain (*.awsapprunner.com)
      - A domain in ALLOWED_REDIRECT_DOMAINS environment variable
      - A subdomain of any allowed domain

    Args:
        url: The URL to validate

    Returns:
        True if the URL is safe for redirects, False otherwise
    """
    if not url:
        return False

    try:
        parsed = urlparse(url)

        # Handle relative URLs
        if not parsed.scheme and not parsed.netloc:
            # Relative URLs starting with '/' are safe
            # But '//' is a protocol-relative URL and should be rejected
            if url.startswith('/') and not url.startswith('//'):
                return True
            return False

        # Must have both scheme and netloc for absolute URLs
        if not parsed.scheme or not parsed.netloc:
            return False

        # Only allow http and https schemes
        if parsed.scheme not in ('http', 'https'):
            LOGGER.warning(f"Rejected redirect URL with invalid scheme: {parsed.scheme}")
            return False

        # Extract hostname (handles port numbers)
        hostname = parsed.hostname
        if not hostname:
            return False

        hostname = hostname.lower()

        # Check against explicitly allowed domains
        allowed_domains = get_allowed_redirect_domains()
        if hostname in allowed_domains:
            return True

        # Check against allowed suffixes (e.g., *.awsapprunner.com)
        for suffix in DEFAULT_ALLOWED_SUFFIXES:
            if hostname.endswith(suffix):
                return True

        # Check for subdomain matches of allowed domains
        for domain in allowed_domains:
            if hostname.endswith(f'.{domain}'):
                return True

        LOGGER.warning(f"Rejected redirect URL with disallowed domain: {hostname}")
        return False

    except Exception as e:
        LOGGER.error(
            "Error validating redirect URL: %s: %s",
            type(e).__name__,
            e,
        )
        return False


def validate_redirect_url_or_raise(url: str, context: str = "redirect") -> str:
    """
    Validate a redirect URL and raise ValueError if invalid.

    Args:
        url: The URL to validate
        context: Context string for error messages

    Returns:
        The validated URL (unchanged)

    Raises:
        ValueError: If the URL is not safe for redirects
    """
    if not is_safe_redirect_url(url):
        raise ValueError(
            f"Invalid {context} URL: domain not in allowed list. "
            f"Set ALLOWED_REDIRECT_DOMAINS environment variable to allow additional domains."
        )
    return url
