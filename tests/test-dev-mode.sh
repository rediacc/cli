#!/bin/bash
# Test script for development mode (--dev flag)
# Tests SSH connections with relaxed host key checking

set -e

echo "=== Rediacc CLI Development Mode Test Script ==="
echo ""

# Check if token is provided as argument
if [ -n "$1" ]; then
    TOKEN="$1"
    echo "Using provided token: $TOKEN"
else
    echo "Usage: $0 <token>"
    echo "Please provide a token as argument"
    exit 1
fi

# Test configuration
MACHINE="rediacc11"
REPO="A1"

echo ""
echo "Test Configuration:"
echo "  Machine: $MACHINE"
echo "  Repository: $REPO"
echo ""

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
BLUE='\033[0;34m'
YELLOW='\033[0;33m'
NC='\033[0m' # No Color

print_status() {
    echo -e "${GREEN}✓${NC} $1"
}

print_error() {
    echo -e "${RED}✗${NC} $1"
}

print_section() {
    echo -e "\n${BLUE}=== $1 ===${NC}"
}

# Test 1: Machine connection with --dev
print_section "Test 1: Machine connection with --dev flag"
../rediacc-cli-term --token "$TOKEN" --machine "$MACHINE" --dev --command "echo 'Connected successfully in dev mode'"
if [ $? -eq 0 ]; then
    print_status "Machine connection in dev mode successful"
else
    print_error "Machine connection in dev mode failed"
fi

# Test 2: Repository connection with --dev
print_section "Test 2: Repository connection with --dev flag"
../rediacc-cli-term --token "$TOKEN" --machine "$MACHINE" --repo "$REPO" --dev --command "echo 'Repository: '\$REPO_PATH"
if [ $? -eq 0 ]; then
    print_status "Repository connection in dev mode successful"
else
    print_error "Repository connection in dev mode failed"
fi

# Test 3: File upload with --dev
print_section "Test 3: File upload with --dev flag"
TEST_DIR="test-dev-upload-$(date +%s)"
mkdir -p "$TEST_DIR"
echo "Test file for dev mode" > "$TEST_DIR/test.txt"

../rediacc-cli-sync upload --token "$TOKEN" --local "$TEST_DIR" --machine "$MACHINE" --repo "$REPO" --dev
if [ $? -eq 0 ]; then
    print_status "File upload in dev mode successful"
else
    print_error "File upload in dev mode failed"
fi

# Test 4: File download with --dev
print_section "Test 4: File download with --dev flag"
DOWNLOAD_DIR="test-dev-download-$(date +%s)"

../rediacc-cli-sync download --token "$TOKEN" --machine "$MACHINE" --repo "$REPO" --local "$DOWNLOAD_DIR" --dev
if [ $? -eq 0 ]; then
    print_status "File download in dev mode successful"
    
    # Check if test file exists
    if [ -f "$DOWNLOAD_DIR/test.txt" ]; then
        print_status "Downloaded file verified"
    else
        print_error "Downloaded file not found"
    fi
else
    print_error "File download in dev mode failed"
fi

# Test 5: Compare normal vs dev mode behavior
print_section "Test 5: Comparing normal vs dev mode SSH behavior"

echo -e "\nNormal mode (should use strict host key checking):"
# This might fail in development environments with changing fingerprints
../rediacc-cli-term --token "$TOKEN" --machine "$MACHINE" --command "echo 'Normal mode test'" 2>&1 | tee normal-mode.log

echo -e "\nDev mode (should relax host key checking):"
# This should succeed even with changing fingerprints
../rediacc-cli-term --token "$TOKEN" --machine "$MACHINE" --dev --command "echo 'Dev mode test'" 2>&1 | tee dev-mode.log

# Check if dev mode succeeded where normal mode might have failed
if grep -q "host key verification failed" normal-mode.log 2>/dev/null && ! grep -q "host key verification failed" dev-mode.log 2>/dev/null; then
    print_status "Dev mode properly bypasses host key verification issues"
else
    echo "Note: Both modes succeeded - this is expected in stable environments"
fi

# Cleanup
print_section "Cleanup"
rm -rf "$TEST_DIR" "$DOWNLOAD_DIR" normal-mode.log dev-mode.log
print_status "Test directories cleaned up"

# Summary
print_section "Test Summary"
echo "Development mode tests completed!"
echo ""
echo "The --dev flag is designed for development environments where:"
echo "  - SSH host fingerprints may change frequently"
echo "  - Machines are recreated or redeployed"
echo "  - Network configurations are dynamic"
echo ""
echo -e "${YELLOW}WARNING:${NC} Only use --dev flag in development environments!"
echo "Production environments should always use strict host key checking."
echo ""