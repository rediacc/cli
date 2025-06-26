# Rediacc CLI Tests

This directory contains test scripts for the Rediacc CLI tools.

## Test Scripts

### Core Tests

- **`test-full-api.sh`** - Comprehensive test of all Rediacc API endpoints and CLI commands
- **`test-quick.sh`** - Quick test of sync and term tools with basic operations
- **`test-integration.sh`** - Integration test for new token management features
- **`test-token-management.sh`** - Comprehensive token management test suite

### Tool-Specific Tests

- **`test-sync.sh`** - Full test suite for `rediacc-cli-sync` file synchronization
  - Tests upload/download operations
  - Tests mirror mode and checksum verification
  - Tests development mode (--dev flag)
- **`test-term.sh`** - Full test suite for `rediacc-cli-term` terminal access
  - Tests repository connections with Docker environment
  - Tests machine-only connections
  - Tests command execution and interactive sessions
  - Tests development mode (--dev flag)
- **`test-term-demo.sh`** - Demo script showing terminal functionality examples
  - Repository connection examples
  - Machine-only connection examples
- **`test-dev-mode.sh`** - Dedicated test for development mode functionality
  - Tests --dev flag for both sync and term tools
  - Verifies SSH host key checking behavior

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

## Development Mode (--dev flag)

Both `rediacc-cli-sync` and `rediacc-cli-term` support a `--dev` flag for development environments where SSH host fingerprints change frequently.

### When to Use --dev:
- Development environments with dynamic infrastructure
- Testing environments where machines are frequently recreated
- Local development with changing network configurations

### Security Warning:
**Never use --dev in production!** It relaxes SSH host key verification which could expose you to man-in-the-middle attacks.

### Example Usage:
```bash
# Terminal with --dev
./rediacc-cli-term --token TOKEN --machine rediacc11 --dev

# Sync with --dev
./rediacc-cli-sync upload --token TOKEN --local ./files --machine rediacc11 --repo A1 --dev
```

## Quick Verification

To quickly verify all tools are working:
```bash
cd tests
./test-quick.sh $(../rediacc-cli login --email admin@rediacc.io --password 111111 --output json | grep -o '"token":"[^"]*' | cut -d'"' -f4)
```

## Token Management Features

The new token management system supports:

### 1. Command Line Override
```bash
# Override saved token
./rediacc-cli --token YOUR_TOKEN list teams
```

### 2. Environment Variables
```bash
# Use environment variable
export REDIACC_TOKEN="YOUR_TOKEN"
./rediacc-cli list teams
```

### 3. Token Validation
- All tokens are validated as GUIDs before use
- Invalid tokens are rejected with clear error messages
- Tokens are masked in all output (only first 8 chars shown)

### 4. Secure Storage
- Config files have 0o600 permissions (owner read/write only)
- Config directory has 0o700 permissions
- Tokens from --token or env vars are never saved to disk

### 5. Testing Token Management
```bash
# Run integration test
./test-integration.sh

# Run comprehensive test suite
./test-token-management.sh
```