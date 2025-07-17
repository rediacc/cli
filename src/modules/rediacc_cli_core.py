#!/usr/bin/env python3
"""
Rediacc CLI Core - Common functionality for Rediacc CLI tools
Provides shared functions for authentication, API communication, and SSH operations

RESOLVED LIMITATIONS:
1. Added inspect command for machines and repositories to get detailed vault data
2. SSH keys are retrieved from team vault (SSH_PRIVATE_KEY field)
3. Machine connection details (ip, user, datastore) come from machine vault
"""
import json
import os
import subprocess
import sys
import tempfile
import platform
from pathlib import Path
from typing import Dict, Any, Optional, Tuple
from config_path import get_config_dir, get_main_config_file

# Import token manager
from token_manager import TokenManager

# Import configuration loader
from config_loader import get, get_required, get_path

# Configuration
CLI_TOOL = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'cli', 'rediacc-cli.py')

def get_cli_command() -> list:
    """Get the CLI command list for cross-platform execution"""
    if is_windows():
        # On Windows, use Python to execute the script
        python_cmd = 'python'
        # Try to find the best Python command
        for cmd in ['python3', 'python', 'py']:
            try:
                result = subprocess.run([cmd, '--version'], capture_output=True, text=True, timeout=5)
                if result.returncode == 0 and 'Python 3' in result.stdout:
                    python_cmd = cmd
                    break
            except:
                continue
        return [python_cmd, CLI_TOOL]
    else:
        # On Unix systems, execute directly
        return [CLI_TOOL]

# Platform utilities
def is_windows() -> bool:
    """Check if running on Windows"""
    return platform.system().lower() == 'windows'

def get_null_device() -> str:
    """Get the null device path for the current platform"""
    return 'NUL' if is_windows() else '/dev/null'

def create_temp_file(suffix: str = '', prefix: str = 'tmp', delete: bool = True) -> str:
    """Create a temporary file in a platform-appropriate way"""
    if is_windows():
        # Use Windows temp directory
        temp_dir = get('REDIACC_TEMP_DIR') or os.environ.get('TEMP') or os.environ.get('TMP')
        if not temp_dir:
            raise ValueError("No temporary directory found. Set REDIACC_TEMP_DIR, TEMP, or TMP environment variable.")
        fd, path = tempfile.mkstemp(suffix=suffix, prefix=prefix, dir=temp_dir)
        os.close(fd)  # Close the file descriptor
        return path
    else:
        # On Unix, use standard tempfile
        f = tempfile.NamedTemporaryFile(mode='w', delete=False, suffix=suffix, prefix=prefix)
        f.close()
        return f.name

def set_file_permissions(path: str, mode: int):
    """Set file permissions in a platform-appropriate way"""
    if not is_windows():
        os.chmod(path, mode)
    else:
        # Windows doesn't support Unix-style permissions
        # We can try to set read-only attribute for 0o400 type permissions
        import stat
        try:
            if mode & 0o200 == 0:  # If write permission is not set
                os.chmod(path, stat.S_IREAD)
            else:
                os.chmod(path, stat.S_IWRITE | stat.S_IREAD)
        except:
            # Ignore permission errors on Windows
            pass

def safe_error_message(message: str) -> str:
    """Sanitize error messages to prevent token leakage"""
    # Replace any GUID-like patterns with masked version
    import re
    guid_pattern = r'\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b'
    
    def mask_guid(match):
        guid = match.group(0)
        return f"{guid[:8]}..."
    
    return re.sub(guid_pattern, mask_guid, message, flags=re.IGNORECASE)

# Get paths from configuration
DATASTORE_PATH = get('REDIACC_DATASTORE_PATH') or '/mnt/datastore'
INTERIM_FOLDER_NAME = get('REDIACC_INTERIM_FOLDER') or 'interim'
MOUNTS_FOLDER_NAME = get('REDIACC_MOUNTS_FOLDER') or 'mounts'
REPOS_FOLDER_NAME = get('REDIACC_REPOS_FOLDER') or 'repos'

