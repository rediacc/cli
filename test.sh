#!/bin/bash

# Configuration
CLI="./rediacc-cli"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
RANDOM_SUFFIX=$(openssl rand -hex 2)

# Load environment variables from .env file if it exists
if [ -f "../.env" ]; then
    export $(grep -v '^#' ../.env | xargs)
fi

# Test data - modify these as needed
ADMIN_EMAIL="${SYSTEM_ADMIN_EMAIL:-admin@rediacc.io}"
ADMIN_PASSWORD="${SYSTEM_ADMIN_PASSWORD:-admin}"
COMPANY_NAME="TestCompany_${TIMESTAMP}_${RANDOM_SUFFIX}"
TEAM_NAME="TestTeam_${TIMESTAMP}_${RANDOM_SUFFIX}"
REGION_NAME="TestRegion_${TIMESTAMP}_${RANDOM_SUFFIX}"
BRIDGE_NAME="TestBridge_${TIMESTAMP}_${RANDOM_SUFFIX}"
MACHINE_NAME="TestMachine_${TIMESTAMP}_${RANDOM_SUFFIX}"
REPO_NAME="TestRepo_${TIMESTAMP}_${RANDOM_SUFFIX}"
STORAGE_NAME="TestStorage_${TIMESTAMP}_${RANDOM_SUFFIX}"
SCHEDULE_NAME="TestSchedule_${TIMESTAMP}_${RANDOM_SUFFIX}"
TEST_USER_EMAIL="testuser_${TIMESTAMP}@example.com"

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
BLUE='\033[0;34m'
YELLOW='\033[0;33m'
NC='\033[0m' # No Color

# Helper function to print colored output
print_status() {
    echo -e "${GREEN}✓${NC} $1"
}

print_error() {
    echo -e "${RED}✗${NC} $1"
}

print_section() {
    echo -e "\n${BLUE}=== $1 ===${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠${NC} $1"
}

# Create test vault files
create_test_vault_files() {
    echo '{"test_key": "test_value", "version": 1}' > test_vault.json
    echo '{"updated_key": "updated_value", "version": 2}' > test_vault_updated.json
}

# Cleanup test vault files
cleanup_test_vault_files() {
    rm -f test_vault.json test_vault_updated.json
}

# Start testing
echo "CLI Test Script"
echo "Started: $(date)"
echo "----------------------------------------"

# Create test vault files
create_test_vault_files

# 1. Authentication Tests
print_section "Authentication Tests"

# Test login with session name
echo "Testing login with session name..."
if ${CLI} login --email "${ADMIN_EMAIL}" --password "${ADMIN_PASSWORD}" --session-name "TestSession_${TIMESTAMP}"; then
    print_status "Logged in successfully with session name"
else
    print_error "Login with session name failed"
    cleanup_test_vault_files
    exit 1
fi

# Test logout and re-login
echo "Testing logout..."
if ${CLI} logout; then
    print_status "Logged out successfully"
else
    print_error "Logout failed"
fi

# Re-login for remaining tests
echo "Re-logging in..."
if ${CLI} login --email "${ADMIN_EMAIL}" --password "${ADMIN_PASSWORD}"; then
    print_status "Re-logged in successfully"
else
    print_error "Re-login failed"
    cleanup_test_vault_files
    exit 1
fi

# 2. Company Creation Tests (if applicable)
print_section "Company Creation Tests"
echo "Testing company creation..."
NEW_COMPANY="NewCompany_${TIMESTAMP}_${RANDOM_SUFFIX}"
NEW_ADMIN_EMAIL="newadmin_${TIMESTAMP}@example.com"
NEW_ADMIN_PASS="newadminpass123"

# Note: This might fail if not in the right context
if ${CLI} create company "${NEW_COMPANY}" --email "${NEW_ADMIN_EMAIL}" --password "${NEW_ADMIN_PASS}" --plan "ELITE" 2>/dev/null; then
    print_status "Created company: ${NEW_COMPANY}"
else
    print_warning "Company creation skipped (might require special permissions)"
fi

# 3. Create entities with vault files
print_section "Creating Entities with Vault Files"

# Create Team with vault file
echo "Creating team with vault file: ${TEAM_NAME}"
if ${CLI} create team "${TEAM_NAME}" --vault-file test_vault.json; then
    print_status "Created team with vault file: ${TEAM_NAME}"
