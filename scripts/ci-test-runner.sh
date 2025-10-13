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

set -euo pipefail  # Exit on error, undefined var is error, fail pipe

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

# Resolve the Python binary from setup-python if available
if [[ -n "${pythonLocation:-}" && -x "${pythonLocation}/bin/python" ]]; then
  PY_BIN="${pythonLocation}/bin/python"
else
  PY_BIN="$(command -v python)"
fi

# Version without dot for directory names
PYTHON_VERSION_NODOT=$(echo "$PYTHON_VERSION" | tr -d '.')
OUTPUT_DIR="ci-outputs/${PLATFORM_NAME}-py${PYTHON_VERSION}"

# Environment hardening for pip/test stability
export PIP_DISABLE_PIP_VERSION_CHECK=1
export PIP_NO_INPUT=1
export PYTHONFAULTHANDLER=1

echo "=========================================="
echo "CI Test Runner"
echo "=========================================="
echo "Platform: $PLATFORM_NAME"
echo "Python: $PYTHON_VERSION"
echo "Output: $OUTPUT_DIR"
echo "Python executable: $PY_BIN"
"$PY_BIN" -V || true
"$PY_BIN" -c 'import sys; print(sys.executable)' || true
echo "=========================================="
echo ""

# Create output directory
mkdir -p "$OUTPUT_DIR"

# Step 1: Install dependencies
(
  echo "Installing dependencies..."
  echo "Upgrading pip/setuptools/wheel..."
  timeout 600s "$PY_BIN" -m pip install --upgrade pip setuptools wheel
  echo "Installing project (editable) with extras [test,dev]..."
  timeout 600s "$PY_BIN" -m pip install --progress-bar off -e ".[test,dev]"
  echo "pip freeze after install:" && "$PY_BIN" -m pip freeze | sort | sed -e 's/.*/  &/'
) 2>&1 | tee "$OUTPUT_DIR/01-install-deps.txt"

# Step 2: Run tests
(
  echo "Running tests..."
  # Common pytest args
  PYTEST_ARGS=(
    -v
    --cov=cli
    --cov-report=xml
    --tb=short
    -o faulthandler_timeout=240
  )

  if [ "$PLATFORM_NAME" = "ubuntu-latest" ]; then
    # Linux: Use xvfb for GUI testing
    timeout 900s xvfb-run -a -s "-screen 0 1920x1080x24" \
      "$PY_BIN" -m pytest tests/ "${PYTEST_ARGS[@]}" \
      --junitxml="test-results-${PYTHON_VERSION}/junit.xml"
  else
    # Windows/macOS: Direct pytest
    timeout 900s "$PY_BIN" -m pytest tests/ "${PYTEST_ARGS[@]}"
  fi
) 2>&1 | tee "$OUTPUT_DIR/02-run-tests.txt"

# Step 3: Integration tests (Linux only, Python 3.8 only)
if [ "$RUN_INTEGRATION" = "true" ] && [ "$PLATFORM_NAME" = "ubuntu-latest" ] && [ "$PYTHON_VERSION" = "3.8" ]; then
  (
    echo "Running integration tests..."
    cd tests
    timeout 1200s ./run_integration_ci.sh
  ) 2>&1 | tee "$OUTPUT_DIR/03-integration-tests.txt"
fi

echo ""
echo "=========================================="
echo "✓ Tests completed successfully"
echo "=========================================="
