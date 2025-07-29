# Rediacc CLI Docker Images

This directory contains Docker configurations for the Rediacc CLI tools.

## Available Images

**rediacc/cli** - Complete CLI image with all tools including GUI support (X11 forwarding)

## Building Images

### Build Image
```bash
# From the cli directory
docker build -f docker/Dockerfile -t rediacc/cli:latest .

# Or use the build script
./scripts/build-docker.sh
```

## Running with Docker

### Basic Usage
```bash
# Show help
docker run --rm rediacc/cli:latest

# Run specific command
docker run --rm -v ./cli/.rediacc:/home/rediacc/.rediacc rediacc/cli:latest ./rediacc list teams

# Interactive shell
docker run -it --rm -v ./cli/.rediacc:/home/rediacc/.rediacc rediacc/cli:latest /bin/bash
```

### With Environment Variables
```bash
# Using .env file
docker run --rm --env-file .env rediacc/cli:latest ./rediacc list teams

# Using individual variables
docker run --rm -e REDIACC_TOKEN=your-token rediacc/cli:latest ./rediacc list teams
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
  -v ./cli/.rediacc:/home/rediacc/.rediacc \
  rediacc/cli:latest ./rediacc gui
```

**Windows (with X server like VcXsrv):**
```bash
docker run -it --rm \
  -e DISPLAY=host.docker.internal:0 \
  -v ./cli/.rediacc:/home/rediacc/.rediacc \
  rediacc/cli:latest ./rediacc gui
```


## Volumes

The following volumes are used:

- `./cli/.rediacc` - CLI configuration and tokens (local to project)
- `~/.ssh` - SSH keys (read-only)

### Important Note on Config Directory

The Docker setup now uses a local `.rediacc` directory within the CLI folder (`./cli/.rediacc`) instead of the user's home directory (`~/.rediacc`). This ensures:

1. **Isolation**: Each project instance has its own configuration
2. **Portability**: Config travels with the project
3. **Permissions**: No conflicts with host user permissions

When running from the monorepo root:
```bash
# Correct - uses local config
docker run -v ./cli/.rediacc:/home/rediacc/.rediacc ...
```

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
  -v ./cli/.rediacc:/home/rediacc/.rediacc \
  rediacc/cli:dev /bin/bash
```

### Debugging
```bash
# Run with verbose output
docker run --rm -e REDIACC_VERBOSE=1 rediacc/cli:latest ./rediacc list teams

# Check image contents
docker run --rm rediacc/cli:latest ls -la /app
```

## Publishing Images

To publish to a registry:

```bash
# Tag for registry
docker tag rediacc/cli:latest registry.example.com/rediacc/cli:latest

# Push image
docker push registry.example.com/rediacc/cli:latest
```