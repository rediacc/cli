# Rediacc CLI Development Guide

## Quick Start

### Prerequisites
- Go 1.21+ installed
- Docker (optional, for containerized development)
- Git

### Development Commands

```bash
# Build the CLI
./go build

# Run in development mode
./go dev --help
./go dev auth login --email test@example.com

# Run tests
./go test
./go test_coverage

# Format and lint code
./go format
./go lint

# Build for multiple platforms
./go release
```

### Docker Development

```bash
# Build and run development container
./go docker_dev

# Build production container
./go docker_prod

# Using docker-compose
docker-compose --profile dev up
docker-compose --profile prod up
```

## Project Structure

```
cli/
├── main.go                 # Entry point
├── go                     # Development script
├── CLAUDE.md              # AI context notes
├── IMPLEMENTATION_PLAN.md # Detailed implementation plan
├── cmd/                   # CLI commands
│   ├── root.go           # Root command setup
│   ├── auth/             # Authentication commands
│   ├── company/          # Company management
│   ├── teams/            # Team management
│   ├── infra/            # Infrastructure commands
│   └── ...               # Other command groups
├── internal/             # Internal packages
│   ├── api/             # HTTP client
│   ├── config/          # Configuration management
│   ├── format/          # Output formatting
│   ├── models/          # Data structures
│   └── utils/           # Utilities
├── scripts/             # Build scripts
├── docs/                # Documentation
└── tests/               # Test files
```

## Configuration

The CLI uses a YAML configuration file at `~/.rediacc-cli.yaml`:

```yaml
server:
  url: "http://localhost:8080"
  timeout: "30s"
auth:
  email: ""
  session_token: ""
  request_credential: ""
format:
  default: "table"
  colors: true
```

## Adding New Commands

1. Create command file in appropriate `cmd/` subdirectory
2. Implement the command using Cobra patterns
3. Add to parent command in `init()` function
4. Use the API client to call stored procedures
5. Format output using the format package

Example:
```go
var loginCmd = &cobra.Command{
    Use:   "login",
    Short: "Login to Rediacc",
    RunE:  runLogin,
}

func runLogin(cmd *cobra.Command, args []string) error {
    email, _ := cmd.Flags().GetString("email")
    
    client := api.NewClient(config.Get().Server.URL)
    response, err := client.Login(email, password)
    if err != nil {
        return err
    }
    
    return format.PrintSuccess("Logged in successfully")
}
```

## API Integration

All API calls go through the `internal/api` client which:
- Handles authentication headers
- Executes stored procedures via HTTP
- Manages session tokens
- Provides error handling

## Output Formatting

The CLI supports multiple output formats:
- `table` - Human-readable tables (default)
- `json` - Machine-readable JSON
- `yaml` - YAML format
- `text` - Simple text output

Use `--output` flag or set in configuration.

## Testing

```bash
# Run all tests
./go test

# Run with coverage
./go test_coverage

# Run specific tests
go test ./internal/api/...

# Run integration tests
go test ./tests/integration/...
```

## Build and Release

```bash
# Local build
./go build

# Multi-platform release
./go release

# Install globally
./go install
```

## Docker Usage

### Development
```bash
# Interactive development container
./go docker_dev

# With docker-compose
docker-compose --profile dev up
```

### Production
```bash
# Production container
docker build -t rediacc-cli .
docker run -it --rm rediacc-cli --help
```

## Environment Variables

- `REDIACC_SERVER_URL` - Override server URL
- `REDIACC_CONFIG` - Override config file path
- `REDIACC_DEBUG` - Enable debug mode

## Troubleshooting

### Common Issues

1. **Build failures**: Ensure Go 1.21+ is installed
2. **Import errors**: Run `./go deps` to update modules
3. **Authentication issues**: Check server URL and credentials
4. **Docker issues**: Ensure Docker is running

### Debug Mode

Enable debug output:
```bash
./go dev --debug command
# or
export REDIACC_DEBUG=true
```

### Configuration Issues

Reset configuration:
```bash
rm ~/.rediacc-cli.yaml
./go dev config init
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make changes following the existing patterns
4. Add tests for new functionality
5. Run `./go format` and `./go lint`
6. Submit a pull request

## Next Steps

The core foundation is complete. Next phase involves implementing:
1. Authentication commands
2. Company management commands
3. Team management commands
4. Infrastructure commands
5. Job execution commands

See `IMPLEMENTATION_PLAN.md` for detailed next steps.