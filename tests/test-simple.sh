#!/bin/bash
# Simple test script that tests basic functionality

set -e

echo "=== Simple Rediacc CLI Test ==="
echo ""

# Get token from parameter or environment
TOKEN="${1:-$REDIACC_TOKEN}"

if [ -z "$TOKEN" ]; then
    echo "Error: No token provided. Usage: $0 <TOKEN>"
    echo "Or set REDIACC_TOKEN environment variable"
    exit 1
fi

echo "Using token: ${TOKEN:0:8}..."

# Test configuration
DEFAULT_MACHINE="rediacc11"
DEFAULT_REPO="A1"

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[0;33m'
NC='\033[0m' # No Color

# Helper functions
print_status() {
    echo -e "${GREEN}✓${NC} $1"
}

print_error() {
    echo -e "${RED}✗${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}⚠${NC} $1"
}

# Note about infrastructure requirements
echo ""
echo "Note: This test assumes existing infrastructure is available."
echo "If tests fail, ensure:"
echo "  1. Machine '$DEFAULT_MACHINE' exists and is accessible"
echo "  2. Repository '$DEFAULT_REPO' exists"
echo ""

# Test 1: Machine connection
echo "Test 1: Machine connection"
if ../rediacc-cli-term --token "$TOKEN" --machine "$DEFAULT_MACHINE" --dev --command "pwd && whoami" 2>&1; then
    print_status "Machine connection successful"
else
    print_error "Machine connection failed - check if machine exists"
    print_warning "Continuing with remaining tests..."
fi
echo ""

# Test 2: Repository connection  
echo "Test 2: Repository connection"
if ../rediacc-cli-term --token "$TOKEN" --machine "$DEFAULT_MACHINE" --repo "$DEFAULT_REPO" --dev --command "pwd && ls -la | head -3" 2>&1; then
    print_status "Repository connection successful"
else
    print_error "Repository connection failed - check if repository exists"
    print_warning "Continuing with remaining tests..."
fi
echo ""

# Test 3: Simple file upload
echo "Test 3: File upload"
TEST_FILE="test-file-$(date +%s).txt"
echo "Test content from simple test at $(date)" > "$TEST_FILE"

if ../rediacc-cli-sync upload --token "$TOKEN" --local "$TEST_FILE" --machine "$DEFAULT_MACHINE" --repo "$DEFAULT_REPO" --dev 2>&1; then
    print_status "File upload successful"
else
    print_error "File upload failed"
fi

# Cleanup
rm -f "$TEST_FILE"
echo ""

echo "=== Tests completed ==="
echo ""
echo "Summary:"
echo "  - Machine: $DEFAULT_MACHINE"
echo "  - Repository: $DEFAULT_REPO"
echo "  - Development mode: enabled (--dev flag)"