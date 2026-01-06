#!/usr/bin/env python3
"""
Script to recreate database tables via admin API endpoint.

This script:
1. Uses your JWT token (from login or provided as argument)
2. Calls the /admin/recreate-table/{table_name} endpoint
3. Drops the specified table (with CASCADE to remove FK constraints)
4. Recreates the table using metadata.create_all()

Usage:
    # Local development (generates token)
    python scripts/recreate_table.py connection_configs

    # Deployed environment (provide JWT token)
    python scripts/recreate_table.py connection_configs --url https://rqs8cicg8h.us-west-2.awsapprunner.com --token YOUR_JWT_TOKEN

To get your JWT token:
    1. Login to https://jid5jmztei.us-west-2.awsapprunner.com
    2. Open browser DevTools > Application > Local Storage
    3. Copy the JWT token value
"""

import requests
import sys
import os
from datetime import datetime, timedelta, timezone


def create_local_admin_token(admin_email: str = "john_carnahan@mcafee.com") -> str:
    """Create a JWT token for local development."""
    try:
        from jose import jwt
        from bondable.bond.config import Config
        jwt_config = Config.config().get_jwt_config()

        token_data = {
            "sub": admin_email,
            "name": "John Carnahan",
            "user_id": f"admin_{admin_email.split('@')[0]}",
            "provider": "okta",
            "exp": datetime.now(timezone.utc) + timedelta(minutes=jwt_config.ACCESS_TOKEN_EXPIRE_MINUTES),
            "iss": "bond-ai",
            "aud": "mcp-server"
        }

        token = jwt.encode(token_data, jwt_config.JWT_SECRET_KEY, algorithm=jwt_config.JWT_ALGORITHM)
        return token

    except Exception as e:
        print(f"❌ Error creating token: {e}")
        raise


def recreate_table(table_name: str, token: str, base_url: str = "http://localhost:8000"):
    """Call the admin endpoint to recreate a table."""
    try:
        headers = {
            'Authorization': f'Bearer {token}'
        }

        # Call the recreation endpoint
        url = f"{base_url.rstrip('/')}/admin/recreate-table/{table_name}"
        print(f"📡 Calling: POST {url}")

        response = requests.post(url, headers=headers)
        response.raise_for_status()

        result = response.json()

        print(f"\n✅ Success!")
        print(f"   Status: {result['status']}")
        print(f"   Message: {result['message']}")
        print(f"   Table existed: {result['table_existed']}")
        print(f"   Table recreated: {result['table_recreated']}")

        return result

    except requests.exceptions.HTTPError as e:
        print(f"\n❌ HTTP Error: {e}")
        if e.response is not None:
            try:
                error_detail = e.response.json()
                print(f"   Detail: {error_detail}")
            except:
                print(f"   Response: {e.response.text}")
        raise
    except Exception as e:
        print(f"\n❌ Error: {e}")
        raise


def main():
    if len(sys.argv) < 2:
        print("Usage: python scripts/recreate_table.py <table_name> [--url <base_url>] [--token <jwt_token>]")
        print("\nExamples:")
        print("  # Local development")
        print("  python scripts/recreate_table.py connection_configs")
        print()
        print("  # Deployed environment")
        print("  python scripts/recreate_table.py connection_configs --url https://rqs8cicg8h.us-west-2.awsapprunner.com --token YOUR_JWT_TOKEN")
        sys.exit(1)

    table_name = sys.argv[1]

    # Parse optional arguments
    base_url = "http://localhost:8000"
    token = None

    if "--url" in sys.argv:
        url_index = sys.argv.index("--url")
        if url_index + 1 < len(sys.argv):
            base_url = sys.argv[url_index + 1]

    if "--token" in sys.argv:
        token_index = sys.argv.index("--token")
        if token_index + 1 < len(sys.argv):
            token = sys.argv[token_index + 1]

    print(f"🗄️  Table Recreation Script")
    print(f"   Table: {table_name}")
    print(f"   URL: {base_url}")

    # If no token provided and not localhost, show instructions
    if not token and "localhost" not in base_url:
        print("\n⚠️  No JWT token provided for deployed environment!")
        print("\nTo get your JWT token:")
        print("  1. Login to https://jid5jmztei.us-west-2.awsapprunner.com")
        print("  2. Open browser DevTools (F12)")
        print("  3. Go to Application > Local Storage > https://jid5jmztei.us-west-2.awsapprunner.com")
        print("  4. Copy the token value")
        print("\nThen run:")
        print(f"  python scripts/recreate_table.py {table_name} --url {base_url} --token YOUR_TOKEN_HERE")
        sys.exit(1)

    # Generate local token if none provided
    if not token:
        print(f"🔑 Creating local admin JWT token...")
        token = create_local_admin_token()
    else:
        print(f"🔑 Using provided JWT token...")

    print()

    result = recreate_table(table_name, token, base_url)

    print("\n✨ Done!")


if __name__ == "__main__":
    main()
