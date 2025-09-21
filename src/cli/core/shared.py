#!/usr/bin/env python3
import json
import os
import subprocess
import sys
import tempfile
import platform
import time
from pathlib import Path
from typing import Dict, Any, Optional, Tuple
from .config import (
    get_config_dir, get_main_config_file,
    TokenManager,
    get, get_required, get_path,
    is_encrypted
)

CLI_TOOL = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'commands', 'cli_main.py')

def _track_ssh_operation(operation: str, host: str = "unknown", success: bool = True,
                        duration_ms: Optional[float] = None, error: Optional[str] = None, **kwargs):
    """Helper function to track SSH operations with telemetry"""
    try:
        from .telemetry import get_telemetry_service
        telemetry = get_telemetry_service()
        telemetry.track_ssh_operation(operation, host, success, duration_ms, error)
    except Exception:
        # Silent fail for telemetry
        pass

def get_cli_command() -> list:
    if not is_windows(): return [CLI_TOOL]
    # On Windows, try 'python' first since 'python3' usually doesn't exist
    for cmd in ['python', 'python3', 'py']:
        try:
            result = subprocess.run([cmd, '--version'], capture_output=True, text=True, timeout=5)
            if result.returncode == 0 and 'Python 3' in result.stdout: 
                return [cmd, CLI_TOOL]
        except: continue
    return ['python', CLI_TOOL]

def is_windows() -> bool:
    return platform.system().lower() == 'windows'

def get_null_device() -> str:
    return 'NUL' if is_windows() else '/dev/null'

def create_temp_file(suffix: str = '', prefix: str = 'tmp', delete: bool = True) -> str:
    if not is_windows():
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix=suffix, prefix=prefix) as f: return f.name
    temp_dir = get('REDIACC_TEMP_DIR') or os.environ.get('TEMP') or os.environ.get('TMP')
    if not temp_dir:
        raise ValueError("No temporary directory found. Set REDIACC_TEMP_DIR, TEMP, or TMP environment variable.")
    fd, path = tempfile.mkstemp(suffix=suffix, prefix=prefix, dir=temp_dir)
    os.close(fd); return path

def set_file_permissions(path: str, mode: int):
    """Set file permissions with cross-platform compatibility"""
    if not is_windows():
        os.chmod(path, mode)
        return

    # Windows: Set restrictive permissions for SSH key files
    import stat
    try:
        if mode == 0o600:  # SSH key file - owner read/write only
            # Remove all permissions first, then add owner read/write
            os.chmod(path, stat.S_IREAD | stat.S_IWRITE)

            # Additional security: try to set Windows ACL for SSH key files
            try:
                import subprocess
                # Use icacls to set restrictive permissions (owner only)
                subprocess.run(['icacls', path, '/inheritance:r', '/grant:r', f'{os.getlogin()}:F'],
                             capture_output=True, check=False)
            except:
                pass  # Fallback to basic chmod
        else:
            # General case: set read/write based on mode
            os.chmod(path, stat.S_IREAD if mode & 0o200 == 0 else stat.S_IWRITE | stat.S_IREAD)
    except Exception as e:
        # Log the error but don't fail - file permissions are important but not critical
        _track_ssh_operation("file_permissions", "windows", False, error=str(e))

def safe_error_message(message: str) -> str:
    import re
    guid_pattern = r'\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b'
    return re.sub(guid_pattern, lambda m: f"{m.group(0)[:8]}...", message, flags=re.IGNORECASE)

# These folder names are constants that must match the values in bridge/cli/scripts/internal.sh
INTERIM_FOLDER_NAME = 'interim'
MOUNTS_FOLDER_NAME = 'mounts'
REPOS_FOLDER_NAME = 'repos'

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
    return f"{COLORS.get(color, '')}{text}{COLORS['ENDC']}" if sys.stdout.isatty() else text

def error_exit(message: str, code: int = 1):
    """Print an error message in red and exit with the specified code.
    
    Args:
        message: The error message to display (without "Error: " prefix)
        code: Exit code (default: 1)
    """
    print(colorize(f"Error: {message}", 'RED'))
    sys.exit(code)

def run_command(cmd, capture_output=True, check=True, quiet=False):
    cmd = cmd.split() if isinstance(cmd, str) else cmd
    
    def handle_error(stderr=None):
        if not quiet:
            error_msg = f"running command: {' '.join([safe_error_message(arg) for arg in cmd])}"
            if stderr: 
                error_msg += f"\n{safe_error_message(stderr)}"
            error_exit(error_msg)
    
    try:
        if not capture_output: return subprocess.run(cmd, check=False, env=os.environ.copy())
        result = subprocess.run(cmd, capture_output=True, text=True, check=False, env=os.environ.copy())
        if result.returncode != 0 and check:
                try:
                    error_data = json.loads(result.stdout)
                    if error_data.get('error') and not quiet: 
                        error_exit(f"API Error: {error_data['error']}")
                except: pass
                handle_error(result.stderr)
        return result.stdout.strip() if result.returncode == 0 else None
    except subprocess.CalledProcessError as e:
        if check: handle_error(getattr(e, 'stderr', None))
        return None