# Color codes for terminal output
COLORS = {
    'HEADER': '\033[95m', 
    'BLUE': '\033[94m', 
    'GREEN': '\033[92m',
    'YELLOW': '\033[93m', 
    'RED': '\033[91m', 
    'ENDC': '\033[0m', 
    'BOLD': '\033[1m',
}

def colorize(text: str, color: str) -> str:
    """Add color to terminal output if supported"""
    return f"{COLORS.get(color, '')}{text}{COLORS['ENDC']}" if sys.stdout.isatty() else text

def run_command(cmd, capture_output=True, check=True, quiet=False):
    """Run a command and return the result"""
    if isinstance(cmd, str):
        cmd = cmd.split()
    
    try:
        if capture_output:
            result = subprocess.run(cmd, capture_output=True, text=True, check=check)
            if result.returncode != 0 and check:
                # Parse JSON error if possible
                try:
                    error_data = json.loads(result.stdout)
                    if error_data.get('error'):
                        if not quiet:
                            print(colorize(f"API Error: {error_data['error']}", 'RED'))
                        sys.exit(1)
                except:
                    pass
                # Sanitize command to hide tokens
                if not quiet:
                    safe_cmd = [safe_error_message(arg) for arg in cmd]
                    print(colorize(f"Error running command: {' '.join(safe_cmd)}", 'RED'))
                    if result.stderr:
                        print(colorize(f"Error: {safe_error_message(result.stderr)}", 'RED'))
                sys.exit(1)
            
            
            return result.stdout.strip() if result.returncode == 0 else None
        else:
            return subprocess.run(cmd, check=check)
    except subprocess.CalledProcessError as e:
        if check:
            # Sanitize command to hide tokens
            if not quiet:
                safe_cmd = [safe_error_message(arg) for arg in cmd]
                print(colorize(f"Error running command: {' '.join(safe_cmd)}", 'RED'))
                if hasattr(e, 'stderr') and e.stderr:
                    print(colorize(f"Error: {safe_error_message(e.stderr)}", 'RED'))
            sys.exit(1)
        return None

def get_machine_info_with_team(team_name: str, machine_name: str) -> Dict[str, Any]:
    """Get machine information when team is known"""
    max_retries = 3
    retry_delay = 0.5  # seconds
    
    for attempt in range(max_retries):
        # Get the latest token from config (TokenManager handles this statically)
        token = TokenManager.get_token()
        if not token:
            print(colorize("No authentication token available", 'RED'))
            sys.exit(1)
        
        # Directly inspect the machine in the specified team
        # Don't pass token explicitly - let CLI read from config to avoid rotation issues
        # Temporarily suppress run_command from exiting on error
        original_exit = sys.exit
        exit_called = False
        exit_code = 0
        def no_exit(code=0):
            nonlocal exit_called, exit_code
            exit_called = True
            exit_code = code
        sys.exit = no_exit
        
        try:
            cmd = get_cli_command() + ['--output', 'json', 'inspect', 'machine', team_name, machine_name]
            # Use quiet mode during retries to avoid confusing error messages
            inspect_output = run_command(cmd, quiet=(attempt > 0))
        finally:
            sys.exit = original_exit
        
        if inspect_output and not exit_called:
            break  # Success
        
        # If we got a 401 error, token will be automatically reloaded on next attempt
        # since TokenManager now always reads from file
        
        # Check if it's an authentication error
        if attempt < max_retries - 1:
            print(colorize(f"API call failed, retrying in {retry_delay}s... (attempt {attempt + 1}/{max_retries})", 'YELLOW'))
            import time
            time.sleep(retry_delay)
            retry_delay *= 2  # Exponential backoff
        else:
            print(colorize(f"Failed to inspect machine {machine_name} in team {team_name} after {max_retries} attempts", 'RED'))
            sys.exit(1)
    
    try:
        inspect_data = json.loads(inspect_output)
        if not inspect_data.get('success'):
            print(colorize(f"Error inspecting machine: {inspect_data.get('error', 'Unknown error')}", 'RED'))
            sys.exit(1)
        
        machine_info = inspect_data['data'][0] if inspect_data.get('data') else {}
        
        # Parse vault content if available
        vault_content = machine_info.get('vaultContent')
        if vault_content:
            if isinstance(vault_content, str):
                try:
                    vault_data = json.loads(vault_content)
                    machine_info['vault'] = vault_data
                except json.JSONDecodeError:
                    pass
            else:
                machine_info['vault'] = vault_content
        
        return machine_info
    except (json.JSONDecodeError, KeyError) as e:
        print(colorize(f"Error parsing machine data: {str(e)}", 'RED'))
        sys.exit(1)


