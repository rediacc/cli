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

# Strip 'v' prefix from version for both Python package and Docker tags
clean_version="${version#v}"

# Optionally update _version.py file (for local testing)
if [ "$update_version_file" = true ] && [ "$version" != "dev" ]; then
    VERSION_FILE="$CLI_ROOT/src/cli/_version.py"
    if [ -f "$VERSION_FILE" ]; then
        echo "Updating $VERSION_FILE to version: $clean_version"
        sed -i.bak "s/__version__ = \"[^\"]*\"/__version__ = \"$clean_version\"/g" "$VERSION_FILE"
        rm -f "${VERSION_FILE}.bak"
    fi
fi

# Build CLI image (includes GUI support)
echo "Building CLI image with GUI support..."

# Check if multi-platform build is requested
if [ "${DOCKER_BUILDX}" = "1" ] && [ -n "${REDIACC_BUILD_PLATFORMS}" ]; then
    echo "Using buildx for multi-platform CLI build: ${REDIACC_BUILD_PLATFORMS}"

    # Calculate registry-prefixed image name (consistent with build.sh)
    REGISTRY_PREFIX="${PUBLISH_DOCKER_REGISTRY:-}"
    if [ -n "$REGISTRY_PREFIX" ]; then
        SLASH_COUNT=$(echo "$REGISTRY_PREFIX" | tr -cd '/' | wc -c)
        if [ $SLASH_COUNT -ge 2 ]; then
            # Multi-level registry: strip rediacc/ prefix
            IMAGE_NAME="$REGISTRY_PREFIX/cli"
        else
            # Simple registry: keep full path
            IMAGE_NAME="$REGISTRY_PREFIX/rediacc/cli"
        fi
    else
        # No registry set - local build only
        IMAGE_NAME="rediacc/cli"
    fi

    if [ "$version" != "dev" ]; then
        # Build with version tag (both VERSION build arg and Docker tag use clean version without 'v')
        if [ -n "$REGISTRY_PREFIX" ]; then
            echo "  Pushing to: $IMAGE_NAME"
            docker buildx build \
                --platform "${REDIACC_BUILD_PLATFORMS}" \
                $no_cache \
                --build-arg VERSION="$clean_version" \
                -t "$IMAGE_NAME:latest" \
                -t "$IMAGE_NAME:$clean_version" \
                -f "$CLI_ROOT/docker/Dockerfile" \
                --pull \
                --push \
                "$CLI_ROOT"
        else
            echo "  Building locally (no PUBLISH_DOCKER_REGISTRY set)"
            docker buildx build \
                --platform "${REDIACC_BUILD_PLATFORMS}" \
                $no_cache \
                --build-arg VERSION="$clean_version" \
                -t "$IMAGE_NAME:latest" \
                -t "$IMAGE_NAME:$clean_version" \
                -f "$CLI_ROOT/docker/Dockerfile" \
                --pull \
                --output type=image,push=false \
                "$CLI_ROOT"
        fi
    else
        # Build with only latest tag when no version specified
        if [ -n "$REGISTRY_PREFIX" ]; then
            echo "  Pushing to: $IMAGE_NAME"
            docker buildx build \
                --platform "${REDIACC_BUILD_PLATFORMS}" \
                $no_cache \
                --build-arg VERSION="latest" \
                -t "$IMAGE_NAME:latest" \
                -f "$CLI_ROOT/docker/Dockerfile" \
                --pull \
                --push \
                "$CLI_ROOT"
        else
            echo "  Building locally (no PUBLISH_DOCKER_REGISTRY set)"
            docker buildx build \
                --platform "${REDIACC_BUILD_PLATFORMS}" \
                $no_cache \
                --build-arg VERSION="latest" \
                -t "$IMAGE_NAME:latest" \
                -f "$CLI_ROOT/docker/Dockerfile" \
                --pull \
                --output type=image,push=false \
                "$CLI_ROOT"
        fi
    fi
else
    if [ "$version" != "dev" ]; then
        # Build with version tag (both VERSION build arg and Docker tag use clean version without 'v')
        docker build $no_cache \
            --build-arg VERSION="$clean_version" \
            -t rediacc/cli:latest \
            -t rediacc/cli:$clean_version \
            -f "$CLI_ROOT/docker/Dockerfile" \
            "$CLI_ROOT"
    else
        # Build with only latest tag when no version specified
        docker build $no_cache \
            --build-arg VERSION="latest" \
            -t rediacc/cli:latest \
            -f "$CLI_ROOT/docker/Dockerfile" \
            "$CLI_ROOT"
    fi
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
echo "  # Interactive shell:"
echo "  docker run -it --rm -v ./cli/.config:/home/rediacc/.config rediacc/cli:latest /bin/bash"
echo ""
echo "  # Run desktop application (requires X11):"
echo "  xhost +local:docker"
echo "  docker run -it --rm -e DISPLAY=\$DISPLAY -v /tmp/.X11-unix:/tmp/.X11-unix:rw -v ./cli/.config:/home/rediacc/.config rediacc/cli:latest ./rediacc desktop"