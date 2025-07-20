# Rediacc CLI Test Framework

A comprehensive, cross-platform testing framework for the Rediacc CLI application that supports both YAML-based declarative tests and Python-based programmatic tests.

## Features

- **Declarative YAML Tests**: Simple, readable test definitions
- **Python-Based Tests**: Full programming power for complex scenarios
- **Dependency Resolution**: Automatically orders tests based on entity dependencies
- **Parallel Execution**: Run independent tests concurrently
- **Smart Cleanup**: Reverses creation order for proper resource cleanup
- **Cross-Platform**: Works on Windows, Linux, and macOS
- **Multiple Report Formats**: JSON, JUnit XML, HTML
- **Real API Testing**: All tests run against actual API endpoints
- **Comprehensive Fixtures**: Pre-created test resources

## Quick Start

### Running All Tests
```bash
# API URL is automatically detected from parent .env file
# Tests will create a new test company if no credentials provided
python -m tests_yaml.run

# Or provide existing credentials:
python -m tests_yaml.run --username 'email@example.com' --password 'password'
```

### Running Specific Test Suite
```bash
python -m tests_yaml.run --suite basic
python -m tests_yaml.run --suite complex
python -m tests_yaml.run --suite negative
```

### Running Single Test
```bash
python -m tests_yaml.run --test "Team CRUD Operations"
python -m tests_yaml.run --test tests/basic/test_team_crud.yaml
```

### Running Tests by Tag
```bash
python -m tests_yaml.run --tags integration queue
```

### Generate Reports
```bash
# JSON report
python -m tests_yaml.run --report json --output results.json

# JUnit XML (for CI integration)
python -m tests_yaml.run --report junit --output junit.xml

# HTML report
python -m tests_yaml.run --report html --output report.html
```

## Writing Tests

### YAML Test Format

Create a `.yaml` file in the `tests/` directory:

```yaml
name: "My Test Name"
description: "What this test does"
tags: [tag1, tag2]

dependencies:
  company: "TestCompany"  # Required entities

setup:
  - create_random_team_name: team_name  # Generate random values
  - set_var:
      api_key: "test-key-123"

steps:
  - action: create
    entity: team
    params:
      name: "{{ team_name }}"
      company: "{{ company }}"
    expect:
      success: true
    capture:
      team_id: "$.id"  # Capture response values

  - action: verify
    entity: team
    params:
      name: "{{ team_name }}"
    expect:
      company: "{{ company }}"

cleanup:
  - action: delete
    entity: team
    params:
      name: "{{ team_name }}"
```

### Python Test Format

Create a `.py` file in the `tests/` directory:

```python
from framework.base import BaseTest

class TestMyScenario(BaseTest):
    """Test description"""
    
    dependencies = ['company']
    tags = ['python', 'integration']
    
    async def test_my_scenario(self):
        # Create entities
        team = await self.create_entity('team',
            name=self.random_name('team'),
            company=self.context.get_var('company')
        )
        
        # Assertions
        self.assert_response_success(team)
        self.assert_equal(team['company'], self.context.get_var('company'))
        
        # Complex logic
        if team.get('vault_encrypted'):
            # Do something special
            pass
```

## Test Actions

### Available Actions

- **create**: Create a new entity
- **verify**: Verify entity exists and has expected properties  
- **update**: Update an existing entity
- **delete**: Delete an entity
- **wait**: Wait for specified seconds

### Entity Types

- company
- user
- team
- region
- bridge
- machine
- repository
- storage
- schedule
- queue_item

## Test Suites

### Basic Tests
Located in `tests/basic/`, these cover fundamental CRUD operations:

- **test_team_crud.yaml**: Team create, read, update, delete operations
- **test_region_crud.yaml**: Region management
- **test_bridge_crud.yaml**: Bridge operations within regions
- **test_machine_creation.yaml**: Machine provisioning and management
- **test_repository_crud.yaml**: Repository lifecycle management
- **test_storage_crud.yaml**: Storage configuration
- **test_schedule_crud.yaml**: Schedule management
- **test_user_management.yaml**: User creation and management
- **test_vault_operations.yaml**: Vault get/set for all entity types
- **test_permission_management.yaml**: Permission groups and user permissions
- **test_queue_operations.yaml**: Queue operations, priorities, and filters

### Complex Tests
Located in `tests/complex/`, these test multi-step workflows:

- **test_infrastructure_deployment.yaml**: Full infrastructure setup
- **test_parallel_operations.yaml**: Concurrent operation testing

### Negative Tests
Located in `tests/negative/`, these test error handling:

- **test_invalid_operations.yaml**: Invalid inputs and error conditions

## Variable Interpolation

Use `{{ variable_name }}` syntax to reference variables:

```yaml
steps:
  - action: create
    entity: machine
    params:
      name: "{{ machine_name }}"
      team: "{{ team_name }}"
      bridge: "{{ bridge_name }}"
```

## Capture and Reuse Values

Capture values from responses:

```yaml
- action: create
  entity: team
  params:
    name: "test_team"
  capture:
    team_id: "$.id"
    team_name: "$.name"

- action: create
  entity: machine
  params:
    name: "test_machine"
    team_id: "{{ team_id }}"  # Use captured value
```

## Parallel Execution

Mark steps or tests that can run in parallel:

```yaml
steps:
  - action: create
    entity: team
    params:
      name: "team1"
    parallel: true

  - action: create
    entity: team
    params:
      name: "team2"
    parallel: true
```

## Configuration

### Environment Variables

- `TEST_API_URL`: API endpoint to test against
- `TEST_USERNAME`: Username for authentication
- `TEST_PASSWORD`: Password for authentication
- `TEST_MASTER_PASSWORD`: Master password for vault encryption

### Configuration File

Create `config.yaml`:

```yaml
test_config:
  api_url: "https://api.rediacc.com"
  timeout: 30
  retry_count: 3
  parallel_workers: 4
  
auth:
  username: "test@example.com"
  password: "${TEST_PASSWORD}"
  
defaults:
  company: "TestCompany"
  region: "us-east-1"
```

## Advanced Features

### Retry Logic

```yaml
- action: verify
  entity: queue_item
  params:
    task_id: "{{ task_id }}"
  expect:
    status: "COMPLETED"
  retry: 10  # Retry up to 10 times
  timeout: 60  # Total timeout in seconds
```

### Conditional Logic (Python Tests)

```python
async def test_conditional(self):
    result = await self.cli.get('machine', 'test-machine')
    
    if result.get('status') == 'active':
        # Do active machine tests
        pass
    else:
        # Do inactive machine tests
        pass
```

### Bulk Operations

```python
async def test_bulk_create(self):
    # Create 100 machines in parallel
    tasks = []
    for i in range(100):
        task = self.create_entity('machine',
            name=f'machine_{i:03d}',
            team='bulk_team',
            bridge='bulk_bridge'
        )
        tasks.append(task)
    
    machines = await asyncio.gather(*tasks)
```

## Debugging

### Verbose Mode
```bash
python -m tests_yaml.run --verbose
```

### Keep Resources on Failure
```bash
python -m tests_yaml.run --keep-on-failure
```

### List Available Tests
```bash
python -m tests_yaml.run --list-tests
```

### API Configuration

The test framework automatically uses the API configuration from the parent `.env` file:
- `SYSTEM_DOMAIN`: API domain (defaults to localhost)
- `SYSTEM_HTTP_PORT`: API port (defaults to 7322)
- `REDIACC_API_URL`: Full API URL (overrides domain/port if set)

For remote APIs, set `SYSTEM_DOMAIN` in your `.env` file:
```bash
SYSTEM_DOMAIN=api.yourcompany.com
```

## CI/CD Integration

### GitHub Actions Example

```yaml
- name: Run Rediacc CLI Tests
  env:
    TEST_API_URL: ${{ secrets.REDIACC_API_URL }}
    TEST_USERNAME: ${{ secrets.REDIACC_USERNAME }}
    TEST_PASSWORD: ${{ secrets.REDIACC_PASSWORD }}
  run: |
    python -m tests_yaml.run --suite integration --report junit --output junit.xml
    
- name: Publish Test Results
  uses: EnricoMi/publish-unit-test-result-action@v2
  if: always()
  with:
    files: junit.xml
```

### Jenkins Example

```groovy
stage('Test') {
    steps {
        sh 'python -m tests_yaml.run --report junit --output results.xml'
    }
    post {
        always {
            junit 'results.xml'
        }
    }
}
```

## Best Practices

1. **Use Unique Names**: Always use random names to avoid conflicts
   ```yaml
   setup:
     - create_random_team_name: team_name
   ```

2. **Clean Up Resources**: Always define cleanup steps
   ```yaml
   cleanup:
     - action: delete
       entity: team
       params:
         name: "{{ team_name }}"
   ```

3. **Test Isolation**: Each test should be independent
4. **Meaningful Assertions**: Check both success and data integrity
5. **Use Tags**: Tag tests for easy filtering
6. **Performance Monitoring**: Track slow tests and optimize

## Troubleshooting

### Common Issues

1. **Authentication Failures**
   - Check TEST_USERNAME and TEST_PASSWORD environment variables
   - Verify API_URL is correct
   - Check network connectivity

2. **Dependency Errors**
   - Ensure required entities exist
   - Check entity relationships are correct
   - Verify cleanup didn't remove dependencies

3. **Timeout Errors**
   - Increase timeout values
   - Check if API is responsive
   - Verify queue jobs are being processed

4. **Cleanup Failures**
   - Use --no-cleanup to skip cleanup
   - Manually clean up resources if needed
   - Check for dependency violations

## Architecture

See [ARCHITECTURE.md](ARCHITECTURE.md) for detailed framework design.

## Contributing

1. Add new test scenarios in appropriate directories
2. Follow existing naming conventions
3. Include both positive and negative test cases
4. Document any new features or actions
5. Run full test suite before submitting