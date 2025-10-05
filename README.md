# Rediacc CLI - Infrastructure Automation Platform

[![CI Test Suite](https://github.com/rediacc/cli/actions/workflows/test-cli.yml/badge.svg)](https://github.com/rediacc/cli/actions/workflows/test-cli.yml)
[![codecov](https://codecov.io/gh/rediacc/cli/branch/main/graph/badge.svg)](https://codecov.io/gh/rediacc/cli)
[![PyPI version](https://badge.fury.io/py/rediacc.svg)](https://badge.fury.io/py/rediacc)
[![Python Versions](https://img.shields.io/pypi/pyversions/rediacc.svg)](https://pypi.org/project/rediacc/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

Command-line tools for the Rediacc Infrastructure Automation Platform.

## Overview

Rediacc is an infrastructure automation platform that enables:
- **Accelerated Development Operations**: Instant environment provisioning and production-like testing environments
- **Next-Generation Disaster Recovery**: Continuous snapshots with 5X-10X reduction in backup overhead
- **AI-Safe Infrastructure Operations**: Instant production clones for safe AI system interactions

The CLI provides command-line access to Rediacc's distributed task execution system, resource management, and remote infrastructure operations

## Configuration

The CLI requires configuration via environment variables:

```bash
cp .env.example .env
# Edit .env with your API settings
```

Required:
- `SYSTEM_HTTP_PORT`: API port (e.g., 7322)
- `SYSTEM_API_URL`: API URL (e.g., http://localhost:7322/api)

## Quick Start

```bash
# Linux/macOS
./rediacc setup --auto          # Install dependencies
./rediacc login                 # Authenticate with API
./rediacc list teams            # List available teams
./rediacc list team-machines    # List machines
./rediacc sync upload --help    # File synchronization
./rediacc term --help           # Terminal access
./rediacc desktop               # Launch desktop application

# Windows
rediacc.bat setup --auto
rediacc.bat login
rediacc.bat list teams
rediacc.bat desktop
```

## Directory Structure

```
cli/
├── rediacc             # Linux/macOS wrapper script
├── rediacc.bat         # Windows batch wrapper
├── src/                # Python source code
│   ├── cli/           # CLI executables
│   ├── modules/       # Shared Python modules
│   └── config/        # Configuration files
├── docs/              # Documentation
├── docker/            # Docker files
├── scripts/           # Setup and utility scripts
└── tests/             # Test files
```

## Key Features

### Core Tools
- **rediacc**: Main CLI for API operations and resource management
- **rediacc sync**: File synchronization using rsync over SSH
- **rediacc term**: Interactive SSH terminal access to repositories
- **rediacc plugin**: SSH tunnel management for secure connections
- **rediacc desktop**: GUI application for visual system management

### Capabilities
- Distributed task execution via queue system
- Secure credential storage with vault encryption
- Cross-platform support (Linux, macOS, Windows)
- Team and machine resource management
- Repository and storage operations
- Audit logging and session management

## Documentation

- [Complete CLI Guide](docs/README.md) - All commands and features
- [Desktop Application](docs/DESKTOP.md) - Desktop application interface
- [System Architecture](../CLAUDE.md) - Communication flow and component architecture
- [Installation Guide](docs/INSTALLATION.md) - Detailed installation instructions

## Installation

For PyPI: `pip install rediacc`

For local development: See [docs/README.md](docs/README.md)

## Docker Support

The CLI can also be run using Docker.

**Important**: Docker volumes now use a local config directory (`./cli/.config`) instead of the user's home directory (`~/.config`). This provides better isolation and portability for containerized environments.

### Running with Docker

```bash
# Build image
docker build -f docker/Dockerfile -t rediacc/cli:latest .

# Run CLI
docker run --rm -v ./cli/.config:/home/rediacc/.config rediacc/cli:latest

# Interactive shell
docker run -it --rm -v ./cli/.config:/home/rediacc/.config rediacc/cli:latest /bin/bash
```

See [docker/README.md](docker/README.md) for complete Docker documentation including details about the local config directory.

## Support

For issues or questions:
- Check the [documentation](docs/README.md)
- Review the [troubleshooting guide](docs/TROUBLESHOOTING.md)
- Visit https://www.rediacc.com for platform information

## License

Proprietary - Part of the Rediacc infrastructure automation platform.