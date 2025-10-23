# Rediacc CLI - Comprehensive Command Implementation Report

## Overview
The Rediacc CLI tool is a comprehensive command-line interface for the Rediacc Middleware API. Commands are defined in a JSON configuration file and implemented through a combination of dynamic handlers and specialized command modules.

## Command Structure

### Configuration Location
- **Source**: `/home/muhammed/cli/src/config/cli-config.json`
- **Entry Point**: `src/cli/commands/cli_main.py`

### Command Categories

The CLI supports two main types of commands:

1. **Configured Commands** - Defined in CLI configuration JSON with subcommands
2. **Specialized Modules** - Dedicated Python modules for complex operations

---

## FULLY IMPLEMENTED & WORKING COMMANDS

### 1. LOGIN & AUTHENTICATION
**Command**: `rediacc login`
- **Module**: `cli_main.py` - `CommandHandler.login()`
- **Status**: FULLY IMPLEMENTED
- **Function**: Authenticate with Rediacc API
- **Parameters**: 
  - Username/Email
  - Password
  - Server endpoint (optional)
- **Notes**: Does NOT require prior authentication

### 2. LOGOUT
**Command**: `rediacc logout`
- **Module**: `cli_main.py` - `CommandHandler.logout()`
- **Status**: FULLY IMPLEMENTED
- **Function**: Clear saved authentication token

---

### 3. LICENSE MANAGEMENT
**Command**: `rediacc license`
- **Module**: `license_main.py` (dedicated module)
- **Status**: FULLY IMPLEMENTED
- **Subcommands**:
  - `generate-id`: Generate hardware ID for offline licensing
    - Options: `--output/-o` (output file)
  - `request`: Request license using hardware ID
    - Required: `--hardware-id/-i` (ID or file path)
    - Optional: `--output/-o`, `--server-url/-s`
  - `install`: Install license file
    - Required: `--file/-f` (license file path)
    - Optional: `--target/-t` (target directory)
- **Notes**: Does NOT require authentication

### 4. PROTOCOL HANDLER
**Command**: `rediacc protocol`
- **Module**: `protocol_main.py` (dedicated module)
- **Status**: FULLY IMPLEMENTED
- **Subcommands**:
  - `register`: Register `rediacc://` protocol for browser integration
    - Optional: `--system-wide` (system-level registration)
  - `unregister`: Unregister `rediacc://` protocol
    - Optional: `--system-wide`
  - `status`: Show protocol registration status
    - Optional: `--system-wide`
  - `run`: Handle `rediacc://` protocol URL from command line
    - Required: URL argument
- **Notes**: Does NOT require authentication

### 5. WORKFLOW COMMANDS
**Command**: `rediacc workflow`
- **Module**: `workflow_main.py` (WorkflowHandler class)
- **Status**: FULLY IMPLEMENTED
- **Requires Authentication**: YES
- **Subcommands**:

#### 5.1 repo-create
- **Description**: Create and initialize repository on machine
- **Required Parameters**:
  - `--team`: Team name
  - `--name`: Repository name
  - `--machine`: Machine to initialize repository on
  - `--size`: Repository size (e.g., 1G, 500M, 10G)
- **Optional Parameters**:
  - `--vault`: Repository vault data (JSON)
  - `--parent`: Parent repository name
  - `--trace`: Show task ID for tracking
  - `--wait`: Wait for completion
  - `--poll-interval`: Polling interval in seconds (default: 2)
  - `--wait-timeout`: Timeout in seconds (default: 300)

#### 5.2 repo-push
- **Description**: Push repository with automatic destination creation
- **Required Parameters**:
  - `--source-team`: Source team name
  - `--source-machine`: Source machine name
  - `--source-repo`: Source repository name
  - `--dest-team`: Destination team name
  - `--dest-repo`: Destination repository name
- **Optional Parameters**:
  - `--source-path`: Source path within repository (default: /)
  - `--dest-type`: Destination type - machine or storage (default: machine)
  - `--dest-machine`: Destination machine name (required if dest-type is machine)
  - `--dest-storage`: Destination storage name (required if dest-type is storage)
  - `--trace`: Show task ID for tracking
  - `--wait`: Wait for completion
  - `--poll-interval`: Polling interval in seconds (default: 2)
  - `--wait-timeout`: Timeout in seconds (default: 300)

#### 5.3 connectivity-test
- **Description**: Test connectivity to multiple machines
- **Required Parameters**:
  - `--team`: Team name
  - `--machines`: Machine names to test (space-separated)
- **Optional Parameters**:
  - `--wait`: Wait for completion
  - `--poll-interval`: Polling interval in seconds (default: 2)
  - `--wait-timeout`: Timeout in seconds per machine (default: 30)

