# Rediacc CLI Implementation Plan

## Project Overview

This document provides a comprehensive implementation plan for building a Go-based CLI application that communicates with the Rediacc middleware service. The CLI will provide command-line access to all functionality available through the middleware's stored procedures.

## Architecture Overview

```
┌─────────────────┐    HTTP/REST    ┌──────────────────┐    SQL    ┌─────────────────┐
│                 │ ──────────────→ │                  │ ────────→ │                 │
│   Rediacc CLI   │                 │    Middleware    │           │   SQL Server    │
│   (Go Binary)   │ ←────────────── │   (.NET API)     │ ←──────── │   (Database)    │
└─────────────────┘    JSON         └──────────────────┘           └─────────────────┘
```

## Project Structure

```
cli/
├── IMPLEMENTATION_PLAN.md          # This file
├── README.md                       # Project documentation
├── go.mod                          # Go module definition
├── go.sum                          # Go module checksums
├── main.go                         # Entry point
├── cmd/                            # CLI commands structure
│   ├── root.go                     # Root command setup
│   ├── auth/                       # Authentication commands
│   │   ├── auth.go                 # Auth command group
│   │   ├── login.go               # Login command
│   │   ├── logout.go              # Logout command
│   │   ├── user.go                # User management commands
│   │   └── twofa.go               # 2FA commands
│   ├── company/                    # Company management
│   │   ├── company.go             # Company command group
│   │   ├── create.go              # Create company
│   │   ├── info.go                # Company info
│   │   ├── users.go               # List users
│   │   ├── limits.go              # Resource limits
│   │   ├── vault.go               # Vault operations
│   │   └── subscription.go        # Subscription info
│   ├── permissions/                # Permission management
│   │   ├── permissions.go         # Permissions command group
│   │   ├── groups.go              # Permission groups
│   │   ├── add.go                 # Add permissions
│   │   ├── remove.go              # Remove permissions
│   │   └── assign.go              # Assign user to group
│   ├── teams/                      # Team management
│   │   ├── teams.go               # Teams command group
│   │   ├── create.go              # Create team
│   │   ├── delete.go              # Delete team
│   │   ├── list.go                # List teams
│   │   ├── rename.go              # Rename team
│   │   ├── vault.go               # Team vault operations
│   │   └── members.go             # Team member management
│   ├── infra/                      # Infrastructure management
│   │   ├── infra.go               # Infra command group
│   │   ├── regions/               # Region management
│   │   │   ├── regions.go         # Regions subcommand
│   │   │   ├── create.go          # Create region
│   │   │   ├── delete.go          # Delete region
│   │   │   ├── list.go            # List regions
│   │   │   └── update.go          # Update region
│   │   ├── bridges/               # Bridge management
│   │   │   ├── bridges.go         # Bridges subcommand
│   │   │   ├── create.go          # Create bridge
│   │   │   ├── delete.go          # Delete bridge
│   │   │   ├── list.go            # List bridges
│   │   │   └── update.go          # Update bridge
│   │   └── machines/              # Machine management
│   │       ├── machines.go        # Machines subcommand
│   │       ├── create.go          # Create machine
│   │       ├── delete.go          # Delete machine
│   │       ├── list.go            # List machines
│   │       ├── move.go            # Move machine
│   │       └── update.go          # Update machine
│   ├── storage/                    # Storage & Repository management
│   │   ├── storage.go             # Storage command group
│   │   ├── create.go              # Create storage
│   │   ├── delete.go              # Delete storage
│   │   ├── list.go                # List storage
│   │   ├── update.go              # Update storage
│   │   └── repos/                 # Repository management
│   │       ├── repos.go           # Repos subcommand
│   │       ├── create.go          # Create repository
│   │       ├── delete.go          # Delete repository
│   │       ├── list.go            # List repositories
│   │       └── update.go          # Update repository
│   ├── schedules/                  # Schedule management
│   │   ├── schedules.go           # Schedules command group
│   │   ├── create.go              # Create schedule
│   │   ├── delete.go              # Delete schedule
│   │   ├── list.go                # List schedules
│   │   └── update.go              # Update schedule
│   ├── queue/                      # Queue management
│   │   ├── queue.go               # Queue command group
│   │   ├── add.go                 # Add queue item
│   │   ├── remove.go              # Remove queue item
│   │   ├── list.go                # List queue items
│   │   ├── next.go                # Get next items
│   │   └── response.go            # Manage responses
│   ├── jobs/                       # Machine job management
│   │   ├── jobs.go                # Jobs command group
│   │   ├── machine/               # Machine operations
│   │   │   ├── machine.go         # Machine subcommand
│   │   │   ├── add.go             # Add machine
│   │   │   ├── setup.go           # Setup machine
│   │   │   └── hello.go           # Test connectivity
│   │   ├── repo/                  # Repository operations
│   │   │   ├── repo.go            # Repo subcommand
│   │   │   ├── new.go             # Create new repo
│   │   │   ├── mount.go           # Mount repo
│   │   │   ├── unmount.go         # Unmount repo
│   │   │   ├── up.go              # Start repo services
│   │   │   ├── down.go            # Stop repo services
│   │   │   ├── remove.go          # Remove repo
│   │   │   ├── resize.go          # Resize repo
│   │   │   ├── push.go            # Push repo
│   │   │   └── pull.go            # Pull repo
│   │   ├── plugin/                # Plugin management
│   │   │   ├── plugin.go          # Plugin subcommand
│   │   │   ├── enable.go          # Enable plugin
│   │   │   └── disable.go         # Disable plugin
│   │   ├── terminal.go            # Terminal access
│   │   ├── ownership.go           # Change ownership
│   │   ├── upload.go              # Upload files
│   │   ├── migrate.go             # Migrate repos
│   │   ├── webterm.go             # Web terminal
│   │   └── map.go                 # Map operations
│   ├── config/                     # CLI configuration
│   │   ├── config.go              # Config command group
│   │   ├── init.go                # Initialize config
│   │   ├── set.go                 # Set config value
│   │   ├── get.go                 # Get config value
│   │   └── list.go                # List config
│   └── raw/                        # Raw procedure execution
│       ├── raw.go                 # Raw command group
│       ├── exec.go                # Execute procedure
│       └── list.go                # List procedures
├── internal/                       # Internal packages
│   ├── api/                        # API client
│   │   ├── client.go              # HTTP client implementation
│   │   ├── auth.go                # Authentication handling
│   │   ├── requests.go            # Request builders
│   │   └── responses.go           # Response handlers
│   ├── config/                     # Configuration management
│   │   ├── config.go              # Config structure and loading
│   │   ├── file.go                # File operations
│   │   └── validation.go          # Config validation
│   ├── format/                     # Output formatting
│   │   ├── table.go               # Table formatter
│   │   ├── json.go                # JSON formatter
│   │   ├── yaml.go                # YAML formatter
│   │   └── text.go                # Text formatter
│   ├── models/                     # Data models
│   │   ├── auth.go                # Authentication models
│   │   ├── company.go             # Company models
│   │   ├── team.go                # Team models
│   │   ├── infra.go               # Infrastructure models
│   │   ├── storage.go             # Storage models
│   │   ├── schedule.go            # Schedule models
│   │   ├── queue.go               # Queue models
│   │   ├── jobs.go                # Jobs models
│   │   └── common.go              # Common models
│   ├── utils/                      # Utility functions
│   │   ├── validation.go          # Input validation
│   │   ├── strings.go             # String utilities
│   │   ├── time.go                # Time utilities
│   │   └── errors.go              # Error handling
│   └── ssh/                        # SSH client for jobs
│       ├── client.go              # SSH client implementation
│       ├── commands.go            # SSH command execution
│       └── config.go              # SSH configuration
├── docs/                           # Documentation
│   ├── commands/                   # Command documentation
│   │   ├── auth.md                # Auth commands docs
│   │   ├── company.md             # Company commands docs
│   │   ├── permissions.md         # Permissions commands docs
│   │   ├── teams.md               # Teams commands docs
│   │   ├── infra.md               # Infrastructure commands docs
│   │   ├── storage.md             # Storage commands docs
│   │   ├── schedules.md           # Schedules commands docs
│   │   ├── queue.md               # Queue commands docs
│   │   ├── jobs.md                # Jobs commands docs
│   │   ├── config.md              # Config commands docs
│   │   └── raw.md                 # Raw commands docs
│   ├── api/                        # API documentation
│   │   ├── endpoints.md           # Middleware endpoints
│   │   ├── procedures.md          # Stored procedures
│   │   └── authentication.md     # Auth flow
│   ├── examples/                   # Usage examples
│   │   ├── basic.md               # Basic usage
│   │   ├── advanced.md            # Advanced usage
│   │   └── workflows.md           # Common workflows
│   └── troubleshooting.md         # Troubleshooting guide
├── scripts/                        # Build and deployment scripts
│   ├── build.sh                   # Build script
│   ├── test.sh                    # Test script
│   ├── install.sh                 # Installation script
│   └── release.sh                 # Release script
├── tests/                          # Test files
│   ├── integration/               # Integration tests
│   │   ├── auth_test.go           # Auth integration tests
│   │   ├── company_test.go        # Company integration tests
│   │   ├── teams_test.go          # Teams integration tests
│   │   ├── infra_test.go          # Infrastructure integration tests
│   │   ├── storage_test.go        # Storage integration tests
│   │   ├── schedules_test.go      # Schedules integration tests
│   │   ├── queue_test.go          # Queue integration tests
│   │   └── jobs_test.go           # Jobs integration tests
│   ├── unit/                      # Unit tests
│   │   ├── api_test.go            # API client tests
│   │   ├── config_test.go         # Config tests
│   │   ├── format_test.go         # Formatter tests
│   │   └── utils_test.go          # Utility tests
│   └── fixtures/                  # Test fixtures
│       ├── responses/             # Mock API responses
│       └── configs/               # Test configurations
├── examples/                       # Usage examples
│   ├── basic-workflow.sh          # Basic workflow example
│   ├── team-setup.sh              # Team setup example
│   ├── infra-deployment.sh        # Infrastructure deployment
│   └── job-execution.sh           # Job execution example
└── .gitignore                     # Git ignore file
```

