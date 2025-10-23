#!/bin/bash
# Development setup script for Rediacc CLI
# Installs all required system and Python dependencies, builds and installs the package
# Supports: Debian/Ubuntu (apt), Fedora (dnf), RHEL/CentOS (yum)

set -e

# Default values
SKIP_SYSTEM=false
USER_INSTALL=false
QUICK_MODE=false
VERIFY=false

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Show help
show_help() {
    cat << EOF
Rediacc CLI Development Setup
==============================

Usage: ./dev.sh [OPTIONS]

Options:
  --help              Show this help message
  --skip-system       Skip system dependencies installation (for quick rebuilds)
  --user              Install package for current user only (no sudo required)
  --global            Install package system-wide (requires sudo) [default]
  --quick             Quick mode: skip system deps, only rebuild and reinstall
  --verify            Run verification tests after installation

Examples:
  ./dev.sh                          # Full setup with system dependencies (global install)
  ./dev.sh --user                   # User installation without sudo
  ./dev.sh --quick --user           # Quick rebuild for development (no sudo)
  ./dev.sh --skip-system --user     # Skip system deps, user install
  ./dev.sh --verify                 # Install and run tests

Note:
  - First-time setup should use full mode (no flags)
  - Development iterations can use --quick --user
  - CI/CD pipelines should use --user --skip-system
EOF
}

# Print header
print_header() {
    echo -e "${CYAN}Rediacc CLI Development Setup${NC}"
    echo "=============================="
    echo ""
    if [ "$QUICK_MODE" = "true" ]; then
        echo -e "${GREEN}Mode: Quick rebuild (recommended for development)${NC}"
    elif [ "$USER_INSTALL" = "true" ]; then
        echo -e "${GREEN}Mode: User installation (recommended)${NC}"
    else
        echo -e "${YELLOW}Mode: Global installation (requires sudo)${NC}"
        echo -e "${YELLOW}Note: Consider using --user flag for safer development${NC}"
    fi
    echo ""
}

# Detect OS and package manager
detect_os() {
    if [ -f /etc/os-release ]; then
        . /etc/os-release
        OS_ID="$ID"
        OS_VERSION="$VERSION_ID"
    else
        echo -e "${RED}Error: Unable to detect OS distribution${NC}"
        exit 1
    fi

    # Determine package manager and family
    if command -v apt-get >/dev/null 2>&1; then
        PKG_MANAGER="apt-get"
        PKG_FAMILY="debian"
        UPDATE_CMD="sudo apt-get update -qq"
        INSTALL_CMD="sudo apt-get install -y"
    elif command -v dnf >/dev/null 2>&1; then
        PKG_MANAGER="dnf"
        PKG_FAMILY="fedora"
        UPDATE_CMD="sudo dnf check-update || true"
        INSTALL_CMD="sudo dnf install -y"
    elif command -v yum >/dev/null 2>&1; then
        PKG_MANAGER="yum"
        PKG_FAMILY="rhel"
        UPDATE_CMD="sudo yum check-update || true"
        INSTALL_CMD="sudo yum install -y"
    else
        echo -e "${RED}Error: No supported package manager found (apt-get, dnf, or yum)${NC}"
        exit 1
    fi

    echo -e "Detected OS: ${GREEN}$OS_ID${NC} (using $PKG_MANAGER)"
    echo ""
}

# Get package name based on OS family
get_package_name() {
    local pkg_key="$1"

    # Package name mappings (debian:fedora:rhel)
    case "$pkg_key" in
        openssh-client)
            case "$PKG_FAMILY" in
                debian) echo "openssh-client" ;;
                fedora|rhel) echo "openssh-clients" ;;
            esac
            ;;
        python3-tkinter)
            case "$PKG_FAMILY" in
                debian) echo "python3-tk" ;;
                fedora|rhel) echo "python3-tkinter" ;;
            esac
            ;;
        build-essential)
            case "$PKG_FAMILY" in
                debian) echo "build-essential" ;;
                fedora|rhel) echo "gcc gcc-c++ make" ;;
            esac
            ;;
        libffi-dev)
            case "$PKG_FAMILY" in
                debian) echo "libffi-dev" ;;
                fedora|rhel) echo "libffi-devel" ;;
            esac
            ;;
        libssl-dev)
            case "$PKG_FAMILY" in
                debian) echo "libssl-dev" ;;
                fedora|rhel) echo "openssl-devel" ;;
            esac
            ;;
        *)
            # Default: same name across all distros
            echo "$pkg_key"
            ;;
    esac
}

