# Rediacc CLI Testing System

## Overview
- YAML-based test framework for Rediacc CLI
- Tests stored procedures and CLI commands
- Located in `/cli/tests/yaml/`

## Key Components
- **Test Runner**: `/cli/tests/run_tests.py`
- **Helper Functions**: `/cli/tests/totp_helper.py`
- **Test Files**: `/cli/tests/yaml/community/*.yaml`
- **Results**: `/cli/test_results/`

## Dynamic Variables
- `${TIMESTAMP}` - Timestamp format: YYYYMMDD_HHMMSS
- `${TEST_ID}` - Unique test run identifier
- `${chain.variable}` - Access exported variables from previous tests
- `${totp(secret)}` - Generate TOTP code for 2FA testing
- `${hash(password)}` - Hash password using Rediacc's static salt

## Important Notes
- **Password Salt**: `Rd!@cc111$ecur3P@$w0rd$@lt#H@$h` (raw string, no escapes)
- **Test Activation Code**: Always use `111111` in test environment
- **Boolean Parameters**: CLI converts "true"/"false" strings to booleans automatically
- **Email Uniqueness**: Use prefixes to avoid conflicts (e.g., `tfa-admin-${TIMESTAMP}@test.com`)

## Common Issues & Solutions

### Email Already Exists Error
- Different test files may create users with same email pattern
- Solution: Add unique prefixes per test category
- Example: `perm-admin2-${TIMESTAMP}@test.com` for permission tests

### API Returns 404
- Check if stored procedure exists in `/middleware/AppData/stored-procedures.json`
- Verify all required entities are created in correct order
- Ensure parameter names match exactly

### SQL Comma-Separated List Parsing
- Bug: Using CHARINDEX twice in position calculation
- Fix: `SET @pos = @pos + @len;` (not `SET @pos = CHARINDEX(...) + 1;`)

### Boolean Parameter Handling
- Stored procedures expect bit type for booleans
- CLI must convert string "true"/"false" to actual boolean
- Fixed in `handle_dynamic_endpoint()` and `parse_dynamic_command()`

## Running Tests
```bash
# Run single test
python3 tests/run_tests.py tests/yaml/community/12000_user_management.yaml

# Run all tests
python3 tests/run_tests.py

# Deploy middleware changes
./go system up --force middleware
```

## Debugging Workflow
1. Check test results in `/cli/test_results/`
2. Look for specific error messages in JSON output
3. For SQL errors, check stored procedure in `/middleware/scripts/db_middleware_*.sql`
4. For 404 errors, verify procedure whitelist in `/middleware/AppData/stored-procedures.json`
5. After fixing SQL, deploy with: `./go system up --force middleware`

## Test Structure Essentials
- **setup**: Creates test environment (company, users, teams)
- **tests**: Actual test cases
- **chain_export**: Pass data between test steps
- **expect**: Define success criteria

## Key Test Patterns
- Always create unique company/team/user names using `${TIMESTAMP}`
- Clean up resources in reverse order of creation
- Use `chain_export` to pass dynamic data like secrets or IDs
- Include descriptive test names for clear error identification