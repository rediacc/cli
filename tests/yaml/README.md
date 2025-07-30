# Rediacc CLI YAML Test Suite

This directory contains YAML-based tests for the Rediacc CLI, organized by subscription plan tiers.

## Directory Structure

```
yaml/
├── config.yaml           # Test configuration with variables
├── basic/               # Tests for Community/Basic features
├── advanced/            # Tests for Advanced plan features  
├── premium/             # Tests for Premium plan features (TBD)
└── elite/               # Tests for Elite plan features (TBD)
```

## Hierarchical Test Execution

Tests are organized hierarchically based on subscription plans:
- **basic**: Community edition features (free tier)
- **advanced**: Requires ADVANCED subscription or higher
- **premium**: Requires PREMIUM subscription or higher
- **elite**: Requires ELITE subscription

When running tests for a higher tier, all lower tier tests are automatically included:
- Running `advanced/*.yaml` executes basic tests first, then advanced
- Running `premium/*.yaml` executes basic, advanced, then premium tests
- Running `elite/*.yaml` executes all tiers in order

## Running Tests

```bash
# Run all basic tests
./run_tests.py "basic/*.yaml"

# Run specific test file
./run_tests.py "basic/00010_company_setup.yaml"

# Run advanced tests (includes basic)
./run_tests.py "advanced/*.yaml"

# Run all tests in all tiers
./run_tests.py
```

## Test Numbering Convention

Tests use a numbering scheme to control execution order:
- `00010_` - First test group
- `00020_` - Second test group
- `00030_` - Third test group
- `00031_` - Sub-test of third group
- `09999_` - Final cleanup tests

Sub-tests use decimal notation:
- `00031.1_` - First sub-test of test 31
- `00031.2_` - Second sub-test of test 31

## Basic Tests

1. **00010_company_setup.yaml** - Company creation and activation
2. **00020_team_management.yaml** - Team CRUD operations
3. **00030_user_management.yaml** - User creation and management
4. **00031_user_password_management.yaml** - Password updates
5. **00040_permission_management.yaml** - Basic permission operations
6. **09999_logout.yaml** - Cleanup and logout

## Advanced Tests

1. **00010.1_company_setup_advanced.yaml** - Create company with ADVANCED plan
2. **00031.2_user_tfa_management.yaml** - TFA documentation (manual testing)
3. **00040.1_permission_management_advanced.yaml** - Custom permission groups

## Test Features

- **Variable substitution**: Use `${config.variable}` or `${chain.variable}`
- **Chain context**: Share data between test files using `chain_export`
- **Automatic output capture**: Results saved to `test_results/` directory
- **Coverage reporting**: Tracks which CLI commands and API endpoints are tested
- **Stdin support**: For commands requiring input (e.g., vault operations)

## Writing New Tests

See individual test files for examples. Key elements:
- `name`: Test suite name
- `description`: What the test covers
- `tests`: Array of test steps
- `chain_export`: Variables to share with subsequent tests
- `expect`: Validation criteria (usually `success: true`)

## Notes

- Tests requiring interactive input (like TOTP for TFA) are documented but skipped
- Subscription plan testing requires development environment
- All tests use `--output json-full` for comprehensive result capture
- Tests stop on first failure to prevent cascading errors