def _retry_with_backoff(func, max_retries=3, initial_delay=0.5, error_msg="Operation failed", exit_on_failure=True):
    import time
    delay = initial_delay
    
    for attempt in range(max_retries):
        output, exit_called = func(quiet=attempt > 0)
        
        if output and not exit_called:
            return output
        
        if attempt < max_retries - 1:
            print(colorize(f"API call failed, retrying in {delay}s... (attempt {attempt + 1}/{max_retries})", 'YELLOW'))
            time.sleep(delay)
            delay *= 2
    else:
        if exit_on_failure:
            error_exit(f"{error_msg} after {max_retries} attempts")
        return None

def _create_api_client():
    """Create a minimal API client for fetching company vault"""
    from .api_client import client
    # Ensure the client has a config manager for token rotation
    client.ensure_config_manager()
    return client

def _get_universal_user_info() -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """Get universal user info and company ID from config or environment.
    Returns: (universal_user_name, universal_user_id, company_id)
    """
    # First try to get from config file
    config_path = get_main_config_file()
    if config_path.exists():
        try:
            config = json.load(open(config_path, 'r'))
            
            # Try to get vault_company from config, or initialize it
            vault_company = config.get('vault_company')
            
            if vault_company:
                # Handle encrypted vault_company
                if not is_encrypted(vault_company):
                    try:
                        vault_data = json.loads(vault_company)
                        company_id = vault_data.get('COMPANY_ID')
                        universal_user_name = vault_data.get('UNIVERSAL_USER_NAME')
                        universal_user_id = vault_data.get('UNIVERSAL_USER_ID')
                    except json.JSONDecodeError:
                        vault_data = {}
                        company_id = None
                        universal_user_name = None
                        universal_user_id = None
                else:
                    # If encrypted, we can't use it
                    vault_data = {}
                    company_id = None
                    universal_user_name = None
                    universal_user_id = None
            else:
                # No vault_company in config, initialize empty
                vault_data = {}
                company_id = None
                universal_user_name = None
                universal_user_id = None
            
            # If we don't have company_id, try to fetch it from API
            if not company_id and TokenManager.get_token():
                try:
                    from .config import TokenManager as TM
                    client = _create_api_client()
                    current_token = TokenManager.get_token()
                    response = client.token_request("GetCompanyVault", {})
                    new_token = TokenManager.get_token()
                    
                    # Force save the token to ensure subprocess gets the updated token
                    if new_token != current_token:
                        # Get current config to preserve other fields
                        config_path = get_main_config_file()
                        if config_path.exists():
                            config = json.load(open(config_path, 'r'))
                            # Ensure token is saved
                            config['token'] = new_token
                            with open(config_path, 'w') as f:
                                json.dump(config, f, indent=2)
                    
                    if not response.get('error'):
                        for table in response.get('resultSets', []):
                            data = table.get('data', [])
                            if data:
                                for row in data:
                                    if 'companyCredential' in row or 'CompanyCredential' in row:
                                        company_id = row.get('companyCredential') or row.get('CompanyCredential')
                                        
                                        # Also parse vault content if available
                                        vault_content = row.get('vaultContent')
                                        if vault_content:
                                            try:
                                                vault_from_api = json.loads(vault_content)
                                                if not universal_user_name:
                                                    universal_user_name = vault_from_api.get('UNIVERSAL_USER_NAME')
                                                if not universal_user_id:
                                                    universal_user_id = vault_from_api.get('UNIVERSAL_USER_ID')
                                                # Merge API vault data with local
                                                vault_data.update(vault_from_api)
                                            except json.JSONDecodeError:
                                                pass
                                        
                                        if company_id:
                                            # Update vault_company with COMPANY_ID and merged data
                                            vault_data['COMPANY_ID'] = company_id
                                            config['vault_company'] = json.dumps(vault_data)
                                            with open(config_path, 'w') as f:
                                                json.dump(config, f, indent=2)
                                            break
                except Exception:
                    pass  # Silently fail if COMPANY_ID cannot be fetched
            
            # If we still don't have the values, get from environment
            if not universal_user_name or not universal_user_id:
                from .env_config import EnvironmentConfig
                universal_user_name, universal_user_id, env_company_id = EnvironmentConfig.get_universal_user_info()
                if not company_id:
                    company_id = env_company_id
            
            return (universal_user_name, universal_user_id, company_id)
        except Exception:
            pass  # Fall through to environment fallback
    
    # Fall back to environment configuration
    from .env_config import EnvironmentConfig
    return EnvironmentConfig.get_universal_user_info()

class _SuppressSysExit:
    def __init__(self): self.exit_called = False; self.original_exit = None
    def __enter__(self):
        self.original_exit = sys.exit
        sys.exit = lambda code=0: setattr(self, 'exit_called', True)
        return self
    def __exit__(self, exc_type, exc_val, exc_tb): sys.exit = self.original_exit

