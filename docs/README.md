# Rediacc CLI Documentation

The Rediacc CLI provides command-line tools for interacting with the Rediacc distributed task execution system.

## Overview

The CLI consists of three main tools:

1. **rediacc-cli** - Main CLI for API operations and system management
2. **rediacc-cli-sync** - File synchronization tool using rsync
3. **rediacc-cli-term** - Terminal access to remote machines and repositories

## Quick Start

### Installation

```bash
# Linux/macOS
./install.sh --auto

# Windows (PowerShell)
.\rediacc.ps1 setup -AutoInstall

# Manual setup
./rediacc setup
```

### Authentication

```bash
# Interactive login
./rediacc login

# With credentials
./rediacc login --email user@example.com --password yourpassword

# Using token directly
./rediacc-cli --token YOUR_TOKEN list teams
```

## Documentation Index

### Core Documentation
- [Installation Guide](INSTALLATION.md) - Detailed installation instructions
- [Authentication](AUTHENTICATION.md) - Token management and authentication
- [Command Reference](COMMANDS.md) - Complete command reference

### Tool-Specific Guides
- [File Synchronization](SYNC.md) - Using rediacc-cli-sync
- [Terminal Access](TERMINAL.md) - Using rediacc-cli-term
- [API Operations](API.md) - Using rediacc-cli for API calls

### Advanced Topics
- [Configuration](guides/CONFIGURATION.md) - Configuration files and environment variables
- [Troubleshooting](guides/TROUBLESHOOTING.md) - Common issues and solutions
- [Development Mode](guides/DEVELOPMENT.md) - Development and debugging features

## System Requirements

### All Platforms
- Python 3.6 or higher
- Internet connection

### Platform-Specific
- **Linux/macOS**: bash, rsync, openssh
- **Windows**: PowerShell, MSYS2 (for rsync functionality)

## Basic Usage Examples

### List Resources
```bash
# List all teams
./rediacc-cli list teams

# List machines in a team
./rediacc-cli list machines --team Default

# List repositories
./rediacc-cli list repositories --team Default
```

### File Operations
```bash
# Upload files
./rediacc sync upload --local ./myproject --machine server --repo webapp

# Download files
./rediacc sync download --machine server --repo webapp --local ./backup

# Mirror directories
./rediacc sync upload --local ./src --machine server --repo code --mirror
```

### Terminal Access
```bash
# Access repository environment
./rediacc term --machine server --repo webapp

# Execute single command
./rediacc term --machine server --command "docker ps"

# Access machine directly
./rediacc term --machine server
```

## Support

For issues or feedback, please visit: https://github.com/anthropics/claude-code/issues