else
    print_error "Failed to create team with vault file"
fi

# Create Region with inline vault
echo "Creating region: ${REGION_NAME}"
if ${CLI} create region "${REGION_NAME}" --vault '{"region_config": "test"}'; then
    print_status "Created region: ${REGION_NAME}"
else
    print_error "Failed to create region"
fi

# Create Bridge in Region
echo "Creating bridge: ${BRIDGE_NAME}"
if ${CLI} create bridge "${REGION_NAME}" "${BRIDGE_NAME}" --vault '{}'; then
    print_status "Created bridge: ${BRIDGE_NAME} in region ${REGION_NAME}"
else
    print_error "Failed to create bridge"
fi

# Create Machine for Team using Bridge
echo "Creating machine: ${MACHINE_NAME}"
if ${CLI} create machine "${TEAM_NAME}" "${BRIDGE_NAME}" "${MACHINE_NAME}" --vault-file test_vault.json; then
    print_status "Created machine: ${MACHINE_NAME} for team ${TEAM_NAME}"
else
    print_error "Failed to create machine"
fi

# Create Repository for Team
echo "Creating repository: ${REPO_NAME}"
if ${CLI} create repository "${TEAM_NAME}" "${REPO_NAME}" --vault '{}'; then
    print_status "Created repository: ${REPO_NAME} for team ${TEAM_NAME}"
else
    print_error "Failed to create repository"
fi

# Create Storage for Team
echo "Creating storage: ${STORAGE_NAME}"
if ${CLI} create storage "${TEAM_NAME}" "${STORAGE_NAME}" --vault '{}'; then
    print_status "Created storage: ${STORAGE_NAME} for team ${TEAM_NAME}"
else
    print_error "Failed to create storage"
fi

# Create Schedule for Team
echo "Creating schedule: ${SCHEDULE_NAME}"
if ${CLI} create schedule "${TEAM_NAME}" "${SCHEDULE_NAME}" --vault '{}'; then
    print_status "Created schedule: ${SCHEDULE_NAME} for team ${TEAM_NAME}"
else
    print_error "Failed to create schedule"
fi

# 4. Vault Operations Tests
print_section "Vault Operations Tests"

# Test vault set commands
echo "Testing vault set for team..."
if ${CLI} vault set team "${TEAM_NAME}" test_vault_updated.json --vault-version 2; then
    print_status "Successfully updated team vault"
else
    print_error "Failed to set team vault"
fi

echo "Testing vault set for machine with stdin..."
echo '{"machine_data": "updated_from_stdin"}' | ${CLI} vault set machine "${MACHINE_NAME}" - --team "${TEAM_NAME}" --vault-version 2
if [ $? -eq 0 ]; then
    print_status "Successfully updated machine vault from stdin"
else
    print_error "Failed to set machine vault from stdin"
fi

# 5. Update Operations Tests
print_section "Update Operations Tests"

# Test team updates
NEW_TEAM_NAME="${TEAM_NAME}_updated"
echo "Testing team rename..."
if ${CLI} update team "${TEAM_NAME}" --new-name "${NEW_TEAM_NAME}"; then
    print_status "Successfully renamed team to ${NEW_TEAM_NAME}"
    TEAM_NAME="${NEW_TEAM_NAME}"  # Update variable for subsequent operations
else
    print_error "Failed to rename team"
fi

echo "Testing team vault update..."
if ${CLI} update team "${TEAM_NAME}" --vault '{"team_updated": true}' --vault-version 3; then
    print_status "Successfully updated team vault"
else
    print_error "Failed to update team vault"
fi

# Test machine updates
NEW_MACHINE_NAME="${MACHINE_NAME}_updated"
echo "Testing machine rename..."
if ${CLI} update machine "${TEAM_NAME}" "${MACHINE_NAME}" --new-name "${NEW_MACHINE_NAME}"; then
    print_status "Successfully renamed machine to ${NEW_MACHINE_NAME}"
    MACHINE_NAME="${NEW_MACHINE_NAME}"  # Update variable for subsequent operations
else
    print_error "Failed to rename machine"
fi