def get_machine_info_with_team(team_name: str, machine_name: str) -> Dict[str, Any]:
    """Get machine info using the API client directly"""
    from .api_client import client
    from .config import TokenManager
    
    if not TokenManager.get_token(): 
        error_exit("No authentication token available")
    
    # Use API client directly instead of spawning CLI subprocess
    response = client.token_request("GetTeamMachines", {"teamName": team_name})
    
    if response.get('error'):
        error_exit(f"Failed to get machines for team {team_name}: {response['error']}")
    
    # Find the specific machine in the response
    machines = []
    for result_set in response.get('resultSets', []):
        machines.extend(result_set.get('data', []))
    
    machine_info = None
    for machine in machines:
        if machine.get('machineName') == machine_name:
            machine_info = machine
            break
    
    if not machine_info:
        error_exit(f"No machine data found for '{machine_name}' in team '{team_name}'")
    
    # Parse vault content if available
    vault_content = machine_info.get('vaultContent')
    if vault_content:
        try: 
            machine_info['vault'] = json.loads(vault_content) if isinstance(vault_content, str) else vault_content
        except json.JSONDecodeError: 
            pass
    
    return machine_info


def get_repository_info(team_name: str, repo_name: str) -> Dict[str, Any]:
    if not TokenManager.get_token(): 
        error_exit("No authentication token available")
    
    def try_inspect(quiet: bool = False):
        with _SuppressSysExit() as ctx:
            cmd = get_cli_command() + ['--output', 'json', 'inspect', 'repository', team_name, repo_name]
            output = run_command(cmd, quiet=quiet)
            return output, ctx.exit_called
    
    # Single attempt only, no retry
    inspect_output, exit_called = try_inspect(quiet=False)
    if not inspect_output or exit_called:
        error_exit(f"Failed to inspect repository {repo_name}")
    
    try:
        inspect_data = json.loads(inspect_output)
        if not inspect_data.get('success'):
            error_exit(f"inspecting repository: {inspect_data.get('error', 'Unknown error')}")
        
        data_list = inspect_data.get('data', [])
        if not data_list:
            error_exit(f"No repository data found for '{repo_name}' in team '{team_name}'")
        repo_info = data_list[0]
        
        vault_content = repo_info.get('vaultContent')
        if vault_content:
            try: repo_info['vault'] = json.loads(vault_content) if isinstance(vault_content, str) else vault_content
            except json.JSONDecodeError: pass
        
        return repo_info
    except json.JSONDecodeError as e:
        error_exit(f"Failed to parse JSON response: {e}")

def get_ssh_key_from_vault(team_name: Optional[str] = None) -> Optional[str]:
    """Get SSH key from team vault using the API client directly"""
    from .api_client import client
    from .config import TokenManager
    
    token = TokenManager.get_token()
    if not token:
        print(colorize("No authentication token available", 'RED'))
        return None
    
    # Use API client directly to get teams
    response = client.token_request("GetCompanyTeams", {})
    
    if response.get('error'):
        return None
    
    # Extract teams from response (GetCompanyTeams returns teams in resultSets[1])
    teams = []
    result_sets = response.get('resultSets', [])
    if len(result_sets) > 1:
        teams = result_sets[1].get('data', [])
    
    for team in teams:
        if team_name and team.get('teamName') != team_name:
            continue
        
        vault_content = team.get('vaultContent')
        if not vault_content:
            continue
        
        try:
            vault_data = json.loads(vault_content) if isinstance(vault_content, str) else vault_content
            ssh_key = vault_data.get('SSH_PRIVATE_KEY')
            if ssh_key:
                return ssh_key
        except json.JSONDecodeError:
            continue
    
    return None

def _decode_ssh_key(ssh_key: str) -> str:
    """Decode and normalize SSH key with proper line endings for cross-platform compatibility"""
    import base64

    if not ssh_key:
        raise ValueError("SSH key is empty")

    # Decode base64 if needed
    if not ssh_key.startswith('-----BEGIN') and '\n' not in ssh_key:
        try:
            ssh_key = base64.b64decode(ssh_key).decode('utf-8')
        except Exception as e:
            raise ValueError(f"Invalid base64 SSH key: {e}")

    # Normalize line endings to Unix format (required for SSH compatibility)
    ssh_key = ssh_key.replace('\r\n', '\n').replace('\r', '\n')

    # Ensure key ends with single newline
    ssh_key = ssh_key.rstrip('\n') + '\n'

    # Basic validation - check for SSH key markers
    if not ('-----BEGIN' in ssh_key and '-----END' in ssh_key):
        raise ValueError("SSH key does not contain valid PEM markers")

    # Validate common SSH key types
    valid_key_types = ['RSA PRIVATE KEY', 'DSA PRIVATE KEY', 'EC PRIVATE KEY', 'PRIVATE KEY', 'OPENSSH PRIVATE KEY']
    if not any(key_type in ssh_key for key_type in valid_key_types):
        raise ValueError("SSH key type not recognized. Supported types: RSA, DSA, EC, OpenSSH")

    return ssh_key

