#!/bin/bash
# Build script for Rediacc CLI Docker images

set -e

echo "Building Rediacc CLI Docker images..."

# Default to no-cache
no_cache="--no-cache"
version="dev"

# Parse arguments
for arg in "$@"; do
    case $arg in
        --cache)
            no_cache=""
            echo "Building with Docker cache enabled"
            ;;
        --version=*)
            version="${arg#*=}"
            echo "Building with version: $version"
            ;;
    esac
done

if [ -z "$no_cache" ]; then
    :
else
    echo "Building without cache (default behavior)"
fi

# Get the CLI root directory (parent of scripts)
CLI_ROOT="$(cd "$(dirname "$0")/.." && pwd)"

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
echo "  # Run with docker-compose:"
echo "  docker-compose run --rm cli"
echo ""
echo "  # Interactive shell:"
echo "  docker-compose run --rm cli-shell"
echo ""
echo "  # Run GUI (requires X11):"
echo "  xhost +local:docker"
echo "  docker run -it --rm -e DISPLAY=\$DISPLAY -v /tmp/.X11-unix:/tmp/.X11-unix:rw -v ./cli/.config:/home/rediacc/.config rediacc/cli:latest ./rediacc gui"