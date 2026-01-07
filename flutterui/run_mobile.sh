#!/bin/bash

# Run the mobile version of Bond AI Flutter app

echo "Starting Bond AI Mobile App..."
echo "Make sure your API server is running on the configured URL"
echo ""

# Check if .env file exists
if [ ! -f .env ]; then
    echo "Error: .env file not found!"
    echo "Please copy .env.example to .env and configure it"
    exit 1
fi

# Display current configuration
echo "Current configuration:"
grep "API_BASE_URL" .env
grep "MOBILE_AGENT_ID" .env
echo ""

# Run the app
flutter run --target lib/main_mobile.dart "$@"
