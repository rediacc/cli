#!/bin/bash
# MSYS2 package installation script for Rediacc CLI
# This script should be run inside MSYS2 terminal

echo "=================================="
echo "MSYS2 Package Installer for Rediacc CLI"
echo "=================================="
echo

# Function to check if a command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Update package database
echo "Step 1: Updating MSYS2 package database..."
echo "Running: pacman -Syu"
echo
pacman -Syu --noconfirm

echo
echo "Step 2: Installing required packages..."
echo

# Check and install rsync
if command_exists rsync; then
    echo "[✓] rsync is already installed ($(rsync --version | head -1))"
else
    echo "[×] rsync is not installed. Installing..."
    pacman -S --noconfirm rsync
    if [ $? -eq 0 ]; then
        echo "[✓] rsync installed successfully"
    else
        echo "[!] Failed to install rsync"
        exit 1
    fi
fi

echo

# Check and install openssh
if command_exists ssh; then
    echo "[✓] SSH client is already installed ($(ssh -V 2>&1))"
else
    echo "[×] SSH client is not installed. Installing..."
    pacman -S --noconfirm openssh
    if [ $? -eq 0 ]; then
        echo "[✓] openssh installed successfully"
    else
        echo "[!] Failed to install openssh"
        exit 1
    fi
fi

echo

# Check and install Python if needed
if command_exists python3; then
    echo "[✓] Python3 is already installed ($(python3 --version))"
else
    echo "[×] Python3 is not installed. Installing..."
    pacman -S --noconfirm python
    if [ $? -eq 0 ]; then
        echo "[✓] Python3 installed successfully"
    else
        echo "[!] Failed to install Python3"
        exit 1
    fi
fi

echo

# Check and install pip if needed
if python3 -m pip --version >/dev/null 2>&1; then
    echo "[✓] pip is already installed ($(python3 -m pip --version))"
else
    echo "[×] pip is not installed. Installing..."
    pacman -S --noconfirm python-pip
    if [ $? -eq 0 ]; then
        echo "[✓] pip installed successfully"
    else
        echo "[!] Failed to install pip"
        exit 1
    fi
fi

echo
echo "Step 3: Installing Python dependencies..."
echo

# Install Python packages via pacman
echo "Installing Python packages via pacman..."

# Detect architecture and MSYS2 environment
ARCH=$(uname -m)
echo "Detected architecture: $ARCH"

# First search for available packages - prefer mingw64 for x86_64
echo "Searching for available Python packages..."
if [ "$ARCH" = "x86_64" ]; then
    # For x86_64, prefer mingw64 packages
    CRYPTO_PKG=$(pacman -Ss "python.*cryptography" 2>/dev/null | grep -E "^(mingw64|ucrt64|clang64|msys)/" | grep -E "(x86_64|any)" | head -1 | awk '{print $1}' | sed 's|.*/||')
    # For requests, search more specifically
    REQUESTS_PKG=$(pacman -Ss "python-requests" 2>/dev/null | grep -E "^(mingw64|ucrt64|clang64|msys)/" | grep -E "(x86_64|any)" | head -1 | awk '{print $1}' | sed 's|.*/||')
else
    # For other architectures
    CRYPTO_PKG=$(pacman -Ss "python.*cryptography" 2>/dev/null | grep -E "^(mingw|ucrt|clang|msys)" | head -1 | awk '{print $1}' | sed 's|.*/||')
    REQUESTS_PKG=$(pacman -Ss "python-requests" 2>/dev/null | grep -E "^(mingw|ucrt|clang|msys)" | head -1 | awk '{print $1}' | sed 's|.*/||')
fi

# Install development dependencies
echo "Installing development dependencies..."
pacman -S --noconfirm --needed \
    gcc \
    make \
    pkg-config \
    libffi-devel \
    openssl-devel

# Try to install cryptography
if [ -n "$CRYPTO_PKG" ]; then
    echo "Found cryptography package: $CRYPTO_PKG"
    pacman -S --noconfirm --needed "$CRYPTO_PKG"
else
    echo "Cryptography package not found in pacman, trying mingw packages..."
    # Try mingw packages if running in MINGW environment
    if [ -n "$MSYSTEM" ] && [[ "$MSYSTEM" == "MINGW"* ]]; then
        pacman -S --noconfirm --needed mingw-w64-x86_64-python-cryptography || true
    fi
fi

# Try to install requests
if [ -n "$REQUESTS_PKG" ]; then
    echo "Found requests package: $REQUESTS_PKG"
    pacman -S --noconfirm --needed "$REQUESTS_PKG"
else
    echo "Requests package not found in pacman, trying mingw packages..."
    # Try mingw packages if running in MINGW environment
    if [ -n "$MSYSTEM" ] && [[ "$MSYSTEM" == "MINGW"* ]]; then
        pacman -S --noconfirm --needed mingw-w64-x86_64-python-requests || true
    fi
fi

# If packages are still not available, try a different approach
if ! python3 -c "import cryptography" 2>/dev/null || ! python3 -c "import requests" 2>/dev/null; then
    echo "Some packages are missing, trying alternative installation methods..."
    
    # First, try installing pre-built wheels if available
    echo "Attempting to install pre-built wheels..."
    python3 -m pip install --break-system-packages --user --only-binary :all: cryptography requests 2>/dev/null || true
    
    # If that fails, try installing without build isolation
    if ! python3 -c "import cryptography" 2>/dev/null; then
        echo "Still missing cryptography, trying MSYS2 system packages..."
        # Try to use system packages for MSYS2
        pacman -S --noconfirm --needed python-cryptography 2>/dev/null || true
    fi
fi

echo
echo "Step 4: Verifying installation..."
echo

# Test cryptography module
if python3 -c "import cryptography" 2>/dev/null; then
    echo "[✓] cryptography module is working correctly"
else
    echo "[×] cryptography module test failed"
    echo "Attempting alternative installation..."
    
    # Try installing with pip using --break-system-packages
    python3 -m pip install --break-system-packages --upgrade --user pip
    python3 -m pip install --break-system-packages --upgrade --user cryptography
    
    # Test again
    if python3 -c "import cryptography" 2>/dev/null; then
        echo "[✓] cryptography module is now working"
    else
        echo "[!] Warning: cryptography module still not working"
        echo "    This might require manual installation or using a virtual environment"
    fi
fi

# Test requests module
if python3 -c "import requests" 2>/dev/null; then
    echo "[✓] requests module is working correctly"
else
    echo "[×] requests module not found. Installing..."
    python3 -m pip install --break-system-packages --user requests
fi

echo
echo "=================================="
echo "Installation Complete!"
echo "=================================="
echo
echo "Installed packages:"
echo "  - rsync: $(rsync --version | head -1)"
echo "  - ssh: $(ssh -V 2>&1)"
echo "  - python3: $(python3 --version)"
echo "  - pip: $(python3 -m pip --version)"
echo

# Check module availability
echo "Python modules status:"
python3 -c "import cryptography; print('  - cryptography:', cryptography.__version__)" 2>/dev/null || echo "  - cryptography: NOT INSTALLED"
python3 -c "import requests; print('  - requests:', requests.__version__)" 2>/dev/null || echo "  - requests: NOT INSTALLED"

echo
echo "You can now use Rediacc CLI on Windows!"
echo
echo "Close this terminal and run setup_windows.bat again to verify."
echo