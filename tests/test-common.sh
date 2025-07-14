#!/bin/bash

# Common test utilities and helper functions
# Source this file in all test scripts: source ./test-common.sh

# Colors for output
export GREEN='\033[0;32m'
export RED='\033[0;31m'
export YELLOW='\033[1;33m'
export BLUE='\033[0;34m'
export NC='\033[0m'

# Test configuration
export TEST_TEAM="${TEST_TEAM:-Default}"
export TEST_MACHINE="${TEST_MACHINE:-test-machine}"
export TEST_REPO="${TEST_REPO:-test-repo}"
export TEST_TIMEOUT="${TEST_TIMEOUT:-30}"

# Tool paths
export CLI="${CLI:-../src/cli/rediacc-cli}"
export SYNC="${SYNC:-../src/cli/rediacc-cli-sync}"
export TERM_CLI="${TERM_CLI:-../src/cli/rediacc-cli-term}"

# Test counters
export TESTS_RUN=0
export TESTS_PASSED=0
export TESTS_FAILED=0

# Load environment if available
if [ -f "../.env" ]; then
    source ../.env
fi

# Print colored status
print_pass() {
    echo -e "${GREEN}✓${NC} $1"
    ((TESTS_PASSED++))
}

print_fail() {
    echo -e "${RED}✗${NC} $1"
    ((TESTS_FAILED++))
}

print_info() {
    echo -e "${BLUE}ℹ${NC} $1"
}

print_warn() {
    echo -e "${YELLOW}⚠${NC} $1"
}

print_error() {
    echo -e "${RED}✗${NC} $1"
}

print_header() {
    echo ""
    echo -e "${YELLOW}=== $1 ===${NC}"
    echo ""
}

print_subheader() {
    echo ""
    echo -e "${BLUE}--- $1 ---${NC}"
}

# Test execution wrapper
run_test() {
    local test_name="$1"
    local test_command="$2"
    
    ((TESTS_RUN++))
    
    if eval "$test_command"; then
        print_pass "$test_name"
        return 0
    else
        print_fail "$test_name"
        return 1
    fi
}

# Check if command succeeded
check_success() {
    local output="$1"
    local description="$2"
    
    if echo "$output" | grep -q '"success": *true'; then
        print_pass "$description"
        return 0
    else
        print_fail "$description"
        echo "Output: $output" >&2
        return 1
    fi
}

# Check if output contains expected text
check_contains() {
    local output="$1"
    local expected="$2"
    local description="$3"
    
    if echo "$output" | grep -q "$expected"; then
        print_pass "$description"
        return 0
    else
        print_fail "$description - expected '$expected'"
        echo "Output: $output" >&2
        return 1
    fi
}

# Check if output does NOT contain text
check_not_contains() {
    local output="$1"
    local forbidden="$2"
    local description="$3"
    
    if echo "$output" | grep -q "$forbidden"; then
        print_fail "$description - found forbidden '$forbidden'"
        echo "Output: $output" >&2
        return 1
    else
        print_pass "$description"
        return 0
    fi
}

# Get token from various sources
get_token() {
    # Priority: parameter > env var > config file
    local token="${1:-$REDIACC_TOKEN}"
    
    # Get CLI directory relative to test directory
    local cli_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/../" && pwd)"
    local config_file="${cli_dir}/.config/config.json"
    
    if [ -z "$token" ] && [ -f "$config_file" ]; then
        token=$(python3 -c "
import json
try:
    with open('$config_file', 'r') as f:
        config = json.load(f)
        if 'token' in config and config['token']:
            print(config['token'])
except:
    pass
" config_file="$config_file" 2>/dev/null || echo "")
    fi
    
    echo "$token"
}

# Validate token exists
require_token() {
    local token=$(get_token "$1")
    
    if [ -z "$token" ]; then
        echo -e "${RED}ERROR: No token available${NC}"
        echo "Provide token as parameter, set REDIACC_TOKEN, or run 'rediacc login'"
        exit 1
    fi
    
    echo "$token"
}

# Clean up test artifacts
cleanup_test_data() {
    local prefix="${1:-test}"
    
    print_info "Cleaning up test data with prefix: $prefix"
    
    # Clean test directories
    rm -rf /tmp/${prefix}_* 2>/dev/null || true
    rm -rf /tmp/rediacc_test_* 2>/dev/null || true
}

# Print test summary
print_summary() {
    echo ""
    echo -e "${YELLOW}=== Test Summary ===${NC}"
    echo "Tests run:    $TESTS_RUN"
    echo -e "Tests passed: ${GREEN}$TESTS_PASSED${NC}"
    echo -e "Tests failed: ${RED}$TESTS_FAILED${NC}"
    
    if [ $TESTS_FAILED -eq 0 ]; then
        echo ""
        echo -e "${GREEN}All tests passed!${NC}"
        return 0
    else
        echo ""
        echo -e "${RED}Some tests failed!${NC}"
        return 1
    fi
}

# Skip test with reason
skip_test() {
    local reason="$1"
    print_warn "SKIPPED: $reason"
}

# Create temporary test directory
create_test_dir() {
    local prefix="${1:-test}"
    local dir="/tmp/${prefix}_$$_$(date +%s)"
    mkdir -p "$dir"
    echo "$dir"
}

# Safe cleanup with confirmation
safe_cleanup() {
    local path="$1"
    
    # Only clean paths in /tmp
    if [[ "$path" == /tmp/* ]]; then
        rm -rf "$path"
    else
        print_warn "Refusing to clean non-tmp path: $path"
    fi
}

# Export common functions for use in sourcing scripts
export -f print_pass print_fail print_info print_warn print_error
export -f print_header print_subheader
export -f run_test check_success check_contains check_not_contains
export -f get_token require_token
export -f cleanup_test_data print_summary skip_test
export -f create_test_dir safe_cleanup