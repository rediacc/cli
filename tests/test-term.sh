#!/bin/bash

# Terminal access tests
# Tests: SSH connections, command execution, repository environments

set -e  # Exit on error

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Source common test utilities
source ./test-common.sh

print_header "Terminal Access Tests"

# Get token
TOKEN=$(require_token "$1")
print_info "Using token: ${TOKEN:0:8}..."

# Test 1: Basic terminal functionality
print_subheader "Basic Terminal Tests"

# Check if we have required test infrastructure
OUTPUT=$(${CLI} --output json --token "$TOKEN" list machines --team "$TEST_TEAM" 2>&1)
if ! echo "$OUTPUT" | grep -q "$TEST_MACHINE"; then
    skip_test "Test machine '$TEST_MACHINE' not found in team '$TEST_TEAM'"
    skip_test "Skipping terminal tests - no test infrastructure"
    print_summary
    exit 0
fi

# Test single command execution
OUTPUT=$(${TERM} \
    --token "$TOKEN" \
    --machine "$TEST_MACHINE" \
    --team "$TEST_TEAM" \
    --command "echo 'Hello from terminal'" \
    2>&1)
check_contains "$OUTPUT" "Hello from terminal" "Single command execution"

# Test 2: Repository environment
print_subheader "Repository Environment Tests"

# Test command in repository context
OUTPUT=$(${TERM} \
    --token "$TOKEN" \
    --machine "$TEST_MACHINE" \
    --repo "$TEST_REPO" \
    --team "$TEST_TEAM" \
    --command "pwd" \
    2>&1)
check_contains "$OUTPUT" "/$TEST_REPO" "Repository working directory set"

# Test environment variables
OUTPUT=$(${TERM} \
    --token "$TOKEN" \
    --machine "$TEST_MACHINE" \
    --repo "$TEST_REPO" \
    --team "$TEST_TEAM" \
    --command "echo \$REPO_NAME" \
    2>&1)
check_contains "$OUTPUT" "$TEST_REPO" "Repository environment variable set"

# Test 3: Machine-only access
print_subheader "Machine-Only Access Tests"

# Test direct machine access (no repo)
OUTPUT=$(${TERM} \
    --token "$TOKEN" \
    --machine "$TEST_MACHINE" \
    --team "$TEST_TEAM" \
    --command "whoami" \
    2>&1)
check_contains "$OUTPUT" "universal" "Machine access uses universal user"

# Test 4: Docker integration
print_subheader "Docker Integration Tests"

# Check if Docker is available on the machine
OUTPUT=$(${TERM} \
    --token "$TOKEN" \
    --machine "$TEST_MACHINE" \
    --team "$TEST_TEAM" \
    --command "which docker" \
    2>&1 || true)

if echo "$OUTPUT" | grep -q "/docker"; then
    # Test Docker command
    OUTPUT=$(${TERM} \
        --token "$TOKEN" \
        --machine "$TEST_MACHINE" \
        --repo "$TEST_REPO" \
        --team "$TEST_TEAM" \
        --command "docker ps --format 'table {{.Names}}' | grep -q ${TEST_REPO} && echo 'Container found'" \
        2>&1 || true)
    if echo "$OUTPUT" | grep -q "Container found"; then
        print_pass "Docker container access verified"
    else
        print_warn "Docker available but container not found"
    fi
else
    skip_test "Docker not available on test machine"
fi

# Test 5: Error handling
print_subheader "Error Handling"

# Invalid machine
OUTPUT=$(${TERM} \
    --token "$TOKEN" \
    --machine "nonexistent-machine" \
    --team "$TEST_TEAM" \
    --command "echo test" \
    2>&1 || true)
check_contains "$OUTPUT" "not found" "Invalid machine error handled"

# Invalid repository
OUTPUT=$(${TERM} \
    --token "$TOKEN" \
    --machine "$TEST_MACHINE" \
    --repo "nonexistent-repo" \
    --team "$TEST_TEAM" \
    --command "echo test" \
    2>&1 || true)
check_contains "$OUTPUT" "Failed" "Invalid repository error handled"

# Test 6: Special characters and escaping
print_subheader "Special Character Tests"

# Test command with quotes
OUTPUT=$(${TERM} \
    --token "$TOKEN" \
    --machine "$TEST_MACHINE" \
    --team "$TEST_TEAM" \
    --command "echo 'Test with spaces and \"quotes\"'" \
    2>&1)
check_contains "$OUTPUT" "Test with spaces and \"quotes\"" "Special characters handled"

# Test command with variables
OUTPUT=$(${TERM} \
    --token "$TOKEN" \
    --machine "$TEST_MACHINE" \
    --team "$TEST_TEAM" \
    --command "VAR='test value'; echo \$VAR" \
    2>&1)
check_contains "$OUTPUT" "test value" "Shell variables work correctly"

# Test 7: Development mode
print_subheader "Development Mode Tests"

# Test with --dev flag (relaxed host checking)
OUTPUT=$(${TERM} \
    --token "$TOKEN" \
    --machine "$TEST_MACHINE" \
    --team "$TEST_TEAM" \
    --command "echo 'Dev mode test'" \
    --dev \
    2>&1)
check_contains "$OUTPUT" "Dev mode test" "Development mode works"

# Print summary
print_summary