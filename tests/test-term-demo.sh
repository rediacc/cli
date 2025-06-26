#!/bin/bash
# Test script to demonstrate rediacc-cli-term functionality

echo "=== Testing Rediacc CLI Terminal ==="
echo ""

# Get token from parameter or environment
TOKEN="${1:-$REDIACC_TOKEN}"

if [ -z "$TOKEN" ]; then
    echo "Error: No token provided. Usage: $0 <TOKEN>"
    echo "Or set REDIACC_TOKEN environment variable"
    exit 1
fi

echo "Using token: ${TOKEN:0:8}..."
echo ""

# Test 1: Execute a simple command
echo "1. Testing command execution:"
../rediacc-cli-term --token "$TOKEN" --machine rediacc11 --repo A1 --command "docker ps --format 'table {{.Names}}\t{{.Status}}'"

echo ""
echo "2. Testing Docker container access:"
../rediacc-cli-term --token "$TOKEN" --machine rediacc11 --repo A1 --command "docker exec plugin-Terminal echo 'Hello from Terminal plugin container'"

echo ""
echo "3. Testing machine-only connection:"
../rediacc-cli-term --token "$TOKEN" --machine rediacc11 --command "echo 'Connected to machine:' && hostname && echo 'Current user:' && whoami"

echo ""
echo "4. For interactive terminal sessions:"
echo ""
echo "   A. Repository session (with Docker environment):"
echo "      ../rediacc-cli-term --token "$TOKEN" --machine rediacc11 --repo A1"
echo ""
echo "      This gives you:"
echo "      - Repository-specific Docker environment"
echo "      - Helper functions: status, enter_container, logs"
echo "      - Working directory set to repository mount"
echo ""
echo "   B. Machine session (direct access):"
echo "      ../rediacc-cli-term --token "$TOKEN" --machine rediacc11"
echo ""
echo "      This gives you:"
echo "      - Direct machine access"
echo "      - Access to all repositories and containers"
echo "      - System administration capabilities"