def _convert_path_for_ssh(path: str, ssh_executable: str = None) -> str:
    """Convert Windows paths for SSH compatibility based on SSH implementation"""
    if not path or not is_windows():
        return path

    # Determine if we're using MSYS2 SSH or Windows OpenSSH
    using_msys2 = False
    if ssh_executable:
        # Check if the SSH executable is from MSYS2
        using_msys2 = 'msys' in ssh_executable.lower() or 'mingw' in ssh_executable.lower()
    else:
        # Try to detect which SSH is in use by checking PATH
        import shutil
        ssh_path = shutil.which('ssh')
        if ssh_path:
            using_msys2 = 'msys' in ssh_path.lower() or 'mingw' in ssh_path.lower()

    if using_msys2:
        # Convert Windows path to MSYS2 format for MSYS2 SSH
        path = path.replace('\\', '/')
        if ':' in path and len(path) > 2:
            # Convert C:/path to /c/path format
            drive = path[0].lower()
            rest = path[2:] if path[1] == ':' else path
            path = f'/{drive}{rest}'
    else:
        # For Windows OpenSSH, just normalize backslashes to forward slashes
        path = path.replace('\\', '/')

    return path

def _setup_ssh_options(host_entry: str, known_hosts_path: str, key_path: str = None, ssh_executable: str = None) -> str:
    """Setup SSH options with proper path handling for cross-platform compatibility"""
    # Convert paths based on SSH implementation (MSYS2 vs Windows OpenSSH)
    if known_hosts_path:
        known_hosts_path = _convert_path_for_ssh(known_hosts_path, ssh_executable)
    if key_path:
        key_path = _convert_path_for_ssh(key_path, ssh_executable)

    # Security: Use different strategies based on host_entry availability
    if host_entry:
        # Host entry exists in vault - use strict checking to prevent MITM attacks
        # This is the secure path for machines with known host keys
        base_opts = f"-o StrictHostKeyChecking=yes -o UserKnownHostsFile={known_hosts_path}"
        _track_ssh_operation("host_key_verification", "known_host", True)
    else:
        # No host entry - this is a first-time connection or dev mode
        # For security, we still want to save the host key for future verification
        # but we need to accept it initially to establish the connection

        # Use a temporary known_hosts file to capture the host key
        # Always use the provided known_hosts path (never null device)
        base_opts = f"-o StrictHostKeyChecking=accept-new -o UserKnownHostsFile={known_hosts_path}"
        _track_ssh_operation("host_key_verification", "new_host", True)

    # Add additional security options
    security_opts = "-o PasswordAuthentication=no -o PubkeyAuthentication=yes -o PreferredAuthentications=publickey"

    # Combine all options
    all_opts = f"{base_opts} {security_opts}"

    return f"{all_opts} -i {key_path}" if key_path else all_opts

def setup_ssh_agent_connection(ssh_key: str, host_entry: str = None) -> Tuple[str, str, str]:
    import subprocess
    
    ssh_key = _decode_ssh_key(ssh_key)
    
    try:
        agent_result = subprocess.run(['ssh-agent', '-s'], capture_output=True, text=True, timeout=10)
        if agent_result.returncode != 0:
            raise RuntimeError(f"Failed to start ssh-agent: {agent_result.stderr}")
        
        agent_env = {}
        for line in agent_result.stdout.strip().split('\n'):
            var_assignment = line.split(';')[0] if ';' in line else line
            if '=' in line and ';' in line and '=' in var_assignment:
                key, value = var_assignment.split('=', 1)
                agent_env[key] = os.environ[key] = value
        
        agent_pid = agent_env.get('SSH_AGENT_PID')
        if not agent_pid: raise RuntimeError("Could not get SSH agent PID")
        
        ssh_add_result = subprocess.run(['ssh-add', '-'], 
                                      input=ssh_key, text=True,
                                      capture_output=True, timeout=10)
        
        if ssh_add_result.returncode != 0:
            subprocess.run(['kill', agent_pid], capture_output=True)
            raise RuntimeError(f"Failed to add SSH key to agent: {ssh_add_result.stderr}")
        
    except Exception as e:
        raise RuntimeError(f"SSH agent setup failed: {e}")
    
    known_hosts_file_path = None
    if host_entry:
        known_hosts_file_path = create_temp_file(suffix='_known_hosts', prefix='known_hosts_')
        with open(known_hosts_file_path, 'w') as f: f.write(host_entry + '\n')
    
    ssh_opts = _setup_ssh_options(host_entry, known_hosts_file_path)
    
    return ssh_opts, agent_pid, known_hosts_file_path

