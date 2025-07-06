#!/usr/bin/env python3
"""
Rediacc CLI Core - Common functionality for Rediacc CLI tools
Provides shared functions for authentication, API communication, and SSH operations

RESOLVED LIMITATIONS:
1. Use --include-vault flag with rediacc-cli to get vaultContent from list teams
2. Added inspect command for machines and repositories to get detailed vault data
3. SSH keys are retrieved from team vault (SSH_PRIVATE_KEY field)
4. Machine connection details (ip, user, datastore) come from machine vault
"""
import json
import os
import subprocess
import sys
import tempfile
import platform
from pathlib import Path
from typing import Dict, Any, Optional, Tuple

# Import token manager
from token_manager import TokenManager, get_default_token_manager

# Import configuration loader
from config_loader import get, get_required, get_path

# Configuration
CLI_TOOL = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'rediacc-cli')

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

def run_command(cmd, capture_output=True, check=True):
    """Run a command and return the result"""
    if isinstance(cmd, str):
        cmd = cmd.split()
    
    try:
        if capture_output:
            result = subprocess.run(cmd, capture_output=True, text=True, check=check)
            return result.stdout.strip() if result.returncode == 0 else None
        else:
            return subprocess.run(cmd, check=check)
    except subprocess.CalledProcessError as e:
        if check:
            # Sanitize command to hide tokens
            safe_cmd = [safe_error_message(arg) for arg in cmd]
            print(colorize(f"Error running command: {' '.join(safe_cmd)}", 'RED'))
            if hasattr(e, 'stderr') and e.stderr:
                print(colorize(f"Error: {safe_error_message(e.stderr)}", 'RED'))
            sys.exit(1)
        return None

def get_machine_info(machine_name: str, token_manager: Optional[TokenManager] = None) -> Dict[str, Any]:
    """Get machine information using rediacc-cli inspect command"""
    if token_manager is None:
        token_manager = get_default_token_manager()
    
    token = token_manager.get_token()
    if not token:
        print(colorize("No authentication token available", 'RED'))
        sys.exit(1)
    
    # First, get the list of all teams to find which team has this machine
    teams_output = run_command([CLI_TOOL, '--token', token, '--output', 'json', 'list', 'teams'])
    if not teams_output:
        print(colorize("Failed to get teams list", 'RED'))
        sys.exit(1)
    
    try:
        teams_data = json.loads(teams_output)
        if not teams_data.get('success'):
            print(colorize(f"Error listing teams: {teams_data.get('error', 'Unknown error')}", 'RED'))
            sys.exit(1)
        
        # Search through teams to find the machine
        for team in teams_data.get('data', []):
            team_name = team.get('teamName')
            if not team_name:
                continue
                
            # Try to inspect the machine in this team
            inspect_output = run_command([CLI_TOOL, '--token', token, '--include-vault', '--output', 'json', 'inspect', 'machine', team_name, machine_name])
            if not inspect_output:
                continue
                
            try:
                inspect_data = json.loads(inspect_output)
                if inspect_data.get('success') and inspect_data.get('data'):
                    # Machine found in this team
                    machine_info = inspect_data['data'][0]
                    
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
            except json.JSONDecodeError:
                continue
        
        # Machine not found in any team
        print(colorize(f"Machine '{machine_name}' not found", 'RED'))
        sys.exit(1)
        
    except json.JSONDecodeError as e:
        print(colorize(f"Failed to parse JSON response: {e}", 'RED'))
        sys.exit(1)

def get_repository_info(team_name: str, repo_name: str, token_manager: Optional[TokenManager] = None) -> Dict[str, Any]:
    """Get repository information using rediacc-cli inspect command"""
    if token_manager is None:
        token_manager = get_default_token_manager()
    
    token = token_manager.get_token()
    if not token:
        print(colorize("No authentication token available", 'RED'))
        sys.exit(1)
    
    inspect_output = run_command([CLI_TOOL, '--token', token, '--include-vault', '--output', 'json', 'inspect', 'repository', team_name, repo_name])
    if not inspect_output:
        print(colorize(f"Failed to inspect repository {repo_name}", 'RED'))
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

def get_ssh_key_from_vault(token_manager: Optional[TokenManager] = None) -> Optional[str]:
    """Extract SSH private key from team vault"""
    if token_manager is None:
        token_manager = get_default_token_manager()
    
    token = token_manager.get_token()
    if not token:
        print(colorize("No authentication token available", 'RED'))
        return None
    
    # Use the CLI with --include-vault flag to get team vault content
    teams_output = run_command([CLI_TOOL, '--token', token, '--include-vault', '--output', 'json', 'list', 'teams'])
    if not teams_output:
        return None
    
    try:
        result = json.loads(teams_output)
        if result.get('success') and result.get('data'):
            # Look through teams for SSH key in vault
            for team in result.get('data', []):
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
    
    # Get IP from vault (it's directly in the machine vault)
    ip = vault.get('ip') or vault.get('IP')
    
    # Get SSH user from vault (this is the user we SSH as)
    ssh_user = vault.get('user') or vault.get('USER')
    
    # Get universal user and ID from company vault (this is the user we sudo to)
    universal_user = None
    universal_user_id = None
    config_path = Path.home() / '.rediacc' / 'config.json'
    if config_path.exists():
        try:
            with open(config_path, 'r') as f:
                config = json.load(f)
                vault_company = config.get('vault_company')
                if vault_company:
                    vault_data = json.loads(vault_company)
                    universal_user = vault_data.get('UNIVERSAL_USER_NAME')
                    universal_user_id = vault_data.get('UNIVERSAL_USER_ID')
        except (json.JSONDecodeError, IOError):
            pass
    
    if not ssh_user:
        raise ValueError(f"Machine user not found in vault for {machine_name}")
    
    # Get datastore from vault
    datastore = vault.get('datastore') or vault.get('DATASTORE', DATASTORE_PATH)
    
    if not ip:
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
    if not os.access(CLI_TOOL, os.X_OK):
        print(colorize(f"Error: rediacc-cli is not executable at {CLI_TOOL}", 'RED'))
        sys.exit(1)

class RepositoryConnection:
    """Helper class to manage repository connections"""
    
    def __init__(self, machine_name: str, repo_name: str, token_manager: Optional[TokenManager] = None):
        self.token_manager = token_manager or get_default_token_manager()
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
        self._machine_info = get_machine_info(self.machine_name, self.token_manager)
        self._connection_info = get_machine_connection_info(self._machine_info)
        
        if not self._connection_info['ip'] or not self._connection_info['user']:
            print(colorize("Machine IP or user not found in vault", 'RED'))
            sys.exit(1)
        
        print(f"Fetching repository information for '{self.repo_name}'...")
        self._repo_info = get_repository_info(self._connection_info['team'], self.repo_name, self.token_manager)
        
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
        config_path = Path.home() / '.rediacc' / 'config.json'
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
        self._ssh_key = get_ssh_key_from_vault(self.token_manager)
        if not self._ssh_key:
            print(colorize("SSH private key not found in team vault", 'RED'))
            print(colorize("Please ensure SSH keys are set in team vault using GetCompanyTeams API", 'YELLOW'))
            print(colorize("The current CLI 'list teams' command doesn't return vaultContent", 'YELLOW'))
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