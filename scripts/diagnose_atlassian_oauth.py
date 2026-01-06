#!/usr/bin/env python3
"""
Diagnose Atlassian OAuth issues.

Tests various redirect URIs and parameters to understand what Atlassian accepts.
"""

import requests
import sys
from urllib.parse import urlencode

ATLASSIAN_AUTHORIZE_URL = "https://mcp.atlassian.com/v1/authorize"
CLIENT_ID = "yuhIYKIc2ZfVVRC6"

def test_url(description, params):
    """Test an authorization URL with given parameters."""
    print(f"\n{'='*70}")
    print(f"TEST: {description}")
    print(f"{'='*70}")

    url = f"{ATLASSIAN_AUTHORIZE_URL}?{urlencode(params)}"
    print(f"URL: {url}\n")

    try:
        # Don't follow redirects - we want to see the initial response
        response = requests.get(url, allow_redirects=False, timeout=10)

        print(f"Status Code: {response.status_code}")
        print(f"Headers:")
        for key, value in response.headers.items():
            if key.lower() in ['location', 'content-type', 'content-length', 'server']:
                print(f"  {key}: {value}")

        if response.status_code >= 400:
            print(f"\nResponse Body (first 500 chars):")
            print(response.text[:500])
        elif response.status_code in [301, 302, 303, 307, 308]:
            print(f"\nRedirect Location: {response.headers.get('Location', 'N/A')}")
        else:
            print(f"\nResponse successful!")

        return response.status_code < 400

    except requests.exceptions.Timeout:
        print("❌ Request timed out")
        return False
    except requests.exceptions.RequestException as e:
        print(f"❌ Request failed: {e}")
        return False


def main():
    """Run diagnostic tests."""
    print("="*70)
    print("ATLASSIAN MCP OAUTH DIAGNOSTICS")
    print("="*70)

    results = {}

    # Test 1: Minimal parameters with mcp-remote redirect_uri
    results['mcp-remote'] = test_url(
        "Original mcp-remote redirect_uri (port 5598)",
        {
            "response_type": "code",
            "client_id": CLIENT_ID,
            "redirect_uri": "http://localhost:5598/oauth/callback",
            "state": "test-state",
            "code_challenge": "test-challenge",
            "code_challenge_method": "S256",
            "scope": "openid email profile"
        }
    )

    # Test 2: Bond backend redirect_uri
    results['bond-8000'] = test_url(
        "Bond backend redirect_uri (port 8000)",
        {
            "response_type": "code",
            "client_id": CLIENT_ID,
            "redirect_uri": "http://localhost:8000/connections/atlassian/callback",
            "state": "test-state",
            "code_challenge": "test-challenge",
            "code_challenge_method": "S256",
            "scope": "openid email profile"
        }
    )

    # Test 3: Different port
    results['port-3000'] = test_url(
        "Random port (3000)",
        {
            "response_type": "code",
            "client_id": CLIENT_ID,
            "redirect_uri": "http://localhost:3000/callback",
            "state": "test-state",
            "code_challenge": "test-challenge",
            "code_challenge_method": "S256",
            "scope": "openid email profile"
        }
    )

    # Test 4: Without PKCE
    results['no-pkce'] = test_url(
        "Without PKCE parameters",
        {
            "response_type": "code",
            "client_id": CLIENT_ID,
            "redirect_uri": "http://localhost:8000/connections/atlassian/callback",
            "state": "test-state",
            "scope": "openid email profile"
        }
    )

    # Test 5: Minimal required params only
    results['minimal'] = test_url(
        "Minimal params (response_type, client_id, redirect_uri)",
        {
            "response_type": "code",
            "client_id": CLIENT_ID,
            "redirect_uri": "http://localhost:8000/connections/atlassian/callback",
        }
    )

    # Test 6: Just check if endpoint is reachable
    print(f"\n{'='*70}")
    print("TEST: Basic endpoint reachability")
    print(f"{'='*70}")
    print(f"URL: {ATLASSIAN_AUTHORIZE_URL}\n")
    try:
        response = requests.get(ATLASSIAN_AUTHORIZE_URL, timeout=10)
        print(f"Status Code: {response.status_code}")
        print(f"Response (first 200 chars): {response.text[:200]}")
        results['endpoint'] = response.status_code < 500
    except Exception as e:
        print(f"❌ Failed: {e}")
        results['endpoint'] = False

    # Summary
    print(f"\n{'='*70}")
    print("SUMMARY")
    print(f"{'='*70}")
    for test_name, passed in results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status} - {test_name}")

    # Analysis
    print(f"\n{'='*70}")
    print("ANALYSIS")
    print(f"{'='*70}")

    if not results.get('endpoint', False):
        print("\n❌ The Atlassian authorization endpoint is not reachable or has issues.")
        print("   This might be a temporary service problem on Atlassian's side.")
    elif results.get('mcp-remote', False) and not results.get('bond-8000', False):
        print("\n⚠️  The mcp-remote redirect_uri works, but Bond's doesn't.")
        print("   Atlassian restricts to port 5598 specifically.")
        print("   Recommendation: Implement Option 3 (keep mcp-remote for Atlassian)")
    elif results.get('mcp-remote', False) and results.get('bond-8000', False):
        print("\n✅ Both redirect URIs work!")
        print("   Atlassian accepts localhost on different ports.")
        print("   The 500 error might be temporary or due to other parameters.")
    elif not results.get('mcp-remote', False) and not results.get('bond-8000', False):
        print("\n❌ Neither redirect_uri works.")
        print("   This suggests:")
        print("   1. Atlassian MCP service is having issues")
        print("   2. The client_id requires special configuration")
        print("   3. Additional parameters are required")
    else:
        print("\n🤔 Unexpected results. Manual investigation needed.")

    print(f"\n{'='*70}")

    return 0 if all(results.values()) else 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n\n⚠️  Diagnostics interrupted")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