## Dependencies and Libraries

### Core Dependencies
```go
// go.mod
module github.com/rediacc/cli

go 1.21

require (
    github.com/spf13/cobra v1.8.0           // CLI framework
    github.com/spf13/viper v1.18.2          // Configuration management
    github.com/spf13/pflag v1.0.5           // CLI flag parsing
    github.com/olekukonko/tablewriter v0.0.5 // Table formatting
    gopkg.in/yaml.v3 v3.0.1                 // YAML support
    golang.org/x/crypto v0.17.0             // SSH and crypto
    golang.org/x/term v0.15.0               // Terminal utilities
    github.com/fatih/color v1.16.0          // Colored output
    github.com/briandowns/spinner v1.23.0   // Loading spinners
    github.com/manifoldco/promptui v0.9.0   // Interactive prompts
    github.com/golang-jwt/jwt/v5 v5.2.0     // JWT handling
    golang.org/x/net v0.19.0                // HTTP utilities
)
```

### Additional Tools
- **golangci-lint**: For code linting
- **goreleaser**: For release automation
- **testify**: For enhanced testing capabilities

## Core Components Implementation

### 1. Main Entry Point (main.go)
```go
package main

import (
    "os"
    "github.com/rediacc/cli/cmd"
)

func main() {
    if err := cmd.Execute(); err != nil {
        os.Exit(1)
    }
}
```

