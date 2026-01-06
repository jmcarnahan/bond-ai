#!/usr/bin/env python3
"""
Standalone test script for AWS Cognito OAuth2 integration.

This script tests the Cognito OAuth flow independently of the main project.

Usage:
    1. Set environment variables (or edit the CONFIG section below)
    2. Run: python scripts/test_cognito_oauth.py
    3. Open the printed URL in your browser
    4. After login, copy the 'code' from the callback URL
    5. Paste it when prompted

Environment variables:
    COGNITO_DOMAIN      - Cognito hosted UI domain (e.g., https://your-prefix.auth.us-west-2.amazoncognito.com)
    COGNITO_CLIENT_ID   - App client ID
    COGNITO_CLIENT_SECRET - App client secret (optional for public clients)
    COGNITO_REDIRECT_URI - Callback URL (default: http://localhost:8000/auth/cognito/callback)
"""

import os
import sys
import json
import webbrowser
import requests
from urllib.parse import urlencode, urlparse, parse_qs
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading

# ============================================================================
# CONFIGURATION - Edit these values or set environment variables
# ============================================================================

CONFIG = {
    # Cognito Hosted UI domain - this is different from the IdP endpoint!
    # Format: https://{domain-prefix}.auth.{region}.amazoncognito.com
    # OR custom domain: https://auth.yourdomain.com
    "domain": os.getenv("COGNITO_DOMAIN", "https://us-west-2udyqdksbm.auth.us-west-2.amazoncognito.com"),

    # App client ID from Cognito User Pool
    "client_id": os.getenv("COGNITO_CLIENT_ID", "4uog2crm587odi3pb39e7b8726"),

    # App client secret (leave empty if using public client without secret)
    "client_secret": os.getenv("COGNITO_CLIENT_SECRET", ""),

    # Redirect URI - must match what's configured in Cognito app client
    "redirect_uri": os.getenv("COGNITO_REDIRECT_URI", "http://localhost:8000/auth/cognito/callback"),

    # OAuth scopes
    "scopes": os.getenv("COGNITO_SCOPES", "email openid phone").split(),

    # Region (for constructing URLs if needed)
    "region": os.getenv("COGNITO_REGION", "us-west-2"),

    # User Pool ID (for constructing IdP endpoint)
    "pool_id": os.getenv("COGNITO_POOL_ID", "us-west-2_udyQDksBm"),
}

# ============================================================================
# COGNITO OAUTH FUNCTIONS
# ============================================================================

def get_idp_endpoint(region: str, pool_id: str) -> str:
    """Get the Cognito IdP endpoint (for JWKS, token verification)."""
    return f"https://cognito-idp.{region}.amazonaws.com/{pool_id}"


def get_authorization_url(config: dict) -> str:
    """Generate the Cognito authorization URL."""
    if not config["domain"]:
        print("\nERROR: COGNITO_DOMAIN is not set!")
        print("\nCognito requires a Hosted UI domain for OAuth flows.")
        print("This is different from the IdP endpoint (authority).")
        print("\nTo set up a domain:")
        print("1. Go to AWS Console > Cognito > User Pools")
        print(f"2. Select your pool: {config['pool_id']}")
        print("3. Go to 'App integration' tab")
        print("4. Under 'Domain', click 'Actions' > 'Create Cognito domain'")
        print("5. Choose a domain prefix (e.g., 'southbayequity')")
        print("6. Your domain will be: https://southbayequity.auth.us-west-2.amazoncognito.com")
        print("\nThen set: COGNITO_DOMAIN=https://your-prefix.auth.us-west-2.amazoncognito.com")
        sys.exit(1)

    params = {
        "client_id": config["client_id"],
        "response_type": "code",
        "scope": " ".join(config["scopes"]),
        "redirect_uri": config["redirect_uri"],
    }

    url = f"{config['domain'].rstrip('/')}/oauth2/authorize?{urlencode(params)}"
    return url


