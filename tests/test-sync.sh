#!/bin/bash

# Configuration
CLI="../rediacc-cli"
SYNC="../rediacc-cli-sync"
TERM="../rediacc-cli-term"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
RANDOM_SUFFIX=$(openssl rand -hex 2)

# Load environment variables from .env file if it exists
if [ -f "../.env" ]; then
    while IFS='=' read -r key value; do
        # Skip comments and empty lines
        [[ $key =~ ^#.*$ ]] && continue
        [[ -z "$key" ]] && continue
        # Remove quotes from value
        value="${value%\"}"
        value="${value#\"}"
        export "$key=$value"
    done < "../.env"
fi

# Test data
ADMIN_EMAIL="${SYSTEM_ADMIN_EMAIL:-admin@rediacc.io}"
ADMIN_PASSWORD="${SYSTEM_ADMIN_PASSWORD:-admin}"
TEST_MACHINE="rediacc11"
TEST_REPO="A1"
TEST_DIR="test-sync-${TIMESTAMP}"

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
BLUE='\033[0;34m'
YELLOW='\033[0;33m'
NC='\033[0m' # No Color

# Helper functions
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

# Create test directory with various files
create_test_data() {
    echo "Creating test data directory: ${TEST_DIR}"
    mkdir -p "${TEST_DIR}/subdir1/subdir2"
    mkdir -p "${TEST_DIR}/empty-dir"
    
    # Create various file types and sizes
    echo "This is a simple text file" > "${TEST_DIR}/simple.txt"
    echo "File with special chars: áéíóú ñ 中文" > "${TEST_DIR}/special-chars.txt"
    echo "#!/bin/bash" > "${TEST_DIR}/script.sh"
    chmod +x "${TEST_DIR}/script.sh"
    
    # Create files in subdirectories
    echo "File in subdir1" > "${TEST_DIR}/subdir1/file1.txt"
    echo "File in subdir2" > "${TEST_DIR}/subdir1/subdir2/nested.txt"
    
    # Create a larger file
    dd if=/dev/urandom of="${TEST_DIR}/binary-data.bin" bs=1024 count=100 2>/dev/null
    
    # Create a file with spaces in name
    echo "File with spaces" > "${TEST_DIR}/file with spaces.txt"
    
    # Show what we created
    echo "Test data structure:"
    tree "${TEST_DIR}" 2>/dev/null || find "${TEST_DIR}" -type f | sort
}

# Start testing
echo "Rediacc CLI Sync Test Script"
echo "Started: $(date)"
echo "----------------------------------------"

# 1. Authentication
print_section "Authentication"

echo "Logging in as admin..."
if ${CLI} login --email "${ADMIN_EMAIL}" --password "${ADMIN_PASSWORD}" --session-name "SyncTest_${TIMESTAMP}"; then
    print_status "Logged in successfully"
    
    # Extract token from config file
    if [ -f ~/.rediacc/config.json ]; then
        TOKEN=$(python3 -c "import json; print(json.load(open('$HOME/.rediacc/config.json'))['token'])" 2>/dev/null)
        if [ -n "${TOKEN}" ]; then
            print_status "Got token: ${TOKEN:0:8}..."
        else
            print_error "Failed to extract token from config"
            exit 1
        fi
    else
        print_error "Config file not found"
        exit 1
    fi
else
    print_error "Login failed"
    exit 1
fi

# 2. Verify machine and repository exist
print_section "Verifying Target Machine and Repository"

echo "Finding team for machine '${TEST_MACHINE}'..."
# For this test, we know the team name
TEAM_NAME="Private Team"
echo "Checking if machine '${TEST_MACHINE}' exists in team '${TEAM_NAME}'..."
MACHINES_OUTPUT=$(${CLI} list team-machines "${TEAM_NAME}" 2>&1)
if echo "${MACHINES_OUTPUT}" | grep -q "${TEST_MACHINE}"; then
    print_status "Machine '${TEST_MACHINE}' found in team '${TEAM_NAME}'"
    MACHINE_FOUND=true
else
    print_error "Machine '${TEST_MACHINE}' not found"
    echo "Available machines:"
    echo "${MACHINES_OUTPUT}"
    MACHINE_FOUND=false
fi

if [ "${MACHINE_FOUND}" != "true" ]; then
    print_error "Machine '${TEST_MACHINE}' not found in any team"
    exit 1
fi

if [ -n "${TEAM_NAME}" ]; then
    echo "Machine belongs to team: ${TEAM_NAME}"
    
    echo "Checking if repository '${TEST_REPO}' exists..."
    REPOS_OUTPUT=$(${CLI} list team-repositories "${TEAM_NAME}" 2>&1)
    if echo "${REPOS_OUTPUT}" | grep -q "${TEST_REPO}"; then
        print_status "Repository '${TEST_REPO}' found"
    else
        print_error "Repository '${TEST_REPO}' not found in team '${TEAM_NAME}'"
        echo "Available repositories:"
        echo "${REPOS_OUTPUT}"
        exit 1
    fi
else
    print_error "Could not determine team for machine"
    exit 1
fi

# 3. Create test data
print_section "Creating Test Data"
create_test_data

# 4. Test Upload Commands
print_section "Testing Upload Commands"

# Test basic upload
echo -e "\n1. Basic upload test:"
if ${SYNC} upload --token="${TOKEN}" --local="${TEST_DIR}" --machine="${TEST_MACHINE}" --repo="${TEST_REPO}"; then
    print_status "Basic upload successful"
else
    print_error "Basic upload failed"
fi

# Test upload with confirm
echo -e "\n2. Upload with confirmation test:"
echo "y" | ${SYNC} upload --token="${TOKEN}" --local="${TEST_DIR}" --machine="${TEST_MACHINE}" --repo="${TEST_REPO}" --confirm
if [ $? -eq 0 ]; then
    print_status "Upload with confirmation successful"
else
    print_error "Upload with confirmation failed"
fi

# Test upload with verify
echo -e "\n3. Upload with checksum verification:"
if ${SYNC} upload --token="${TOKEN}" --local="${TEST_DIR}" --machine="${TEST_MACHINE}" --repo="${TEST_REPO}" --verify; then
    print_status "Upload with verification successful"
else
    print_error "Upload with verification failed"
fi

# 5. Create download directory
print_section "Testing Download Commands"
DOWNLOAD_DIR="test-download-${TIMESTAMP}"

# Test basic download
echo -e "\n1. Basic download test:"
if ${SYNC} download --token="${TOKEN}" --machine="${TEST_MACHINE}" --repo="${TEST_REPO}" --local="${DOWNLOAD_DIR}"; then
    print_status "Basic download successful"
    
    # Verify downloaded files
    echo "Verifying downloaded files..."
    if diff -r "${TEST_DIR}" "${DOWNLOAD_DIR}" > /dev/null 2>&1; then
        print_status "Downloaded files match original"
    else
        print_warning "Downloaded files differ from original"
        diff -r "${TEST_DIR}" "${DOWNLOAD_DIR}" || true
    fi
else
    print_error "Basic download failed"
fi

# Test download with confirm
echo -e "\n2. Download with confirmation test:"
DOWNLOAD_DIR2="test-download2-${TIMESTAMP}"
echo "y" | ${SYNC} download --token="${TOKEN}" --machine="${TEST_MACHINE}" --repo="${TEST_REPO}" --local="${DOWNLOAD_DIR2}" --confirm
if [ $? -eq 0 ]; then
    print_status "Download with confirmation successful"
else
    print_error "Download with confirmation failed"
fi

# 6. Test Mirror Functionality
print_section "Testing Mirror Functionality"

# Add a new file locally
echo "New file added after initial sync" > "${TEST_DIR}/new-file.txt"

# Remove a file locally
rm -f "${TEST_DIR}/simple.txt"

echo -e "\n1. Upload with mirror (should delete remote simple.txt and add new-file.txt):"
echo "y" | ${SYNC} upload --token="${TOKEN}" --local="${TEST_DIR}" --machine="${TEST_MACHINE}" --repo="${TEST_REPO}" --mirror --confirm
if [ $? -eq 0 ]; then
    print_status "Upload with mirror successful"
else
    print_error "Upload with mirror failed"
fi

# Download to verify mirror worked
echo -e "\n2. Download to verify mirror changes:"
MIRROR_TEST_DIR="test-mirror-${TIMESTAMP}"
if ${SYNC} download --token="${TOKEN}" --machine="${TEST_MACHINE}" --repo="${TEST_REPO}" --local="${MIRROR_TEST_DIR}"; then
    print_status "Mirror verification download successful"
    
    # Check if simple.txt is gone and new-file.txt exists
    if [ ! -f "${MIRROR_TEST_DIR}/simple.txt" ] && [ -f "${MIRROR_TEST_DIR}/new-file.txt" ]; then
        print_status "Mirror functionality verified: old file removed, new file added"
    else
        print_error "Mirror functionality not working as expected"
        ls -la "${MIRROR_TEST_DIR}/"
    fi
else
    print_error "Mirror verification download failed"
fi

# 7. Test Terminal Access
print_section "Testing Terminal Access"

echo "Testing repository terminal access..."
${TERM} --token="${TOKEN}" --machine="${TEST_MACHINE}" --repo="${TEST_REPO}" --command="pwd && ls -la | head -5"
if [ $? -eq 0 ]; then
    print_status "Terminal access successful"
else
    print_error "Terminal access failed"
fi

# Test Docker access
echo -e "\nTesting Docker access in repository:"
${TERM} --token="${TOKEN}" --machine="${TEST_MACHINE}" --repo="${TEST_REPO}" --command="docker ps || echo 'Docker not running'"

# 8. Test Error Handling
print_section "Testing Error Handling"

echo -e "\n1. Test with invalid machine:"
${SYNC} upload --token="${TOKEN}" --local="${TEST_DIR}" --machine="InvalidMachine" --repo="${TEST_REPO}" 2>&1 | grep -q "not found"
if [ $? -eq 0 ]; then
    print_status "Properly handled invalid machine"
else
    print_error "Did not properly handle invalid machine"
fi

echo -e "\n2. Test with invalid repository:"
${SYNC} upload --token="${TOKEN}" --local="${TEST_DIR}" --machine="${TEST_MACHINE}" --repo="InvalidRepo" 2>&1 | grep -q "not found"
if [ $? -eq 0 ]; then
    print_status "Properly handled invalid repository"
else
    print_error "Did not properly handle invalid repository"
fi

echo -e "\n3. Test with invalid local path:"
${SYNC} upload --token="${TOKEN}" --local="/nonexistent/path" --machine="${TEST_MACHINE}" --repo="${TEST_REPO}" 2>&1 | grep -q "does not exist"
if [ $? -eq 0 ]; then
    print_status "Properly handled invalid local path"
else
    print_error "Did not properly handle invalid local path"
fi

# 9. Cleanup
print_section "Cleanup"

echo "Cleaning up test directories..."
rm -rf "${TEST_DIR}" "${DOWNLOAD_DIR}" "${DOWNLOAD_DIR2}" "${MIRROR_TEST_DIR}"
print_status "Test directories cleaned up"

echo "Logging out..."
${CLI} logout
print_status "Logged out"

# Summary
print_section "Test Summary"
echo "Test completed successfully!"
echo "Finished: $(date)"
echo "----------------------------------------"