def setup_ssh_for_connection(ssh_key: str, host_entry: str = None, ssh_executable: str = None) -> Tuple[str, str, str]:
    """Setup SSH connection with enhanced error handling and cross-platform compatibility"""
    try:
        ssh_key = _decode_ssh_key(ssh_key)
    except ValueError as e:
        _track_ssh_operation("key_validation", "unknown", False, error=str(e))
        raise RuntimeError(f"SSH key validation failed: {e}")

    ssh_key_file_path = create_temp_file(suffix='_rsa', prefix='ssh_key_')

    try:
        # Write SSH key with Unix line endings for cross-platform compatibility
        # Use newline='\n' to force Unix line endings on Windows
        with open(ssh_key_file_path, 'w', newline='\n', encoding='utf-8') as f:
            f.write(ssh_key)

        set_file_permissions(ssh_key_file_path, 0o600)

        # Verify the file was written correctly
        if not os.path.exists(ssh_key_file_path):
            raise RuntimeError("SSH key file was not created successfully")

        # On Windows, verify the file content (for debugging libcrypto issues)
        if is_windows():
            try:
                with open(ssh_key_file_path, 'r', encoding='utf-8') as f:
                    written_content = f.read()
                if '-----BEGIN' not in written_content:
                    raise RuntimeError("SSH key file content validation failed")
            except Exception as e:
                _track_ssh_operation("key_file_validation", "windows", False, error=str(e))
                raise RuntimeError(f"SSH key file validation failed: {e}")

    except Exception as e:
        # Clean up the file if creation failed
        if os.path.exists(ssh_key_file_path):
            try:
                os.unlink(ssh_key_file_path)
            except:
                pass
        raise RuntimeError(f"Failed to create SSH key file: {e}")
    
    # Always create a known_hosts file, even for first-time connections
    # This allows SSH to save the host key for future verification
    known_hosts_file_path = create_temp_file(suffix='_known_hosts', prefix='known_hosts_')
    if host_entry:
        # Write the existing host entry from the vault
        with open(known_hosts_file_path, 'w') as f: 
            f.write(host_entry + '\n')
    # If no host_entry, the file is empty but will be used to store the new host key
    
    ssh_opts = _setup_ssh_options(host_entry, known_hosts_file_path, ssh_key_file_path, ssh_executable)
    
    return ssh_opts, ssh_key_file_path, known_hosts_file_path

def cleanup_ssh_agent(agent_pid: str, known_hosts_file: str = None):
    import subprocess
    if agent_pid:
        try: subprocess.run(['kill', agent_pid], capture_output=True, timeout=5)
        except: pass
    if known_hosts_file and os.path.exists(known_hosts_file): os.unlink(known_hosts_file)

def cleanup_ssh_key(ssh_key_file: str, known_hosts_file: str = None):
    for file_path in (ssh_key_file, known_hosts_file):
        if file_path and os.path.exists(file_path): os.unlink(file_path)

class SSHConnection:
    """Context manager for SSH connections with automatic cleanup.
    
    Tries SSH agent first, falls back to file-based keys if agent fails.
    Automatically cleans up resources on exit.
    """
    
    def __init__(self, ssh_key: str, host_entry: str = None, prefer_agent: bool = True):
        """Initialize SSH connection context.
        
        Args:
            ssh_key: SSH private key content
            host_entry: Optional known_hosts entry
            prefer_agent: Whether to try SSH agent first (default: True)
        """
        self.ssh_key = ssh_key
        self.host_entry = host_entry
        self.prefer_agent = prefer_agent
        self.ssh_opts = None
        self.agent_pid = None
        self.ssh_key_file = None
        self.known_hosts_file = None
        self._using_agent = False
    
    def __enter__(self):
        """Setup SSH connection."""
        start_time = time.time()
        success = False
        error = None

        try:
            if self.prefer_agent:
                try:
                    self.ssh_opts, self.agent_pid, self.known_hosts_file = setup_ssh_agent_connection(
                        self.ssh_key, self.host_entry
                    )
                    self._using_agent = True
                    success = True
                    _track_ssh_operation("connection_setup", "ssh-agent", True,
                                       (time.time() - start_time) * 1000)
                    return self
                except Exception as e:
                    error = str(e)
                    # Log warning and fall back to file-based
                    if sys.stdout.isatty():
                        print(colorize(f"SSH agent setup failed: {e}, falling back to file-based keys", 'YELLOW'))

            # File-based fallback
            self.ssh_opts, self.ssh_key_file, self.known_hosts_file = setup_ssh_for_connection(
                self.ssh_key, self.host_entry
            )
            success = True
            _track_ssh_operation("connection_setup", "file-based", True,
                               (time.time() - start_time) * 1000)
            return self
        except Exception as e:
            error = str(e)
            _track_ssh_operation("connection_setup", "unknown", False,
                               (time.time() - start_time) * 1000, error)
            raise
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Cleanup SSH resources."""
        start_time = time.time()
        try:
            if self.agent_pid:
                cleanup_ssh_agent(self.agent_pid, self.known_hosts_file)
                _track_ssh_operation("connection_cleanup", "ssh-agent", True,
                                   (time.time() - start_time) * 1000)
            elif self.ssh_key_file:
                cleanup_ssh_key(self.ssh_key_file, self.known_hosts_file)
                _track_ssh_operation("connection_cleanup", "file-based", True,
                                   (time.time() - start_time) * 1000)
        except Exception as e:
            _track_ssh_operation("connection_cleanup", self.connection_method, False,
                               (time.time() - start_time) * 1000, str(e))
    
    @property
    def is_using_agent(self) -> bool:
        """Check if using SSH agent."""
        return self._using_agent
    
    @property
    def connection_method(self) -> str:
        """Get the connection method being used."""
        return "ssh-agent" if self._using_agent else "file-based"

class SSHTunnelConnection(SSHConnection):
    """Context manager for SSH connections that need to maintain tunnels.
    
    This is a special variant that doesn't automatically cleanup SSH resources
    on exit, allowing tunnels to persist. Cleanup must be done manually.
    """
    
    def __init__(self, ssh_key: str, host_entry: str = None, prefer_agent: bool = True):
        """Initialize SSH tunnel connection context."""
        super().__init__(ssh_key, host_entry, prefer_agent)
        self._cleanup_on_exit = True
    
    def disable_auto_cleanup(self):
        """Disable automatic cleanup on exit (for persistent tunnels)."""
        self._cleanup_on_exit = False
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Only cleanup if auto-cleanup is enabled."""
        if self._cleanup_on_exit:
            super().__exit__(exc_type, exc_val, exc_tb)
    
    def manual_cleanup(self):
        """Manually cleanup SSH resources."""
        if self.agent_pid:
            cleanup_ssh_agent(self.agent_pid, self.known_hosts_file)
        elif self.ssh_key_file:
            cleanup_ssh_key(self.ssh_key_file, self.known_hosts_file)

