"""
Internal Admin MCP Tools.

Provides MCP-like tools for admin users to query application metadata.
These tools are executed internally without external MCP server calls.

The tools appear in the UI as a regular MCP server called "Admin Tools"
but are only visible to users configured in ADMIN_USERS or ADMIN_EMAIL
environment variables.

Tool path format: /b.ADMIN0.{tool_name}
- The "ADMIN0" hash is a reserved identifier for admin tools
- This format matches the standard MCP tool path format for seamless integration
"""

import json
import logging
import re
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, List, Optional, Callable
from sqlalchemy import func

LOGGER = logging.getLogger(__name__)

# =============================================================================
# Constants
# =============================================================================

# Special 6-character "hash" for admin tools (matches the /b.{hash6}.{tool} format)
# This is NOT a real hash - it's a reserved identifier that won't collide with
# actual server name hashes (which are hex characters only: 0-9, a-f)
ADMIN_SERVER_HASH = "ADMIN0"

# Server identification for tool listing
ADMIN_SERVER_NAME = "admin_tools"
ADMIN_DISPLAY_NAME = "Admin Tools"
ADMIN_DESCRIPTION = "Internal tools for monitoring application usage (admin only)"

# Set of admin tool names for quick lookup
ADMIN_TOOL_NAMES = {
    "get_usage_stats",
    "list_all_users",
    "list_all_agents",
    "get_agent_usage",
    "get_recent_activity",
    "execute_sql_query",
}

# SQL keywords that are NOT allowed (anything that modifies data or schema)
FORBIDDEN_SQL_KEYWORDS = {
    'INSERT', 'UPDATE', 'DELETE', 'DROP', 'ALTER', 'CREATE', 'TRUNCATE',
    'GRANT', 'REVOKE', 'EXECUTE', 'EXEC', 'CALL', 'INTO',  # INTO blocks SELECT INTO
    'MERGE', 'REPLACE', 'UPSERT', 'LOCK', 'UNLOCK',
    'RENAME', 'COMMENT', 'SET', 'VACUUM', 'ANALYZE', 'REINDEX',
    'COPY', 'LOAD', 'UNLOAD', 'IMPORT', 'EXPORT',
}

# =============================================================================
# Tool Definitions (MCP-compatible schema format)
# =============================================================================

ADMIN_TOOL_DEFINITIONS = [
    {
        "name": "get_usage_stats",
        "description": "Get overall application usage statistics including counts of users, agents, threads, messages, and files. Returns a summary of the current state of the application.",
        "inputSchema": {
            "type": "object",
            "properties": {},
            "required": []
        }
    },
    {
        "name": "list_all_users",
        "description": "List all registered users in the system with their metadata including email, sign-in method, and registration date.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of users to return (default 50, max 200)"
                },
                "offset": {
                    "type": "integer",
                    "description": "Number of users to skip for pagination (default 0)"
                }
            },
            "required": []
        }
    },
    {
        "name": "list_all_agents",
        "description": "List all agents in the system with their owners, names, and creation dates.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of agents to return (default 50, max 200)"
                },
                "offset": {
                    "type": "integer",
                    "description": "Number of agents to skip for pagination (default 0)"
                }
            },
            "required": []
        }
    },
    {
        "name": "get_agent_usage",
        "description": "Get detailed usage statistics for a specific agent including thread count, message count, and recent activity.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "agent_id": {
                    "type": "string",
                    "description": "The agent ID to get usage statistics for"
                }
            },
            "required": ["agent_id"]
        }
    },
    {
        "name": "get_recent_activity",
        "description": "Get recent activity across the application including new threads, messages, and user activity within the specified time period.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "hours": {
                    "type": "integer",
                    "description": "Number of hours to look back for activity (default 24, max 168/1 week)"
                }
            },
            "required": []
        }
    },
    {
        "name": "execute_sql_query",
        "description": "Execute a read-only SQL query against the application database. Only SELECT statements are allowed. Use this for custom analytics queries not covered by other tools.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The SQL SELECT query to execute. Must be a read-only query."
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of rows to return (default 100, max 1000)"
                }
            },
            "required": ["query"]
        }
    }
]


# =============================================================================
# Public Functions
# =============================================================================

def get_admin_tool_definitions() -> List[Dict[str, Any]]:
    """
    Get the list of admin tool definitions.

    Returns:
        List of tool definition dictionaries with name, description, and inputSchema
    """
    return ADMIN_TOOL_DEFINITIONS.copy()


def is_admin_tool(tool_name: str) -> bool:
    """
    Check if a tool name is an admin tool.

    Args:
        tool_name: Name of the tool to check

    Returns:
        True if the tool is an admin tool
    """
    return tool_name in ADMIN_TOOL_NAMES


