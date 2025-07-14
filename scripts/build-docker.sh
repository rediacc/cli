#!/bin/bash
# Build script for Rediacc CLI Docker images

set -e

echo "Building Rediacc CLI Docker images..."

# Build base CLI image
echo "Building base CLI image..."
docker build -t rediacc/cli:latest .

# Build GUI image (optional)
if [ "$1" = "--with-gui" ]; then
    echo "Building GUI-enabled image..."
    docker build -f Dockerfile.gui -t rediacc/cli-gui:latest .
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

if [ "$1" = "--with-gui" ]; then
    echo ""
    echo "  # Run GUI (requires X11):"
    echo "  xhost +local:docker"
    echo "  docker-compose run --rm cli-gui"
fi