#!/bin/bash
# Test script to demonstrate rediacc-cli-term functionality

echo "=== Testing Rediacc CLI Terminal ==="
echo ""

# Test 1: Execute a simple command
echo "1. Testing command execution:"
../rediacc-cli-term --token $1 --machine rediacc11 --repo A1 --command "docker ps --format 'table {{.Names}}\t{{.Status}}'"

echo ""
echo "2. Testing Docker container access:"
../rediacc-cli-term --token $1 --machine rediacc11 --repo A1 --command "docker exec plugin-Terminal echo 'Hello from Terminal plugin container'"

echo ""
echo "3. For interactive terminal session, run:"
echo "   ../rediacc-cli-term --token $1 --machine rediacc11 --repo A1"
echo ""
echo "   This will give you a full terminal session where you can:"
echo "   - Run 'status' to see repository status"
echo "   - Run 'enter_container plugin-Terminal' to enter the Terminal container"
echo "   - Run 'logs plugin-Browser' to see Browser plugin logs"
echo "   - Use all standard Docker commands with the repository's isolated Docker daemon"