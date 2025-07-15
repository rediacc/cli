#!/bin/bash
# Build script for Rediacc CLI Docker images

set -e

echo "Building Rediacc CLI Docker images..."

# Default to no-cache
no_cache="--no-cache"
with_gui=false

# Parse arguments
for arg in "$@"; do
    case $arg in
        --cache)
            no_cache=""
            echo "Building with Docker cache enabled"
            ;;
        --with-gui)
            with_gui=true
            ;;
    esac
done

if [ -z "$no_cache" ]; then
    :
else
    echo "Building without cache (default behavior)"
fi

# Build base CLI image
echo "Building base CLI image..."
docker build $no_cache -t rediacc/cli:latest .

# Build GUI image (optional)
if [ "$with_gui" = true ]; then
    echo "Building GUI-enabled image..."
    docker build $no_cache -f Dockerfile.gui -t rediacc/cli-gui:latest .
fi

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

if [ "$with_gui" = true ]; then
    echo ""
    echo "  # Run GUI (requires X11):"
    echo "  xhost +local:docker"
    echo "  docker-compose run --rm cli-gui"
fi