### 2. Root Command Setup (cmd/root.go)
- Initialize Cobra CLI framework
- Set up global flags and configuration
- Configure output formatting options
- Handle global error management
- Set up logging and debug modes

### 3. API Client (internal/api/client.go)
```go
type Client struct {
    BaseURL    string
    HTTPClient *http.Client
    Auth       *AuthConfig
    Headers    map[string]string
}

type AuthConfig struct {
    Email       string
    SessionToken string
    RequestCredential string
}

// Core methods to implement:
func (c *Client) ExecuteStoredProcedure(procedure string, params map[string]interface{}) (*Response, error)
func (c *Client) Login(email, password string) (*AuthResponse, error)
func (c *Client) RefreshToken() error
func (c *Client) SetRequestHeaders(headers map[string]string)
```

### 4. Configuration Management (internal/config/config.go)
```go
type Config struct {
    Server    ServerConfig    `yaml:"server"`
    Auth      AuthConfig      `yaml:"auth"`
    Jobs      JobsConfig      `yaml:"jobs"`
    Format    FormatConfig    `yaml:"format"`
    SSH       SSHConfig       `yaml:"ssh"`
}

type ServerConfig struct {
    URL     string `yaml:"url"`
    Timeout string `yaml:"timeout"`
}

type JobsConfig struct {
    DefaultDatastoreSize string     `yaml:"default_datastore_size"`
    SSHTimeout          string     `yaml:"ssh_timeout"`
    SSHKeyPath          string     `yaml:"ssh_key_path"`
    Machines            []Machine  `yaml:"machines"`
}

type Machine struct {
    Alias     string `yaml:"alias"`
    IP        string `yaml:"ip"`
    User      string `yaml:"user"`
    Datastore string `yaml:"datastore"`
}
```