def get_repository_info(team_name: str, repo_name: str) -> Dict[str, Any]:
    """Get repository information using rediacc-cli inspect command"""
    max_retries = 3
    retry_delay = 0.5  # seconds
    
    # Get the latest token from config (TokenManager handles this statically)
    token = TokenManager.get_token()
    if not token:
        print(colorize("No authentication token available", 'RED'))
        sys.exit(1)
    
    # Don't pass token explicitly - let CLI read from config to avoid rotation issues
    for attempt in range(max_retries):
        # Temporarily suppress run_command from exiting on error
        original_exit = sys.exit
        exit_called = False
        exit_code = 0
        def no_exit(code=0):
            nonlocal exit_called, exit_code
            exit_called = True
            exit_code = code
        sys.exit = no_exit
        
        try:
            # Use quiet mode during retries to avoid confusing error messages
            inspect_output = run_command(get_cli_command() + ['--output', 'json', 'inspect', 'repository', team_name, repo_name], quiet=(attempt > 0))
        finally:
            sys.exit = original_exit
        
        if inspect_output and not exit_called:
            break  # Success
        
        # If we got a 401 error, token will be automatically reloaded on next attempt
        # since TokenManager now always reads from file
        
        if attempt < max_retries - 1:
            print(colorize(f"API call failed, retrying in {retry_delay}s... (attempt {attempt + 1}/{max_retries})", 'YELLOW'))
            import time
            time.sleep(retry_delay)
            retry_delay *= 2  # Exponential backoff
        else:
            print(colorize(f"Failed to inspect repository {repo_name} after {max_retries} attempts", 'RED'))
            sys.exit(1)
    
    try:
        inspect_data = json.loads(inspect_output)
        if not inspect_data.get('success'):
            print(colorize(f"Error inspecting repository: {inspect_data.get('error', 'Unknown error')}", 'RED'))
            sys.exit(1)
        
        if inspect_data.get('data'):
            repo_info = inspect_data['data'][0]
            
            # Parse vault content if available
            vault_content = repo_info.get('vaultContent')
            if vault_content:
                if isinstance(vault_content, str):
                    try:
                        vault_data = json.loads(vault_content)
                        repo_info['vault'] = vault_data
                    except json.JSONDecodeError:
                        pass
                else:
                    repo_info['vault'] = vault_content
            
            return repo_info
        
        return {}
    except json.JSONDecodeError as e:
        print(colorize(f"Failed to parse JSON response: {e}", 'RED'))
        sys.exit(1)

