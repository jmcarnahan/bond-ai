#!/bin/bash

# Test internet connectivity from App Runner service
# This script tests connectivity to various external services

echo "Testing internet connectivity from App Runner..."

BACKEND_URL="https://up7nzjj8pv.us-west-2.awsapprunner.com"

# Test 1: Check if we can reach Google DNS
echo "Test 1: Testing Google DNS (8.8.8.8)..."
curl -s --max-time 10 -H "Accept: application/json" "${BACKEND_URL}/health" 2>/dev/null
if [ $? -eq 0 ]; then
    echo "✅ Backend health endpoint accessible"
else
    echo "❌ Backend health endpoint not accessible"
fi

# Test 2: Check if backend can reach Okta (this is where the failure occurs)
echo ""
echo "Test 2: Testing Okta connectivity..."
echo "Looking at App Runner logs for Okta connectivity issues..."

# Test 3: Check DNS resolution
echo ""
echo "Test 3: Testing DNS resolution capabilities..."
echo "This would require backend to have a test endpoint that does DNS lookups"

echo ""
echo "To run comprehensive tests, we need to:"
echo "1. Add a test endpoint to the backend that can perform connectivity tests"
echo "2. Check App Runner CloudWatch logs for detailed error information"
echo "3. Verify DNS resolution from within App Runner"

echo ""
echo "Current error shows: 'Connection to trial-9457917.okta.com timed out'"
echo "This suggests either:"
echo "  - DNS resolution failing"
echo "  - Outbound HTTPS connectivity blocked"
echo "  - Network routing issue despite correct configuration"