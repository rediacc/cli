#!/bin/bash

# Master test runner for Rediacc CLI
# Runs all simplified test suites

# Temporarily disable exit on error for debugging
# set -e  # Exit on error

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Source common test utilities
source ./test-common.sh

# Load environment variables from .env file
if [ -f "../../.env" ]; then
    # Load each line separately to handle quotes properly
    while IFS='=' read -r key value; do
        # Skip comments and empty lines
        if [[ ! "$key" =~ ^[[:space:]]*# ]] && [[ -n "$key" ]]; then
            # Remove leading/trailing whitespace
            key=$(echo "$key" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')
            value=$(echo "$value" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')
            # Remove surrounding quotes from value
            value=$(echo "$value" | sed 's/^"\(.*\)"$/\1/')
            # Export the variable
            export "$key=$value"
        fi
    done < "../../.env"
fi

print_header "Rediacc CLI Test Suite"
print_info "Running simplified test suite..."

# Get token
TOKEN=$(get_token "$1")
if [ -z "$TOKEN" ]; then
    print_info "No token provided. Attempting to login..."
    
    # Get credentials from .env file
    ADMIN_EMAIL="${SYSTEM_ADMIN_EMAIL:-admin@rediacc.io}"
    ADMIN_PASSWORD="${SYSTEM_ADMIN_PASSWORD:-admin}"
    
    # Try to login
    print_info "Logging in with email: $ADMIN_EMAIL"
    # Set correct CLI path
    CLI="${CLI:-../src/cli/rediacc-cli}"
    LOGIN_OUTPUT=$($CLI login --email "$ADMIN_EMAIL" --password "$ADMIN_PASSWORD" 2>&1)
    
    if echo "$LOGIN_OUTPUT" | grep -qi "successfully logged in\|authentication successful\|logged in as"; then
        print_pass "Successfully logged in"
        
        # Try to get token again after login
        TOKEN=$(get_token)
        
        if [ -z "$TOKEN" ]; then
            print_error "Failed to retrieve token after login"
            print_info "Login output: $LOGIN_OUTPUT"
            exit 1
        fi
    else
        print_error "Failed to login with credentials from .env"
        print_info "Login output: $LOGIN_OUTPUT"
        print_info "Usage: $0 <TOKEN>"
        print_info "Or set REDIACC_TOKEN environment variable"
        exit 1
    fi
fi

# Track overall results
TOTAL_TESTS=0
TOTAL_PASSED=0
TOTAL_FAILED=0
FAILED_SUITES=()

# Function to run a test suite
run_suite() {
    local suite_name="$1"
    local test_script="$2"
    
    print_header "Running $suite_name"
    
    if [ ! -f "$test_script" ]; then
        print_warn "Test script not found: $test_script"
        return 1
    fi
    
    # Run the test and capture result
    if bash "$test_script" "$TOKEN"; then
        print_pass "$suite_name completed successfully"
        return 0
    else
        print_fail "$suite_name failed"
        FAILED_SUITES+=("$suite_name")
        return 1
    fi
}

# Run test suites
print_info "Starting test execution..."

# 1. Core functionality tests (always run)
if run_suite "Core Functionality Tests" "./test-core.sh"; then
    TOTAL_TESTS=$((TOTAL_TESTS + TESTS_RUN))
    TOTAL_PASSED=$((TOTAL_PASSED + TESTS_PASSED))
    TOTAL_FAILED=$((TOTAL_FAILED + TESTS_FAILED))
fi
TESTS_RUN=0; TESTS_PASSED=0; TESTS_FAILED=0

# 2. API endpoint tests
if [ -n "$TOKEN" ]; then
    if run_suite "API Endpoint Tests" "./test-api.sh"; then
        TOTAL_TESTS=$((TOTAL_TESTS + TESTS_RUN))
        TOTAL_PASSED=$((TOTAL_PASSED + TESTS_PASSED))
        TOTAL_FAILED=$((TOTAL_FAILED + TESTS_FAILED))
    fi
    TESTS_RUN=0; TESTS_PASSED=0; TESTS_FAILED=0
else
    skip_test "API tests - no token provided"
fi

# 3. File synchronization tests
if [ -n "$TOKEN" ]; then
    if run_suite "File Synchronization Tests" "./test-sync.sh"; then
        TOTAL_TESTS=$((TOTAL_TESTS + TESTS_RUN))
        TOTAL_PASSED=$((TOTAL_PASSED + TESTS_PASSED))
        TOTAL_FAILED=$((TOTAL_FAILED + TESTS_FAILED))
    fi
    TESTS_RUN=0; TESTS_PASSED=0; TESTS_FAILED=0
else
    skip_test "Sync tests - no token provided"
fi

# 4. Terminal access tests
if [ -n "$TOKEN" ]; then
    if run_suite "Terminal Access Tests" "./test-term.sh"; then
        TOTAL_TESTS=$((TOTAL_TESTS + TESTS_RUN))
        TOTAL_PASSED=$((TOTAL_PASSED + TESTS_PASSED))
        TOTAL_FAILED=$((TOTAL_FAILED + TESTS_FAILED))
    fi
    TESTS_RUN=0; TESTS_PASSED=0; TESTS_FAILED=0
else
    skip_test "Terminal tests - no token provided"
fi

# Final summary
echo ""
print_header "Overall Test Summary"
echo "Total tests run:    $TOTAL_TESTS"
echo -e "Total tests passed: ${GREEN}$TOTAL_PASSED${NC}"
echo -e "Total tests failed: ${RED}$TOTAL_FAILED${NC}"

if [ ${#FAILED_SUITES[@]} -gt 0 ]; then
    echo ""
    echo -e "${RED}Failed test suites:${NC}"
    for suite in "${FAILED_SUITES[@]}"; do
        echo "  - $suite"
    done
fi

echo ""
echo "Test run completed: $(date)"

# Exit with appropriate code
if [ $TOTAL_FAILED -eq 0 ]; then
    echo -e "${GREEN}All tests passed!${NC}"
    exit 0
else
    echo -e "${RED}Some tests failed!${NC}"
    exit 1
fi