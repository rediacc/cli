#!/bin/bash
# CI-agnostic PyPI publishing script
# Can be called from any CI platform (GitHub Actions, GitLab CI, Jenkins, etc.)
#
# Usage:
#   ./publish.sh [options]
#
# Options:
#   --version=VERSION          Version to publish (e.g., v0.1.41 or 0.1.41)
#   --token-pypi=TOKEN         PyPI API token (or set PYPI_TOKEN env var)
#   --token-testpypi=TOKEN     TestPyPI API token (or set TESTPYPI_TOKEN env var)
#   --skip-testpypi            Skip TestPyPI publishing
#   --skip-pypi                Skip PyPI publishing (TestPyPI only)
#   --skip-build               Skip building (use existing dist/)
#   --dry-run                  Don't actually publish, just validate
#   --release-notes=FILE       Output release notes to file
#   --help                     Show this help

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Show help
show_help() {
    grep "^#" "$0" | grep -v "#!/bin/bash" | sed 's/^# //g' | sed 's/^#//g'
    exit 0
}

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

cd "$REPO_ROOT"

# Default values
VERSION=""
PYPI_TOKEN="${PYPI_TOKEN:-}"
TESTPYPI_TOKEN="${TESTPYPI_TOKEN:-}"
SKIP_TESTPYPI=false
SKIP_PYPI=false
SKIP_BUILD=false
DRY_RUN=false
RELEASE_NOTES_FILE=""

# Parse arguments
for arg in "$@"; do
    case "$arg" in
        --version=*)
            VERSION="${arg#--version=}"
            ;;
        --token-pypi=*)
            PYPI_TOKEN="${arg#--token-pypi=}"
            ;;
        --token-testpypi=*)
            TESTPYPI_TOKEN="${arg#--token-testpypi=}"
            ;;
        --skip-testpypi)
            SKIP_TESTPYPI=true
            ;;
        --skip-pypi)
            SKIP_PYPI=true
            ;;
        --skip-build)
            SKIP_BUILD=true
            ;;
        --dry-run)
            DRY_RUN=true
            ;;
        --release-notes=*)
            RELEASE_NOTES_FILE="${arg#--release-notes=}"
            ;;
        --help)
            show_help
            ;;
        *)
            log_error "Unknown argument: $arg"
            show_help
            ;;
    esac
done

# Detect version if not provided
if [ -z "$VERSION" ]; then
    # Try to get from git tag
    VERSION=$(git describe --exact-match --tags HEAD 2>/dev/null || echo "")

    if [ -z "$VERSION" ]; then
        log_error "No version specified and not on a git tag"
        log_error "Use --version=X.Y.Z or create a git tag"
        exit 1
    fi

    log_info "Detected version from git tag: $VERSION"
fi

# Normalize version (remove 'v' prefix for PyPI)
VERSION_NORMALIZED="${VERSION#v}"
VERSION_TAG="v${VERSION_NORMALIZED}"

log_info "Publishing Rediacc CLI version: $VERSION_NORMALIZED"

# Validate version format (semantic versioning)
if ! [[ "$VERSION_NORMALIZED" =~ ^[0-9]+\.[0-9]+\.[0-9]+(-[a-zA-Z0-9.-]+)?(\+[a-zA-Z0-9.-]+)?$ ]]; then
    log_error "Invalid version format: $VERSION_NORMALIZED"
    log_error "Expected semantic version (e.g., 1.2.3 or 1.2.3-beta.1)"
    exit 1
fi

# Check tokens
if [ "$SKIP_TESTPYPI" = false ] && [ -z "$TESTPYPI_TOKEN" ]; then
    log_error "TestPyPI token not provided"
    log_error "Use --token-testpypi=TOKEN or set TESTPYPI_TOKEN env var"
    exit 1
fi

if [ "$SKIP_PYPI" = false ] && [ -z "$PYPI_TOKEN" ]; then
    log_error "PyPI token not provided"
    log_error "Use --token-pypi=TOKEN or set PYPI_TOKEN env var"
    exit 1
