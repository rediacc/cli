#!/usr/bin/env python3
"""
Subprocess runner for executing CLI commands from GUI
"""

import subprocess
import json
import os
import sys
import shutil
import platform
from typing import Dict, List, Any, Optional

# Import logging configuration
from logging_config import get_logger


class SubprocessRunner:
    """Runs CLI commands and captures output"""
    
    def __init__(self):
        self.logger = get_logger(__name__)
        # Store original Windows paths
        self.cli_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.cli_path = os.path.join(self.cli_dir, 'cli', 'rediacc-cli')
        self.sync_path = os.path.join(self.cli_dir, 'cli', 'rediacc-cli-sync')
        self.term_path = os.path.join(self.cli_dir, 'cli', 'rediacc-cli-term')
        self.plugin_path = os.path.join(self.cli_dir, 'cli', 'rediacc-cli-plugin')
        self.wrapper_path = os.path.join(os.path.dirname(self.cli_dir), 'rediacc')
        
        # Check for MSYS2 on Windows for better compatibility
        self.msys2_path = None
        self.use_msys2_python = False
        if platform.system().lower() == 'windows':
            self.msys2_path = self._find_msys2_installation()
            
        self.python_cmd = self._find_python()
        
        # If using MSYS2 Python, convert paths to MSYS2 format
        if self.use_msys2_python:
            self.cli_dir_msys2 = self._windows_to_msys2_path(self.cli_dir)
            self.cli_path_msys2 = self._windows_to_msys2_path(self.cli_path)
            self.sync_path_msys2 = self._windows_to_msys2_path(self.sync_path)
            self.term_path_msys2 = self._windows_to_msys2_path(self.term_path)
            self.plugin_path_msys2 = self._windows_to_msys2_path(self.plugin_path)
        else:
            # Use original paths
            self.cli_dir_msys2 = self.cli_dir
            self.cli_path_msys2 = self.cli_path
            self.sync_path_msys2 = self.sync_path
            self.term_path_msys2 = self.term_path
            self.plugin_path_msys2 = self.plugin_path
    
    def _find_msys2_installation(self):
        """Find MSYS2 installation path on Windows"""
        msys2_paths = [
            'C:\\msys64',
            'C:\\msys2',
            os.path.expanduser('~\\msys64'),
            os.path.expanduser('~\\msys2'),
        ]
        
        # Check MSYS2_ROOT environment variable
        msys2_root = os.environ.get('MSYS2_ROOT')
        if msys2_root:
            msys2_paths.insert(0, msys2_root)
        
        for path in msys2_paths:
            if os.path.exists(path):
                return path
        return None

    def _windows_to_msys2_path(self, windows_path):
        """Convert Windows path to MSYS2 format"""
        if not windows_path:
            return windows_path
            
        # Convert C:\path\to\file to /c/path/to/file
        if len(windows_path) >= 2 and windows_path[1] == ':':
            drive = windows_path[0].lower()
            rest = windows_path[2:].replace('\\', '/')
            return f'/{drive}{rest}'
        return windows_path.replace('\\', '/')

    def _find_python(self) -> str:
        """Find the correct Python command to use"""
        self.logger.debug("Finding Python command...")
        self.logger.debug(f"MSYS2 path: {self.msys2_path}")
        
        # On Windows with MSYS2, prefer MSYS2 python3
        if self.msys2_path:
            msys2_python = os.path.join(self.msys2_path, 'usr', 'bin', 'python3.exe')
            self.logger.debug(f"Checking MSYS2 Python: {msys2_python}")
            if os.path.exists(msys2_python):
                self.logger.debug(f"Using MSYS2 Python: {msys2_python}")
                self.use_msys2_python = True
                return msys2_python
            else:
                self.logger.debug("MSYS2 Python not found")
        
        # Try different Python commands in order of preference
        python_commands = ['python3', 'python', 'py']
        self.logger.debug(f"Trying Python commands: {python_commands}")
        
        for cmd in python_commands:
            self.logger.debug(f"Testing command: {cmd}")
            if shutil.which(cmd):
                try:
                    # Test if it actually works and is Python 3+
                    result = subprocess.run([cmd, '--version'], 
                                          capture_output=True, text=True, timeout=5)
                    self.logger.debug(f"{cmd} version check: returncode={result.returncode}, stdout='{result.stdout.strip()}'")
                    if result.returncode == 0 and 'Python 3' in result.stdout:
                        self.logger.debug(f"Using Python command: {cmd}")
                        return cmd
                except Exception as e:
                    self.logger.debug(f"Error testing {cmd}: {e}")
                    continue
            else:
                self.logger.debug(f"{cmd} not found in PATH")
        
        # Fallback to python3 if nothing found (will fail gracefully)
        self.logger.debug("No suitable Python found, falling back to 'python3'")
        return 'python3'
    
    def run_command(self, args: List[str], timeout: Optional[int] = None) -> Dict[str, Any]:
        """Run a command and return output"""
        try:
            # Set up environment for MSYS2 if available
            env = os.environ.copy()
            if self.msys2_path and platform.system().lower() == 'windows':
                # Add MSYS2 paths to environment
                msys2_bin = os.path.join(self.msys2_path, 'usr', 'bin')
                mingw64_bin = os.path.join(self.msys2_path, 'mingw64', 'bin')
                if 'PATH' in env:
                    env['PATH'] = f"{msys2_bin};{mingw64_bin};{env['PATH']}"
                else:
                    env['PATH'] = f"{msys2_bin};{mingw64_bin}"
            
            if args[0] == 'sync':
                # Don't add token - let sync tool read from TokenManager
                sync_args = args[1:]
                cmd = [self.python_cmd, self.sync_path_msys2] + sync_args
                self.logger.debug(f"Sync command: {cmd}")
            elif args[0] == 'term':
                # Don't add token for term command - let it read from config
                # to avoid token rotation issues between API calls
                term_args = args[1:]
                cmd = [self.python_cmd, self.term_path_msys2] + term_args
                self.logger.debug(f"Term command: {cmd}")
            elif args[0] == 'plugin':
                # Don't add token - let plugin tool read from TokenManager
                plugin_args = args[1:]
                cmd = [self.python_cmd, self.plugin_path_msys2] + plugin_args
                self.logger.debug(f"Plugin command: {cmd}")
            else:
                cmd = [self.wrapper_path] + args
                self.logger.debug(f"Wrapper command: {cmd}")
            
            self.logger.debug(f"Executing command in directory: {self.cli_dir}")
            self.logger.debug(f"Environment PATH includes: {env.get('PATH', 'Not set')[:200]}...")
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, cwd=self.cli_dir, env=env)
            
            self.logger.debug(f"Command completed with return code: {result.returncode}")
            if result.stdout:
                self.logger.debug(f"STDOUT: {result.stdout[:500]}...")
            if result.stderr:
                self.logger.debug(f"STDERR: {result.stderr[:500]}...")
            
            return {
                'success': result.returncode == 0,
                'output': result.stdout,
                'error': result.stderr,
                'returncode': result.returncode
            }
        except subprocess.TimeoutExpired:
            self.logger.error(f"Command timed out: {cmd}")
            return {'success': False, 'output': '', 'error': 'Command timed out', 'returncode': -1}
        except Exception as e:
            self.logger.error(f"Error executing command: {cmd}")
            self.logger.error(f"Exception: {e}")
            import traceback
            traceback.print_exc()
            return {'success': False, 'output': '', 'error': str(e), 'returncode': -1}
    
    def run_cli_command(self, args: List[str], timeout: Optional[int] = None) -> Dict[str, Any]:
        """Run rediacc-cli command and parse JSON output if applicable"""
        try:
            # Don't pass token via command line - let rediacc-cli read it from TokenManager
            # This avoids issues with token rotation and ensures fresh tokens are always used
            
            cli_cmd = [self.python_cmd, self.cli_path_msys2] + args
            self.logger.debug(f"Executing CLI command: {cli_cmd}")
            self.logger.debug(f"Working directory: {self.cli_dir}")
            
            result = subprocess.run(cli_cmd, capture_output=True, text=True, timeout=timeout, cwd=self.cli_dir)
            
            self.logger.debug(f"CLI command completed with return code: {result.returncode}")
            if result.stdout:
                self.logger.debug(f"CLI STDOUT: {result.stdout[:500]}...")
            if result.stderr:
                self.logger.debug(f"CLI STDERR: {result.stderr[:500]}...")
            output = result.stdout.strip()
            
            if '--output' in args and 'json' in args:
                try:
                    data = json.loads(output) if output else {}
                    
                    # Token rotation is already handled by rediacc-cli itself
                    # No need to handle it here as it would cause duplicate saves
                    
                    # Extract data from tables format
                    response_data = data.get('data')
                    if not response_data and data.get('tables'):
                        for table in data.get('tables', []):
                            table_data = table.get('data', [])
                            if table_data and not any('nextRequestCredential' in row for row in table_data):
                                response_data = table_data
                                break
                    
                    return {
                        'success': result.returncode == 0 and data.get('success', False),
                        'data': response_data,
                        'error': data.get('error', result.stderr),
                        'raw_output': output
                    }
                except json.JSONDecodeError:
                    pass
            
            return {
                'success': result.returncode == 0,
                'output': output,
                'error': result.stderr,
                'returncode': result.returncode
            }
        except Exception as e:
            self.logger.error(f"Error executing CLI command: {[self.python_cmd, self.cli_path_msys2] + args}")
            self.logger.error(f"Exception: {e}")
            import traceback
            traceback.print_exc()
            return {'success': False, 'output': '', 'error': str(e), 'returncode': -1}