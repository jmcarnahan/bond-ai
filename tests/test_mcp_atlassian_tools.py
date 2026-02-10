#!/usr/bin/env python3
"""
List all tools from mcp-atlassian and test schema sanitization.

Usage:
    poetry run python tests/test_mcp_atlassian_tools.py

Connects to the Atlassian MCP server (remote or local) and:
1. Lists all available tools with their raw schemas
2. Runs schema sanitization on each tool
3. Reports any issues found
"""

import asyncio
import json
import os
import sys

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastmcp import Client
from fastmcp.client.transports import SSETransport
from fastmcp.client import StreamableHttpTransport


async def main():
    # Try to get URL from BOND_MCP_CONFIG or fallback
    mcp_url = os.environ.get("ATLASSIAN_MCP_URL")
    if not mcp_url:
        # Try to parse from BOND_MCP_CONFIG
        mcp_config_str = os.environ.get("BOND_MCP_CONFIG", "")
        if mcp_config_str:
            try:
                mcp_config = json.loads(mcp_config_str)
                atlassian_config = mcp_config.get("mcpServers", {}).get("atlassian", {})
                mcp_url = atlassian_config.get("url")
            except json.JSONDecodeError:
                pass

    if not mcp_url:
        mcp_url = "https://fa3vbibtmu.us-west-2.awsapprunner.com/mcp/"

    print(f"\n{'='*70}")
    print(f"Atlassian MCP Tool Schema Analysis")
    print(f"Server: {mcp_url}")
    print(f"{'='*70}\n")

    # Try without auth first (for tool listing)
    headers = {"User-Agent": "Bond-AI-Test/1.0"}

    # Check if we have a token
    try:
        from bondable.bond.auth.mcp_token_cache import get_mcp_token_cache
        test_user_id = os.environ.get("TEST_USER_ID", "00uxpu9a9teaAE5rn697")
        cache = get_mcp_token_cache()
        token = cache.get_token(test_user_id, "atlassian")
        if token and not token.is_expired():
            headers["Authorization"] = f"Bearer {token.access_token}"
            print(f"Using OAuth token for user {test_user_id}\n")
        else:
            print(f"No valid OAuth token found - connecting without auth\n")
    except Exception as e:
        print(f"Could not load token cache: {e}")
        print(f"Connecting without auth\n")

    try:
        transport = StreamableHttpTransport(mcp_url, headers=headers)
        async with Client(transport) as client:
            all_tools = await client.list_tools()
            print(f"Found {len(all_tools)} tools\n")

            # Import sanitization functions
            from bondable.bond.providers.bedrock.BedrockMCP import (
                _sanitize_tool_parameters,
                _sanitize_description,
                MAX_PARAMS_PER_FUNCTION,
                MAX_APIS_PER_AGENT,
                MAX_DESCRIPTION_LENGTH,
            )

            issues = []
            sanitized_tools = []

            for i, tool in enumerate(all_tools, 1):
                name = tool.name
                desc = tool.description or ""
                schema = tool.inputSchema if hasattr(tool, 'inputSchema') else {}
                raw_props = schema.get('properties', {}) if schema else {}
                raw_required = schema.get('required', []) if schema else []

                # Sanitize
                sanitized_props, sanitized_required = _sanitize_tool_parameters(
                    tool_name=name,
                    properties=dict(raw_props),
                    required=list(raw_required),
                )
                sanitized_desc = _sanitize_description(desc)

                # Check for issues
                tool_issues = []
                if len(raw_props) > MAX_PARAMS_PER_FUNCTION:
                    tool_issues.append(f"Params: {len(raw_props)} -> {len(sanitized_props)} (limit: {MAX_PARAMS_PER_FUNCTION})")
                if len(desc) > MAX_DESCRIPTION_LENGTH:
                    tool_issues.append(f"Desc truncated: {len(desc)} -> {len(sanitized_desc)} chars")

                # Check for schema changes
                changed_props = []
                for prop_name in raw_props:
                    if prop_name in sanitized_props:
                        raw_type = raw_props[prop_name].get('type', 'N/A')
                        has_anyof = 'anyOf' in raw_props[prop_name]
                        has_oneof = 'oneOf' in raw_props[prop_name]
                        san_type = sanitized_props[prop_name].get('type', 'N/A')
                        if has_anyof or has_oneof or raw_type in ('object', 'array'):
                            changed_props.append(f"{prop_name}: {raw_type}{'(anyOf)' if has_anyof else '(oneOf)' if has_oneof else ''} -> {san_type}")

                if changed_props:
                    tool_issues.append(f"Schema changes: {', '.join(changed_props)}")

                # Print tool info
                status = "!" if tool_issues else "ok"
                print(f"  {i:2d}. [{status:>2}] {name} ({len(raw_props)} params -> {len(sanitized_props)})")

                if tool_issues:
                    for issue in tool_issues:
                        print(f"         {issue}")
                    issues.extend([(name, issue) for issue in tool_issues])

                sanitized_tools.append({
                    'name': name,
                    'description': sanitized_desc,
                    'parameters': sanitized_props,
                    'required': sanitized_required,
                })

            # Summary
            print(f"\n{'='*70}")
            print(f"SUMMARY")
            print(f"{'='*70}")
            print(f"Total tools:        {len(all_tools)}")
            print(f"Bedrock API limit:  {MAX_APIS_PER_AGENT}")
            print(f"Tools with issues:  {len(set(name for name, _ in issues))}")
            print(f"Total issues:       {len(issues)}")

            if len(all_tools) > MAX_APIS_PER_AGENT:
                print(f"\nWARNING: {len(all_tools)} tools exceed Bedrock limit of {MAX_APIS_PER_AGENT}.")
                print(f"Only first {MAX_APIS_PER_AGENT} will be registered as action group APIs.")

            # Verify all sanitized schemas are Bedrock-compatible
            print(f"\nValidating sanitized schemas...")
            valid = True
            for tool in sanitized_tools:
                for prop_name, prop_schema in tool['parameters'].items():
                    prop_type = prop_schema.get('type', 'MISSING')
                    if prop_type not in ('string', 'integer', 'number', 'boolean'):
                        print(f"  FAIL: {tool['name']}.{prop_name} has type '{prop_type}'")
                        valid = False
                    for kw in ('anyOf', 'oneOf', 'allOf', '$ref', 'additionalProperties', 'items'):
                        if kw in prop_schema:
                            print(f"  FAIL: {tool['name']}.{prop_name} still has '{kw}'")
                            valid = False

            if valid:
                print(f"  All sanitized schemas are Bedrock-compatible!")
            else:
                print(f"  ERRORS found in sanitized schemas!")

            print()

    except Exception as e:
        print(f"ERROR connecting to MCP server: {e}")
        import traceback
        traceback.print_exc()
        return 1

    return 0


if __name__ == "__main__":
    exit(asyncio.run(main()))
