#!/bin/bash

# Quick integration test for token management changes
# This tests the actual workflow with real commands

set -e  # Exit on error

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${YELLOW}=== Token Management Integration Test ===${NC}"
echo ""

# Test tools
CLI="../rediacc-cli"
SYNC="../rediacc-cli-sync"
TERM="../rediacc-cli-term"

# Load environment
if [ -f "../.env" ]; then
    source ../.env
fi

# Get token from parameter or environment
TOKEN="${1:-$REDIACC_TOKEN}"

if [ -z "$TOKEN" ]; then
    echo -e "${RED}✗${NC} No token provided. Usage: $0 <TOKEN>"
    echo "Or set REDIACC_TOKEN environment variable"
    exit 1
fi

echo "1. Using provided token..."
echo -e "${GREEN}✓${NC} Token: ${TOKEN:0:8}..."

echo ""
echo "2. Testing CLI with --token override..."
OUTPUT=$(${CLI} --output json --token "$TOKEN" list teams)
if echo "$OUTPUT" | grep -q '"success": *true'; then
    echo -e "${GREEN}✓${NC} CLI works with --token override"
else
    echo -e "${RED}✗${NC} CLI failed with --token override"
    echo "Output: $OUTPUT"
    exit 1
fi

echo ""
echo "3. Testing environment variable..."
# Use the provided token for env var test
# Move config aside temporarily to test env var takes precedence
mv ~/.rediacc/config.json ~/.rediacc/config.json.tmp 2>/dev/null || true
export REDIACC_TOKEN="$TOKEN"
OUTPUT=$(${CLI} --output json list teams)
# Restore config
mv ~/.rediacc/config.json.tmp ~/.rediacc/config.json 2>/dev/null || true
if echo "$OUTPUT" | grep -q '"success": *true'; then
    echo -e "${GREEN}✓${NC} CLI works with REDIACC_TOKEN env var"
else
    echo -e "${RED}✗${NC} CLI failed with env var"
    exit 1
fi
unset REDIACC_TOKEN

echo ""
echo "4. Testing invalid token format..."
OUTPUT=$(${CLI} --token "not-a-valid-token" list teams 2>&1 || true)
if echo "$OUTPUT" | grep -q "Invalid token format"; then
    echo -e "${GREEN}✓${NC} Invalid token format correctly rejected"
else
    echo -e "${RED}✗${NC} Invalid token format not caught"
    exit 1
fi

echo ""
echo "5. Testing token masking in errors..."
# Force an error that might contain the token
OUTPUT=$(${CLI} --token "$TOKEN" inspect machine "team_${TOKEN}" "machine" 2>&1 || true)
if echo "$OUTPUT" | grep -q "$TOKEN"; then
    echo -e "${RED}✗${NC} SECURITY WARNING: Full token exposed in error!"
    exit 1
else
    echo -e "${GREEN}✓${NC} Token not exposed in error messages"
fi

echo ""
echo "6. Testing sync tool integration..."
# This will fail because machine doesn't exist, but that's ok - we're testing token acceptance
OUTPUT=$(${SYNC} upload --token "$TOKEN" --local /tmp --machine nonexistent --repo test 2>&1 || true)
if echo "$OUTPUT" | grep -q "Fetching machine information"; then
    echo -e "${GREEN}✓${NC} Sync tool accepts and uses token"
else
    echo -e "${RED}✗${NC} Sync tool token integration issue"
    exit 1
fi

echo ""
echo "7. Testing term tool integration..."
OUTPUT=$(${TERM} --token "$TOKEN" --machine nonexistent --repo test --command "echo test" 2>&1 || true)
if echo "$OUTPUT" | grep -q "Fetching machine information"; then
    echo -e "${GREEN}✓${NC} Term tool accepts and uses token"
else
    echo -e "${RED}✗${NC} Term tool token integration issue"
    exit 1
fi

echo ""
echo "8. Testing config file permissions..."
if [ -f ~/.rediacc/config.json ]; then
    PERMS=$(stat -c "%a" ~/.rediacc/config.json 2>/dev/null || stat -f "%OLp" ~/.rediacc/config.json 2>/dev/null)
    if [ "$PERMS" = "600" ]; then
        echo -e "${GREEN}✓${NC} Config file has secure permissions (600)"
    else
        echo -e "${RED}✗${NC} Config file has insecure permissions: $PERMS"
        exit 1
    fi
fi

echo ""
echo -e "${GREEN}=== All integration tests passed! ===${NC}"
echo ""
echo "Token management is working correctly with:"
echo "  • Token validation"
echo "  • Command line override"
echo "  • Environment variables" 
echo "  • Secure storage"
echo "  • Error masking"
echo "  • Tool integration"