#!/bin/bash

# Test script for Rediacc CLI
set -e

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "Running tests for Rediacc CLI..."

cd "$PROJECT_ROOT"

# Run go mod tidy
echo "Tidying modules..."
go mod tidy

# Run tests
echo "Running unit tests..."
go test ./... -v

# Run tests with coverage
echo "Running tests with coverage..."
go test ./... -coverprofile=coverage.out

# Generate coverage report
if command -v go >/dev/null 2>&1; then
    echo "Generating coverage report..."
    go tool cover -html=coverage.out -o coverage.html
    echo "Coverage report generated: coverage.html"
fi

# Run linting (if available)
if command -v golangci-lint >/dev/null 2>&1; then
    echo "Running linter..."
    golangci-lint run
else
    echo "golangci-lint not found, skipping linting"
fi

echo "All tests completed successfully!"