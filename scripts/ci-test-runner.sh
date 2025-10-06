#!/usr/bin/env bash
#
# CI Test Runner Script
# Reusable script for running tests across different platforms and Python versions
#
# Usage: ./ci-test-runner.sh <platform> <python-version> [options]
#
# Examples:
#   ./ci-test-runner.sh ubuntu-latest 3.8
#   ./ci-test-runner.sh windows-latest 3.9
#   ./ci-test-runner.sh macos-latest 3.10
#

set -e  # Exit on error

# Parse arguments
PLATFORM="${1:-ubuntu-latest}"
PYTHON_VERSION="${2:-3.8}"
RUN_INTEGRATION="${3:-false}"

# Normalize platform name
case "$PLATFORM" in
  ubuntu*|linux*)
    PLATFORM_NAME="ubuntu-latest"
    ;;
  windows*)
    PLATFORM_NAME="windows-latest"
    ;;
  macos*|darwin*)
    PLATFORM_NAME="macos-latest"
    ;;
  *)
    PLATFORM_NAME="$PLATFORM"
    ;;
esac

# Version without dot for directory names
PYTHON_VERSION_NODOT=$(echo "$PYTHON_VERSION" | tr -d '.')
OUTPUT_DIR="ci-outputs/${PLATFORM_NAME}-py${PYTHON_VERSION}"

echo "=========================================="
echo "CI Test Runner"
echo "=========================================="
echo "Platform: $PLATFORM_NAME"
echo "Python: $PYTHON_VERSION"
echo "Output: $OUTPUT_DIR"
echo "=========================================="
echo ""

# Create output directory
mkdir -p "$OUTPUT_DIR"

# Step 1: Install dependencies
echo "Installing dependencies..." | tee "$OUTPUT_DIR/01-install-deps.txt"
python -m pip install --upgrade pip setuptools wheel 2>&1 | tee -a "$OUTPUT_DIR/01-install-deps.txt"
python -m pip install -e ".[test,dev]" 2>&1 | tee -a "$OUTPUT_DIR/01-install-deps.txt"

# Step 2: Run tests
echo "Running tests..." | tee "$OUTPUT_DIR/02-run-tests.txt"

# Platform-specific test command
if [ "$PLATFORM_NAME" = "ubuntu-latest" ]; then
    # Linux: Use xvfb for GUI testing
    xvfb-run -a -s "-screen 0 1920x1080x24" python -m pytest tests/ \
        -v \
        --cov=cli \
        --cov-report=xml \
        --cov-report=html \
        --junitxml="test-results-${PYTHON_VERSION}/junit.xml" \
        --tb=short \
        2>&1 | tee -a "$OUTPUT_DIR/02-run-tests.txt"
else
    # Windows/macOS: Direct pytest
    python -m pytest tests/ \
        -v \
        --cov=cli \
        --cov-report=xml \
        --tb=short \
        2>&1 | tee -a "$OUTPUT_DIR/02-run-tests.txt"
fi

# Step 3: Integration tests (Linux only, Python 3.8 only)
if [ "$RUN_INTEGRATION" = "true" ] && [ "$PLATFORM_NAME" = "ubuntu-latest" ] && [ "$PYTHON_VERSION" = "3.8" ]; then
    echo "Running integration tests..." | tee "$OUTPUT_DIR/03-integration-tests.txt"
    cd tests
    ./run_integration_ci.sh 2>&1 | tee -a "../$OUTPUT_DIR/03-integration-tests.txt"
    cd ..
fi

echo ""
echo "=========================================="
echo "✓ Tests completed successfully"
echo "=========================================="
