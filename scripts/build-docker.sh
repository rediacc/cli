#!/bin/bash
# Build script for Rediacc CLI Docker images

set -e

echo "Building Rediacc CLI Docker images..."

# Default to using cache for better performance
no_cache=""
version="dev"
update_version_file=false

# Parse arguments
for arg in "$@"; do
    case $arg in
        --no-cache)
            no_cache="--no-cache"
            echo "Building without Docker cache"
            ;;
        --cache)
            # Kept for backward compatibility but cache is now default
            no_cache=""
            echo "Building with Docker cache (default)"
            ;;
        --version=*)
            version="${arg#*=}"
            echo "Building with version: $version"
            ;;
        --update-version-file)
            update_version_file=true
            echo "Will update _version.py before build"
            ;;
    esac
done

if [ -z "$no_cache" ]; then
    echo "Building with cache enabled (default behavior)"
else
    echo "Building without cache (--no-cache specified)"
fi

# Get the CLI root directory (parent of scripts)
CLI_ROOT="$(cd "$(dirname "$0")/.." && pwd)"

# Optionally update _version.py file (for local testing)
if [ "$update_version_file" = true ] && [ "$version" != "dev" ]; then
    VERSION_FILE="$CLI_ROOT/src/cli/_version.py"
    if [ -f "$VERSION_FILE" ]; then
        # Strip "v" prefix if present for PyPI compatibility
        pypi_version="${version#v}"
        echo "Updating $VERSION_FILE to version: $pypi_version"
        sed -i.bak "s/__version__ = \"[^\"]*\"/__version__ = \"$pypi_version\"/g" "$VERSION_FILE"
        rm -f "${VERSION_FILE}.bak"
    fi
fi

# Build CLI image (includes GUI support)
echo "Building CLI image with GUI support..."
docker build $no_cache \
    --build-arg VERSION="$version" \
    -t rediacc/cli:latest \
    -t rediacc/cli:$version \
    -f "$CLI_ROOT/docker/Dockerfile" \
    "$CLI_ROOT"

echo "Build complete!"
echo ""
echo "Available images:"
docker images | grep rediacc/cli

echo ""
echo "Usage examples:"
echo "  # Run CLI in Docker:"
echo "  docker run -it --rm -v ./cli/.config:/home/rediacc/.config rediacc/cli:latest ./rediacc help"
echo ""
echo "  # Interactive shell:"
echo "  docker run -it --rm -v ./cli/.config:/home/rediacc/.config rediacc/cli:latest /bin/bash"
echo ""
echo "  # Run GUI (requires X11):"
echo "  xhost +local:docker"
echo "  docker run -it --rm -e DISPLAY=\$DISPLAY -v /tmp/.X11-unix:/tmp/.X11-unix:rw -v ./cli/.config:/home/rediacc/.config rediacc/cli:latest ./rediacc gui"