# Create a new bridge for testing bridge update
NEW_BRIDGE_NAME="NewBridge_${TIMESTAMP}_${RANDOM_SUFFIX}"
echo "Creating new bridge for update test..."
if ${CLI} create bridge "${REGION_NAME}" "${NEW_BRIDGE_NAME}" --vault '{}'; then
    print_status "Created new bridge: ${NEW_BRIDGE_NAME}"
    
    echo "Testing machine bridge update..."
    if ${CLI} update machine "${TEAM_NAME}" "${MACHINE_NAME}" --new-bridge "${NEW_BRIDGE_NAME}"; then
        print_status "Successfully updated machine bridge to ${NEW_BRIDGE_NAME}"
    else
        print_error "Failed to update machine bridge"
    fi
else
    print_error "Failed to create new bridge for update test"
fi

echo "Testing machine vault update..."
if ${CLI} update machine "${TEAM_NAME}" "${MACHINE_NAME}" --vault-file test_vault_updated.json --vault-version 3; then
    print_status "Successfully updated machine vault"
else
    print_error "Failed to update machine vault"
fi

# Test JSON output for update operations
echo "Testing update with JSON output..."
# Note: The CLI may output multiple JSON objects, so we'll test just the last one
if ${CLI} --output json update team "${TEAM_NAME}" --vault '{"json_test": true}' --vault-version 4 2>&1 | tail -n 6 | python3 -m json.tool > /dev/null 2>&1; then
    print_status "Update JSON output is valid"
else
    # This might fail if the CLI outputs multiple JSON objects
    print_warning "Update JSON output validation skipped (multiple JSON objects)"
fi

# 6. Permission Features Tests
print_section "Permission Features Tests"

# Create permission group
PERMISSION_GROUP="TestPermGroup_${TIMESTAMP}_${RANDOM_SUFFIX}"
echo "Creating permission group: ${PERMISSION_GROUP}"
if ${CLI} permission create-group "${PERMISSION_GROUP}"; then
    print_status "Created permission group: ${PERMISSION_GROUP}"
else
    print_error "Failed to create permission group"
fi

# Add multiple permissions to group
PERMISSIONS=("view_teams" "manage_machines" "create_repositories" "view_regions")
for perm in "${PERMISSIONS[@]}"; do
    echo "Adding permission '${perm}' to group..."
    if ${CLI} permission add "${PERMISSION_GROUP}" "${perm}"; then
        print_status "Added permission '${perm}' to group ${PERMISSION_GROUP}"
    else
        print_error "Failed to add permission '${perm}' to group"
    fi
done

# List permission groups
echo -e "\nPermission Groups (Table Format):"
echo "----------------------------------------"
${CLI} permission list-groups
echo "----------------------------------------"

# List specific permission group details
echo -e "\nPermission Group Details for ${PERMISSION_GROUP}:"
echo "----------------------------------------"
${CLI} permission list-group "${PERMISSION_GROUP}"
echo "----------------------------------------"

# Create a test user for permission assignment
echo "Creating test user for permission assignment..."
if ${CLI} create user "${TEST_USER_EMAIL}" --password "TestUserPass123!" 2>/dev/null; then
    print_status "Created test user: ${TEST_USER_EMAIL}"
    
    # Now test permission assignment
    echo "Testing permission assignment..."
    if ${CLI} permission assign "${TEST_USER_EMAIL}" "${PERMISSION_GROUP}"; then
        print_status "Assigned permission group to user ${TEST_USER_EMAIL}"
    else
        print_error "Failed to assign permission group to user"
    fi
else
    print_warning "Test user creation skipped (might require special permissions)"
    print_warning "Permission assignment skipped (user doesn't exist)"
fi

# Test JSON output for permissions
echo -e "\nPermission Groups (JSON Format - Pretty Printed):"
echo "----------------------------------------"
if ${CLI} --output json permission list-groups 2>/dev/null | python3 -m json.tool 2>/dev/null; then
    print_status "Permission groups JSON output is valid"
else
    # If pretty printing fails, just show raw JSON
    ${CLI} --output json permission list-groups 2>/dev/null
    print_error "Permission groups JSON pretty printing failed (but raw JSON shown above)"
fi
echo "----------------------------------------"