def get_machine_connection_info(machine_info: Dict[str, Any]) -> Dict[str, Any]:
    machine_name = machine_info.get('machineName')
    vault = machine_info.get('vault', {})
    
    if not vault:
        vault_content = machine_info.get('vaultContent')
        if vault_content:
            if isinstance(vault_content, str):
                try:
                    vault = machine_info['vault'] = json.loads(vault_content)
                except json.JSONDecodeError as e:
                    print(colorize(f"Failed to parse vaultContent: {e}", 'RED'))
    
    ip = vault.get('ip') or vault.get('IP')
    ssh_user = vault.get('user') or vault.get('USER')
    datastore = vault.get('datastore') or vault.get('DATASTORE')
    host_entry = vault.get('hostEntry') or vault.get('HOST_ENTRY')
    
    # Validate required fields
    if not datastore:
        error_exit(f"Machine vault for '{machine_name}' is missing required 'datastore' field")
    
    universal_user, universal_user_id, _ = _get_universal_user_info()
    
    # Use defaults if values are None
    if not universal_user:
        universal_user = 'rediacc'
        print(colorize("Warning: Using default universal user 'rediacc'", 'YELLOW'))
    
    if not universal_user_id:
        universal_user_id = '7111'
        print(colorize("Warning: Using default universal user ID '7111'", 'YELLOW'))
    
    if not ssh_user:
        print(colorize(f"ERROR: SSH user not found in machine vault. Vault contents: {vault}", 'RED'))
        raise ValueError(f"SSH user not found in machine vault for {machine_name}. The machine vault should contain 'user' field.")
    
    if not ip:
        print(colorize(f"\n✗ Machine configuration error", 'RED'))
        print(colorize(f"  Machine '{machine_name}' does not have an IP address configured", 'RED'))
        print(colorize("\nThe machine vault must contain:", 'YELLOW'))
        print(colorize("  • 'ip' or 'IP': The machine's IP address", 'YELLOW'))
        print(colorize("  • 'user' or 'USER': SSH username", 'YELLOW'))
        print(colorize("  • 'datastore' or 'DATASTORE': Datastore path (optional)", 'YELLOW'))
        print(colorize("\nPlease update the machine configuration in the Rediacc console.", 'YELLOW'))
        raise ValueError(f"Machine IP not found in vault for {machine_name}")
    
    return {
        'ip': ip,
        'user': ssh_user,
        'universal_user': universal_user,
        'universal_user_id': universal_user_id,
        'datastore': datastore,
        'team': machine_info.get('teamName'),
        'host_entry': host_entry
    }

def get_crc32(text: str) -> str:
    """Calculate CRC32 for a string, compatible with cksum command."""
    import zlib
    # Use zlib.crc32 which is cross-platform
    crc = zlib.crc32(text.encode('utf-8')) & 0xffffffff
    return str(crc)

