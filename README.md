# Rediacc CLI

A command-line interface for the Rediacc platform that provides access to all functionality available through the Rediacc middleware service.

## Overview

The Rediacc CLI is a Go-based application that communicates with the Rediacc middleware via HTTP/REST API, which in turn interfaces with the SQL Server database through stored procedures.

## Architecture

```
┌─────────────────┐    HTTP/REST    ┌──────────────────┐    SQL    ┌─────────────────┐
│                 │ ──────────────→ │                  │ ────────→ │                 │
│   Rediacc CLI   │                 │    Middleware    │           │   SQL Server    │
│   (Go Binary)   │ ←────────────── │   (.NET API)     │ ←──────── │   (Database)    │
└─────────────────┘    JSON         └──────────────────┘           └─────────────────┘
```

## Installation

### From Source

```bash
# Clone the repository
git clone <repository-url>
cd cli

# Build the CLI
go build -o bin/rediacc main.go

# Install globally (optional)
sudo mv bin/rediacc /usr/local/bin/
```

### Using Go Install

```bash
go install github.com/rediacc/cli@latest
```

## Quick Start

1. **Initialize configuration:**
   ```bash
   rediacc config init
   ```

2. **Login to your account:**
   ```bash
   rediacc auth login --email your@email.com
   ```

3. **List available commands:**
   ```bash
   rediacc --help
   ```

## Configuration

The CLI uses a configuration file located at `~/.rediacc-cli.yaml`. You can specify a different location using the `--config` flag.

### Default Configuration

```yaml
server:
  url: "http://localhost:8080"
  timeout: "30s"

auth:
  email: ""
  session_token: ""
  request_credential: ""

jobs:
  default_datastore_size: "100G"
  ssh_timeout: "30s"
  ssh_key_path: "~/.ssh/id_rsa"
  machines: []

format:
  default: "table"
  colors: true
  timestamps: true

ssh:
  timeout: "30s"
  retry_attempts: 3
  retry_delay: "5s"
```

## Available Commands

### Authentication
- `auth login` - Login to Rediacc
- `auth logout` - Logout from current session
- `auth user` - User management commands
- `auth 2fa` - Two-factor authentication commands

### Company Management
- `company create` - Create a new company
- `company info` - Get company information
- `company users` - Manage company users
- `company limits` - View resource limits
- `company vault` - Manage company vault
- `company subscription` - View subscription details

### Permission Management
- `permissions groups` - Manage permission groups
- `permissions add` - Add permissions to groups
- `permissions remove` - Remove permissions from groups
- `permissions assign` - Assign users to permission groups

### Team Management
- `teams list` - List teams
- `teams create` - Create teams
- `teams delete` - Delete teams
- `teams members` - Manage team members
- `teams vault` - Manage team vaults

### Infrastructure Management
- `infra regions` - Manage regions
- `infra bridges` - Manage bridges
- `infra machines` - Manage machines

### Storage Management
- `storage list` - List storage
- `storage create` - Create storage
- `storage repos` - Manage repositories

### Schedule Management
- `schedules list` - List schedules
- `schedules create` - Create schedules
- `schedules update` - Update schedules

### Queue Management
- `queue list` - List queue items
- `queue add` - Add queue items
- `queue response` - Manage responses

### Job Management
- `jobs machine` - Machine operations
- `jobs repo` - Repository operations
- `jobs plugin` - Plugin management
- `jobs terminal` - Terminal access

### Configuration
- `config init` - Initialize configuration
- `config set` - Set configuration values
- `config get` - Get configuration values
- `config list` - List current configuration

### Raw Operations
- `raw exec` - Execute raw stored procedures
- `raw list` - List available procedures

## Output Formats

The CLI supports multiple output formats:

- **Table** (default): Human-readable tabular format
- **JSON**: Machine-readable JSON format
- **YAML**: YAML format for configuration files
- **Text**: Simple text format

Use the `--output` or `-o` flag to specify the format:

```bash
rediacc teams list --output json
rediacc company info -o yaml
```

## Global Flags

- `--config`: Specify configuration file path
- `--debug`: Enable debug mode
- `--output, -o`: Set output format (table, json, yaml, text)

## Examples

### Basic Workflow

```bash
# Login
rediacc auth login --email admin@company.com

# Create a team
rediacc teams create "development-team"

# Create a region
rediacc infra regions create "us-east-1"

# Create a bridge
rediacc infra bridges create --region "us-east-1" "main-bridge"

# Add a machine
rediacc jobs machine add --alias "web-server-1" --ip "192.168.1.100" --user "admin"

# Create a repository
rediacc jobs repo new --repo "web-app" --size "50G"
```

### Team Setup

```bash
# Create permission group
rediacc permissions groups create "developers"

# Add permissions
rediacc permissions add --group "developers" --permission "read"
rediacc permissions add --group "developers" --permission "write"

# Create team
rediacc teams create "backend-team"

# Add user to team
rediacc teams members add --team "backend-team" --user "dev@company.com"

# Assign permission group
rediacc permissions assign --user "dev@company.com" --group "developers"
```

## Development

### Prerequisites

- Go 1.21 or later
- Access to Rediacc middleware API

### Building

```bash
# Install dependencies
go mod download

# Build
go build -o bin/rediacc main.go

# Run tests
go test ./...

# Run with debug
go run main.go --debug auth login
```

### Project Structure

```
cli/
├── main.go                 # Entry point
├── cmd/                    # CLI commands
├── internal/               # Internal packages
│   ├── api/               # API client
│   ├── config/            # Configuration management
│   ├── format/            # Output formatting
│   ├── models/            # Data models
│   ├── utils/             # Utility functions
│   └── ssh/               # SSH client
├── docs/                  # Documentation
├── tests/                 # Test files
└── examples/              # Usage examples
```

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Support

For support and documentation, please visit:
- Documentation: [docs/](docs/)
- Issues: [GitHub Issues](issues)
- Email: support@rediacc.com