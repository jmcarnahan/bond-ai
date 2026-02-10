"""
MCP (Model Context Protocol) integration for Bedrock Provider.
Handles MCP tool definitions and execution for Bedrock agents using native action groups.

Authentication Types (auth_type in server config):
- "bond_jwt" (default): Use Bond's JWT token passed via Authorization header
- "oauth2": Use user-specific OAuth tokens from external providers (e.g., Atlassian)
- "static": Use static headers from config only (API keys, etc.)

For oauth2 auth_type, tokens are stored in the session-only MCPTokenCache.
Users must authorize external MCP servers each session.
"""

import json
import logging
import hashlib
import re
from typing import List, Dict, Any, Optional, Tuple
from fastmcp import Client
from fastmcp.client import StreamableHttpTransport  # Use fastmcp's transport wrapper
from fastmcp.client.transports import SSETransport
import asyncio
from bondable.bond.config import Config
from bondable.bond.auth.mcp_token_cache import (
    get_mcp_token_cache,
    AuthorizationRequiredError,
    TokenExpiredError
)
from bondable.bond.auth.oauth_utils import safe_isoformat

LOGGER = logging.getLogger(__name__)

# Auth type constants
AUTH_TYPE_BOND_JWT = "bond_jwt"
AUTH_TYPE_OAUTH2 = "oauth2"
AUTH_TYPE_STATIC = "static"

# Token cache initialization no longer needed - it gets DB session automatically from Config


# =============================================================================
# Tool Naming Utilities
# =============================================================================
# New tool naming format: /b.{hash6}.{tool_name}
# - Prefix: /b. (identifies Bond MCP tools)
# - Hash: 6-character SHA256 hash of server name (or "ADMIN0" for admin tools)
# - Tool name: Original MCP tool name
# This enables direct server routing without searching all servers.
#
# Admin tools use a special reserved hash "ADMIN0" that won't collide with
# real SHA256 hashes (which are hex-only). Admin tool paths look like:
# /b.ADMIN0.get_usage_stats
# =============================================================================

# Import admin tool constants
from bondable.bond.providers.bedrock.AdminMCP import (
    ADMIN_SERVER_HASH,
    ADMIN_SERVER_NAME,
    ADMIN_TOOL_NAMES,
    get_admin_tool_definitions,
    is_admin_tool
)

def _hash_server_name(server_name: str) -> str:
    """
    Generate 6-character hash of server name.

    Uses SHA256 and takes first 6 hex characters. This provides
    ~16 million unique values, sufficient for MCP server identification.

    Args:
        server_name: MCP server name from config

    Returns:
        6-character lowercase hex string
    """
    return hashlib.sha256(server_name.encode()).hexdigest()[:6]


def _build_tool_path(server_name: str, tool_name: str) -> str:
    """
    Build tool path with server hash: /b.{hash6}.{tool_name}

    Args:
        server_name: MCP server name
        tool_name: Original MCP tool name

    Returns:
        Tool path in new format, e.g., /b.a1b2c3.current_time
    """
    server_hash = _hash_server_name(server_name)
    return f"/b.{server_hash}.{tool_name}"


def _parse_tool_path(api_path: str) -> Tuple[Optional[str], Optional[str]]:
    """
    Parse tool path to extract server hash and tool name.

    Handles both:
    - Regular MCP tools: /b.{hex6}.{tool_name} (e.g., /b.a1b2c3.list_tools)
    - Admin tools: /b.ADMIN0.{tool_name} (e.g., /b.ADMIN0.get_usage_stats)

    Args:
        api_path: API path from Bedrock action invocation

    Returns:
        Tuple of (server_hash, tool_name) or (None, None) if not a Bond MCP tool
    """
    if not api_path:
        return None, None
    # Match hex hash (a-f0-9) OR the special ADMIN0 identifier
    match = re.match(r'^/b\.([a-f0-9]{6}|ADMIN0)\.(.+)$', api_path)
    if match:
        return match.group(1), match.group(2)
    return None, None


def _build_admin_tool_path(tool_name: str) -> str:
    """
    Build tool path for an admin tool: /b.ADMIN0.{tool_name}

    Args:
        tool_name: Admin tool name

    Returns:
        Tool path in admin format, e.g., /b.ADMIN0.get_usage_stats
    """
    return f"/b.{ADMIN_SERVER_HASH}.{tool_name}"


def _resolve_server_from_hash(server_hash: str, mcp_config: Dict[str, Any]) -> Optional[str]:
    """
    Resolve server hash to server name.

    Args:
        server_hash: 6-character hash from tool path
        mcp_config: MCP configuration dict with mcpServers

    Returns:
        Server name if found, None otherwise
    """
    servers = mcp_config.get('mcpServers', {})
    for server_name in servers:
        if _hash_server_name(server_name) == server_hash:
            return server_name
    return None


def _get_bedrock_agent_client() -> Any:
    from bondable.bond.providers.bedrock.BedrockProvider import BedrockProvider
    bond_provider: BedrockProvider = Config.config().get_provider()
    return bond_provider.bedrock_agent_client


# =============================================================================
# Bedrock Schema Sanitization
# =============================================================================
# Bedrock's OpenAPI parser only supports basic JSON Schema types:
# string, integer, number, boolean. Complex constructs like anyOf, oneOf,
# allOf, $ref, nested objects, and arrays of objects cause
# internalServerException at invocation time.
#
# Bedrock also has limits:
# - Max 11 APIs per agent (adjustable quota)
# - Max 5 parameters per function (adjustable quota)
# - Max 200 characters for action group description
# =============================================================================