## Stored Procedures Mapping

### Authentication & User Management
| CLI Command | Stored Procedure | Parameters |
|-------------|------------------|------------|
| `auth login` | `web.protected_CreateAuthenticationRequest` | email, password, 2fa_code? |
| `auth logout` | `web.public_LogoutUserSession` | session_id |
| `auth user create` | `web.public_CreateNewUser` | email, password |
| `auth user update-email` | `web.public_UpdateUserEmail` | old_email, new_email |
| `auth user update-password` | `web.public_UpdateUserPassword` | email, old_password, new_password |
| `auth user enable` | `web.protected_ActivateUserAccount` | email |
| `auth user disable` | `web.public_DisableUserAccount` | email |
| `auth 2fa enable` | `web.public_ManageUser2FA` | email, action: "enable" |
| `auth 2fa generate` | `dbo.sp2FAGenerateSecretKey` | - |
| `auth 2fa validate` | `dbo.sp2FAValidate` | secret, code |
| `auth sessions list` | `web.public_GetUserSessions` | email |

### Company Management
| CLI Command | Stored Procedure | Parameters |
|-------------|------------------|------------|
| `company create` | `web.protected_CreateNewCompany` | name, admin_email |
| `company info` | `web.public_GetUserCompanyDetails` | - |
| `company users list` | `web.public_GetCompanyUsers` | - |
| `company limits` | `web.public_GetCompanyResourceLimits` | - |
| `company vault get` | `web.public_GetCompanySecureData` | - |
| `company vault update` | `web.public_UpdateCompanySecureData` | data |
| `company subscription info` | `web.public_GetSubscriptionDetails` | - |

### Permission Management
| CLI Command | Stored Procedure | Parameters |
|-------------|------------------|------------|
| `permissions groups list` | `web.public_GetCompanyPermissionGroups` | - |
| `permissions groups create` | `web.public_CreatePermissionGroup` | name |
| `permissions groups delete` | `web.public_DeletePermissionGroup` | name |
| `permissions groups show` | `web.public_GetPermissionGroupDetails` | name |
| `permissions add` | `web.public_AddPermissionToGroup` | group, permission |
| `permissions remove` | `web.public_DeletePermissionFromGroup` | group, permission |
| `permissions assign` | `web.public_ChangeUserPermissionGroup` | user_email, group |

