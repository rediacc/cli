#!/bin/bash
# Rediacc CLI Installation Script for Linux/macOS
# This script checks and installs required dependencies

set -e

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Helper functions
print_header() {
    echo -e "${CYAN}=== $1 ===${NC}"
}

print_success() {
    echo -e "${GREEN}[✓] $1${NC}"
}

print_error() {
    echo -e "${RED}[✗] $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}[!] $1${NC}"
}

print_info() {
    echo -e "${BLUE}[i] $1${NC}"
}

# Detect OS
detect_os() {
    if [[ "$OSTYPE" == "linux-gnu"* ]]; then
        # Detect Linux distribution
        if [ -f /etc/os-release ]; then
            . /etc/os-release
            OS=$ID
            OS_FAMILY=$ID_LIKE
            OS_VERSION=$VERSION_ID
        else
            OS="unknown"
        fi
    elif [[ "$OSTYPE" == "darwin"* ]]; then
        OS="macos"
        OS_FAMILY="macos"
        OS_VERSION=$(sw_vers -productVersion)
    else
        OS="unknown"
    fi
}

# Check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Check Python installation
check_python() {
    print_header "Checking Python"
    
    if command_exists python3; then
        PYTHON_CMD="python3"
        PYTHON_VERSION=$($PYTHON_CMD --version 2>&1 | awk '{print $2}')
        print_success "Python $PYTHON_VERSION found"
        
        # Check version (need 3.6+)
        MAJOR=$(echo $PYTHON_VERSION | cut -d. -f1)
        MINOR=$(echo $PYTHON_VERSION | cut -d. -f2)
        
        if [ $MAJOR -lt 3 ] || ([ $MAJOR -eq 3 ] && [ $MINOR -lt 6 ]); then
            print_error "Python 3.6+ required (found $PYTHON_VERSION)"
            return 1
        fi
    elif command_exists python; then
        PYTHON_VERSION=$(python --version 2>&1 | awk '{print $2}')
        MAJOR=$(echo $PYTHON_VERSION | cut -d. -f1)
        
        if [ $MAJOR -eq 3 ]; then
            PYTHON_CMD="python"
            print_success "Python $PYTHON_VERSION found"
        else
            print_error "Python 3 not found"
            return 1
        fi
    else
        print_error "Python not found"
        return 1
    fi
    
    return 0
}

# Check rsync installation
check_rsync() {
    print_header "Checking rsync"
    
    if command_exists rsync; then
        RSYNC_VERSION=$(rsync --version | head -1)
        print_success "rsync found: $RSYNC_VERSION"
        return 0
    else
        print_error "rsync not found"
        return 1
    fi
}

# Check SSH client
check_ssh() {
    print_header "Checking SSH client"
    
    if command_exists ssh; then
        SSH_VERSION=$(ssh -V 2>&1)
        print_success "SSH client found: $SSH_VERSION"
        return 0
    else
        print_error "SSH client not found"
        return 1
    fi
}

# Install Python
install_python() {
    print_header "Installing Python"
    
    case $OS in
        ubuntu|debian)
            print_info "Installing Python using apt..."
            sudo apt update
            sudo apt install -y python3 python3-pip
            ;;
        fedora|rhel|centos)
            print_info "Installing Python using dnf/yum..."
            if command_exists dnf; then
                sudo dnf install -y python3 python3-pip
            else
                sudo yum install -y python3 python3-pip
            fi
            ;;
        arch|manjaro)
            print_info "Installing Python using pacman..."
            sudo pacman -S --noconfirm python python-pip
            ;;
        alpine)
            print_info "Installing Python using apk..."
            sudo apk add python3 py3-pip
            ;;
        macos)
            if command_exists brew; then
                print_info "Installing Python using Homebrew..."
                brew install python3
            else
                print_error "Homebrew not found. Please install from https://brew.sh/"
                return 1
            fi
            ;;
        *)
            print_error "Unknown OS. Please install Python 3 manually."
            return 1
            ;;
    esac
}

