#!/usr/bin/env python3
"""
Simple test script for MCP REST API endpoints.
Tests the /mcp/tools, /mcp/resources, and /mcp/status endpoints.
"""

import asyncio
import requests
import json
import sys
import os
from datetime import datetime, timedelta, timezone
from jose import jwt
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configuration
API_BASE_URL = "http://localhost:8000"
TEST_USER_EMAIL = "test@example.com"
TEST_USER_NAME = "Test User"

def create_test_jwt_token():
    """Create a test JWT token for API authentication."""
    try:
        # Try to get JWT config from environment or use defaults
        JWT_SECRET_KEY = os.getenv('JWT_SECRET_KEY', 'your-secret-key-here-make-it-long-and-secure')
        JWT_ALGORITHM = os.getenv('JWT_ALGORITHM', 'HS256')
        
        # Create token data
        token_data = {
            "sub": TEST_USER_EMAIL,
            "name": TEST_USER_NAME,
            "exp": datetime.now(timezone.utc) + timedelta(hours=1)
        }
        
        # Create JWT token
        access_token = jwt.encode(token_data, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)
        return access_token
    except Exception as e:
        print(f"Error creating JWT token: {e}")
        print("Make sure you have the correct JWT configuration in your .env file")
        return None

def test_mcp_endpoint(endpoint, token):
    """Test a single MCP endpoint."""
    url = f"{API_BASE_URL}/mcp/{endpoint}"
    headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json'
    }
    
    print(f"\n{'='*60}")
    print(f"Testing: GET {url}")
    print(f"{'='*60}")
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        
        print(f"Status Code: {response.status_code}")
        print(f"Headers: {dict(response.headers)}")
        
        if response.status_code == 200:
            try:
                data = response.json()
                print(f"Response Data:")
                print(json.dumps(data, indent=2))
                
                if endpoint in ['tools', 'resources']:
                    print(f"\nFound {len(data)} {endpoint}")
                    if data:
                        print(f"First item: {data[0]}")
                
            except json.JSONDecodeError as e:
                print(f"Failed to parse JSON response: {e}")
                print(f"Raw response: {response.text}")
        else:
            print(f"Error Response: {response.text}")
            
    except requests.exceptions.RequestException as e:
        print(f"Request failed: {e}")
    except Exception as e:
        print(f"Unexpected error: {e}")

def test_health_endpoint():
    """Test the health endpoint to verify server is running."""
    url = f"{API_BASE_URL}/health"
    
    print(f"\n{'='*60}")
    print(f"Testing: GET {url}")
    print(f"{'='*60}")
    
    try:
        response = requests.get(url, timeout=5)
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"Response: {data}")
            return True
        else:
            print(f"Health check failed: {response.text}")
            return False
            
    except requests.exceptions.RequestException as e:
        print(f"Health check failed: {e}")
        print("Make sure the FastAPI server is running on http://localhost:8000")
        return False

def main():
    """Main test function."""
    print("MCP REST API Test Script")
    print("=" * 60)
    
    # Test health endpoint first
    if not test_health_endpoint():
        print("\n❌ Server is not responding. Please start the FastAPI server first.")
        print("Run: uvicorn bondable.rest.main:app --reload --host 0.0.0.0 --port 8000")
        sys.exit(1)
    
    print("\n✅ Server is running!")
    
    # Create test JWT token
    token = create_test_jwt_token()
    if not token:
        print("\n❌ Failed to create JWT token")
        sys.exit(1)
    
    print(f"\n✅ Created JWT token: {token[:50]}...")
    
    # Test MCP endpoints
    endpoints = ['status', 'tools', 'resources']
    
    for endpoint in endpoints:
        test_mcp_endpoint(endpoint, token)
    
    print(f"\n{'='*60}")
    print("Test Summary:")
    print("- Health check: ✅")
    print("- JWT token: ✅")
    print("- MCP endpoints tested: ✅")
    print(f"{'='*60}")
    print("\nIf you see empty lists for tools/resources, that's expected")
    print("when no MCP servers are configured in your backend.")
    print("\nTo configure MCP servers, set the BOND_MCP_CONFIG environment variable")
    print("or check the scripts/test_mcp_integration.py for examples.")

if __name__ == "__main__":
    main()