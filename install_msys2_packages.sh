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
echo "=================================="
echo "Installation Complete!"
echo "=================================="
echo
echo "Installed packages:"
echo "  - rsync: $(rsync --version | head -1)"
echo "  - ssh: $(ssh -V 2>&1)"
echo
echo "You can now use Rediacc CLI on Windows!"
echo
echo "Close this terminal and run setup_windows.bat again to verify."
echo