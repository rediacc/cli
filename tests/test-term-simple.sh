#!/bin/bash
# Simplified test script for rediacc-cli-term
# Tests basic terminal access functionality

set -e

echo "=== Rediacc CLI Terminal Test Script (Simplified) ==="
echo ""

# Get token from parameter or environment
TOKEN="${1:-$REDIACC_TOKEN}"

if [ -z "$TOKEN" ]; then
    echo "Error: No token provided. Usage: $0 <TOKEN>"
    echo "Or set REDIACC_TOKEN environment variable"
    exit 1
fi

echo "Using token: ${TOKEN:0:8}..."

# Test configuration - use whatever machine is available
MACHINE="${TEST_MACHINE:-rediacc11}"

echo ""
echo "Test Configuration:"
echo "  Machine: $MACHINE"
echo ""

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

# Test 1: Basic machine connection
echo "=== Test 1: Basic machine connection ==="
if ../rediacc-cli-term --token "$TOKEN" --machine "$MACHINE" --command "echo 'Connected successfully' && pwd && whoami" 2>&1; then
    print_status "Successfully connected to machine"
else
    print_error "Failed to connect to machine"
    echo ""
    echo "Note: This test requires:"
    echo "  1. A valid machine name (default: rediacc11)"
    echo "  2. Proper SSH access configured"
    echo "  3. Valid token with appropriate permissions"
    echo ""
    echo "You can specify a different machine with: TEST_MACHINE=<machine> $0"
    exit 1
fi
echo ""

# Test 2: Check system info
echo "=== Test 2: System information ==="
if ../rediacc-cli-term --token "$TOKEN" --machine "$MACHINE" --command "uname -a" 2>&1; then
    print_status "Retrieved system information"
else
    print_error "Failed to get system info"
fi
echo ""

# Test 3: Check datastore access
echo "=== Test 3: Datastore access ==="
if ../rediacc-cli-term --token "$TOKEN" --machine "$MACHINE" --command "ls -la /mnt/datastore 2>/dev/null | head -5 || echo 'Datastore not accessible'" 2>&1; then
    print_status "Checked datastore access"
else
    print_error "Failed to check datastore"
fi
echo ""

# Test 4: Test development mode
echo "=== Test 4: Development mode ==="
if ../rediacc-cli-term --token "$TOKEN" --machine "$MACHINE" --dev --command "echo 'Dev mode active'" 2>&1; then
    print_status "Development mode works"
else
    print_error "Failed in development mode"
fi
echo ""

# Test 5: Check Docker availability
echo "=== Test 5: Docker availability ==="
if ../rediacc-cli-term --token "$TOKEN" --machine "$MACHINE" --command "which docker >/dev/null 2>&1 && echo 'Docker is installed' || echo 'Docker not found'" 2>&1; then
    print_status "Checked Docker availability"
else
    print_error "Failed to check Docker"
fi
echo ""

echo "=== Basic tests completed ==="
echo ""
echo "For interactive testing, try:"
echo "  ../rediacc-cli-term --token $TOKEN --machine $MACHINE"
echo ""
echo "For repository-specific tests, ensure a repository exists and run:"
echo "  ../rediacc-cli-term --token $TOKEN --machine $MACHINE --repo <repo_name>"