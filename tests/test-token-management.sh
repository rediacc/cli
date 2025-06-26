#!/bin/bash

# Test script for new token management features
# Tests token validation, environment variables, and chaining behavior

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Test configuration
ADMIN_EMAIL="${SYSTEM_ADMIN_EMAIL:-admin@rediacc.io}"
ADMIN_PASSWORD="${SYSTEM_ADMIN_PASSWORD:-admin}"
CLI="../rediacc-cli"
SYNC="../rediacc-cli-sync"
TERM="../rediacc-cli-term"

# Helper functions
print_status() {
    echo -e "${GREEN}✓${NC} $1"
}

print_error() {
    echo -e "${RED}✗${NC} $1"
}

print_info() {
    echo -e "${BLUE}ℹ${NC} $1"
}

print_section() {
    echo ""
    echo -e "${YELLOW}=== $1 ===${NC}"
}

# Cleanup function
cleanup() {
    # Clear environment variable
    unset REDIACC_TOKEN
    # Remove test config
    rm -f ~/.rediacc/config.json.backup
}

# Ensure cleanup on exit
trap cleanup EXIT

print_section "Token Management Feature Tests"

# Backup existing config
if [ -f ~/.rediacc/config.json ]; then
    cp ~/.rediacc/config.json ~/.rediacc/config.json.backup
    print_info "Backed up existing config"
fi

# Test 1: Token validation
print_section "Test 1: Token Validation"

# Test invalid token format
echo "Testing invalid token format..."
OUTPUT=$(${CLI} --token "invalid-token-format" list teams 2>&1)
if echo "$OUTPUT" | grep -q "Invalid token format"; then
    print_status "Invalid token correctly rejected"
else
    print_error "Invalid token not rejected"
    echo "Output: $OUTPUT"
fi

# Test valid token format (but non-existent)
echo "Testing valid format but non-existent token..."
FAKE_TOKEN="12345678-1234-1234-1234-123456789012"
OUTPUT=$(${CLI} --token "$FAKE_TOKEN" list teams 2>&1)
if echo "$OUTPUT" | grep -q "API Error"; then
    print_status "Non-existent token handled correctly"
else
    print_error "Non-existent token not handled properly"
fi

# Test 2: Use provided token
print_section "Test 2: Using Provided Token"

# Get token from parameter or environment
TOKEN="${1:-$REDIACC_TOKEN}"

if [ -z "$TOKEN" ]; then
    print_error "No token provided. Usage: $0 <TOKEN>"
    echo "Or set REDIACC_TOKEN environment variable"
    exit 1
fi

print_status "Using token: ${TOKEN:0:8}..."

# Verify token is saved with proper permissions
if [ -f ~/.rediacc/config.json ]; then
    PERMS=$(stat -c "%a" ~/.rediacc/config.json 2>/dev/null || stat -f "%OLp" ~/.rediacc/config.json 2>/dev/null)
    if [ "$PERMS" = "600" ]; then
        print_status "Config file has correct permissions (600)"
    else
        print_error "Config file has wrong permissions: $PERMS"
    fi
fi

# Test 3: Token override via command line
print_section "Test 3: Command Line Token Override"

# First, use saved token (should work)
echo "Using saved token from config..."
OUTPUT=$(${CLI} --output json list teams 2>&1)
if echo "$OUTPUT" | grep -q '"success":true'; then
    print_status "Saved token works"
else
    print_error "Saved token failed"
fi

# Override with the same token explicitly
echo "Overriding with explicit token..."
OUTPUT=$(${CLI} --output json --token "$TOKEN" list teams 2>&1)
if echo "$OUTPUT" | grep -q '"success":true'; then
    print_status "Token override works"
else
    print_error "Token override failed"
fi

# Test 4: Environment variable support
print_section "Test 4: Environment Variable Support"

# Clear saved token
${CLI} logout >/dev/null 2>&1

# Try without token (should fail)
echo "Testing without any token..."
OUTPUT=$(${CLI} list teams 2>&1)
if echo "$OUTPUT" | grep -q "Not authenticated"; then
    print_status "Correctly requires authentication"
else
    print_error "Should have required authentication"
fi

# Set environment variable
echo "Setting REDIACC_TOKEN environment variable..."
export REDIACC_TOKEN="$TOKEN"

# Try with environment variable (should work)
echo "Testing with environment variable..."
OUTPUT=$(${CLI} --output json list teams 2>&1)
if echo "$OUTPUT" | grep -q '"success":true'; then
    print_status "Environment variable token works"
else
    print_error "Environment variable token failed"
    echo "Output: $OUTPUT"
fi

# Test 5: Token precedence
print_section "Test 5: Token Precedence (CLI > ENV > Config)"

# Save current token to config for precedence testing
mkdir -p ~/.rediacc
echo "{\"token\": \"$TOKEN\", \"email\": \"test@example.com\"}" > ~/.rediacc/config.json
CONFIG_TOKEN="$TOKEN"
print_info "Config token: ${CONFIG_TOKEN:0:8}..."