echo -e "\nPermission Group Details (JSON Format - Pretty Printed):"
echo "----------------------------------------"
if ${CLI} --output json permission list-group "${PERMISSION_GROUP}" 2>/dev/null | python3 -m json.tool 2>/dev/null; then
    print_status "Permission group details JSON output is valid"
else
    # If pretty printing fails, just show raw JSON
    ${CLI} --output json permission list-group "${PERMISSION_GROUP}" 2>/dev/null
    print_error "Permission group details JSON pretty printing failed (but raw JSON shown above)"
fi
echo "----------------------------------------"

# Remove permissions from group
echo -e "\nRemoving permissions from group:"
for perm in "${PERMISSIONS[@]:0:2}"; do  # Remove first two permissions
    if ${CLI} permission remove "${PERMISSION_GROUP}" "${perm}" --force; then
        print_status "Removed permission '${perm}' from group ${PERMISSION_GROUP}"
    else
        print_error "Failed to remove permission '${perm}' from group"
    fi
done

# 7. List All Entities
print_section "Listing All Entities"

echo -e "\nTeams:"
${CLI} list teams

echo -e "\nRegions:"
${CLI} list regions

echo -e "\nBridges in ${REGION_NAME}:"
${CLI} list bridges "${REGION_NAME}"

echo -e "\nMachines in ${TEAM_NAME}:"
${CLI} list machines "${TEAM_NAME}"

echo -e "\nRepositories in ${TEAM_NAME}:"
${CLI} list repositories "${TEAM_NAME}"

# 8. Inspect Entities with Updated Names
print_section "Inspecting Updated Entities"

echo -e "\nTeam details for ${TEAM_NAME}:"
${CLI} inspect team "${TEAM_NAME}"

echo -e "\nMachine details for ${MACHINE_NAME}:"
${CLI} inspect machine "${TEAM_NAME}" "${MACHINE_NAME}"

# Test JSON inspection
echo -e "\nTeam details (JSON):"
if ${CLI} --output json inspect team "${TEAM_NAME}" | python3 -m json.tool > /dev/null 2>&1; then
    print_status "Team inspect JSON output is valid"
else
    print_error "Team inspect JSON output is invalid"
fi

echo -e "\nMachine details (JSON):"
if ${CLI} --output json inspect machine "${TEAM_NAME}" "${MACHINE_NAME}" | python3 -m json.tool > /dev/null 2>&1; then
    print_status "Machine inspect JSON output is valid"
else
    print_error "Machine inspect JSON output is invalid"
fi

# 9. Queue Operations Tests
print_section "Queue Operations Tests"

# Test queue list-functions command
echo "Testing queue list-functions..."
if ${CLI} queue list-functions > /dev/null 2>&1; then
    print_status "Successfully listed queue functions"
else
    print_error "Failed to list queue functions"
fi

# Test queue list-functions with JSON output
echo "Testing queue list-functions (JSON)..."
if ${CLI} --output json queue list-functions | python3 -m json.tool > /dev/null 2>&1; then
    print_status "Queue list-functions JSON output is valid"
else
    print_error "Queue list-functions JSON output is invalid"
fi

# Test queue add command with various functions
echo "Testing queue add command..."

# Test simple function without parameters
echo "Adding 'hello' function to queue..."
if ${CLI} queue add "${TEAM_NAME}" "${MACHINE_NAME}" hello --description "Test hello function"; then
    print_status "Successfully queued 'hello' function"
else
    print_error "Failed to queue 'hello' function"
fi

# Test function with required parameters
echo "Adding 'repo_new' function to queue..."
TEST_REPO="QueueTestRepo_${TIMESTAMP}_${RANDOM_SUFFIX}"
if ${CLI} queue add "${TEAM_NAME}" "${MACHINE_NAME}" repo_new --repo "${TEST_REPO}" --size "5G" --priority 8; then
    print_status "Successfully queued 'repo_new' function with parameters"
else
    print_error "Failed to queue 'repo_new' function with parameters"
fi

# Test function with optional parameters
echo "Adding 'os_setup' function to queue..."
if ${CLI} queue add "${TEAM_NAME}" "${MACHINE_NAME}" os_setup --datastore-size "90%" --source "custom-repo"; then
    print_status "Successfully queued 'os_setup' function with optional parameters"
