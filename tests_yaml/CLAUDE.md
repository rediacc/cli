# Rediacc CLI Test Framework

## Quick Start

### Real API Testing

The test framework requires real API connections and automatically uses the API configuration from your `.env` file:

```bash
# The framework uses SYSTEM_DOMAIN from parent .env file
# API URL is constructed as:
#   - http://localhost:7322/api (for localhost)
#   - https://yourdomain.com/api (for other domains)

cd ~/monorepo/cli
python3 -m tests_yaml.run --suite basic
```

### Authentication Options

1. **Create Test Company** (automatic if no credentials provided):
```bash
python3 tests_yaml/setup_test_company.py
# Outputs: email and password
```

2. **Run Tests with Existing Credentials**:
```bash
# Option 1: Command line args
python3 -m tests_yaml.run --suite basic --username 'test_123@example.com' --password 'TestPass123!'

# Option 2: Environment variables
export REDIACC_TEST_USERNAME='test_123@example.com'
export REDIACC_TEST_PASSWORD='TestPass123!'
python3 -m tests_yaml.run --suite basic
```

3. **Parallel Testing** (each with unique company):
```bash
./tests_yaml/run_parallel_tests.sh
```

## Architecture

```
tests_yaml/
├── framework/          # Core testing engine
│   ├── base.py        # TestContext, TestScenario, TestResult
│   ├── runner.py      # Test execution & dependency resolution
│   ├── entities.py    # Entity DTOs & relationships
│   └── cli_wrapper.py # CLI integration
├── tests/             # Test scenarios
│   ├── basic/         # CRUD operations
│   ├── complex/       # Multi-step workflows
│   └── negative/      # Error cases
└── run.py            # Main entry point
```

## Key Features

- **Hybrid Tests**: YAML (declarative) + Python (programmatic)
- **Auto Dependencies**: Tests run in correct order based on entity relationships
- **Real API Testing**: All tests run against actual API endpoints
- **Parallel Execution**: Independent tests run concurrently
- **Auto Cleanup**: Resources deleted in reverse order

## Entity Hierarchy

```
Company → Teams → Machines (needs Bridge) → Repositories
        → Regions → Bridges
        → Users
```

## Writing Tests

### YAML Test
```yaml
name: "Create Team"
steps:
  - action: create
    entity: team
    params:
      name: "{{ team_name }}"
    expect:
      success: true
cleanup:
  - action: delete
    entity: team
    params:
      name: "{{ team_name }}"
```

### Python Test
```python
class TestWorkflow(BaseTest):
    async def test_create_infrastructure(self):
        team = await self.create_entity('team', name=self.random_name('team'))
        self.assert_response_success(team)
```

## Commands

```bash
# Run all tests (requires credentials)
python3 -m tests_yaml.run --username 'test@example.com' --password 'password'

# Specific suite
python3 -m tests_yaml.run --suite basic --username 'test@example.com' --password 'password'

# Single test
python3 -m tests_yaml.run --test "Team CRUD Operations" --username 'test@example.com' --password 'password'

# List tests
python3 -m tests_yaml.run --list-tests

# Generate report
python3 -m tests_yaml.run --report html --output report.html --username 'test@example.com' --password 'password'
```


## Tips

1. API URL is automatically detected from `.env` file
2. Tests auto-cleanup unless `--keep-on-failure`
3. Variable interpolation: `{{ var_name }}`
4. Capture values: `capture: { team_id: "$.id" }`
5. All entities need unique names (use `random_name()`)

## Common Issues

- **Import errors**: Run from `~/monorepo/cli` directory
- **Test failures**: Check entity dependencies exist
- **Cleanup errors**: Some entities may already be deleted

## Architecture Benefits

- **Minimal dependencies**: Python stdlib only
- **Cross-platform**: Windows, Linux, macOS
- **Real API testing**: Validates actual API behavior
- **Clean separation**: Test logic isolated from CLI wrapper