# Rediacc CLI Docker Setup

This document describes the Docker setup for the Rediacc CLI tool.

## Features

- **Alpine-based Python 3.11** image for minimal size
- **Non-root user** (rediacc:rediacc) with UID/GID 111 for security
- **All required dependencies** including rsync for sync operations
- **Volume mounts** for configuration and SSH keys
- **Health checks** to ensure CLI responsiveness
- **Auto-build** feature when running containers

## Quick Start

### Build the Docker image
```bash
./go cli docker_build
```

### Run CLI commands in Docker
```bash
# Login
./go cli docker_run login --email user@example.com

# List teams
./go cli docker_run list teams

# Sync files
./go cli docker_run sync /local/path remote:path
```

### Interactive shell
```bash
./go cli docker_shell
```

## Docker Compose

For more complex workflows, use docker-compose:

```bash
# Start CLI service
docker-compose -f cli/docker-compose.yml up cli

# Run tests
docker-compose -f cli/docker-compose.yml run cli-test

# Interactive shell
docker-compose -f cli/docker-compose.yml run cli-shell
```

## Volume Mounts

The Docker container mounts these directories:

- `~/.rediacc` → `/home/rediacc/.rediacc` - CLI configuration and tokens
- `~/.ssh` → `/home/rediacc/.ssh` (read-only) - SSH keys for authentication
- Current directory → `/workspace` - Access to local files

## Network

The container runs with `--network host` to allow easy access to local services.

## Security

- Runs as non-root user (rediacc:rediacc)
- SSH keys mounted as read-only
- Minimal Alpine Linux base image
- Only necessary dependencies installed

## Environment Variables

- `SYSTEM_HTTP_PORT` - Default: 7322
- `REDIACC_API_URL` - Default: http://localhost:7322/api

## Troubleshooting

### Permission Issues
If you encounter permission issues with mounted volumes:
```bash
# Ensure .rediacc directory exists with correct permissions
mkdir -p ~/.rediacc
chmod 700 ~/.rediacc
```

### Build Issues
If the build fails:
```bash
# Clean Docker cache and rebuild
docker system prune -f
./go cli docker_build --no-cache
```

### Connection Issues
If CLI can't connect to API:
- Check if the API is running on the host
- Verify `REDIACC_API_URL` environment variable
- Ensure `--network host` is used