def exchange_code_for_tokens(config: dict, auth_code: str) -> dict:
    """Exchange authorization code for tokens."""
    token_url = f"{config['domain'].rstrip('/')}/oauth2/token"

    data = {
        "grant_type": "authorization_code",
        "client_id": config["client_id"],
        "code": auth_code,
        "redirect_uri": config["redirect_uri"],
    }

    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
    }

    # Add client secret if configured
    if config["client_secret"]:
        data["client_secret"] = config["client_secret"]

    print(f"\n--- Token Exchange ---")
    print(f"URL: {token_url}")
    print(f"Data: {json.dumps({k: v[:20] + '...' if k in ['code', 'client_secret'] and len(str(v)) > 20 else v for k, v in data.items()}, indent=2)}")

    response = requests.post(token_url, data=data, headers=headers)

    print(f"\nStatus: {response.status_code}")

    if response.status_code != 200:
        print(f"Error: {response.text}")
        return None

    tokens = response.json()
    print(f"Tokens received: {list(tokens.keys())}")
    return tokens


def get_user_info(config: dict, access_token: str) -> dict:
    """Get user info using access token."""
    userinfo_url = f"{config['domain'].rstrip('/')}/oauth2/userInfo"

    headers = {
        "Authorization": f"Bearer {access_token}",
    }

    print(f"\n--- User Info ---")
    print(f"URL: {userinfo_url}")

    response = requests.get(userinfo_url, headers=headers)

    print(f"Status: {response.status_code}")

    if response.status_code != 200:
        print(f"Error: {response.text}")
        return None

    user_info = response.json()
    return user_info


# ============================================================================
# LOCAL CALLBACK SERVER
# ============================================================================

class CallbackHandler(BaseHTTPRequestHandler):
    """Simple HTTP handler to capture OAuth callback."""

    auth_code = None

    def do_GET(self):
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)

        if "code" in params:
            CallbackHandler.auth_code = params["code"][0]
            self.send_response(200)
            self.send_header("Content-type", "text/html")
            self.end_headers()
            self.wfile.write(b"""
                <html>
                <head><title>Cognito OAuth Success</title></head>
                <body>
                    <h1>Authorization Successful!</h1>
                    <p>You can close this window and return to the terminal.</p>
                    <p>Auth code captured.</p>
                </body>
                </html>
            """)
        elif "error" in params:
            error = params.get("error", ["unknown"])[0]
            error_desc = params.get("error_description", ["No description"])[0]
            self.send_response(400)
            self.send_header("Content-type", "text/html")
            self.end_headers()
            self.wfile.write(f"""
                <html>
                <head><title>Cognito OAuth Error</title></head>
                <body>
                    <h1>Authorization Failed</h1>
                    <p>Error: {error}</p>
                    <p>Description: {error_desc}</p>
                </body>
                </html>
            """.encode())
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        pass  # Suppress default logging


def start_callback_server(port: int = 8000):
    """Start a local server to capture the OAuth callback."""
    server = HTTPServer(("localhost", port), CallbackHandler)
    thread = threading.Thread(target=server.handle_request)
    thread.daemon = True
    thread.start()
    return server, thread


# ============================================================================
# MAIN TEST FLOW
# ============================================================================

def print_config(config: dict):
    """Print current configuration."""
    print("\n" + "=" * 60)
    print("COGNITO OAUTH TEST CONFIGURATION")
    print("=" * 60)
    print(f"Region:       {config['region']}")
    print(f"Pool ID:      {config['pool_id']}")
    print(f"IdP Endpoint: {get_idp_endpoint(config['region'], config['pool_id'])}")
    print(f"Domain:       {config['domain'] or '(NOT SET)'}")
    print(f"Client ID:    {config['client_id']}")
    print(f"Client Secret: {'(set)' if config['client_secret'] else '(not set)'}")
    print(f"Redirect URI: {config['redirect_uri']}")
    print(f"Scopes:       {' '.join(config['scopes'])}")
    print("=" * 60)