MAX_APIS_PER_AGENT = 11
MAX_PARAMS_PER_FUNCTION = 5
MAX_DESCRIPTION_LENGTH = 200

# Unsupported JSON Schema keywords that must be removed for Bedrock
_UNSUPPORTED_SCHEMA_KEYWORDS = {
    'anyOf', 'oneOf', 'allOf', '$ref', 'additionalProperties',
    'items', 'prefixItems', 'patternProperties', 'if', 'then', 'else',
    'not', 'dependentSchemas', 'dependentRequired', 'unevaluatedProperties',
    'unevaluatedItems', 'contains', 'minContains', 'maxContains',
}


def _sanitize_property_schema(prop_name: str, prop_schema: Dict[str, Any]) -> Dict[str, Any]:
    """
    Sanitize a single property schema for Bedrock OpenAPI compatibility.

    Bedrock supports only basic types: string, integer, number, boolean.
    Complex constructs are converted to string type with descriptive text.

    Args:
        prop_name: Property name (for logging)
        prop_schema: Raw JSON Schema for this property

    Returns:
        Sanitized schema dict with only Bedrock-compatible constructs
    """
    if not isinstance(prop_schema, dict):
        return {"type": "string", "description": f"Parameter {prop_name}"}

    result = {}
    original_desc = prop_schema.get('description', '')
    original_title = prop_schema.get('title', '')

    # Handle anyOf/oneOf (common in Python type hints like str | None, dict | str | None)
    for union_key in ('anyOf', 'oneOf'):
        if union_key in prop_schema:
            variants = prop_schema[union_key]
            non_null_variants = [v for v in variants if v.get('type') != 'null']

            if len(non_null_variants) == 1:
                # Simple nullable: str | None -> string
                inner = non_null_variants[0]
                inner_type = inner.get('type', 'string')
                if inner_type in ('string', 'integer', 'number', 'boolean'):
                    result = {"type": inner_type}
                elif inner_type == 'object':
                    result = {"type": "string"}
                    if not original_desc:
                        original_desc = f"JSON object string for {prop_name}"
                elif inner_type == 'array':
                    result = {"type": "string"}
                    if not original_desc:
                        original_desc = f"JSON array string for {prop_name}"
                else:
                    result = {"type": "string"}
            elif len(non_null_variants) > 1:
                # Mixed union: dict | str | None -> string with JSON hint
                type_names = [v.get('type', 'unknown') for v in non_null_variants]
                result = {"type": "string"}
                if not original_desc:
                    original_desc = f"Value for {prop_name} (accepts: {', '.join(type_names)}). Use JSON string for complex types."
            else:
                # All null or empty - fallback to string
                result = {"type": "string"}

            # Add description and return early
            desc = original_desc or original_title or f"Parameter {prop_name}"
            if desc:
                result['description'] = desc
            if 'enum' in prop_schema:
                result['enum'] = prop_schema['enum']
            return result

    # Handle allOf (merge schemas)
    if 'allOf' in prop_schema:
        result = {"type": "string"}
        desc = original_desc or original_title or f"Parameter {prop_name}"
        if desc:
            result['description'] = desc
        return result

    # Handle $ref
    if '$ref' in prop_schema:
        result = {"type": "string"}
        desc = original_desc or original_title or f"Parameter {prop_name} (reference type)"
        result['description'] = desc
        return result

    # Handle by type
    prop_type = prop_schema.get('type', 'string')

    if prop_type == 'object':
        # Convert object types to string (user passes JSON string)
        result = {"type": "string"}
        if not original_desc:
            original_desc = f"JSON object string for {prop_name}"

    elif prop_type == 'array':
        # Convert array types to string (user passes JSON array or comma-separated)
        items = prop_schema.get('items', {})
        items_type = items.get('type', 'string') if isinstance(items, dict) else 'string'
        result = {"type": "string"}
        if items_type in ('string', 'integer', 'number'):
            if not original_desc:
                original_desc = f"Comma-separated list of {items_type} values for {prop_name}"
        else:
            if not original_desc:
                original_desc = f"JSON array string for {prop_name}"

    elif prop_type in ('string', 'integer', 'number', 'boolean'):
        result = {"type": prop_type}
    else:
        # Unknown type - default to string
        result = {"type": "string"}
        LOGGER.debug(f"[Schema Sanitize] Unknown type '{prop_type}' for property '{prop_name}', defaulting to string")

    # Preserve safe attributes
    desc = original_desc or original_title
    if desc:
        result['description'] = desc
    if 'enum' in prop_schema:
        result['enum'] = prop_schema['enum']
    if 'default' in prop_schema and isinstance(prop_schema['default'], (str, int, float, bool)):
        result['default'] = prop_schema['default']

    return result