def get_ssh_key_from_vault(team_name: Optional[str] = None) -> Optional[str]:
    """Extract SSH private key from team vault
    
    The SSH private key should be stored in the team's vault with the key 'SSH_PRIVATE_KEY'.
    This is different from the machine vault which contains connection details (IP, user, etc).
    
    Args:
        team_name: Optional team name to get SSH key for. If not provided, returns first found SSH key.
    """
    max_retries = 3
    retry_delay = 0.5  # seconds
    
    # Get the latest token from config (TokenManager handles this statically)
    token = TokenManager.get_token()
    if not token:
        print(colorize("No authentication token available", 'RED'))
        return None
    
    # Use the CLI to get team vault content
    # Don't pass token explicitly - let CLI read from config to avoid rotation issues
    for attempt in range(max_retries):
        # Temporarily suppress run_command from exiting on error
        original_exit = sys.exit
        exit_called = False
        exit_code = 0
        def no_exit(code=0):
            nonlocal exit_called, exit_code
            exit_called = True
            exit_code = code
        sys.exit = no_exit
        
        try:
            # Use quiet mode during retries to avoid confusing error messages
            teams_output = run_command(get_cli_command() + ['--output', 'json', 'list', 'teams'], quiet=(attempt > 0))
        finally:
            sys.exit = original_exit
        
        if teams_output and not exit_called:
            break  # Success
        
        # If we got a 401 error, token will be automatically reloaded on next attempt
        # since TokenManager now always reads from file
        
        if attempt < max_retries - 1:
            print(colorize(f"API call failed, retrying in {retry_delay}s... (attempt {attempt + 1}/{max_retries})", 'YELLOW'))
            import time
            time.sleep(retry_delay)
            retry_delay *= 2  # Exponential backoff
        else:
            return None
    
    try:
        result = json.loads(teams_output)
        if result.get('success') and result.get('data'):
            # Look through teams for SSH key in vault
            for team in result.get('data', []):
                # If team_name is specified, only check that team
                if team_name and team.get('teamName') != team_name:
                    continue
                    
                vault_content = team.get('vaultContent')
                if vault_content:
                    # Parse vault content if it's a string
                    if isinstance(vault_content, str):
                        try:
                            vault_data = json.loads(vault_content)
                        except json.JSONDecodeError:
                            continue
                    else:
                        vault_data = vault_content
                    
                    # Look for SSH_PRIVATE_KEY in the vault
                    ssh_key = vault_data.get('SSH_PRIVATE_KEY')
                    if ssh_key:
                        return ssh_key
    except json.JSONDecodeError:
        pass
    
    return None

def setup_ssh_agent_connection(ssh_key: str, host_entry: str = None) -> Tuple[str, str, str]:
    """Set up SSH agent for connection and return SSH command options, agent PID, and known_hosts file"""
    import subprocess
    import base64
    
    # Check if the SSH key is base64 encoded (no newlines, no BEGIN/END markers)
    if not ssh_key.startswith('-----BEGIN') and '\n' not in ssh_key:
        try:
            # Decode base64 SSH key
            decoded_key = base64.b64decode(ssh_key).decode('utf-8')
            ssh_key = decoded_key
        except Exception:
            # If decoding fails, use as-is
            pass
    
    # Ensure the SSH key ends with a newline (required by OpenSSH)
    if not ssh_key.endswith('\n'):
        ssh_key = ssh_key + '\n'
    
    # Start SSH agent
    try:
        agent_result = subprocess.run(['ssh-agent', '-s'], capture_output=True, text=True, timeout=10)
        if agent_result.returncode != 0:
            raise RuntimeError(f"Failed to start ssh-agent: {agent_result.stderr}")
        
        # Parse SSH agent output to get environment variables
        agent_env = {}
        for line in agent_result.stdout.strip().split('\n'):
            if '=' in line and ';' in line:
                var_assignment = line.split(';')[0]
                if '=' in var_assignment:
                    key, value = var_assignment.split('=', 1)
                    agent_env[key] = value
                    # Set in current environment
                    os.environ[key] = value
        
        agent_pid = agent_env.get('SSH_AGENT_PID')
        if not agent_pid:
            raise RuntimeError("Could not get SSH agent PID")
        
        # Add SSH key to agent
        ssh_add_result = subprocess.run(['ssh-add', '-'], 
                                      input=ssh_key, text=True,
                                      capture_output=True, timeout=10)
        
        if ssh_add_result.returncode != 0:
            # Kill the agent if key addition failed
            subprocess.run(['kill', agent_pid], capture_output=True)
            raise RuntimeError(f"Failed to add SSH key to agent: {ssh_add_result.stderr}")
        
    except Exception as e:
        raise RuntimeError(f"SSH agent setup failed: {e}")
    
    # Create temporary known_hosts file if host_entry is provided
    known_hosts_file_path = None
    if host_entry:
        known_hosts_file_path = create_temp_file(suffix='_known_hosts', prefix='known_hosts_')
        with open(known_hosts_file_path, 'w') as f:
            f.write(host_entry + '\n')
        ssh_opts = f"-o StrictHostKeyChecking=yes -o UserKnownHostsFile={known_hosts_file_path}"
    else:
        null_device = get_null_device()
        ssh_opts = f"-o StrictHostKeyChecking=accept-new -o UserKnownHostsFile={null_device}"
    
    return ssh_opts, agent_pid, known_hosts_file_path

