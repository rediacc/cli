#!/bin/bash

# Build script for Rediacc CLI
set -e

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BIN_DIR="$PROJECT_ROOT/bin"
VERSION=${VERSION:-"1.0.0"}
BUILD_TIME=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
GIT_COMMIT=${GIT_COMMIT:-$(git rev-parse --short HEAD 2>/dev/null || echo "unknown")}

# Create bin directory
mkdir -p "$BIN_DIR"

# Build flags
LDFLAGS="-X github.com/rediacc/cli/internal/version.Version=$VERSION"
LDFLAGS="$LDFLAGS -X github.com/rediacc/cli/internal/version.BuildTime=$BUILD_TIME"
LDFLAGS="$LDFLAGS -X github.com/rediacc/cli/internal/version.GitCommit=$GIT_COMMIT"

echo "Building Rediacc CLI..."
echo "Version: $VERSION"
echo "Build Time: $BUILD_TIME"
echo "Git Commit: $GIT_COMMIT"

cd "$PROJECT_ROOT"

# Build for current platform
echo "Building for current platform..."
go build -ldflags "$LDFLAGS" -o "$BIN_DIR/rediacc" main.go

echo "Build completed successfully!"
echo "Binary location: $BIN_DIR/rediacc"

# Make executable
chmod +x "$BIN_DIR/rediacc"

# Test the build
echo "Testing build..."
"$BIN_DIR/rediacc" --version