def _sanitize_tool_parameters(
    tool_name: str,
    properties: Dict[str, Any],
    required: Optional[List[str]] = None,
    max_params: int = MAX_PARAMS_PER_FUNCTION,
) -> Tuple[Dict[str, Any], List[str]]:
    """
    Sanitize all parameters for a tool for Bedrock compatibility.

    Sanitizes each property schema and enforces the max parameter limit,
    prioritizing required parameters when truncating.

    Args:
        tool_name: Tool name for logging
        properties: Raw properties dict from inputSchema
        required: List of required parameter names
        max_params: Maximum allowed parameters per function

    Returns:
        Tuple of (sanitized_properties, filtered_required_list)
    """
    if not properties:
        return {}, []

    required = required or []

    # Sanitize each property
    sanitized = {}
    for prop_name, prop_schema in properties.items():
        sanitized[prop_name] = _sanitize_property_schema(prop_name, prop_schema)

    # Enforce max parameter limit
    if len(sanitized) > max_params:
        # Prioritize required parameters, then take remaining in order
        required_params = {k: sanitized[k] for k in required if k in sanitized}
        optional_params = {k: v for k, v in sanitized.items() if k not in required_params}

        truncated = dict(required_params)
        remaining_slots = max_params - len(truncated)
        for k, v in optional_params.items():
            if remaining_slots <= 0:
                break
            truncated[k] = v
            remaining_slots -= 1

        dropped = set(sanitized.keys()) - set(truncated.keys())
        LOGGER.warning(
            f"[Schema Sanitize] Tool '{tool_name}': truncated from {len(sanitized)} to "
            f"{len(truncated)} params (Bedrock limit: {max_params}). "
            f"Dropped: {dropped}"
        )
        sanitized = truncated

    # Filter required list to only include params that survived truncation
    filtered_required = [r for r in required if r in sanitized]

    return sanitized, filtered_required


def _sanitize_description(description: str, max_length: int = MAX_DESCRIPTION_LENGTH) -> str:
    """
    Truncate description to Bedrock's max length.

    Args:
        description: Original description text
        max_length: Maximum allowed length

    Returns:
        Truncated description string
    """
    if not description:
        return ""
    if len(description) <= max_length:
        return description
    return description[:max_length - 3] + "..."


def _validate_openapi_for_bedrock(openapi_spec: Dict[str, Any]) -> List[str]:
    """
    Validate an OpenAPI spec against known Bedrock restrictions.

    Returns a list of warning messages for any issues found.
    This is a safety-net check run after sanitization.

    Args:
        openapi_spec: The generated OpenAPI 3.0 spec

    Returns:
        List of warning strings (empty if no issues)
    """
    warnings = []
    paths = openapi_spec.get('paths', {})

    # Check total API count
    if len(paths) > MAX_APIS_PER_AGENT:
        warnings.append(
            f"API count ({len(paths)}) exceeds Bedrock limit ({MAX_APIS_PER_AGENT})"
        )

    # Check payload size
    payload_json = json.dumps(openapi_spec)
    payload_size = len(payload_json.encode('utf-8'))
    if payload_size > 100000:
        warnings.append(f"OpenAPI payload size ({payload_size} bytes) exceeds 100KB threshold")

    for path_key, path_def in paths.items():
        for method, operation in path_def.items():
            op_id = operation.get('operationId', path_key)

            # Check description length
            for desc_field in ('summary', 'description'):
                desc = operation.get(desc_field, '')
                if len(desc) > MAX_DESCRIPTION_LENGTH:
                    warnings.append(
                        f"{op_id}: {desc_field} length ({len(desc)}) exceeds {MAX_DESCRIPTION_LENGTH}"
                    )

            # Check parameter schemas for unsupported constructs
            request_body = operation.get('requestBody', {})
            schema = (request_body.get('content', {})
                     .get('application/json', {})
                     .get('schema', {}))
            props = schema.get('properties', {})

            if len(props) > MAX_PARAMS_PER_FUNCTION:
                warnings.append(
                    f"{op_id}: parameter count ({len(props)}) exceeds {MAX_PARAMS_PER_FUNCTION}"
                )

            for prop_name, prop_schema in props.items():
                if isinstance(prop_schema, dict):
                    for keyword in _UNSUPPORTED_SCHEMA_KEYWORDS:
                        if keyword in prop_schema:
                            warnings.append(
                                f"{op_id}.{prop_name}: contains unsupported keyword '{keyword}'"
                            )

    return warnings


def _resolve_expected_type(prop_schema: Dict[str, Any]) -> Optional[str]:
    """
    Resolve the expected non-null type from a property schema.

    Handles direct types and anyOf/oneOf unions (picks the first non-null type).

    Args:
        prop_schema: Property schema dict

    Returns:
        Expected type string (e.g., 'string', 'integer', 'object') or None
    """
    direct_type = prop_schema.get('type')
    if direct_type:
        return direct_type

    # Check anyOf/oneOf for the first non-null type
    for union_key in ('anyOf', 'oneOf'):
        if union_key in prop_schema:
            for variant in prop_schema[union_key]:
                vtype = variant.get('type')
                if vtype and vtype != 'null':
                    return vtype

    return None