#### 5.4 hello-test
- **Description**: Execute hello function on machine
- **Required Parameters**:
  - `--team`: Team name
  - `--machine`: Machine name
- **Optional Parameters**:
  - `--wait`: Wait for completion
  - `--poll-interval`: Polling interval in seconds (default: 2)
  - `--wait-timeout`: Timeout in seconds (default: 30)

#### 5.5 ssh-test
- **Description**: Test SSH connectivity through bridge
- **Required Parameters**:
  - `--team`: Team name (required by API)
  - `--bridge`: Bridge name
  - `--host`: Target host to test
  - `--user`: SSH username
- **Optional Parameters**:
  - `--password`: SSH password
  - `--wait`: Wait for completion
  - `--poll-interval`: Polling interval in seconds (default: 2)
  - `--wait-timeout`: Timeout in seconds (default: 30)

#### 5.6 machine-setup
- **Description**: Setup machine with datastore
- **Required Parameters**:
  - `--team`: Team name
  - `--machine`: Machine name
- **Optional Parameters**:
  - `--datastore-size`: Datastore size (default: default)
  - `--wait`: Wait for completion
  - `--poll-interval`: Polling interval in seconds (default: 2)
  - `--wait-timeout`: Timeout in seconds (default: 300)

#### 5.7 add-machine
- **Description**: Create machine with SSH connection test
- **Required Parameters**:
  - `--team`: Team name
  - `--name`: Machine name
  - `--bridge`: Bridge name
- **Optional Parameters**:
  - `--vault`: Machine vault data (JSON) with ip, user, ssh_password, etc.
  - `--no-test`: Skip SSH connection test
  - `--auto-setup`: Automatically run machine setup if SSH test passes
  - `--datastore-size`: Datastore size for auto-setup (default: 95%)
  - `--wait`: Wait for SSH test completion
  - `--trace`: Show task IDs for tracking
  - `--poll-interval`: Polling interval in seconds (default: 2)
  - `--wait-timeout`: Timeout in seconds for SSH test (default: 30)

---

## DYNAMIC API-BASED COMMANDS

These commands are dynamically generated from the API configuration and require authentication (unless specified otherwise).

### Command Categories (15 Main Commands)

#### 1. CREATE COMMAND
**Command**: `rediacc create <resource>`
**Default**: Requires Authentication
**Subcommands** (resources that can be created):
- `bridge`
- `company` (NO AUTH REQUIRED)
- `machine`
- `queue-item`
- `region`
- `repository`
- `schedule`
- `storage`
- `team`
- `user`

#### 2. LIST COMMAND
**Command**: `rediacc list <resource>`
**Required**: Authentication
**Subcommands** (resources that can be listed):
- `audit-logs`
- `bridges`
- `company-vault`
- `data-graph`
- `entity-history`
- `lookup-data`
- `regions`
- `resource-limits`
- `sessions`
- `subscription`
- `team-machines`
- `team-members`
- `team-repositories`
- `team-schedules`
- `team-storages`
- `teams`
- `user-company`
- `users`

#### 3. UPDATE COMMAND
**Command**: `rediacc update <resource>`
**Required**: Authentication
**Subcommands** (resources that can be updated):
- `bridge`
- `machine`
- `machine-bridge`
- `machine-status`
- `region`
- `repository`
- `repository-vault`
- `schedule`
- `schedule-vault`
- `storage`
- `storage-vault`
- `team`
**Special Features**:
- Vault support: `--vault`, `--vault-file`, `--vault-version`
- For machine update: `--new-bridge` option

#### 4. DELETE (RM) COMMAND
**Command**: `rediacc rm <resource>`
**Required**: Authentication
**Subcommands** (resources that can be deleted):
- `bridge`
- `machine`
- `queue-item`
- `region`
- `repository`
- `schedule`
- `storage`
- `team`

#### 5. VAULT COMMAND
**Command**: `rediacc vault <operation>`
**Required**: Authentication
**Subcommands**:
- `clear-password`: Clear saved vault password
- `set`: Set vault data
- `set-password`: Set vault password
- `status`: Show vault status

#### 6. PERMISSION COMMAND
**Command**: `rediacc permission <operation>`
**Required**: Authentication
**Subcommands**:
- `add`: Add permission
- `assign`: Assign permission
- `create-group`: Create permission group
- `delete-group`: Delete permission group
- `list-group`: List permissions in a group
- `list-groups`: List all permission groups
- `remove`: Remove permission

#### 7. USER COMMAND
**Command**: `rediacc user <operation>`
**Default**: Requires Authentication
**Subcommands**:
- `activate`: Activate user account (NO AUTH REQUIRED)
- `deactivate`: Deactivate user account
- `update-email`: Update user email
- `update-password`: Update user password
- `update-tfa`: Update two-factor authentication settings

