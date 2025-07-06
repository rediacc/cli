# API Operations Guide

The `rediacc-cli` tool provides comprehensive access to the Rediacc API for managing resources and operations.

## Overview

The CLI provides operations for:
- Companies and teams
- Machines and bridges
- Repositories and storage
- Users and permissions
- Schedules and automation
- Queue operations

## Resource Management

### Companies

```bash
# List all companies
rediacc-cli list companies

# Create new company (admin only)
rediacc-cli create company "TechCorp" \
  --email admin@techcorp.com \
  --password securepass \
  --plan ELITE

# Inspect company details
rediacc-cli inspect company "TechCorp"

# Update company vault
echo '{"settings": {"tier": "enterprise"}}' > company-vault.json
rediacc-cli update company "TechCorp" --vault-file company-vault.json
```

### Teams

```bash
# List teams
rediacc-cli list teams

# Create team
rediacc-cli create team "Development"

# Create team with initial vault data
echo '{"ssh_key": "...", "config": {...}}' > team-vault.json
rediacc-cli create team "Production" --vault-file team-vault.json

# Update team vault
rediacc-cli update team "Production" --vault-file updated-vault.json

# Delete team
rediacc-cli delete team "OldTeam"
```

### Machines

```bash
# List machines in team
rediacc-cli list machines --team Production

# Create machine with vault configuration
cat > machine-vault.json << EOF
{
  "ip": "192.168.1.100",
  "user": "ubuntu",
  "datastore": "/mnt/data",
  "ssh_port": 22
}
EOF
rediacc-cli create machine "web-server-01" --team Production \
  --vault-file machine-vault.json

# Inspect machine (shows vault data)
rediacc-cli inspect machine "web-server-01" --team Production

# Update machine configuration
rediacc-cli update machine "web-server-01" --team Production \
  --vault-file new-config.json

# Delete machine
rediacc-cli delete machine "old-server" --team Production
```

### Repositories

```bash
# List repositories
rediacc-cli list repositories --team Development

# Create repository
rediacc-cli create repository "webapp" \
  --team Development \
  --machine "dev-server"

# Create with initial configuration
echo '{"docker_image": "node:14", "port": 3000}' > repo-config.json
rediacc-cli create repository "api" \
  --team Production \
  --machine "api-server" \
  --vault-file repo-config.json

# Update repository settings
rediacc-cli update repository "api" --team Production \
  --vault-file updated-config.json

# Delete repository
rediacc-cli delete repository "old-app" --team Development
```

### Storage

```bash
# List storage configurations
rediacc-cli list storages --team Production

# Create storage with S3 configuration
cat > s3-storage.json << EOF
{
  "type": "s3",
  "bucket": "my-backups",
  "region": "us-east-1",
  "access_key": "...",
  "secret_key": "..."
}
EOF
rediacc-cli create storage "backup-s3" --team Production \
  --vault-file s3-storage.json

# Update storage credentials
rediacc-cli update storage "backup-s3" --team Production \
  --vault-file new-creds.json

# Delete storage
rediacc-cli delete storage "old-backup" --team Production
```

## User Management

```bash
# List team users
rediacc-cli list users --team Development

# Add user to team
rediacc-cli create user "developer@company.com" \
  --team Development \
  --role MEMBER

# Available roles:
# - ADMIN: Full team management
# - MEMBER: Standard access
# - VIEWER: Read-only access

# Remove user from team
rediacc-cli delete user "former@company.com" --team Development

# Get current user info
rediacc-cli me
```

## Automation & Scheduling

### Schedules

```bash
# List schedules
rediacc-cli list schedules --team Production

# Create backup schedule
cat > backup-task.json << EOF
{
  "task": "backup",
  "source_repo": "database",
  "destination": "backup-s3",
  "options": {
    "compression": true,
    "retention_days": 30
  }
}
EOF
rediacc-cli create schedule "daily-backup" \
  --team Production \
  --cron "0 2 * * *" \
  --vault-file backup-task.json

# Update schedule
rediacc-cli update schedule "daily-backup" \
  --team Production \
  --cron "0 3 * * *" \
  --vault-file updated-task.json

# Delete schedule
rediacc-cli delete schedule "old-schedule" --team Production
```

### Queue Operations

```bash
# Create custom queue item
cat > queue-task.json << EOF
{
  "function": "custom",
  "command": "python /scripts/process.py",
  "repository": "worker",
  "priority": 1
}
EOF
rediacc-cli create queue-item \
  --team Production \
  --machine "worker-01" \
  --bridge "bridge-01" \
  --vault-file queue-task.json

# Check queue status (if available)
rediacc-cli list queue-items --team Production --status PENDING
```

## Search Operations

