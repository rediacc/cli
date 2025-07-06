# Command Reference

Complete reference for all Rediacc CLI commands.

## Global Options

These options work with all commands:

```bash
--token TOKEN           # Override authentication token
--api-url URL          # Override API endpoint
--output FORMAT        # Output format: table (default) or json
--help                 # Show help message
--version              # Show version information
```

## rediacc (Wrapper Script)

The main wrapper provides convenient access to all tools:

```bash
# Show available commands
./rediacc --help

# Login/logout
./rediacc login [--email EMAIL] [--password PASSWORD]
./rediacc logout

# Tool shortcuts
./rediacc cli ARGS      # Run rediacc-cli
./rediacc sync ARGS     # Run rediacc-cli-sync  
./rediacc term ARGS     # Run rediacc-cli-term
```

## rediacc-cli Commands

### Authentication & User

```bash
# Get current user info
rediacc-cli me

# Manage tokens
rediacc-cli token save NAME VALUE
rediacc-cli token list
rediacc-cli token remove NAME
```

### List Commands

```bash
# List entities
rediacc-cli list companies [--limit N]
rediacc-cli list teams [--limit N]
rediacc-cli list machines --team TEAM [--limit N]
rediacc-cli list bridges --team TEAM [--limit N]
rediacc-cli list repositories --team TEAM [--limit N]
rediacc-cli list storages --team TEAM [--limit N]
rediacc-cli list schedules --team TEAM [--limit N]
rediacc-cli list users --team TEAM [--limit N]
```

### Create Commands

```bash
# Create entities
rediacc-cli create company NAME --email EMAIL --password PASS --plan PLAN
rediacc-cli create team NAME [--vault-file FILE]
rediacc-cli create machine NAME --team TEAM [--vault-file FILE]
rediacc-cli create bridge NAME --team TEAM [--vault-file FILE]
rediacc-cli create repository NAME --team TEAM --machine MACHINE [--vault-file FILE]
rediacc-cli create storage NAME --team TEAM [--vault-file FILE]
rediacc-cli create schedule NAME --team TEAM --cron CRON [--vault-file FILE]
rediacc-cli create user EMAIL --team TEAM --role ROLE
```

### Update Commands

```bash
# Update entity vaults
rediacc-cli update company NAME --vault-file FILE
rediacc-cli update team NAME --vault-file FILE
rediacc-cli update machine NAME --team TEAM --vault-file FILE
rediacc-cli update bridge NAME --team TEAM --vault-file FILE
rediacc-cli update repository NAME --team TEAM --vault-file FILE
rediacc-cli update storage NAME --team TEAM --vault-file FILE
rediacc-cli update schedule NAME --team TEAM --vault-file FILE [--cron CRON]
```

### Delete Commands

```bash
# Delete entities
rediacc-cli delete team NAME
rediacc-cli delete machine NAME --team TEAM
rediacc-cli delete bridge NAME --team TEAM
rediacc-cli delete repository NAME --team TEAM
rediacc-cli delete storage NAME --team TEAM
rediacc-cli delete schedule NAME --team TEAM
rediacc-cli delete user EMAIL --team TEAM
```

### Inspect Commands

```bash
# Get detailed info including vault data
rediacc-cli inspect company NAME
rediacc-cli inspect team NAME
rediacc-cli inspect machine NAME --team TEAM
rediacc-cli inspect bridge NAME --team TEAM
rediacc-cli inspect repository NAME --team TEAM
rediacc-cli inspect storage NAME --team TEAM
rediacc-cli inspect schedule NAME --team TEAM
```

### Other Commands

```bash
# Search across all entities
rediacc-cli search QUERY

# Configuration management
rediacc-cli config get KEY
rediacc-cli config set KEY VALUE
rediacc-cli config list
```

## rediacc-cli-sync Commands

### Upload

```bash
rediacc-cli-sync upload --local PATH --machine MACHINE --repo REPO [OPTIONS]

Options:
  --team TEAM              # Team name (default: from config)
  --token TOKEN            # Override token
  --mirror                 # Delete remote files not in local
  --exclude PATTERN        # Exclude files matching pattern (multiple allowed)
  --confirm                # Show what would be done without executing
  --dev                    # Development mode (relaxed SSH checking)
```

### Download

```bash
rediacc-cli-sync download --machine MACHINE --repo REPO --local PATH [OPTIONS]

Options:
  --team TEAM              # Team name (default: from config)
  --token TOKEN            # Override token
  --mirror                 # Delete local files not in remote
  --verify                 # Check file integrity after transfer
  --exclude PATTERN        # Exclude files matching pattern
  --confirm                # Show what would be done without executing
  --dev                    # Development mode
```

### Examples

```bash
# Basic upload
rediacc-cli-sync upload --local ./myapp --machine server --repo webapp

# Mirror with exclusions
rediacc-cli-sync upload --local ./src --machine dev --repo code \
  --mirror --exclude "*.pyc" --exclude "__pycache__" --confirm

# Download with verification
rediacc-cli-sync download --machine backup --repo data \
  --local ./restore --verify
```

## rediacc-cli-term Commands

### Basic Usage

```bash
rediacc-cli-term --machine MACHINE [OPTIONS]

Options:
  --team TEAM              # Team name (default: from config)
  --repo REPO              # Repository name (optional)
  --command CMD            # Execute command and exit
  --token TOKEN            # Override token
  --dev                    # Development mode
```

### Access Modes

```bash
# Access repository environment (Docker container)
rediacc-cli-term --machine server --repo webapp

# Access machine directly (universal user)
rediacc-cli-term --machine server

# Execute single command
rediacc-cli-term --machine server --command "docker ps"

# Execute command in repository
rediacc-cli-term --machine server --repo webapp --command "npm list"
```

### Examples

```bash
# Interactive shell in repository
rediacc-cli-term --machine prod --repo api

# Check logs
rediacc-cli-term --machine prod --repo api \
  --command "tail -n 100 /logs/app.log"

# Restart service
rediacc-cli-term --machine prod --repo api \
  --command "docker restart api"
```

## Common Patterns

### Working with Different Teams

```bash
# Set default team
rediacc-cli config set default_team "Production"

# Override team for specific commands
rediacc-cli list machines --team "Development"
```

### Batch Operations

```bash
# Upload multiple repositories
for repo in api web worker; do
  rediacc-cli-sync upload --local ./$repo --machine prod --repo $repo
done

# Check status across machines
for machine in server1 server2 server3; do
  echo "=== $machine ==="
  rediacc-cli-term --machine $machine --command "df -h"
done
```

### JSON Output for Scripting

```bash
# Get machine details as JSON
MACHINES=$(rediacc-cli --output json list machines --team Default)

# Parse with jq
echo "$MACHINES" | jq -r '.data[].name'

# Use in scripts
MACHINE_COUNT=$(echo "$MACHINES" | jq '.data | length')
echo "Found $MACHINE_COUNT machines"
```