# Install rsync
install_rsync() {
    print_header "Installing rsync"
    
    case $OS in
        ubuntu|debian)
            print_info "Installing rsync using apt..."
            sudo apt update
            sudo apt install -y rsync
            ;;
        fedora|rhel|centos)
            print_info "Installing rsync using dnf/yum..."
            if command_exists dnf; then
                sudo dnf install -y rsync
            else
                sudo yum install -y rsync
            fi
            ;;
        arch|manjaro)
            print_info "Installing rsync using pacman..."
            sudo pacman -S --noconfirm rsync
            ;;
        alpine)
            print_info "Installing rsync using apk..."
            sudo apk add rsync
            ;;
        macos)
            # rsync comes pre-installed on macOS, but we can upgrade it
            if command_exists brew; then
                print_info "Upgrading rsync using Homebrew..."
                brew install rsync
            else
                print_warning "rsync should be pre-installed on macOS"
            fi
            ;;
        *)
            print_error "Unknown OS. Please install rsync manually."
            return 1
            ;;
    esac
}

# Install SSH client
install_ssh() {
    print_header "Installing SSH client"
    
    case $OS in
        ubuntu|debian)
            print_info "Installing OpenSSH client using apt..."
            sudo apt update
            sudo apt install -y openssh-client
            ;;
        fedora|rhel|centos)
            print_info "Installing OpenSSH client using dnf/yum..."
            if command_exists dnf; then
                sudo dnf install -y openssh-clients
            else
                sudo yum install -y openssh-clients
            fi
            ;;
        arch|manjaro)
            print_info "Installing OpenSSH using pacman..."
            sudo pacman -S --noconfirm openssh
            ;;
        alpine)
            print_info "Installing OpenSSH client using apk..."
            sudo apk add openssh-client
            ;;
        macos)
            print_warning "SSH client should be pre-installed on macOS"
            ;;
        *)
            print_error "Unknown OS. Please install SSH client manually."
            return 1
            ;;
    esac
}

# Make scripts executable
make_executable() {
    print_header "Setting executable permissions"
    
    SCRIPTS=(
        "rediacc"
        "rediacc-cli"
        "rediacc-cli-sync"
        "rediacc-cli-term"
        "install.sh"
    )
    
    for script in "${SCRIPTS[@]}"; do
        if [ -f "$script" ]; then
            chmod +x "$script"
            print_success "Made $script executable"
        fi
    done
}

# Install Python dependencies
install_python_deps() {
    print_header "Installing Python dependencies"
    
    if [ -f "requirements.txt" ]; then
        print_info "Installing from requirements.txt..."
        $PYTHON_CMD -m pip install --user -r requirements.txt
        if [ $? -eq 0 ]; then
            print_success "Python dependencies installed successfully"
        else
            print_warning "Some dependencies may have failed to install"
        fi
    else
        print_info "Installing essential dependencies..."
        $PYTHON_CMD -m pip install --user cryptography requests
        if [ $? -eq 0 ]; then
            print_success "Essential dependencies installed"
        else
            print_warning "Some dependencies may have failed to install"
        fi
    fi
}

# Test Python modules
test_python_modules() {
    print_header "Testing Python modules"
    
    # Test if cryptography module is available
    if $PYTHON_CMD -c "import cryptography" 2>/dev/null; then
        print_success "cryptography module available (vault encryption supported)"
    else
        print_warning "cryptography module not found (needed for vault encryption)"
        return 1
    fi
    
    # Test if requests module is available
    if $PYTHON_CMD -c "import requests" 2>/dev/null; then
        print_success "requests module available"
    else
        print_warning "requests module not found (needed for API calls)"
        return 1
    fi
    
    # Test if our modules work
    if $PYTHON_CMD -c "import rediacc_cli_core" 2>/dev/null; then
        print_success "Rediacc CLI modules load correctly"
    else
        print_error "Failed to import Rediacc CLI modules"
        return 1
    fi
    
    return 0
}

