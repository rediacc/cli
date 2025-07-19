#!/bin/bash

# Simple test to verify the setup works

# Source common utilities
source ./test-common.sh

# Load environment variables from .env file
if [ -f "../../.env" ]; then
    while IFS='=' read -r key value; do
        if [[ ! "$key" =~ ^[[:space:]]*# ]] && [[ -n "$key" ]]; then
            key=$(echo "$key" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')
            value=$(echo "$value" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')
            value=$(echo "$value" | sed 's/^"\(.*\)"$/\1/')
            export "$key=$value"
        fi
    done < "../../.env"
fi

# Get token
TOKEN=$(get_token "$1")
if [ -z "$TOKEN" ]; then
    echo "No token provided. Attempting to login..."
    
    ADMIN_EMAIL="${SYSTEM_ADMIN_EMAIL:-admin@rediacc.io}"
    ADMIN_PASSWORD="${SYSTEM_ADMIN_PASSWORD:-admin}"
    
    echo "Logging in with email: $ADMIN_EMAIL"
    LOGIN_OUTPUT=$(${CLI} login --email "$ADMIN_EMAIL" --password "$ADMIN_PASSWORD" 2>&1)
    
    if echo "$LOGIN_OUTPUT" | grep -qi "successfully logged in\|logged in as"; then
        echo "Login successful: $LOGIN_OUTPUT"
        TOKEN=$(get_token)
        echo "Retrieved token: ${TOKEN:0:8}..."
    else
        echo "Login failed: $LOGIN_OUTPUT"
        exit 1
    fi
else
    echo "Using provided token: ${TOKEN:0:8}..."
fi

# Test basic CLI command
echo ""
echo "Testing CLI help..."
${CLI} --help >/dev/null 2>&1 && echo "✓ CLI help works" || echo "✗ CLI help failed"

echo ""
echo "Testing list teams..."
OUTPUT=$(${CLI} --output json --token "$TOKEN" list teams 2>&1)
if echo "$OUTPUT" | grep -q '"success": *true'; then
    echo "✓ List teams successful"
    echo "$OUTPUT" | python3 -m json.tool | head -20
else
    echo "✗ List teams failed"
    echo "$OUTPUT"
fi

echo ""
echo "Simple test completed!"