def get_repository_paths(repo_guid: str, datastore: str, universal_user_id: str, company_id: str) -> Dict[str, str]:
    """Calculate repository paths. Both universal_user_id and company_id are required."""
    if not universal_user_id or not company_id:
        raise ValueError("Both universal_user_id and company_id are required for repository paths")
    
    base_path = f"{datastore}/{universal_user_id}/{company_id}"
    docker_base = f"{base_path}/{INTERIM_FOLDER_NAME}/{repo_guid}/docker"
    
    # Calculate runtime paths for short socket locations
    company_crc = get_crc32(company_id)
    repo_crc = get_crc32(repo_guid)
    runtime_base = f"/var/run/rediacc/{universal_user_id}/{company_crc}/{repo_crc}"
    runtime_paths = {
        'runtime_base': runtime_base,
        'docker_socket': f"{runtime_base}/docker.sock",
        'plugin_socket_dir': f"{runtime_base}/plugins",
        'docker_exec': f"{runtime_base}/exec",
    }
    
    paths = {
        'mount_path': f"{base_path}/{MOUNTS_FOLDER_NAME}/{repo_guid}",
        'image_path': f"{base_path}/{REPOS_FOLDER_NAME}/{repo_guid}",
        'docker_folder': docker_base,
        'docker_socket': runtime_paths['docker_socket'],
        'docker_data': f"{docker_base}/data",
        'docker_exec': runtime_paths['docker_exec'],
        'plugin_socket_dir': runtime_paths['plugin_socket_dir'],
        **runtime_paths  # Include all runtime paths
    }
    
    return paths

def initialize_cli_command(args, parser, requires_cli_tool=True):
    """Standard initialization for CLI commands.
    
    Performs common initialization tasks:
    1. Validates authentication
    2. Validates CLI tool availability (if required)
    
    Args:
        args: Parsed command line arguments
        parser: ArgumentParser instance for error reporting
        requires_cli_tool: Whether to validate rediacc.py exists (default: True)
    """
    # Validate authentication
    if hasattr(args, 'token') and args.token:
        os.environ['REDIACC_TOKEN'] = args.token
    elif not TokenManager.get_token():
        parser.error("No authentication token available. Please login first.")
    
    # Validate CLI tool if required
    if requires_cli_tool:
        if not os.path.exists(CLI_TOOL): 
            error_exit(f"rediacc not found at {CLI_TOOL}")
        if not is_windows() and not os.access(CLI_TOOL, os.X_OK): 
            error_exit(f"rediacc is not executable at {CLI_TOOL}")

def add_common_arguments(parser, include_args=None, required_overrides=None):
    """Add common arguments to an argument parser.
    
    Args:
        parser: ArgumentParser or subparser to add arguments to
        include_args: List of argument names to include. If None, includes all.
                     Valid names: 'token', 'team', 'machine', 'repo', 'verbose'
        required_overrides: Dict mapping argument names to their required status.
                           E.g., {'team': False, 'machine': False} to make them optional
    
    Returns:
        parser: The modified parser (for chaining)
    """
    # Define all common arguments with their configurations
    common_args = {
        'token': {
            'flags': ['--token'],
            'kwargs': {
                'help': 'Authentication token (GUID) - uses saved token if not specified',
                'required': False
            }
        },
        'team': {
            'flags': ['--team'],
            'kwargs': {
                'help': 'Team name',
                'required': True
            }
        },
        'machine': {
            'flags': ['--machine'],
            'kwargs': {
                'help': 'Machine name',
                'required': True
            }
        },
        'repo': {
            'flags': ['--repo'],
            'kwargs': {
                'help': 'Repository name',
                'required': True
            }
        },
        'verbose': {
            'flags': ['--verbose', '-v'],
            'kwargs': {
                'action': 'store_true',
                'help': 'Enable verbose logging output'
            }
        }
    }
    
    # If no specific args requested, include all
    if include_args is None:
        include_args = list(common_args.keys())
    
    # Initialize required_overrides if not provided
    if required_overrides is None:
        required_overrides = {}
    
    # Add requested arguments
    for arg_name in include_args:
        if arg_name in common_args:
            arg_config = common_args[arg_name].copy()
            kwargs = arg_config['kwargs'].copy()
            
            # Apply required override if specified
            if arg_name in required_overrides:
                kwargs['required'] = required_overrides[arg_name]
            
            parser.add_argument(*arg_config['flags'], **kwargs)
    
    return parser

def wait_for_enter(message: str = "Press Enter to continue..."):
    input(colorize(f"\n{message}", 'YELLOW'))

def test_ssh_connectivity(ip: str, port: int = 22, timeout: int = 5) -> Tuple[bool, str]:
    import socket
    start_time = time.time()
    success = False
    error = ""

    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(timeout)
            if sock.connect_ex((ip, port)) == 0:
                success = True
                result = (True, "")
            else:
                error = f"Cannot connect to {ip}:{port} - port appears to be closed or filtered"
                result = (False, error)
    except socket.timeout:
        error = f"Connection to {ip}:{port} timed out after {timeout} seconds"
        result = (False, error)
    except socket.gaierror:
        error = f"Failed to resolve hostname: {ip}"
        result = (False, error)
    except Exception as e:
        error = f"Connection test failed: {str(e)}"
        result = (False, error)

    # Track connectivity test
    _track_ssh_operation("connectivity_test", ip, success,
                       (time.time() - start_time) * 1000, error if not success else None)

    return result

