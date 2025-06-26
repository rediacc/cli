#!/bin/bash
# Demo script showing repository creation and management

set -e

echo "=== Rediacc Repository Creation Demo ==="
echo ""

# Configuration
CLI="../rediacc-cli"
MACHINE="rediacc11"
TEAM="Private Team"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
REPO_NAME="DemoRepo_${TIMESTAMP}"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
RED='\033[0;31m'
NC='\033[0m'

print_status() {
    echo -e "${GREEN}✓${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}⚠${NC} $1"
}

print_error() {
    echo -e "${RED}✗${NC} $1"
}

# Get token
TOKEN="${1:-$REDIACC_TOKEN}"
if [ -z "$TOKEN" ]; then
    echo "Please provide token as argument or set REDIACC_TOKEN"
    exit 1
fi

echo "Using token: ${TOKEN:0:8}..."
echo ""

# Step 1: Show current repositories
echo "=== Current Repositories ==="
${CLI} --output json list team-repositories "$TEAM" 2>/dev/null | python3 -c "
import sys, json
data = json.load(sys.stdin)
if data.get('success'):
    repos = data.get('data', [])
    print(f'Found {len(repos)} existing repositories')
    for repo in repos:
        print(f'  - {repo.get(\"repoName\")} (GUID: {repo.get(\"repoGuid\")})')
" || print_error "Failed to list repositories"
echo ""

# Step 2: Create new repository
echo "=== Creating New Repository ==="
echo "Repository name: $REPO_NAME"
if ${CLI} create repository "$TEAM" "$REPO_NAME" --vault '{"description": "Demo repository for testing"}' 2>/dev/null; then
    print_status "Repository created successfully"
else
    print_error "Failed to create repository"
    exit 1
fi
echo ""

# Step 3: Verify creation
echo "=== Verifying Repository Creation ==="
REPO_INFO=$(${CLI} --output json list team-repositories "$TEAM" 2>/dev/null | python3 -c "
import sys, json
data = json.load(sys.stdin)
if data.get('success'):
    for repo in data.get('data', []):
        if repo.get('repoName') == '$REPO_NAME':
            print(json.dumps(repo))
            break
" 2>/dev/null)

if [ -n "$REPO_INFO" ]; then
    REPO_GUID=$(echo "$REPO_INFO" | python3 -c "import sys, json; print(json.load(sys.stdin)['repoGuid'])")
    print_status "Repository verified: $REPO_NAME"
    echo "  Repository GUID: $REPO_GUID"
else
    print_error "Could not verify repository creation"
fi
echo ""

# Step 4: Show repository details
echo "=== Repository Details ==="
${CLI} list team-repositories "$TEAM" | grep "$REPO_NAME" || print_error "Repository not found in list"
echo ""

# Step 5: Cleanup option
echo "=== Cleanup ==="
echo "To delete this repository, run:"
echo "  ${CLI} rm repository \"$TEAM\" \"$REPO_NAME\" --force"
echo ""
echo "Note: For actual mount/sync operations, SSH keys and machine IPs need to be configured in the vault."