#### 8. TEAM-MEMBER COMMAND
**Command**: `rediacc team-member <operation>`
**Required**: Authentication
**Subcommands**:
- `add`: Add member to team
- `remove`: Remove member from team

#### 9. BRIDGE COMMAND
**Command**: `rediacc bridge <operation>`
**Required**: Authentication
**Subcommands**:
- `reset-auth`: Reset bridge authentication

#### 10. QUEUE COMMAND
**Command**: `rediacc queue <operation>`
**Default**: Requires Authentication
**Subcommands**:
- `add`: Add item to queue (requires auth)
- `cancel`: Cancel queue item (requires auth)
- `complete`: Mark queue item as complete (requires auth)
- `get-next`: Get next queue item (requires auth)
- `list`: List queue items (requires auth)
- `list-functions`: List available queue functions (NO AUTH REQUIRED)
- `retry`: Retry failed queue item (requires auth)
- `trace`: Trace queue item execution (requires auth)
- `update-response`: Update queue item response (requires auth)

#### 11. COMPANY COMMAND
**Command**: `rediacc company <operation>`
**Required**: Authentication
**Subcommands**:
- `block-user-requests`: Block user requests
- `export-data`: Export company data
- `get-vaults`: Get company vaults
- `import-data`: Import company data
- `update-vault`: Update company vault
- `update-vaults`: Update multiple company vaults

#### 12. AUDIT COMMAND
**Command**: `rediacc audit <operation>`
**Required**: Authentication
**Subcommands**:
- `trace`: Trace audit logs

#### 13. INSPECT COMMAND
**Command**: `rediacc inspect <resource>`
**Required**: Authentication
**Subcommands**:
- `machine`: Inspect machine details
- `repository`: Inspect repository details

#### 14. DISTRIBUTED-STORAGE COMMAND
**Command**: `rediacc distributed-storage <operation>`
**Required**: Authentication
**Subcommands**:
- `add-machines`: Add machines to storage cluster
- `create-cluster`: Create distributed storage cluster
- `delete-cluster`: Delete distributed storage cluster
- `get-cluster`: Get cluster details
- `list-clusters`: List distributed storage clusters
- `remove-machines`: Remove machines from cluster
- `update-status`: Update cluster status
- `update-vault`: Update cluster vault

#### 15. AUTH COMMAND
**Command**: `rediacc auth <operation>`
**Required**: Authentication
**Subcommands**:
- `privilege`: Check user privileges
- `status`: Check authentication status

---

## GLOBAL OPTIONS (Available for All Commands)

These options can be used with any CLI command:

```
--output/-o {text|json|json-full}  Output format (default: text)
--token/-t TOKEN                    Authentication token (overrides saved token)
--endpoint ENDPOINT                 API endpoint URL (e.g., https://rediacc.com/api)
--verbose/-v                        Enable verbose logging output
--sandbox                           Use sandbox API (https://sandbox.rediacc.com)
--help                              Show help information
--version                           Show version information
```

---

## COMMAND AUTHENTICATION REQUIREMENTS

### NO AUTHENTICATION REQUIRED (7 groups)
- `rediacc login` - Initial authentication
- `rediacc logout` - Clear token (token-less operation)
- `rediacc license` - All subcommands (generate-id, request, install)
- `rediacc protocol` - All subcommands (register, unregister, status, run)
- `rediacc setup` - Setup command
- `rediacc user activate` - Account activation
- `rediacc create company` - Company creation
- `rediacc queue list-functions` - List available functions

### AUTHENTICATION REQUIRED
- All `workflow` subcommands
- All `create` commands except company
- All `list` commands
- All `update` commands
- All `rm` commands
- All `vault` commands
- All `permission` commands
- All `user` commands except activate
- All `team-member` commands
- All `bridge` commands
- Most `queue` commands (except list-functions)
- All `company` commands
- All `audit` commands
- All `inspect` commands
- All `distributed-storage` commands
- All `auth` commands

---

## DYNAMIC ENDPOINT SUPPORT

The CLI supports calling dynamic API endpoints directly. If a command is not recognized as a known command, it will attempt to call it as a dynamic endpoint:

```bash
rediacc custom-endpoint --param1 value1 --param2 value2
```

This allows for:
- Direct API method calls
- Custom endpoint invocation
- Forward compatibility with API updates

---

## IMPLEMENTATION DETAILS

### Command Parsing Architecture

1. **Argument Reordering**: Global options are reordered to work with argparse limitations
2. **Parser Setup**: Dynamic parser construction from `cli-config.json`
3. **Command Handlers**: 
   - `CommandHandler` class for generic API commands
   - `WorkflowHandler` class for workflow operations
   - Specialized handler functions for login/logout

### Configuration-Driven Design

