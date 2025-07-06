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
        # Get the CLI directory
        self.cli_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.cli_path = os.path.join(self.cli_dir, 'cli', 'rediacc-cli')
        self.sync_path = os.path.join(self.cli_dir, 'cli', 'rediacc-cli-sync')
        self.term_path = os.path.join(self.cli_dir, 'cli', 'rediacc-cli-term')
        
        # Wrapper script path
        self.wrapper_path = os.path.join(os.path.dirname(self.cli_dir), 'rediacc')
    
    def run_command(self, args: List[str], timeout: Optional[int] = None) -> Dict[str, Any]:
        """Run a command and return output"""
        try:
            # Determine which tool to use
            if args[0] == 'sync':
                cmd = [self.sync_path] + args[1:]
            elif args[0] == 'term':
                cmd = [self.term_path] + args[1:]
            else:
                # Use wrapper for other commands
                cmd = [self.wrapper_path] + args
            
            # Run command
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=self.cli_dir
            )
            
            return {
                'success': result.returncode == 0,
                'output': result.stdout,
                'error': result.stderr,
                'returncode': result.returncode
            }
            
        except subprocess.TimeoutExpired:
            return {
                'success': False,
                'output': '',
                'error': 'Command timed out',
                'returncode': -1
            }
        except Exception as e:
            return {
                'success': False,
                'output': '',
                'error': str(e),
                'returncode': -1
            }
    
    def run_cli_command(self, args: List[str], timeout: Optional[int] = None) -> Dict[str, Any]:
        """Run rediacc-cli command and parse JSON output if applicable"""
        try:
            cmd = ['python3', self.cli_path] + args
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=self.cli_dir
            )
            
            output = result.stdout.strip()
            
            # Try to parse JSON output
            if '--output' in args and 'json' in args:
                try:
                    data = json.loads(output) if output else {}
                    return {
                        'success': result.returncode == 0 and data.get('success', False),
                        'data': data.get('data'),
                        'error': data.get('error', result.stderr),
                        'raw_output': output
                    }
                except json.JSONDecodeError:
                    # Not JSON, return as-is
                    pass
            
            return {
                'success': result.returncode == 0,
                'output': output,
                'error': result.stderr,
                'returncode': result.returncode
            }
            
        except Exception as e:
            return {
                'success': False,
                'output': '',
                'error': str(e),
                'returncode': -1
            }