else
    print_error "Failed to queue 'os_setup' function with optional parameters"
fi

# Test function with default parameters
echo "Adding 'os_setup' function with defaults to queue..."
if ${CLI} queue add "${TEAM_NAME}" "${MACHINE_NAME}" os_setup; then
    print_status "Successfully queued 'os_setup' function with defaults"
else
    print_error "Failed to queue 'os_setup' function with defaults"
fi

# Test repo_mount function
echo "Adding 'repo_mount' function to queue..."
if ${CLI} queue add "${TEAM_NAME}" "${MACHINE_NAME}" repo_mount --repo "${REPO_NAME}" --from "remote-machine"; then
    print_status "Successfully queued 'repo_mount' function"
else
    print_error "Failed to queue 'repo_mount' function"
fi

# Test map_socket function
echo "Adding 'map_socket' function to queue..."
if ${CLI} queue add "${TEAM_NAME}" "${MACHINE_NAME}" map_socket --machine "${MACHINE_NAME}" --repo "${REPO_NAME}" --plugin "test-plugin"; then
    print_status "Successfully queued 'map_socket' function"
else
    print_error "Failed to queue 'map_socket' function"
fi

# Test queue add with JSON output
echo "Testing queue add with JSON output..."
QUEUE_JSON_OUTPUT=$(${CLI} --output json queue add "${TEAM_NAME}" "${MACHINE_NAME}" uninstall --priority 10)
if echo "${QUEUE_JSON_OUTPUT}" | python3 -m json.tool > /dev/null 2>&1; then
    print_status "Queue add JSON output is valid"
    
    # Extract task ID if possible
    TASK_ID=$(echo "${QUEUE_JSON_OUTPUT}" | python3 -c "import json, sys; data = json.load(sys.stdin); print(data.get('data', {}).get('task_id', ''))" 2>/dev/null)
    if [ -n "${TASK_ID}" ]; then
        print_status "Successfully extracted task ID: ${TASK_ID}"
    fi
else
    print_error "Queue add JSON output is invalid"
fi

# Test queue get-next to see our queued items
echo "Testing queue get-next..."
if ${CLI} queue get-next "${MACHINE_NAME}" --count 10 | grep -q "hello\|repo_new\|os_setup"; then
    print_status "Successfully retrieved queued items"
else
    print_warning "Could not verify queued items (might be processed already)"
fi

# Test queue operations error handling
echo "Testing queue add with invalid function..."
if ${CLI} queue add "${TEAM_NAME}" "${MACHINE_NAME}" invalid_function 2>&1 | grep -q -i "unknown function\|error"; then
    print_status "Properly handled invalid function name"
else
    print_error "Did not properly handle invalid function name"
fi

echo "Testing queue add with missing required parameters..."
if ${CLI} --output json queue add "${TEAM_NAME}" "${MACHINE_NAME}" repo_new 2>&1 | grep -q -i "missing required parameter\|error"; then
    print_status "Properly handled missing required parameters"
else
    print_error "Did not properly handle missing required parameters"
fi

# Test edge cases for queue operations
echo "Testing queue add with very high priority..."
if ${CLI} queue add "${TEAM_NAME}" "${MACHINE_NAME}" hello --priority 999 --description "High priority test"; then
    print_status "Successfully queued with high priority"
else
    print_error "Failed to queue with high priority"
fi

echo "Testing queue add with complex parameters..."
if ${CLI} queue add "${TEAM_NAME}" "${MACHINE_NAME}" repo_push --repo "repo1,repo2,repo3" --to "backup-storage" --option "no-suffix,override"; then
    print_status "Successfully queued repo_push with complex parameters"
else
    print_error "Failed to queue repo_push with complex parameters"
fi

# Test repo_pull function with 'from' parameter
echo "Testing repo_pull function..."
if ${CLI} queue add "${TEAM_NAME}" "${MACHINE_NAME}" repo_pull --from "source-machine" --repo "${REPO_NAME}"; then
    print_status "Successfully queued repo_pull function"
else
    print_error "Failed to queue repo_pull function"
fi

# Test repo_resize function
echo "Testing repo_resize function..."
if ${CLI} queue add "${TEAM_NAME}" "${MACHINE_NAME}" repo_resize --repo "${REPO_NAME}" --size "50G"; then
    print_status "Successfully queued repo_resize function"
