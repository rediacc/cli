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

# Determine timeout command availability (not present on macOS by default)
if command -v timeout >/dev/null 2>&1; then
  TIMEOUT_CMD="timeout"
else
  TIMEOUT_CMD=""
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
  if [ -n "$TIMEOUT_CMD" ]; then $TIMEOUT_CMD 600s "$PY_BIN" -m pip install --upgrade pip setuptools wheel; else "$PY_BIN" -m pip install --upgrade pip setuptools wheel; fi
  echo "Installing project (editable) with extras [test,dev]..."
  if [ -n "$TIMEOUT_CMD" ]; then $TIMEOUT_CMD 600s "$PY_BIN" -m pip install --progress-bar off -e ".[test,dev]"; else "$PY_BIN" -m pip install --progress-bar off -e ".[test,dev]"; fi
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
    # Linux: split problematic Python versions into non-GUI and GUI phases to isolate hangs
    if [ "$PYTHON_VERSION" = "3.12" ] || [ "$PYTHON_VERSION" = "3.13" ]; then
      echo "[Phase 1] Non-GUI tests (excluding 'gui' marked)"
      if [ -n "$TIMEOUT_CMD" ]; then $TIMEOUT_CMD 600s "$PY_BIN" -m pytest tests/ "${PYTEST_ARGS[@]}" -k "not gui" \
        --junitxml="test-results-${PYTHON_VERSION}/junit-nongui.xml"; else "$PY_BIN" -m pytest tests/ "${PYTEST_ARGS[@]}" -k "not gui" \
        --junitxml="test-results-${PYTHON_VERSION}/junit-nongui.xml"; fi

      echo "[Smoke] Tkinter availability under Xvfb"
      SMOKE_OK=1
      if xvfb-run -a -s "-screen 0 1920x1080x24" "$PY_BIN" - <<'PY'
import sys
try:
    import tkinter as tk
    r=tk.Tk(); r.update(); r.destroy()
except Exception as e:
    sys.exit(2)
PY
      then
        SMOKE_OK=0
        echo "Tk smoke-check: OK"
      else
        echo "Tk smoke-check: FAILED (will skip GUI tests for Python $PYTHON_VERSION)"
      fi

      if [ "$SMOKE_OK" -eq 0 ]; then
        echo "[Phase 2] GUI tests only under Xvfb"
        if [ -n "$TIMEOUT_CMD" ]; then $TIMEOUT_CMD 600s xvfb-run -a -s "-screen 0 1920x1080x24" \
          "$PY_BIN" -m pytest tests/ "${PYTEST_ARGS[@]}" -k "gui" \
          --junitxml="test-results-${PYTHON_VERSION}/junit-gui.xml"; else xvfb-run -a -s "-screen 0 1920x1080x24" \
          "$PY_BIN" -m pytest tests/ "${PYTEST_ARGS[@]}" -k "gui" \
          --junitxml="test-results-${PYTHON_VERSION}/junit-gui.xml"; fi
      else
        echo "Skipping GUI tests due to failing Tk smoke-check"
      fi
      
    else
      # Other versions: run all under Xvfb
      if [ -n "$TIMEOUT_CMD" ]; then $TIMEOUT_CMD 900s xvfb-run -a -s "-screen 0 1920x1080x24" \
        "$PY_BIN" -m pytest tests/ "${PYTEST_ARGS[@]}" \
        --junitxml="test-results-${PYTHON_VERSION}/junit.xml"; else xvfb-run -a -s "-screen 0 1920x1080x24" \
        "$PY_BIN" -m pytest tests/ "${PYTEST_ARGS[@]}" \
        --junitxml="test-results-${PYTHON_VERSION}/junit.xml"; fi
    fi
  else
    # Windows/macOS: Direct pytest
    if [ -n "$TIMEOUT_CMD" ]; then $TIMEOUT_CMD 900s "$PY_BIN" -m pytest tests/ "${PYTEST_ARGS[@]}"; else "$PY_BIN" -m pytest tests/ "${PYTEST_ARGS[@]}"; fi
  fi
) 2>&1 | tee "$OUTPUT_DIR/02-run-tests.txt"

# Step 3: Integration tests (Linux only, Python 3.8 only)
if [ "$RUN_INTEGRATION" = "true" ] && [ "$PLATFORM_NAME" = "ubuntu-latest" ] && [ "$PYTHON_VERSION" = "3.8" ]; then
  (
    echo "Running integration tests..."
    cd tests
    if [ -n "$TIMEOUT_CMD" ]; then $TIMEOUT_CMD 1200s ./run_integration_ci.sh; else ./run_integration_ci.sh; fi
  ) 2>&1 | tee "$OUTPUT_DIR/03-integration-tests.txt"
fi

echo ""
echo "=========================================="
echo "✓ Tests completed successfully"
echo "=========================================="
