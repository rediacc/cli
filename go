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

docker_build() {
    echo -e "\e[32mBuilding CLI Docker image...\e[0m"
    
    # Build Docker image with tag
    docker build -t rediacc-cli:latest \
        --build-arg REDIACC_LINUX_USER=rediacc \
        --build-arg REDIACC_LINUX_GROUP=rediacc \
        -f "$CLI_HOME/Dockerfile" \
        "$CLI_HOME"
    
    if [ $? -eq 0 ]; then
        echo -e "\e[32mDocker image built successfully: rediacc-cli:latest\e[0m"
    else
        echo -e "\e[31mDocker build failed\e[0m"
        return 1
    fi
}

docker_run() {
    echo -e "\e[32mRunning CLI in Docker container...\e[0m"
    
    # Check if image exists
    if ! docker images | grep -q "rediacc-cli.*latest"; then
        echo -e "\e[33mDocker image not found. Building it first...\e[0m"
        docker_build || return 1
    fi
    
    # Run Docker container with proper user mapping
    docker run -it --rm \
        --name rediacc-cli-container \
        -v "$HOME/.rediacc:/home/rediacc/.rediacc" \
        -v "$HOME/.ssh:/home/rediacc/.ssh:ro" \
        -v "$PWD:/workspace" \
        -w /workspace \
        --network host \
        rediacc-cli:latest \
        ./rediacc "$@"
}

docker_shell() {
    echo -e "\e[32mStarting interactive shell in CLI Docker container...\e[0m"
    
    # Check if image exists
    if ! docker images | grep -q "rediacc-cli.*latest"; then
        echo -e "\e[33mDocker image not found. Building it first...\e[0m"
        docker_build || return 1
    fi
    
    # Run Docker container with bash shell
    docker run -it --rm \
        --name rediacc-cli-shell \
        -v "$HOME/.rediacc:/home/rediacc/.rediacc" \
        -v "$HOME/.ssh:/home/rediacc/.ssh:ro" \
        -v "$PWD:/workspace" \
        -w /workspace \
        --network host \
        rediacc-cli:latest \
        /bin/bash
}

docker_compose_up() {
    echo -e "\e[32mStarting CLI with docker-compose...\e[0m"
    docker-compose -f "$CLI_HOME/docker-compose.yml" up -d cli
}

docker_compose_down() {
    echo -e "\e[32mStopping CLI containers...\e[0m"
    docker-compose -f "$CLI_HOME/docker-compose.yml" down
}

dashboard_install() {
    echo -e "\e[32mInstalling CLI Dashboard dependencies...\e[0m"
    
    # Install dashboard dependencies
    cd "$CLI_HOME/cli-dashboard"
    npm install
    cd "$CLI_HOME"
    
    # Install Python WebSocket dependencies
    pip3 install -r requirements.txt
    
    echo -e "\e[32mDashboard dependencies installed successfully\e[0m"
}

dashboard_dev() {
    echo -e "\e[32mStarting CLI Dashboard in development mode...\e[0m"
    
    # Start WebSocket server in background
    echo -e "\e[36mStarting WebSocket server...\e[0m"
    python3 "$CLI_HOME/rediacc_cli_websocket.py" &
    WEBSOCKET_PID=$!
    
    # Give WebSocket server time to start
    sleep 2
    
    # Start dashboard dev server
    echo -e "\e[36mStarting dashboard dev server...\e[0m"
    cd "$CLI_HOME/cli-dashboard"
    npm run dev
    
    # Kill WebSocket server when dashboard stops
    kill $WEBSOCKET_PID 2>/dev/null
}

dashboard_build() {
    echo -e "\e[32mBuilding CLI Dashboard for production...\e[0m"
    
    cd "$CLI_HOME/cli-dashboard"
    npm run build
    
    echo -e "\e[32mDashboard built successfully in cli-dashboard/dist/\e[0m"
}

dashboard_serve() {
    echo -e "\e[32mServing CLI Dashboard in production mode...\e[0m"
    
    # Start WebSocket server
    python3 "$CLI_HOME/rediacc_cli_websocket.py" &
    WEBSOCKET_PID=$!
    
    # Serve built dashboard
    cd "$CLI_HOME/cli-dashboard"
    npx serve dist -p 5173
    
    # Kill WebSocket server when server stops
    kill $WEBSOCKET_PID 2>/dev/null
}

websocket_start() {
    echo -e "\e[32mStarting CLI WebSocket server...\e[0m"
    python3 "$CLI_HOME/rediacc_cli_websocket.py"
}

# Help function for integration with main go script
help_short() {
    echo "  cli start|test|release|docker_*|dashboard_*|websocket_start    Manage CLI operations"
}

help() {
    echo "Usage: $0 {start|test|release|docker_*|dashboard_*|websocket_start|help} [args...]"
    echo ""
    echo "CLI Commands:"
    echo "  start [args]      - Run the CLI with optional arguments"
    echo "  test              - Run CLI tests"
    echo "  release           - Prepare CLI for distribution"
    echo ""
    echo "Docker Commands:"
    echo "  docker_build      - Build Docker image for CLI"
    echo "  docker_run [args] - Run CLI in Docker container"
    echo "  docker_shell      - Start interactive shell in Docker container"
    echo ""
    echo "Dashboard Commands:"
    echo "  dashboard_install - Install dashboard dependencies"
    echo "  dashboard_dev     - Start dashboard in development mode"
    echo "  dashboard_build   - Build dashboard for production"
    echo "  dashboard_serve   - Serve production dashboard"
    echo "  websocket_start   - Start WebSocket server only"
    echo ""
    echo "Examples:"
    echo "  ./go start login --email user@example.com"
    echo "  ./go dashboard_dev"
    echo "  ./go docker_build"
}

# Execute command if run directly
[[ "${BASH_SOURCE[0]}" == "${0}" ]] && "$@"