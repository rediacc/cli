#!/bin/bash

# Configuration
CLI="./rediacc-cli"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
RANDOM_SUFFIX=$(openssl rand -hex 2)

# Test data - modify these as needed
ADMIN_EMAIL="admin@system.local"
ADMIN_PASSWORD="admin"
COMPANY_NAME="TestCompany_${TIMESTAMP}_${RANDOM_SUFFIX}"
TEAM_NAME="TestTeam_${TIMESTAMP}_${RANDOM_SUFFIX}"
REGION_NAME="TestRegion_${TIMESTAMP}_${RANDOM_SUFFIX}"
BRIDGE_NAME="TestBridge_${TIMESTAMP}_${RANDOM_SUFFIX}"
MACHINE_NAME="TestMachine_${TIMESTAMP}_${RANDOM_SUFFIX}"
REPO_NAME="TestRepo_${TIMESTAMP}_${RANDOM_SUFFIX}"
STORAGE_NAME="TestStorage_${TIMESTAMP}_${RANDOM_SUFFIX}"
SCHEDULE_NAME="TestSchedule_${TIMESTAMP}_${RANDOM_SUFFIX}"

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
BLUE='\033[0;34m'
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

# Start testing
echo "CLI Test Script"
echo "Started: $(date)"
echo "----------------------------------------"

# 1. Login
print_section "Authentication"
echo "Logging in as ${ADMIN_EMAIL}..."
if ${CLI} login --email "${ADMIN_EMAIL}" --password "${ADMIN_PASSWORD}"; then
    print_status "Logged in successfully"
else
    print_error "Login failed"
    exit 1
fi

# 2. Create entities
print_section "Creating Entities"

# Create Team
echo "Creating team: ${TEAM_NAME}"
if ${CLI} create team "${TEAM_NAME}" --vault '{}'; then
    print_status "Created team: ${TEAM_NAME}"
else
    print_error "Failed to create team"
fi

# Create Region
echo "Creating region: ${REGION_NAME}"
if ${CLI} create region "${REGION_NAME}" --vault '{}'; then
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
if ${CLI} create machine "${TEAM_NAME}" "${BRIDGE_NAME}" "${MACHINE_NAME}" --vault '{}'; then
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

# 3. List entities
print_section "Listing Entities"

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

# 4. Inspect entities
print_section "Inspecting Entities"

echo -e "\nTeam details for ${TEAM_NAME}:"
${CLI} inspect team "${TEAM_NAME}"

echo -e "\nMachine details for ${MACHINE_NAME}:"
${CLI} inspect machine "${TEAM_NAME}" "${MACHINE_NAME}"

# 5. Clean up (uncomment if you want to delete after testing)
print_section "Cleanup"
echo "Deleting created entities..."
${CLI} rm machine "${TEAM_NAME}" "${MACHINE_NAME}" --force
${CLI} rm repository "${TEAM_NAME}" "${REPO_NAME}" --force
${CLI} rm storage "${TEAM_NAME}" "${STORAGE_NAME}" --force
${CLI} rm schedule "${TEAM_NAME}" "${SCHEDULE_NAME}" --force
${CLI} rm team "${TEAM_NAME}" --force
${CLI} rm bridge "${REGION_NAME}" "${BRIDGE_NAME}" --force
${CLI} rm region "${REGION_NAME}" --force

print_section "Test Complete"
echo "Finished: $(date)"

# Logout
${CLI} logout
print_status "Logged out"