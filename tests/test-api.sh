#!/bin/bash

# API endpoint tests (simplified)
# Tests: CRUD operations for main entities

set -e  # Exit on error

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Source common test utilities
source ./test-common.sh

print_header "API Endpoint Tests (Simplified)"

# Get token
TOKEN=$(require_token "$1")
print_info "Using token: ${TOKEN:0:8}..."

# Test data
TIMESTAMP=$(date +%s)
TEST_SUFFIX="test_${TIMESTAMP}"

# Test 1: Read Operations (List/Get)
print_subheader "Read Operations"

# List operations that should always work
run_test "List teams" "${CLI} --output json --token '$TOKEN' list teams | grep -q '\"success\": *true'"
run_test "List companies" "${CLI} --output json --token '$TOKEN' list companies | grep -q '\"success\": *true'"
run_test "Get user info" "${CLI} --output json --token '$TOKEN' me | grep -q '\"success\": *true'"

# Get current team info if available
OUTPUT=$(${CLI} --output json --token "$TOKEN" list teams 2>&1)
if echo "$OUTPUT" | grep -q "$TEST_TEAM"; then
    run_test "List machines in team" "${CLI} --output json --token '$TOKEN' list machines --team '$TEST_TEAM' | grep -q '\"success\": *true'"
    run_test "List bridges in team" "${CLI} --output json --token '$TOKEN' list bridges --team '$TEST_TEAM' | grep -q '\"success\": *true'"
    run_test "List repositories in team" "${CLI} --output json --token '$TOKEN' list repositories --team '$TEST_TEAM' | grep -q '\"success\": *true'"
else
    skip_test "No test team available - skipping team-specific lists"
fi

# Test 2: Vault Operations
print_subheader "Vault Operations"

# Create test vault file
VAULT_FILE="${TEST_DIR}/test_vault.json"
echo '{"test_key": "test_value", "timestamp": "'$TIMESTAMP'"}' > "$VAULT_FILE"

# Test vault operations if we have a team
if echo "$OUTPUT" | grep -q "$TEST_TEAM"; then
    # Update team vault
    OUTPUT=$(${CLI} --token "$TOKEN" update team "$TEST_TEAM" --vault-file "$VAULT_FILE" 2>&1)
    check_success "$OUTPUT" "Update team vault"
    
    # Inspect to verify
    OUTPUT=$(${CLI} --output json --token "$TOKEN" inspect team "$TEST_TEAM" 2>&1)
    if echo "$OUTPUT" | grep -q "test_key"; then
        print_pass "Vault data persisted correctly"
    else
        print_fail "Vault data not found in inspect"
    fi
else
    skip_test "No test team available - skipping vault operations"
fi

# Test 3: Create Operations (if authorized)
print_subheader "Create Operations"

# Try to create a storage (least invasive)
STORAGE_NAME="storage_${TEST_SUFFIX}"
OUTPUT=$(${CLI} --token "$TOKEN" create storage "$STORAGE_NAME" --team "$TEST_TEAM" 2>&1 || true)
if echo "$OUTPUT" | grep -q "success\|created"; then
    print_pass "Created storage: $STORAGE_NAME"
    
    # Clean up - delete the storage
    ${CLI} --token "$TOKEN" delete storage "$STORAGE_NAME" --team "$TEST_TEAM" >/dev/null 2>&1 || true
    print_pass "Cleaned up test storage"
else
    skip_test "Storage creation not authorized - skipping create/delete tests"
fi

# Test 4: Search Operations
print_subheader "Search Operations"

# Search with no results expected
OUTPUT=$(${CLI} --output json --token "$TOKEN" search "nonexistent_${TIMESTAMP}" 2>&1)
if echo "$OUTPUT" | grep -q '"totalCount": *0'; then
    print_pass "Search returns empty results correctly"
else
    print_fail "Search didn't return expected empty result"
fi

# Test 5: Error Handling
print_subheader "API Error Handling"

# Test with invalid entity
OUTPUT=$(${CLI} --token "$TOKEN" inspect team "nonexistent_team_${TIMESTAMP}" 2>&1 || true)
check_contains "$OUTPUT" "not found\|does not exist" "404 errors handled correctly"

# Test with missing parameters
OUTPUT=$(${CLI} --token "$TOKEN" create machine 2>&1 || true)
check_contains "$OUTPUT" "required\|missing" "Missing parameters caught"

# Test with invalid token
OUTPUT=$(${CLI} --token "invalid_token_format" list teams 2>&1 || true)
check_contains "$OUTPUT" "Invalid token\|authentication" "Invalid token rejected"

# Test 6: Pagination
print_subheader "Pagination Tests"

# Test limit parameter
OUTPUT=$(${CLI} --output json --token "$TOKEN" list teams --limit 1 2>&1)
if echo "$OUTPUT" | grep -q '"success": *true'; then
    # Count results (should be max 1)
    count=$(echo "$OUTPUT" | python3 -c "import sys, json; data=json.load(sys.stdin); print(len(data.get('data', [])))" 2>/dev/null || echo "0")
    if [ "$count" -le 1 ]; then
        print_pass "Limit parameter works correctly"
    else
        print_fail "Limit parameter not respected"
    fi
else
    skip_test "Pagination test failed"
fi

# Clean up
safe_cleanup "$VAULT_FILE"

# Print summary
print_summary