def _coerce_parameters_for_mcp(tool_name: str, parameters: Dict[str, Any], tool_schema: Dict[str, Any]) -> Dict[str, Any]:
    """
    Coerce parameter values to match the MCP tool's expected types.

    Bedrock sends ALL parameter values as strings. This function converts
    them back to the types the MCP server expects based on the tool's
    original inputSchema:
    - "true"/"false" -> True/False for boolean params
    - "10" -> 10 for integer params
    - "3.14" -> 3.14 for number params
    - '{"key": "val"}' -> {"key": "val"} for object params
    - '["a", "b"]' -> ["a", "b"] for array params

    Args:
        tool_name: Tool name for logging
        parameters: Parameters dict from Bedrock (values are typically strings)
        tool_schema: The tool's original inputSchema from the MCP server

    Returns:
        New parameters dict with coerced values
    """
    if not parameters or not tool_schema:
        return parameters

    properties = tool_schema.get('properties', {})
    if not properties:
        return parameters

    coerced = parameters.copy()

    for param_name, value in coerced.items():
        if not isinstance(value, str) or param_name not in properties:
            continue

        prop_schema = properties[param_name]
        expected_type = _resolve_expected_type(prop_schema)

        if not expected_type or expected_type == 'string':
            continue  # Already a string, no coercion needed

        # Boolean coercion
        if expected_type == 'boolean':
            lower = value.strip().lower()
            if lower == 'true':
                coerced[param_name] = True
                LOGGER.debug(f"[MCP Execute] Coerced '{param_name}' to bool True")
            elif lower == 'false':
                coerced[param_name] = False
                LOGGER.debug(f"[MCP Execute] Coerced '{param_name}' to bool False")
            continue

        # Integer coercion
        if expected_type == 'integer':
            try:
                coerced[param_name] = int(value)
                LOGGER.debug(f"[MCP Execute] Coerced '{param_name}' to int {coerced[param_name]}")
            except ValueError:
                LOGGER.debug(f"[MCP Execute] Could not coerce '{param_name}' to int, keeping string")
            continue

        # Number (float) coercion
        if expected_type == 'number':
            try:
                coerced[param_name] = float(value)
                LOGGER.debug(f"[MCP Execute] Coerced '{param_name}' to float {coerced[param_name]}")
            except ValueError:
                LOGGER.debug(f"[MCP Execute] Could not coerce '{param_name}' to float, keeping string")
            continue

        # Object/array coercion (parse JSON string)
        if expected_type in ('object', 'array'):
            stripped = value.strip()
            if (stripped.startswith('{') and stripped.endswith('}')) or \
               (stripped.startswith('[') and stripped.endswith(']')):
                try:
                    coerced[param_name] = json.loads(value)
                    LOGGER.debug(
                        f"[MCP Execute] Coerced '{param_name}' from string to "
                        f"{type(coerced[param_name]).__name__}"
                    )
                except json.JSONDecodeError:
                    LOGGER.debug(
                        f"[MCP Execute] '{param_name}' looks like JSON but "
                        f"failed to parse, keeping as string"
                    )

    return coerced


