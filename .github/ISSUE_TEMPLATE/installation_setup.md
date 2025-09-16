---
name: Installation/Setup Issue
about: Report problems with installing or setting up Rediacc CLI
title: '[SETUP] '
labels: 'installation, needs-triage'
assignees: ''
---

## Installation Issue Description
<!-- Describe the installation or setup problem you're experiencing -->

## Environment

### System Information
- **Operating System**: <!-- e.g., Ubuntu 22.04, macOS 14.0, Windows 11 -->
- **Architecture**: <!-- x86_64, arm64, etc. -->
- **Python Version**: <!-- Run: python --version or python3 --version -->
- **pip Version**: <!-- Run: pip --version -->

### Installation Method Attempted
<!-- Check the method you tried -->
- [ ] pip install (`pip install rediacc-cli`)
- [ ] Manual installation (`./scripts/install.sh`)
- [ ] Windows batch installation (`rediacc.bat setup`)
- [ ] Docker installation
- [ ] Development setup
- [ ] Other: <!-- Specify -->

## Pre-Installation Checks

### Python Environment
```bash
# Python installation check
which python3  # or where python on Windows
python3 --version

# pip availability
which pip3  # or where pip on Windows
pip3 --version

# Virtual environment (if used)
# Specify if using venv, conda, pyenv, etc.
```

### Platform-Specific Requirements

<details>
<summary>Windows Requirements</summary>

- [ ] Python 3.8+ installed
- [ ] MSYS2 installed (for rsync support)
- [ ] Command Prompt or PowerShell available
- [ ] Administrator privileges (if needed)

```powershell
# Check PowerShell version
$PSVersionTable.PSVersion

# Check if MSYS2 is installed
Test-Path "C:\msys64"

# Check if rsync is available (in MSYS2)
C:\msys64\usr\bin\bash.exe -c "rsync --version"
```

</details>

<details>
<summary>Linux/macOS Requirements</summary>

- [ ] Python 3.8+ installed
- [ ] rsync installed
- [ ] OpenSSH client installed
- [ ] tkinter (for GUI) - optional

```bash
# Check dependencies
rsync --version
ssh -V
python3 -c "import tkinter" 2>/dev/null && echo "tkinter available" || echo "tkinter not found"
```

</details>

## Installation Steps Taken
<!-- List the exact steps you followed -->

1. <!-- Step 1 -->
2. <!-- Step 2 -->
3. <!-- Step 3 -->

### Commands Executed
```bash
# Paste the exact commands you ran
```

## Error Messages

### Installation Error
```
# Paste the complete error output here
```

### Import/Module Errors
```python
# If getting Python import errors, paste them here
```

## Installation Logs

<details>
<summary>pip install log (if applicable)</summary>

```
# Run with: pip install --verbose rediacc-cli
# Paste output here
```

</details>

<details>
<summary>Manual installation log</summary>

```
# Paste install.sh or setup script output
```

</details>

## Post-Installation Issues

### Configuration Problems
- [ ] Config file not created
- [ ] Permissions issues
- [ ] Path not set correctly

```bash
# Check installation
ls -la ~/.rediacc/  # Config directory
which rediacc       # Command availability
./rediacc --version # Version check
```

### First Run Issues
```bash
# What happens when you first run the CLI?
./rediacc --help
```

## Dependency Status

### Python Packages
```bash
# List installed packages
pip list | grep -E "(rediacc|requests|cryptography|paramiko)"

# Or check requirements
pip freeze > current_packages.txt
```

### System Dependencies
- **rsync**: <!-- Installed/Not installed/Version -->
- **OpenSSH**: <!-- Installed/Not installed/Version -->
- **tkinter**: <!-- Available/Not available -->
- **MSYS2** (Windows): <!-- Installed/Not installed -->

## Attempted Solutions
<!-- What have you tried to resolve the issue? -->

- [ ] Reinstalled Python
- [ ] Used virtual environment
- [ ] Installed missing dependencies
- [ ] Ran as administrator/sudo
- [ ] Cleared pip cache
- [ ] Other: <!-- Specify -->

## Additional Information

### Network Configuration
- **Behind Corporate Proxy**: <!-- Yes/No -->
- **Firewall Restrictions**: <!-- Yes/No -->
- **PyPI Access**: <!-- Can you access pypi.org? -->

### Related Documentation Consulted
- [ ] [Installation Guide](docs/INSTALLATION.md)
- [ ] [Troubleshooting Guide](docs/guides/TROUBLESHOOTING.md)
- [ ] [Development Guide](docs/guides/DEVELOPMENT.md)

## Possible Cause
<!-- If you have any ideas about what might be causing the issue -->

## System Diagnostics
```bash
# Run this diagnostic command if possible:
python3 -c "
import sys
import platform
print(f'Python: {sys.version}')
print(f'Platform: {platform.platform()}')
print(f'Architecture: {platform.machine()}')
try:
    import rediacc_cli
    print(f'Rediacc CLI installed: {rediacc_cli.__version__}')
except ImportError:
    print('Rediacc CLI not found')
"
```

---
<!-- 
Before submitting:
1. Check the installation documentation thoroughly
2. Ensure you meet all system requirements
3. Try installation in a clean virtual environment
4. Remove any sensitive information from logs
-->