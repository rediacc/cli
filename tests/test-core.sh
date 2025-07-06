#!/bin/bash

# Core CLI functionality tests
# Tests: authentication, token management, basic API operations

set -e  # Exit on error

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Source common test utilities
source ./test-common.sh

print_header "Core CLI Functionality Tests"

# Get token
TOKEN=$(require_token "$1")
print_info "Using token: ${TOKEN:0:8}..."

# Test 1: Basic CLI functionality
print_subheader "Basic CLI Operations"

run_test "CLI help command" "${CLI} --help >/dev/null 2>&1"
run_test "CLI version command" "${CLI} --version >/dev/null 2>&1"

# Test 2: Token management
print_subheader "Token Management"

# Test --token override
OUTPUT=$(${CLI} --output json --token "$TOKEN" list teams 2>&1)
check_success "$OUTPUT" "CLI works with --token parameter"

# Test environment variable (temporarily move config)
if [ -f ~/.rediacc/config.json ]; then
    mv ~/.rediacc/config.json ~/.rediacc/config.json.bak
fi
export REDIACC_TOKEN="$TOKEN"
OUTPUT=$(${CLI} --output json list teams 2>&1)
check_success "$OUTPUT" "CLI works with REDIACC_TOKEN env var"
unset REDIACC_TOKEN
if [ -f ~/.rediacc/config.json.bak ]; then
    mv ~/.rediacc/config.json.bak ~/.rediacc/config.json
fi

# Test invalid token format
OUTPUT=$(${CLI} --token "invalid-token" list teams 2>&1 || true)
check_contains "$OUTPUT" "Invalid token format" "Invalid token format rejected"

# Test token masking in errors
OUTPUT=$(${CLI} --token "$TOKEN" inspect machine "nonexistent_${TOKEN}" "machine" 2>&1 || true)
check_not_contains "$OUTPUT" "$TOKEN" "Token not exposed in error messages"

# Test 3: Basic API operations
print_subheader "Basic API Operations"

# List teams
OUTPUT=$(${CLI} --output json --token "$TOKEN" list teams)
check_success "$OUTPUT" "List teams"

# List companies
OUTPUT=$(${CLI} --output json --token "$TOKEN" list companies)
check_success "$OUTPUT" "List companies"

# Get user info
OUTPUT=$(${CLI} --output json --token "$TOKEN" me)
check_success "$OUTPUT" "Get user information"

# Test 4: Parameter validation
print_subheader "Parameter Validation"

# Test missing required parameters
OUTPUT=$(${CLI} --token "$TOKEN" list machines 2>&1 || true)
check_contains "$OUTPUT" "required" "Missing required parameter caught"

# Test invalid command
OUTPUT=$(${CLI} --token "$TOKEN" invalid-command 2>&1 || true)
check_contains "$OUTPUT" "usage" "Invalid command caught"

# Test 5: Output formats
print_subheader "Output Formats"

# JSON output
OUTPUT=$(${CLI} --output json --token "$TOKEN" list teams)
if echo "$OUTPUT" | python3 -m json.tool >/dev/null 2>&1; then
    print_pass "JSON output is valid"
else
    print_fail "JSON output is invalid"
fi

# Table output (default)
OUTPUT=$(${CLI} --token "$TOKEN" list teams 2>&1)
check_contains "$OUTPUT" "│" "Table output format works"

# Test 6: Error handling
print_subheader "Error Handling"

# Network error simulation (invalid API URL)
OUTPUT=$(${CLI} --token "$TOKEN" --api-url "http://invalid.local" list teams 2>&1 || true)
check_contains "$OUTPUT" "Failed" "Network error handled gracefully"

# Print summary
print_summary