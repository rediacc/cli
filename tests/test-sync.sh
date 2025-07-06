#!/bin/bash

# File synchronization tests
# Tests: upload, download, mirror, verify, exclusions

set -e  # Exit on error

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Source common test utilities
source ./test-common.sh

print_header "File Synchronization Tests"

# Get token
TOKEN=$(require_token "$1")
print_info "Using token: ${TOKEN:0:8}..."

# Test configuration
TEST_DIR=$(create_test_dir "sync")
TEST_FILES_DIR="${TEST_DIR}/files"
TEST_DOWNLOAD_DIR="${TEST_DIR}/download"

# Create test data
print_subheader "Preparing Test Data"
mkdir -p "${TEST_FILES_DIR}/subdir"
echo "Test content 1" > "${TEST_FILES_DIR}/file1.txt"
echo "Test content 2" > "${TEST_FILES_DIR}/file2.txt"
echo "Subdirectory file" > "${TEST_FILES_DIR}/subdir/file3.txt"
echo "Should be excluded" > "${TEST_FILES_DIR}/exclude.tmp"
touch "${TEST_FILES_DIR}/.hidden"
print_pass "Created test files in ${TEST_FILES_DIR}"

# Test 1: Basic upload
print_subheader "Basic Upload Tests"

# Check if we have required test infrastructure
OUTPUT=$(${CLI} --output json --token "$TOKEN" list machines --team "$TEST_TEAM" 2>&1)
if ! echo "$OUTPUT" | grep -q "$TEST_MACHINE"; then
    skip_test "Test machine '$TEST_MACHINE' not found in team '$TEST_TEAM'"
    skip_test "Skipping sync tests - no test infrastructure"
    print_summary
    safe_cleanup "$TEST_DIR"
    exit 0
fi

# Basic upload
OUTPUT=$(${SYNC} upload \
    --token "$TOKEN" \
    --local "${TEST_FILES_DIR}" \
    --machine "$TEST_MACHINE" \
    --repo "$TEST_REPO" \
    --team "$TEST_TEAM" \
    2>&1)
check_contains "$OUTPUT" "files transferred" "Basic upload successful"

# Test 2: Download verification
print_subheader "Download Tests"

mkdir -p "$TEST_DOWNLOAD_DIR"
OUTPUT=$(${SYNC} download \
    --token "$TOKEN" \
    --machine "$TEST_MACHINE" \
    --repo "$TEST_REPO" \
    --team "$TEST_TEAM" \
    --local "$TEST_DOWNLOAD_DIR" \
    2>&1)
check_contains "$OUTPUT" "files transferred" "Basic download successful"

# Verify downloaded content
if [ -f "${TEST_DOWNLOAD_DIR}/file1.txt" ]; then
    content=$(cat "${TEST_DOWNLOAD_DIR}/file1.txt")
    if [ "$content" = "Test content 1" ]; then
        print_pass "Downloaded file content matches"
    else
        print_fail "Downloaded file content mismatch"
    fi
else
    print_fail "Downloaded file not found"
fi

# Test 3: Mirror mode
print_subheader "Mirror Mode Tests"

# Add extra file to remote (simulated by modifying local and re-uploading)
echo "Extra file" > "${TEST_FILES_DIR}/extra.txt"
${SYNC} upload --token "$TOKEN" --local "${TEST_FILES_DIR}" --machine "$TEST_MACHINE" --repo "$TEST_REPO" --team "$TEST_TEAM" >/dev/null 2>&1

# Remove extra file locally
rm "${TEST_FILES_DIR}/extra.txt"

# Download without mirror (extra file should remain)
rm -rf "$TEST_DOWNLOAD_DIR"
mkdir -p "$TEST_DOWNLOAD_DIR"
OUTPUT=$(${SYNC} download \
    --token "$TOKEN" \
    --machine "$TEST_MACHINE" \
    --repo "$TEST_REPO" \
    --team "$TEST_TEAM" \
    --local "$TEST_DOWNLOAD_DIR" \
    2>&1)
if [ -f "${TEST_DOWNLOAD_DIR}/extra.txt" ]; then
    print_pass "Non-mirror mode preserves remote files"
else
    print_fail "Non-mirror mode: remote file missing"
fi

# Download with mirror (extra file should be removed)
OUTPUT=$(${SYNC} download \
    --token "$TOKEN" \
    --machine "$TEST_MACHINE" \
    --repo "$TEST_REPO" \
    --team "$TEST_TEAM" \
    --local "$TEST_DOWNLOAD_DIR" \
    --mirror \
    --confirm \
    2>&1)
if [ ! -f "${TEST_DOWNLOAD_DIR}/extra.txt" ]; then
    print_pass "Mirror mode removes extra files"
else
    print_fail "Mirror mode: extra file not removed"
fi

# Test 4: Exclusions
print_subheader "Exclusion Tests"

# Upload with exclusions
echo "*.tmp" > "${TEST_DIR}/exclude_patterns.txt"
echo ".hidden" >> "${TEST_DIR}/exclude_patterns.txt"

OUTPUT=$(${SYNC} upload \
    --token "$TOKEN" \
    --local "${TEST_FILES_DIR}" \
    --machine "$TEST_MACHINE" \
    --repo "${TEST_REPO}_exclude" \
    --team "$TEST_TEAM" \
    --exclude "*.tmp" \
    --exclude ".hidden" \
    2>&1)
check_contains "$OUTPUT" "files transferred" "Upload with exclusions"

# Verify exclusions worked
rm -rf "$TEST_DOWNLOAD_DIR"
mkdir -p "$TEST_DOWNLOAD_DIR"
${SYNC} download \
    --token "$TOKEN" \
    --machine "$TEST_MACHINE" \
    --repo "${TEST_REPO}_exclude" \
    --team "$TEST_TEAM" \
    --local "$TEST_DOWNLOAD_DIR" \
    >/dev/null 2>&1

if [ ! -f "${TEST_DOWNLOAD_DIR}/exclude.tmp" ] && [ ! -f "${TEST_DOWNLOAD_DIR}/.hidden" ]; then
    print_pass "Excluded files not uploaded"
else
    print_fail "Exclusion failed - excluded files were uploaded"
fi

# Test 5: Verify mode
print_subheader "Verify Mode Tests"

# Corrupt a local file
echo "Corrupted content" > "${TEST_DOWNLOAD_DIR}/file1.txt"

OUTPUT=$(${SYNC} download \
    --token "$TOKEN" \
    --machine "$TEST_MACHINE" \
    --repo "$TEST_REPO" \
    --team "$TEST_TEAM" \
    --local "$TEST_DOWNLOAD_DIR" \
    --verify \
    2>&1)
check_contains "$OUTPUT" "file1.txt" "Verify mode detects changed files"

# Test 6: Error handling
print_subheader "Error Handling"

# Invalid machine
OUTPUT=$(${SYNC} upload \
    --token "$TOKEN" \
    --local "$TEST_FILES_DIR" \
    --machine "nonexistent-machine" \
    --repo "$TEST_REPO" \
    --team "$TEST_TEAM" \
    2>&1 || true)
check_contains "$OUTPUT" "not found" "Invalid machine error handled"

# Invalid local path
OUTPUT=$(${SYNC} upload \
    --token "$TOKEN" \
    --local "/nonexistent/path" \
    --machine "$TEST_MACHINE" \
    --repo "$TEST_REPO" \
    --team "$TEST_TEAM" \
    2>&1 || true)
check_contains "$OUTPUT" "does not exist" "Invalid local path error handled"

# Clean up
safe_cleanup "$TEST_DIR"
print_pass "Cleaned up test data"

# Print summary
print_summary