# Dockerfile Requirements Analysis for Rediacc CLI

## Missing Requirements Identified and Fixed

### 1. **rsync** (CRITICAL)
- **Purpose**: Required by `rediacc-cli-sync` for file synchronization operations
- **Usage**: The sync command uses rsync to transfer files between local and remote repositories
- **Fix**: Added `rsync` to the apk package list

### 2. **Build Dependencies for cryptography**
- **Purpose**: Required to compile the Python cryptography library
- **Packages Added**:
  - `build-base`: Alpine's meta-package for build tools
  - `libffi-dev`: Required by cryptography
  - `openssl-dev`: Required by cryptography
  - `python3-dev`: Python development headers
- **Fix**: Added these packages to support pip install cryptography

### 3. **Python cryptography Library**
- **Purpose**: Provides vault encryption functionality
- **Usage**: Optional but recommended for secure vault data handling
- **Fix**: Added `pip install --no-cache-dir cryptography`

### 4. **Executable Permissions**
- **Files**: rediacc, rediacc-cli, rediacc-cli-sync, rediacc-cli-term, go
- **Purpose**: These Python scripts need execute permissions to run as commands
- **Fix**: Added explicit chmod +x for all executable scripts

### 5. **SSH Directory Structure**
- **Purpose**: CLI creates temporary SSH keys for connections
- **Fix**: Created `/home/rediacc/.ssh` with proper permissions (700)

### 6. **Configuration Directory**
- **Purpose**: CLI stores tokens and configuration in ~/.rediacc
- **Fix**: Created `/home/rediacc/.rediacc` with proper permissions (700)

### 7. **Environment Variables**
- **Added**:
  - `SYSTEM_HTTP_PORT=7322`: Default API port
  - `REDIACC_API_URL=http://localhost:7322/api`: Default API endpoint
- **Purpose**: Provides sensible defaults for containerized environment

### 8. **Default Command**
- **Changed**: From `/bin/bash` to `./rediacc help`
- **Purpose**: Shows help when container runs without arguments

## Python Dependencies Summary

### Standard Library (No installation needed):
- argparse, base64, datetime, getpass, hashlib, json, logging
- os, pathlib, platform, re, shutil, subprocess, sys
- tempfile, typing, urllib

### Internal Modules (Copied in Dockerfile):
- rediacc_cli_core
- rediacc_cli_platform
- token_manager

### External Dependencies:
- cryptography (optional, but installed for full functionality)

## Integration with Monorepo

The CLI integrates with the main monorepo through:
1. The `cli/go` script that provides docker_build, docker_run commands
2. Following the same security patterns (non-root user, UID/GID 111)
3. Using shared environment variables from parent .env file

## Security Considerations

1. Non-root user execution (rediacc:rediacc with UID/GID 111)
2. Secure permissions on .ssh (700) and .rediacc (700) directories
3. No hardcoded credentials or tokens
4. Temporary SSH keys are properly managed and cleaned up

## Testing the Docker Image

```bash
# Build the image
./go docker_build

# Test basic functionality
docker run --rm rediacc-cli:latest ./rediacc help

# Test with volume mounts for persistent config
docker run -it --rm \
  -v "$HOME/.rediacc:/home/rediacc/.rediacc" \
  rediacc-cli:latest \
  ./rediacc-cli list teams

# Test sync functionality
docker run -it --rm \
  -v "$HOME/.rediacc:/home/rediacc/.rediacc" \
  -v "$PWD:/workspace" \
  rediacc-cli:latest \
  ./rediacc-cli-sync --help
```