def build_admin_tool_path(tool_name: str) -> str:
    """
    Build the API path for an admin tool.

    Args:
        tool_name: Name of the admin tool

    Returns:
        Tool path in format /b.ADMIN0.{tool_name}
    """
    return f"/b.{ADMIN_SERVER_HASH}.{tool_name}"


def execute_admin_tool(
    tool_name: str,
    parameters: Dict[str, Any],
    current_user: Any,
    db_session_factory: Callable
) -> Dict[str, Any]:
    """
    Execute an admin tool and return results.

    Args:
        tool_name: Name of the admin tool to execute
        parameters: Parameters for the tool (from Bedrock)
        current_user: Current user object (for audit logging)
        db_session_factory: Factory function to create database sessions

    Returns:
        Dictionary with 'success' and 'result' or 'error' fields
        (same format as execute_mcp_tool_sync for consistency)
    """
    handlers = {
        "get_usage_stats": _handle_get_usage_stats,
        "list_all_users": _handle_list_all_users,
        "list_all_agents": _handle_list_all_agents,
        "get_agent_usage": _handle_get_agent_usage,
        "get_recent_activity": _handle_get_recent_activity,
        "execute_sql_query": _handle_execute_sql_query,
    }

    handler = handlers.get(tool_name)
    if not handler:
        LOGGER.warning(f"[Admin MCP] Unknown admin tool requested: {tool_name}")
        return {"success": False, "error": f"Unknown admin tool: {tool_name}"}

    user_email = getattr(current_user, 'email', 'unknown')
    LOGGER.info(f"[Admin MCP] Executing tool '{tool_name}' for admin user {user_email}")
    LOGGER.debug(f"[Admin MCP] Tool parameters: {parameters}")

    try:
        session = db_session_factory()
        try:
            result = handler(session, parameters, current_user)
            LOGGER.info(f"[Admin MCP] Tool '{tool_name}' completed successfully")
            # Return result as JSON string (same format as MCP tools)
            return {"success": True, "result": json.dumps(result, default=str, indent=2)}
        finally:
            session.close()
    except Exception as e:
        LOGGER.exception(f"[Admin MCP] Error executing tool '{tool_name}': {e}")
        return {"success": False, "error": str(e)}


# =============================================================================
# Tool Handlers
# =============================================================================

def _handle_get_usage_stats(session, parameters: Dict[str, Any], current_user: Any) -> Dict[str, Any]:
    """
    Get overall application usage statistics.

    Returns counts of users, agents, threads, messages, and files.
    """
    from bondable.bond.providers.metadata import User, AgentRecord, Thread, FileRecord
    from bondable.bond.providers.bedrock.BedrockMetadata import BedrockMessage

    user_count = session.query(func.count(User.id)).scalar() or 0
    agent_count = session.query(func.count(AgentRecord.agent_id)).scalar() or 0
    thread_count = session.query(func.count(Thread.thread_id)).scalar() or 0
    message_count = session.query(func.count(BedrockMessage.id)).scalar() or 0
    file_count = session.query(func.count(FileRecord.file_id)).scalar() or 0

    return {
        "total_users": user_count,
        "total_agents": agent_count,
        "total_threads": thread_count,
        "total_messages": message_count,
        "total_files": file_count,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "generated_by": getattr(current_user, 'email', 'unknown')
    }


def _handle_list_all_users(session, parameters: Dict[str, Any], current_user: Any) -> Dict[str, Any]:
    """
    List all registered users with metadata.

    Supports pagination via limit and offset parameters.
    """
    from bondable.bond.providers.metadata import User

    # Get pagination params with sensible defaults and limits
    limit = min(parameters.get('limit', 50), 200)
    offset = parameters.get('offset', 0)

    # Get total count
    total_count = session.query(func.count(User.id)).scalar() or 0

    # Get users with pagination
    users = session.query(User).order_by(User.created_at.desc()).offset(offset).limit(limit).all()

    user_list = []
    for user in users:
        user_list.append({
            "user_id": user.id,
            "email": user.email,
            "name": user.name,
            "sign_in_method": user.sign_in_method,
            "created_at": user.created_at.isoformat() if user.created_at else None,
            "updated_at": user.updated_at.isoformat() if user.updated_at else None
        })

    return {
        "users": user_list,
        "total_count": total_count,
        "limit": limit,
        "offset": offset,
        "has_more": (offset + limit) < total_count
    }