def setup_ssh_for_connection(ssh_key: str, host_entry: str = None) -> Tuple[str, str, str]:
    """Set up SSH key for connection and return SSH command options, cleanup path, and known_hosts file"""
    # Check if the SSH key is base64 encoded (no newlines, no BEGIN/END markers)
    if not ssh_key.startswith('-----BEGIN') and '\n' not in ssh_key:
        try:
            # Decode base64 SSH key
            import base64
            decoded_key = base64.b64decode(ssh_key).decode('utf-8')
            ssh_key = decoded_key
        except Exception:
            # If decoding fails, use as-is
            pass
    
    # Create temporary SSH key file
    ssh_key_file_path = create_temp_file(suffix='_rsa', prefix='ssh_key_')
    with open(ssh_key_file_path, 'w') as f:
        # Ensure the SSH key ends with a newline (required by OpenSSH)
        if not ssh_key.endswith('\n'):
            ssh_key = ssh_key + '\n'
        f.write(ssh_key)
    
    # Set proper permissions
    set_file_permissions(ssh_key_file_path, 0o600)
    
    # Create temporary known_hosts file if host_entry is provided
    known_hosts_file_path = None
    if host_entry:
        known_hosts_file_path = create_temp_file(suffix='_known_hosts', prefix='known_hosts_')
        with open(known_hosts_file_path, 'w') as f:
            f.write(host_entry + '\n')
        ssh_opts = f"-o StrictHostKeyChecking=yes -o UserKnownHostsFile={known_hosts_file_path} -i {ssh_key_file_path}"
    else:
        null_device = get_null_device()
        ssh_opts = f"-o StrictHostKeyChecking=accept-new -o UserKnownHostsFile={null_device} -i {ssh_key_file_path}"
    
    return ssh_opts, ssh_key_file_path, known_hosts_file_path

def cleanup_ssh_agent(agent_pid: str, known_hosts_file: str = None):
    """Clean up SSH agent and known_hosts files"""
    import subprocess
    if agent_pid:
        try:
            subprocess.run(['kill', agent_pid], capture_output=True, timeout=5)
        except Exception:
            pass  # Agent might already be dead
    if known_hosts_file and os.path.exists(known_hosts_file):
        os.unlink(known_hosts_file)

def cleanup_ssh_key(ssh_key_file: str, known_hosts_file: str = None):
    """Clean up temporary SSH key and known_hosts files"""
    if ssh_key_file and os.path.exists(ssh_key_file):
        os.unlink(ssh_key_file)
    if known_hosts_file and os.path.exists(known_hosts_file):
        os.unlink(known_hosts_file)