Commands are primarily defined in `/home/muhammed/cli/src/config/cli-config.json`:
- `CLI_COMMANDS`: Command definitions and subcommands
- `API_ENDPOINTS`: API method mappings
- `QUEUE_FUNCTIONS`: Queue function definitions
- `METADATA`: Configuration metadata

### Specialized Modules

Located in `/home/muhammed/cli/src/cli/commands/`:
- `license_main.py`: License management (offline/online licensing)
- `protocol_main.py`: Protocol handler registration and management
- `workflow_main.py`: High-level workflow operations
- `cli_main.py`: Main CLI entry point and generic command handler

---

## OUTPUT FORMATS

All commands support multiple output formats via `--output/-o`:

1. **text** (default): Human-readable colored output with terminal formatting
2. **json**: Concise JSON format with structure: `{success, data, message/error}`
3. **json-full**: Comprehensive JSON format with all details

---

## USAGE EXAMPLES

```bash
# Authentication
rediacc login                           # Login with credentials
rediacc logout                          # Logout

# License Management (Offline Licensing)
rediacc license generate-id             # Generate hardware ID
rediacc license request -i hardware-id  # Request license
rediacc license install -f license.lic  # Install license

# Protocol Management
rediacc protocol register               # Register protocol handler
rediacc protocol status                 # Check registration status

# Workflow Operations
rediacc workflow repo-create \
  --team myteam \
  --name myrepo \
  --machine mymachine \
  --size 1G \
  --wait

# Create Resources
rediacc create team --name myteam
rediacc create machine --team myteam --name mymachine --bridge mybridge

# List Resources
rediacc list teams
rediacc list team-machines --team myteam

# Update Resources
rediacc update machine --team myteam --name mymachine --vault '{"ip":"192.168.1.1"}'

# Delete Resources
rediacc rm machine --team myteam --name mymachine

# Queue Operations
rediacc queue list-functions            # List available functions
rediacc queue add --function myfunction --data '{"param":"value"}'

# Get Help
rediacc --help                          # Show all commands
rediacc create --help                   # Show create subcommands
rediacc create team --help              # Show team creation parameters
```

---

## SUMMARY STATISTICS

- **Total Top-Level Commands**: 21
  - Specialized Modules: 4 (login, logout, license, protocol, workflow)
  - Dynamic API Commands: 15 (create, list, update, rm, vault, permission, user, team-member, bridge, queue, company, audit, inspect, distributed-storage, auth)
  - Setup Command: 1 (setup)

- **Total Subcommands**: 94+
  - Workflow: 7 subcommands
  - Create: 10 subcommands
  - List: 18 subcommands
  - Update: 12 subcommands
  - Delete (rm): 8 subcommands
  - Vault: 4 subcommands
  - Permission: 7 subcommands
  - User: 5 subcommands
  - Team-Member: 2 subcommands
  - Bridge: 1 subcommand
  - Queue: 9 subcommands
  - Company: 6 subcommands
  - Audit: 1 subcommand
  - Inspect: 2 subcommands
  - Distributed-Storage: 8 subcommands
  - Auth: 2 subcommands

- **Global Options**: 6

---

## AUTHENTICATION & AUTHORIZATION

- **Token-based** authentication system
- Support for **inline token** via `--token/-t` flag
- **Token persistence** in configuration for subsequent commands
- **Vault integration** for sensitive data management
- **Two-factor authentication** support (via `user update-tfa`)
- **Session management** (list and inspect sessions)

---

## FILE LOCATIONS

- **Main Entry Point**: `/home/muhammed/cli/src/cli/commands/cli_main.py`
- **CLI Configuration**: `/home/muhammed/cli/src/config/cli-config.json`
- **License Module**: `/home/muhammed/cli/src/cli/commands/license_main.py`
- **Protocol Module**: `/home/muhammed/cli/src/cli/commands/protocol_main.py`
- **Workflow Module**: `/home/muhammed/cli/src/cli/commands/workflow_main.py`
- **API Client**: `/home/muhammed/cli/src/cli/core/api_client.py`
- **Configuration Manager**: `/home/muhammed/cli/src/cli/core/config.py`

---

## KEY ARCHITECTURAL FEATURES

1. **Configuration-Driven**: Most commands defined in JSON, not hard-coded
2. **Modular Design**: Specialized handlers for complex operations
3. **Dynamic Command Support**: Can call any API endpoint directly
4. **Authentication Flexible**: Some commands work without auth, most require it
5. **Multiple Output Formats**: Text, JSON, and comprehensive JSON
6. **Global Options**: Consistent token, endpoint, and output format across all commands
7. **Workflow Automation**: High-level workflow commands that combine multiple API calls
8. **Async Support**: Commands can wait for completion with configurable polling

