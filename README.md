# Rediacc CLI and Desktop

This directory contains the Rediacc command-line tools and Rediacc Desktop GUI application.

## Configuration

The CLI requires configuration via environment variables. Copy `.env.example` to `.env` and update with your values:

```bash
cp .env.example .env
# Edit .env with your configuration
```

Required configuration:
- `SYSTEM_HTTP_PORT`: API server port (e.g., 7322)
- `SYSTEM_API_URL`: Full API URL (e.g., http://localhost:7322/api)

See `.env.example` for all available configuration options.

## Quick Start

```bash
# Linux/macOS
./rediacc login          # Authenticate
./rediacc gui            # Launch Rediacc Desktop GUI
./rediacc desktop        # Alternative for GUI

# Windows
.\rediacc.ps1 login      # Authenticate
.\rediacc.ps1 gui        # Launch Rediacc Desktop GUI
```

## Directory Structure

```
cli/
├── rediacc             # Linux/macOS wrapper script
├── rediacc.ps1         # Windows PowerShell wrapper
├── src/                # Python source code
│   ├── cli/           # CLI executables
│   ├── modules/       # Shared Python modules
│   └── config/        # Configuration files
├── docs/              # Documentation
├── docker/            # Docker files
├── scripts/           # Setup and utility scripts
└── tests/             # Test files
```

## Documentation

- [Main Documentation](docs/README.md) - Complete guide to all CLI tools
- [GUI Documentation](docs/GUI_README.md) - Rediacc Desktop documentation
- [Platform Guides](docs/guides/) - Platform-specific troubleshooting

## Installation

See [docs/README.md](docs/README.md) for detailed installation instructions.

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

## License

Part of the Rediacc monorepo. See the main repository for license information.