# Main installation flow
main() {
    echo -e "${CYAN}=====================================${NC}"
    echo -e "${CYAN}Rediacc CLI Installation for Linux/macOS${NC}"
    echo -e "${CYAN}=====================================${NC}"
    echo
    
    # Detect OS
    detect_os
    print_info "Detected OS: $OS ($OS_FAMILY) version $OS_VERSION"
    echo
    
    # Check for auto-install flag
    AUTO_INSTALL=false
    if [[ "$1" == "--auto" ]] || [[ "$1" == "-y" ]]; then
        AUTO_INSTALL=true
        print_info "Auto-install mode enabled"
    fi
    
    # Track what needs to be installed
    NEED_PYTHON=false
    NEED_RSYNC=false
    NEED_SSH=false
    
    # Check requirements
    if ! check_python; then
        NEED_PYTHON=true
    fi
    echo
    
    if ! check_rsync; then
        NEED_RSYNC=true
    fi
    echo
    
    if ! check_ssh; then
        NEED_SSH=true
    fi
    echo
    
    # Install missing components
    if $NEED_PYTHON || $NEED_RSYNC || $NEED_SSH; then
        print_header "Missing Dependencies"
        
        if $NEED_PYTHON; then
            print_warning "Python 3 needs to be installed"
        fi
        if $NEED_RSYNC; then
            print_warning "rsync needs to be installed"
        fi
        if $NEED_SSH; then
            print_warning "SSH client needs to be installed"
        fi
        
        echo
        
        if $AUTO_INSTALL; then
            ANSWER="y"
        else
            read -p "Would you like to install missing dependencies? (y/N) " ANSWER
        fi
        
        if [[ "$ANSWER" =~ ^[Yy]$ ]]; then
            if $NEED_PYTHON && ! install_python; then
                print_error "Failed to install Python"
                exit 1
            fi
            
            if $NEED_RSYNC && ! install_rsync; then
                print_error "Failed to install rsync"
                exit 1
            fi
            
            if $NEED_SSH && ! install_ssh; then
                print_error "Failed to install SSH client"
                exit 1
            fi
            
            echo
            print_success "Dependencies installed successfully"
        else
            print_warning "Please install missing dependencies manually"
            exit 1
        fi
    fi
    
    echo
    
    # Make scripts executable
    make_executable
    echo
    
    # Install Python dependencies
    install_python_deps
    echo
    
    # Test Python modules
    test_python_modules
    echo
    
    # Final status
    print_header "Installation Summary"
    
    if check_python >/dev/null 2>&1 && check_rsync >/dev/null 2>&1 && check_ssh >/dev/null 2>&1; then
        print_success "All requirements satisfied!"
        echo
        print_info "You can now use Rediacc CLI:"
        echo "  ./rediacc login"
        echo "  ./rediacc sync upload --help"
        echo "  ./rediacc sync download --help"
        echo "  ./rediacc term --help"
        echo
        
        # Optionally create symlinks
        if [[ "$PATH" =~ "$HOME/.local/bin" ]] || [[ "$PATH" =~ "$HOME/bin" ]]; then
            if $AUTO_INSTALL; then
                CREATE_SYMLINKS="y"
            else
                read -p "Would you like to create symlinks in your PATH for easier access? (y/N) " CREATE_SYMLINKS
            fi
            
            if [[ "$CREATE_SYMLINKS" =~ ^[Yy]$ ]]; then
                # Determine target directory
                if [[ "$PATH" =~ "$HOME/.local/bin" ]]; then
                    BIN_DIR="$HOME/.local/bin"
                else
                    BIN_DIR="$HOME/bin"
                fi
                
                mkdir -p "$BIN_DIR"
                
                # Create symlinks
                ln -sf "$PWD/rediacc" "$BIN_DIR/rediacc"
                ln -sf "$PWD/rediacc-cli" "$BIN_DIR/rediacc-cli"
                ln -sf "$PWD/rediacc-cli-sync" "$BIN_DIR/rediacc-cli-sync"
                ln -sf "$PWD/rediacc-cli-term" "$BIN_DIR/rediacc-cli-term"
                
                print_success "Created symlinks in $BIN_DIR"
                print_info "You can now run commands from anywhere:"
                echo "  rediacc login"
                echo "  rediacc sync upload --help"
                echo "  rediacc term --help"
            fi
        fi
    else
        print_error "Some requirements are still missing"
        exit 1
    fi
}

# Run main function
main "$@"