fi

# Build package if not skipped
if [ "$SKIP_BUILD" = false ]; then
    log_info "Building package..."

    # Clean previous builds
    rm -rf dist/ build/ *.egg-info src/*.egg-info

    # Run build script
    if [ "$DRY_RUN" = true ]; then
        log_info "[DRY RUN] Would build: python3 scripts/build-pypi.py $VERSION_NORMALIZED"
    else
        python3 scripts/build-pypi.py "$VERSION_NORMALIZED" || {
            log_error "Build failed"
            exit 1
        }
    fi

    log_success "Package built successfully"
else
    log_warning "Skipping build (using existing dist/)"

    # Verify dist exists
    if [ ! -d "dist" ] || [ -z "$(ls -A dist)" ]; then
        log_error "dist/ directory is empty. Build first or remove --skip-build"
        exit 1
    fi
fi

# Publish to TestPyPI
if [ "$SKIP_TESTPYPI" = false ]; then
    log_info "Publishing to TestPyPI..."

    if [ "$DRY_RUN" = true ]; then
        log_info "[DRY RUN] Would upload to TestPyPI"
    else
        TWINE_USERNAME="__token__" \
        TWINE_PASSWORD="$TESTPYPI_TOKEN" \
        python3 -m twine upload --repository testpypi dist/* || {
            log_error "TestPyPI upload failed"
            exit 1
        }

        log_success "Published to TestPyPI: https://test.pypi.org/project/rediacc/$VERSION_NORMALIZED/"

        # Wait a bit for TestPyPI to process
        log_info "Waiting 10 seconds for TestPyPI to process..."
        sleep 10
    fi
else
    log_warning "Skipping TestPyPI publishing"
fi

# Publish to PyPI
if [ "$SKIP_PYPI" = false ]; then
    log_info "Publishing to PyPI..."

    if [ "$DRY_RUN" = true ]; then
        log_info "[DRY RUN] Would upload to PyPI"
    else
        TWINE_USERNAME="__token__" \
        TWINE_PASSWORD="$PYPI_TOKEN" \
        python3 -m twine upload dist/* || {
            log_error "PyPI upload failed"
            exit 1
        }

        log_success "Published to PyPI: https://pypi.org/project/rediacc/$VERSION_NORMALIZED/"
    fi
else
    log_warning "Skipping PyPI publishing"
fi

# Generate release notes
if [ -n "$RELEASE_NOTES_FILE" ] || [ "$DRY_RUN" = false ]; then
    log_info "Generating release notes..."

    NOTES_OUTPUT="$("$SCRIPT_DIR/generate-release-notes.sh" "$VERSION_TAG" 2>/dev/null || echo "")"

    if [ -n "$RELEASE_NOTES_FILE" ]; then
        echo "$NOTES_OUTPUT" > "$RELEASE_NOTES_FILE"
        log_success "Release notes written to: $RELEASE_NOTES_FILE"
    fi

    # Output to stdout for CI to capture
    if [ -n "$NOTES_OUTPUT" ]; then
        echo ""
        echo "=========================================="
        echo "RELEASE NOTES"
        echo "=========================================="
        echo "$NOTES_OUTPUT"
        echo "=========================================="
    fi
fi

# Summary
echo ""
log_success "Publishing completed successfully!"
echo ""
echo "Version: $VERSION_NORMALIZED"

if [ "$SKIP_TESTPYPI" = false ]; then
    echo "TestPyPI: https://test.pypi.org/project/rediacc/$VERSION_NORMALIZED/"
fi

if [ "$SKIP_PYPI" = false ]; then
    echo "PyPI: https://pypi.org/project/rediacc/$VERSION_NORMALIZED/"
fi

echo ""
echo "Installation:"
echo "  pip install rediacc==$VERSION_NORMALIZED"
echo ""