def get_machine_connection_info(machine_info: Dict[str, Any]) -> Dict[str, Any]:
    """Extract connection information from machine info"""
    vault = machine_info.get('vault', {})
    machine_name = machine_info.get('machineName')
    
    # Try to parse vaultContent if vault is missing
    if not vault:
        vault_content = machine_info.get('vaultContent')
        if vault_content and isinstance(vault_content, str):
            try:
                vault = json.loads(vault_content)
                machine_info['vault'] = vault
            except json.JSONDecodeError as e:
                print(colorize(f"Failed to parse vaultContent: {e}", 'RED'))
    
    # Get IP from vault (it's directly in the machine vault)
    ip = vault.get('ip') or vault.get('IP')
    
    # Get SSH user from vault (this is the user we SSH as)
    ssh_user = vault.get('user') or vault.get('USER')
    
    # Get universal user and ID from company vault (this is the user we sudo to)
    universal_user = None
    universal_user_id = None
    # Use centralized config path
    config_path = get_main_config_file()
    if config_path.exists():
        try:
            with open(config_path, 'r') as f:
                config = json.load(f)
                vault_company = config.get('vault_company')
                if vault_company:
                    vault_data = json.loads(vault_company)
                    universal_user = vault_data.get('UNIVERSAL_USER_NAME')
                    universal_user_id = vault_data.get('UNIVERSAL_USER_ID')
        except (json.JSONDecodeError, IOError) as e:
            print(colorize(f"Warning: Failed to read universal user from config: {e}", 'YELLOW'))
    else:
        print(colorize(f"Warning: Config file not found at {config_path}", 'YELLOW'))
    
    if not ssh_user:
        print(colorize(f"ERROR: SSH user not found in machine vault. Vault contents: {vault}", 'RED'))
        raise ValueError(f"SSH user not found in machine vault for {machine_name}. The machine vault should contain 'user' field.")
    
    # Get datastore from vault
    datastore = vault.get('datastore') or vault.get('DATASTORE', DATASTORE_PATH)
    
    if not ip:
        print(colorize(f"\n✗ Machine configuration error", 'RED'))
        print(colorize(f"  Machine '{machine_name}' does not have an IP address configured", 'RED'))
        print(colorize("\nThe machine vault must contain:", 'YELLOW'))
        print(colorize("  • 'ip' or 'IP': The machine's IP address", 'YELLOW'))
        print(colorize("  • 'user' or 'USER': SSH username", 'YELLOW'))
        print(colorize("  • 'datastore' or 'DATASTORE': Datastore path (optional)", 'YELLOW'))
        print(colorize("\nPlease update the machine configuration in the Rediacc console.", 'YELLOW'))
        raise ValueError(f"Machine IP not found in vault for {machine_name}")
    
    # Get host entry for SSH verification
    host_entry = vault.get('hostEntry') or vault.get('HOST_ENTRY')
    
    return {
        'ip': ip,
        'user': ssh_user,  # SSH connection user
        'universal_user': universal_user,  # User to sudo to for operations
        'universal_user_id': universal_user_id,  # User ID for datastore path
        'datastore': datastore,
        'team': machine_info.get('teamName'),
        'host_entry': host_entry
    }

def get_repository_paths(repo_guid: str, datastore: str, universal_user_id: str = None) -> Dict[str, str]:
    """Get all repository-related paths based on repo GUID"""
    # If universal_user_id is provided, append it to datastore path
    if universal_user_id:
        datastore = f"{datastore}/{universal_user_id}"
    
    return {
        'mount_path': f"{datastore}/{MOUNTS_FOLDER_NAME}/{repo_guid}",
        'image_path': f"{datastore}/{REPOS_FOLDER_NAME}/{repo_guid}",
        'docker_folder': f"{datastore}/{INTERIM_FOLDER_NAME}/{repo_guid}/docker",
        'docker_socket': f"{datastore}/{INTERIM_FOLDER_NAME}/{repo_guid}/docker/docker.sock",
        'docker_data': f"{datastore}/{INTERIM_FOLDER_NAME}/{repo_guid}/docker/data",
        'docker_exec': f"{datastore}/{INTERIM_FOLDER_NAME}/{repo_guid}/docker/exec",
    }

