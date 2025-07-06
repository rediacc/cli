# Rediacc CLI Docker Images

This directory contains Docker configurations for the Rediacc CLI tools.

## Available Images

1. **rediacc/cli** - Base CLI image with all tools
2. **rediacc/cli-gui** - CLI with GUI support (X11 forwarding)

## Building Images

### Build Base Image
```bash
# From the cli directory
docker build -f docker/Dockerfile -t rediacc/cli:latest .

# Or use the build script
./scripts/build-docker.sh
```

### Build GUI Image
```bash
# Build base image first, then GUI image
docker build -f docker/Dockerfile -t rediacc/cli:latest .
docker build -f docker/Dockerfile.gui -t rediacc/cli-gui:latest .

# Or use the build script
./scripts/build-docker.sh --with-gui
```

## Running with Docker

### Basic Usage
```bash
# Show help
docker run --rm rediacc/cli:latest

# Run specific command
docker run --rm -v ~/.rediacc:/home/rediacc/.rediacc rediacc/cli:latest ./rediacc-cli list teams

# Interactive shell
docker run -it --rm -v ~/.rediacc:/home/rediacc/.rediacc rediacc/cli:latest /bin/bash
```

### With Environment Variables
```bash
# Using .env file
docker run --rm --env-file .env rediacc/cli:latest ./rediacc-cli list teams

# Using individual variables
docker run --rm -e REDIACC_TOKEN=your-token rediacc/cli:latest ./rediacc-cli list teams
```

### GUI Support (X11 Forwarding)

**Linux/macOS:**
```bash
# Allow X11 connections
xhost +local:docker

# Run GUI
docker run -it --rm \
  -e DISPLAY=$DISPLAY \
  -v /tmp/.X11-unix:/tmp/.X11-unix:rw \
  -v ~/.rediacc:/home/rediacc/.rediacc \
  rediacc/cli-gui:latest ./rediacc gui
```

**Windows (with X server like VcXsrv):**
```bash
docker run -it --rm \
  -e DISPLAY=host.docker.internal:0 \
  -v ~/.rediacc:/home/rediacc/.rediacc \
  rediacc/cli-gui:latest ./rediacc gui
```

## Docker Compose

Docker Compose provides pre-configured services:

```bash
# Run CLI command
docker-compose run --rm cli

# Interactive shell
docker-compose run --rm cli-shell

# Run tests
docker-compose run --rm cli-test

# GUI (requires X11 setup)
docker-compose run --rm cli-gui
```

### Available Services

- **cli** - Basic CLI service
- **cli-shell** - Interactive development shell
- **cli-test** - Test runner
- **cli-gui** - GUI-enabled CLI

## Volumes

The following volumes are used:

- `~/.rediacc` - CLI configuration and tokens
- `~/.ssh` - SSH keys (read-only)
- `/workspace` - Current directory (for docker-compose)

## Security Notes

- Images run as non-root user (`rediacc`)
- SSH keys are mounted read-only
- No sensitive data is baked into images
- Use `--env-file` for credentials, not build args

## Development

### Building for Development
```bash
# Build with local changes
docker build -f docker/Dockerfile -t rediacc/cli:dev .

# Run with live code mounting
docker run -it --rm \
  -v $(pwd):/app \
  -v ~/.rediacc:/home/rediacc/.rediacc \
  rediacc/cli:dev /bin/bash
```

### Debugging
```bash
# Run with verbose output
docker run --rm -e REDIACC_VERBOSE=1 rediacc/cli:latest ./rediacc-cli list teams

# Check image contents
docker run --rm rediacc/cli:latest ls -la /app
```

## Publishing Images

To publish to a registry:

```bash
# Tag for registry
docker tag rediacc/cli:latest registry.example.com/rediacc/cli:latest
docker tag rediacc/cli-gui:latest registry.example.com/rediacc/cli-gui:latest

# Push images
docker push registry.example.com/rediacc/cli:latest
docker push registry.example.com/rediacc/cli-gui:latest
```