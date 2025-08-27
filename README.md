# Rediacc CLI - Infrastructure Protection Platform

**Built for 60-second recovery from infrastructure failures.** Instant cloning, time-travel recovery, and 90% storage reduction.

This directory contains the Rediacc command-line tools for infrastructure protection and disaster recovery.

## 🚀 Why Rediacc?

### Protection Against Common Disasters
- **AI Agent Risks**: Isolate AI operations with instant cloning - production stays safe
- **Regional Outages**: Cross-continental failover for business continuity
- **Data Loss Events**: Time-travel recovery from any point in the last 3 weeks

### Your Protection Arsenal
- **🤖 AI Safety**: AI works on clones, production untouchable
- **💰 90% Storage Savings**: 300TB → 3TB for 10TB database
- **⏰ Time Travel**: Restore to any point in last 3 weeks
- **🌍 Cross-Continental**: Instant failover between regions
- **🚀 Instant Scaling**: Clone 100TB in 3 seconds

## Configuration

The CLI requires configuration via environment variables:

```bash
cp .env.example .env
# Edit .env with your API settings
```

Required:
- `SYSTEM_HTTP_PORT`: API port (e.g., 7322)
- `SYSTEM_API_URL`: API URL (e.g., http://localhost:7322/api)

## Quick Start - Get Protected in 60 Seconds

```bash
# Linux/macOS
./rediacc login                                      # Authenticate
./rediacc create clone --source prod --name ai-safe # Create AI-safe environment
./rediacc backup create --repo production           # Instant backup
./rediacc restore --point-in-time "1 hour ago"      # Time travel recovery

# Windows PowerShell
.\rediacc.ps1 login                                 # Authenticate  
.\rediacc.ps1 create clone --source prod --name test # Safe testing environment

# Launch desktop application for visual management
./rediacc desktop                                    # Desktop application
```

## Directory Structure

```
cli/
├── rediacc             # Linux/macOS wrapper script
├── rediacc.ps1         # Windows PowerShell wrapper
├── src/                # Python source code
│   ├── cli/           # CLI executables
│   ├── modules/       # Shared Python modules
│   └── config/        # Configuration files
├── docs/              # Documentation
├── docker/            # Docker files
├── scripts/           # Setup and utility scripts
└── tests/             # Test files
```

## 📊 Key Benefits

- **90% storage reduction** with Copy-on-Write technology
- **60-second recovery** from any disaster scenario
- **3-week retention** with hourly snapshots
- **Instant cloning** even for 100TB databases
- **Cross-continental** replication and failover

## Documentation

- [Complete CLI Guide](docs/README.md) - All commands and features
- [Disaster Recovery](docs/guides/) - Recovery procedures
- [Desktop Application Documentation](docs/DESKTOP.md) - Desktop application interface
- [AI Safety Guide](https://rediacc.com/docs/guides/ai-safety) - Protect against AI disasters

## Installation

For PyPI: `pip install rediacc`

For local development: See [docs/README.md](docs/README.md)

## Docker Support

The CLI can also be run using Docker.

**Important**: Docker volumes now use a local config directory (`./cli/.config`) instead of the user's home directory (`~/.config`). This provides better isolation and portability for containerized environments.

### Running with Docker

```bash
# Build image
docker build -f docker/Dockerfile -t rediacc/cli:latest .

# Run CLI
docker run --rm -v ./cli/.config:/home/rediacc/.config rediacc/cli:latest

# Interactive shell
docker run -it --rm -v ./cli/.config:/home/rediacc/.config rediacc/cli:latest /bin/bash
```

See [docker/README.md](docker/README.md) for complete Docker documentation including details about the local config directory.

## 🆘 Emergency Support

**Currently experiencing downtime?** Contact emergency@rediacc.com for immediate assistance.

- **Community Forum**: https://community.rediacc.com
- **Enterprise Support**: 24/7 for Premium/Elite customers
- **Documentation**: https://rediacc.com/docs

## License

Proprietary - Part of the Rediacc infrastructure protection platform. Free tier available.