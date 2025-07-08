#!/usr/bin/env python3
"""
Subprocess runner for executing CLI commands from GUI
"""

import subprocess
import json
import os
import sys
from typing import Dict, List, Any, Optional


class SubprocessRunner:
    """Runs CLI commands and captures output"""
    
    def __init__(self):
        self.cli_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.cli_path = os.path.join(self.cli_dir, 'cli', 'rediacc-cli')
        self.sync_path = os.path.join(self.cli_dir, 'cli', 'rediacc-cli-sync')
        self.term_path = os.path.join(self.cli_dir, 'cli', 'rediacc-cli-term')
        self.wrapper_path = os.path.join(os.path.dirname(self.cli_dir), 'rediacc')
    
    def run_command(self, args: List[str], timeout: Optional[int] = None) -> Dict[str, Any]:
        """Run a command and return output"""
        try:
            if args[0] == 'sync':
                # Don't add token - let sync tool read from TokenManager
                sync_args = args[1:]
                cmd = [self.sync_path] + sync_args
            elif args[0] == 'term':
                # Don't add token for term command - let it read from config
                # to avoid token rotation issues between API calls
                term_args = args[1:]
                cmd = [self.term_path] + term_args
            else:
                cmd = [self.wrapper_path] + args
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, cwd=self.cli_dir)
            
            return {
                'success': result.returncode == 0,
                'output': result.stdout,
                'error': result.stderr,
                'returncode': result.returncode
            }
        except subprocess.TimeoutExpired:
            return {'success': False, 'output': '', 'error': 'Command timed out', 'returncode': -1}
        except Exception as e:
            return {'success': False, 'output': '', 'error': str(e), 'returncode': -1}
    
    def run_cli_command(self, args: List[str], timeout: Optional[int] = None) -> Dict[str, Any]:
        """Run rediacc-cli command and parse JSON output if applicable"""
        try:
            # Don't pass token via command line - let rediacc-cli read it from TokenManager
            # This avoids issues with token rotation and ensures fresh tokens are always used
            
            result = subprocess.run(['python3', self.cli_path] + args, 
                                  capture_output=True, text=True, timeout=timeout, cwd=self.cli_dir)
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
            return {'success': False, 'output': '', 'error': str(e), 'returncode': -1}