def create_mcp_action_groups(bedrock_agent_id: str, mcp_tools: List[str], mcp_resources: List[str], user_id: Optional[str] = None):
    """
    Create action groups for MCP tools.

    Args:
        bedrock_agent_id: The Bedrock agent ID
        mcp_tools: List of MCP tool names to create action groups for
        mcp_resources: List of MCP resource names (for future use)
        user_id: User ID for OAuth token lookup (required for oauth2 servers)
    """
    LOGGER.debug(f"[MCP Action Groups] Creating action groups for agent {bedrock_agent_id}, tools={mcp_tools}, user_id={user_id}")

    if not mcp_tools:
        LOGGER.debug("[MCP Action Groups] No MCP tools specified, skipping action group creation")
        return

    bedrock_agent_client = _get_bedrock_agent_client()

    try:
        # Get MCP config
        mcp_config = Config.config().get_mcp_config()

        if not mcp_config:
            LOGGER.error("[MCP Action Groups] MCP tools specified but no MCP config available")
            return

        # Get tool definitions from MCP (with OAuth support)
        LOGGER.debug(f"[MCP Action Groups] Fetching tool definitions for {len(mcp_tools)} tools with user_id={user_id}")
        mcp_tool_definitions = _get_mcp_tool_definitions_sync(mcp_config, mcp_tools, user_id=user_id)

        if not mcp_tool_definitions:
            LOGGER.warning("[MCP Action Groups] No MCP tool definitions found - action group will NOT be created")
            return

        LOGGER.debug(f"[MCP Action Groups] Got {len(mcp_tool_definitions)} tool definitions")

        # Enforce Bedrock API count limit
        if len(mcp_tool_definitions) > MAX_APIS_PER_AGENT:
            LOGGER.warning(
                f"[MCP Action Groups] {len(mcp_tool_definitions)} tools exceed Bedrock limit of "
                f"{MAX_APIS_PER_AGENT}. Only first {MAX_APIS_PER_AGENT} will be registered. "
                f"All tools: {[t['name'] for t in mcp_tool_definitions]}"
            )
            mcp_tool_definitions = mcp_tool_definitions[:MAX_APIS_PER_AGENT]

        # Build OpenAPI paths for MCP tools
        paths = {}
        for tool in mcp_tool_definitions:
            # Use new naming format: /b.{hash6}.{tool_name}
            # This embeds server identification in the tool path for direct routing
            tool_server_name = tool.get('server_name', 'unknown')

            # Check if this is an admin tool (use ADMIN0 hash instead of hashing server name)
            if tool_server_name == ADMIN_SERVER_NAME:
                tool_path = _build_admin_tool_path(tool['name'])
                server_hash = ADMIN_SERVER_HASH
                LOGGER.debug(f"[MCP Action Groups] Building admin tool path: {tool_path}")
            else:
                tool_path = _build_tool_path(tool_server_name, tool['name'])
                server_hash = _hash_server_name(tool_server_name)

            operation_id = f"b_{server_hash}_{tool['name']}"

            # Sanitize descriptions to fit Bedrock limits
            tool_desc = _sanitize_description(
                tool.get('description', f"MCP tool {tool['name']}")
            )

            paths[tool_path] = {
                "post": {
                    "operationId": operation_id,
                    "summary": tool_desc,
                    "description": tool_desc,
                    "responses": {
                        "200": {
                            "description": "Tool execution result",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "object",
                                        "properties": {
                                            "result": {
                                                "type": "string",
                                                "description": "Tool execution result"
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }

            # Add parameters if any (already sanitized in _get_mcp_tool_definitions)
            if tool.get('parameters'):
                schema_obj = {
                    "type": "object",
                    "properties": tool['parameters']
                }
                if tool.get('required'):
                    schema_obj["required"] = tool['required']

                paths[tool_path]["post"]["requestBody"] = {
                    "content": {
                        "application/json": {
                            "schema": schema_obj
                        }
                    }
                }

        # Create action group
        openapi_spec = {
            "openapi": "3.0.0",
            "info": {
                "title": "MCP Tools API",
                "version": "1.0.0",
                "description": "MCP tools for external integrations"
            },
            "paths": paths
        }

        # Validate and log diagnostics
        payload_json = json.dumps(openapi_spec)
        payload_size = len(payload_json.encode('utf-8'))
        LOGGER.info(
            f"[MCP Action Groups] Creating action group with {len(paths)} tools "
            f"(payload: {payload_size} bytes): {list(paths.keys())}"
        )
        LOGGER.debug(f"[MCP Action Groups] OpenAPI spec: {json.dumps(openapi_spec, indent=2)}")

        # Run validation and log any warnings
        validation_warnings = _validate_openapi_for_bedrock(openapi_spec)
        for warning in validation_warnings:
            LOGGER.warning(f"[MCP Action Groups] Bedrock validation: {warning}")

        action_group_spec = {
            "actionGroupName": "MCPTools",
            "description": _sanitize_description(
                "MCP (Model Context Protocol) tools for external integrations"
            ),
            "actionGroupExecutor": {
                "customControl": "RETURN_CONTROL"  # Return control to client for execution
            },
            "apiSchema": {
                "payload": payload_json
            }
        }

        LOGGER.info(f"Creating MCP action group with {len(paths)} tools")
        action_response = bedrock_agent_client.create_agent_action_group(
            agentId=bedrock_agent_id,
            agentVersion="DRAFT",
            **action_group_spec
        )

        LOGGER.info(f"Created MCP action group: {action_response['agentActionGroup']['actionGroupId']}")

    except Exception as e:
        LOGGER.error(f"Error creating MCP action groups: {e}")
        # Continue without MCP tools rather than failing agent creation


async def _get_mcp_tool_definitions(mcp_config: Dict[str, Any], tool_names: List[str], user_id: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Get tool definitions from MCP servers.

    Searches ALL configured MCP servers for the requested tools.

    Args:
        mcp_config: MCP configuration dict
        tool_names: List of tool names to get definitions for
        user_id: User ID for OAuth token lookup (required for oauth2 servers)

    Returns:
        List of tool definition dicts with name, description, and parameters
    """
    servers = mcp_config.get('mcpServers', {})
    if not servers:
        LOGGER.warning("[MCP Tool Defs] No MCP servers configured")
        return []

    LOGGER.debug(f"[MCP Tool Defs] Searching {len(servers)} servers for {len(tool_names)} tools: {tool_names}")

    # Create user context for OAuth lookup if user_id is provided
    current_user = None
    if user_id:
        class UserContext:
            def __init__(self, uid):
                self.user_id = uid
                self.email = 'unknown'
        current_user = UserContext(user_id)

    tool_definitions = []
    remaining_tools = set(tool_names)  # Track which tools we still need to find

    # =================================================================
    # First, check for admin tools in the requested list
    # =================================================================
    # Admin tools are handled internally and don't need external MCP calls
    admin_tool_names_requested = remaining_tools & ADMIN_TOOL_NAMES
    if admin_tool_names_requested:
        LOGGER.debug(f"[MCP Tool Defs] Found {len(admin_tool_names_requested)} admin tools in request: {admin_tool_names_requested}")
        admin_tool_defs = get_admin_tool_definitions()
        admin_tool_map = {t['name']: t for t in admin_tool_defs}

        for tool_name in admin_tool_names_requested:
            if tool_name in admin_tool_map:
                admin_tool = admin_tool_map[tool_name]
                raw_properties = admin_tool['inputSchema'].get('properties', {})
                raw_required = admin_tool['inputSchema'].get('required', [])
                sanitized_props, sanitized_required = _sanitize_tool_parameters(
                    tool_name=tool_name,
                    properties=raw_properties,
                    required=raw_required,
                )
                tool_def = {
                    'name': tool_name,
                    'description': admin_tool['description'],
                    'parameters': sanitized_props,
                    'required': sanitized_required,
                    'server_name': ADMIN_SERVER_NAME  # Mark as admin tool
                }
                tool_definitions.append(tool_def)
                remaining_tools.remove(tool_name)
                LOGGER.debug(f"[MCP Tool Defs] Added admin tool '{tool_name}'")

    # =================================================================
    # Search each external MCP server for the remaining tools
    # =================================================================
    for server_name, server_config in servers.items():
        if not remaining_tools:
            break  # Found all tools

        server_url = server_config.get('url')
        if not server_url:
            LOGGER.warning(f"[MCP Tool Defs] No URL configured for MCP server {server_name}")
            continue

        try:
            # Get authentication headers (handles oauth2, bond_jwt, static)
            try:
                headers = _get_auth_headers_for_server(server_name, server_config, current_user)
                headers['User-Agent'] = 'Bond-AI-MCP-Client/1.0'
                LOGGER.debug(f"[MCP Tool Defs] Server '{server_name}': authenticated successfully")
            except (AuthorizationRequiredError, TokenExpiredError) as e:
                LOGGER.warning(f"[MCP Tool Defs] Server '{server_name}': OAuth not available - {e}")
                # Fall back to static headers only
                headers = server_config.get('headers', {})
                headers['User-Agent'] = 'Bond-AI-MCP-Client/1.0'

            # Use appropriate transport based on config
            transport_type = server_config.get('transport', 'streamable-http')

            # Note: Don't override Accept/Content-Type headers for streamable-http
            # The MCP SDK sets these by default with lowercase keys

            if transport_type == 'sse':
                transport = SSETransport(server_url, headers=headers)
            else:
                transport = StreamableHttpTransport(server_url, headers=headers)

            async with Client(transport) as client:
                # Fetch all available tools from this server
                all_tools = await client.list_tools()
                tool_dict = {tool.name: tool for tool in all_tools}
                server_tool_names = list(tool_dict.keys())
                LOGGER.debug(f"[MCP Tool Defs] Server '{server_name}': {len(all_tools)} tools available")

                # Check which requested tools are on this server
                for tool_name in list(remaining_tools):
                    if tool_name in tool_dict:
                        tool = tool_dict[tool_name]
                        tool_def = {
                            'name': tool_name,
                            'description': tool.description or f"MCP tool {tool_name}",
                            'server_name': server_name  # Track which server has this tool
                        }

                        # Add parameter schema if available, with sanitization
                        if hasattr(tool, 'inputSchema') and tool.inputSchema:
                            schema = tool.inputSchema
                            if 'properties' in schema:
                                raw_properties = dict(schema['properties'])
                                raw_required = schema.get('required', [])
                                sanitized_props, sanitized_required = _sanitize_tool_parameters(
                                    tool_name=tool_name,
                                    properties=raw_properties,
                                    required=raw_required,
                                )
                                tool_def['parameters'] = sanitized_props
                                tool_def['required'] = sanitized_required
                                LOGGER.info(
                                    f"[MCP Tool Defs] Tool '{tool_name}' schema: "
                                    f"{len(raw_properties)} raw params -> "
                                    f"{len(sanitized_props)} sanitized params, "
                                    f"required={sanitized_required}"
                                )
                            else:
                                tool_def['parameters'] = {}
                                tool_def['required'] = []
                        else:
                            tool_def['parameters'] = {}
                            tool_def['required'] = []

                        tool_definitions.append(tool_def)
                        remaining_tools.remove(tool_name)
                        LOGGER.debug(f"[MCP Tool Defs] Found tool '{tool_name}' on server '{server_name}'")

        except Exception as e:
            LOGGER.error(f"[MCP Tool Defs] Error fetching tools from server '{server_name}': {e}")
            continue

    if remaining_tools:
        LOGGER.warning(f"[MCP Tool Defs] Tools not found on any server: {remaining_tools}")

    LOGGER.debug(f"[MCP Tool Defs] Total tool definitions found: {len(tool_definitions)}")
    return tool_definitions


def _get_mcp_tool_definitions_sync(mcp_config: Dict[str, Any], tool_names: List[str], user_id: Optional[str] = None) -> List[Dict[str, Any]]:
    """Synchronous wrapper for getting MCP tool definitions."""
    try:
        # Try to get the current event loop
        loop = asyncio.get_running_loop()
        # If we're in an async context, create a task
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor() as executor:
            future = executor.submit(asyncio.run, _get_mcp_tool_definitions(mcp_config, tool_names, user_id))
            return future.result()
    except RuntimeError:
        # No event loop running, we can use asyncio.run directly
        return asyncio.run(_get_mcp_tool_definitions(mcp_config, tool_names, user_id))


def _get_auth_headers_for_server(
    server_name: str,
    server_config: Dict[str, Any],
    current_user: Optional[Any] = None,
    jwt_token: Optional[str] = None
) -> Dict[str, str]:
    """
    Get authentication headers for an MCP server based on its auth_type.

    Args:
        server_name: Name of the MCP server
        server_config: Server configuration dict
        current_user: User object with authentication context
        jwt_token: Bond JWT token for bond_jwt auth type

    Returns:
        Headers dict with appropriate Authorization header

    Raises:
        AuthorizationRequiredError: If oauth2 auth is required but user hasn't authorized
        TokenExpiredError: If oauth2 token exists but is expired
    """
    # Start with any static headers from config
    headers = server_config.get('headers', {}).copy()

    # Get auth type (default to bond_jwt for backwards compatibility)
    auth_type = server_config.get('auth_type', AUTH_TYPE_BOND_JWT)

    user_id = getattr(current_user, 'user_id', None) if current_user else None
    user_email = getattr(current_user, 'email', 'unknown') if current_user else 'unknown'

    if auth_type == AUTH_TYPE_OAUTH2:
        # OAuth2: Use user-specific token from cache (backed by database)
        if not user_id:
            raise AuthorizationRequiredError(
                server_name,
                f"User authentication required to access MCP server '{server_name}'"
            )

        token_cache = get_mcp_token_cache()

        # First check if token exists (including expired tokens for better error message)
        user_connections = token_cache.get_user_connections(user_id)
        connection_info = user_connections.get(server_name)

        if connection_info is None:
            LOGGER.debug(f"[MCP Auth] No OAuth token found for user={user_email}, server={server_name}")
            raise AuthorizationRequiredError(
                server_name,
                f"Please authorize access to '{server_name}' before using its tools"
            )

        # Check if token is expired (connection exists but not valid)
        LOGGER.debug(f"[MCP Auth] Connection info for {server_name}: connected={connection_info.get('connected')}, valid={connection_info.get('valid')}, expires_at={connection_info.get('expires_at')}")
        if connection_info.get('connected') and not connection_info.get('valid'):
            LOGGER.debug(f"[MCP Auth] OAuth token expired for user={user_email}, server={server_name}")
            expires_at = connection_info.get('expires_at')
            raise TokenExpiredError(server_name, expires_at)

        # Get the actual token (will return None if expired due to 5-min buffer)
        token_data = token_cache.get_token(user_id, server_name)

        if token_data is None:
            LOGGER.debug(f"No valid OAuth token for user={user_email}, server={server_name}")
            raise AuthorizationRequiredError(
                server_name,
                f"Please authorize access to '{server_name}' before using its tools"
            )

        # Use "Bearer" (capitalized) as per RFC 6750 - some servers (like Atlassian) require this
        headers['Authorization'] = f'Bearer {token_data.access_token}'

        # TODO: Make cloud_id header configurable via oauth_config.cloud_id_header_name
        # to support different MCP servers that may use different header names
        # For now, hardcode X-Atlassian-Cloud-Id for Atlassian MCP compatibility
        cloud_id = server_config.get('cloud_id')
        if cloud_id:
            headers['X-Atlassian-Cloud-Id'] = cloud_id
            LOGGER.debug(f"[MCP Auth] Added X-Atlassian-Cloud-Id header: {cloud_id}")
        else:
            LOGGER.warning(f"[MCP Auth] No cloud_id found in config for OAuth2 server '{server_name}'. Some MCP servers (like Atlassian) may require this.")

        LOGGER.debug(f"Using OAuth2 token for MCP server {server_name} (user: {user_email})")

    elif auth_type == AUTH_TYPE_BOND_JWT:
        # Bond JWT: Use the passed JWT token
        if jwt_token:
            headers['Authorization'] = f'Bearer {jwt_token}'
            LOGGER.debug(f"Using Bond JWT for MCP server {server_name} (user: {user_email})")
        else:
            LOGGER.debug(f"No JWT token provided for bond_jwt auth on server {server_name}")

    elif auth_type == AUTH_TYPE_STATIC:
        # Static: Only use headers from config (already set above)
        LOGGER.debug(f"Using static headers for MCP server {server_name}")

    else:
        LOGGER.warning(f"Unknown auth_type '{auth_type}' for server {server_name}, using static headers")

    return headers


async def execute_mcp_tool(
    mcp_config: Dict[str, Any],
    tool_name: str,
    parameters: Optional[Dict[str, Any]] = None,
    current_user: Optional[Any] = None,
    jwt_token: Optional[str] = None,
    target_server: Optional[str] = None
) -> Dict[str, Any]:
    """
    Execute an MCP tool call with authentication.

    If target_server is provided, executes directly on that server.
    Otherwise, searches ALL configured MCP servers to find which one has the tool.

    Args:
        mcp_config: MCP configuration dict
        tool_name: Name of the tool to execute
        parameters: Parameters for the tool
        current_user: User object with authentication context
        jwt_token: Raw JWT token for authentication (used for bond_jwt auth_type)
        target_server: Optional server name for direct routing (from tool path hash)

    Returns:
        Result dictionary with 'success' and 'result' or 'error' fields

    Note:
        For oauth2 auth_type servers, the user must have authorized the server
        via the /mcp/{server}/connect endpoint first. If not authorized,
        this will return an error with authorization_required flag.
    """
    servers = mcp_config.get('mcpServers', {})
    if not servers:
        return {"success": False, "error": "No MCP servers configured"}

    # If target_server is specified, only check that server (direct routing)
    if target_server:
        if target_server in servers:
            servers_to_check = {target_server: servers[target_server]}
            LOGGER.debug(f"[MCP Execute] Direct routing to server '{target_server}' for tool '{tool_name}'")
        else:
            LOGGER.error(f"[MCP Execute] Target server '{target_server}' not found in config")
            return {"success": False, "error": f"Target server '{target_server}' not found in MCP configuration"}
    else:
        servers_to_check = servers
        LOGGER.debug(f"[MCP Execute] Searching {len(servers)} servers for tool '{tool_name}'")

    # Track whether the tool was found (vs execution failed) for better error messages
    last_execution_error = None

    # Search each server for the tool (or just the target server if direct routing)
    for server_name, server_config in servers_to_check.items():
        server_url = server_config.get('url')
        if not server_url:
            LOGGER.warning(f"[MCP Execute] No URL configured for MCP server {server_name}")
            continue

        try:
            # Get authentication headers based on auth_type
            headers = _get_auth_headers_for_server(
                server_name=server_name,
                server_config=server_config,
                current_user=current_user,
                jwt_token=jwt_token
            )
            headers['User-Agent'] = 'Bond-AI-MCP-Client/1.0'

            # Use appropriate transport based on config
            transport_type = server_config.get('transport', 'streamable-http')

            # Note: Don't override Accept/Content-Type headers for streamable-http
            # The MCP SDK sets these by default with lowercase keys

            if transport_type == 'sse':
                transport = SSETransport(server_url, headers=headers)
            else:
                transport = StreamableHttpTransport(server_url, headers=headers)

            async with Client(transport) as client:
                # Check if this server has the tool
                all_tools = await client.list_tools()
                tool_dict = {t.name: t for t in all_tools}

                if tool_name not in tool_dict:
                    LOGGER.debug(f"[MCP Execute] Tool '{tool_name}' not found on server '{server_name}'")
                    continue

                LOGGER.debug(f"[MCP Execute] Found tool '{tool_name}' on server '{server_name}'")

                # Prepare parameters
                tool_parameters = parameters.copy() if parameters else {}

                # Coerce parameters to match MCP tool's expected types
                # (reverses object/array -> string sanitization done for Bedrock)
                tool = tool_dict[tool_name]
                tool_schema = getattr(tool, 'inputSchema', None) or {}
                tool_parameters = _coerce_parameters_for_mcp(tool_name, tool_parameters, tool_schema)

                LOGGER.debug(f"[MCP Execute] Executing tool '{tool_name}' with parameters: {list(tool_parameters.keys())}")
                result = await client.call_tool(tool_name, tool_parameters)

                # Handle different result types (inside the async with block)
                if hasattr(result, 'content') and isinstance(result.content, list):
                    # Extract text from content list
                    text_parts = []
                    for content_item in result.content:
                        if hasattr(content_item, 'text'):
                            text_parts.append(content_item.text)
                        elif hasattr(content_item, 'type') and content_item.type == 'text':
                            text_parts.append(str(content_item))
                    return {"success": True, "result": " ".join(text_parts)}
                elif hasattr(result, 'text'):
                    return {"success": True, "result": result.text}
                else:
                    # Fallback to string representation
                    return {"success": True, "result": str(result)}

        except AuthorizationRequiredError as e:
            LOGGER.debug(f"[MCP Execute] Authorization required for server '{server_name}': {e.server_name}")
            if target_server:
                # Direct routing - return error immediately
                return {
                    "success": False,
                    "error": e.message,
                    "authorization_required": True,
                    "server_name": e.server_name
                }
            # Searching - continue to next server
            LOGGER.debug(f"[MCP Execute] Server '{server_name}' needs auth, trying next server...")
            continue
        except TokenExpiredError as e:
            LOGGER.debug(f"[MCP Execute] Token expired for server '{server_name}': {e.connection_name}")
            if target_server:
                # Direct routing - return error immediately
                return {
                    "success": False,
                    "error": e.message,
                    "token_expired": True,
                    "connection_name": e.connection_name,
                    "expired_at": safe_isoformat(e.expired_at)
                }
            # Searching - continue to next server
            LOGGER.debug(f"[MCP Execute] Server '{server_name}' token expired, trying next server...")
            continue
        except Exception as e:
            # Log full exception details including traceback for debugging
            LOGGER.exception(f"[MCP Execute] Error on server '{server_name}' when executing tool '{tool_name}' with parameters {list(parameters.keys()) if parameters else []}: {e}")
            last_execution_error = str(e)
            continue  # Try next server

    # Distinguish between "tool not found" and "tool found but execution failed"
    if last_execution_error:
        LOGGER.error(f"[MCP Execute] Tool '{tool_name}' execution failed: {last_execution_error}")
        return {"success": False, "error": f"Tool '{tool_name}' execution failed: {last_execution_error}"}
    else:
        LOGGER.error(f"[MCP Execute] Tool '{tool_name}' not found on any configured MCP server")
        return {"success": False, "error": f"Tool '{tool_name}' not found on any configured MCP server"}


def execute_mcp_tool_sync(
    mcp_config: Dict[str, Any],
    tool_name: str,
    parameters: Optional[Dict[str, Any]] = None,
    current_user: Optional[Any] = None,
    jwt_token: Optional[str] = None,
    target_server: Optional[str] = None
) -> Dict[str, Any]:
    """
    Synchronous wrapper for executing MCP tool with authentication.

    Args:
        mcp_config: MCP configuration dict
        tool_name: Name of the tool to execute
        parameters: Parameters for the tool
        current_user: User object with authentication context
        jwt_token: Raw JWT token for authentication
        target_server: Optional server name for direct routing

    Returns:
        Result dictionary with 'success' and 'result' or 'error' fields
    """
    try:
        # Try to get the current event loop
        loop = asyncio.get_running_loop()
        # If we're in an async context, create a task
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor() as executor:
            future = executor.submit(
                asyncio.run,
                execute_mcp_tool(mcp_config, tool_name, parameters, current_user, jwt_token, target_server)
            )
            return future.result()
    except RuntimeError:
        # No event loop running, we can use asyncio.run directly
        return asyncio.run(execute_mcp_tool(mcp_config, tool_name, parameters, current_user, jwt_token, target_server))
