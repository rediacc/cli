# Token Management with Chaining Support

## Overview
The new token management system is fully aware of Rediacc's token chaining mechanism while providing clean separation of concerns.

## How Token Chaining Works

### 1. **Token Chain Mechanism**
- Each API response contains `nextRequestCredential` in the first table
- This new token must be used for the next API request
- Tokens are single-use for security

### 2. **Token Flow**
```
Login → Initial Token → API Request 1 → New Token → API Request 2 → New Token → ...
```

## Implementation Details

### Command Line Interface (`rediacc-cli`)

1. **Global --token Option**
   ```bash
   rediacc-cli --token <TOKEN> list machines
   ```
   - Overrides any saved token
   - Validated before use
   - Does NOT save to config file

2. **Token Chaining Behavior**
   - When using `--token`: Chained tokens update in memory only
   - Without `--token`: Chained tokens save to config file
   - Ensures one-time tokens don't break subsequent commands

3. **ConfigManager Updates**
   ```python
   # Track if token was overridden
   self._token_overridden = False
   
   # In token chaining:
   if not self.config_manager._token_overridden:
       self.config_manager.save_config()
   ```

### Sync and Terminal Tools

1. **Token Manager Integration**
   ```python
   # Create token manager with provided token
   token_manager = TokenManager()
   token_manager.set_token(args.token)
   
   # Pass to all API calls
   conn = RepositoryConnection(machine, repo, token_manager)
   ```

2. **Direct Token Passing**
   - All CLI commands now use `--token` parameter
   - No more indirect config file reading
   - Token passed directly to rediacc-cli

## Usage Patterns

### 1. **Standard Usage (with chaining)**
```bash
# Login - saves initial token
rediacc-cli login --email user@example.com

# Subsequent commands use chained tokens from config
rediacc-cli list machines
rediacc-cli create repository --team DevTeam --name MyRepo
```

### 2. **CI/CD Usage (override token)**
```bash
# Use environment variable
export REDIACC_TOKEN="12345678-1234-1234-1234-123456789012"
rediacc-cli list machines

# Or command line
rediacc-cli --token "$CI_TOKEN" list machines
```

### 3. **Sync/Terminal Tools**
```bash
# Direct token usage
rediacc-cli-sync upload --token "$TOKEN" --machine server1 --repo data --local ./files

# Token manager handles validation and passing
rediacc-cli-term --token "$TOKEN" --machine server1 --repo data
```

## Security Features

1. **Token Validation**: All tokens validated as GUIDs before use
2. **Token Masking**: Only first 8 chars shown in logs/errors
3. **No Persistence**: Override tokens never saved to disk
4. **Secure Storage**: Config files have 0o600 permissions

## Benefits

1. **Clean Architecture**: No more unused token parameters
2. **Flexible Usage**: Works for both interactive and automated use
3. **Chaining Support**: Fully compatible with Rediacc's security model
4. **Environment Support**: CI/CD friendly with env vars
5. **No Breaking Changes**: Existing workflows continue to work