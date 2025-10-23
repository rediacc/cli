# Rediacc CLI - Command-Line Tools for Rediacc Platform

Command-line interface for managing your Rediacc infrastructure automation platform.

## What This Is

This package provides CLI tools to interact with the Rediacc platform via API. The CLI lets you manage teams, machines, repositories, storage, and distributed task queues from your terminal.

**Note:** This is a client tool. Infrastructure features (cloning, snapshots, disaster recovery) are provided by the Rediacc platform service, which requires an account and backend infrastructure.

## Installation

```bash
pip install rediacc
```

## Prerequisites

- Python 3.8 or higher
- Rediacc account (sign up at https://rediacc.com)
- Access to a Rediacc backend service

## Quick Start

```bash
# Install
pip install rediacc

# Initial setup (registers protocol handler)
rediacc setup

# Authenticate with your Rediacc account
rediacc login

# View available teams
rediacc cli list teams

# List machines in a team
rediacc cli list team-machines --team YourTeam

# Create a repository
rediacc cli create repository --name myrepo --team YourTeam

# Add a task to the queue
rediacc cli queue add --function backup --team YourTeam --machine mymachine

# View queue status
rediacc cli queue list --team YourTeam
```

## Available Commands

### Authentication
- `rediacc login` - Authenticate with Rediacc API
- `rediacc logout` - End current session

### Resource Management
- `rediacc cli list` - List resources (teams, machines, repositories, regions, bridges, etc.)
- `rediacc cli create` - Create resources (company, team, machine, repository, storage, etc.)
- `rediacc cli update` - Update resource configurations
- `rediacc cli delete` - Remove resources

### Queue Operations
- `rediacc cli queue add` - Add tasks to distributed queue
- `rediacc cli queue list` - View queued tasks
- `rediacc cli queue list-functions` - Show available queue functions

### Configuration
- `rediacc cli vault` - Manage encrypted credentials
- `rediacc cli permission` - Manage user permissions
- `rediacc cli user` - User management operations

### Workflows
- `rediacc cli workflow repo-create` - Automated repository creation
- `rediacc cli workflow repo-push` - Push repository to storage/machine
- `rediacc cli workflow machine-setup` - Set up new machines

### Utilities
- `rediacc setup` - Initial setup and configuration
- `rediacc protocol` - Manage rediacc:// URL handler
- `rediacc license` - License management (offline/online)
- `rediacc version` - Show version information
- `rediacc help` - Display help

## CLI Tools

This package installs several command-line tools:

- **rediacc** - Main CLI for API operations and resource management
- **rediacc-sync** - File synchronization (requires rsync)
- **rediacc-term** - SSH terminal access to repositories
- **rediacc-plugin** - SSH tunnel management
- **rediacc-desktop** - GUI application (if available)

## Platform Support

- Linux (Ubuntu, RHEL, Debian, etc.)
- macOS (Intel & Apple Silicon)
- Windows (via PowerShell, MSYS2 recommended for sync features)
- Docker containers
- CI/CD pipelines (Jenkins, GitHub Actions, GitLab CI)

## Configuration

The CLI stores configuration in `~/.config/rediacc/`:
- Authentication tokens
- API endpoints
- Encrypted vault credentials (if company has vault encryption enabled)

Environment variables can override configuration:
- `SYSTEM_API_URL` - API endpoint URL
- `SYSTEM_HTTP_PORT` - API port
- `REDIACC_SANDBOX_MODE` - Use sandbox environment

## Docker Support

Run the CLI in Docker for isolated environments:

```bash
# Build image
docker build -f docker/Dockerfile -t rediacc/cli:latest .

# Run CLI
docker run --rm -v ./cli/.config:/home/rediacc/.config rediacc/cli:latest rediacc login

# Interactive shell
docker run -it --rm -v ./cli/.config:/home/rediacc/.config rediacc/cli:latest /bin/bash
```

## Output Formats

All commands support multiple output formats:

```bash
# Human-readable (default)
rediacc cli list teams

# JSON output
rediacc cli list teams --output json

# Detailed JSON (includes metadata)
rediacc cli list teams --output json-full
```

## About the Rediacc Platform

The Rediacc platform (accessed via this CLI) provides:

- **Infrastructure Automation**: Distributed task execution and resource management
- **Snapshot Technology**: Copy-on-Write based repository cloning and versioning
- **Disaster Recovery**: Point-in-time recovery capabilities
- **Distributed Storage**: Multi-region storage orchestration
- **Queue System**: Distributed task queue with priority scheduling

These features require a Rediacc platform subscription. The CLI is the management interface.

## Use Cases

- Automate infrastructure provisioning and deployment
- Manage distributed teams and machines
- Schedule backup and sync operations via queues
- Integrate Rediacc operations into CI/CD pipelines
- Manage repositories and storage across multiple regions

## Documentation

- **CLI Documentation**: See `docs/README.md` in the repository
- **Platform Documentation**: https://rediacc.com/docs
- **API Reference**: https://rediacc.com/docs/cli/api-reference

## Common Commands Reference

```bash
# Authentication
rediacc login                                    # Login to your account
rediacc logout                                   # Logout

# List resources
rediacc cli list teams                           # Show all teams
rediacc cli list team-machines --team MyTeam     # Show machines in team
rediacc cli list repositories --team MyTeam      # Show repositories

# Create resources
rediacc cli create repository --name myrepo --team MyTeam
rediacc cli create machine --name mymachine --team MyTeam --region us-west

# Queue operations
rediacc cli queue add --function backup --team MyTeam --machine mymachine
rediacc cli queue list --team MyTeam
rediacc cli queue list-functions                 # No auth required

# License management
rediacc license generate-id                      # Generate machine ID
rediacc license request                          # Request license file
rediacc license install                          # Install license
```

## Troubleshooting

### Authentication Issues
```bash
# Check if authenticated
rediacc cli auth status

# Re-login if token expired
rediacc logout
rediacc login
```

### Configuration Issues
```bash
# Check configuration directory
ls ~/.config/rediacc/

# Run setup to reconfigure
rediacc setup
```

### rsync/sync Issues
On Windows, install MSYS2 for full sync functionality:
```bash
# Install MSYS2, then:
pacman -S rsync openssh
```

## Support

- **GitHub Issues**: https://github.com/rediacc/cli/issues
- **Documentation**: https://docs.rediacc.com
- **Website**: https://www.rediacc.com

## License

Proprietary - Part of the Rediacc infrastructure automation platform.

---

**Getting Started**

1. Install: `pip install rediacc`
2. Setup: `rediacc setup`
3. Login: `rediacc login`
4. Explore: `rediacc help`
