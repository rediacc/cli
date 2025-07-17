#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Rediacc CLI Plugin - SSH tunnel management for Rediacc repository plugins
Forwards remote Unix sockets to local TCP ports for plugin access
"""
import argparse
import os
import subprocess
import sys
import json
import signal
import socket
import time
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime

# Add parent directory to path for module imports
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'modules'))

# Import common functionality from core module
from rediacc_cli_core import (
    colorize,
    validate_cli_tool,
    RepositoryConnection,
    setup_ssh_for_connection,
    cleanup_ssh_key,
    is_windows,
    safe_error_message
)

# Import token manager
from token_manager import TokenManager

# Import centralized config path
from config_path import get_config_dir, get_plugin_connections_file, get_ssh_control_dir

# Configuration
# Use centralized config directory
LOCAL_CONFIG_DIR = get_config_dir()
CONNECTIONS_FILE = str(get_plugin_connections_file())
DEFAULT_PORT_RANGE = (7111, 9111)
SSH_CONTROL_DIR = str(get_ssh_control_dir())

def ensure_directories():
    """Ensure necessary directories exist"""
    os.makedirs(os.path.dirname(CONNECTIONS_FILE), exist_ok=True)
    os.makedirs(SSH_CONTROL_DIR, exist_ok=True)

def load_connections() -> Dict[str, Any]:
    """Load active connections from state file"""
    if not os.path.exists(CONNECTIONS_FILE):
        return {}
    
    try:
        with open(CONNECTIONS_FILE, 'r') as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return {}

def save_connections(connections: Dict[str, Any]):
    """Save active connections to state file"""
    ensure_directories()
    with open(CONNECTIONS_FILE, 'w') as f:
        json.dump(connections, f, indent=2)

def is_port_available(port: int) -> bool:
    """Check if a local port is available"""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(('localhost', port))
            return True
    except OSError:
        return False

def find_available_port(start: int = DEFAULT_PORT_RANGE[0], end: int = DEFAULT_PORT_RANGE[1]) -> Optional[int]:
    """Find an available port in the given range"""
    for port in range(start, end + 1):
        if is_port_available(port):
            return port
    return None

def is_process_running(pid: int) -> bool:
    """Check if a process is running"""
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False

def clean_stale_connections():
    """Remove connections with dead SSH processes"""
    connections = load_connections()
    active_connections = {}
    
    for conn_id, conn_info in connections.items():
        pid = conn_info.get('ssh_pid')
        if pid and is_process_running(pid):
            active_connections[conn_id] = conn_info
        else:
            print(colorize(f"Cleaning up stale connection: {conn_id}", 'YELLOW'))
    
    if len(active_connections) != len(connections):
        save_connections(active_connections)

def generate_connection_id(team: str, machine: str, repo: str, plugin: str) -> str:
    """Generate a unique connection ID"""
    import hashlib
    data = f"{team}:{machine}:{repo}:{plugin}:{time.time()}"
    return hashlib.md5(data.encode()).hexdigest()[:8]

def list_plugins(args):
    """List available plugins in a repository"""
    print(colorize(f"Listing plugins for repository '{args.repo}' on machine '{args.machine}'...", 'HEADER'))
    
    # Create repository connection
    conn = RepositoryConnection(args.team, args.machine, args.repo)
    conn.connect()
    
    # Set up SSH
    if args.dev:
        original_host_entry = conn.connection_info.get('host_entry')
        conn.connection_info['host_entry'] = None
    
    ssh_opts, ssh_key_file, known_hosts_file = conn.setup_ssh()
    
    if args.dev and 'original_host_entry' in locals():
        conn.connection_info['host_entry'] = original_host_entry
    
    try:
        # List socket files in the repository
        universal_user = conn.connection_info.get('universal_user', 'rediacc')
        
        ssh_cmd = [
            'ssh',
        ] + ssh_opts.split() + [
            conn.ssh_destination,
            f"sudo -u {universal_user} bash -c 'cd {conn.repo_paths['mount_path']} && ls -la *.sock 2>/dev/null || true'"
        ]
        
        result = subprocess.run(ssh_cmd, capture_output=True, text=True)
        
        if result.returncode == 0 and result.stdout.strip():
            print(colorize("\nAvailable plugins:", 'BLUE'))
            print(colorize("=" * 60, 'BLUE'))
            
            # Parse socket files
            plugins = []
            for line in result.stdout.strip().split('\n'):
                if '.sock' in line:
                    parts = line.split()
                    if len(parts) >= 9:
                        socket_file = parts[-1]
                        plugin_name = socket_file.replace('.sock', '')
                        plugins.append(plugin_name)
                        print(f"  • {colorize(plugin_name, 'GREEN')} ({socket_file})")
            
            if not plugins:
                print(colorize("  No plugin sockets found", 'YELLOW'))
            else:
                # Check if plugins are running
                print(colorize("\nPlugin container status:", 'BLUE'))
                docker_cmd = f"sudo -u {universal_user} bash -c 'export DOCKER_HOST=\"{conn.repo_paths['docker_socket']}\" && docker ps --format \"table {{{{.Names}}}}\\t{{{{.Image}}}}\\t{{{{.Status}}}}\" | grep plugin || true'"
                
                ssh_cmd = [
                    'ssh',
                ] + ssh_opts.split() + [
                    conn.ssh_destination,
                    docker_cmd
                ]
                
                docker_result = subprocess.run(ssh_cmd, capture_output=True, text=True)
                if docker_result.returncode == 0 and docker_result.stdout.strip():
                    print(docker_result.stdout.strip())
                else:
                    print(colorize("  No plugin containers running", 'YELLOW'))
                
                # Show existing connections
                connections = load_connections()
                active_for_repo = []
                for conn_id, conn_info in connections.items():
                    if (conn_info.get('team') == args.team and 
                        conn_info.get('machine') == args.machine and 
                        conn_info.get('repo') == args.repo):
                        active_for_repo.append(conn_info)
                
                if active_for_repo:
                    print(colorize("\nActive local connections:", 'BLUE'))
                    for conn_info in active_for_repo:
                        print(f"  • {conn_info['plugin']} → localhost:{conn_info['local_port']}")
        else:
            print(colorize("No plugins found or repository not accessible", 'YELLOW'))
            if result.stderr:
                print(colorize(f"Error: {safe_error_message(result.stderr)}", 'RED'))
                
    finally:
        # Clean up SSH key and known_hosts files
        conn.cleanup_ssh(ssh_key_file, known_hosts_file)

def connect_plugin(args):
    """Connect to a plugin by forwarding its socket to a local port"""
    print(colorize(f"Connecting to plugin '{args.plugin}' in repository '{args.repo}'...", 'HEADER'))
    
    # Clean stale connections first
    clean_stale_connections()
    
    # Check if already connected
    connections = load_connections()
    for conn_id, conn_info in connections.items():
        if (conn_info.get('team') == args.team and 
            conn_info.get('machine') == args.machine and 
            conn_info.get('repo') == args.repo and 
            conn_info.get('plugin') == args.plugin):
            print(colorize(f"Plugin already connected on port {conn_info['local_port']}", 'YELLOW'))
            print(f"Connection ID: {conn_id}")
            return
    
    # Find available port
    if args.port:
        if not is_port_available(args.port):
            print(colorize(f"Port {args.port} is not available", 'RED'))
            sys.exit(1)
        local_port = args.port
    else:
        local_port = find_available_port()
        if not local_port:
            print(colorize("No available ports in range 7111-9111", 'RED'))
            sys.exit(1)
    
    # Create repository connection
    conn = RepositoryConnection(args.team, args.machine, args.repo)
    conn.connect()
    
    # Set up SSH
    if args.dev:
        original_host_entry = conn.connection_info.get('host_entry')
        conn.connection_info['host_entry'] = None
    
    ssh_opts, ssh_key_file, known_hosts_file = conn.setup_ssh()
    
    if args.dev and 'original_host_entry' in locals():
        conn.connection_info['host_entry'] = original_host_entry
    
    try:
        # Verify plugin socket exists
        universal_user = conn.connection_info.get('universal_user', 'rediacc')
        socket_path = f"{conn.repo_paths['mount_path']}/{args.plugin}.sock"
        
        check_cmd = [
            'ssh',
        ] + ssh_opts.split() + [
            conn.ssh_destination,
            f"sudo -u {universal_user} test -S {socket_path} && echo 'exists' || echo 'not found'"
        ]
        
        result = subprocess.run(check_cmd, capture_output=True, text=True)
        if result.returncode != 0 or 'not found' in result.stdout:
            print(colorize(f"Plugin socket '{args.plugin}.sock' not found", 'RED'))
            print("Use 'list' command to see available plugins")
            sys.exit(1)
        
        # Generate connection ID
        conn_id = generate_connection_id(args.team, args.machine, args.repo, args.plugin)
        control_path = os.path.join(SSH_CONTROL_DIR, f"plugin-{conn_id}")
        
        # Check OpenSSH version to see if we can use Unix socket forwarding
        ssh_version_cmd = ['ssh', '-V']
        version_result = subprocess.run(ssh_version_cmd, capture_output=True, text=True)
        ssh_version_output = (version_result.stdout + version_result.stderr).lower()
        
        # OpenSSH 6.7+ supports Unix socket forwarding
        supports_unix_forwarding = False
        if 'openssh' in ssh_version_output:
            try:
                # Extract version number
                import re
                version_match = re.search(r'openssh[_\s]+(\d+)\.(\d+)', ssh_version_output)
                if version_match:
                    major, minor = int(version_match.group(1)), int(version_match.group(2))
                    if major > 6 or (major == 6 and minor >= 7):
                        supports_unix_forwarding = True
            except:
                pass
        
        if supports_unix_forwarding:
            # Use native Unix socket forwarding
            ssh_tunnel_cmd = [
                'ssh',
                '-N',  # No command execution
                '-f',  # Background
                '-o', 'ControlMaster=auto',
                '-o', f'ControlPath={control_path}',
                '-o', 'ControlPersist=10m',
                '-o', 'ExitOnForwardFailure=yes',
                '-L', f'localhost:{local_port}:{socket_path}',
            ] + ssh_opts.split() + [
                conn.ssh_destination,
            ]
            
            print(f"Establishing tunnel on port {local_port} (using native Unix socket forwarding)...")
            
            # Start SSH tunnel
            result = subprocess.run(ssh_tunnel_cmd, capture_output=True, text=True)
            
            if result.returncode != 0:
                print(colorize(f"Failed to establish tunnel: {safe_error_message(result.stderr)}", 'RED'))
                cleanup_ssh_key(ssh_key_file, known_hosts_file)
                sys.exit(1)
            
            # Since we used -f, we need to find the SSH process PID
            ssh_pid = None
            # Try to get from control socket
            try:
                check_master = subprocess.run(['ssh', '-O', 'check', '-o', f'ControlPath={control_path}', 'dummy'], 
                                            capture_output=True, text=True)
                if 'pid=' in check_master.stderr:
                    ssh_pid = int(check_master.stderr.split('pid=')[1].split()[0].rstrip(')'))
            except:
                pass
            
            process = type('Process', (), {'pid': ssh_pid})()
        else:
            # Fallback: Use socat if available
            # First, check if socat is available on remote
            check_socat_cmd = [
                'ssh',
            ] + ssh_opts.split() + [
                conn.ssh_destination,
                "which socat >/dev/null 2>&1 && echo 'available' || echo 'missing'"
            ]
            
            socat_check = subprocess.run(check_socat_cmd, capture_output=True, text=True)
            if 'missing' in socat_check.stdout:
                print(colorize("Error: Your SSH client doesn't support Unix socket forwarding", 'RED'))
                print("Please upgrade to OpenSSH 6.7+ or install socat on the remote machine")
                cleanup_ssh_key(ssh_key_file, known_hosts_file)
                sys.exit(1)
            
            # Build SSH command with remote socat forwarding
            ssh_tunnel_cmd = [
                'ssh',
                '-N',  # No command execution
                '-L', f'{local_port}:localhost:{local_port}',
                '-o', 'ControlMaster=auto',
                '-o', f'ControlPath={control_path}',
                '-o', 'ControlPersist=10m',
            ] + ssh_opts.split() + [
                conn.ssh_destination,
                f"sudo -u {universal_user} socat TCP-LISTEN:{local_port},bind=localhost,reuseaddr,fork UNIX-CONNECT:{socket_path}"
            ]
            
            print(f"Establishing tunnel on port {local_port} (using socat bridge)...")
            
            # Start SSH tunnel in background
            process = subprocess.Popen(ssh_tunnel_cmd, 
                                     stdout=subprocess.PIPE, 
                                     stderr=subprocess.PIPE)
            
            # Give it a moment to establish
            time.sleep(2)
            
            # Check if process is still running
            if process.poll() is not None:
                stdout, stderr = process.communicate()
                print(colorize(f"Failed to establish tunnel: {safe_error_message(stderr.decode())}", 'RED'))
                cleanup_ssh_key(ssh_key_file, known_hosts_file)
                sys.exit(1)
        
        # Save connection info
        connection_info = {
            'connection_id': conn_id,
            'team': args.team,
            'machine': args.machine,
            'repo': args.repo,
            'plugin': args.plugin,
            'local_port': local_port,
            'ssh_pid': process.pid,
            'control_path': control_path,
            'ssh_key_file': ssh_key_file,
            'known_hosts_file': known_hosts_file,
            'created_at': datetime.now().isoformat()
        }
        
        connections = load_connections()
        connections[conn_id] = connection_info
        save_connections(connections)
        
        print(colorize(f"\n✓ Plugin '{args.plugin}' connected successfully!", 'GREEN'))
        print(colorize("=" * 60, 'BLUE'))
        print(f"Connection ID: {colorize(conn_id, 'YELLOW')}")
        print(f"Local URL: {colorize(f'http://localhost:{local_port}', 'GREEN')}")
        print(colorize("=" * 60, 'BLUE'))
        print(f"\nTo disconnect, run: {colorize(f'rediacc plugin disconnect --connection-id {conn_id}', 'YELLOW')}")
        
    except Exception as e:
        print(colorize(f"Error: {str(e)}", 'RED'))
        # Clean up on error
        cleanup_ssh_key(ssh_key_file, known_hosts_file)
        sys.exit(1)

def disconnect_plugin(args):
    """Disconnect a plugin connection"""
    connections = load_connections()
    
    # Find connection(s) to disconnect
    to_disconnect = []
    
    if args.connection_id:
        if args.connection_id in connections:
            to_disconnect.append(args.connection_id)
        else:
            print(colorize(f"Connection ID '{args.connection_id}' not found", 'RED'))
            sys.exit(1)
    else:
        # Find by team/machine/repo/plugin
        for conn_id, conn_info in connections.items():
            if (conn_info.get('team') == args.team and 
                conn_info.get('machine') == args.machine and 
                conn_info.get('repo') == args.repo and 
                (not args.plugin or conn_info.get('plugin') == args.plugin)):
                to_disconnect.append(conn_id)
    
    if not to_disconnect:
        print(colorize("No matching connections found", 'YELLOW'))
        return
    
    # Disconnect each connection
    for conn_id in to_disconnect:
        conn_info = connections[conn_id]
        print(colorize(f"Disconnecting {conn_info['plugin']} (port {conn_info['local_port']})...", 'BLUE'))
        
        # Stop SSH tunnel using control socket
        control_path = conn_info.get('control_path')
        if control_path:
            try:
                # Try to stop via control socket
                subprocess.run(['ssh', '-O', 'stop', '-o', f'ControlPath={control_path}', 'dummy'], 
                             capture_output=True, stderr=subprocess.DEVNULL)
            except:
                pass
        
        # Kill SSH process as fallback
        if conn_info.get('ssh_pid'):
            try:
                os.kill(conn_info['ssh_pid'], signal.SIGTERM)
                # Give it a moment to clean up
                time.sleep(0.5)
                # Force kill if still running
                if is_process_running(conn_info['ssh_pid']):
                    os.kill(conn_info['ssh_pid'], signal.SIGKILL)
            except ProcessLookupError:
                pass  # Process already dead
            except:
                pass
        
        # Clean up SSH key files
        if conn_info.get('ssh_key_file') and os.path.exists(conn_info['ssh_key_file']):
            try:
                os.remove(conn_info['ssh_key_file'])
            except:
                pass
        
        if conn_info.get('known_hosts_file') and os.path.exists(conn_info['known_hosts_file']):
            try:
                os.remove(conn_info['known_hosts_file'])
            except:
                pass
        
        # Remove from connections
        del connections[conn_id]
        print(colorize(f"✓ Disconnected {conn_info['plugin']}", 'GREEN'))
    
    # Save updated connections
    save_connections(connections)

def show_status(args):
    """Show status of all plugin connections"""
    clean_stale_connections()
    connections = load_connections()
    
    if not connections:
        print(colorize("No active plugin connections", 'YELLOW'))
        return
    
    print(colorize("Active Plugin Connections", 'HEADER'))
    print(colorize("=" * 80, 'BLUE'))
    print(f"{'ID':<10} {'Plugin':<15} {'Repository':<15} {'Machine':<15} {'Port':<8} {'Status'}")
    print(colorize("-" * 80, 'BLUE'))
    
    for conn_id, conn_info in connections.items():
        # Check if port is actually listening
        port_status = 'Active' if not is_port_available(conn_info['local_port']) else 'Error'
        status_color = 'GREEN' if port_status == 'Active' else 'RED'
        
        print(f"{conn_id:<10} {conn_info['plugin']:<15} {conn_info['repo']:<15} "
              f"{conn_info['machine']:<15} {conn_info['local_port']:<8} "
              f"{colorize(port_status, status_color)}")
    
    print(colorize("-" * 80, 'BLUE'))
    print(f"Total connections: {len(connections)}")

def main():
    parser = argparse.ArgumentParser(
        description='Rediacc CLI Plugin - SSH tunnel management for repository plugins',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  List available plugins:
    %(prog)s list --team="Private Team" --machine=server1 --repo=myrepo
    
  Connect to a plugin:
    %(prog)s connect --team="Private Team" --machine=server1 --repo=myrepo --plugin=browser
    %(prog)s connect --team="Private Team" --machine=server1 --repo=myrepo --plugin=terminal --port=9001
    
  Show connection status:
    %(prog)s status
    
  Disconnect a plugin:
    %(prog)s disconnect --connection-id=abc123
    %(prog)s disconnect --team="Private Team" --machine=server1 --repo=myrepo --plugin=browser

Plugin Access:
  Once connected, access plugins via local URLs:
    Browser: http://localhost:9000
    Terminal: http://localhost:9001
    
  The local port forwards to the plugin's Unix socket on the remote repository.
"""
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Commands')
    
    # List command
    list_parser = subparsers.add_parser('list', help='List available plugins in a repository')
    list_parser.add_argument('--token', required=False, help='Authentication token (GUID) - uses saved token if not specified')
    list_parser.add_argument('--team', required=True, help='Team name')
    list_parser.add_argument('--machine', required=True, help='Machine name')
    list_parser.add_argument('--repo', required=True, help='Repository name')
    list_parser.add_argument('--dev', action='store_true', help='Development mode - relaxes SSH host key checking')
    list_parser.set_defaults(func=list_plugins)
    
    # Connect command
    connect_parser = subparsers.add_parser('connect', help='Connect to a plugin')
    connect_parser.add_argument('--token', required=False, help='Authentication token (GUID) - uses saved token if not specified')
    connect_parser.add_argument('--team', required=True, help='Team name')
    connect_parser.add_argument('--machine', required=True, help='Machine name')
    connect_parser.add_argument('--repo', required=True, help='Repository name')
    connect_parser.add_argument('--plugin', required=True, help='Plugin name (e.g., browser, terminal)')
    connect_parser.add_argument('--port', type=int, help='Local port to use (auto-assigned if not specified)')
    connect_parser.add_argument('--dev', action='store_true', help='Development mode - relaxes SSH host key checking')
    connect_parser.set_defaults(func=connect_plugin)
    
    # Disconnect command
    disconnect_parser = subparsers.add_parser('disconnect', help='Disconnect plugin connection(s)')
    disconnect_parser.add_argument('--connection-id', help='Connection ID to disconnect')
    disconnect_parser.add_argument('--team', help='Team name')
    disconnect_parser.add_argument('--machine', help='Machine name')
    disconnect_parser.add_argument('--repo', help='Repository name')
    disconnect_parser.add_argument('--plugin', help='Plugin name (disconnect all if not specified)')
    disconnect_parser.set_defaults(func=disconnect_plugin)
    
    # Status command
    status_parser = subparsers.add_parser('status', help='Show status of all plugin connections')
    status_parser.set_defaults(func=show_status)
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        sys.exit(1)
    
    # Handle token authentication for commands that need it
    if hasattr(args, 'token') and args.command in ['list', 'connect']:
        if args.token:
            # If token provided via command line, set it as environment variable
            os.environ['REDIACC_TOKEN'] = args.token
        else:
            # Verify token exists in TokenManager
            token = TokenManager.get_token()
            if not token:
                parser.error("No authentication token available. Please login first.")
    
    # Validate CLI tool exists for commands that need it
    if args.command in ['list', 'connect']:
        validate_cli_tool()
    
    
    # Execute the command
    args.func(args)

if __name__ == '__main__':
    main()