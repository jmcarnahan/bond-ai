"""
Common Tools MCP - Web tools available to all users.

Provides MCP-like tools for web browsing and search, available to all users
(not gated to admins). These tools are executed internally without external
MCP server calls.

Tool path format: /b.COMN00.{tool_name}
- The "COMN00" hash is a reserved identifier for common tools
- This format matches the standard MCP tool path format for seamless integration
"""

import copy
import ipaddress
import json
import logging
import os
from typing import Dict, Any, List, Set
from urllib.parse import urlparse

LOGGER = logging.getLogger(__name__)

# =============================================================================
# Constants
# =============================================================================

# Explicit timeout configuration for trafilatura URL fetching
def _create_trafilatura_config():
    from trafilatura.settings import use_config
    config = use_config()
    config.set("DEFAULT", "DOWNLOAD_TIMEOUT", "30")
    return config

_TRAFILATURA_CONFIG = _create_trafilatura_config()

# Special 6-character "hash" for common tools (matches the /b.{hash6}.{tool} format)
# This is NOT a real hash - it's a reserved identifier that won't collide with
# actual server name hashes (which are hex characters only: 0-9, a-f)
COMMON_SERVER_HASH = "COMN00"

# Server identification for tool listing
COMMON_SERVER_NAME = "common_tools"
COMMON_DISPLAY_NAME = "Common Tools"
COMMON_DESCRIPTION = "Built-in tools for web browsing and search"

# Set of common tool names for quick lookup
COMMON_TOOL_NAMES = {"fetch_urls", "web_search"}

# =============================================================================
# Tool Definitions (MCP-compatible schema format)
# =============================================================================

COMMON_TOOL_DEFINITIONS = [
    {
        "name": "fetch_urls",
        "description": "Fetch one or more URLs and return their content as condensed markdown. Useful for reading web pages, documentation, articles, and other online content.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "urls": {
                    "type": "string",
                    "description": "URLs to fetch. Can be a comma-separated list or a JSON array of URLs. Maximum 5 URLs per request."
                }
            },
            "required": ["urls"]
        }
    },
    {
        "name": "web_search",
        "description": "Search the web for information using a text query. Returns a list of relevant results with titles, snippets, and links.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The search query to look up on the web"
                },
                "max_results": {
                    "type": "integer",
                    "description": "Maximum number of search results to return (default 5, max 10)"
                }
            },
            "required": ["query"]
        }
    }
]

# Per-URL content truncation limit (characters)
MAX_CONTENT_PER_URL = 10000

# Blocked hostnames for SSRF protection.
# Override via SSRF_BLOCKED_HOSTNAMES env var (comma-separated).
_DEFAULT_BLOCKED_HOSTNAMES = "localhost,127.0.0.1,0.0.0.0,[::1],metadata.google.internal"  # nosec B104


def _load_blocked_hostnames() -> Set[str]:
    raw = os.environ.get("SSRF_BLOCKED_HOSTNAMES", _DEFAULT_BLOCKED_HOSTNAMES)
    return {h.strip().lower() for h in raw.split(",") if h.strip()}


_BLOCKED_HOSTNAMES = _load_blocked_hostnames()


# =============================================================================
# Public Functions
# =============================================================================

def get_common_tool_definitions() -> List[Dict[str, Any]]:
    """
    Get the list of common tool definitions.

    Returns:
        List of tool definition dictionaries with name, description, and inputSchema
    """
    return copy.deepcopy(COMMON_TOOL_DEFINITIONS)


def is_common_tool(tool_name: str) -> bool:
    """
    Check if a tool name is a common tool.

    Args:
        tool_name: Name of the tool to check

    Returns:
        True if the tool is a common tool
    """
    return tool_name in COMMON_TOOL_NAMES


def build_common_tool_path(tool_name: str) -> str:
    """
    Build the API path for a common tool.

    Args:
        tool_name: Name of the common tool

    Returns:
        Tool path in format /b.COMN00.{tool_name}
    """
    return f"/b.{COMMON_SERVER_HASH}.{tool_name}"


