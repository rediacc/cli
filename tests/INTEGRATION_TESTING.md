# Integration Testing with Elite Backend

This document explains how the CLI integration tests work with the Elite backend services in CI/CD.

## Overview

The CLI integration tests now run against **real Rediacc Elite services** in GitHub Actions:

- **nginx** - Reverse proxy
- **api** - .NET Middleware
- **sql** - SQL Server 2022 Express

This enables comprehensive end-to-end testing that catches bugs unit tests can't find.

## Architecture

```
GitHub Actions Workflow
├── Unit Tests (pytest)                    # Fast, mocked
│   └── Tests CLI logic in isolation
│
└── Integration Tests (YAML tests)         # Comprehensive, real backend
    ├── Elite Action spins up services
    ├── CLI connects to http://localhost/api
    └── Tests execute real API calls
```

## How It Works

### 1. Elite Action Starts Services

The workflow uses the [Elite GitHub Action](../../cloud/elite/action/):

```yaml
- uses: ./monorepo/cloud/elite/action
  env:
    GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
    GITHUB_ACTOR: ${{ github.actor }}
```

This automatically:
- Pulls Elite Docker images
- Starts nginx, API, and SQL Server
- Waits for services to be healthy
- Exposes API at `http://localhost`

### 2. Integration Test Runner Executes

The `run_integration_ci.sh` script:

```bash
# Wait for API
timeout 60 bash -c 'until curl -f http://localhost/api/health; done'

# Run tests
python run_tests.py "yaml/community/01*.yaml"
```

### 3. Tests Make Real API Calls

YAML tests execute against live backend:

```yaml
# From yaml/community/01000_company.yaml
tests:
  - name: "Get company info"
    command: ["get", "company"]
    expect:
      success: true
```

This makes an actual HTTP request to `http://localhost/api` and validates the response.

## Running Integration Tests

### In CI (Automatic)

Integration tests run automatically on every push/PR to the CLI repo:

1. Unit tests run first (across OS/Python matrix)
2. Integration tests run after (Ubuntu only, Python 3.12)
3. Results uploaded as artifacts

### Locally (Manual)

#### Option 1: With Docker Compose

```bash
# Start Elite services
cd ../../cloud/elite
./go up

# Run integration tests
cd ../../cli/tests
export SYSTEM_API_URL=http://localhost/api
export SYSTEM_ADMIN_EMAIL=admin@rediacc.io
export SYSTEM_ADMIN_PASSWORD=admin
./run_integration_ci.sh
```

#### Option 2: Against Remote Instance

```bash
cd cli/tests
export SYSTEM_API_URL=https://sandbox.rediacc.com/api
export SYSTEM_ADMIN_EMAIL=your@email.com
export SYSTEM_ADMIN_PASSWORD=yourpassword
./run_integration_ci.sh
```

## Test Coverage

### Current Integration Tests

The integration test suite validates:

- **Company Operations** (`01xxx`) - Company creation, settings, vault
- **Permissions** (`02xxx`) - Permission management, groups
- **Users** (`03xxx`) - User CRUD, authentication
- **Teams** (`04xxx`) - Team operations, repositories, storage
- **Regions** (`05xxx`) - Region management
- **Bridges** (`06xxx`) - Bridge configuration
- **Machines** (`07xxx`) - Machine lifecycle
- **Queue** (`08xxx`) - Queue operations
- **Audit** (`09xxx`) - Audit logging

### What Gets Tested

✅ **API Integration** - Real HTTP requests/responses
✅ **Authentication** - Login, token management
✅ **Database Operations** - CRUD via stored procedures
✅ **Data Validation** - Schema compliance
✅ **Error Handling** - API error responses
✅ **Workflow Chains** - Multi-step operations

### What Doesn't Get Tested

❌ **Bridge Queue Processing** - Requires bridge container
❌ **SSH Operations** - Requires remote machines
❌ **File Sync** - Requires SSH + rsync
❌ **Desktop GUI** - Requires display server

## Configuration

### Environment Variables

Required for integration tests:

| Variable | Default | Description |
|----------|---------|-------------|
| `SYSTEM_API_URL` | `http://localhost/api` | Elite API endpoint |
| `SYSTEM_ADMIN_EMAIL` | `admin@rediacc.io` | Admin account email |
| `SYSTEM_ADMIN_PASSWORD` | `admin` | Admin account password |
| `REDIACC_TEST_ACTIVATION_CODE` | `111111` | Account activation code |
| `API_TIMEOUT` | `60` | API startup timeout (seconds) |

### Test Configuration

Tests use `yaml/config.yaml`:

```yaml
test_environment:
  api_url: "${env.SYSTEM_API_URL:-http://localhost/api}"
  activation_code: "${env.REDIACC_TEST_ACTIVATION_CODE:-111111}"
```

Fallback values allow tests to run with minimal configuration.

## Debugging

### View Test Results

Test results are saved to `test_results/test_YYYYMMDD_HHMMSS/`:

```bash
# List test runs
ls test_results/

# View specific test output
cat test_results/test_20251005_120000/community.01000_company.*.json
```

### Check Service Health

```bash
# API health endpoint
curl http://localhost/api/health

# Service logs (if running locally)
cd ../../cloud/elite
./go logs api
./go logs nginx
./go logs sql
```

### Common Issues

**API not responding:**
```bash
# Check if services are running
cd ../../cloud/elite
./go health

# Restart services
./go restart api
```

**Authentication failures:**
- Check `SYSTEM_ADMIN_EMAIL` and `SYSTEM_ADMIN_PASSWORD`
- Verify Elite initialized with correct admin credentials

**Test timeouts:**
- Increase `API_TIMEOUT` environment variable
- Check Docker resource limits

## CI/CD Workflow

The integration test job in `.github/workflows/test-cli.yml`:

```yaml
integration-test:
  runs-on: ubuntu-latest
  needs: test  # After unit tests

  steps:
    - Checkout monorepo
    - Start Elite services (via action)
    - Install CLI
    - Run integration tests
    - Upload results
```

**Strategy:**
- Run after unit tests pass
- Ubuntu only (cost optimization)
- Python 3.12 only (latest stable)
- Continue on error (non-blocking initially)

## Benefits

### Before Integration Testing
- ❌ API changes broke CLI silently
- ❌ Integration bugs found in production
- ❌ Manual testing required for API validation

### After Integration Testing
- ✅ API contract validated in CI
- ✅ Integration bugs caught early
- ✅ Automated end-to-end validation
- ✅ Confidence in releases

## Future Enhancements

Potential improvements:

1. **Expand Coverage** - Add more test scenarios (08xxx-12xxx series)
2. **Bridge Testing** - Include bridge queue processing tests
3. **Performance Tests** - Add load/stress testing
4. **Contract Testing** - Validate API schema changes
5. **Matrix Testing** - Test against multiple Elite versions

## Contributing

When adding new CLI features:

1. Add unit tests first (fast feedback)
2. Add integration tests (E2E validation)
3. Update test documentation
4. Verify tests pass in CI

Integration tests should focus on **API interaction**, not implementation details.

## Resources

- [Elite GitHub Action](../../cloud/elite/action/README.md)
- [YAML Test Guide](README.md)
- [CLI Development Guide](../docs/guides/DEVELOPMENT.md)