def validate_cli_tool():
    """Check if rediacc-cli exists and is executable"""
    if not os.path.exists(CLI_TOOL):
        print(colorize(f"Error: rediacc-cli not found at {CLI_TOOL}", 'RED'))
        sys.exit(1)
    
    # On Windows, we don't need to check executable permissions since we use Python
    if not is_windows() and not os.access(CLI_TOOL, os.X_OK):
        print(colorize(f"Error: rediacc-cli is not executable at {CLI_TOOL}", 'RED'))
        sys.exit(1)

def wait_for_enter(message: str = "Press Enter to continue..."):
    """Wait for user to press Enter key"""
    input(colorize(f"\n{message}", 'YELLOW'))

def test_ssh_connectivity(ip: str, port: int = 22, timeout: int = 5) -> Tuple[bool, str]:
    """Test if SSH port is accessible on the target machine
    
    Args:
        ip: Target IP address
        port: SSH port (default: 22)
        timeout: Connection timeout in seconds
        
    Returns:
        Tuple of (success, error_message)
    """
    import socket
    
    try:
        # Create a TCP socket
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        
        # Try to connect to the SSH port
        result = sock.connect_ex((ip, port))
        sock.close()
        
        if result == 0:
            return True, ""
        else:
            return False, f"Cannot connect to {ip}:{port} - port appears to be closed or filtered"
            
    except socket.timeout:
        return False, f"Connection to {ip}:{port} timed out after {timeout} seconds"
    except socket.gaierror:
        return False, f"Failed to resolve hostname: {ip}"
    except Exception as e:
        return False, f"Connection test failed: {str(e)}"

def validate_machine_accessibility(machine_name: str, team_name: str, ip: str, repo_name: str = None):
    """Validate machine is accessible and show appropriate error messages if not
    
    Args:
        machine_name: Name of the machine
        team_name: Name of the team
        ip: IP address of the machine
        repo_name: Optional repository name for context
    """
    print(f"Testing connectivity to {ip}...")
    is_accessible, error_msg = test_ssh_connectivity(ip)
    
    if not is_accessible:
        print(colorize(f"\n✗ Machine '{machine_name}' is not accessible", 'RED'))
        print(colorize(f"  Error: {error_msg}", 'RED'))
        print(colorize("\nPossible reasons:", 'YELLOW'))
        print(colorize("  • The machine is offline or powered down", 'YELLOW'))
        print(colorize("  • Network connectivity issues between client and machine", 'YELLOW'))
        print(colorize("  • Firewall blocking SSH port (22)", 'YELLOW'))
        print(colorize("  • Incorrect IP address in machine configuration", 'YELLOW'))
        print(colorize(f"\nMachine IP: {ip}", 'BLUE'))
        print(colorize(f"Team: {team_name}", 'BLUE'))
        if repo_name:
            print(colorize(f"Repository: {repo_name}", 'BLUE'))
        print(colorize("\nPlease verify the machine is online and accessible from your network.", 'YELLOW'))
        wait_for_enter("Press Enter to exit...")
        sys.exit(1)
    
    print(colorize("✓ Machine is accessible", 'GREEN'))

def handle_ssh_exit_code(returncode: int, connection_type: str = "machine"):
    """Handle SSH command exit codes and display appropriate messages
    
    Args:
        returncode: SSH command exit code
        connection_type: Type of connection ("machine" or "repository terminal")
    """
    if returncode != 0:
        if returncode == 255:
            print(colorize(f"\n✗ SSH connection failed (exit code: {returncode})", 'RED'))
            print(colorize("\nPossible reasons:", 'YELLOW'))
            print(colorize("  • SSH authentication failed (check SSH key in team vault)", 'YELLOW'))
            print(colorize("  • SSH host key verification failed", 'YELLOW'))
            print(colorize("  • SSH service not running on the machine", 'YELLOW'))
            print(colorize("  • Network connection interrupted", 'YELLOW'))
        else:
            print(colorize(f"\nDisconnected from {connection_type} (exit code: {returncode})", 'YELLOW'))
    else:
        print(colorize(f"\nDisconnected from {connection_type}.", 'GREEN'))

