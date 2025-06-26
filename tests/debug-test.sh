#!/bin/bash

# Debug script to test token flow

echo "=== Debug Token Flow ==="

# Get fresh token
cd ..
./rediacc-cli logout >/dev/null 2>&1
./rediacc-cli --output json login --email admin@rediacc.io --password admin >/dev/null 2>&1
TOKEN=$(cat ~/.rediacc/config.json | python3 -c "import sys,json; print(json.load(sys.stdin)['token'])")
cd tests

echo "Token obtained: ${TOKEN:0:8}..."

# Test 1: Direct call
echo ""
echo "Test 1: Direct rediacc-cli call with token"
../rediacc-cli --output json --token "$TOKEN" list teams | grep -E "(success|error)"

# Test 2: Sync tool
echo ""
echo "Test 2: Sync tool with simple file"
echo "test content" > test-file.txt
../rediacc-cli-sync upload --token "$TOKEN" --local test-file.txt --machine rediacc11 --repo A1 2>&1 | head -10
rm -f test-file.txt

# Test 3: Term tool
echo ""
echo "Test 3: Term tool command"
../rediacc-cli-term --token "$TOKEN" --machine rediacc11 --repo A1 --command "echo hello" 2>&1 | head -10

echo ""
echo "=== Debug Complete ==="