def _handle_list_all_agents(session, parameters: Dict[str, Any], current_user: Any) -> Dict[str, Any]:
    """
    List all agents with their owners.

    Supports pagination via limit and offset parameters.
    """
    from bondable.bond.providers.metadata import AgentRecord, User

    # Get pagination params with sensible defaults and limits
    limit = min(parameters.get('limit', 50), 200)
    offset = parameters.get('offset', 0)

    # Get total count
    total_count = session.query(func.count(AgentRecord.agent_id)).scalar() or 0

    # Get agents with owner info
    agents = session.query(AgentRecord, User.email).outerjoin(
        User, AgentRecord.owner_user_id == User.id
    ).order_by(AgentRecord.created_at.desc()).offset(offset).limit(limit).all()

    agent_list = []
    for agent, owner_email in agents:
        agent_list.append({
            "agent_id": agent.agent_id,
            "name": agent.name,
            "owner_user_id": agent.owner_user_id,
            "owner_email": owner_email,
            "is_default": agent.is_default,
            "created_at": agent.created_at.isoformat() if agent.created_at else None
        })

    return {
        "agents": agent_list,
        "total_count": total_count,
        "limit": limit,
        "offset": offset,
        "has_more": (offset + limit) < total_count
    }


def _handle_get_agent_usage(session, parameters: Dict[str, Any], current_user: Any) -> Dict[str, Any]:
    """
    Get usage statistics for a specific agent.

    Returns thread count, message count, and recent activity for the agent.
    """
    from bondable.bond.providers.metadata import AgentRecord, Thread, User
    from bondable.bond.providers.bedrock.BedrockMetadata import BedrockMessage
    from bondable.bond.providers.bedrock.BedrockMetadata import BedrockAgentOptions

    agent_id = parameters.get('agent_id')
    if not agent_id:
        return {"error": "agent_id parameter is required"}

    # Get agent info
    agent = session.query(AgentRecord).filter_by(agent_id=agent_id).first()
    if not agent:
        return {"error": f"Agent {agent_id} not found"}

    # Get owner info
    owner = session.query(User).filter_by(id=agent.owner_user_id).first()

    # Get Bedrock-specific info
    bedrock_options = session.query(BedrockAgentOptions).filter_by(agent_id=agent_id).first()

    # Count threads that have messages from this agent
    # Note: Messages reference agent via metadata, but we can count threads
    # For now, we'll count total threads by owner as a proxy
    thread_count = session.query(func.count(Thread.thread_id)).filter(
        Thread.user_id == agent.owner_user_id
    ).scalar() or 0

    # Count messages (we'd need to check metadata for agent_id if available)
    # For now, count all messages by owner
    message_count = session.query(func.count(BedrockMessage.id)).filter(
        BedrockMessage.user_id == agent.owner_user_id
    ).scalar() or 0

    # Get last activity
    last_message = session.query(BedrockMessage).filter(
        BedrockMessage.user_id == agent.owner_user_id
    ).order_by(BedrockMessage.created_at.desc()).first()

    return {
        "agent_id": agent_id,
        "agent_name": agent.name,
        "owner_user_id": agent.owner_user_id,
        "owner_email": owner.email if owner else None,
        "is_default": agent.is_default,
        "created_at": agent.created_at.isoformat() if agent.created_at else None,
        "bedrock_agent_id": bedrock_options.bedrock_agent_id if bedrock_options else None,
        "mcp_tools": bedrock_options.mcp_tools if bedrock_options else [],
        "thread_count": thread_count,
        "message_count": message_count,
        "last_activity": last_message.created_at.isoformat() if last_message and last_message.created_at else None
    }


def _handle_get_recent_activity(session, parameters: Dict[str, Any], current_user: Any) -> Dict[str, Any]:
    """
    Get recent activity across the application.

    Returns new threads, messages, and users within the specified time period.
    """
    from bondable.bond.providers.metadata import User, AgentRecord, Thread
    from bondable.bond.providers.bedrock.BedrockMetadata import BedrockMessage

    # Get hours parameter with sensible default and limit
    hours = min(parameters.get('hours', 24), 168)  # Max 1 week
    cutoff_time = datetime.now(timezone.utc) - timedelta(hours=hours)

    # Count new users
    new_users = session.query(func.count(User.id)).filter(
        User.created_at >= cutoff_time
    ).scalar() or 0

    # Count new agents
    new_agents = session.query(func.count(AgentRecord.agent_id)).filter(
        AgentRecord.created_at >= cutoff_time
    ).scalar() or 0

    # Count new threads
    new_threads = session.query(func.count(Thread.thread_id)).filter(
        Thread.created_at >= cutoff_time
    ).scalar() or 0

    # Count new messages
    new_messages = session.query(func.count(BedrockMessage.id)).filter(
        BedrockMessage.created_at >= cutoff_time
    ).scalar() or 0

    # Get most active users (by message count) in period
    active_users = session.query(
        User.email,
        func.count(BedrockMessage.id).label('message_count')
    ).join(
        BedrockMessage, User.id == BedrockMessage.user_id
    ).filter(
        BedrockMessage.created_at >= cutoff_time
    ).group_by(User.id, User.email).order_by(
        func.count(BedrockMessage.id).desc()
    ).limit(10).all()

    active_users_list = [
        {"email": email, "message_count": count}
        for email, count in active_users
    ]

    return {
        "period_hours": hours,
        "period_start": cutoff_time.isoformat(),
        "period_end": datetime.now(timezone.utc).isoformat(),
        "new_users": new_users,
        "new_agents": new_agents,
        "new_threads": new_threads,
        "new_messages": new_messages,
        "most_active_users": active_users_list
    }


