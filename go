#!/bin/bash

# Exit on error
set -e

# Project configuration
PROJECT_NAME="rediacc-cli"
BINARY_NAME="rediacc"
VERSION=${VERSION:-"1.0.0"}

# Function to build the CLI
function build() {
  echo "Building $PROJECT_NAME..."
  ./scripts/build.sh
}

# Function to run the CLI in development mode
function dev() {
  echo "Running $PROJECT_NAME in development mode..."
  go run main.go "$@"
}

# Function to run tests
function test() {
  echo "Running tests for $PROJECT_NAME..."
  go test ./... -v
}

# Function to run tests with coverage
function test_coverage() {
  echo "Running tests with coverage..."
  go test ./... -coverprofile=coverage.out
  go tool cover -html=coverage.out -o coverage.html
  echo "Coverage report generated: coverage.html"
}

# Function to run linting
function lint() {
  echo "Running linter..."
  if command -v golangci-lint >/dev/null 2>&1; then
    golangci-lint run
  else
    echo "Installing golangci-lint..."
    go install github.com/golangci/golangci-lint/cmd/golangci-lint@latest
    golangci-lint run
  fi
}

# Function to format code
function format() {
  echo "Formatting code..."
  go fmt ./...
  if command -v goimports >/dev/null 2>&1; then
    goimports -w .
  else
    echo "Installing goimports..."
    go install golang.org/x/tools/cmd/goimports@latest
    goimports -w .
  fi
}

# Function to clean build artifacts
function clean() {
  echo "Cleaning build artifacts..."
  rm -rf bin/
  rm -f coverage.out coverage.html
  go clean
}

# Function to install the CLI globally
function install() {
  echo "Installing $PROJECT_NAME globally..."
  build
  sudo cp bin/$BINARY_NAME /usr/local/bin/
  echo "$PROJECT_NAME installed to /usr/local/bin/$BINARY_NAME"
}

# Function to uninstall the CLI
function uninstall() {
  echo "Uninstalling $PROJECT_NAME..."
  sudo rm -f /usr/local/bin/$BINARY_NAME
  echo "$PROJECT_NAME uninstalled"
}

# Function to run docker for development
function docker_dev() {
  echo "Building and starting Docker container for development..."
  docker stop $PROJECT_NAME-dev 2>/dev/null || true
  docker rm $PROJECT_NAME-dev 2>/dev/null || true
  docker build -f Dockerfile.dev -t $PROJECT_NAME-dev .
  docker run -it --rm --name $PROJECT_NAME-dev -v "$(pwd)":/app $PROJECT_NAME-dev
}

# Function to run docker for production
function docker_prod() {
  echo "Building and starting Docker container for production..."
  docker build -t $PROJECT_NAME:$VERSION .
  docker run -it --rm $PROJECT_NAME:$VERSION
}

# Function to create a release build
function release() {
  echo "Creating release build for $PROJECT_NAME v$VERSION..."
  
  # Create release directory
  mkdir -p dist/
  
  # Build for multiple platforms
  echo "Building for Linux AMD64..."
  GOOS=linux GOARCH=amd64 go build -ldflags "-X main.version=$VERSION" -o dist/${BINARY_NAME}-linux-amd64 main.go
  
  echo "Building for Linux ARM64..."
  GOOS=linux GOARCH=arm64 go build -ldflags "-X main.version=$VERSION" -o dist/${BINARY_NAME}-linux-arm64 main.go
  
  echo "Building for macOS AMD64..."
  GOOS=darwin GOARCH=amd64 go build -ldflags "-X main.version=$VERSION" -o dist/${BINARY_NAME}-darwin-amd64 main.go
  
  echo "Building for macOS ARM64..."
  GOOS=darwin GOARCH=arm64 go build -ldflags "-X main.version=$VERSION" -o dist/${BINARY_NAME}-darwin-arm64 main.go
  
  echo "Building for Windows AMD64..."
  GOOS=windows GOARCH=amd64 go build -ldflags "-X main.version=$VERSION" -o dist/${BINARY_NAME}-windows-amd64.exe main.go
  
  # Create checksums
  cd dist/
  sha256sum * > checksums.txt
  cd ..
  
  echo "Release builds created in dist/ directory"
}

