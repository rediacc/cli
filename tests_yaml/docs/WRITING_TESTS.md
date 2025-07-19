# Writing Tests for Rediacc CLI

This guide provides detailed instructions on how to write effective tests for the Rediacc CLI using our test framework.

## Table of Contents

1. [Choosing Between YAML and Python](#choosing-between-yaml-and-python)
2. [YAML Test Structure](#yaml-test-structure)
3. [Python Test Structure](#python-test-structure)
4. [Variable Management](#variable-management)
5. [Entity Dependencies](#entity-dependencies)
6. [Assertions and Expectations](#assertions-and-expectations)
7. [Error Handling](#error-handling)
8. [Performance Testing](#performance-testing)
9. [Test Data Generation](#test-data-generation)
10. [Best Practices](#best-practices)

## Choosing Between YAML and Python

### Use YAML Tests When:
- Testing straightforward CRUD operations
- Following a linear workflow
- No complex conditional logic needed
- Want readable, declarative tests
- Testing can be expressed as a sequence of actions

### Use Python Tests When:
- Need conditional logic or loops
- Require complex data transformations
- Testing async operations or timing-sensitive scenarios
- Need to test error recovery or retry logic
- Want to reuse code across multiple test methods

## YAML Test Structure

### Complete Example

```yaml
# Metadata
name: "Repository Sync Test"
description: "Test syncing repositories between machines"
tags: [repository, sync, integration]

# Required entities that must exist
dependencies:
  company: "TestCompany"
  region: "us-east-1"

# Setup phase - prepare test data
setup:
  # Generate random names
  - create_random_team_name: team_name
  - create_random_repository_name: repo_name
  
  # Set static variables
  - set_var:
      source_machine: "source-server"
      target_machine: "target-server"
      sync_interval: 300

# Main test steps
steps:
  # Create infrastructure
  - action: create
    entity: team
    params:
      name: "{{ team_name }}"
      company: "{{ company }}"
      vault:
        SSH_PRIVATE_KEY: "test-key"
    expect:
      success: true
    capture:
      team_id: "$.id"

  # Create source repository
  - action: create
    entity: repository
    params:
      name: "{{ repo_name }}"
      team: "{{ team_name }}"
      machine: "{{ source_machine }}"
      repo_type: "git"
      url: "https://github.com/example/app.git"
    capture:
      repo_id: "$.id"

  # Submit sync job
  - action: create
    entity: queue_item
    params:
      team: "{{ team_name }}"
      machine: "{{ target_machine }}"
      function: "sync_repository"
      priority: 2
      vault:
        source_repo: "{{ repo_name }}"
        source_machine: "{{ source_machine }}"
        sync_type: "mirror"
    capture:
      task_id: "$.taskId"

  # Wait and verify
  - action: wait
    params:
      seconds: 10

  - action: verify
    entity: queue_item
    params:
      task_id: "{{ task_id }}"
    expect:
      status: "COMPLETED"
    retry: 5
    timeout: 60

# Cleanup phase - runs even if test fails
cleanup:
  - action: delete
    entity: repository
    params:
      name: "{{ repo_name }}"
      
  - action: delete
    entity: team
    params:
      name: "{{ team_name }}"

# Optional settings
settings:
  parallel: false  # Don't run this test in parallel
  skip_cleanup: false  # Always run cleanup
  timeout: 600  # Overall test timeout in seconds
```

### Action Types

#### create
```yaml
- action: create
  entity: machine
  params:
    name: "prod-server-01"
    team: "production"
    bridge: "us-east-bridge"
    vault:
      ip: "10.0.1.50"
      user: "deploy"
  expect:
    success: true
  capture:
    machine_id: "$.id"
    machine_ip: "$.vault.ip"
```

#### verify
```yaml
- action: verify
  entity: machine
  params:
    name: "prod-server-01"
  expect:
    team: "production"
    status: "active"
    vault_encrypted: true
  retry: 3  # Retry up to 3 times
  timeout: 30  # Total timeout
```

#### update
```yaml
- action: update
  entity: team
  params:
    name: "dev-team"
    vault:
      NEW_KEY: "new-value"
      UPDATED_KEY: "updated-value"
  expect:
    success: true
```

#### delete
```yaml
- action: delete
  entity: machine
  params:
    name: "old-server"
  expect:
    success: true
```

#### wait
```yaml
- action: wait
  params:
    seconds: 30  # Wait 30 seconds
```

## Python Test Structure

### Complete Example

```python
import asyncio
from typing import List, Dict, Any
import time

from framework.base import BaseTest


class TestRepositoryManagement(BaseTest):
    """
    Test repository creation, management, and synchronization.
    """
    
    # Test configuration
    dependencies = ['company', 'region']
    tags = ['repository', 'python', 'integration']
    timeout = 900  # 15 minutes
    parallel = True  # Can run in parallel with other tests
    
    async def setup(self):
        """Setup method called before test execution"""
        # Create shared infrastructure
        self.team = await self.create_entity('team',
            name=self.random_name('repo_team'),
            company=self.context.get_var('company'),
            vault={
                'SSH_PRIVATE_KEY': self.generate_ssh_key(),
                'GIT_TOKEN': 'test-token-123'
            }
        )
        
        self.region = await self.create_entity('region',
            name=self.random_name('repo_region'),
            company=self.context.get_var('company')
        )
        
        self.bridge = await self.create_entity('bridge',
            name=self.random_name('repo_bridge'),
            region=self.region['name']
        )
    
    async def test_repository_lifecycle(self):
        """Test complete repository lifecycle"""
        
        # Create machine
        machine = await self.create_entity('machine',
            name=self.random_name('repo_machine'),
            team=self.team['name'],
            bridge=self.bridge['name'],
            vault={
                'ip': '10.0.2.100',
                'user': 'git',
                'datastore': '/var/repos'
            }
        )
        
        # Create multiple repositories
        repos = []
        for i in range(5):
            repo = await self.create_entity('repository',
                name=self.random_name(f'repo_{i}'),
                team=self.team['name'],
                machine=machine['name'],
                repo_type='git',
                url=f'https://github.com/example/app{i}.git'
            )
            repos.append(repo)
        
        # Verify all created successfully
        for repo in repos:
            self.assert_response_success(repo)
            self.assert_equal(repo['machine'], machine['name'])
        
        # Test bulk operations
        await self._test_bulk_sync(repos, machine)
        
        # Test error scenarios
        await self._test_error_handling(machine)
    
    async def _test_bulk_sync(self, repos: List[Dict[str, Any]], 
                              machine: Dict[str, Any]):
        """Test syncing multiple repositories"""
        
        # Create target machine
        target_machine = await self.create_entity('machine',
            name=self.random_name('sync_target'),
            team=self.team['name'],
            bridge=self.bridge['name'],
            vault={
                'ip': '10.0.2.101',
                'user': 'git',
                'datastore': '/var/repos_mirror'
            }
        )
        
        # Submit sync jobs for all repos
        sync_jobs = []
        for repo in repos:
            job = await self.cli.create_queue_item(
                team=self.team['name'],
                machine=target_machine['name'],
                function='sync_repository',
                priority=2,
                vault={
                    'source_repo': repo['name'],
                    'source_machine': machine['name'],
                    'sync_mode': 'mirror'
                }
            )
            sync_jobs.append(job)
        
        # Monitor all jobs
        completed = await self._wait_for_jobs(sync_jobs, timeout=300)
        
        # Verify results
        self.assert_equal(len(completed), len(sync_jobs),
                         "All sync jobs should complete")
        
        for job in completed:
            self.assert_equal(job['status'], 'COMPLETED')
    
    async def _test_error_handling(self, machine: Dict[str, Any]):
        """Test error scenarios"""
        
        # Test creating repo with invalid data
        with self.assertRaises(AssertionError):
            await self.create_entity('repository',
                name='',  # Empty name
                team=self.team['name'],
                machine=machine['name']
            )
        
        # Test creating repo on non-existent machine
        result = await self.cli.create('repository',
            name=self.random_name('orphan_repo'),
            team=self.team['name'],
            machine='non_existent_machine',
            repo_type='git'
        )
        
        self.assert_equal(result.get('success'), False)
        self.assert_in('not found', result.get('error', '').lower())
    
    async def _wait_for_jobs(self, jobs: List[Dict[str, Any]], 
                            timeout: int = 300) -> List[Dict[str, Any]]:
        """Wait for multiple queue jobs to complete"""
        
        start_time = time.time()
        completed = []
        pending = jobs.copy()
        
        while pending and time.time() - start_time < timeout:
            # Check status of all pending jobs
            for job in pending[:]:  # Copy to allow removal
                status = await self.cli.get_queue_status(job['taskId'])
                
                if status.get('status') in ['COMPLETED', 'FAILED']:
                    completed.append(status)
                    pending.remove(job)
                    
                    self.logger.info(
                        f"Job {job['taskId']} finished: {status.get('status')}"
                    )
            
            if pending:
                await self._sleep(5)
        
        if pending:
            self.logger.warning(f"{len(pending)} jobs did not complete in time")
        
        return completed
    
    def generate_ssh_key(self) -> str:
        """Generate test SSH key"""
        return """-----BEGIN RSA PRIVATE KEY-----
MIIEpAIBAAKCAQEA0Z3VS5JJcds...test...
-----END RSA PRIVATE KEY-----"""
    
    async def teardown(self):
        """Custom teardown logic"""
        # The base class handles cleanup of created entities
        await super().teardown()
        
        # Any additional cleanup
        self.logger.info("Repository tests cleanup completed")
```

## Variable Management

### YAML Variables

#### Setting Variables
```yaml
setup:
  # Random generation
  - create_random_team_name: team_var
  - create_random_machine_name: machine_var
  
  # Static values
  - set_var:
      environment: "staging"
      timeout: 300
      config:
        feature_flags:
          - "new_ui"
          - "async_processing"
```

#### Using Variables
```yaml
steps:
  - action: create
    entity: team
    params:
      name: "{{ team_var }}"
      vault:
        ENVIRONMENT: "{{ environment }}"
        TIMEOUT: "{{ timeout }}"
        FLAGS: "{{ config.feature_flags }}"
```

### Python Variables

```python
async def test_variables(self):
    # Set context variables
    self.context.set_var('environment', 'production')
    self.context.set_var('region', 'us-west-2')
    
    # Get variables
    env = self.context.get_var('environment')
    region = self.context.get_var('region', default='us-east-1')
    
    # Use in entity creation
    team = await self.create_entity('team',
        name=self.random_name('team'),
        company=self.context.get_var('company'),
        vault={
            'ENVIRONMENT': env,
            'REGION': region
        }
    )
```

## Entity Dependencies

### Dependency Hierarchy
```
Company
├── Teams
│   ├── Machines (also needs Bridge)
│   │   └── Repositories
│   │       └── Queue Items
│   ├── Storages
│   └── Schedules
├── Regions
│   └── Bridges
└── Users
```

### YAML Dependencies
```yaml
dependencies:
  company: "TestCompany"
  region: "us-east-1"

steps:
  # These use the pre-existing dependencies
  - action: create
    entity: bridge
    params:
      name: "new-bridge"
      region: "{{ region }}"  # Uses dependency
```

### Python Dependencies
```python
class TestWithDependencies(BaseTest):
    dependencies = ['company', 'region', 'team']
    
    async def test_something(self):
        # Dependencies are available in context
        company = self.context.get_var('company')
        region = self.context.get_var('region')
        team = self.context.get_var('team')
```

## Assertions and Expectations

### YAML Expectations

#### Basic Expectations
```yaml
- action: create
  entity: team
  params:
    name: "test-team"
  expect:
    success: true
    name: "test-team"
```

#### Advanced Expectations
```yaml
- action: verify
  entity: queue_item
  params:
    task_id: "{{ task_id }}"
  expect:
    status_in: ["COMPLETED", "PROCESSING"]  # One of these values
    result_contains: "success"  # Substring match
    duration_less_than: 300  # Numeric comparison
```

### Python Assertions

```python
# Basic assertions
self.assert_equal(actual, expected, "Custom message")
self.assert_in(item, container)
self.assert_response_success(response)

# Custom assertions
assert response['duration'] < 300, f"Too slow: {response['duration']}s"
assert 'error' not in response, f"Unexpected error: {response.get('error')}"

# Using Python's assert
assert len(results) > 0, "No results returned"
assert all(r['status'] == 'active' for r in results), "Not all active"
```

## Error Handling

### YAML Error Testing
```yaml
# Test expected failures
- action: create
  entity: machine
  params:
    name: "invalid-machine"
    team: "non-existent-team"
    bridge: "non-existent-bridge"
  expect:
    success: false
    error_contains: "not found"
```

### Python Error Testing
```python
async def test_error_scenarios(self):
    # Test with context manager
    with self.assertRaises(ValueError):
        await self.create_entity('team', name='')
    
    # Test and examine error
    try:
        result = await self.cli.create('machine',
            name='test',
            team='invalid'
        )
        self.fail("Should have failed")
    except Exception as e:
        self.assert_in('not found', str(e).lower())
    
    # Test API errors
    result = await self.cli.delete('team', 'non-existent')
    self.assert_equal(result['success'], False)
    self.logger.info(f"Expected error: {result['error']}")
```

## Performance Testing

### YAML Performance Tests
```yaml
name: "Bulk Creation Performance"
steps:
  # Create many entities
  - action: create
    entity: team
    params:
      name: "perf_team_{{ index }}"
      company: "{{ company }}"
    repeat: 100  # Create 100 teams
    parallel: true
    expect:
      success: true
    capture_all: teams  # Capture all results

  # Verify performance
  - action: verify_performance
    metrics:
      total_duration_less_than: 60  # Should complete in 60s
      average_duration_less_than: 2  # Each should take < 2s
```

### Python Performance Tests
```python
async def test_performance(self):
    """Test system performance under load"""
    
    import statistics
    
    # Measure creation times
    creation_times = []
    
    for i in range(100):
        start = time.time()
        
        team = await self.create_entity('team',
            name=f'perf_team_{i:03d}',
            company=self.context.get_var('company')
        )
        
        duration = time.time() - start
        creation_times.append(duration)
    
    # Analyze performance
    avg_time = statistics.mean(creation_times)
    max_time = max(creation_times)
    p95_time = sorted(creation_times)[int(len(creation_times) * 0.95)]
    
    self.logger.info(f"Performance: avg={avg_time:.2f}s, "
                    f"max={max_time:.2f}s, p95={p95_time:.2f}s")
    
    # Assert performance requirements
    assert avg_time < 1.0, f"Average too slow: {avg_time:.2f}s"
    assert p95_time < 2.0, f"P95 too slow: {p95_time:.2f}s"
```

## Test Data Generation

### Using Data Generators

```python
from framework.generators import DataGenerator

async def test_with_generated_data(self):
    generator = DataGenerator()
    
    # Generate valid data
    team_data = generator.generate_team(
        company=self.context.get_var('company')
    )
    team = await self.create_entity('team', **team_data)
    
    # Generate bulk data
    machines_data = generator.generate_bulk_data(
        'machine',
        count=10,
        team=team['name'],
        bridge=self.bridge['name']
    )
    
    # Generate invalid data for negative testing
    invalid_data = generator.generate_invalid_data('team')
    for data in invalid_data:
        result = await self.cli.create('team', **data)
        self.assert_equal(result['success'], False)
```

## Best Practices

### 1. Test Naming
- Use descriptive names that explain what is being tested
- Include the entity type and operation
- Examples:
  - "Team CRUD Operations"
  - "Machine Creation with Dependencies"
  - "Queue Job Timeout Handling"

### 2. Test Organization
```
tests/
├── basic/           # Simple CRUD operations
├── complex/         # Multi-step workflows
├── negative/        # Error cases and validation
├── performance/     # Load and performance tests
└── integration/     # Full system integration tests
```

### 3. Resource Cleanup
- Always define cleanup steps
- Use unique names to avoid conflicts
- Test cleanup in isolation:
  ```yaml
  cleanup:
    - action: delete
      entity: machine
      params:
        name: "{{ machine_name }}"
      continue_on_error: true  # Don't fail if already deleted
  ```

### 4. Idempotency
- Tests should produce same results when run multiple times
- Use random names for all created resources
- Don't depend on external state

### 5. Error Messages
- Provide clear error messages in assertions
- Include actual vs expected values
- Add context about what was being tested

### 6. Test Independence
- Each test should be completely independent
- Don't rely on side effects from other tests
- Use fixtures for shared setup

### 7. Timeout Handling
```python
# Set appropriate timeouts
async def test_long_operation(self):
    # Use wait_for_condition with timeout
    await self.wait_for_condition(
        lambda: self._check_status(task_id),
        timeout=300,  # 5 minutes
        interval=10   # Check every 10 seconds
    )
```

### 8. Logging
```python
# Add helpful log messages
self.logger.info(f"Creating {count} machines")
self.logger.debug(f"Machine data: {machine_data}")
self.logger.warning(f"Retry attempt {attempt}/{max_retries}")
self.logger.error(f"Unexpected response: {response}")
```

### 9. Mock vs Real Tests
- Use mock mode for unit tests
- Use real API for integration tests
- Structure tests to work in both modes when possible

### 10. Documentation
- Add docstrings to Python test methods
- Add descriptions to YAML tests
- Document any special requirements or setup
- Include examples of expected output