#!/bin/bash
# Run workflow tests for Rediacc CLI

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Get script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
TESTS_DIR="$(dirname "$SCRIPT_DIR")"
CLI_DIR="$(dirname "$TESTS_DIR")"

echo -e "${BLUE}=== Rediacc Workflow Test Suite ===${NC}"
echo "Test Time: $(date '+%Y-%m-%d %H:%M:%S')"
echo

# Check if user is logged in
if ! "$CLI_DIR/rediacc" cli list teams --output json >/dev/null 2>&1; then
    echo -e "${RED}Error: Not authenticated. Please login first.${NC}"
    echo -e "${YELLOW}Run: ./rediacc login${NC}"
    exit 1
fi

# Function to run a test and report results
run_test() {
    local test_name="$1"
    local test_file="$2"
    
    echo -e "${BLUE}Running: $test_name${NC}"
    
    if [ -f "$test_file" ]; then
        if python3 "$test_file"; then
            echo -e "${GREEN}✓ $test_name passed${NC}"
            return 0
        else
            echo -e "${RED}✗ $test_name failed${NC}"
            return 1
        fi
    else
        echo -e "${YELLOW}⚠ $test_name not found: $test_file${NC}"
        return 1
    fi
}

# Track test results
TESTS_PASSED=0
TESTS_FAILED=0

# Run Python-based workflow test
echo -e "${BLUE}=== Python-based Workflow Tests ===${NC}"
if run_test "Workflow Hello Test" "$SCRIPT_DIR/test_workflow_hello.py"; then
    ((TESTS_PASSED++))
else
    ((TESTS_FAILED++))
fi
echo

# Run YAML-based workflow test
echo -e "${BLUE}=== YAML-based Workflow Tests ===${NC}"
if [ -f "$TESTS_DIR/run_tests.py" ]; then
    if python3 "$TESTS_DIR/run_tests.py" "$TESTS_DIR/yaml/community/13000_workflow_tests.yaml"; then
        echo -e "${GREEN}✓ YAML workflow tests passed${NC}"
        ((TESTS_PASSED++))
    else
        echo -e "${RED}✗ YAML workflow tests failed${NC}"
        ((TESTS_FAILED++))
    fi
else
    echo -e "${YELLOW}⚠ YAML test runner not found${NC}"
    ((TESTS_FAILED++))
fi
echo

# Summary
echo -e "${BLUE}=== Test Summary ===${NC}"
echo "Tests Passed: $TESTS_PASSED"
echo "Tests Failed: $TESTS_FAILED"

if [ $TESTS_FAILED -eq 0 ]; then
    echo -e "${GREEN}✓ All workflow tests passed!${NC}"
    exit 0
else
    echo -e "${RED}✗ Some tests failed${NC}"
    exit 1
fi