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
./rediacc cli ARGS      # Run rediacc
./rediacc sync ARGS     # Run rediacc-sync  
./rediacc term ARGS     # Run rediacc-term
```

## rediacc Commands

### Authentication & User

```bash
# Get current user info
rediacc me

# Manage tokens
rediacc token save NAME VALUE
rediacc token list
rediacc token remove NAME
```

### List Commands

```bash
# List entities
rediacc list companies [--limit N]
rediacc list teams [--limit N]
rediacc list machines --team TEAM [--limit N]
rediacc list bridges --team TEAM [--limit N]
rediacc list repositories --team TEAM [--limit N]
rediacc list storages --team TEAM [--limit N]
rediacc list schedules --team TEAM [--limit N]
rediacc list users --team TEAM [--limit N]
```

### Create Commands

```bash
# Create entities
rediacc create company NAME --email EMAIL --password PASS --plan PLAN
rediacc create team NAME [--vault-file FILE]
rediacc create machine NAME --team TEAM [--vault-file FILE]
rediacc create bridge NAME --team TEAM [--vault-file FILE]
rediacc create repository NAME --team TEAM --machine MACHINE [--vault-file FILE]
rediacc create storage NAME --team TEAM [--vault-file FILE]
rediacc create schedule NAME --team TEAM --cron CRON [--vault-file FILE]
rediacc create user EMAIL --team TEAM --role ROLE
```

### Update Commands

```bash
# Update entity vaults
rediacc update company NAME --vault-file FILE
rediacc update team NAME --vault-file FILE
rediacc update machine NAME --team TEAM --vault-file FILE
rediacc update bridge NAME --team TEAM --vault-file FILE
rediacc update repository NAME --team TEAM --vault-file FILE
rediacc update storage NAME --team TEAM --vault-file FILE
rediacc update schedule NAME --team TEAM --vault-file FILE [--cron CRON]
```

### Delete Commands

```bash
# Delete entities
rediacc delete team NAME
rediacc delete machine NAME --team TEAM
rediacc delete bridge NAME --team TEAM
rediacc delete repository NAME --team TEAM
rediacc delete storage NAME --team TEAM
rediacc delete schedule NAME --team TEAM
rediacc delete user EMAIL --team TEAM
```

### Inspect Commands

```bash
# Get detailed info including vault data
rediacc inspect company NAME
rediacc inspect team NAME
rediacc inspect machine NAME --team TEAM
rediacc inspect bridge NAME --team TEAM
rediacc inspect repository NAME --team TEAM
rediacc inspect storage NAME --team TEAM
rediacc inspect schedule NAME --team TEAM
```

### Other Commands

```bash
# Search across all entities
rediacc search QUERY

# Configuration management
rediacc config get KEY
rediacc config set KEY VALUE
rediacc config list
```

## rediacc-sync Commands

### Upload

```bash
rediacc-sync upload --local PATH --machine MACHINE --repo REPO [OPTIONS]

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
rediacc-sync download --machine MACHINE --repo REPO --local PATH [OPTIONS]

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
rediacc-sync upload --local ./myapp --machine server --repo webapp

# Mirror with exclusions
rediacc-sync upload --local ./src --machine dev --repo code \
  --mirror --exclude "*.pyc" --exclude "__pycache__" --confirm

# Download with verification
rediacc-sync download --machine backup --repo data \
  --local ./restore --verify
```

## rediacc-term Commands

### Basic Usage

```bash
rediacc-term --machine MACHINE [OPTIONS]

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
rediacc-term --machine server --repo webapp

# Access machine directly (universal user)
rediacc-term --machine server

# Execute single command
rediacc-term --machine server --command "docker ps"

# Execute command in repository
rediacc-term --machine server --repo webapp --command "npm list"
```

### Examples

```bash
# Interactive shell in repository
rediacc-term --machine prod --repo api

# Check logs
rediacc-term --machine prod --repo api \
  --command "tail -n 100 /logs/app.log"

# Restart service
rediacc-term --machine prod --repo api \
  --command "docker restart api"
```

## Common Patterns

### Working with Different Teams

```bash
# Set default team
rediacc config set default_team "Production"

# Override team for specific commands
rediacc list machines --team "Development"
```

### Batch Operations

```bash
# Upload multiple repositories
for repo in api web worker; do
  rediacc-sync upload --local ./$repo --machine prod --repo $repo
done

# Check status across machines
for machine in server1 server2 server3; do
  echo "=== $machine ==="
  rediacc-term --machine $machine --command "df -h"
done
```

### JSON Output for Scripting

```bash
# Get machine details as JSON
MACHINES=$(rediacc --output json list machines --team Default)

# Parse with jq
echo "$MACHINES" | jq -r '.data[].name'

# Use in scripts
MACHINE_COUNT=$(echo "$MACHINES" | jq '.data | length')
echo "Found $MACHINE_COUNT machines"
```