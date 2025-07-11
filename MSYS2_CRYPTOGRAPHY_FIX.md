# MSYS2 Cryptography Module Fix

## Problem
The warning "cryptography library not installed. Vault encryption will not be available." appears when using Rediacc CLI on Windows with MSYS2 because:
1. MSYS2 Python (`/usr/bin/python3`) and MinGW64 Python (`/mingw64/bin/python3`) are separate installations
2. The cryptography module needs to be installed for the correct Python environment
3. MSYS2 has an "externally managed environment" that prevents direct pip installations

## Solution

### 1. Install MinGW64 Python packages
```bash
pacman -S mingw-w64-x86_64-python-cryptography mingw-w64-x86_64-python-requests
```

### 2. Use the correct Python interpreter
The MinGW64 Python (`/mingw64/bin/python3`) has the cryptography module, while MSYS2 Python (`/usr/bin/python3`) does not.

### 3. Updated installation script
The `install_msys2_packages.sh` script now:
- Detects the system architecture
- Installs the correct MinGW64 packages for x86_64
- Falls back to pip with `--break-system-packages` if needed
- Verifies module availability

### 4. CLI wrapper update
The main `rediacc` wrapper now automatically detects MSYS2 environment and uses MinGW64 Python

## Usage

### Quick Fix (Manual)
```bash
# In MSYS2 terminal
pacman -S mingw-w64-x86_64-python-cryptography mingw-w64-x86_64-python-requests
```

### Automated Installation
```bash
# Run the updated installation script
./scripts/install_msys2_packages.sh
```

### Using the CLI
```bash
# Just use the regular wrapper - it automatically detects MSYS2
./rediacc --help

# The wrapper will use /mingw64/bin/python3 when MSYSTEM is set
```

## Technical Details

### Package Differences
- **MSYS2 packages** (`python-cryptography`): For MSYS2 Python, requires building from source
- **MinGW64 packages** (`mingw-w64-x86_64-python-cryptography`): Pre-built for Windows, works immediately

### Environment Detection
The CLI now checks for:
1. `$MSYSTEM` environment variable
2. Presence of `/mingw64/bin/python3`
3. Windows platform with MSYS2 paths

### Path Resolution
MSYS2 paths are converted:
- Windows: `C:\Users\muhammed\cli`
- MSYS2: `/c/Users/muhammed/cli`
- MinGW64 Python understands both formats