### Team Management
| CLI Command | Stored Procedure | Parameters |
|-------------|------------------|------------|
| `teams list` | `web.public_GetAllCompanyTeams` | - |
| `teams create` | `web.public_CreateTeam` | name |
| `teams delete` | `web.public_DeleteTeam` | name |
| `teams rename` | `web.public_UpdateTeamName` | old_name, new_name |
| `teams vault update` | `web.public_UpdateTeamSecureData` | name, data |
| `teams members list` | `web.public_GetTeamMembers` | name |
| `teams members add` | `web.public_AddUserToTeam` | team_name, user_email |
| `teams members remove` | `web.public_DeleteUserFromTeam` | team_name, user_email |

### Infrastructure Management
| CLI Command | Stored Procedure | Parameters |
|-------------|------------------|------------|
| `infra regions list` | `web.public_GetCompanyRegions` | - |
| `infra regions create` | `web.public_CreateRegion` | name |
| `infra regions delete` | `web.public_DeleteRegion` | name |
| `infra regions update` | `web.public_UpdateRegionSecureData` | name, vault_data |
| `infra bridges list` | `web.public_GetRegionBridges` | region |
| `infra bridges create` | `web.public_CreateBridge` | region, name |
| `infra bridges delete` | `web.public_DeleteBridge` | region, name |
| `infra bridges update` | `web.public_UpdateBridgeSecureData` | region, name, vault_data |
| `infra machines list` | `web.public_GetTeamMachines` | team |
| `infra machines create` | `web.public_CreateMachine` | team, name, bridge |
| `infra machines delete` | `web.public_DeleteMachine` | team, name |
| `infra machines move` | `web.public_ChangeMachineBridge` | team, name, new_bridge |
| `infra machines update` | `web.public_UpdateMachineSecureData` | team, name, vault_data |

### Storage & Repository Management
| CLI Command | Stored Procedure | Parameters |
|-------------|------------------|------------|
| `storage list` | `web.public_GetTeamStorages` | team |
| `storage create` | `web.public_CreateStorage` | team, name |
| `storage delete` | `web.public_DeleteStorage` | team, name |
| `storage update` | `web.public_UpdateStorageSecureData` | team, name, vault_data |
| `storage repos list` | `web.public_GetTeamRepositories` | team |
| `storage repos create` | `web.public_CreateRepository` | team, name |
| `storage repos delete` | `web.public_DeleteRepository` | team, name |
| `storage repos update` | `web.public_UpdateRepositorySecureData` | team, name, vault_data |

### Schedule Management
| CLI Command | Stored Procedure | Parameters |
|-------------|------------------|------------|
| `schedules list` | `web.public_GetTeamSchedules` | team |
| `schedules create` | `web.public_CreateSchedule` | team, name |
| `schedules delete` | `web.public_DeleteSchedule` | team, name |
| `schedules update` | `web.public_UpdateScheduleSecureData` | team, name, vault_data |

### Queue Management
| CLI Command | Stored Procedure | Parameters |
|-------------|------------------|------------|
| `queue list` | `web.public_GetTeamQueueItems` | team |
| `queue add` | `web.public_CreateQueueItem` | team, data |
| `queue remove` | `web.public_DeleteQueueItem` | item_id |
| `queue response add` | `web.public_AddQueueItemResponse` | item_id, response |
| `queue response update` | `web.public_AddQueueItemResponse` | item_id, response |
| `queue next` | `web.public_GetNextQueueItems` | team, count |

## Jobs Commands Implementation

The jobs commands require special handling as they interact with remote machines via SSH and bridge functionality:

### Machine Management Jobs
These commands interface with the bridge CLI system to manage remote machines:

```go
// internal/ssh/client.go
type SSHClient struct {
    Host       string
    Port       int
    User       string
    Password   string
    KeyPath    string
    Timeout    time.Duration
}

func (c *SSHClient) ExecuteCommand(cmd string) (*SSHResult, error)
func (c *SSHClient) ExecuteWithJSON(cmd string) (*JSONResponse, error)
```

