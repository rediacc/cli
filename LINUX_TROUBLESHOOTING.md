# Linux/macOS Troubleshooting Guide for Rediacc CLI

## Common Issues and Solutions

### 1. "Permission denied" when running scripts

**Problem**: Scripts are not executable.

**Solution**:
```bash
chmod +x rediacc rediacc-cli rediacc-cli-sync rediacc-cli-term install.sh
```

Or run the installer:
```bash
./install.sh
# or
./rediacc setup
```

### 2. "Python3: command not found"

**Problem**: Python 3 is not installed or not in PATH.

**Solution**:
Run the installer to automatically install Python:
```bash
./install.sh
```

Or install manually:
```bash
# Ubuntu/Debian
sudo apt update && sudo apt install python3

# Fedora/RHEL
sudo dnf install python3

# macOS
brew install python3

# Alpine
sudo apk add python3
```

### 3. "rsync: command not found"

**Problem**: rsync is not installed.

**Solution**:
Run the installer:
```bash
./install.sh
```

Or install manually:
```bash
# Ubuntu/Debian
sudo apt install rsync

# Fedora/RHEL
sudo dnf install rsync

# macOS (should be pre-installed, but to update)
brew install rsync

# Alpine
sudo apk add rsync
```

### 4. SSH Connection Issues

**Problem**: SSH authentication fails or connection refused.

**Solution**:
1. Ensure SSH client is installed:
   ```bash
   ./install.sh
   ```

2. Check SSH key permissions (should be 600):
   ```bash
   ls -la ~/.ssh/
   chmod 600 ~/.ssh/id_rsa  # If needed
   ```

3. Test SSH connectivity:
   ```bash
   ssh -v user@host  # Verbose mode for debugging
   ```

### 5. ImportError: No module named 'rediacc_cli_core'

**Problem**: Running scripts from wrong directory.

**Solution**:
Always run scripts from the CLI directory:
```bash
cd /path/to/cli
./rediacc login
```

### 6. Vault Encryption Not Available

**Problem**: cryptography module not installed.

**Solution**:
```bash
pip3 install cryptography
# or
python3 -m pip install cryptography
```

### 7. "command not found" after installation

**Problem**: Scripts not in PATH.

**Solution**:
Option 1: Use the wrapper script from CLI directory:
```bash
cd /path/to/cli
./rediacc login
```

Option 2: Add to PATH (add to ~/.bashrc or ~/.zshrc):
```bash
export PATH="$PATH:/path/to/cli"
# Then you can use from anywhere:
rediacc login
```

Option 3: Create symlinks (installer can do this):
```bash
./install.sh
# Choose 'y' when asked about creating symlinks
```

### 8. Package Manager Issues

**Problem**: sudo/root access required but not available.

**Solution for non-root installation**:
1. Install Python locally:
   ```bash
   # Use pyenv or compile from source
   curl https://pyenv.run | bash
   pyenv install 3.9.0
   pyenv local 3.9.0
   ```

2. Use pre-compiled rsync binary or request from system admin

3. Most systems have SSH client pre-installed

### 9. SSL Certificate Errors

**Problem**: SSL certificate verification failed.

**Solution**:
1. Update certificates:
   ```bash
   # Ubuntu/Debian
   sudo apt install ca-certificates
   
   # Fedora/RHEL
   sudo dnf install ca-certificates
   
   # macOS
   brew install ca-certificates
   ```

2. For corporate proxies, set environment variables:
   ```bash
   export HTTP_PROXY=http://proxy.company.com:8080
   export HTTPS_PROXY=http://proxy.company.com:8080
   ```

## Testing Your Installation

Run the test command:
```bash
./rediacc test
# or
python3 test_windows_compat.py
```

Expected output:
- Platform: unix
- rsync command: rsync
- SSH available
- Python modules load correctly

## Quick Diagnostic

Run this command to check all dependencies:
```bash
./install.sh
```

It will show:
- ✓ for installed components
- ✗ for missing components
- Installation instructions for your specific OS

## Getting Help

1. Check installation status: `./install.sh`
2. Run compatibility test: `./rediacc test`
3. Check Python version: `python3 --version`
4. Check rsync version: `rsync --version`
5. Check SSH version: `ssh -V`

## Platform-Specific Notes

### macOS
- Most tools come pre-installed
- Use Homebrew for updates: `brew install python3 rsync`
- May need to allow terminal access in System Preferences > Security & Privacy

### Ubuntu/Debian
- Use apt for package management
- May need to install python3-pip separately: `sudo apt install python3-pip`

### RHEL/CentOS/Fedora
- Use dnf (Fedora 22+) or yum (older versions)
- May need EPEL repository for some packages

### Alpine Linux
- Minimal by default, most tools need installation
- Use apk for package management
- Python package is `python3`, not `python`

### WSL (Windows Subsystem for Linux)
- Works like regular Linux
- Ensure WSL2 for better performance
- File paths: `/mnt/c/Users/...` for Windows files