def validate_machine_accessibility(machine_name: str, team_name: str, ip: str, repo_name: str = None):
    print(f"Testing connectivity to {ip}...")
    is_accessible, error_msg = test_ssh_connectivity(ip)
    if is_accessible: print(colorize("✓ Machine is accessible", 'GREEN')); return
    
    print(colorize(f"\n✗ Machine '{machine_name}' is not accessible", 'RED'))
    print(colorize(f"  Error: {error_msg}", 'RED'))
    print(colorize("\nPossible reasons:", 'YELLOW'))
    for reason in ["The machine is offline or powered down", "Network connectivity issues between client and machine", "Firewall blocking SSH port (22)", "Incorrect IP address in machine configuration"]:
        print(colorize(f"  • {reason}", 'YELLOW'))
    
    print(colorize(f"\nMachine IP: {ip}", 'BLUE'))
    print(colorize(f"Team: {team_name}", 'BLUE'))
    if repo_name:
        print(colorize(f"Repository: {repo_name}", 'BLUE'))
    print(colorize("\nPlease verify the machine is online and accessible from your network.", 'YELLOW'))
    wait_for_enter("Press Enter to exit...")
    sys.exit(1)  # Keep as is - this is a special user interaction case

def handle_ssh_exit_code(returncode: int, connection_type: str = "machine"):
    success = returncode == 0
    error = None

    if returncode == 0:
        print(colorize(f"\nDisconnected from {connection_type}.", 'GREEN'))
    elif returncode == 255:
        error = f"SSH connection failed (exit code: {returncode})"
        print(colorize(f"\n✗ {error}", 'RED'))
        print(colorize("\nPossible reasons:", 'YELLOW'))
        reasons = [
            "SSH authentication failed (check SSH key in team vault)",
            "SSH host key verification failed",
            "SSH service not running on the machine",
            "Network connection interrupted"
        ]
        for reason in reasons:
            print(colorize(f"  • {reason}", 'YELLOW'))
    else:
        error = f"SSH disconnected with exit code {returncode}"
        print(colorize(f"\nDisconnected from {connection_type} (exit code: {returncode})", 'YELLOW'))

    # Track SSH command execution result
    _track_ssh_operation("command_execution", connection_type, success, error=error)

class RepositoryConnection:
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
        print("Fetching machine information...")
        
        self._machine_info = get_machine_info_with_team(self.team_name, self.machine_name)
        self._connection_info = get_machine_connection_info(self._machine_info)
        
        if not all([self._connection_info.get('ip'), self._connection_info.get('user')]):
            error_exit("Machine IP or user not found in vault")
        
        print(f"Fetching repository information for '{self.repo_name}'...")
        self._repo_info = get_repository_info(self._connection_info['team'], self.repo_name)
        
        repo_guid = self._repo_info.get('repoGuid') or self._repo_info.get('grandGuid')
        if not repo_guid:
            print(colorize(f"Repository info: {json.dumps(self._repo_info, indent=2)}", 'YELLOW'))
            error_exit(f"Repository GUID not found for '{self.repo_name}'")
        
        _, universal_user_id, company_id = _get_universal_user_info()
        
        if not company_id:
            error_exit("COMPANY_ID not found. Please re-login or check your company configuration.")
        
        if not universal_user_id:
            error_exit("Universal user ID not found. Please re-login or check your company configuration.")
        
        self._repo_paths = get_repository_paths(repo_guid, self._connection_info['datastore'], universal_user_id, company_id)
        
        if not self._repo_paths:
            error_exit("Failed to calculate repository paths")
        
        print("Retrieving SSH key...")
        team_name = self._connection_info.get('team', self.team_name)
        self._ssh_key = get_ssh_key_from_vault(team_name)
        if not self._ssh_key:
            error_msg = f"SSH private key not found in vault for team '{team_name}'"
            print(colorize(error_msg, 'RED'))
            print(colorize("The team vault should contain 'SSH_PRIVATE_KEY' field with the SSH private key.", 'YELLOW'))
            print(colorize("Please ensure SSH keys are properly configured in your team's vault settings.", 'YELLOW'))
            raise Exception(error_msg)  # Raise exception instead of sys.exit so GUI can handle it
    
    def setup_ssh(self, ssh_executable: str = None) -> Tuple[str, str, str]:
        host_entry = self._connection_info.get('host_entry')
        return setup_ssh_for_connection(self._ssh_key, host_entry, ssh_executable)
    
    def cleanup_ssh(self, ssh_key_file: str, known_hosts_file: str = None):
        cleanup_ssh_key(ssh_key_file, known_hosts_file)
    
    def ssh_context(self, prefer_agent: bool = True):
        """Get SSH connection context manager.
        
        Args:
            prefer_agent: Whether to try SSH agent first (default: True)
            
        Returns:
            SSHConnection context manager
        """
        host_entry = self._connection_info.get('host_entry')
        return SSHConnection(self._ssh_key, host_entry, prefer_agent)
    
    @property
    def ssh_destination(self) -> str:
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