def execute_common_tool(
    tool_name: str,
    parameters: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Execute a common tool and return results.

    Args:
        tool_name: Name of the common tool to execute
        parameters: Parameters for the tool (from Bedrock)

    Returns:
        Dictionary with 'success' and 'result' or 'error' fields
    """
    handlers = {
        "fetch_urls": _handle_fetch_urls,
        "web_search": _handle_web_search,
    }

    handler = handlers.get(tool_name)
    if not handler:
        LOGGER.warning(f"[Common Tools] Unknown common tool requested: {tool_name}")
        return {"success": False, "error": f"Unknown common tool: {tool_name}"}

    LOGGER.info(f"[Common Tools] Executing tool '{tool_name}'")
    LOGGER.debug(f"[Common Tools] Tool parameters: {parameters}")

    try:
        result = handler(parameters)
        LOGGER.info(f"[Common Tools] Tool '{tool_name}' completed successfully")
        return result
    except Exception as e:
        LOGGER.exception(f"[Common Tools] Error executing tool '{tool_name}': {e}")
        return {"success": False, "error": str(e)}


# =============================================================================
# Tool Handlers
# =============================================================================

def _is_internal_url(url: str) -> bool:
    """
    Check if a URL points to an internal/private network address.

    Blocks requests to localhost, private IP ranges (10.x, 172.16-31.x, 192.168.x),
    link-local (169.254.x), and cloud metadata endpoints to prevent SSRF attacks.

    Args:
        url: URL string to check

    Returns:
        True if the URL targets an internal address
    """
    try:
        parsed = urlparse(url)
        hostname = parsed.hostname
        if not hostname:
            return True  # No hostname = reject

        # Check blocked hostnames
        if hostname.lower() in _BLOCKED_HOSTNAMES:
            return True

        # Try to parse as IP address and check if private/reserved
        try:
            ip = ipaddress.ip_address(hostname)
            if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
                return True
        except ValueError:
            pass  # Not an IP address, it's a hostname - allow it

        return False
    except Exception:
        return True  # If we can't parse it, reject it


def _parse_urls(urls_param: str) -> List[str]:
    """
    Parse URLs from a string parameter.

    Accepts either a JSON array or comma-separated list of URLs.

    Args:
        urls_param: String containing URLs

    Returns:
        List of URL strings
    """
    if not urls_param or not urls_param.strip():
        return []

    urls_param = urls_param.strip()

    # Try JSON array first
    try:
        parsed = json.loads(urls_param)
        if isinstance(parsed, list):
            return [str(u).strip() for u in parsed if str(u).strip()]
    except (json.JSONDecodeError, TypeError):
        pass

    # Fall back to comma-separated
    return [u.strip() for u in urls_param.split(',') if u.strip()]


def _handle_fetch_urls(parameters: Dict[str, Any]) -> Dict[str, Any]:
    """
    Fetch URLs and return their content as markdown.

    Args:
        parameters: Dict with 'urls' key

    Returns:
        Dict with 'success' and 'result' keys
    """
    import trafilatura

    urls_param = parameters.get('urls', '')
    urls = _parse_urls(urls_param)

    if not urls:
        return {"success": False, "error": "No URLs provided. Please provide at least one URL."}

    # Validate URLs (scheme + SSRF protection)
    valid_urls = []
    for url in urls:
        if not (url.startswith('http://') or url.startswith('https://')):
            LOGGER.warning(f"[Common Tools] Rejecting invalid URL (not http/https): {url}")
            continue
        if _is_internal_url(url):
            LOGGER.warning(f"[Common Tools] Rejecting internal/private URL (SSRF protection): {url}")
            continue
        valid_urls.append(url)

    if not valid_urls:
        return {"success": False, "error": "No valid URLs provided. URLs must start with http:// or https:// and must not target internal/private addresses."}

    # Limit to 5 URLs
    truncated = False
    if len(valid_urls) > 5:
        valid_urls = valid_urls[:5]
        truncated = True

    # Fetch each URL
    results_parts = []
    for url in valid_urls:
        try:
            html = trafilatura.fetch_url(url, config=_TRAFILATURA_CONFIG)
            if html is None:
                results_parts.append(f"## {url}\n\n*Error: Could not fetch URL (network error or URL not accessible)*\n")
                continue

            content = trafilatura.extract(
                html,
                output_format="markdown",
                include_links=True
            )

            if content is None or not content.strip():
                results_parts.append(f"## {url}\n\n*No extractable content found on this page.*\n")
                continue

            # Truncate if needed
            if len(content) > MAX_CONTENT_PER_URL:
                content = content[:MAX_CONTENT_PER_URL] + "\n\n*[Content truncated due to length]*"

            results_parts.append(f"## {url}\n\n{content}\n")

        except Exception as e:
            LOGGER.warning(f"[Common Tools] Error fetching URL {url}: {e}")
            results_parts.append(f"## {url}\n\n*Error fetching URL: {e}*\n")

    markdown = "\n---\n\n".join(results_parts)
    if truncated:
        markdown += "\n\n*Note: Only the first 5 URLs were fetched. Additional URLs were ignored.*"

    return {"success": True, "result": markdown}


def _handle_web_search(parameters: Dict[str, Any]) -> Dict[str, Any]:
    """
    Search the web using DuckDuckGo.

    Args:
        parameters: Dict with 'query' key and optional 'max_results'

    Returns:
        Dict with 'success' and 'result' keys
    """
    from duckduckgo_search import DDGS
    from duckduckgo_search.exceptions import RatelimitException

    query = parameters.get('query', '').strip()
    if not query:
        return {"success": False, "error": "Search query is required."}

    max_results = parameters.get('max_results', 5)
    try:
        max_results = int(max_results)
    except (TypeError, ValueError):
        max_results = 5
    max_results = max(1, min(max_results, 10))

    try:
        results = DDGS().text(query, max_results=max_results)

        if not results:
            return {"success": True, "result": f"No search results found for: {query}"}

        # Format as markdown
        parts = []
        for r in results:
            title = r.get('title', 'Untitled')
            body = r.get('body', '')
            href = r.get('href', '')
            parts.append(f"### {title}\n{body}\n[Link]({href})")

        markdown = "\n\n".join(parts)
        return {"success": True, "result": markdown}

    except RatelimitException:
        LOGGER.warning("[Common Tools] DuckDuckGo rate limit reached")
        return {"success": False, "error": "Web search rate limit reached. Please try again in a moment."}
    except Exception as e:
        LOGGER.exception(f"[Common Tools] Web search error: {e}")
        return {"success": False, "error": f"Web search failed: {e}"}
