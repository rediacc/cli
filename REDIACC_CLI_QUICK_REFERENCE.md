# Rediacc CLI - Quick Reference Guide

## 21 Main Commands

### Essential Commands (No Auth Required)
1. **login** - Authenticate with Rediacc API
2. **logout** - Clear saved token
3. **license** - Manage offline/online licensing
4. **protocol** - Manage rediacc:// protocol handler
5. **setup** - Initial setup instructions

### Workflow Commands (Auth Required)
6. **workflow** - High-level workflow operations (7 subcommands)
   - repo-create, repo-push, connectivity-test, hello-test, ssh-test, machine-setup, add-machine

### Resource Management (Auth Required)
7. **create** - Create resources (10 types)
8. **list** - List resources (18 types)
9. **update** - Update resources (12 types)
10. **rm** - Delete resources (8 types)

### Configuration & Security
11. **vault** - Manage encrypted vault data (4 operations)
12. **permission** - Manage permissions (7 operations)
13. **user** - Manage user accounts (5 operations)
14. **team-member** - Manage team membership (2 operations)

### Infrastructure
15. **bridge** - Manage bridge connections (1 operation)
16. **queue** - Manage task queue (9 operations)
17. **company** - Company-level operations (6 operations)
18. **audit** - Audit logging (1 operation)
19. **inspect** - Inspect resources (2 types)
20. **distributed-storage** - Distributed storage operations (8 operations)
21. **auth** - Authentication operations (2 operations)

---

## Global Options (All Commands)

```
--output/-o {text|json|json-full}     # Output format
--token/-t TOKEN                      # Inline authentication token
--endpoint URL                        # Custom API endpoint
--verbose/-v                          # Verbose logging
--sandbox                             # Use sandbox API
--help                                # Show help
--version                             # Show version
```

---

## Commands That Don't Require Authentication

```bash
rediacc login                              # Login
rediacc logout                             # Logout
rediacc license generate-id                # Generate hardware ID
rediacc license request -i HWID            # Request license
rediacc license install -f LICENSE         # Install license
rediacc protocol register                  # Register protocol
rediacc protocol unregister                # Unregister protocol
rediacc protocol status                    # Check protocol status
rediacc protocol run rediacc://...         # Handle protocol URL
rediacc setup                              # Show setup instructions
rediacc user activate --email ...          # Activate user account
rediacc create company --name ...          # Create company
rediacc queue list-functions               # List queue functions
```

---

## Common Command Patterns

### Authentication
```bash
rediacc login                    # Interactive login
rediacc logout                   # Clear saved token
rediacc --token TOKEN command    # Use inline token
```

### Creating Resources
```bash
rediacc create team --name myteam
rediacc create machine --team myteam --name machine1 --bridge bridge1
rediacc create repository --team myteam --name repo1
rediacc create storage --team myteam --name storage1
```

### Listing Resources
```bash
rediacc list teams
rediacc list team-machines --team myteam
rediacc list team-repositories --team myteam
rediacc list team-members --team myteam
rediacc list bridges
rediacc list sessions
```

### Updating Resources
```bash
rediacc update team --name myteam --vault '{"key":"value"}'
rediacc update machine --team myteam --name m1 --vault '{"ip":"1.2.3.4"}'
rediacc update machine --team myteam --name m1 --new-bridge newbridge
```

### Deleting Resources
```bash
rediacc rm team --name myteam
rediacc rm machine --team myteam --name m1
rediacc rm repository --team myteam --name repo1
rediacc rm bridge --name bridge1
```

### Workflows
```bash
# Create repository
rediacc workflow repo-create \
  --team myteam \
  --name myrepo \
  --machine machine1 \
  --size 1G

# Push repository
rediacc workflow repo-push \
  --source-team team1 \
  --source-machine m1 \
  --source-repo repo1 \
  --dest-team team2 \
  --dest-repo repo1 \
  --dest-machine m2 \
  --wait

# Test connectivity
rediacc workflow connectivity-test \
  --team myteam \
  --machines m1 m2 m3 \
  --wait

# Setup machine
rediacc workflow machine-setup \
  --team myteam \
  --machine m1 \
  --wait

# Add machine with auto-setup
rediacc workflow add-machine \
  --team myteam \
  --name m1 \
  --bridge b1 \
  --vault '{"ip":"1.2.3.4","user":"admin","ssh_password":"pass"}' \
  --auto-setup \
  --wait
```

### Vault Operations
```bash
rediacc vault status                    # Show vault status
rediacc vault set --data '{"key":"val"}'  # Set vault data
rediacc vault set-password              # Set vault password
rediacc vault clear-password            # Clear vault password
```