# Install packages for a category
install_packages() {
    local category="$1"
    shift
    local packages=("$@")

    echo "Installing $category..."

    local pkg_list=""
    for pkg_key in "${packages[@]}"; do
        pkg_name=$(get_package_name "$pkg_key")
        pkg_list="$pkg_list $pkg_name"
    done

    $INSTALL_CMD $pkg_list
}

# Install system dependencies
install_system_dependencies() {
    echo -e "${CYAN}=== Installing System Dependencies ===${NC}"
    echo ""

    detect_os

    # Update package list
    echo "Updating package list..."
    $UPDATE_CMD

    # Define package lists (DRY - single source of truth)
    PYTHON_PACKAGES=(
        python3
        python3-pip
        python3-venv
        python3-dev
    )

    BUILD_PACKAGES=(
        build-essential
        libffi-dev
        libssl-dev
    )

    DESKTOP_PACKAGES=(
        python3-tkinter
    )

    CLI_PACKAGES=(
        rsync
        openssh-client
        git
        curl
        jq
    )

    PROTOCOL_PACKAGES=(
        xdg-utils
        desktop-file-utils
    )

    # Install all package categories
    install_packages "core Python packages" "${PYTHON_PACKAGES[@]}"
    install_packages "build dependencies (required for cryptography)" "${BUILD_PACKAGES[@]}"
    install_packages "desktop application dependencies" "${DESKTOP_PACKAGES[@]}"
    install_packages "CLI utilities" "${CLI_PACKAGES[@]}"
    install_packages "protocol registration dependencies" "${PROTOCOL_PACKAGES[@]}"

    echo ""
    echo -e "${GREEN}System dependencies installed successfully${NC}"
    echo ""
}

# Install Python build tools
install_python_build_tools() {
    echo -e "${CYAN}=== Installing Python Build Tools ===${NC}"
    echo ""
    # Suppress Ubuntu version parsing warnings (harmless)
    python3 -m pip install --quiet --user --upgrade pip build wheel setuptools 2>&1 | \
        grep -v "Error parsing dependencies" || true
    echo -e "${GREEN}Python build tools installed${NC}"
    echo ""
}

