#!/usr/bin/env python3
"""
Sample MCP Server with JWT Authentication for BondAI Testing.

This server provides both public and protected tools to test MCP authentication:
- Public tools: greet, current_time (work without authentication)
- Protected tools: get_user_profile, fetch_protected_data, validate_auth (require JWT token)

Authentication uses FastMCP's standard Bearer token approach:
- JWT tokens are passed in the Authorization: Bearer <token> header
- The server validates tokens using JWTVerifier with HS256 shared secret
- Tools use get_access_token() to extract user information

Usage:
    export JWT_SECRET_KEY="your-secret-key-from-env"
    fastmcp run scripts/sample_mcp_server.py --transport streamable-http --port 5555
"""

from fastmcp import FastMCP
from fastmcp.server.dependencies import get_http_headers
from typing import List, Dict, Any, Optional
from datetime import datetime
import os
import logging
from jose import jwt, JWTError

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load JWT configuration
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "your-secret-key-here")
JWT_ISSUER = os.getenv("JWT_ISSUER", "bond-ai")  # Issuer claim from JWT
JWT_AUDIENCE = os.getenv("JWT_AUDIENCE", "mcp-server")  # Audience claim

print("=" * 70)
print("Sample MCP Server - JWT Authentication")
print("=" * 70)
print(f"JWT Secret Key: {'✅ Set' if JWT_SECRET_KEY != 'your-secret-key-here' else '❌ NOT SET'}")
print(f"JWT Issuer: {JWT_ISSUER}")
print(f"JWT Audience: {JWT_AUDIENCE}")
print("=" * 70)

# Initialize FastMCP server WITHOUT server-level authentication
# This allows tool discovery (listing) without auth, but tools validate JWT on execution
mcp = FastMCP("Authenticated MCP Server")

print("✅ FastMCP Server initialized (manual JWT validation in tools)")
print("   Tool listing: public | Tool execution: requires JWT")
print("=" * 70)


def get_user_from_token() -> Optional[Dict[str, Any]]:
    """
    Helper function to extract and validate JWT token from Authorization header.

    Returns:
        Dict with user info, or None if not authenticated
    """
    try:
        # Get HTTP headers
        headers = get_http_headers()
        auth_header = headers.get('authorization') or headers.get('Authorization')

        if not auth_header:
            logger.debug("No Authorization header found")
            return None

        # Extract Bearer token
        if not auth_header.startswith('Bearer '):
            logger.debug("Authorization header doesn't start with 'Bearer '")
            return None

        token = auth_header[7:]  # Remove "Bearer " prefix

        # Validate and decode JWT
        try:
            claims = jwt.decode(
                token,
                JWT_SECRET_KEY,
                algorithms=["HS256"],
                issuer=JWT_ISSUER,
                audience=JWT_AUDIENCE
            )
        except JWTError as e:
            # Try decoding without validation to see what's in the token
            try:
                from jose import jwt as jwt_module
                unverified_claims = jwt_module.get_unverified_claims(token)
                logger.warning(f"JWT validation failed: {e}")
                logger.warning(f"Token has: iss={unverified_claims.get('iss', 'NOT SET')}, aud={unverified_claims.get('aud', 'NOT SET')}")
                logger.warning(f"Expected: iss={JWT_ISSUER}, aud={JWT_AUDIENCE}")
                logger.warning(f"ACTION REQUIRED: Log out and log back in to get a new JWT token with correct claims")
            except Exception as debug_e:
                logger.warning(f"Could not decode token for debugging: {debug_e}")
            raise

        return {
            "authenticated": True,
            "email": claims.get('sub'),
            "user_id": claims.get('user_id'),
            "name": claims.get('name'),
            "given_name": claims.get('given_name'),
            "family_name": claims.get('family_name'),
            "provider": claims.get('provider'),
            "okta_sub": claims.get('okta_sub'),
        }
    except JWTError as e:
        logger.warning(f"JWT validation failed: {e}")
        return None
    except Exception as e:
        logger.debug(f"Error extracting token: {e}")
        return None


def require_auth() -> Dict[str, Any]:
    """
    Require authentication and return user info.

    Returns:
        Dict with user info

    Raises:
        PermissionError: If not authenticated
    """
    user = get_user_from_token()
    if not user or not user.get('authenticated'):
        raise PermissionError("Authentication required. Please provide a valid JWT token.")
    return user


# ============================================================================
# PUBLIC TOOLS (No authentication required)
# ============================================================================

@mcp.tool()
def current_time() -> str:
    """
    Get current server time.

    No authentication required.
    """
    user = get_user_from_token()
    curr_time = datetime.now().isoformat()
    logger.info(f"Current time requested by {user['email'] if user else 'anonymous'}: {curr_time}")
    return curr_time


@mcp.resource(uri="example://resource", name="ExampleResource")
def example_resource() -> str:
    """Example resource. No authentication required."""
    logger.info("Accessing example resource")
    return "This is an example resource content."


