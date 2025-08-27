# Rediacc CLI Test Runner

A YAML-based test runner for the Rediacc CLI tools.

## TL;DR

```bash
# Run all tests
./run_tests.py

# Run tests in a directory (pattern relative to yaml/)
./run_tests.py "basic/*.yaml"

# Run single test file (pattern relative to yaml/)
./run_tests.py basic/00001_company_setup.yaml

# Run single test file (absolute/relative path)
./run_tests.py yaml/basic/00001_company_setup.yaml
```

## Quick Example

Create a test file `my_test.yaml`:

```yaml
name: "My Test"
executor: "commands/cli_main.py"

tests:
  - name: "Create team"
    command: ["create", "team"]  # Array format for precise parsing
    args:
      name: "${config.test_data.team.name_pattern}"  # From config.yaml
    expect:
      success: true
```

Run it:
```bash
./run_tests.py my_test.yaml
```

## Features

- **Simple YAML syntax** - No code required
- **JSON validation** - Automatically uses `--output json`
- **Variable support** - `${TIMESTAMP}`, `${RANDOM}`, `${tests.0.data.field}`
- **Output recording** - All responses auto-saved with descriptive filenames
- **Colored output** - Easy to see pass/fail status
- **Coverage tracking** - Automatic tracking of tested commands and stored procedures
- **Coverage report** - Shows which CLI commands and endpoints are tested

## Test Structure

```
tests/
├── run_tests.py           # Test runner
└── yaml/
    ├── config.yaml       # Global test configuration
    └── basic/            # Basic functionality tests
        ├── 00001_company_setup.yaml       # First test - creates company
        ├── 00002_team_operations.yaml     # Second test - creates teams
        ├── 00003_machine_operations.yaml  # Third test - creates machines
        └── 00004_repository_operations.yaml # Fourth test - creates repositories
```

## Test Chaining

Tests are ordered using 5-digit prefixes (00001, 00002, etc.) and can share data:

```yaml
# In 00001_company_setup.yaml
chain_export:
  admin_email: "${config.test_data.company.admin_email_pattern}"
  admin_password: "${config.test_data.company.admin_password}"

# In 00002_team_operations.yaml
tests:
  - name: "Login with previous admin"
    command: ["login"]
    args:
      email: "${chain.admin_email}"      # From previous test
      password: "${chain.admin_password}" # From previous test
```

## Writing Tests

```yaml
name: "Test Name"
executor: "commands/cli_main.py"    # Or commands/term_main.py, etc.

tests:
  - name: "Step 1"
    command: ["login"]        # CLI command as array
    args:                     # Command arguments
      email: "test@example.com"
      password: "pass123"
    expect:                   # Validate response
      success: true           # Only validation - must succeed
    
  - name: "Step 2"
    command: ["create", "company", "MyCompany"]  # Positional args in array
    args:
      email: "admin@mycompany.com"
      password: "secure123"
    expect:
      success: true
```

## Variables

- `${TIMESTAMP}` - Current timestamp
- `${RANDOM}` - Random number
- `${TEST_ID}` - Unique test run ID
- `${env.VAR}` - Environment variable
- `${tests.0.data.field}` - Previous test output
- `${config.path.to.value}` - Value from yaml/config.yaml

## Validation

The test runner validates the success field:

```yaml
# For positive tests
expect:
  success: true    # Test passes if command succeeds

# For negative tests (testing error handling)
expect:
  success: false   # Test passes if command fails
```

Example negative test:
```yaml
- name: "Login with invalid credentials"
  command: ["login"]
  args:
    email: "invalid@test.com"
    password: "wrongpassword"
  expect:
    success: false   # This test PASSES when login fails
```

## Output

Results are saved to `test_results/test_YYYYMMDD_HHMMSS/` with:
- Automatic filename format: `basic.00001_company_setup.COMPANY_SETUP_TEST.create_new_company.json`
- Individual JSON files for each test step
- Colored console output showing pass/fail
- Summary at the end

## Tips

- Set `timeout: 60` for long-running commands
- Check `test_results/` for debugging failed tests
- All tests must pass - no errors are ignored
- Use array format for commands with positional arguments
- Chain tests using 5-digit prefixes to share data between test files
- Check the coverage report to see which commands and endpoints are tested
- Tests stop immediately on first failure (unless expecting failure with `success: false`)
- Use `expect: { success: false }` for negative tests that should fail

## Known Issues

- **Company Creation**: The `create company` command requires the middleware to have `SYSTEM_COMPANY_VAULT_DEFAULTS` environment variable set. See `BACKEND_CONFIG_NOTES.md` for details.
- **Workaround**: Use `00000_existing_company_test.yaml` with existing credentials via environment variables.