### Queue Operations
```bash
rediacc queue list-functions            # List available functions
rediacc queue list                      # List queue items
rediacc queue add --function func1      # Add to queue
rediacc queue get-next                  # Get next item
rediacc queue complete --id ITEM_ID     # Mark complete
rediacc queue retry --id ITEM_ID        # Retry item
```

### Permission Management
```bash
rediacc permission list-groups          # List groups
rediacc permission create-group --name g1  # Create group
rediacc permission add --group g1       # Add permission
rediacc permission remove --group g1    # Remove permission
```

### User Management
```bash
rediacc user activate --email ...       # Activate user (no auth needed)
rediacc user deactivate --email ...     # Deactivate user
rediacc user update-password --email ... # Change password
rediacc user update-email --email ... --new-email ... # Change email
rediacc user update-tfa --email ...     # Setup 2FA
```

### Output Formats
```bash
rediacc list teams                          # Text output (default)
rediacc list teams --output json            # Concise JSON
rediacc list teams --output json-full       # Full JSON with details
```

### Debugging
```bash
rediacc command --verbose                  # Enable verbose logging
rediacc command --sandbox                  # Use sandbox API
rediacc command --endpoint https://api.example.com  # Custom endpoint
```

---

## Resource Types Summary

### CREATE Resources (10)
bridge, company, machine, queue-item, region, repository, schedule, storage, team, user

### LIST Resources (18)
audit-logs, bridges, company-vault, data-graph, entity-history, lookup-data, regions, 
resource-limits, sessions, subscription, team-machines, team-members, team-repositories, 
team-schedules, team-storages, teams, user-company, users

### UPDATE Resources (12)
bridge, machine, machine-bridge, machine-status, region, repository, repository-vault, 
schedule, schedule-vault, storage, storage-vault, team

### DELETE Resources (8)
bridge, machine, queue-item, region, repository, schedule, storage, team

---

## Authentication Requirements

### NO AUTH (7 groups)
- login, logout
- license (all)
- protocol (all)
- setup
- user activate
- create company
- queue list-functions

### AUTH REQUIRED (14 groups)
- All workflow operations
- create (except company)
- All list operations
- All update operations
- All rm (delete) operations
- All vault operations
- All permission operations
- user (except activate)
- All team-member operations
- All bridge operations
- queue (except list-functions)
- All company operations
- All audit operations
- All inspect operations
- All distributed-storage operations
- All auth operations

---

## Output Format Examples

### Text (Default)
```
Team: myteam
  Created: 2024-01-15
  Status: active
  Members: 5
```

### JSON (Concise)
```json
{
  "success": true,
  "data": {
    "teamName": "myteam",
    "created": "2024-01-15",
    "status": "active"
  }
}
```

### JSON-Full (Comprehensive)
```json
{
  "success": true,
  "data": {
    "teamName": "myteam",
    "created": "2024-01-15",
    "status": "active",
    "members": 5,
    "description": "...",
    "metadata": {...}
  },
  "message": "Team retrieved successfully"
}
```

---

## Key Files
- Config: `/home/muhammed/cli/src/config/cli-config.json`
- Entry: `/home/muhammed/cli/src/cli/commands/cli_main.py`
- License: `/home/muhammed/cli/src/cli/commands/license_main.py`
- Protocol: `/home/muhammed/cli/src/cli/commands/protocol_main.py`
- Workflow: `/home/muhammed/cli/src/cli/commands/workflow_main.py`

---

## Tips & Tricks

1. **Use --output json for scripting**
   ```bash
   rediacc list teams --output json | jq '.data[] | .teamName'
   ```

2. **Chain commands for workflows**
   ```bash
   TEAM=$(rediacc create team --name newteam --output json | jq -r '.data.teamName')
   rediacc list team-machines --team $TEAM
   ```

3. **Save token for session**
   ```bash
   TOKEN=$(rediacc login --output json | jq -r '.data.token')
   rediacc list teams --token $TOKEN
   ```

4. **Use vault for sensitive data**
   ```bash
   rediacc update machine --team t --name m --vault '{"password":"secret"}'
   ```

5. **Wait for workflow completion**
   ```bash
   rediacc workflow repo-create ... --wait --wait-timeout 600
   ```

6. **Debug with verbose mode**
   ```bash
   rediacc command --verbose 2>&1 | grep -i error
   ```

7. **Test with sandbox**
   ```bash
   rediacc --sandbox list teams
   ```

