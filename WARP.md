# Rediacc CLI - WARP Development Guide

This document provides comprehensive guidance for working with the Rediacc CLI codebase in Warp terminal, including common commands, architecture overview, and troubleshooting information.

## Table of Contents

- [Quick Start](#quick-start)
- [Common Commands](#common-commands)
- [Architecture Overview](#architecture-overview)
- [Development Workflow](#development-workflow)
- [Platform-Specific Notes](#platform-specific-notes)
- [Testing](#testing)
- [Troubleshooting](#troubleshooting)
- [Protocol Handler](#protocol-handler)
- [Docker Support](#docker-support)
- [Contributing](#contributing)

## Quick Start

### Initial Setup
```bash
# Clone and setup the CLI
git clone <repository-url>
cd cli
python3 rediacc.py setup

# Run setup with verbose logging (recommended for troubleshooting)
python3 rediacc.py setup --verbose
```

### Configuration
```bash
# Copy environment template
cp .env.example .env

# Edit configuration
nano .env  # or use your preferred editor
```

### Basic Usage
```bash
# Launch desktop application
python3 rediacc.py desktop

# Login to Rediacc
python3 rediacc.py login

# File synchronization
python3 rediacc.py sync --help

# Terminal access
python3 rediacc.py term --help

# Plugin management
python3 rediacc.py plugin --help
```

## Common Commands

### Core Operations
| Command | Description | Example |
|---------|-------------|---------|
| `python3 rediacc.py login` | Authenticate with Rediacc API | Interactive login process |
| `python3 rediacc.py sync` | File synchronization operations | `sync --team myteam --repo myrepo` |
| `python3 rediacc.py term` | Terminal access to repositories | `term --team myteam --machine server01` |
| `python3 rediacc.py plugin` | Manage SSH tunnels/connections | `plugin list` |
| `python3 rediacc.py desktop` | Launch GUI application | Desktop mode selection |

### Development & Testing
| Command | Description | Example |
|---------|-------------|---------|
| `python3 rediacc.py setup` | Install dependencies and check environment | Auto-installs MSYS2 on Windows |
| `python3 rediacc.py test` | Run all tests | Full test suite execution |
| `python3 rediacc.py test desktop` | Run GUI tests | Desktop application tests |
| `python3 rediacc.py test yaml` | Run YAML-based tests | Workflow validation tests |
| `python3 rediacc.py test protocol` | Run protocol handler tests | Browser integration tests |

### Protocol Registration
| Command | Description | Platform |
|---------|-------------|----------|
| `python3 rediacc.py protocol register` | Register rediacc:// protocol | All platforms |
| `python3 rediacc.py protocol register --system-wide` | System-wide registration | Windows/Linux |
| `python3 rediacc.py protocol unregister` | Unregister protocol | All platforms |
| `python3 rediacc.py protocol status` | Check registration status | All platforms |

### Docker Operations
| Command | Description | Use Case |
|---------|-------------|----------|
| `python3 rediacc.py docker-build` | Build CLI Docker image | Development setup |
| `python3 rediacc.py docker-run` | Run CLI in container | Isolated execution |
| `python3 rediacc.py docker-shell` | Interactive Docker shell | Container debugging |
| `python3 rediacc.py desktop docker` | Run desktop app in Docker | Cross-platform GUI |

### License Management
| Command | Description | Example |
|---------|-------------|---------|
| `python3 rediacc.py license generate-id` | Generate hardware ID | Offline licensing |
| `python3 rediacc.py license request -i hw-id.txt` | Request license file | Using hardware ID |
| `python3 rediacc.py license install -f license.lic` | Install license | Activate license |

## Architecture Overview

### Directory Structure
```
cli/
├── src/cli/                    # Core CLI modules
│   ├── core/                  # Core functionality
│   │   ├── config.py         # Configuration management
│   │   ├── api_client.py     # API communication
│   │   ├── sync_client.py    # File synchronization
│   │   ├── terminal_detector.py # Terminal launching
│   │   ├── protocol_handler.py # Protocol handling
│   │   └── msys2_installer.py # Windows MSYS2 support
│   ├── gui/                   # Desktop application
│   │   ├── main.py          # Main GUI window
│   │   ├── settings.py      # Settings dialog
│   │   └── terminal_launcher.py # Terminal integration
│   └── commands/              # CLI commands
├── tests/                     # Test suite
│   ├── gui/                  # GUI tests
│   ├── protocol/             # Protocol tests
│   ├── workflow/             # Workflow tests
│   └── yaml/                 # YAML test definitions
├── docker/                    # Docker configurations
├── rediacc.py                # Main CLI entry point
├── rediacc.bat               # Windows batch wrapper
└── requirements.txt          # Python dependencies
```

### Key Components

#### 1. Main CLI (`rediacc.py`)
- **Purpose**: Primary entry point and command router
- **Key Features**:
  - Command parsing and routing
  - Environment setup and validation
  - Cross-platform compatibility
  - Telemetry and error handling

#### 2. Core Modules (`src/cli/core/`)
- **config.py**: Configuration management, token storage, environment setup
- **api_client.py**: REST API communication with Rediacc backend
- **sync_client.py**: File synchronization using rsync
- **terminal_detector.py**: Cross-platform terminal launching logic
- **protocol_handler.py**: Browser protocol integration (rediacc://)
- **msys2_installer.py**: Windows MSYS2 auto-installation for rsync support

#### 3. Desktop Application (`src/cli/gui/`)
- **main.py**: Main GUI window with menu integration
- **terminal_launcher.py**: GUI-initiated terminal launching
- **settings.py**: Configuration dialogs

#### 4. Testing Infrastructure (`tests/`)
- **Unit Tests**: pytest-based test suite
- **YAML Tests**: Workflow validation via `run_tests.py`
- **Protocol Tests**: Browser integration testing
- **GUI Tests**: Desktop application validation

## Development Workflow

### Setting Up Development Environment
```bash
# Clone repository
git clone <repository-url>
cd cli

# Set up environment
python3 rediacc.py setup --verbose

# Install development dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your configuration
```

### Making Changes
```bash
# Create feature branch
git checkout -b feature/my-feature

# Make changes and test
python3 rediacc.py test

# Test specific components
python3 rediacc.py test desktop
python3 rediacc.py test protocol

# Commit changes
git add .
git commit -m "Description of changes"

# Push to remote
git push origin feature/my-feature
```

### Testing Your Changes
```bash
# Run full test suite
python3 rediacc.py test

# Test specific areas
python3 rediacc.py test gui      # Desktop application
python3 rediacc.py test yaml     # Workflow tests
python3 rediacc.py test protocol # Browser integration

# Manual testing
python3 rediacc.py desktop       # Test GUI
python3 rediacc.py protocol register # Test protocol
```

## Platform-Specific Notes

### Windows Development

#### Terminal Launcher Fix
The GUI "Tools → Machine Terminal" feature previously failed on Windows with "'rediacc.bat' is not recognized". This has been fixed to:
1. Prefer installed `rediacc.exe` from pip packages
2. Fall back to local development scripts
3. Use Python module execution as final fallback

#### MSYS2 Integration
The setup command now automatically installs MSYS2 with rsync on Windows:
- Downloads and installs MSYS2 silently
- Installs rsync package via pacman
- Adds MSYS2 to PATH for current session
- Provides manual installation instructions on failure

#### Protocol Registration
```powershell
# Register protocol (run as administrator for system-wide)
python3 rediacc.py protocol register --system-wide

# Check registration
python3 rediacc.py protocol status
```

### macOS/Linux Development

#### Dependencies
```bash
# Ubuntu/Debian
sudo apt-get install python3-tk rsync ssh

# macOS
brew install rsync
# tkinter included with Python
```

#### Protocol Registration
```bash
# Register protocol
python3 rediacc.py protocol register

# For system-wide (Linux)
python3 rediacc.py protocol register --system-wide
```

### WSL (Windows Subsystem for Linux)

The CLI fully supports WSL environments:
- Terminal launching uses WSL-specific paths
- File synchronization works across WSL/Windows boundary
- GUI applications launch via X11 forwarding or native Windows

## Testing

### Test Categories

#### 1. Unit Tests (pytest)
```bash
# All tests
python3 rediacc.py test

# Specific test files
python3 rediacc.py test tests/test_specific.py

# With coverage
python3 rediacc.py test --cov=src/cli
```

#### 2. YAML-Based Tests
```bash
# Run YAML test suite
python3 rediacc.py test yaml

# Specific test file
python3 rediacc.py test yaml tests/yaml/sync_test.yaml

# List available tests
python3 tests/run_tests.py --list
```

#### 3. Desktop/GUI Tests
```bash
# GUI test suite
python3 rediacc.py test desktop

# Specific GUI tests
python3 rediacc.py test desktop tests/gui/test_main_window.py
```

#### 4. Protocol Handler Tests
```bash
# Protocol integration tests
python3 rediacc.py test protocol

# Manual protocol testing
python3 rediacc.py protocol-server
# Then visit http://localhost:8765 for test page
```

### Test Data and Configuration

#### Test Environment
- Tests use isolated configuration in `tests/.test_env`
- Mock API responses defined in `tests/fixtures/`
- Temporary directories for file operations

#### Continuous Integration
- GitHub Actions workflows in `.github/workflows/`
- Cross-platform testing (Windows, macOS, Linux)
- Docker-based testing environment

## Troubleshooting

### Common Issues

#### 1. "rediacc.bat is not recognized" (Windows)
**Problem**: GUI terminal launcher fails on Windows
**Solution**: Already fixed in latest version. Update to use installed `rediacc.exe` or local scripts.

#### 2. "rsync not found" (Windows)
**Problem**: Missing rsync dependency on Windows
**Solution**: Run `python3 rediacc.py setup` - now auto-installs MSYS2 with rsync

#### 3. Desktop application won't start
**Problem**: Missing tkinter dependency
**Solutions**:
- Ubuntu/Debian: `sudo apt-get install python3-tk`
- Windows: Ensure Python was installed with tkinter
- macOS: tkinter should be included with Python

#### 4. Protocol handler not working
**Problem**: Browser doesn't recognize rediacc:// URLs
**Solution**:
```bash
# Re-register protocol
python3 rediacc.py protocol unregister
python3 rediacc.py protocol register

# Check status
python3 rediacc.py protocol status
```

#### 5. Import errors in development
**Problem**: Module import failures
**Solution**:
```bash
# Ensure src directory is in Python path
export PYTHONPATH="${PYTHONPATH}:$(pwd)/src"

# Or run from CLI root directory
cd /path/to/cli
python3 rediacc.py <command>
```

### Debug Mode

#### Enable Verbose Logging
```bash
# Environment variable
export REDIACC_DEBUG=1
python3 rediacc.py <command>

# Command flag
python3 rediacc.py <command> --verbose
```

#### Protocol Debugging
```bash
# Start test server for protocol testing
python3 rediacc.py protocol-server

# Visit http://localhost:8765 for test interface
# Check protocol registration and URL handling
```

### Log Files and Diagnostics

#### Log Locations
- **Windows**: `%APPDATA%/Rediacc/logs/`
- **macOS**: `~/Library/Application Support/Rediacc/logs/`
- **Linux**: `~/.config/Rediacc/logs/`

#### Configuration Files
- **Main config**: `.env` in CLI root
- **User settings**: Platform-specific config directories
- **Token storage**: Secure credential storage per platform

## Protocol Handler

### Overview
The protocol handler enables browser integration through `rediacc://` URLs, allowing one-click access to terminals, file operations, and other CLI functions.

### Registration
```bash
# Register for current user
python3 rediacc.py protocol register

# Register system-wide (requires admin/sudo)
python3 rediacc.py protocol register --system-wide

# Check registration status
python3 rediacc.py protocol status

# Unregister
python3 rediacc.py protocol unregister
```

### URL Format
```
rediacc://action?param1=value1&param2=value2
```

#### Supported Actions
- `terminal`: Open machine terminal
- `sync`: Initiate file synchronization
- `plugin`: Manage plugin connections

#### Examples
```
rediacc://terminal?team=myteam&machine=server01
rediacc://sync?team=myteam&repo=myrepo&direction=push
rediacc://plugin?action=connect&team=myteam&plugin=database
```

### Testing Protocol Integration
```bash
# Start test server
python3 rediacc.py protocol-server --port 8765

# Visit test interface
# Open http://localhost:8765 in browser
# Test various protocol URLs and parameter combinations
```

## Docker Support

### Building Images
```bash
# Build CLI Docker image
python3 rediacc.py docker-build

# Verify image creation
docker images | grep rediacc
```

### Running in Docker
```bash
# Run CLI command in container
python3 rediacc.py docker-run login

# Interactive shell
python3 rediacc.py docker-shell

# Desktop application in Docker
python3 rediacc.py desktop docker
```

### Docker Configuration
- **Dockerfile**: `docker/Dockerfile`
- **User**: Non-root user `rediacc` (UID: 7111)
- **Volumes**: Mounts `.config`, `.ssh`, and working directory
- **Network**: Host networking for local development

### Development with Docker
```bash
# Build and run tests in Docker
python3 rediacc.py docker-build
python3 rediacc.py docker-run test

# Development workflow
python3 rediacc.py docker-shell
# Inside container:
# cd /workspace
# python3 rediacc.py test
```

## Contributing

### Code Style
- Follow PEP 8 Python style guidelines
- Use type hints where appropriate
- Document all public functions and classes
- Add unit tests for new functionality

### Pull Request Process
1. Fork the repository
2. Create feature branch
3. Make changes with tests
4. Update documentation
5. Submit pull request with description

### Testing Requirements
- All new code must include unit tests
- Integration tests for GUI components
- Protocol handler tests for browser features
- Cross-platform compatibility verification

### Development Guidelines
- Maintain backward compatibility
- Follow existing architecture patterns
- Handle errors gracefully with user-friendly messages
- Support all target platforms (Windows, macOS, Linux, WSL)

---

## Quick Reference

### Essential Commands
```bash
python3 rediacc.py setup           # Initial setup
python3 rediacc.py login           # Authenticate
python3 rediacc.py desktop         # Launch GUI
python3 rediacc.py test            # Run tests
python3 rediacc.py protocol register # Enable browser integration
```

### Key Files to Know
- `rediacc.py` - Main entry point
- `src/cli/core/config.py` - Configuration
- `src/cli/gui/main.py` - Desktop application
- `src/cli/core/protocol_handler.py` - Browser integration
- `.env` - Environment configuration

### Getting Help
```bash
python3 rediacc.py help            # Command overview
python3 rediacc.py <command> --help # Command-specific help
python3 rediacc.py test --help     # Testing options
```

This guide covers the essential aspects of working with the Rediacc CLI codebase. For specific implementation details, refer to the source code and inline documentation.