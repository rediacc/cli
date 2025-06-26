#!/bin/bash

# Master test runner for Rediacc CLI
# Logs in once and runs all test scripts with the token

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
NC='\033[0m' # No Color

# Test configuration
CLI="../rediacc-cli"
ADMIN_EMAIL="${SYSTEM_ADMIN_EMAIL:-admin@rediacc.io}"
ADMIN_PASSWORD="${SYSTEM_ADMIN_PASSWORD:-admin}"

# Track test results
declare -a PASSED_TESTS=()
declare -a FAILED_TESTS=()
declare -a SKIPPED_TESTS=()

# Helper functions
print_header() {
    echo ""
    echo -e "${PURPLE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${PURPLE}$1${NC}"
    echo -e "${PURPLE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
}

print_test_start() {
    echo ""
    echo -e "${YELLOW}▶ Running: $1${NC}"
    echo -e "${BLUE}────────────────────────────────────────${NC}"
}

print_test_result() {
    local test_name=$1
    local exit_code=$2
    
    if [ $exit_code -eq 0 ]; then
        echo -e "${GREEN}✓ PASSED: $test_name${NC}"
        PASSED_TESTS+=("$test_name")
    else
        echo -e "${RED}✗ FAILED: $test_name (exit code: $exit_code)${NC}"
        FAILED_TESTS+=("$test_name")
    fi
}

print_summary() {
    echo ""
    print_header "TEST SUMMARY"
    
    local total=$((${#PASSED_TESTS[@]} + ${#FAILED_TESTS[@]} + ${#SKIPPED_TESTS[@]}))
    
    echo -e "${GREEN}Passed:  ${#PASSED_TESTS[@]}/$total${NC}"
    if [ ${#PASSED_TESTS[@]} -gt 0 ]; then
        for test in "${PASSED_TESTS[@]}"; do
            echo -e "  ${GREEN}✓${NC} $test"
        done
    fi
    
    if [ ${#FAILED_TESTS[@]} -gt 0 ]; then
        echo ""
        echo -e "${RED}Failed:  ${#FAILED_TESTS[@]}/$total${NC}"
        for test in "${FAILED_TESTS[@]}"; do
            echo -e "  ${RED}✗${NC} $test"
        done
    fi
    
    if [ ${#SKIPPED_TESTS[@]} -gt 0 ]; then
        echo ""
        echo -e "${YELLOW}Skipped: ${#SKIPPED_TESTS[@]}/$total${NC}"
        for test in "${SKIPPED_TESTS[@]}"; do
            echo -e "  ${YELLOW}⊘${NC} $test"
        done
    fi
    
    echo ""
    if [ ${#FAILED_TESTS[@]} -eq 0 ]; then
        echo -e "${GREEN}━━━ All tests passed! ━━━${NC}"
        return 0
    else
        echo -e "${RED}━━━ Some tests failed ━━━${NC}"
        return 1
    fi
}

run_test() {
    local test_script=$1
    local test_name=${test_script%.sh}
    
    print_test_start "$test_name"
    
    # Run test and capture output
    set +e  # Don't exit on test failure
    if [ -f "$test_script" ]; then
        # Export token for tests that need it
        export REDIACC_TOKEN="$TOKEN"
        
        # Run test with timeout
        timeout 300 "./$test_script" "$TOKEN"
        local exit_code=$?
        
        if [ $exit_code -eq 124 ]; then
            echo -e "${RED}Test timed out after 5 minutes${NC}"
            FAILED_TESTS+=("$test_name (timeout)")
        else
            print_test_result "$test_name" $exit_code
        fi
    else
        echo -e "${YELLOW}Test script not found: $test_script${NC}"
        SKIPPED_TESTS+=("$test_name")
    fi
    set -e
}

# Main execution
print_header "REDIACC CLI TEST SUITE"
echo "Starting comprehensive test suite..."
echo ""

# Load environment variables
if [ -f "../.env" ]; then
    source ../.env
    echo -e "${BLUE}ℹ Environment loaded from .env${NC}"
fi

# Step 1: Login and get token
echo -e "${YELLOW}▶ Authenticating...${NC}"
${CLI} logout >/dev/null 2>&1 || true

LOGIN_OUTPUT=$(${CLI} --output json login --email "$ADMIN_EMAIL" --password "$ADMIN_PASSWORD" 2>&1)
if echo "$LOGIN_OUTPUT" | grep -q '"success": *true'; then
    TOKEN=$(python3 -c "import json; print(json.load(open('$HOME/.rediacc/config.json'))['token'])" 2>/dev/null)
    if [ -n "$TOKEN" ]; then
        echo -e "${GREEN}✓ Login successful${NC}"
        echo -e "${BLUE}  Token: ${TOKEN:0:8}...${NC}"
    else
        echo -e "${RED}✗ Failed to extract token${NC}"
        exit 1
    fi
else
    echo -e "${RED}✗ Login failed${NC}"
    echo "$LOGIN_OUTPUT"
    exit 1
fi

# Step 2: Run all tests
print_header "RUNNING TEST SUITE"

# Define test order (quick tests first, comprehensive tests last)
TEST_SCRIPTS=(
    # Core tests first
    "verify-setup.sh"
    "test-integration.sh"
    "test-token-management.sh"
    
    # API tests before infrastructure tests (note: test-full-api.sh logs out at end)
    "test-full-api.sh"
    
    # Infrastructure-dependent tests
    "test-simple.sh"
    "test-quick.sh"
    "test-dev-mode.sh"
    "test-sync.sh"
    "test-term.sh"
    
    # Alternative simpler tests
    # "test-term-simple.sh"  # Simplified version of test-term.sh
)

# Optional: Add test-term-demo.sh if you want to include it
# TEST_SCRIPTS+=("test-term-demo.sh")

# Run each test
for test_script in "${TEST_SCRIPTS[@]}"; do
    run_test "$test_script"
done

# Step 3: Show summary
print_summary
exit_code=$?

# Cleanup
unset REDIACC_TOKEN

exit $exit_code