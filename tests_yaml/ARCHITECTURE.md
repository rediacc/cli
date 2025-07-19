# Rediacc CLI Test Framework Architecture

## Overview

This testing framework provides a comprehensive, cross-platform solution for testing the Rediacc CLI application. It supports both YAML-based declarative tests and Python-based programmatic tests, with automatic dependency resolution, parallel execution, and intelligent cleanup.

## Design Principles

1. **Minimal Dependencies**: Uses only Python stdlib where possible
2. **Cross-Platform**: Works on Windows, Linux, and macOS
3. **Declarative First**: YAML for simple tests, Python for complex scenarios
4. **Dependency Aware**: Automatically orders tests based on entity dependencies
5. **Parallel Where Possible**: Runs independent tests concurrently
6. **Smart Cleanup**: Reverses creation order for proper cleanup
7. **Comprehensive Reporting**: Detailed logs, metrics, and reports

## Architecture Components

### 1. Core Framework (`framework/`)

#### `base.py` - Base Classes
- `TestContext`: Manages test state, variables, and authentication
- `TestStep`: Individual test operation (create, verify, delete)
- `TestScenario`: Collection of steps forming a complete test
- `TestResult`: Detailed result tracking with metrics

#### `runner.py` - Test Execution
- `TestRunner`: Main test executor with dependency resolution
- `DependencyResolver`: Analyzes and orders tests based on entity hierarchy
- `ParallelExecutor`: Runs independent tests concurrently
- `CleanupManager`: Ensures proper cleanup in reverse order

#### `entities.py` - Entity Management
- DTO classes for each entity type (Company, Team, Machine, etc.)
- Validation logic for entity relationships
- Dependency tracking between entities
- State management for created resources

#### `cli_wrapper.py` - CLI Integration
- `CLIWrapper`: Wraps rediacc-cli.py for testing
- Handles JSON output parsing
- Manages authentication tokens
- Provides mock mode for unit tests

### 2. Test Definitions (`tests/`)

#### YAML Test Format
```yaml
name: "Create Team with Custom Vault"
description: "Tests team creation with encrypted vault data"
tags: [team, vault, integration]
dependencies:
  - company: default
setup:
  - create_random_team_name: team_name
steps:
  - action: create
    entity: team
    params:
      name: "{{ team_name }}"
      company: "{{ company }}"
      vault:
        custom_key: "secret_value"
    expect:
      status: success
      response:
        name: "{{ team_name }}"
    capture:
      team_id: "$.id"
  - action: verify
    entity: team
    params:
      name: "{{ team_name }}"
    expect:
      vault_encrypted: true
cleanup:
  - action: delete
    entity: team
    params:
      name: "{{ team_name }}"
```

#### Python Test Format
```python
class TestComplexWorkflow(BaseTest):
    """Tests a complete infrastructure deployment workflow"""
    
    dependencies = ['company', 'region']
    
    async def test_deploy_infrastructure(self):
        # Create team
        team = await self.create_entity('team', name=self.random_name('team'))
        
        # Create bridge and machine in parallel
        bridge, machine = await asyncio.gather(
            self.create_entity('bridge', region=self.region, name=self.random_name('bridge')),
            self.create_entity('machine', team=team.name, name=self.random_name('machine'))
        )
        
        # Create repository
        repo = await self.create_entity('repository', 
            team=team.name, 
            machine=machine.name,
            name=self.random_name('repo')
        )
        
        # Submit queue job
        job = await self.create_queue_item(
            team=team.name,
            machine=machine.name,
            function='create_repository',
            params={'repository': repo.name}
        )
        
        # Wait for completion
        result = await self.wait_for_queue_item(job.id, timeout=300)
        assert result.status == 'COMPLETED'
```

### 3. Fixtures and Utilities (`fixtures/`)

#### `generators.py` - Test Data Generation
- Random name generators with prefixes
- Valid data generators for each entity type
- Invalid data for negative testing
- Bulk data generation for load testing

#### `fixtures.py` - Shared Test Resources
- Pre-created entities for faster tests
- Authentication tokens
- Common configuration values
- Mock data for unit tests

### 4. Entity Dependency Graph

```
Company
├── Teams
│   ├── Machines (requires Bridge)
│   │   └── Repositories
│   │       └── Queue Items
│   ├── Storages
│   └── Schedules
├── Regions
│   └── Bridges
└── Users
```

## Key Features

### 1. Dependency Resolution
- Automatically determines test execution order
- Creates required entities before dependent tests
- Parallelizes independent test branches
- Ensures cleanup happens in reverse dependency order

### 2. Variable Interpolation
- Supports `{{ variable }}` syntax in YAML
- Variables cascade through test steps
- Can reference previous step outputs
- Environment variable support

### 3. Parallel Execution
- Identifies independent test paths
- Uses Python asyncio for concurrent execution
- Configurable parallelism level
- Thread-safe result collection

### 4. Smart Cleanup
- Tracks all created resources
- Cleans up in reverse creation order
- Handles partial test failures
- Optional keep-on-failure mode

### 5. Comprehensive Reporting
- Real-time progress updates
- Detailed error logs with context
- Performance metrics per operation
- HTML and JSON report formats
- JUnit XML for CI integration

## Test Categories

### 1. Unit Tests
- Test individual CLI commands
- Mock API responses
- Validate input parsing
- Test error handling

### 2. Integration Tests
- Real API interactions
- Full entity lifecycle
- Cross-entity relationships
- End-to-end workflows

### 3. Performance Tests
- Bulk operations
- Concurrent requests
- Response time tracking
- Resource usage monitoring

### 4. Negative Tests
- Invalid inputs
- Permission errors
- Network failures
- Malformed responses

## Usage Examples

### Running All Tests
```bash
python -m tests_yaml.run
```

### Running Specific Test Suite
```bash
python -m tests_yaml.run --suite integration
```

### Running Single Test
```bash
python -m tests_yaml.run --test test_create_team
```

### Parallel Execution
```bash
python -m tests_yaml.run --parallel 4
```

### Keep Failed Resources
```bash
python -m tests_yaml.run --keep-on-failure
```

### Generate Report
```bash
python -m tests_yaml.run --report html --output test-report.html
```

## Configuration

### `config.yaml`
```yaml
test_config:
  api_url: "https://api.rediacc.com"
  timeout: 30
  retry_count: 3
  parallel_workers: 4
  cleanup_on_exit: true
  
auth:
  username: "test@example.com"
  password: "${TEST_PASSWORD}"
  
defaults:
  company: "TestCompany"
  region: "us-east-1"
```

## Best Practices

1. **Test Isolation**: Each test should be independent
2. **Unique Names**: Use random generators to avoid conflicts
3. **Proper Cleanup**: Always define cleanup steps
4. **Meaningful Assertions**: Check both success and data integrity
5. **Error Context**: Include relevant data in test failures
6. **Performance Tracking**: Monitor test execution times

## Extension Points

1. **Custom Actions**: Add new test actions in `framework/actions.py`
2. **Entity Types**: Extend `entities.py` for new resource types
3. **Reporters**: Create custom report formats in `framework/reporters.py`
4. **Validators**: Add custom validation logic in `framework/validators.py`