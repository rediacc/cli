#!/bin/bash

# Rediacc CLI Integration Test Framework
# Tests the built CLI binary by sending parameters and validating outputs

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Test configuration
CLI_BINARY="${CLI_BINARY:-./bin/rediacc}"
TEST_CONFIG_FILE="/tmp/rediacc-cli-test.yaml"
TEST_EMAIL="test@example.com"
TEST_PASSWORD="password123"
MIDDLEWARE_URL="${MIDDLEWARE_URL:-http://localhost:8080}"

# Test counters
TESTS_RUN=0
TESTS_PASSED=0
TESTS_FAILED=0

# Utility functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[PASS]${NC} $1"
}

log_error() {
    echo -e "${RED}[FAIL]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

# Test framework functions
test_start() {
    local test_name="$1"
    TESTS_RUN=$((TESTS_RUN + 1))
    log_info "Running test: $test_name"
}

test_pass() {
    local test_name="$1"
    TESTS_PASSED=$((TESTS_PASSED + 1))
    log_success "$test_name"
}

test_fail() {
    local test_name="$1"
    local reason="$2"
    TESTS_FAILED=$((TESTS_FAILED + 1))
    log_error "$test_name - $reason"
}

# CLI execution wrapper
run_cli() {
    local expected_exit_code="${1:-0}"
    shift
    local output_file="/tmp/cli_output_$$"
    local error_file="/tmp/cli_error_$$"
    
    # Run CLI command and capture exit code
    set +e
    $CLI_BINARY --config "$TEST_CONFIG_FILE" "$@" > "$output_file" 2> "$error_file"
    local actual_exit_code=$?
    set -e
    
    # Store outputs in global variables
    CLI_OUTPUT=$(cat "$output_file")
    CLI_ERROR=$(cat "$error_file")
    CLI_EXIT_CODE=$actual_exit_code
    
    # Clean up temp files
    rm -f "$output_file" "$error_file"
    
    # Check exit code if specified
    if [ "$expected_exit_code" != "any" ] && [ "$actual_exit_code" != "$expected_exit_code" ]; then
        return 1
    fi
    
    return 0
}

# Assertion functions
assert_exit_code() {
    local expected="$1"
    local test_name="$2"
    
    if [ "$CLI_EXIT_CODE" -eq "$expected" ]; then
        test_pass "$test_name - exit code $expected"
    else
        test_fail "$test_name" "Expected exit code $expected, got $CLI_EXIT_CODE"
        return 1
    fi
}

assert_output_contains() {
    local expected="$1"
    local test_name="$2"
    
    if echo "$CLI_OUTPUT" | grep -q "$expected"; then
        test_pass "$test_name - output contains '$expected'"
    else
        test_fail "$test_name" "Output does not contain '$expected'. Got: $CLI_OUTPUT"
        return 1
    fi
}

assert_output_not_contains() {
    local unexpected="$1"
    local test_name="$2"
    
    if ! echo "$CLI_OUTPUT" | grep -q "$unexpected"; then
        test_pass "$test_name - output does not contain '$unexpected'"
    else
        test_fail "$test_name" "Output unexpectedly contains '$unexpected'. Got: $CLI_OUTPUT"
        return 1
    fi
}

assert_error_contains() {
    local expected="$1"
    local test_name="$2"
    
    if echo "$CLI_ERROR" | grep -q "$expected"; then
        test_pass "$test_name - error contains '$expected'"
    else
        test_fail "$test_name" "Error does not contain '$expected'. Got: $CLI_ERROR"
        return 1
    fi
}

# Test setup and cleanup
setup_test_environment() {
    log_info "Setting up test environment..."
    
    # Ensure CLI binary exists
    if [ ! -f "$CLI_BINARY" ]; then
        log_error "CLI binary not found at $CLI_BINARY"
        log_info "Please build the CLI first: go build -o bin/rediacc main.go"
        exit 1
    fi
    
    # Create clean test config
    cat > "$TEST_CONFIG_FILE" << EOF
server:
  url: $MIDDLEWARE_URL
  timeout: 30s
auth:
  email: ""
  session_token: ""
  request_credential: ""
format:
  default: table
  colors: false
  timestamps: false
jobs:
  default_datastore_size: "100G"
  ssh_timeout: "30s"
  ssh_key_path: "~/.ssh/id_rsa"
  machines: []
ssh:
  timeout: "30s"
  retry_attempts: 3
  retry_delay: "5s"
EOF
    
    log_info "Test config created at $TEST_CONFIG_FILE"
}

cleanup_test_environment() {
    log_info "Cleaning up test environment..."
    rm -f "$TEST_CONFIG_FILE"
}

# Check middleware availability
check_middleware() {
    log_info "Checking middleware availability at $MIDDLEWARE_URL..."
    
    if curl -s --max-time 5 "$MIDDLEWARE_URL/api/StoredProcedure/ActivateUserAccount" \
       -H "Content-Type: application/json" \
       -d '{"userEmail": "health@check.com"}' > /dev/null 2>&1; then
        log_success "Middleware is responding"
        return 0
    else
        log_warning "Middleware is not responding at $MIDDLEWARE_URL"
        log_info "You may need to start middleware: cd ../middleware && ./go start"
        return 1
    fi
}

# Test result summary
print_test_summary() {
    echo
    echo "=========================================="
    echo "           TEST SUMMARY"
    echo "=========================================="
    echo "Tests Run:    $TESTS_RUN"
    echo "Tests Passed: $TESTS_PASSED"
    echo "Tests Failed: $TESTS_FAILED"
    echo "=========================================="
    
    if [ "$TESTS_FAILED" -gt 0 ]; then
        echo -e "${RED}SOME TESTS FAILED${NC}"
        exit 1
    else
        echo -e "${GREEN}ALL TESTS PASSED${NC}"
        exit 0
    fi
}

# Global variables for CLI output
CLI_OUTPUT=""
CLI_ERROR=""
CLI_EXIT_CODE=0

# Export functions for use in test files
export -f test_start test_pass test_fail
export -f run_cli assert_exit_code assert_output_contains assert_output_not_contains assert_error_contains
export -f log_info log_success log_error log_warning