# Workflow Tests

This directory contains automated tests for the Rediacc CLI workflow commands.

## Test Files

1. **test_01_discovery_and_connectivity.yaml** - Discovers available infrastructure and tests connectivity
2. **test_02_ssh_test.yaml** - Tests SSH access for bridge-only operations
3. **test_03_hello_test.yaml** - Simple function test on connected machines
4. **test_04_machine_setup.yaml** - Machine setup test (DESTRUCTIVE - skipped by default)
5. **test_05_repo_create.yaml** - Repository creation with success/failure scenarios
6. **test_06_repo_push.yaml** - Repository push operations including self-push

## Running the Tests

### Run All Workflow Tests
```bash
cd /home/muhammed/monorepo/cli
python3 -m tests_yaml.run --suite workflows --username admin@rediacc.io --password your_password
```

### Run Specific Test
```bash
python3 -m tests_yaml.run --test "SSH Test Workflow" --username admin@rediacc.io --password your_password
```

### Skip Destructive Tests
```bash
python3 -m tests_yaml.run --suite workflows --skip-tags destructive --username admin@rediacc.io --password your_password
```

## Test Dependencies

The tests are designed to work with the following infrastructure:
- Team: "Private Team"
- Machines: rediacc11, rediacc12
- Bridge: "Global Bridges"
- Hosts: 192.168.111.11, 192.168.111.12, 192.168.111.21

Tests will fail if required entities are missing.

## Important Notes

1. **Machine Setup Test** is skipped by default as it's destructive
2. **Repository tests** automatically clean up created resources
3. **All tests use JSON output** for better validation
4. **Tests are independent** - each can run standalone

## Test Results

Tests validate:
- Command completion status
- Expected output format
- Error scenarios (e.g., large repository creation failure)
- Cleanup of created resources

## Troubleshooting

If tests fail:
1. Check authentication credentials
2. Verify infrastructure exists (teams, machines, bridges)
3. Check available disk space for repository tests
4. Review test output for specific error messages