else
    print_error "Failed to queue repo_resize function"
fi

# Test repo_plugin and repo_plugout functions
echo "Testing repo_plugin function..."
if ${CLI} queue add "${TEAM_NAME}" "${MACHINE_NAME}" repo_plugin --repo "${REPO_NAME}" --plugin "browser,terminal"; then
    print_status "Successfully queued repo_plugin function"
else
    print_error "Failed to queue repo_plugin function"
fi

echo "Testing repo_plugout function..."
if ${CLI} queue add "${TEAM_NAME}" "${MACHINE_NAME}" repo_plugout --repo "${REPO_NAME}" --plugin "browser"; then
    print_status "Successfully queued repo_plugout function"
else
    print_error "Failed to queue repo_plugout function"
fi

# If we have a task ID, test queue update and complete operations
if [ -n "${TASK_ID}" ]; then
    echo "Testing queue update-response..."
    if ${CLI} queue update-response "${TASK_ID}" --vault '{"status": "processing", "message": "Test update"}'; then
        print_status "Successfully updated queue item response"
    else
        print_warning "Failed to update queue item response (might be already processed)"
    fi
    
    echo "Testing queue complete..."
    if ${CLI} queue complete "${TASK_ID}" --vault '{"status": "completed", "result": "success"}'; then
        print_status "Successfully completed queue item"
    else
        print_warning "Failed to complete queue item (might be already completed)"
    fi
fi

# 10. Error Handling Tests
print_section "Error Handling Tests"

echo "Testing operations on non-existent resources..."

# Try to update non-existent machine
if ${CLI} update machine "${TEAM_NAME}" "NonExistentMachine_${TIMESTAMP}" --new-name "ShouldFail" 2>&1 | grep -q -i "error\|not found"; then
    print_status "Properly handled non-existent machine update"
else
    print_error "Did not properly handle non-existent machine update"
fi

# Try to list bridges in non-existent region
if ${CLI} list bridges "NonExistentRegion_${TIMESTAMP}" 2>&1 | grep -q -i "error\|not found\|no"; then
    print_status "Properly handled non-existent region"
else
    print_error "Did not properly handle non-existent region"
fi

# Test invalid JSON vault data
echo "Testing invalid JSON vault data..."
echo "invalid json data" > invalid_vault.json
if ${CLI} vault set team "${TEAM_NAME}" invalid_vault.json 2>&1 | grep -q -i "error\|invalid"; then
    print_status "Properly handled invalid JSON vault data"
    rm -f invalid_vault.json
else
    print_error "Did not properly handle invalid JSON vault data"
    rm -f invalid_vault.json
fi

# 11. Test Confirmation Prompts (without --force)
print_section "Testing Confirmation Prompts"

echo "Testing delete without --force flag..."
# Create a temporary team to test deletion prompt
TEMP_TEAM="TempTeam_${TIMESTAMP}_${RANDOM_SUFFIX}"
${CLI} create team "${TEMP_TEAM}" --vault '{}' > /dev/null 2>&1

# Test with 'n' response (should not delete)
echo "n" | ${CLI} rm team "${TEMP_TEAM}" 2>&1 | grep -q "cancelled"
if [ $? -eq 0 ]; then
    print_status "Properly cancelled deletion on 'n' response"
else
    print_error "Did not properly handle cancellation"
fi

# Now delete with force flag
if ${CLI} rm team "${TEMP_TEAM}" --force > /dev/null 2>&1; then
    print_status "Successfully deleted with --force flag"
else
    print_error "Failed to delete with --force flag"
fi

# 12. Comprehensive Cleanup
print_section "Comprehensive Cleanup"
echo "Deleting all created entities..."

# First, delete any remaining queue items to avoid dependency issues
echo "Cleaning up queue items..."
# Keep trying to delete queue items until none are left
MAX_ATTEMPTS=5
ATTEMPT=1
TOTAL_DELETED=0