# Function to update dependencies
function deps() {
  echo "Updating dependencies..."
  go mod tidy
  go mod download
}

# Function to generate documentation
function docs() {
  echo "Generating documentation..."
  mkdir -p docs/commands/
  go run main.go --help > docs/commands/README.md 2>/dev/null || true
  
  # Generate command documentation if available
  if [ -f "bin/$BINARY_NAME" ]; then
    ./bin/$BINARY_NAME auth --help > docs/commands/auth.md 2>/dev/null || true
    ./bin/$BINARY_NAME company --help > docs/commands/company.md 2>/dev/null || true
    ./bin/$BINARY_NAME teams --help > docs/commands/teams.md 2>/dev/null || true
    echo "Documentation generated in docs/commands/"
  else
    echo "Build the project first with './go build'"
  fi
}

# Function to run security scan
function security() {
  echo "Running security scan..."
  if command -v gosec >/dev/null 2>&1; then
    gosec ./...
  else
    echo "Installing gosec..."
    go install github.com/securecodewarrior/gosec/v2/cmd/gosec@latest
    gosec ./...
  fi
}

# Function to benchmark
function bench() {
  echo "Running benchmarks..."
  go test -bench=. -benchmem ./...
}

# Help message
function show_help() {
  echo "Usage: ./go [COMMAND] [ARGS...]"
  echo ""
  echo "Development Commands:"
  echo "  build         Build the CLI binary"
  echo "  dev [args]    Run the CLI in development mode with args"
  echo "  test          Run unit tests"
  echo "  test_coverage Run tests with coverage report"
  echo "  lint          Run code linter"
  echo "  format        Format code with go fmt and goimports"
  echo "  deps          Update and tidy dependencies"
  echo ""
  echo "Build & Release Commands:"
  echo "  clean         Clean build artifacts"
  echo "  release       Create multi-platform release builds"
  echo "  install       Install CLI globally"
  echo "  uninstall     Uninstall CLI from system"
  echo ""
  echo "Docker Commands:"
  echo "  docker_dev    Build and run Docker container (development)"
  echo "  docker_prod   Build and run Docker container (production)"
  echo ""
  echo "Utility Commands:"
  echo "  docs          Generate documentation"
  echo "  security      Run security scan"
  echo "  bench         Run benchmarks"
  echo "  help          Show this help message"
  echo ""
  echo "Examples:"
  echo "  ./go build                    # Build the binary"
  echo "  ./go dev --help               # Run CLI with --help flag"
  echo "  ./go dev auth login           # Run auth login command in dev mode"
  echo "  ./go test                     # Run all tests"
  echo "  ./go release                  # Create release builds"
  echo ""
}

# Make sure Go modules are downloaded
if [ ! -f "go.sum" ] || [ ! -d "vendor" ] && [ -f "go.mod" ]; then
  echo "Downloading Go modules..."
  go mod download
fi

# Check command line argument
case "$1" in
  build)
    shift
    build "$@"
    ;;
  dev)
    shift
    dev "$@"
    ;;
  test)
    shift
    test "$@"
    ;;
  test_coverage)
    shift
    test_coverage "$@"
    ;;
  lint)
    shift
    lint "$@"
    ;;
  format)
    shift
    format "$@"
    ;;
  clean)
    shift
    clean "$@"
    ;;
  install)
    shift
    install "$@"
    ;;
  uninstall)
    shift
    uninstall "$@"
    ;;
  docker_dev)
    shift
    docker_dev "$@"
    ;;
  docker_prod)
    shift
    docker_prod "$@"
    ;;
  release)
    shift
    release "$@"
    ;;
  deps)
    shift
    deps "$@"
    ;;
  docs)
    shift
    docs "$@"
    ;;
  security)
    shift
    security "$@"
    ;;
  bench)
    shift
    bench "$@"
    ;;
  help|--help|-h)
    show_help
    ;;
  *)
    if [ $# -eq 0 ]; then
      show_help
    else
      echo "Unknown command: $1"
      echo "Run './go help' for usage information."
      exit 1
    fi
    ;;
esac