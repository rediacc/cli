# Installation Guide

This guide covers the installation of Rediacc CLI tools on different platforms.

## Prerequisites

### All Platforms
- Python 3.6 or higher
- pip (Python package installer)
- Internet connection

### Platform-Specific Requirements

#### Linux/macOS
- bash shell
- rsync
- OpenSSH client

#### Windows
- PowerShell 5.0 or higher
- MSYS2 (for rsync functionality)

## Installation Methods

### 1. Automated Installation (Recommended)

#### Linux/macOS
```bash
# Clone or download the repository
git clone <repository-url>
cd cli

# Run automated installer
./install.sh --auto
```

#### Windows
```powershell
# Clone or download the repository
git clone <repository-url>
cd cli

# Run PowerShell installer
.\rediacc.ps1 setup -AutoInstall
```

### 2. Interactive Installation

```bash
# Linux/macOS
./rediacc setup

# Windows
.\rediacc.ps1 setup
```

The interactive installer will:
1. Check Python version
2. Install required Python packages
3. Verify system dependencies
4. Configure the environment

### 3. Manual Installation

#### Step 1: Install Python Dependencies
```bash
pip install -r requirements.txt
```

#### Step 2: Install System Dependencies

**Linux (Debian/Ubuntu)**:
```bash
sudo apt-get update
sudo apt-get install -y rsync openssh-client
```

**Linux (RHEL/CentOS)**:
```bash
sudo yum install -y rsync openssh-clients
```

**macOS**:
```bash
# rsync and ssh are pre-installed on macOS
# If needed, install via Homebrew:
brew install rsync
```

**Windows**:
1. Install MSYS2 from https://www.msys2.org/
2. Open MSYS2 terminal and run:
```bash
pacman -S rsync openssh
```
3. Add MSYS2 to your PATH:
   - Default location: `C:\msys64\usr\bin`

#### Step 3: Verify Installation
```bash
# Check Python
python3 --version

# Check rsync (except Windows CMD)
rsync --version

# Check SSH
ssh -V
```

## Post-Installation Setup

### 1. Authentication
```bash
# Login to your Rediacc account
./rediacc login
```

### 2. Verify Connection
```bash
# Test API connection
./rediacc-cli list teams
```

### 3. Configure Defaults (Optional)
```bash
# Set default team
./rediacc-cli config set default_team "MyTeam"

# Set default output format
./rediacc-cli config set output_format "json"
```

## Troubleshooting Installation

### Python Not Found
- Ensure Python 3.6+ is installed
- Check if `python3` is in your PATH
- On Windows, try `python` instead of `python3`

### MSYS2 Issues (Windows)
- Ensure MSYS2 bin directory is in PATH
- Restart terminal after PATH changes
- Run MSYS2 terminal as administrator for package installation

### Permission Errors
- On Linux/macOS, you may need to use `sudo` for system package installation
- Ensure you have write permissions to `~/.rediacc/` directory

### SSL/TLS Errors
- Update your system's certificate store
- Install/update `ca-certificates` package
- For Python: `pip install --upgrade certifi`

## Updating

To update the CLI tools:

```bash
# Pull latest changes
git pull

# Re-run setup to update dependencies
./rediacc setup
```

## Uninstallation

To remove Rediacc CLI:

1. Remove the CLI directory
2. Remove configuration: `rm -rf ~/.rediacc/`
3. Uninstall Python packages: `pip uninstall -r requirements.txt`