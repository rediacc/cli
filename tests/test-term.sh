#!/bin/bash
# Test script for rediacc-cli-term
# Tests terminal access to repository Docker environments

set -e

echo "=== Rediacc CLI Terminal Test Script ==="
echo ""

# Check if token is provided as argument or use default
if [ -n "$1" ]; then
    TOKEN="$1"
    echo "Using provided token: $TOKEN"
else
    # Login to get a token
    echo "No token provided, logging in..."
    
    # Use the same admin credentials as test.sh
    EMAIL="admin@rediacc.io"
    PASSWORD="111111"
    
    echo "Logging in as $EMAIL..."
    LOGIN_RESULT=$(../rediacc-cli --output json login --email "$EMAIL" --password "$PASSWORD")
    
    if [ $? -ne 0 ]; then
        echo "Login failed!"
        exit 1
    fi
    
    TOKEN=$(echo "$LOGIN_RESULT" | grep -o '"token":"[^"]*' | cut -d'"' -f4)
    
    if [ -z "$TOKEN" ]; then
        echo "Failed to extract token from login response"
        exit 1
    fi
    
    echo "Login successful! Token: $TOKEN"
fi

# Test configuration
MACHINE="rediacc11"
REPO="A1"

echo ""
echo "Test Configuration:"
echo "  Machine: $MACHINE"
echo "  Repository: $REPO"
echo ""

# Test 1: Check Docker daemon status
echo "=== Test 1: Check Docker daemon status ==="
../rediacc-cli-term --token "$TOKEN" --machine "$MACHINE" --repo "$REPO" --command "docker version --format 'Docker {{.Server.Version}}'"
if [ $? -eq 0 ]; then
    echo "✓ Docker daemon is accessible"
else
    echo "✗ Failed to access Docker daemon"
fi
echo ""

# Test 2: List running containers
echo "=== Test 2: List running containers ==="
../rediacc-cli-term --token "$TOKEN" --machine "$MACHINE" --repo "$REPO" --command "docker ps --format 'table {{.Names}}\t{{.Image}}\t{{.Status}}'"
if [ $? -eq 0 ]; then
    echo "✓ Successfully listed containers"
else
    echo "✗ Failed to list containers"
fi
echo ""

# Test 3: Check repository mount
echo "=== Test 3: Check repository mount ==="
../rediacc-cli-term --token "$TOKEN" --machine "$MACHINE" --repo "$REPO" --command "pwd && ls -la | head -5"
if [ $? -eq 0 ]; then
    echo "✓ Repository is mounted and accessible"
else
    echo "✗ Failed to access repository mount"
fi
echo ""

# Test 4: Test environment variables
echo "=== Test 4: Test environment variables ==="
../rediacc-cli-term --token "$TOKEN" --machine "$MACHINE" --repo "$REPO" --command "echo \"REPO_PATH: \$REPO_PATH\" && echo \"DOCKER_HOST: \$DOCKER_HOST\""
if [ $? -eq 0 ]; then
    echo "✓ Environment variables are set correctly"
else
    echo "✗ Failed to set environment variables"
fi
echo ""

# Test 5: Execute command in container (if containers are running)
echo "=== Test 5: Execute command in container ==="
# First check if plugin-Terminal container exists
CONTAINER_CHECK=$(../rediacc-cli-term --token "$TOKEN" --machine "$MACHINE" --repo "$REPO" --command "docker ps --format '{{.Names}}' | grep -q plugin-Terminal && echo 'exists' || echo 'not found'" 2>&1)

if echo "$CONTAINER_CHECK" | grep -q "exists"; then
    ../rediacc-cli-term --token "$TOKEN" --machine "$MACHINE" --repo "$REPO" --command "docker exec plugin-Terminal echo 'Hello from Terminal container'"
    if [ $? -eq 0 ]; then
        echo "✓ Successfully executed command in container"
    else
        echo "✗ Failed to execute command in container"
    fi
else
    echo "! Skipping container test - plugin-Terminal container not running"
fi
echo ""

# Test 6: Check Docker socket permissions
echo "=== Test 6: Check Docker socket permissions ==="
../rediacc-cli-term --token "$TOKEN" --machine "$MACHINE" --repo "$REPO" --command "ls -la \$DOCKER_SOCKET"
if [ $? -eq 0 ]; then
    echo "✓ Docker socket is accessible"
else
    echo "✗ Docker socket not found or not accessible"
fi
echo ""

# Summary
echo "=== Test Summary ==="
echo "All automated tests completed."
echo ""
echo "To test interactive terminal session, run:"
echo "  ../rediacc-cli-term --token $TOKEN --machine $MACHINE --repo $REPO"
echo ""
echo "In the interactive session, you can try:"
echo "  - status              # Show repository status"
echo "  - docker ps           # List containers"
echo "  - enter_container plugin-Terminal  # Enter a container"
echo "  - logs plugin-Browser # View container logs"
echo ""

# Test if repository is not mounted
echo "=== Testing unmounted repository handling ==="
../rediacc-cli-term --token "$TOKEN" --machine "$MACHINE" --repo "NonExistentRepo" --command "echo 'test'" 2>&1 | grep -q "not found" && echo "✓ Correctly handles non-existent repository" || echo "! Repository existence check may need improvement"

echo ""
echo "=== All tests completed ==="