class RepositoryConnection:
    """Helper class to manage repository connections"""
    
    def __init__(self, team_name: str, machine_name: str, repo_name: str):
        self.team_name = team_name
        self.machine_name = machine_name
        self.repo_name = repo_name
        self._machine_info = None
        self._repo_info = None
        self._connection_info = None
        self._repo_paths = None
        self._ssh_key = None
        self._ssh_key_file = None
    
    def connect(self):
        """Establish connection and gather all necessary information"""
        print("Fetching machine information...")
        self._machine_info = get_machine_info_with_team(self.team_name, self.machine_name)
        self._connection_info = get_machine_connection_info(self._machine_info)
        
        if not self._connection_info['ip'] or not self._connection_info['user']:
            print(colorize("Machine IP or user not found in vault", 'RED'))
            sys.exit(1)
        
        print(f"Fetching repository information for '{self.repo_name}'...")
        self._repo_info = get_repository_info(self._connection_info['team'], self.repo_name)
        
        # The repository GUID is in the repoGuid field or the vault's credential field
        repo_guid = self._repo_info.get('repoGuid') or self._repo_info.get('grandGuid')
        if not repo_guid and self._repo_info.get('vault'):
            # Check in vault for credential (which is not the GUID but a credential string)
            # The actual GUID is in repoGuid field
            pass
        
        if not repo_guid:
            print(colorize(f"Repository GUID not found for '{self.repo_name}'", 'RED'))
            print(colorize(f"Repository info: {json.dumps(self._repo_info, indent=2)}", 'YELLOW'))
            sys.exit(1)
        
        # Get universal user ID from company vault
        universal_user_id = None
        # Use centralized config path
        config_path = get_main_config_file()
        if config_path.exists():
            try:
                with open(config_path, 'r') as f:
                    config = json.load(f)
                    vault_company = config.get('vault_company')
                    if vault_company:
                        vault_data = json.loads(vault_company)
                        universal_user_id = vault_data.get('UNIVERSAL_USER_ID')
            except (json.JSONDecodeError, IOError):
                pass
        
        self._repo_paths = get_repository_paths(repo_guid, self._connection_info['datastore'], universal_user_id)
        
        print("Retrieving SSH key...")
        # Get SSH key from the specific team's vault
        team_name = self._connection_info.get('team', self.team_name)
        self._ssh_key = get_ssh_key_from_vault(team_name)
        if not self._ssh_key:
            print(colorize(f"SSH private key not found in vault for team '{team_name}'", 'RED'))
            print(colorize("The team vault should contain 'SSH_PRIVATE_KEY' field with the SSH private key.", 'YELLOW'))
            print(colorize("Please ensure SSH keys are properly configured in your team's vault settings.", 'YELLOW'))
            sys.exit(1)
    
    def setup_ssh(self) -> Tuple[str, str, str]:
        """Set up SSH and return (ssh_options, key_file_path, known_hosts_file_path)"""
        host_entry = self._connection_info.get('host_entry')
        return setup_ssh_for_connection(self._ssh_key, host_entry)
    
    def cleanup_ssh(self, ssh_key_file: str, known_hosts_file: str = None):
        """Clean up SSH key and known_hosts files"""
        cleanup_ssh_key(ssh_key_file, known_hosts_file)
    
    @property
    def ssh_destination(self) -> str:
        """Get SSH destination string (user@host)"""
        return f"{self._connection_info['user']}@{self._connection_info['ip']}"
    
    @property
    def machine_info(self) -> Dict[str, Any]:
        return self._machine_info
    
    @property
    def repo_info(self) -> Dict[str, Any]:
        return self._repo_info
    
    @property
    def connection_info(self) -> Dict[str, Any]:
        return self._connection_info
    
    @property
    def repo_paths(self) -> Dict[str, str]:
        return self._repo_paths
    
    @property
    def repo_guid(self) -> str:
        return self._repo_info.get('repoGuid') or self._repo_info.get('grandGuid')