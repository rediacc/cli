#!/usr/bin/env python3
"""
Rediacc CLI Terminal - Interactive terminal access to Rediacc repository Docker environments
Establishes SSH connection with proper Docker environment variables and socket access
"""
import argparse
import subprocess
import sys
import os

# Add parent directory to path for module imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import common functionality from core module
from rediacc_cli_core import (
    colorize,
    validate_cli_tool,
    RepositoryConnection,
    INTERIM_FOLDER_NAME,
    get_ssh_key_from_vault
)

# Import from consolidated core module
from core import (
    TokenManager,
    setup_logging, get_logger
)


def connect_to_machine(args):
    """Connect to machine via SSH (without repository)"""
    print(colorize(f"Connecting to machine '{args.machine}'...", 'HEADER'))
    
    from rediacc_cli_core import (
        get_machine_info_with_team,
        get_machine_connection_info,
        setup_ssh_for_connection,
        cleanup_ssh_key,
        validate_machine_accessibility,
        handle_ssh_exit_code,
        setup_ssh_agent_connection,
        cleanup_ssh_agent
    )
    
    # Get machine info and validate
    print("Fetching machine information...")
    machine_info = get_machine_info_with_team(args.team, args.machine)
    connection_info = get_machine_connection_info(machine_info)
    validate_machine_accessibility(args.machine, args.team, connection_info['ip'])
    
    # Get SSH key
    print("Retrieving SSH key...")
    ssh_key = get_ssh_key_from_vault(args.team)
    if not ssh_key:
        print(colorize(f"SSH private key not found in vault for team '{args.team}'", 'RED'))
        sys.exit(1)
    
    # Set up SSH using SSH agent (no temporary files)
    host_entry = None if args.dev else connection_info.get('host_entry')
    
    try:
        ssh_opts, agent_pid, known_hosts_file = setup_ssh_agent_connection(ssh_key, host_entry)
        print(f"SSH agent set up with PID {agent_pid}")
        ssh_key_file = None
    except Exception as e:
        print(colorize(f"SSH agent setup failed, falling back to temporary files: {e}", 'YELLOW'))
        ssh_opts, ssh_key_file, known_hosts_file = setup_ssh_for_connection(ssh_key, host_entry)
        agent_pid = None
    
    try:
        # Build SSH command
        ssh_cmd = ['ssh', '-tt'] + ssh_opts.split() + [
            f"{connection_info['user']}@{connection_info['ip']}"
        ]
        
        # Get universal user info
        universal_user = connection_info.get('universal_user', 'rediacc')
        universal_user_id = connection_info.get('universal_user_id')
        datastore_path = f"{connection_info['datastore']}/{universal_user_id}" if universal_user_id else connection_info['datastore']
        
        if args.command:
            # Execute command directly as universal user
            full_command = f"sudo -u {universal_user} bash -c 'cd {datastore_path} 2>/dev/null; {args.command}'"
            ssh_cmd.append(full_command)
            print(colorize(f"Executing command as {universal_user}: {args.command}", 'BLUE'))
            print(colorize(f"Working directory: {datastore_path}", 'BLUE'))
        else:
            # Interactive session with automatic switch to universal user
            def build_welcome_message():
                lines = [
                    "clear",
                    r'echo -e "\033[1;36m━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\033[0m"',
                    rf'echo -e "\033[1;32mConnected to Rediacc Machine:\033[0m \033[1;33m{args.machine}\033[0m"',
                    r'echo -e "\033[1;36m━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\033[0m"',
                    "echo",
                    r'echo -e "\033[1;34mMachine Info:\033[0m"',
                    f'echo "  • IP: {connection_info["ip"]}"',
                    f'echo "  • Connected as: {connection_info["user"]}"',
                    f'echo "  • Switched to: {universal_user}"',
                    f'echo "  • Datastore: {datastore_path}"',
                    "echo",
                    r'echo -e "\033[1;33mUseful Commands:\033[0m"',
                    'echo "  • ls -la                               - List current directory"',
                    'echo "  • ls -la mounts/                       - List repository mounts"',
                    'echo "  • docker ps -a                         - List all containers"',
                    "echo",
                    r'echo -e "\033[1;36m━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\033[0m"',
                    "echo",
                    f'cd {datastore_path} 2>/dev/null || echo "Warning: Could not change to datastore directory"',
                    "exec bash -l"
                ]
                return " && ".join(lines)
            
            welcome_cmd = f"sudo -u {universal_user} bash -c '{build_welcome_message()}'"
            ssh_cmd.append(welcome_cmd)
            print(colorize("Opening interactive terminal...", 'BLUE'))
            print(colorize("Type 'exit' to disconnect.", 'YELLOW'))
        
        # Execute SSH connection
        result = subprocess.run(ssh_cmd)
        handle_ssh_exit_code(result.returncode, "machine")
            
    finally:
        # Clean up SSH agent or SSH key files
        if agent_pid:
            cleanup_ssh_agent(agent_pid, known_hosts_file)
        elif ssh_key_file:
            cleanup_ssh_key(ssh_key_file, known_hosts_file)


