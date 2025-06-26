#!/bin/bash
# Quick test script for all Rediacc CLI tools
# This script demonstrates basic usage of sync and term tools

set -e

echo "=== Testing All Rediacc CLI Tools ==="
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
CLI="../rediacc-cli"

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

# Check if infrastructure exists
echo "Checking infrastructure availability..."
echo ""

# Verify machine exists
MACHINE="$DEFAULT_MACHINE"
REPO="$DEFAULT_REPO"

echo "Configuration:"
echo "  Machine: $MACHINE"
echo "  Repository: $REPO"
echo ""

# Note about infrastructure
echo "Note: This test assumes existing infrastructure is available."
echo "If tests fail, ensure:"
echo "  1. Machine '$MACHINE' exists and is accessible"
echo "  2. Repository '$REPO' exists"
echo ""

# Test 1: Sync - Create and upload a test file
echo "=== Test 1: File Sync (Upload) ==="
echo "Creating test file..."
TEST_FILE="test-sync-$(date +%s).txt"
echo "Test file created at $(date)" > "$TEST_FILE"

echo "Uploading file to repository..."
if ../rediacc-cli-sync upload --token "$TOKEN" --local "$TEST_FILE" --machine "$MACHINE" --repo "$REPO" 2>&1; then
    print_status "File upload successful"
else
    print_error "File upload failed - check if machine/repository exists"
    print_warning "Continuing with remaining tests..."
fi
echo ""

# Test 2: Sync - Download files
echo "=== Test 2: File Sync (Download) ==="
DOWNLOAD_DIR="test-download-$(date +%s)"
mkdir -p "$DOWNLOAD_DIR"
echo "Downloading repository files..."
if ../rediacc-cli-sync download --token "$TOKEN" --machine "$MACHINE" --repo "$REPO" --local "$DOWNLOAD_DIR/" 2>&1; then
    print_status "File download successful"
    echo "Downloaded files:"
    ls -la "$DOWNLOAD_DIR/" | head -10
else
    print_error "File download failed"
fi
echo ""

# Test 3: Terminal - Execute simple command
echo "=== Test 3: Terminal Command Execution (Repository) ==="
echo "Checking repository path..."
if ../rediacc-cli-term --token "$TOKEN" --machine "$MACHINE" --repo "$REPO" --command "pwd" 2>&1; then
    print_status "Repository path check successful"
else
    print_error "Repository path check failed"
fi

echo ""
echo "Listing repository files..."
if ../rediacc-cli-term --token "$TOKEN" --machine "$MACHINE" --repo "$REPO" --command "ls -la | head -10" 2>&1; then
    print_status "Repository file listing successful"
else
    print_error "Repository file listing failed"
fi

echo ""
echo "Checking Docker status..."
if ../rediacc-cli-term --token "$TOKEN" --machine "$MACHINE" --repo "$REPO" --command "docker ps --format 'Container: {{.Names}} ({{.Status}})' || echo 'No containers running'" 2>&1; then
    print_status "Docker status check successful"
else
    print_error "Docker status check failed"
fi

echo ""
# Test 4: Terminal - Machine-only connection
echo "=== Test 4: Terminal Command Execution (Machine Only) ==="
echo "Checking machine hostname..."
if ../rediacc-cli-term --token "$TOKEN" --machine "$MACHINE" --command "hostname" 2>&1; then
    print_status "Machine hostname check successful"
else
    print_error "Machine hostname check failed"
fi

echo ""
echo "Checking datastore..."
if ../rediacc-cli-term --token "$TOKEN" --machine "$MACHINE" --command "ls -la /mnt/datastore/ | head -5" 2>&1; then
    print_status "Datastore check successful"
else
    print_error "Datastore check failed"
fi

echo ""
echo "=== All Tests Completed ==="
echo ""
echo "To start interactive terminal sessions:"
echo "  1. Repository: ../rediacc-cli-term --token '$TOKEN' --machine $MACHINE --repo $REPO"
echo "  2. Machine:    ../rediacc-cli-term --token '$TOKEN' --machine $MACHINE"
echo "  3. With --dev:  ../rediacc-cli-term --token '$TOKEN' --machine $MACHINE --dev"
echo ""
echo "Cleaning up test files..."
rm -f "$TEST_FILE" test-sync-*.txt
rm -rf "$DOWNLOAD_DIR" test-download-*

print_status "Cleanup completed"
echo ""
echo "Done!"