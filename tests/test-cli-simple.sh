#!/bin/bash

# Simple test for test-cli.sh functionality

# Configuration
CLI="../src/cli/rediacc-cli"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo "Simple CLI Test"
echo "==============="

# Load .env file
if [ -f "../../.env" ]; then
    while IFS='=' read -r key value; do
        if [[ ! "$key" =~ ^[[:space:]]*# ]] && [[ -n "$key" ]]; then
            key=$(echo "$key" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')
            value=$(echo "$value" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')
            value=$(echo "$value" | sed 's/^"\(.*\)"$/\1/')
            export "$key=$value"
        fi
    done < "../../.env"
fi

# Login
echo -e "\n${YELLOW}1. Testing Login${NC}"
ADMIN_EMAIL="${SYSTEM_ADMIN_EMAIL:-admin@rediacc.io}"
ADMIN_PASSWORD="${SYSTEM_ADMIN_PASSWORD:-admin}"

echo "Logging in as: $ADMIN_EMAIL"
# Get CLI directory
CLI_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../" && pwd)"
CONFIG_FILE="${CLI_DIR}/.config/config.json"
rm -f "$CONFIG_FILE"
LOGIN_OUTPUT=$(${CLI} login --email "$ADMIN_EMAIL" --password "$ADMIN_PASSWORD" 2>&1)
if echo "$LOGIN_OUTPUT" | grep -qi "successfully logged in"; then
    echo -e "${GREEN}✓${NC} Login successful"
else
    echo -e "${RED}✗${NC} Login failed: $LOGIN_OUTPUT"
    exit 1
fi

# Test basic operations
echo -e "\n${YELLOW}2. Testing List Teams${NC}"
TEAMS_OUTPUT=$(${CLI} list teams 2>&1)
if echo "$TEAMS_OUTPUT" | grep -q "teamName"; then
    echo -e "${GREEN}✓${NC} List teams successful"
    echo "$TEAMS_OUTPUT" | head -10
else
    echo -e "${RED}✗${NC} List teams failed"
fi

# Create a test team
echo -e "\n${YELLOW}3. Testing Team Creation${NC}"
TEAM_NAME="TestTeam_${TIMESTAMP}"
echo "Creating team: $TEAM_NAME"
CREATE_OUTPUT=$(${CLI} create team "$TEAM_NAME" --vault '{"test": "data"}' 2>&1)
if echo "$CREATE_OUTPUT" | grep -qi "successfully created"; then
    echo -e "${GREEN}✓${NC} Team created successfully"
else
    echo -e "${RED}✗${NC} Team creation failed: $CREATE_OUTPUT"
fi

# List teams again to verify
echo -e "\n${YELLOW}4. Verifying Team Creation${NC}"
VERIFY_OUTPUT=$(${CLI} list teams 2>&1)
if echo "$VERIFY_OUTPUT" | grep -q "$TEAM_NAME"; then
    echo -e "${GREEN}✓${NC} Team found in list"
else
    echo -e "${RED}✗${NC} Team not found in list"
fi

# Create repository for the team
echo -e "\n${YELLOW}5. Testing Repository Creation${NC}"
REPO_NAME="TestRepo_${TIMESTAMP}"
echo "Creating repository: $REPO_NAME"
REPO_OUTPUT=$(${CLI} create repository "$TEAM_NAME" "$REPO_NAME" --vault '{}' 2>&1)
if echo "$REPO_OUTPUT" | grep -qi "successfully created"; then
    echo -e "${GREEN}✓${NC} Repository created successfully"
else
    echo -e "${RED}✗${NC} Repository creation failed: $REPO_OUTPUT"
fi

# Test JSON output
echo -e "\n${YELLOW}6. Testing JSON Output${NC}"
JSON_OUTPUT=$(${CLI} --output json list teams 2>&1)
if echo "$JSON_OUTPUT" | python3 -m json.tool > /dev/null 2>&1; then
    echo -e "${GREEN}✓${NC} JSON output is valid"
    echo "$JSON_OUTPUT" | python3 -m json.tool | head -20
else
    echo -e "${RED}✗${NC} JSON output is invalid"
fi

# Cleanup
echo -e "\n${YELLOW}7. Cleanup${NC}"
echo "Deleting repository..."
${CLI} rm repository "$TEAM_NAME" "$REPO_NAME" --force 2>&1
echo "Deleting team..."
${CLI} rm team "$TEAM_NAME" --force 2>&1

echo -e "\n${GREEN}Test completed!${NC}"