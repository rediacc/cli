# Rediacc CLI Tools

Command-line interface tools for Rediacc middleware system.

## Tools

### Core CLI
- **`rediacc-cli`** - Main CLI for Rediacc API operations
  - User authentication and session management
  - Team, machine, and repository management
  - Queue operations for system tasks
  - Vault encryption/decryption support

### Specialized Tools
- **`rediacc-cli-sync`** - Rsync-based file synchronization
  - Upload/download files to/from repositories
  - Mirror mode for exact replication
  - Checksum verification
  - Preview mode with confirmation

- **`rediacc-cli-term`** - Interactive terminal access
  - SSH access to repository Docker environments
  - Isolated Docker daemon per repository
  - Built-in helper functions for container management
  - Environment variables pre-configured

### Core Module
- **`rediacc_cli_core.py`** - Shared functionality module
  - Authentication and token management
  - SSH key handling
  - Machine and repository information retrieval
  - Common utilities

## Configuration Files
- **`rediacc-cli.json`** - CLI command and API endpoint configuration
- **`.gitignore`** - Git ignore patterns for test artifacts and temporary files

## Documentation
- **`TERMINAL_USAGE.md`** - Detailed guide for interactive terminal sessions
- **`tests/README.md`** - Test suite documentation

## Quick Start

### Authentication
```bash
# Login
./rediacc-cli login --email user@example.com --password yourpassword

# Your token is stored in ~/.rediacc/config.json
```

### File Sync
```bash
# Upload files
./rediacc-cli-sync upload --token TOKEN --local /path/to/files --machine rediacc11 --repo myrepo

# Download files
./rediacc-cli-sync download --token TOKEN --machine rediacc11 --repo myrepo --local /local/path

# Development mode - relaxes SSH host key checking
./rediacc-cli-sync upload --token TOKEN --local /path/to/files --machine rediacc11 --repo myrepo --dev
./rediacc-cli-sync download --token TOKEN --machine rediacc11 --repo myrepo --local /local/path --dev
```

### Terminal Access
```bash
# Interactive session to repository (with Docker environment)
./rediacc-cli-term --token TOKEN --machine rediacc11 --repo myrepo

# Interactive session to machine only (automatically switches to universal user and datastore)
./rediacc-cli-term --token TOKEN --machine rediacc11

# Execute single command in repository
./rediacc-cli-term --token TOKEN --machine rediacc11 --repo myrepo --command "docker ps"

# Execute single command on machine (runs as universal user in datastore)
./rediacc-cli-term --token TOKEN --machine rediacc11 --command "ls -la mounts/"

# Development mode - relaxes SSH host key checking
./rediacc-cli-term --token TOKEN --machine rediacc11 --dev
./rediacc-cli-term --token TOKEN --machine rediacc11 --repo myrepo --dev --command "docker ps"
```

**Note**: When connecting to a machine without specifying a repository:
- Automatically switches to the universal user (e.g., `rediacc`)
- Changes directory to the user's datastore (e.g., `/mnt/datastore/7111`)
- Commands are executed in this context

## Testing

Run the test suite:
```bash
cd tests
./test-quick.sh YOUR_TOKEN  # Quick test
./test-sync.sh              # Full sync test (auto-login)
./test-term.sh              # Full terminal test (auto-login)
```

## Requirements

- Python 3.6+
- SSH client
- rsync
- Optional: cryptography library for vault operations

## Installation

1. Clone the repository
2. Make scripts executable:
   ```bash
   chmod +x rediacc-cli rediacc-cli-sync rediacc-cli-term
   ```
3. Optional: Add to PATH for system-wide access

## Security Notes

- Tokens are stored in `~/.rediacc/config.json`
- SSH keys are handled in memory and cleaned up after use
- Vault encryption uses AES-256-GCM with PBKDF2

## License

[License information here]