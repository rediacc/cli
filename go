#!/bin/bash
# Rediacc CLI Management Script

# Get script directory
CLI_HOME=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )

# Source environment if available
if [ -f "$CLI_HOME/.env" ]; then
    source "$CLI_HOME/.env"
fi

start() {
    # Check if Python 3 is installed
    if ! command -v python3 &> /dev/null; then
        echo -e "\e[31mError: Python 3 is not installed. Please install Python 3 and try again.\e[0m"
        return 1
    fi
    
    # Run CLI with arguments
    python3 "$CLI_HOME/rediacc-cli" "$@"
}

test() {
    echo -e "\e[32mRunning CLI tests...\e[0m"
    
    # Run test script if it exists
    if [ -f "$CLI_HOME/test.sh" ]; then
        bash "$CLI_HOME/test.sh"
    else
        echo -e "\e[33mNo test script found. Create test.sh to add tests.\e[0m"
    fi
}

release() {
    echo -e "\e[32mPreparing CLI release...\e[0m"
    
    # Create bin directory if it doesn't exist
    mkdir -p "$CLI_HOME/../bin/cli"
    
    # Copy CLI script to bin
    cp "$CLI_HOME/rediacc-cli" "$CLI_HOME/../bin/cli/"
    
    # Create a simple wrapper script
    cat > "$CLI_HOME/../bin/cli/rediacc" << 'EOF'
#!/bin/bash
# Rediacc CLI wrapper
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
python3 "$DIR/rediacc-cli" "$@"
EOF
    chmod +x "$CLI_HOME/../bin/cli/rediacc"
    
    # Create version info
    echo "{\"version\": \"$(date +%Y.%m.%d.%H%M)\", \"build_date\": \"$(date -u +%Y-%m-%dT%H:%M:%SZ)\"}" > "$CLI_HOME/../bin/cli/version.json"
    
    echo -e "\e[32mCLI release prepared in ../bin/cli/\e[0m"
    echo -e "\e[36mYou can add ../bin/cli to your PATH to use 'rediacc' command globally\e[0m"
}

# Help function for integration with main go script
help_short() {
    echo "  cli start|test|release                    Manage CLI operations"
}

help() {
    echo "Usage: $0 {start|test|release|help} [args...]"
    echo "  start [args]  - Run the CLI with optional arguments"
    echo "  test          - Run CLI tests"
    echo "  release       - Prepare CLI for distribution"
    echo ""
    echo "Examples:"
    echo "  ./go start login --email user@example.com"
    echo "  ./go start list teams"
    echo "  ./go test"
    echo "  ./go release"
}

# Execute command if run directly
[[ "${BASH_SOURCE[0]}" == "${0}" ]] && "$@"