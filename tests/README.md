# Rediacc CLI Tests

This directory contains test scripts for the Rediacc CLI tools.

## Test Scripts

### Core Tests

- **`test-full-api.sh`** - Comprehensive test of all Rediacc API endpoints and CLI commands
- **`test-quick.sh`** - Quick test of sync and term tools with basic operations

### Tool-Specific Tests

- **`test-sync.sh`** - Full test suite for `rediacc-cli-sync` file synchronization
- **`test-term.sh`** - Full test suite for `rediacc-cli-term` terminal access
- **`test-term-demo.sh`** - Demo script showing terminal functionality examples

## Running Tests

### With Token
If you have a valid token:
```bash
./test-quick.sh YOUR_TOKEN
./test-sync.sh YOUR_TOKEN
./test-term.sh YOUR_TOKEN
```

### Without Token (Auto-login)
The test scripts will automatically login using admin credentials:
```bash
./test-sync.sh
./test-term.sh
./test-full-api.sh
```

## Test Artifacts

Test scripts may create temporary files and directories:
- `test*.txt` - Test files for sync operations
- `test-download/` - Directory for download tests
- `test-upload/` - Directory for upload tests

These are automatically cleaned up after tests complete and are ignored by git.

## Quick Verification

To quickly verify all tools are working:
```bash
cd tests
./test-quick.sh $(../rediacc-cli login --email admin@rediacc.io --password 111111 --output json | grep -o '"token":"[^"]*' | cut -d'"' -f4)
```