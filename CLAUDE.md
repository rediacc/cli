# CLAUDE.md - Key Project Notes for Rediacc CLI

## Project Overview
This is a Go-based CLI application for the Rediacc platform that communicates with middleware via HTTP/REST API, which interfaces with SQL Server through stored procedures.

## Architecture
```
CLI (Go) → HTTP/REST → Middleware (.NET) → SQL Server (Stored Procedures)
```

## Current Implementation Status

### ✅ Phase 1 Complete: Core Foundation
- **Project Structure**: Complete directory hierarchy with cmd/, internal/, docs/, tests/
- **Go Module**: Initialized with core dependencies (Cobra, Viper, tablewriter, etc.)
- **Main Entry**: Simple main.go that delegates to cmd package
- **Root Command**: Cobra CLI framework with all command groups as placeholders
- **API Client**: HTTP client with authentication, stored procedure execution
- **Configuration**: YAML-based config system with defaults and validation
- **Output Formatting**: Table, JSON, YAML, Text formatters with colors
- **Models & Utils**: Common data structures, validation, error handling
- **Build System**: Working build scripts and go development file

### 🚧 Next Phase: Core Commands (Phase 2)
- Implement auth commands (login, logout, user management, 2FA)
- Implement company commands (create, info, users, limits, vault)
- Implement permissions commands (groups, add/remove, assign)
- Implement teams commands (create, delete, members, vault)

## Key Architecture Patterns

### Command Structure
```go
// Each command follows this pattern:
var cmdName = &cobra.Command{
    Use:   "command-name",
    Short: "Brief description",
    Long:  "Detailed description",
    RunE:  runCommandName,
}

func runCommandName(cmd *cobra.Command, args []string) error {
    // 1. Get and validate flags/args
    // 2. Create API client
    // 3. Call stored procedure via client
    // 4. Format and display results
    return nil
}
```

### API Client Usage
```go
client := api.NewClient(config.Get().Server.URL)
response, err := client.ExecuteStoredProcedure("procedureName", params)
if err != nil {
    return err
}
return format.Print(response.Data)
```

### Configuration Access
```go
cfg := config.Get()  // Get current config
config.SetDebug(true)  // Set debug mode
config.GetOutputFormat()  // Get output format
```

## Stored Procedures Mapping

### Authentication
- `auth login` → `web.protected_CreateAuthenticationRequest`
- `auth logout` → `web.public_LogoutUserSession`
- `auth user create` → `web.public_CreateNewUser`

### Company Management
- `company create` → `web.protected_CreateNewCompany`
- `company info` → `web.public_GetUserCompanyDetails`
- `company users list` → `web.public_GetCompanyUsers`

### Teams Management
- `teams list` → `web.public_GetCompanyTeams`
- `teams create` → `web.public_CreateTeam`
- `teams members add` → `web.public_AddUserToTeam`

## Configuration File Structure
Default location: `~/.rediacc-cli.yaml`
```yaml
server:
  url: "http://localhost:7322/api"
  timeout: "30s"
auth:
  email: ""
  session_token: ""
  request_credential: ""
jobs:
  default_datastore_size: "100G"
  ssh_timeout: "30s"
  ssh_key_path: "~/.ssh/id_rsa"
format:
  default: "table"
  colors: true
  timestamps: true
```

## Authentication Headers
Required headers for authenticated requests:
```
UserEmail: user@example.com
UserHash: [SHA256 hash of email]
RequestCredential: [UUID from login response]
Verification: [verification string - TBD]
```

## Development Workflow

### Middleware Dependency
**IMPORTANT**: The CLI requires the middleware service to be running for authentication and API calls.

To start the middleware in vibe coding:
```bash
@middleware/go start
```
This will start the .NET middleware service that the CLI communicates with.

### Using the `./go` script:
```bash
./go build              # Build the binary
./go dev --help         # Run in development mode
./go dev auth login     # Test auth login in dev mode
./go test               # Run tests
./go format             # Format code
./go release            # Create release builds
```

### Building and Testing:
```bash
./go build                    # Creates bin/rediacc
./bin/rediacc --help         # Test built binary
./go test                    # Run unit tests
./go test_coverage           # Run with coverage
```

## File Organization

### Commands Location:
- `cmd/auth/` - Authentication commands
- `cmd/company/` - Company management
- `cmd/teams/` - Team management
- `cmd/infra/` - Infrastructure (regions, bridges, machines)
- `cmd/jobs/` - Job operations (machine, repo, plugin)

### Internal Packages:
- `internal/api/` - HTTP client and API communication
- `internal/config/` - Configuration management
- `internal/format/` - Output formatting (table, JSON, YAML, text)
- `internal/models/` - Data structures
- `internal/utils/` - Validation and utilities

## Important Implementation Notes

### Error Handling:
- Use `utils.APIError` for API-related errors
- Use `utils.ValidationError` for input validation
- Use `utils.MultiError` for multiple validation errors
- Always check authentication with `client.IsAuthenticated()`

### Output Formatting:
- Use `format.Print(data)` for standard output
- Use `format.PrintSuccess()` for success messages
- Use `format.PrintError()` for error messages
- Support --output flag (table, json, yaml, text)

### Validation:
- Use functions in `internal/utils/validation.go`
- Validate emails with `utils.ValidateEmail()`
- Validate names with `utils.ValidateName()`
- Validate IPs with `utils.ValidateIP()`

### Testing Strategy:
- Unit tests for each internal package
- Integration tests for command execution
- Mock API responses in `tests/fixtures/responses/`
- Test configurations in `tests/fixtures/configs/`

## Next Implementation Priority

1. **Auth Commands** - Core login/logout functionality
2. **Company Commands** - Company management operations  
3. **Teams Commands** - Team operations
4. **Infrastructure Commands** - Regions, bridges, machines
5. **Jobs Commands** - SSH-based operations

## Dependencies
Core libraries used:
- `github.com/spf13/cobra` - CLI framework
- `github.com/spf13/viper` - Configuration management
- `github.com/olekukonko/tablewriter` - Table formatting
- `github.com/fatih/color` - Colored output
- `gopkg.in/yaml.v3` - YAML support

## Build Information
- **Go Version**: 1.21+
- **Module**: `github.com/rediacc/cli`
- **Binary Name**: `rediacc`
- **Version**: 1.0.0

## Quick Reference Commands

```bash
# Development
./go dev auth login --email test@example.com
./go dev company info
./go dev teams list

# Building
./go build
./bin/rediacc --version

# Testing
./go test
./go format
./go lint
```