def _validate_sql_query(query: str) -> Optional[str]:
    """
    Validate that a SQL query is read-only.

    Args:
        query: The SQL query to validate

    Returns:
        None if valid, error message string if invalid
    """
    if not query or not query.strip():
        return "Query cannot be empty"

    # Normalize query for checking (uppercase, collapse whitespace)
    normalized = ' '.join(query.upper().split())

    # Must start with SELECT or WITH (for CTEs)
    if not (normalized.startswith('SELECT ') or normalized.startswith('WITH ')):
        return "Query must be a SELECT statement (or WITH clause for CTEs)"

    # Check for forbidden keywords
    # We check word boundaries to avoid false positives (e.g., "UPDATED_AT" column)
    for keyword in FORBIDDEN_SQL_KEYWORDS:
        # Match keyword as a whole word (not part of a column/table name)
        pattern = r'\b' + keyword + r'\b'
        if re.search(pattern, normalized):
            return f"Query contains forbidden keyword: {keyword}"

    # Check for multiple statements (semicolon followed by more SQL)
    # Allow trailing semicolon but not multiple statements
    parts = query.strip().rstrip(';').split(';')
    if len(parts) > 1:
        return "Multiple SQL statements are not allowed"

    return None  # Valid


def _get_database_dialect(session) -> str:
    """
    Detect the database dialect from the session.

    Returns:
        Database dialect name (e.g., 'sqlite', 'postgresql', 'mysql')
    """
    try:
        dialect = session.bind.dialect.name
        return dialect
    except Exception:
        return "unknown"


def _handle_execute_sql_query(session, parameters: Dict[str, Any], current_user: Any) -> Dict[str, Any]:
    """
    Execute a read-only SQL query.

    Validates the query to ensure it's read-only, then executes it and returns results.
    """
    from sqlalchemy import text

    query = parameters.get('query', '').strip()
    limit = min(parameters.get('limit', 100), 1000)  # Max 1000 rows

    # Detect database dialect
    db_dialect = _get_database_dialect(session)

    # Validate the query
    validation_error = _validate_sql_query(query)
    if validation_error:
        return {"error": validation_error, "database_dialect": db_dialect}

    user_email = getattr(current_user, 'email', 'unknown')
    LOGGER.info(f"[Admin MCP] Executing SQL query for {user_email} on {db_dialect}: {query[:200]}...")

    try:
        # Add LIMIT if not already present (to prevent massive result sets)
        query_upper = query.upper()
        if 'LIMIT' not in query_upper:
            # Remove trailing semicolon if present, add LIMIT, then re-add semicolon
            query = query.rstrip(';').strip()
            query = f"{query} LIMIT {limit}"

        result = session.execute(text(query))

        # Get column names
        columns = list(result.keys()) if result.keys() else []

        # Fetch rows (up to limit)
        rows = result.fetchmany(limit)

        # Convert to list of dicts
        data = []
        for row in rows:
            row_dict = {}
            for i, col in enumerate(columns):
                value = row[i]
                # Convert non-JSON-serializable types to strings
                if isinstance(value, (datetime,)):
                    value = value.isoformat()
                elif hasattr(value, '__dict__'):
                    value = str(value)
                row_dict[col] = value
            data.append(row_dict)

        result = {
            "database_dialect": db_dialect,
            "query": query,
            "columns": columns,
            "row_count": len(data),
            "limit_applied": limit,
            "data": data,
            "executed_by": user_email,
            "executed_at": datetime.now(timezone.utc).isoformat()
        }

        # Add helpful message for empty results so agent can respond appropriately
        if len(data) == 0:
            result["message"] = "Query executed successfully but returned no results. Please inform the user that the query completed but no matching records were found."

        return result

    except Exception as e:
        LOGGER.exception(f"[Admin MCP] SQL query execution error: {e}")
        return {
            "error": f"Query execution failed: {str(e)}",
            "database_dialect": db_dialect,
            "hint": "Check SQL syntax compatibility with the database dialect."
        }