### Job Command Mapping
| CLI Command | Bridge CLI Command | Parameters |
|-------------|---------------------|------------|
| `jobs machine add` | `--add_machine` | alias, ip, user, datastore, ssh_password? |
| `jobs machine setup` | `setup` | datastore_size? |
| `jobs machine hello` | `hello` | - |
| `jobs repo new` | `new` | repo, size |
| `jobs repo mount` | `mount` | repo, from? |
| `jobs repo unmount` | `unmount` | repo, from? |
| `jobs repo up` | `up` | repo |
| `jobs repo down` | `down` | repo |
| `jobs repo remove` | `rm` | repo |
| `jobs repo resize` | `resize` | repo, size |
| `jobs repo push` | `push` | repo, to? |
| `jobs repo pull` | `pull` | repo, from? |
| `jobs plugin enable` | `plugin` | repo, plugin |
| `jobs plugin disable` | `plugout` | repo, plugin |
| `jobs terminal` | `--term` | repo |
| `jobs ownership` | `ownership` | repo, from, to |
| `jobs upload` | `--upload` | file paths |
| `jobs migrate` | `--migrate` | source, destination |
| `jobs webterm` | `--webterm` | repo |
| `jobs map` | `--map` | repo |

## Authentication Flow

### Session Management
1. **Login Process**:
   - User provides email/password
   - CLI calls `web.protected_CreateAuthenticationRequest`
   - Store session token and request credential
   - Save to config file

2. **Request Headers**:
   ```
   UserEmail: user@example.com
   UserHash: [SHA256 hash]
   RequestCredential: [UUID from login]
   Verification: [verification string]
   ```

3. **Token Refresh**:
   - Automatic token refresh on 401 responses
   - Re-authenticate if refresh fails

## Output Formatting

### Table Format (Default)
```
+------------+------------------+--------+
| Name       | Email            | Status |
+------------+------------------+--------+
| John Doe   | john@example.com | Active |
| Jane Smith | jane@example.com | Active |
+------------+------------------+--------+
```

### JSON Format
```json
{
  "data": [
    {
      "name": "John Doe",
      "email": "john@example.com",
      "status": "Active"
    }
  ],
  "success": true,
  "total": 2
}
```

### YAML Format
```yaml
data:
  - name: John Doe
    email: john@example.com
    status: Active
  - name: Jane Smith
    email: jane@example.com
    status: Active
success: true
total: 2
```

## Error Handling

### Error Types
1. **Network Errors**: Connection issues, timeouts
2. **Authentication Errors**: Invalid credentials, expired tokens
3. **Validation Errors**: Invalid input parameters
4. **Authorization Errors**: Insufficient permissions
5. **Server Errors**: Internal server errors, database issues
6. **SSH Errors**: Connection failures, command execution errors

### Error Response Format
```go
type ErrorResponse struct {
    Error   string            `json:"error"`
    Code    int               `json:"code"`
    Details map[string]string `json:"details,omitempty"`
}
```

## Configuration File Structure

### Default Location: `~/.rediacc-cli.yaml`
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
  machines:
    - alias: "web-server-1"
      ip: "192.168.1.100"
      user: "admin"
      datastore: "/mnt/datastore"

format:
  default: "table"
  colors: true
  timestamps: true

ssh:
  timeout: "30s"
  retry_attempts: 3
  retry_delay: "5s"