def test_interactive():
    """Run interactive OAuth test with local callback server."""
    print_config(CONFIG)

    # Generate auth URL
    auth_url = get_authorization_url(CONFIG)

    print(f"\n--- Authorization URL ---")
    print(auth_url)

    # Parse redirect URI to get port
    parsed_redirect = urlparse(CONFIG["redirect_uri"])
    port = parsed_redirect.port or 8000

    # Ask user how they want to proceed
    print(f"\n--- Options ---")
    print(f"1. Start local server on port {port} and open browser automatically")
    print(f"2. Open browser manually, then paste the authorization code")
    print(f"3. Just print the URL (manual testing)")

    choice = input("\nSelect option (1/2/3): ").strip()

    if choice == "1":
        print(f"\nStarting callback server on port {port}...")
        server, thread = start_callback_server(port)

        print("Opening browser...")
        webbrowser.open(auth_url)

        print("Waiting for callback (login in the browser)...")
        thread.join(timeout=120)  # Wait up to 2 minutes

        if CallbackHandler.auth_code:
            auth_code = CallbackHandler.auth_code
            print(f"\nAuth code received!")
        else:
            print("\nTimeout waiting for callback. Try manual option.")
            return

    elif choice == "2":
        print(f"\nOpen this URL in your browser:")
        print(auth_url)
        print(f"\nAfter login, you'll be redirected to: {CONFIG['redirect_uri']}")
        print("Copy the 'code' parameter from the URL.")
        auth_code = input("\nPaste the authorization code: ").strip()

    else:
        print(f"\nAuthorization URL:")
        print(auth_url)
        print("\nTest manually, then run this script again to exchange the code.")
        return

    # Exchange code for tokens
    if not auth_code:
        print("No authorization code provided.")
        return

    tokens = exchange_code_for_tokens(CONFIG, auth_code)

    if not tokens:
        print("\nFailed to exchange code for tokens.")
        return

    print(f"\n--- Tokens ---")
    if "id_token" in tokens:
        # Decode ID token (without verification for display)
        import base64
        parts = tokens["id_token"].split(".")
        if len(parts) >= 2:
            payload = json.loads(base64.urlsafe_b64decode(parts[1] + "=="))
            print(f"ID Token claims: {json.dumps(payload, indent=2)}")

    # Get user info
    if "access_token" in tokens:
        user_info = get_user_info(CONFIG, tokens["access_token"])
        if user_info:
            print(f"\n--- User Info ---")
            print(json.dumps(user_info, indent=2))

            # Show normalized format (what we'd store)
            print(f"\n--- Normalized User Info (for Bond AI) ---")
            normalized = {
                "sub": user_info.get("sub"),
                "email": user_info.get("email"),
                "name": user_info.get("name") or user_info.get("email", "").split("@")[0],
                "given_name": user_info.get("given_name"),
                "family_name": user_info.get("family_name"),
                "email_verified": user_info.get("email_verified", False),
                "cognito_username": user_info.get("cognito:username"),
            }
            print(json.dumps(normalized, indent=2))

    print("\n" + "=" * 60)
    print("TEST COMPLETE!")
    print("=" * 60)


def test_check_domain():
    """Check if Cognito domain is configured."""
    print("\n--- Checking Cognito Configuration ---")

    # Try to discover domain from AWS (would need boto3)
    print(f"\nUser Pool ID: {CONFIG['pool_id']}")
    print(f"Region: {CONFIG['region']}")

    if CONFIG["domain"]:
        print(f"\nDomain is set: {CONFIG['domain']}")

        # Test if domain responds
        try:
            well_known_url = f"{CONFIG['domain']}/.well-known/openid-configuration"
            print(f"Testing: {well_known_url}")
            response = requests.get(well_known_url, timeout=5)
            if response.status_code == 200:
                print("Domain is accessible!")
                config = response.json()
                print(f"Issuer: {config.get('issuer')}")
                print(f"Authorization endpoint: {config.get('authorization_endpoint')}")
                print(f"Token endpoint: {config.get('token_endpoint')}")
                print(f"Userinfo endpoint: {config.get('userinfo_endpoint')}")
            else:
                print(f"Warning: Domain returned status {response.status_code}")
        except Exception as e:
            print(f"Error checking domain: {e}")
    else:
        print("\nDomain is NOT set.")
        print("\nTo find or create your Cognito domain:")
        print("1. Go to AWS Console > Cognito > User Pools")
        print(f"2. Select pool: {CONFIG['pool_id']}")
        print("3. Go to 'App integration' tab")
        print("4. Look for 'Domain' section")
        print("5. If no domain exists, click 'Actions' > 'Create Cognito domain'")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Test Cognito OAuth2 integration")
    parser.add_argument("--check", action="store_true", help="Check domain configuration")
    parser.add_argument("--domain", help="Set Cognito domain")
    parser.add_argument("--client-id", help="Set client ID")
    parser.add_argument("--client-secret", help="Set client secret")

    args = parser.parse_args()

    if args.domain:
        CONFIG["domain"] = args.domain
    if args.client_id:
        CONFIG["client_id"] = args.client_id
    if args.client_secret:
        CONFIG["client_secret"] = args.client_secret

    if args.check:
        test_check_domain()
    else:
        test_interactive()
