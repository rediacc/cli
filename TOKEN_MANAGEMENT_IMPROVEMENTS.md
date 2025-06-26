# Token Management Improvements

## Overview
This document describes the improvements made to the token management system in the Rediacc CLI to address security concerns and architectural inconsistencies.

## Problems Identified

1. **Inconsistent Token Flow**: Functions accepted token parameters but didn't use them, relying instead on the CLI reading from config files
2. **Plain Text Storage**: Tokens stored without encryption in `~/.rediacc/config.json`
3. **Insecure File Permissions**: Config files created without proper access restrictions
4. **No Token Validation**: Invalid tokens could be stored and used
5. **Token Leakage Risk**: Tokens could appear in error messages and logs
6. **No Environment Variable Support**: No way to provide tokens via environment variables for CI/CD

## Implemented Solutions

### 1. Centralized Token Manager (`token_manager.py`)
- Single source of truth for token operations
- Clear precedence: CLI args > env vars > config file
- Automatic file permission management (0o600)
- Token validation using GUID regex pattern
- Token masking for display (shows only first 8 chars)

### 2. Secure Configuration Storage
- Config directory created with 0o700 permissions
- Config files created with 0o600 permissions
- Atomic file writes to prevent corruption
- Automatic permission fixing on existing files

### 3. Direct Token Passing
- Updated all CLI commands to use `--token` parameter
- Removed dependency on config file for token reading
- Functions now accept TokenManager instances instead of unused token strings

### 4. Environment Variable Support
- `REDIACC_TOKEN` environment variable checked automatically
- Useful for CI/CD pipelines and automated scripts
- Takes precedence over config file but not CLI arguments

### 5. Token Security Features
- **Validation**: All tokens validated against GUID pattern before storage
- **Masking**: Tokens displayed as "12345678..." in logs and errors
- **Sanitization**: Error messages automatically scrubbed of token values
- **No HTTPS requirement**: Acknowledged development environment limitation

## Usage Examples

### Basic Usage
```python
from token_manager import TokenManager

# Create token manager
tm = TokenManager()

# Set token
tm.set_token("12345678-1234-1234-1234-123456789012")

# Get token (checks env vars, config, etc.)
token = tm.get_token()

# Override with specific token
token = tm.get_token("override-token-guid")
```

### Environment Variable
```bash
export REDIACC_TOKEN="12345678-1234-1234-1234-123456789012"
./rediacc-cli list teams  # Automatically uses env token
```

### Updated Repository Connection
```python
# Old way
conn = RepositoryConnection(token, machine, repo)

# New way
token_manager = TokenManager()
token_manager.set_token(token)
conn = RepositoryConnection(machine, repo, token_manager)
```

## Migration Notes

1. **Function Signatures**: All functions updated to use TokenManager instead of token strings
2. **Error Messages**: All error outputs now sanitized automatically
3. **Test Scripts**: Already mask tokens properly (show first 8 chars only)
4. **No Backward Compatibility**: Old patterns completely removed for cleaner architecture

## Security Improvements

1. ✅ Config files now have proper Unix permissions (0o600)
2. ✅ Tokens validated before storage
3. ✅ Tokens masked in all output (logs, errors, display)
4. ✅ Environment variable support for secure CI/CD
5. ✅ Atomic file operations prevent corruption
6. ⚠️ HTTPS not enforced (development environment limitation)

## Future Enhancements

1. **OS Keyring Integration**: Store tokens in system keyring
2. **Token Expiration**: Track and refresh expired tokens
3. **Encrypted Storage**: Optional encryption at rest
4. **Audit Logging**: Track token usage for security
5. **Multiple Token Support**: Different tokens for different environments

## Testing

Run the test suite to verify token management:
```bash
python3 test_token_manager.py
```

All existing scripts continue to work with improved security.