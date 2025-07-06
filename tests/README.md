# Rediacc CLI Test Suite (Simplified)

This directory contains the simplified test suite for the Rediacc CLI tools.

## Test Structure

The test suite has been simplified from 14+ test files down to 6 core files:

### Core Test Files

1. **test-common.sh** - Shared test utilities and helper functions
   - Color output helpers
   - Test assertion functions
   - Token management
   - Test data cleanup

2. **test-core.sh** - Core CLI functionality tests
   - Basic CLI operations (help, version)
   - Token management (parameter, env var, config)
   - Basic API operations (list teams, companies, user info)
   - Error handling and output formats

3. **test-api.sh** - API endpoint tests (simplified)
   - CRUD operations for main entities
   - Vault operations
   - Search functionality
   - Pagination tests
   - API error handling

4. **test-sync.sh** - File synchronization tests
   - Upload/download operations
   - Mirror mode
   - File exclusions
   - Verify mode
   - Error handling

5. **test-term.sh** - Terminal access tests
   - SSH connections
   - Command execution
   - Repository environments
   - Docker integration
   - Special character handling

6. **run-all-tests.sh** - Master test runner
   - Runs all test suites in order
   - Aggregates results
   - Provides overall summary

## Running Tests

### Run All Tests
```bash
./run-all-tests.sh <TOKEN>
# or with env var
export REDIACC_TOKEN=your-token
./run-all-tests.sh
```

### Run Individual Test Suites
```bash
# Core functionality (can run without token)
./test-core.sh [TOKEN]

# API tests (requires token)
./test-api.sh <TOKEN>

# Sync tests (requires token and test infrastructure)
./test-sync.sh <TOKEN>

# Terminal tests (requires token and test infrastructure)
./test-term.sh <TOKEN>
```

## Test Requirements

- **Token**: Valid Rediacc API token (via parameter or REDIACC_TOKEN env var)
- **Test Infrastructure**: Some tests require:
  - Test team (default: "Default")
  - Test machine (default: "test-machine")
  - Test repository (default: "test-repo")

## Environment Variables

- `REDIACC_TOKEN` - API token for authentication
- `TEST_TEAM` - Team to use for tests (default: "Default")
- `TEST_MACHINE` - Machine to use for tests (default: "test-machine")
- `TEST_REPO` - Repository to use for tests (default: "test-repo")
- `TEST_TIMEOUT` - Timeout for operations (default: 30 seconds)

## Test Output

Tests use colored output for clarity:
- ✓ Green - Test passed
- ✗ Red - Test failed  
- ⚠ Yellow - Test skipped/warning
- ℹ Blue - Information

Each test suite provides:
- Individual test results
- Summary of passed/failed tests
- Clear error messages for failures

## Cleaning Up Old Tests

To remove the old redundant test files after migration:
```bash
./cleanup-old-tests.sh
```

This will show which files will be removed and ask for confirmation.

## Benefits of Simplification

1. **Reduced Maintenance** - Fewer files to update when APIs change
2. **Faster Execution** - Eliminated duplicate tests
3. **Clearer Purpose** - Each test file has a specific focus
4. **Better Reliability** - Less dependency on infrastructure
5. **Easier Debugging** - Simpler test logic and clearer output