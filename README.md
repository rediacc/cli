# Rediacc CLI Tools

Command-line interface tools for Rediacc middleware system.

## Quick Start

```bash
# Linux/macOS
./install.sh --auto      # Install dependencies
./rediacc login          # Authenticate
./rediacc sync --help    # View sync options

# Windows
.\rediacc.ps1 setup -AutoInstall  # Install dependencies
.\rediacc.ps1 login              # Authenticate
.\rediacc.ps1 sync --help        # View sync options
```

Both platforms use a unified wrapper interface with the same base name: `./rediacc` on Linux/macOS and `.\rediacc.ps1` on Windows.

The commands are nearly identical across platforms:
| Linux/macOS | Windows | Description |
|-------------|---------|-------------|
| `./rediacc setup` | `.\rediacc.ps1 setup` | Install dependencies |
| `./rediacc login` | `.\rediacc.ps1 login` | Authenticate |
| `./rediacc sync` | `.\rediacc.ps1 sync` | File synchronization |
| `./rediacc term` | `.\rediacc.ps1 term` | Terminal access |
| `./rediacc test` | `.\rediacc.ps1 test` | Test installation |

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
- **`LINUX_TROUBLESHOOTING.md`** - Linux/macOS troubleshooting guide
- **`WINDOWS_TROUBLESHOOTING.md`** - Windows-specific troubleshooting guide
- **`tests/README.md`** - Test suite documentation

## Installation

### Linux/macOS

#### Quick Setup
```bash
# One-time setup (checks and installs dependencies)
./install.sh

# Or auto-install without prompts
./install.sh --auto

# Using the wrapper script
./rediacc setup
./rediacc setup --auto
```

The installer will:
- Check for Python 3.6+, rsync, and SSH client
- Install missing dependencies using your package manager
- Set executable permissions on scripts
- Optionally create symlinks in your PATH

#### Manual Installation
If you prefer to install dependencies manually:
- **Python 3.6+**: Required for all tools
- **rsync**: Required for file synchronization
- **OpenSSH client**: Required for remote connections
- **cryptography** (optional): For vault encryption support
  ```bash
  pip3 install cryptography
  ```

### Windows
Windows requires MSYS2 for rsync support. Use the PowerShell wrapper for all operations:

#### Quick Setup
```powershell
# PowerShell - One-time setup (installs MSYS2 packages if needed)
.\rediacc.ps1 setup

# Or auto-install without prompts
.\rediacc.ps1 setup -AutoInstall

# Command Prompt alternative
rediacc setup
```

#### Manual MSYS2 Installation (if needed)
1. Download MSYS2 from https://www.msys2.org/
2. Install to default location (C:\msys64)
3. Open MSYS2 terminal and run:
   ```bash
   pacman -Syu
   # If terminal closes, reopen and run:
   pacman -Su
   # Install required packages:
   pacman -S rsync openssh
   ```
4. Run setup to verify: `.\rediacc.ps1 setup`

## Quick Start

### Authentication
```bash
# Linux/macOS
./rediacc login --email user@example.com --password yourpassword

# Windows (PowerShell)
.\rediacc.ps1 login --email user@example.com --password yourpassword

# Windows (Command Prompt)
rediacc login --email user@example.com --password yourpassword

# Interactive login (all platforms)
./rediacc login  # Linux/macOS
.\rediacc.ps1 login  # Windows PowerShell
rediacc login  # Windows CMD

# Your token is stored in ~/.rediacc/config.json
```

### File Sync
```bash
# Linux/macOS
./rediacc sync upload --token TOKEN --local /path/to/files --machine server --repo myrepo
./rediacc sync download --token TOKEN --machine server --repo myrepo --local /local/path

# Windows (PowerShell)
.\rediacc.ps1 sync upload --token TOKEN --local C:\MyFiles --machine server --repo myrepo
.\rediacc.ps1 sync download --token TOKEN --machine server --repo myrepo --local C:\Backup

# Windows (Command Prompt)
rediacc sync upload --token TOKEN --local C:\MyFiles --machine server --repo myrepo
rediacc sync download --token TOKEN --machine server --repo myrepo --local C:\Backup

# With options (all platforms)
# --mirror: Delete files in destination that don't exist in source
# --verify: Use checksums to verify all transfers
# --confirm: Preview changes before executing
# --dev: Development mode (relaxes SSH host key checking)
```

### Terminal Access
```bash
# Linux/macOS
./rediacc term --token TOKEN --machine server --repo myrepo

# Windows (PowerShell)
.\rediacc.ps1 term --token TOKEN --machine server --repo myrepo

# Execute single command
./rediacc term --token TOKEN --machine server --repo myrepo --command "docker ps"  # Linux/macOS
.\rediacc.ps1 term --token TOKEN --machine server --repo myrepo --command "docker ps"  # Windows
```

**Note**: When connecting to a machine without specifying a repository:
- Automatically switches to the universal user (e.g., `rediacc`)
- Changes directory to the user's datastore (e.g., `/mnt/datastore/7111`)

## Command Examples

### Complete Workflow Example
```bash
# 1. Setup (first time only)
./rediacc setup              # Linux/macOS
.\rediacc.ps1 setup          # Windows

# 2. Login
./rediacc login              # Linux/macOS
.\rediacc.ps1 login          # Windows

# 3. Upload a project
./rediacc sync upload --token YOUR_TOKEN --local ./myproject --machine prod-server --repo webapp
.\rediacc.ps1 sync upload --token YOUR_TOKEN --local C:\myproject --machine prod-server --repo webapp

# 4. Connect to work on it
./rediacc term --token YOUR_TOKEN --machine prod-server --repo webapp
.\rediacc.ps1 term --token YOUR_TOKEN --machine prod-server --repo webapp

# 5. Download changes
./rediacc sync download --token YOUR_TOKEN --machine prod-server --repo webapp --local ./myproject-backup
.\rediacc.ps1 sync download --token YOUR_TOKEN --machine prod-server --repo webapp --local C:\myproject-backup
```

### Advanced Options
```bash
# Mirror sync (deletes destination files not in source)
./rediacc sync upload --token TOKEN --local ./src --machine server --repo code --mirror

# Verify mode with checksums
./rediacc sync download --token TOKEN --machine server --repo data --local ./backup --verify

# Preview changes before sync
./rediacc sync upload --token TOKEN --local ./files --machine server --repo docs --confirm

# Development mode (relaxed SSH checking)
./rediacc term --token TOKEN --machine dev-server --repo test --dev
```
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