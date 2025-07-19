# Rediacc CLI Test Framework

## Quick Start

```bash
cd ~/monorepo/cli
python3 -m tests_yaml.run --mock --suite basic
```

**Note**: Always use `--mock` flag for testing. Real API testing requires creating test companies.

### Real API Testing

1. **Create Test Company** (generates unique credentials):
```bash
python3 tests_yaml/setup_test_company.py
# Outputs: email and password
```

2. **Run Tests with Credentials**:
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
│   ├── cli_wrapper.py # CLI integration
│   ├── mock_handler.py # Mock responses
│   └── mock_config.json # Entity definitions
├── tests/             # Test scenarios
│   ├── basic/         # CRUD operations
│   ├── complex/       # Multi-step workflows
│   └── negative/      # Error cases
└── run.py            # Main entry point
```

## Key Features

- **Hybrid Tests**: YAML (declarative) + Python (programmatic)
- **Auto Dependencies**: Tests run in correct order based on entity relationships
- **Smart Mocking**: JSON-configured mock responses, no real API needed
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
# Run all tests
python3 -m tests_yaml.run --mock

# Specific suite
python3 -m tests_yaml.run --mock --suite basic

# Single test
python3 -m tests_yaml.run --mock --test "Team CRUD Operations"

# List tests
python3 -m tests_yaml.run --mock --list-tests

# Generate report
python3 -m tests_yaml.run --mock --report html --output report.html
```

## Mock Configuration

Edit `framework/mock_config.json` to:
- Add new entity types
- Define required fields
- Set default values
- Configure error responses

## Tips

1. Use `--mock` for fast local testing
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
- **Easy extension**: Add entities via JSON
- **Clean separation**: Mock logic isolated from CLI wrapper