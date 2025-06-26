# Test Suite Update Summary

## Overview
All test scripts have been updated to support the new token management system with single login.

## Key Changes Made

### 1. Master Test Runner (`run-all-tests.sh`)
- **Created**: A master test runner that logs in once and runs all tests
- **Features**:
  - Single login at the beginning
  - Passes token to all test scripts
  - Comprehensive test summary
  - Color-coded output
  - Timeout handling

### 2. Test Script Updates
All test scripts now:
- Accept token as parameter: `./test-script.sh <TOKEN>`
- Support environment variable: `REDIACC_TOKEN`
- No longer perform individual logins
- Use consistent token handling pattern

### 3. Updated Test Scripts
- ✅ `test-simple.sh` - Basic functionality tests
- ✅ `test-quick.sh` - Quick validation tests
- ✅ `test-sync.sh` - File synchronization tests
- ✅ `test-term.sh` - Terminal access tests
- ✅ `test-full-api.sh` - Comprehensive API tests
- ✅ `test-integration.sh` - Token management integration
- ✅ `test-token-management.sh` - Token feature tests
- ✅ `test-dev-mode.sh` - Development mode tests
- ✅ `test-term-demo.sh` - Terminal demo tests
- ✅ `verify-setup.sh` - Setup verification

### 4. Token Handling Pattern
```bash
# Get token from parameter or environment
TOKEN="${1:-$REDIACC_TOKEN}"

if [ -z "$TOKEN" ]; then
    echo "Error: No token provided. Usage: $0 <TOKEN>"
    echo "Or set REDIACC_TOKEN environment variable"
    exit 1
fi
```

## Test Results

### Core Tests (Infrastructure Independent)
- ✅ **verify-setup** - All tools properly installed
- ✅ **test-integration** - Token management features working  
- ✅ **test-token-management** - Comprehensive token tests passing
- ✅ **test-simple.sh** - Basic functionality tests
- ✅ **test-quick.sh** - Quick validation tests
- ✅ **test-dev-mode.sh** - Development mode tests
- ✅ **test-full-api.sh** - Comprehensive API tests

### Infrastructure Tests
Tests requiring specific machines/repositories:
- ⚠️ **test-sync.sh** - File synchronization tests (requires machine/repo)
- ⚠️ **test-term.sh** - Terminal access tests (requires machine/repo)
- **test-term-simple.sh** - Created as simplified version for basic testing

**Note**: 
1. Infrastructure tests require valid machines configured in the system
2. test-full-api.sh logs out at the end, invalidating the token for subsequent tests
3. Token chaining mechanism means each API call may update the token

## Usage

### Run All Core Tests
```bash
./run-all-tests.sh
```

### Run Individual Test
```bash
# Option 1: With token parameter
./test-integration.sh YOUR_TOKEN

# Option 2: With environment variable
export REDIACC_TOKEN=YOUR_TOKEN
./test-integration.sh
```

### Run Specific Test Set
```bash
# Get token
../rediacc-cli --output json login --email admin@rediacc.io --password admin
TOKEN=$(cat ~/.rediacc/config.json | python3 -c "import sys,json; print(json.load(sys.stdin)['token'])")

# Run tests
./test-sync.sh "$TOKEN"
./test-term.sh "$TOKEN"
```

## Benefits
1. **Single Login**: No duplicate authentication
2. **Faster Testing**: Tests run sequentially without re-authentication
3. **Consistent Token Handling**: All tests use the same pattern
4. **Environment Support**: CI/CD friendly with REDIACC_TOKEN
5. **Better Error Handling**: Clear messages when token is missing

## Notes
- Token expiration is handled by the Rediacc token chaining mechanism
- Tests clean up after themselves
- Old test artifacts are automatically removed
- Config file permissions are verified (600)