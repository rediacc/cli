#!/bin/bash
# CI Integration Test Runner
# Runs integration tests against Elite backend services in CI environment

set -e

echo "========================================="
echo "Rediacc CLI Integration Test Runner"
echo "========================================="
echo ""

# Configuration
API_URL="${SYSTEM_API_URL:-http://localhost/api}"
ADMIN_EMAIL="${SYSTEM_ADMIN_EMAIL:-admin@rediacc.io}"
ADMIN_PASSWORD="${SYSTEM_ADMIN_PASSWORD:-admin}"
ACTIVATION_CODE="${REDIACC_TEST_ACTIVATION_CODE:-111111}"
TIMEOUT="${API_TIMEOUT:-60}"

echo "Configuration:"
echo "  API URL: $API_URL"
echo "  Admin Email: $ADMIN_EMAIL"
echo "  Activation Code: $ACTIVATION_CODE"
echo "  Timeout: ${TIMEOUT}s"
echo ""

# Wait for Elite API to be ready
echo "Waiting for Elite API to be ready..."
if timeout "$TIMEOUT" bash -c "until curl -f $API_URL/health 2>/dev/null; do echo '  Waiting...'; sleep 2; done"; then
    echo "✓ Elite API is ready!"
else
    echo "✗ Elite API failed to start within ${TIMEOUT}s"
    exit 1
fi

echo ""
echo "========================================="
echo "Running Integration Tests"
echo "========================================="
echo ""

# Export environment variables for tests
export SYSTEM_API_URL="$API_URL"
export SYSTEM_ADMIN_EMAIL="$ADMIN_EMAIL"
export SYSTEM_ADMIN_PASSWORD="$ADMIN_PASSWORD"
export REDIACC_TEST_ACTIVATION_CODE="$ACTIVATION_CODE"

# Run integration tests
# Start with basic company/team/user tests (01xxx series)
echo "Running basic integration tests (01xxx series)..."
python run_tests.py "yaml/community/01*.yaml"

EXIT_CODE=$?

echo ""
echo "========================================="
echo "Integration Test Summary"
echo "========================================="

if [ $EXIT_CODE -eq 0 ]; then
    echo "✓ All integration tests passed!"
else
    echo "✗ Some integration tests failed (exit code: $EXIT_CODE)"
    echo ""
    echo "Check test results in test_results/ directory for details"
fi

exit $EXIT_CODE
