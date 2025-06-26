#!/bin/bash
# Verify test setup - checks that all tools are accessible

echo "=== Verifying Test Setup ==="
echo ""

# Check if we're in the tests directory
if [ ! -f "README.md" ] || [ "$(basename $(pwd))" != "tests" ]; then
    echo "Error: This script should be run from the tests/ directory"
    exit 1
fi

echo "Current directory: $(pwd)"
echo ""

# Check each tool
echo "Checking tools availability:"

# Check rediacc-cli
if [ -x "../rediacc-cli" ]; then
    echo "✓ rediacc-cli found and executable"
    VERSION=$(../rediacc-cli --version 2>&1 | head -1 || echo "Version check not available")
    echo "  $VERSION"
else
    echo "✗ rediacc-cli not found or not executable"
fi

# Check rediacc-cli-sync
if [ -x "../rediacc-cli-sync" ]; then
    echo "✓ rediacc-cli-sync found and executable"
else
    echo "✗ rediacc-cli-sync not found or not executable"
fi

# Check rediacc-cli-term
if [ -x "../rediacc-cli-term" ]; then
    echo "✓ rediacc-cli-term found and executable"
else
    echo "✗ rediacc-cli-term not found or not executable"
fi

# Check core module
if [ -f "../rediacc_cli_core.py" ]; then
    echo "✓ rediacc_cli_core.py found"
else
    echo "✗ rediacc_cli_core.py not found"
fi

echo ""
echo "Checking test scripts:"

# List all test scripts
for script in test-*.sh; do
    if [ -x "$script" ]; then
        echo "✓ $script is executable"
    else
        echo "✗ $script is not executable"
    fi
done

echo ""
echo "Test environment verified!"
echo ""
echo "To run tests:"
echo "  1. Get a token: ../rediacc-cli login --email admin@rediacc.io --password YOUR_PASSWORD"
echo "  2. Run quick test: ./test-quick.sh YOUR_TOKEN"
echo "  3. Or run auto-login tests: ./test-sync.sh"