def connect_to_terminal(args):
    """Connect to repository terminal via SSH"""
    print(colorize(f"Connecting to repository '{args.repo}' on machine '{args.machine}'...", 'HEADER'))
    
    from rediacc_cli_core import (
        validate_machine_accessibility, 
        handle_ssh_exit_code,
        setup_ssh_agent_connection, 
        cleanup_ssh_agent
    )
    
    # Create repository connection
    conn = RepositoryConnection(args.team, args.machine, args.repo)
    conn.connect()
    
    # Validate machine accessibility
    validate_machine_accessibility(args.machine, args.team, conn.connection_info['ip'], args.repo)
    
    # Set up SSH
    # In dev mode, temporarily disable host key checking
    if args.dev:
        original_host_entry = conn.connection_info.get('host_entry')
        conn.connection_info['host_entry'] = None
    
    # Use SSH agent approach for repository connections too
    ssh_key = get_ssh_key_from_vault(args.team)
    if not ssh_key:
        print(colorize(f"SSH private key not found in vault for team '{args.team}'", 'RED'))
        sys.exit(1)
    
    host_entry = None if args.dev else conn.connection_info.get('host_entry')
    
    try:
        ssh_opts, agent_pid, known_hosts_file = setup_ssh_agent_connection(ssh_key, host_entry)
        print(f"SSH agent set up with PID {agent_pid}")
        ssh_key_file = None
    except Exception as e:
        print(colorize(f"SSH agent setup failed, falling back to temporary files: {e}", 'YELLOW'))
        ssh_opts, ssh_key_file, known_hosts_file = conn.setup_ssh()
        agent_pid = None
    
    # Restore original host entry
    if args.dev and 'original_host_entry' in locals():
        conn.connection_info['host_entry'] = original_host_entry
    
    try:
        # Build environment variables for the repository using paths from connection
        docker_folder = conn.repo_paths['docker_folder']
        docker_socket = conn.repo_paths['docker_socket']
        docker_host = f"unix://{docker_socket}"
        repo_mount_path = conn.repo_paths['mount_path']
        
        # Build SSH command with environment setup
        if args.command:
            # For command execution, minimal setup
            ssh_env_setup = f"""
export REPO_PATH='{repo_mount_path}'
export DOCKER_HOST='{docker_host}'
export DOCKER_FOLDER='{docker_folder}'
export DOCKER_SOCKET='{docker_socket}'
export DOCKER_DATA='{conn.repo_paths['docker_data']}'
export DOCKER_EXEC='{conn.repo_paths['docker_exec']}'
# Try to cd to repo path, fallback to mounts directory if not mounted
if [ -d "$REPO_PATH" ]; then
    cd "$REPO_PATH"
else
    # Fallback to mounts directory (parent of REPO_PATH)
    MOUNTS_DIR=$(dirname "$REPO_PATH")
    [ -d "$MOUNTS_DIR" ] && cd "$MOUNTS_DIR"
fi
"""
        else:
            # For interactive session, full setup with welcome message
            ssh_env_setup = f"""
export REPO_PATH='{repo_mount_path}'
export DOCKER_HOST='{docker_host}'
export DOCKER_FOLDER='{docker_folder}'
export DOCKER_SOCKET='{docker_socket}'
export DOCKER_DATA='{conn.repo_paths['docker_data']}'
export DOCKER_EXEC='{conn.repo_paths['docker_exec']}'
export PS1='\\[\\033[01;32m\\][\\u@{args.repo}\\[\\033[00m\\]:\\[\\033[01;34m\\]\\w\\[\\033[00m\\]]\\$ '
# Try to cd to repo path, fallback to mounts directory if not mounted
if [ -d "$REPO_PATH" ]; then
    cd "$REPO_PATH"
else
    # Fallback to mounts directory (parent of REPO_PATH)
    MOUNTS_DIR=$(dirname "$REPO_PATH")
    if [ -d "$MOUNTS_DIR" ]; then
        cd "$MOUNTS_DIR"
        echo "Note: Repository not mounted yet. You are in the mounts directory."
        echo "Mount path will be: $REPO_PATH"
    else
        echo "Warning: Could not find repository or mounts directory"
    fi
fi

# Define helper functions
enter_container() {{
    local container="${{1:-}}"
    if [ -z "$container" ]; then
        echo "Usage: enter_container <container_name_or_id>"
        echo "Available containers:"
        docker ps --format "table {{{{.Names}}}}\\t{{{{.Image}}}}\\t{{{{.Status}}}}"
        return 1
    fi
    docker exec -it "$container" bash || docker exec -it "$container" sh
}}

logs() {{
    local container="${{1:-}}"
    local lines="${{2:-50}}"
    if [ -z "$container" ]; then
        echo "Usage: logs <container_name_or_id> [lines]"
        echo "Available containers:"
        docker ps -a --format "table {{{{.Names}}}}\\t{{{{.Status}}}}"
        return 1
    fi
    docker logs --tail "$lines" -f "$container"
}}

status() {{
    echo -e '\\033[1;36m━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\\033[0m'
    echo -e '\\033[1;32mRepository Status\\033[0m'
    echo -e '\\033[1;36m━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\\033[0m'
    echo -e "\\n\\033[1;34mDocker Status:\\033[0m"
    if docker version >/dev/null 2>&1; then
        echo "  ✓ Docker daemon is running"
        docker ps -q | wc -l | xargs -I {{}} echo "  • {{}} containers running"
    else
        echo "  ✗ Docker daemon is not accessible"
    fi
    echo -e "\\n\\033[1;34mRepository Files:\\033[0m"
    ls -la "$REPO_PATH" 2>/dev/null | tail -n +2 | head -10
    echo ""
}}

# Export functions
export -f enter_container
export -f logs
export -f status

clear
echo -e '\\033[1;36m━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\\033[0m'
echo -e '\\033[1;32mConnected to Rediacc Repository:\\033[0m \\033[1;33m{args.repo}\\033[0m'
echo -e '\\033[1;36m━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\\033[0m'
echo ""
echo -e '\\033[1;34mRepository Path:\\033[0m $REPO_PATH'
echo -e '\\033[1;34mDocker Socket:\\033[0m   $DOCKER_SOCKET'
echo ""
echo -e '\\033[1;33mQuick Commands:\\033[0m'
echo "  • status                       - Show repository status"
echo "  • enter_container <name>       - Enter a container"
echo "  • logs <name>                  - View container logs"
echo "  • docker ps                    - List running containers"
echo ""
echo -e '\\033[1;36m━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\\033[0m'
echo ""
"""
        
        # Get universal user for sudo
        universal_user = conn.connection_info.get('universal_user', 'rediacc')
        
        # Prepare the SSH command
        ssh_cmd = [
            'ssh',
            '-tt',  # Force pseudo-terminal allocation even if stdin is not a terminal
        ] + ssh_opts.split() + [
            conn.ssh_destination
        ]
        
        if args.command:
            # If a command is provided, execute it instead of interactive shell
            # Escape the environment setup and command properly
            full_command = ssh_env_setup.replace("'", "'\"'\"'") + args.command
            ssh_cmd.append(f"sudo -u {universal_user} bash -c '{full_command}'")
            print(colorize(f"Executing command: {args.command}", 'BLUE'))
        else:
            # Interactive shell
            print(colorize("Opening interactive terminal...", 'BLUE'))
            print(colorize("Type 'exit' to disconnect.", 'YELLOW'))
            full_command = ssh_env_setup.replace("'", "'\"'\"'") + "exec bash -l"
            ssh_cmd.append(f"sudo -u {universal_user} bash -c '{full_command}'")
        
        # Execute SSH connection
        result = subprocess.run(ssh_cmd)
        
        # Handle SSH exit code
        handle_ssh_exit_code(result.returncode, "repository terminal")
            
    finally:
        # Clean up SSH agent or SSH key files
        if 'agent_pid' in locals() and agent_pid:
            cleanup_ssh_agent(agent_pid, known_hosts_file)
        elif 'ssh_key_file' in locals():
            conn.cleanup_ssh(ssh_key_file, known_hosts_file)