```bash
# Search across all resources
rediacc-cli search "production"

# Search with JSON output for parsing
rediacc-cli --output json search "web" | jq '.data[]'
```

## Vault Data Management

### Understanding Vaults

Vaults store encrypted configuration and credentials:
- **Company Vault**: Organization-wide settings
- **Team Vault**: SSH keys, shared credentials
- **Machine Vault**: Connection details, IP addresses
- **Repository Vault**: App configuration, environment variables
- **Storage Vault**: Backup destinations, cloud credentials

### Working with Vault Files

```bash
# Inspect current vault data
rediacc-cli inspect team Production > current-vault.json

# Modify vault data
jq '.ssh_private_key = "new-key-content"' current-vault.json > updated-vault.json

# Apply vault update
rediacc-cli update team Production --vault-file updated-vault.json

# Verify update
rediacc-cli inspect team Production
```

## Output Formats

### Table Format (Default)

```bash
rediacc-cli list machines --team Production
# ┌─────────────┬──────────┬─────────┐
# │ Name        │ Status   │ Created │
# ├─────────────┼──────────┼─────────┤
# │ web-01      │ ACTIVE   │ 2024-01 │
# │ web-02      │ ACTIVE   │ 2024-01 │
# └─────────────┴──────────┴─────────┘
```

### JSON Format

```bash
rediacc-cli --output json list machines --team Production
# {
#   "success": true,
#   "data": [
#     {"name": "web-01", "status": "ACTIVE", ...},
#     {"name": "web-02", "status": "ACTIVE", ...}
#   ]
# }
```

## Advanced Usage

### Batch Operations

```bash
# Create multiple machines
for i in {1..3}; do
  cat > machine-$i.json << EOF
{
  "ip": "192.168.1.10$i",
  "user": "ubuntu",
  "datastore": "/data"
}
EOF
  rediacc-cli create machine "worker-0$i" \
    --team Production \
    --vault-file machine-$i.json
done

# Update all repositories in a team
for repo in $(rediacc-cli --output json list repositories --team Dev | jq -r '.data[].name'); do
  echo "Updating $repo..."
  rediacc-cli update repository "$repo" --team Dev --vault-file config.json
done
```

### Pipeline Integration

```bash
#!/bin/bash
# Deploy script using CLI

# Get machine details
MACHINE_INFO=$(rediacc-cli --output json inspect machine prod-web --team Production)
MACHINE_IP=$(echo "$MACHINE_INFO" | jq -r '.data.vault.ip')

# Create deployment task
cat > deploy-task.json << EOF
{
  "function": "deploy",
  "repository": "webapp",
  "version": "$GIT_COMMIT",
  "pre_deploy": "npm test",
  "post_deploy": "npm run migrate"
}
EOF

# Queue deployment
rediacc-cli create queue-item \
  --team Production \
  --machine prod-web \
  --bridge prod-bridge \
  --vault-file deploy-task.json
```

### Error Handling

```bash
# Check operation success
if rediacc-cli create machine "test" --team Dev --vault-file config.json; then
  echo "Machine created successfully"
else
  echo "Failed to create machine"
  exit 1
fi

# Capture and parse errors
ERROR=$(rediacc-cli delete machine "nonexistent" --team Dev 2>&1)
if [[ $ERROR == *"not found"* ]]; then
  echo "Machine doesn't exist"
fi
```

## Best Practices

### 1. Use Vault Files for Sensitive Data

Never put credentials in command arguments:
```bash
# Bad - credentials visible in process list
rediacc-cli create storage "s3" --team Prod --data '{"key":"secret"}'

# Good - credentials in file
echo '{"access_key":"...","secret_key":"..."}' > s3-creds.json
chmod 600 s3-creds.json
rediacc-cli create storage "s3" --team Prod --vault-file s3-creds.json
rm s3-creds.json
```

### 2. Validate JSON Before Updates

```bash
# Validate JSON syntax
jq . vault-update.json > /dev/null || echo "Invalid JSON"

# Preview changes
rediacc-cli inspect resource Current > current.json
diff current.json new.json
```

### 3. Use Meaningful Names

```bash
# Good naming
rediacc-cli create machine "prod-web-us-east-1" --team Production
rediacc-cli create repository "api-v2-staging" --team Staging

# Poor naming  
rediacc-cli create machine "server1" --team Production
rediacc-cli create repository "test" --team Staging
```

### 4. Regular Backups

```bash
# Backup team configuration
for team in Production Staging Development; do
  rediacc-cli inspect team "$team" > "backup-$team-$(date +%Y%m%d).json"
done

# Backup all machine configs
rediacc-cli --output json list machines --team Prod | \
  jq -r '.data[].name' | \
  while read machine; do
    rediacc-cli inspect machine "$machine" --team Prod > "machine-$machine.json"
  done
```