@mcp.tool(description="Fetch data from a SQL query")
def fetch_data(query: str) -> List[Dict[str, Any]]:
    """
    Fetch sample data based on a query.

    No authentication required.
    """
    user = get_user_from_token()
    logger.info(f"Fetch data called by {user['email'] if user else 'anonymous'} with query '{query}'")

    return [
        {'subscription_type': 'foo'},
        {'subscription_type': 'bar'},
        {'subscription_type': 'baz'}
    ]


# ============================================================================
# PROTECTED TOOLS (Authentication required)
# ============================================================================

@mcp.tool(description="Greet the authenticated user")
def greet() -> str:
    """
    Greet the authenticated user.

    REQUIRES AUTHENTICATION.
    Returns a personalized greeting for the authenticated user.
    """
    user = require_auth()
    logger.info(f"Greet called by {user['email']}")

    # Use given name if available, otherwise use email
    display_name = user.get('given_name') or user.get('name') or user['email']
    return f"Hello, {display_name}! Welcome back."


@mcp.tool(description="Get current user profile information")
def get_user_profile() -> Dict[str, Any]:
    """
    Get the authenticated user's profile.

    REQUIRES AUTHENTICATION.
    Returns user information from the JWT token.
    """
    user = require_auth()
    logger.info(f"User profile requested by {user['email']}")

    return {
        "email": user['email'],
        "user_id": user.get('user_id'),
        "name": user.get('name'),
        "given_name": user.get('given_name'),
        "family_name": user.get('family_name'),
        "provider": user.get('provider'),
        "okta_sub": user.get('okta_sub'),
        "authenticated": True
    }


@mcp.tool(description="Fetch protected user-specific data")
def fetch_protected_data(query: str) -> Dict[str, Any]:
    """
    Fetch data that requires authentication.

    REQUIRES AUTHENTICATION.
    Returns user-specific data based on the query.
    """
    user = require_auth()
    logger.info(f"Protected data fetch by {user['email']} with query: {query}")

    # Simulate user-specific data
    return {
        "query": query,
        "user_email": user['email'],
        "user_id": user.get('user_id'),
        "data": [
            {"id": 1, "item": f"Item 1 for {user['email']}", "private": True},
            {"id": 2, "item": f"Item 2 for {user['email']}", "private": True},
            {"id": 3, "item": f"Item 3 for {user['email']}", "private": True}
        ],
        "timestamp": datetime.now().isoformat()
    }


@mcp.tool(description="Create a user-specific resource")
def create_user_resource(
    resource_name: str,
    resource_type: str
) -> Dict[str, Any]:
    """
    Create a resource for the authenticated user.

    REQUIRES AUTHENTICATION.
    Simulates creating a resource that belongs to the authenticated user.
    """
    user = require_auth()
    logger.info(f"Creating resource '{resource_name}' for user {user['email']}")

    return {
        "success": True,
        "resource_id": f"res_{datetime.now().timestamp()}",
        "resource_name": resource_name,
        "resource_type": resource_type,
        "owner": user['email'],
        "owner_id": user.get('user_id'),
        "owner_name": f"{user.get('given_name', '')} {user.get('family_name', '')}".strip() or user.get('name'),
        "created_at": datetime.now().isoformat()
    }


@mcp.tool(description="Validate authentication token")
def validate_auth() -> Dict[str, Any]:
    """
    Validate authentication and return auth status.

    REQUIRES AUTHENTICATION.
    Useful for testing authentication flow.
    """
    user = require_auth()
    logger.info(f"Auth validation requested by {user['email']}")

    return {
        "authenticated": True,
        "method": "jwt_bearer",
        "user": {
            "email": user['email'],
            "user_id": user.get('user_id'),
            "name": user.get('name'),
            "provider": user.get('provider'),
            "given_name": user.get('given_name'),
            "family_name": user.get('family_name'),
            "okta_sub": user.get('okta_sub')
        },
        "timestamp": datetime.now().isoformat()
    }


# ============================================================================
# Server Startup
# ============================================================================

if __name__ == "__main__":
    logger.info("=" * 60)
    logger.info("Starting Authenticated MCP Server")
    logger.info("=" * 60)
    logger.info(f"Authentication: JWT Bearer Token (HS256)")
    logger.info(f"Issuer: {JWT_ISSUER}")
    logger.info(f"Audience: {JWT_AUDIENCE}")
    logger.info("")
    logger.info("Available Tools:")
    logger.info("  PUBLIC (no auth required):")
    logger.info("    - current_time() - Get current time")
    logger.info("    - fetch_data(query) - Get sample data")
    logger.info("")
    logger.info("  PROTECTED (auth required):")
    logger.info("    - greet() - Greet the authenticated user")
    logger.info("    - get_user_profile() - Get user profile")
    logger.info("    - fetch_protected_data(query) - Get user-specific data")
    logger.info("    - create_user_resource(name, type) - Create user resource")
    logger.info("    - validate_auth() - Validate authentication")
    logger.info("")
    logger.info("Authentication:")
    logger.info("  - JWT tokens passed via Authorization: Bearer <token> header")
    logger.info("  - Manual JWT validation in each protected tool")
    logger.info("  - Use require_auth() for protected tools")
    logger.info("=" * 60)

    mcp.run()