```

## Build and Deployment

### Build Scripts (scripts/build.sh)
```bash
#!/bin/bash
# Build for multiple platforms
GOOS=linux GOARCH=amd64 go build -o bin/rediacc-cli-linux-amd64 main.go
GOOS=darwin GOARCH=amd64 go build -o bin/rediacc-cli-darwin-amd64 main.go
GOOS=windows GOARCH=amd64 go build -o bin/rediacc-cli-windows-amd64.exe main.go
```

### Release Process
1. Version tagging with semantic versioning
2. Automated builds with goreleaser
3. Multi-platform binary distribution
4. Package managers integration (Homebrew, apt, etc.)

## Testing Strategy

### Unit Tests
- API client functionality
- Configuration management
- Input validation
- Output formatting
- Utility functions

### Integration Tests
- End-to-end command execution
- API communication
- SSH connectivity
- Error handling scenarios

### Test Coverage Goals
- Minimum 80% code coverage
- All critical paths tested
- Error scenarios covered

## Development Workflow

### Phase 1: Core Foundation (Week 1-2)
1. Set up project structure
2. Implement basic CLI framework with Cobra
3. Create API client with authentication
4. Implement configuration management
5. Set up basic output formatting

### Phase 2: Core Commands (Week 3-4)
1. Implement auth commands
2. Implement company commands
3. Implement permissions commands
4. Implement teams commands
5. Add comprehensive error handling

### Phase 3: Infrastructure Commands (Week 5-6)
1. Implement infra commands (regions, bridges, machines)
2. Implement storage commands
3. Implement schedule commands
4. Implement queue commands
5. Add advanced output formatting

### Phase 4: Jobs Commands (Week 7-8)
1. Implement SSH client
2. Implement machine management jobs
3. Implement repository operations
4. Implement plugin management
5. Add file operations and terminal access

### Phase 5: Polish and Testing (Week 9-10)
1. Comprehensive testing suite
2. Documentation completion
3. Performance optimization
4. Security review
5. Release preparation

## AI Implementation Guidelines

### For each command implementation:

1. **Start with the command structure**:
   ```go
   // cmd/auth/login.go
   var loginCmd = &cobra.Command{
       Use:   "login",
       Short: "Login to Rediacc",
       Long:  "Authenticate with Rediacc using email and password",
       RunE:  runLogin,
   }
   ```

2. **Implement the command logic**:
   ```go
   func runLogin(cmd *cobra.Command, args []string) error {
       // Get flags
       email, _ := cmd.Flags().GetString("email")
       password, _ := cmd.Flags().GetString("password")
       
       // Validate input
       if err := validateLoginInput(email, password); err != nil {
           return err
       }
       
       // Call API
       client := api.NewClient(config.Get().Server.URL)
       response, err := client.Login(email, password)
       if err != nil {
           return err
       }
       
       // Save auth info
       config.Get().Auth.SessionToken = response.Token
       config.Save()
       
       // Format output
       formatter.Success("Successfully logged in as %s", email)
       return nil
   }
   ```

3. **Add comprehensive error handling**:
   ```go
   func validateLoginInput(email, password string) error {
       if email == "" {
           return errors.New("email is required")
       }
       if !isValidEmail(email) {
           return errors.New("invalid email format")
       }
       if password == "" {
           return errors.New("password is required")
       }
       return nil
   }
   ```

4. **Implement API client methods**:
   ```go
   func (c *Client) Login(email, password string) (*AuthResponse, error) {
       params := map[string]interface{}{
           "UserEmail": email,
           "UserPassword": password,
       }
       
       response, err := c.ExecuteStoredProcedure("CreateAuthenticationRequest", params)
       if err != nil {
           return nil, err
       }
       
       return parseAuthResponse(response)
   }
   ```

5. **Add tests for each component**:
   ```go
   func TestLoginCommand(t *testing.T) {
       // Test successful login
       // Test invalid email
       // Test invalid password
       // Test network error
       // Test authentication error
   }
   ```

### Code Quality Standards:
- Follow Go conventions and best practices
- Use meaningful variable and function names
- Add comprehensive comments for complex logic
- Implement proper error handling with context
- Use structured logging where appropriate
- Validate all user inputs
- Handle edge cases gracefully

### Security Considerations:
- Never log sensitive information (passwords, tokens)
- Secure storage of authentication tokens
- Validate all inputs to prevent injection
- Use secure defaults for all configurations
- Implement proper timeout handling
- Sanitize error messages to avoid information leakage

This implementation plan provides a comprehensive roadmap for building the Rediacc CLI application. Each component is designed to be modular, testable, and maintainable, following Go best practices and providing a robust command-line interface for the Rediacc platform.