def main():
    parser = argparse.ArgumentParser(
        description='Rediacc CLI Terminal - Interactive terminal access to Rediacc machines and repository Docker environments',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  Connect to machine only (no repository):
    %(prog)s --token=<GUID> --team=MyTeam --machine=server1
    
  Execute a command on machine:
    %(prog)s --token=<GUID> --team=MyTeam --machine=server1 --command="ls -la mounts/"
    
  Connect to repository terminal:
    %(prog)s --token=<GUID> --team=MyTeam --machine=server1 --repo=myrepo
    
  Execute a command in repository environment:
    %(prog)s --token=<GUID> --team=MyTeam --machine=server1 --repo=myrepo --command="docker ps"
    
  Enter a specific container:
    %(prog)s --token=<GUID> --team=MyTeam --machine=server1 --repo=myrepo --command="docker exec -it mycontainer bash"
    
  Check Docker status:
    %(prog)s --token=<GUID> --team=MyTeam --machine=server1 --repo=myrepo --command="docker stats --no-stream"

When connected to a repository:
  Environment Variables Set:
    REPO_PATH       - Repository mount path
    DOCKER_HOST     - Repository's Docker socket
    DOCKER_FOLDER   - Docker configuration folder
    DOCKER_SOCKET   - Docker socket path
    DOCKER_DATA     - Docker data directory
    DOCKER_EXEC     - Docker exec directory
    
When connected to machine only:
  - Automatically switches to universal user (e.g., rediacc)
  - Changes to user's datastore directory (e.g., /mnt/datastore/7111)
  - Commands are executed in this context
  - Useful for managing repositories and datastore
"""
    )
    # Add verbose logging option
    parser.add_argument('--verbose', '-v', action='store_true',
                       help='Enable verbose logging output')
    
    parser.add_argument('--token', required=False, help='Authentication token (GUID)')
    parser.add_argument('--team', required=False, help='Team name')
    parser.add_argument('--machine', required=False, help='Target machine name')
    parser.add_argument('--repo', help='Target repository name (optional - if not specified, connects to machine only)')
    parser.add_argument('--command', help='Command to execute (interactive shell if not specified)')
    parser.add_argument('--dev', action='store_true', help='Development mode - relaxes SSH host key checking')
    
    args = parser.parse_args()
    
    # Setup logging based on verbose flag
    setup_logging(verbose=args.verbose)
    logger = get_logger(__name__)
    
    # Log startup information in verbose mode
    if args.verbose:
        logger.debug("Rediacc CLI Term starting up")
        logger.debug(f"Arguments: {vars(args)}")
    
    
    # Check required arguments for CLI mode
    if not all([args.team, args.machine]):
        parser.error("--team and --machine are required in CLI mode")
    
    # Handle token authentication
    if args.token:
        os.environ['REDIACC_TOKEN'] = args.token
    elif not TokenManager.get_token():
        parser.error("No authentication token available. Please login first.")
    
    # Validate CLI tool exists
    validate_cli_tool()
    
    # Connect to terminal or machine
    (connect_to_terminal if args.repo else connect_to_machine)(args)

if __name__ == '__main__':
    main()