#!/bin/bash

# Script to remove old/redundant test files after simplification
# This script shows what will be removed and asks for confirmation

echo "=== Test Cleanup Script ==="
echo ""
echo "The following test files are now redundant and can be removed:"
echo ""

# List of files to remove
OLD_FILES=(
    "test-integration.sh"        # Merged into test-core.sh
    "test-token-management.sh"   # Merged into test-core.sh
    "test-full-api.sh"          # Replaced by simplified test-api.sh
    "test-term-simple.sh"       # Merged into test-term.sh
    "test-term-demo.sh"         # Merged into test-term.sh
    "test-quick.sh"             # Functionality covered in main tests
    "test-simple.sh"            # Functionality covered in main tests
    "test-dev-mode.sh"          # Dev mode testing included in test-term.sh
    "demo-repo-creation.sh"     # Demo script, not a proper test
    "debug-test.sh"             # Debug helper, not needed
    "verify-setup.sh"           # Setup verification in test-core.sh
)

# Show files that will be removed
for file in "${OLD_FILES[@]}"; do
    if [ -f "$file" ]; then
        echo "  - $file"
    fi
done

echo ""
echo "The following files will be KEPT:"
echo "  - test-common.sh     (shared utilities)"
echo "  - test-core.sh       (core functionality)"
echo "  - test-api.sh        (API endpoints)"
echo "  - test-sync.sh       (file synchronization)"
echo "  - test-term.sh       (terminal access)"
echo "  - run-all-tests.sh   (master test runner)"
echo ""

# Ask for confirmation
read -p "Do you want to remove the old test files? (y/N): " -n 1 -r
echo ""

if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "Removing old test files..."
    for file in "${OLD_FILES[@]}"; do
        if [ -f "$file" ]; then
            rm -f "$file"
            echo "Removed: $file"
        fi
    done
    echo ""
    echo "Cleanup complete!"
else
    echo "Cleanup cancelled."
fi