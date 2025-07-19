"""
CLI wrapper for testing the Rediacc CLI application.
Provides both real execution and mock modes for unit testing.
"""

import json
import subprocess
import os
import sys
import logging
from typing import Dict, Any, List, Optional, Tuple
from pathlib import Path
import tempfile
import shlex

try:
    from .mock_handler import MockHandler
except ImportError:
    from mock_handler import MockHandler


class CLIWrapper:
    """
    Wrapper around the rediacc-cli.py for testing purposes.
    Supports both real execution and mock modes.
    """
    
    def __init__(self, 
                 cli_path: Optional[str] = None,
                 config_dir: Optional[str] = None,
                 mock_mode: bool = False,
                 verbose: bool = False):
        
        # Find CLI path
        if cli_path:
            self.cli_path = Path(cli_path)
        else:
            # Try to find the CLI relative to this file
            base_dir = Path(__file__).parent.parent.parent
            self.cli_path = base_dir / "src" / "cli" / "rediacc-cli.py"
        
        if not self.cli_path.exists() and not mock_mode:
            raise FileNotFoundError(f"CLI not found at {self.cli_path}")
        
        # Setup config directory
        if config_dir:
            self.config_dir = Path(config_dir)
        else:
            self.config_dir = Path(tempfile.mkdtemp(prefix="rediacc_test_"))
        
        self.config_dir.mkdir(exist_ok=True)
        self.config_file = self.config_dir / "config.json"
        
        self.mock_mode = mock_mode
        self.verbose = verbose
        self.logger = logging.getLogger(self.__class__.__name__)
        
        # Initialize mock handler if in mock mode
        if mock_mode:
            self.mock_handler = MockHandler()
        else:
            self.mock_handler = None
        
        # Authentication state
        self.auth_token: Optional[str] = None
        self.master_password: Optional[str] = None
    
    def _build_command(self, *args, output_json: bool = True) -> List[str]:
        """Build command line arguments"""
        cmd = [sys.executable, str(self.cli_path)]
        
        # Add global options BEFORE the command
        # Add JSON output by default
        if output_json:
            cmd.extend(["--output", "json"])
        
        # Add verbose flag
        if self.verbose:
            cmd.append("--verbose")
        
        # Now add the command and its arguments
        cmd.extend(str(arg) for arg in args)
        
        # Add config directory AFTER the command for login
        if args and args[0] == "login":
            # For login, we might not need config-dir
            pass
        else:
            # For other commands, add token if available
            if self.auth_token:
                cmd.extend(["--token", self.auth_token])
        
        # Add master password if set
        if self.master_password:
            cmd.extend(["--master-password", self.master_password])
        
        return cmd
    
    def _execute(self, cmd: List[str]) -> Tuple[int, str, str]:
        """Execute a command and return (returncode, stdout, stderr)"""
        if self.mock_mode:
            return self._execute_mock(cmd)
        
        self.logger.debug(f"Executing: {' '.join(cmd)}")
        
        env = os.environ.copy()
        # Ensure HOME is set for config directory
        env['HOME'] = str(Path.home())
        
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                env=env,
                timeout=60
            )
            
            return result.returncode, result.stdout, result.stderr
            
        except subprocess.TimeoutExpired:
            self.logger.error("Command timed out")
            return 1, "", "Command timed out"
        except Exception as e:
            self.logger.error(f"Command failed: {e}")
            return 1, "", str(e)
    
    def _execute_mock(self, cmd: List[str]) -> Tuple[int, str, str]:
        """Execute in mock mode for unit testing"""
        self.logger.debug(f"Mock executing: {' '.join(cmd)}")
        
        try:
            # Parse command
            parsed_cmd = self.mock_handler.parse_command(cmd)
            
            # Generate response
            response_data = self.mock_handler.generate_response(parsed_cmd)
            
            # Return as JSON
            return 0, json.dumps(response_data), ""
            
        except Exception as e:
            self.logger.error(f"Mock execution failed: {e}")
            error_response = {"success": False, "error": str(e)}
            return 1, json.dumps(error_response), str(e)
    
    def _handle_command_result(self, returncode: int, stdout: str, stderr: str, entity_type: str = None, operation: str = None) -> Dict[str, Any]:
        """Handle command execution result with proper error extraction"""
        if returncode != 0:
            # Try to parse JSON from stdout first, as it may contain detailed error info
            parsed = self._parse_json_output(stdout)
            if parsed.get("error"):
                return {"success": False, "error": parsed["error"]}
            
            # Fall back to stderr or generic message
            default_msg = f"Failed to {operation or 'execute command'}"
            if entity_type:
                default_msg = f"Failed to {operation or 'process'} {entity_type}"
            return {"success": False, "error": stderr or default_msg}
        
        return self._parse_json_output(stdout)
    
    def _parse_json_output(self, stdout: str) -> Dict[str, Any]:
        """Parse JSON output from CLI"""
        if not stdout.strip():
            return {}
        
        try:
            # First try to parse the entire output as JSON
            # This handles multi-line JSON responses
            return json.loads(stdout.strip())
            
        except json.JSONDecodeError as e:
            self.logger.error(f"Failed to parse JSON: {e}")
            self.logger.error(f"Output was: {stdout}")
            return {"error": "Failed to parse JSON output", "raw": stdout}
    
    def add_mock_response(self, entity_type: str, entity_name: str, data: Dict[str, Any]):
        """Add a pre-configured entity to mock handler"""
        if self.mock_handler:
            entity_key = f"{entity_type}:{entity_name}"
            self.mock_handler.entities[entity_key] = data
    
    def login(self, username: str, password: str) -> Dict[str, Any]:
        """Authenticate with the API"""
        cmd = self._build_command("login", "--email", username, "--password", password)
        
        if self.verbose:
            self.logger.debug(f"Login command: {' '.join(cmd)}")
        
        returncode, stdout, stderr = self._execute(cmd)
        
        if returncode != 0:
            self.logger.error(f"Login failed with code {returncode}")
            self.logger.error(f"stdout: {stdout}")
            self.logger.error(f"stderr: {stderr}")
            return {"success": False, "error": stderr or stdout or "Login failed"}
        
        result = self._parse_json_output(stdout)
        
        # Check if we got a proper error message from the API
        if not result.get("success") and result.get("error"):
            # Extract the actual error message
            error_msg = result.get("error", "")
            if "API Error:" in error_msg:
                # Extract the meaningful part
                try:
                    # Look for the errors array in the API response
                    import re
                    match = re.search(r'"errors":\["([^"]+)"\]', error_msg)
                    if match:
                        result["error"] = match.group(1)
                except:
                    pass
        
        # Save auth token if successful
        if result.get("success"):
            self.auth_token = result.get("token")
            self._save_config()
        
        return result
    
    def _save_config(self):
        """Save configuration including auth token"""
        config = {
            "tokens": {
                "default": self.auth_token
            },
            "current_token": "default"
        }
        
        with open(self.config_file, 'w') as f:
            json.dump(config, f, indent=2)
    
    def create(self, entity_type: str, **params) -> Dict[str, Any]:
        """Create an entity"""
        cmd = self._build_command("create", entity_type)
        
        # Handle special cases where name is a positional argument
        if entity_type in ["team", "region", "user"] and "name" in params:
            name = params.pop("name")
            cmd.append(name)
        elif entity_type == "bridge" and "name" in params:
            # For bridge: create bridge <region> <name>
            region = params.pop("region", None)
            name = params.pop("name")
            if region:
                cmd.append(region)
            cmd.append(name)
        elif entity_type == "machine":
            # For machine: create machine <team> <bridge> <name>
            team = params.pop("team", None)
            bridge = params.pop("bridge", None) 
            name = params.pop("name", None)
            if team:
                cmd.append(team)
            if bridge:
                cmd.append(bridge)
            if name:
                cmd.append(name)
        elif entity_type in ["repository", "storage", "schedule"]:
            # For these: create <type> <team> <name>
            team = params.pop("team", None)
            name = params.pop("name", None)
            if team:
                cmd.append(team)
            if name:
                cmd.append(name)
        elif entity_type == "company" and "name" in params:
            name = params.pop("name")
            cmd.append(name)
        
        # Add remaining parameters as flags
        for key, value in params.items():
            if value is not None:
                # Special handling for vault - convert dict to JSON
                if key == "vault" and isinstance(value, dict):
                    cmd.extend(["--vault", json.dumps(value)])
                else:
                    cmd.extend([f"--{key.replace('_', '-')}", str(value)])
        
        returncode, stdout, stderr = self._execute(cmd)
        return self._handle_command_result(returncode, stdout, stderr, entity_type, "create")
    
    def list(self, entity_type: str, **params) -> Dict[str, Any]:
        """List entities"""
        cmd = self._build_command("list", entity_type)
        
        # Handle special cases where team is a positional argument
        if entity_type in ["team-machines", "team-members", "team-repositories", "team-schedules", "team-storages"] and "team" in params:
            team = params.pop("team")
            cmd.append(team)
        
        # Add remaining parameters as flags
        for key, value in params.items():
            if value is not None:
                cmd.extend([f"--{key.replace('_', '-')}", str(value)])
        
        returncode, stdout, stderr = self._execute(cmd)
        return self._handle_command_result(returncode, stdout, stderr, entity_type, "list")
    
    def get(self, entity_type: str, name: str, **params) -> Dict[str, Any]:
        """Get a specific entity"""
        if entity_type == "machine":
            # Machine inspect requires team name
            team = params.get("team")
            if not team:
                # Try to get team from context if not provided
                return {"success": False, "error": "Team name required for machine inspect"}
            cmd = self._build_command("inspect", entity_type, team, name)
        else:
            cmd = self._build_command("inspect", entity_type, name)
        
        returncode, stdout, stderr = self._execute(cmd)
        return self._handle_command_result(returncode, stdout, stderr, entity_type, "get")
    
    def update(self, entity_type: str, name: str, **params) -> Dict[str, Any]:
        """Update an entity"""
        cmd = self._build_command("update", entity_type, name)
        
        # Add parameters
        for key, value in params.items():
            if value is not None:
                cmd.extend([f"--{key.replace('_', '-')}", str(value)])
        
        returncode, stdout, stderr = self._execute(cmd)
        return self._handle_command_result(returncode, stdout, stderr, entity_type, "update")
    
    def delete(self, entity_type: str, name: str) -> Dict[str, Any]:
        """Delete an entity"""
        cmd = self._build_command("rm", entity_type, name, "--force")
        
        returncode, stdout, stderr = self._execute(cmd)
        return self._handle_command_result(returncode, stdout, stderr, entity_type, "delete")
    
    def create_queue_item(self, **params) -> Dict[str, Any]:
        """Create a queue item"""
        cmd = self._build_command("queue", "create")
        
        # Required parameters
        for key in ['team', 'machine', 'function']:
            if key in params:
                cmd.extend([f"--{key}", str(params[key])])
        
        # Optional parameters
        if 'priority' in params:
            cmd.extend(["--priority", str(params['priority'])])
        
        # Vault data
        if 'vault' in params:
            vault_json = json.dumps(params['vault'])
            cmd.extend(["--vault", vault_json])
        
        returncode, stdout, stderr = self._execute(cmd)
        return self._handle_command_result(returncode, stdout, stderr, "queue item", "create")
    
    def get_queue_status(self, task_id: str) -> Dict[str, Any]:
        """Get queue item status"""
        cmd = self._build_command("queue", "status", task_id)
        
        returncode, stdout, stderr = self._execute(cmd)
        return self._handle_command_result(returncode, stdout, stderr, "queue", "get status")
    
    def execute_raw(self, args: List[str], output_json: bool = True) -> Dict[str, Any]:
        """Execute raw CLI command"""
        cmd = self._build_command(*args, output_json=output_json)
        
        returncode, stdout, stderr = self._execute(cmd)
        
        if returncode != 0:
            # For raw execution, include stdout in error response
            result = self._handle_command_result(returncode, stdout, stderr, None, "execute")
            result["stdout"] = stdout
            return result
        
        if output_json:
            return self._parse_json_output(stdout)
        else:
            return {"success": True, "output": stdout}
    
    def set_master_password(self, password: str):
        """Set master password for vault encryption"""
        self.master_password = password
    
    def cleanup(self):
        """Clean up temporary files and reset mock state"""
        if self.config_dir and self.config_dir.name.startswith("rediacc_test_"):
            import shutil
            shutil.rmtree(self.config_dir, ignore_errors=True)
        
        # Reset mock handler
        if self.mock_handler:
            self.mock_handler.reset()