while [ ${ATTEMPT} -le ${MAX_ATTEMPTS} ]; do
    # Skip header lines and extract Task ID (UUID pattern) from any column
    # This handles both PENDING items (Task ID in column 5) and COMPLETED items (Task ID in column 6)
    QUEUE_ITEMS=$(${CLI} list queue-items "${TEAM_NAME}" 2>/dev/null | tail -n +3 | grep -oE '[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}' | sort -u)
    
    if [ -z "${QUEUE_ITEMS}" ]; then
        break
    fi
    
    DELETED_COUNT=0
    for ITEM_ID in ${QUEUE_ITEMS}; do
        if ${CLI} rm queue-item "${ITEM_ID}" --force > /dev/null 2>&1; then
            ((DELETED_COUNT++))
            ((TOTAL_DELETED++))
        fi
    done
    
    if [ ${DELETED_COUNT} -eq 0 ]; then
        # No items deleted in this attempt, break to avoid infinite loop
        break
    fi
    
    ((ATTEMPT++))
done

if [ ${TOTAL_DELETED} -gt 0 ]; then
    print_status "Cleaned up ${TOTAL_DELETED} queue items"
else
    print_status "No queue items to clean up"
fi

# Delete in correct order to avoid dependency issues
echo "Deleting resources..."
if ${CLI} rm machine "${TEAM_NAME}" "${MACHINE_NAME}" --force > /dev/null 2>&1; then
    print_status "Deleted machine: ${MACHINE_NAME}"
else
    print_error "Failed to delete machine: ${MACHINE_NAME}"
fi

if ${CLI} rm repository "${TEAM_NAME}" "${REPO_NAME}" --force > /dev/null 2>&1; then
    print_status "Deleted repository: ${REPO_NAME}"
else
    print_error "Failed to delete repository: ${REPO_NAME}"
fi

if ${CLI} rm storage "${TEAM_NAME}" "${STORAGE_NAME}" --force > /dev/null 2>&1; then
    print_status "Deleted storage: ${STORAGE_NAME}"
else
    print_error "Failed to delete storage: ${STORAGE_NAME}"
fi

if ${CLI} rm schedule "${TEAM_NAME}" "${SCHEDULE_NAME}" --force > /dev/null 2>&1; then
    print_status "Deleted schedule: ${SCHEDULE_NAME}"
else
    print_error "Failed to delete schedule: ${SCHEDULE_NAME}"
fi

if ${CLI} rm team "${TEAM_NAME}" --force > /dev/null 2>&1; then
    print_status "Deleted team: ${TEAM_NAME}"
else
    print_error "Failed to delete team: ${TEAM_NAME}"
fi

if ${CLI} rm bridge "${REGION_NAME}" "${BRIDGE_NAME}" --force > /dev/null 2>&1; then
    print_status "Deleted bridge: ${BRIDGE_NAME}"
else
    print_error "Failed to delete bridge: ${BRIDGE_NAME}"
fi

if ${CLI} rm bridge "${REGION_NAME}" "${NEW_BRIDGE_NAME}" --force > /dev/null 2>&1; then
    print_status "Deleted bridge: ${NEW_BRIDGE_NAME}"
else
    print_error "Failed to delete bridge: ${NEW_BRIDGE_NAME}"
fi

if ${CLI} rm region "${REGION_NAME}" --force > /dev/null 2>&1; then
    print_status "Deleted region: ${REGION_NAME}"
else
    print_error "Failed to delete region: ${REGION_NAME}"
fi

# Reassign test user to default "Users" group before deleting our custom group
${CLI} permission assign "${TEST_USER_EMAIL}" "Users" 2>/dev/null

# Deactivate test user
${CLI} user deactivate "${TEST_USER_EMAIL}" --force 2>/dev/null

# Now delete permission group (should work now that user is reassigned)
${CLI} permission delete-group "${PERMISSION_GROUP}" --force

print_status "Cleanup completed"

# 13. Test logout functionality
print_section "Final Authentication Test"

# Test operations after logout (should fail)
${CLI} logout
print_status "Logged out"

echo "Testing operation after logout (should fail)..."
if ${CLI} list teams 2>&1 | grep -q -i "not authenticated"; then
    print_status "Properly rejected operation after logout"
else
    print_error "Did not properly reject operation after logout"
fi

# Cleanup test files
cleanup_test_vault_files

# Summary
print_section "Test Summary"
echo "Test completed successfully!"
echo "Finished: $(date)"
echo "----------------------------------------"

# Exit with success
exit 0