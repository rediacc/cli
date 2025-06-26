#!/bin/bash
# Quick test script for all Rediacc CLI tools
# This script demonstrates basic usage of sync and term tools

set -e

echo "=== Testing All Rediacc CLI Tools ==="
echo ""

# Check if token is provided
if [ -z "$1" ]; then
    echo "Usage: $0 <token>"
    echo ""
    echo "Please provide a valid token. You can get one by running:"
    echo "  ../rediacc-cli login --email admin@rediacc.io --password 111111"
    exit 1
fi

TOKEN="$1"
MACHINE="rediacc11"
REPO="A1"

echo "Configuration:"
echo "  Token: $TOKEN"
echo "  Machine: $MACHINE"
echo "  Repository: $REPO"
echo ""

# Test 1: Sync - Create and upload a test file
echo "=== Test 1: File Sync (Upload) ==="
echo "Creating test file..."
echo "Test file created at $(date)" > test-sync-$(date +%s).txt

echo "Uploading file to repository..."
../rediacc-cli-sync upload --token "$TOKEN" --local test-sync-*.txt --machine "$MACHINE" --repo "$REPO"
echo ""

# Test 2: Sync - Download files
echo "=== Test 2: File Sync (Download) ==="
mkdir -p test-download
echo "Downloading repository files..."
../rediacc-cli-sync download --token "$TOKEN" --machine "$MACHINE" --repo "$REPO" --local test-download/

echo "Downloaded files:"
ls -la test-download/ | head -10
echo ""

# Test 3: Terminal - Execute simple command
echo "=== Test 3: Terminal Command Execution (Repository) ==="
echo "Checking repository path..."
../rediacc-cli-term --token "$TOKEN" --machine "$MACHINE" --repo "$REPO" --command "pwd"

echo ""
echo "Listing repository files..."
../rediacc-cli-term --token "$TOKEN" --machine "$MACHINE" --repo "$REPO" --command "ls -la | head -10"

echo ""
echo "Checking Docker status..."
../rediacc-cli-term --token "$TOKEN" --machine "$MACHINE" --repo "$REPO" --command "docker ps --format 'Container: {{.Names}} ({{.Status}})' || echo 'No containers running'"

echo ""
# Test 4: Terminal - Machine-only connection
echo "=== Test 4: Terminal Command Execution (Machine Only) ==="
echo "Checking machine hostname..."
../rediacc-cli-term --token "$TOKEN" --machine "$MACHINE" --command "hostname"

echo ""
echo "Checking datastore..."
../rediacc-cli-term --token "$TOKEN" --machine "$MACHINE" --command "ls -la /mnt/datastore/ | head -5"

echo ""
echo "=== All Tests Completed ==="
echo ""
echo "To start interactive terminal sessions:"
echo "  1. Repository: ../rediacc-cli-term --token $TOKEN --machine $MACHINE --repo $REPO"
echo "  2. Machine:    ../rediacc-cli-term --token $TOKEN --machine $MACHINE"
echo ""
echo "Cleaning up test files..."
rm -f test-sync-*.txt
rm -rf test-download/

echo "Done!"