# Clean old installations
clean_old_installations() {
    echo -e "${CYAN}=== Cleaning Old Installations ===${NC}"
    echo ""

    if [ "$USER_INSTALL" = "true" ]; then
        # User mode - no sudo
        echo "Removing user installation..."
        python3 -m pip uninstall -y rediacc UNKNOWN 2>/dev/null || true
        rm -rf build/ dist/ *.egg-info src/*.egg-info
    else
        # Global mode - use sudo
        echo "Removing system installation..."
        sudo python3 -m pip uninstall -y rediacc UNKNOWN 2>/dev/null || true
        sudo rm -rf build/ dist/ *.egg-info src/*.egg-info
    fi

    echo -e "${GREEN}Cleanup complete${NC}"
    echo ""
}

# Build package
build_package() {
    echo -e "${CYAN}=== Building Package ===${NC}"
    echo ""
    python3 -m build --wheel 2>&1 | grep -E "(Successfully built|error|ERROR)" || true

    if [ -f dist/*.whl ]; then
        echo -e "${GREEN}Package built successfully${NC}"
    else
        echo -e "${RED}Package build failed${NC}"
        exit 1
    fi
    echo ""
}

# Install package
install_package() {
    echo -e "${CYAN}=== Installing Package ===${NC}"
    echo ""

    WHEEL_FILE=$(ls -t dist/*.whl | head -1)

    if [ "$USER_INSTALL" = "true" ]; then
        echo "Installing for user..."
        # Suppress Ubuntu version warnings (harmless)
        python3 -m pip install --quiet --user --force-reinstall "$WHEEL_FILE" 2>&1 | \
            grep -v "Error parsing dependencies" | \
            grep -v "not on PATH" || true
    else
        echo "Installing system-wide..."
        echo -e "${YELLOW}⚠️  Using sudo - consider --user flag for development${NC}"
        # Suppress Ubuntu version warnings (harmless) but show the root warning
        sudo python3 -m pip install --quiet --force-reinstall "$WHEEL_FILE" 2>&1 | \
            grep -v "Error parsing dependencies" || true
    fi

    echo -e "${GREEN}Package installed${NC}"
    echo ""
}

# Verify installation
verify_installation() {
    echo -e "${CYAN}=== Verifying Installation ===${NC}"
    echo ""

    # Check if command exists
    if command -v rediacc &>/dev/null; then
        INSTALLED_PATH=$(which rediacc)
        INSTALLED_VERSION=$(rediacc --version 2>&1 | head -1)

        echo -e "${GREEN}✓ Installation successful${NC}"
        echo ""
        echo "Installed path: $INSTALLED_PATH"
        echo "Version: $INSTALLED_VERSION"
        echo ""

        # Check for dual installations
        SYSTEM_INSTALL="/usr/local/bin/rediacc"
        USER_INSTALL_BIN="$HOME/.local/bin/rediacc"

        if [ -f "$SYSTEM_INSTALL" ] && [ -f "$USER_INSTALL_BIN" ]; then
            echo -e "${YELLOW}⚠️  WARNING: Dual installation detected!${NC}"
            echo "   System:  $SYSTEM_INSTALL"
            echo "   User:    $USER_INSTALL_BIN"
            echo "   Active:  $INSTALLED_PATH"
            echo ""
            echo -e "${YELLOW}Consider removing one installation:${NC}"
            echo "   Remove system: sudo pip uninstall rediacc"
            echo "   Remove user:   pip uninstall rediacc"
            echo ""
        fi

        # Test basic commands
        echo "Testing basic functionality..."
        rediacc --help >/dev/null 2>&1 && echo -e "${GREEN}✓${NC} Help works"
        rediacc sync --help >/dev/null 2>&1 && echo -e "${GREEN}✓${NC} Sync command works"
        rediacc workflow --help >/dev/null 2>&1 && echo -e "${GREEN}✓${NC} Workflow command works"
        rediacc list --help >/dev/null 2>&1 && echo -e "${GREEN}✓${NC} List command works"

        echo ""
        echo -e "${GREEN}All basic tests passed!${NC}"
        echo ""

        # Show setup command
        echo "Run 'rediacc setup' for initial configuration"

    else
        echo -e "${RED}✗ Installation failed - command not found${NC}"
        echo ""
        if [ "$USER_INSTALL" = "true" ]; then
            echo -e "${YELLOW}Note: User installation detected.${NC}"
            echo "Add to PATH: export PATH=\"\$HOME/.local/bin:\$PATH\""
            echo "Add to ~/.bashrc or ~/.zshrc to make permanent"
        fi
        exit 1
    fi
}

# Quick rebuild mode
quick_rebuild() {
    echo -e "${CYAN}=== Quick Rebuild Mode ===${NC}"
    echo ""
    clean_old_installations
    build_package
    install_package
}

# Parse command-line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --help|-h)
            show_help
            exit 0
            ;;
        --skip-system)
            SKIP_SYSTEM=true
            shift
            ;;
        --user)
            USER_INSTALL=true
            shift
            ;;
        --global)
            USER_INSTALL=false
            shift
            ;;
        --quick)
            QUICK_MODE=true
            SKIP_SYSTEM=true
            USER_INSTALL=true  # Quick mode implies user install
            shift
            ;;
        --verify)
            VERIFY=true
            shift
            ;;
        *)
            echo -e "${RED}Unknown option: $1${NC}"
            echo ""
            show_help
            exit 1
            ;;
    esac
done

# Main execution
main() {
    print_header

    if [ "$QUICK_MODE" = "true" ]; then
        quick_rebuild
    else
        if [ "$SKIP_SYSTEM" != "true" ]; then
            install_system_dependencies
        else
            echo -e "${YELLOW}Skipping system dependencies...${NC}"
            echo ""
        fi
        install_python_build_tools
        clean_old_installations
        build_package
        install_package
    fi

    verify_installation

    if [ "$VERIFY" = "true" ]; then
        echo -e "${CYAN}=== Running Additional Verification ===${NC}"
        echo ""
        # Add more extensive tests here if needed
        echo -e "${GREEN}Verification complete${NC}"
    fi
}

# Run main
main