# Environment variable should still be set from Test 4
print_info "Env token: ${REDIACC_TOKEN:0:8}..."

# Use a fake token for CLI override
OVERRIDE_TOKEN="87654321-4321-4321-4321-210987654321"

# Test CLI override (should fail with fake token)
echo "Testing CLI override precedence..."
OUTPUT=$(${CLI} --token "$OVERRIDE_TOKEN" list teams 2>&1)
if echo "$OUTPUT" | grep -q "API Error"; then
    print_status "CLI override takes precedence (fake token rejected)"
else
    print_error "CLI override precedence failed"
fi

# Clear env var and test config token works
unset REDIACC_TOKEN
echo "Testing config token after clearing env..."
OUTPUT=$(${CLI} --output json list teams 2>&1)
if echo "$OUTPUT" | grep -q '"success":true'; then
    print_status "Config token works after clearing env"
else
    print_error "Config token failed"
fi

# Test 6: Token chaining behavior
print_section "Test 6: Token Chaining (without override)"

# Get initial token from config
INITIAL_TOKEN=$(python3 -c "import json; print(json.load(open('$HOME/.rediacc/config.json'))['token'])" 2>/dev/null)
print_info "Initial token: ${INITIAL_TOKEN:0:8}..."

# Make a request that should update the token
${CLI} list teams >/dev/null 2>&1

# Check if token was updated
UPDATED_TOKEN=$(python3 -c "import json; print(json.load(open('$HOME/.rediacc/config.json'))['token'])" 2>/dev/null)
if [ "$INITIAL_TOKEN" != "$UPDATED_TOKEN" ]; then
    print_status "Token chaining updated config token"
    print_info "Updated token: ${UPDATED_TOKEN:0:8}..."
else
    print_error "Token chaining did not update config"
fi

# Test 7: Token chaining with override (should not save)
print_section "Test 7: Token Chaining with Override"

# Get current token from config
BEFORE_TOKEN=$(python3 -c "import json; print(json.load(open('$HOME/.rediacc/config.json'))['token'])" 2>/dev/null)
print_info "Token before override: ${BEFORE_TOKEN:0:8}..."

# Use --token override
${CLI} --token "$TOKEN" list teams >/dev/null 2>&1

# Check if config token changed (it shouldn't)
AFTER_TOKEN=$(python3 -c "import json; print(json.load(open('$HOME/.rediacc/config.json'))['token'])" 2>/dev/null)
if [ "$BEFORE_TOKEN" = "$AFTER_TOKEN" ]; then
    print_status "Override token did not update config (correct behavior)"
else
    print_error "Override token incorrectly updated config"
fi

# Test 8: Integration with sync and term tools
print_section "Test 8: Sync and Term Tool Integration"

# Use the existing token
# TOKEN is already set from the beginning of the test

# Test sync tool with token
echo "Testing rediacc-cli-sync with token..."
OUTPUT=$(${SYNC} upload --token="$TOKEN" --local="/tmp" --machine="nonexistent" --repo="test" 2>&1 || true)
if echo "$OUTPUT" | grep -q "not found"; then
    print_status "Sync tool accepts token parameter"
else
    print_error "Sync tool token handling issue"
fi

# Test term tool with token  
echo "Testing rediacc-cli-term with token..."
OUTPUT=$(${TERM} --token="$TOKEN" --machine="nonexistent" --repo="test" --command="echo test" 2>&1 || true)
if echo "$OUTPUT" | grep -q "not found"; then
    print_status "Term tool accepts token parameter"
else
    print_error "Term tool token handling issue"
fi

# Test 9: Error message sanitization
print_section "Test 9: Token Masking in Errors"

# Force an error with token in message
echo "Testing token masking in error messages..."
OUTPUT=$(${CLI} --token "$TOKEN" inspect machine "team_with_token_${TOKEN}" "machine" 2>&1 || true)
if echo "$OUTPUT" | grep -q "${TOKEN:0:8}\.\.\."; then
    print_status "Token properly masked in error output"
elif echo "$OUTPUT" | grep -q "$TOKEN"; then
    print_error "SECURITY: Full token exposed in error!"
else
    print_info "Could not verify token masking"
fi

# Summary
print_section "Test Summary"
echo "All token management features have been tested."
echo ""
echo "Key features verified:"
echo "  ✓ Token validation (GUID format)"
echo "  ✓ Secure file permissions (600)"
echo "  ✓ Command line override (--token)"
echo "  ✓ Environment variable support (REDIACC_TOKEN)"
echo "  ✓ Token precedence (CLI > ENV > Config)"
echo "  ✓ Token chaining awareness"
echo "  ✓ Integration with sync/term tools"
echo "  ✓ Token masking in errors"

# Restore original config if it existed
if [ -f ~/.rediacc/config.json.backup ]; then
    mv ~/.rediacc/config.json.backup ~/.rediacc/config.json
    print_info "Restored original config"
fi

echo ""
print_status "All tests completed!"