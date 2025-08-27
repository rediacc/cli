#!/usr/bin/env python3
"""
YAML-based test runner for Rediacc CLI
Simple and smart test execution with JSON output validation
"""
import argparse
import json
import os
import re
import subprocess
import sys
import time
import yaml
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional, Union

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))
sys.path.insert(0, str(Path(__file__).parent))  # For totp_helper

# Import TOTP and password helpers
try:
    from totp_helper import generate_totp_code, hash_password
    TOTP_AVAILABLE = True
    PASSWORD_HASH_AVAILABLE = True
except ImportError:
    TOTP_AVAILABLE = False
    PASSWORD_HASH_AVAILABLE = False
    print("Warning: TOTP helper not available, TOTP functions will return dummy codes")

# Load environment variables from parent .env file
env_file = Path(__file__).parent.parent.parent / '.env'
if env_file.exists():
    with open(env_file) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                # Remove quotes if present
                value = value.strip('"').strip("'")
                os.environ[key] = value

# ANSI color codes
COLORS = {
    'GREEN': '\033[92m',
    'RED': '\033[91m',
    'YELLOW': '\033[93m',
    'BLUE': '\033[94m',
    'BOLD': '\033[1m',
    'RESET': '\033[0m'
}

def colorize(text: str, color: str) -> str:
    """Add color to text for terminal output"""
    return f"{COLORS.get(color, '')}{text}{COLORS['RESET']}" if sys.stdout.isatty() else text

class TestRunner:
    def __init__(self, config_file: str = None, output_dir: str = None, stop_on_failure: bool = False):
        self.config = self._load_config(config_file)
        self.cli_config = self._load_cli_config()
        self.timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        self.test_id = f"test_{self.timestamp}"
        self.output_dir = Path(output_dir or "test_results")
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.all_test_results = []  # Collect all test results for display
        self.stop_on_failure = stop_on_failure
        
        # Clean up old test results - keep only last 10
        self._cleanup_old_results()
        self.results = []
        self.tested_commands = set()
        self.tested_endpoints = set()
        self.chain_context = {}  # Context that persists across test files
        self.current_test_dir = None  # Will be set when running test file
        self.context = {
            'env': dict(os.environ),
            'TIMESTAMP': self.timestamp,
            'TEST_ID': self.test_id,
            'RANDOM': str(int(time.time() * 1000) % 100000),
            'tests': [],
            'chain': self.chain_context  # Access to chain context
        }
    
    def _cleanup_old_results(self):
        """Clean up all JSON files in test results directory"""
        # Delete all JSON files in the output directory
        if self.output_dir.exists():
            for json_file in self.output_dir.glob('*.json'):
                try:
                    json_file.unlink()
                except Exception as e:
                    print(f"Warning: Failed to delete {json_file}: {e}")
            print(f"Cleaned up test results directory: {self.output_dir}")
    
    def _load_config(self, config_file: str) -> dict:
        """Load test configuration"""
        if not config_file:
            config_file = Path(__file__).parent / 'yaml' / 'config.yaml'
        
        if isinstance(config_file, str):
            config_file = Path(config_file)
            
        if config_file.exists():
            with open(config_file, 'r') as f:
                return yaml.safe_load(f) or {}
        return {}
    
    def _load_cli_config(self) -> dict:
        """Load CLI configuration with command endpoints"""
        cli_config_file = Path(__file__).parent.parent / 'src' / 'config' / 'cli-config.json'
        
        if cli_config_file.exists():
            with open(cli_config_file, 'r') as f:
                return json.load(f) or {}
        return {}
    
    def _resolve_variables(self, value: Any) -> Any:
        """Resolve variables in strings"""
        if isinstance(value, str):
            # Find all variables in format ${var}
            pattern = r'\$\{([^}]+)\}'
            
            def replace_var(match):
                var_path = match.group(1)
                
                # Check for function calls like totp(secret)
                func_match = re.match(r'(\w+)\((.*)\)', var_path)
                if func_match:
                    func_name = func_match.group(1)
                    func_args = func_match.group(2)
                    
                    # Handle TOTP function
                    if func_name == 'totp' and TOTP_AVAILABLE:
                        # Resolve the argument (could be a variable)
                        resolved_arg = self._resolve_variables(f'${{{func_args}}}')
                        try:
                            return generate_totp_code(resolved_arg)
                        except Exception as e:
                            print(f"Warning: Failed to generate TOTP code: {e}")
                            return "000000"  # Return dummy code on error
                    # Handle password hash function
                    elif func_name == 'hash' and PASSWORD_HASH_AVAILABLE:
                        # Don't double-resolve, func_args is already the raw password
                        try:
                            return hash_password(func_args)
                        except Exception as e:
                            print(f"Warning: Failed to hash password: {e}")
                            return "0x" + "0" * 64  # Return dummy hash on error
                    else:
                        # Unknown function, return as-is
                        return match.group(0)
                
                parts = var_path.split('.')
                
                # Check if it's a config reference
                if parts[0] == 'config':
                    result = self.config
                    for part in parts[1:]:
                        if isinstance(result, dict):
                            result = result.get(part, match.group(0))
                        else:
                            return match.group(0)
                    # Recursively resolve variables in config values
                    if isinstance(result, str):
                        return self._resolve_variables(result)
                    return str(result)
                
                # Navigate through context
                result = self.context
                for i, part in enumerate(parts):
                    if isinstance(result, dict):
                        prev_result = result
                        result = result.get(part, None)
                        if result is None:
                            # Debug when resolving chain exports
                            if var_path.startswith("result.data.result"):
                                print(f"    DEBUG resolve path: Failed at part '{part}', path so far: {'.'.join(parts[:i+1])}")
                                print(f"    DEBUG resolve path: Available keys: {list(prev_result.keys())}")
                            return match.group(0)
                    elif isinstance(result, list):
                        try:
                            idx = int(part)
                            result = result[idx] if idx < len(result) else None
                            if result is None:
                                return match.group(0)
                        except (ValueError, IndexError):
                            return match.group(0)
                    else:
                        return match.group(0)
                
                # If we get None, return the original variable
                if result is None:
                    return match.group(0)
                
                return str(result)
            
            return re.sub(pattern, replace_var, value)
        elif isinstance(value, dict):
            return {k: self._resolve_variables(v) for k, v in value.items()}
        elif isinstance(value, list):
            return [self._resolve_variables(v) for v in value]
        return value
    
    def _build_command(self, test_spec: dict, executor: str) -> List[str]:
        """Build command line from test specification"""
        # Get executor path
        cli_dir = Path(__file__).parent.parent / 'src' / 'cli'
        executor_path = cli_dir / executor
        
        # Start with python and executor
        cmd = [sys.executable, str(executor_path)]
        
        # Add command - handle both string and array format
        if 'command' in test_spec:
            command = self._resolve_variables(test_spec['command'])
            if isinstance(command, list):
                # Array format - resolve each element
                cmd.extend([str(c) for c in command])
            else:
                # String format for backward compatibility
                cmd.extend(command.split())
        
        # Always use json-full for testing to capture all data
        cmd.extend(['--output', 'json-full'])
        
        # Add arguments
        args = self._resolve_variables(test_spec.get('args', {}))
        for key, value in args.items():
            # Convert underscores to dashes for CLI args
            cli_key = key.replace('_', '-')
            
            # Handle boolean flags
            if isinstance(value, bool):
                cmd.append(f'--{cli_key}')
                cmd.append(str(value).lower())
            # Handle lists
            elif isinstance(value, list):
                cmd.append(f'--{cli_key}')
                cmd.extend([str(v) for v in value])
            # Handle other values
            elif value is not None:
                # Keep numeric types as-is for proper type handling
                if isinstance(value, (int, float)):
                    cmd.extend([f'--{cli_key}', str(value)])
                else:
                    cmd.extend([f'--{cli_key}', str(value)])
        
        return cmd
    
    def _execute_command(self, cmd: List[str], timeout: int = 30, stdin_data: str = None) -> dict:
        """Execute command and return result"""
        try:
            # Execute command
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
                input=stdin_data
            )
            
            # Try to parse JSON output
            try:
                output = json.loads(result.stdout)
                return {
                    'success': result.returncode == 0,
                    'output': output,
                    'stderr': result.stderr,
                    'returncode': result.returncode
                }
            except json.JSONDecodeError:
                # If not JSON, return raw output
                return {
                    'success': result.returncode == 0,
                    'output': result.stdout,
                    'stderr': result.stderr,
                    'returncode': result.returncode,
                    'raw': True
                }
        
        except subprocess.TimeoutExpired:
            return {
                'success': False,
                'error': f'Command timed out after {timeout} seconds',
                'timeout': True
            }
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    def _validate_expectation(self, actual: Any, expected: Any) -> List[str]:
        """Validate actual output against expected values"""
        errors = []
        
        # We only validate success field
        if isinstance(expected, dict) and 'success' in expected:
            expected_success = expected['success']
            
            # Check if actual has success field
            if not isinstance(actual, dict):
                errors.append(f"Expected JSON response but got {type(actual).__name__}")
            elif 'success' not in actual:
                errors.append("Missing 'success' field in response")
            elif actual['success'] != expected_success:
                errors.append(f"Expected success: {expected_success} but got success: {actual.get('success')}")
        
        return errors
    
    def _generate_output_filename(self, test_file_name: str, parent_test_name: str, step_name: str) -> str:
        """Generate automatic output filename based on test hierarchy"""
        # Build filename: basic.00001_company_setup.COMPANY_SETUP_TEST.create_new_company.json
        filename_parts = []
        
        # Only include directory if it's not empty (i.e., not in yaml root)
        if self.current_test_dir:
            filename_parts.append(self.current_test_dir)
            
        filename_parts.extend([
            test_file_name,           # Test file name (e.g., "00001_company_setup")
            parent_test_name,         # Parent test name (e.g., "COMPANY_SETUP_TEST")
            step_name                 # Step name (e.g., "create_new_company")
        ])
        
        filename = '.'.join(filename_parts) + '.json'
        return filename
    
    def _generate_consolidated_filename(self, test_file_name: str, parent_test_name: str) -> str:
        """Generate filename for consolidated test results"""
        # Build filename: basic.00001_company_setup.COMPANY_SETUP_TEST.json
        filename_parts = []
        
        # Only include directory if it's not empty (i.e., not in yaml root)
        if self.current_test_dir:
            filename_parts.append(self.current_test_dir)
            
        filename_parts.extend([
            test_file_name,           # Test file name (e.g., "00001_company_setup")
            parent_test_name          # Parent test name (e.g., "COMPANY_SETUP_TEST")
        ])
        
        filename = '.'.join(filename_parts) + '.json'
        return filename
    
    def _save_output(self, test_name: str, filename: str, data: Any, command_info: dict = None):
        """Save test output to file with command metadata"""
        output_file = self.output_dir / filename
        
        # Create wrapper with metadata
        output_data = {
            'test_metadata': {
                'test_name': test_name,
                'timestamp': datetime.now().isoformat(),
                'test_id': self.test_id
            },
            'command_executed': command_info or {},
            'result': data
        }
        
        with open(output_file, 'w') as f:
            json.dump(output_data, f, indent=2)
    
    def run_test_file(self, test_file: str, base_files: List[Path] = None) -> bool:
        """Run a single test file"""
        # Show progress
        test_file_path = Path(test_file)
        print(f"Running: {test_file_path.name}", end='', flush=True)
        
        # Start timing for entire test file
        file_start_time = time.time()
        
        # Load test file and merge with base files if provided
        test_spec = self._load_and_merge_test_files(test_file, base_files)
        
        # Debug: show if merging happened
        # (suppressed for cleaner output)
        
        # Extract configuration
        name = test_spec.get('name', 'Unnamed Test')
        description = test_spec.get('description', '')
        executor = test_spec.get('executor', 'commands/cli_main.py')
        
        # (test name and description suppressed for cleaner output)
        
        # Extract test file info for output naming
        test_file_path = Path(test_file)
        test_file_base = test_file_path.stem  # e.g., "00001_company_setup"
        test_dir = test_file_path.parent.name  # e.g., "basic"
        
        # Store test directory in context for filename generation
        # If test is directly in yaml folder, don't include directory in filename
        if test_dir == 'yaml':
            self.current_test_dir = ''
        else:
            self.current_test_dir = test_dir
        
        # Initialize collection for this test file
        test_file_results = {
            'test_metadata': {
                'test_file': str(test_file_path),
                'test_name': name,
                'description': description,
                'timestamp': datetime.now().isoformat(),
                'test_id': self.test_id
            },
            'setup_results': [],
            'test_results': [],
            'chain_exports': {}
        }
        
        # Run setup if present
        if 'setup' in test_spec:
            print()  # Add newline after filename when we have setup
            print(colorize('Running setup...', 'YELLOW'))
            for setup_step in test_spec['setup']:
                result = self._run_test_step(setup_step, executor, is_setup=True, 
                                  test_file_name=test_file_base, 
                                  parent_test_name=name,
                                  collect_results=True)
                test_file_results['setup_results'].append(result)
        
        # Clear test context for this file
        self.context['tests'] = []
        
        # Run tests
        test_results = []
        for i, test in enumerate(test_spec.get('tests', [])):
            # Process the test - but first handle any chain exports from THIS test
            # We need to check before running so we can update chain context
            
            result = self._run_test_step(test, executor, test_index=i,
                                       test_file_name=test_file_base,
                                       parent_test_name=name,
                                       collect_results=True)
            test_results.append(result)
            test_file_results['test_results'].append(result)
            
            # Stop on failure if requested
            if not result['success'] and self.stop_on_failure:
                print(f"\n{colorize('STOPPING: Test failed, halting execution', 'RED')}")
                break
            
            # Store result in context for variable resolution
            if i >= len(self.context['tests']):
                self.context['tests'].append({})
            
            # Extract output from the result.result.output structure
            if result['success'] and 'result' in result and 'output' in result['result']:
                self.context['tests'][i] = result['result']['output']
                
                # Handle chain exports for individual tests IMMEDIATELY
                if 'chain_export' in test:
                    # For chain exports, we need a special handling of the result
                    # The test output structure is result['result']['output'] which contains
                    # {success, data: {endpoint, parameters, result: [...]}, message}
                    output_data = result['result']['output']
                    
                    # Resolve each export variable
                    for key, value in test['chain_export'].items():
                        # Special handling for common patterns
                        if value == "${result.data.result[0].taskId}":
                            # Direct extraction for this common case
                            try:
                                resolved_value = output_data['data']['result'][0]['taskId']
                            except (KeyError, IndexError, TypeError):
                                resolved_value = value  # Keep original if extraction fails
                        elif value == "${result.data.result[0].secret}":
                            # Direct extraction for TFA secret
                            try:
                                resolved_value = output_data['data']['result'][0]['secret']
                            except (KeyError, IndexError, TypeError):
                                resolved_value = value  # Keep original if extraction fails
                        else:
                            # For other patterns, create a context with just the output data
                            temp_context = dict(self.context)
                            # Add the output data directly under various keys for flexibility
                            temp_context['result'] = output_data
                            temp_context['output'] = output_data
                            temp_context['data'] = output_data.get('data', {})
                            
                            # Try to resolve
                            old_context = self.context
                            self.context = temp_context
                            resolved_value = self._resolve_variables(value)
                            self.context = old_context
                        
                        # Update chain context immediately
                        self.chain_context[key] = resolved_value
                        self.context['chain'] = self.chain_context
                        
                        # Always show chain exports for now
                        print(f"  Chain export: {key} = {resolved_value}")
        
        # Handle chain exports
        if 'chain_export' in test_spec:
            exports = self._resolve_variables(test_spec['chain_export'])
            self.chain_context.update(exports)
            test_file_results['chain_exports'] = exports
            # Chain exports saved but not displayed
        
        # Calculate total execution time
        total_execution_time = time.time() - file_start_time
        test_file_results['test_metadata']['total_execution_time_seconds'] = round(total_execution_time, 3)
        
        # Save consolidated results for this test file
        consolidated_filename = self._generate_consolidated_filename(test_file_base, name)
        consolidated_path = self.output_dir / consolidated_filename
        with open(consolidated_path, 'w') as f:
            json.dump(test_file_results, f, indent=2)
        # Results saved silently
        
        # Collect results for later display
        for result in test_results:
            self.all_test_results.append({
                'suite_name': name,
                'test_name': result['test_name'],
                'success': result['success'],
                'execution_time_seconds': result['execution_time_seconds'],
                'command': result.get('command_executed', {}).get('command', [])
            })
            
        # Summary
        passed = sum(1 for r in test_results if r['success'])
        failed = len(test_results) - passed
        
        # Complete the progress line
        if failed == 0:
            print(f" {colorize('✓', 'GREEN')} ({passed} tests, {total_execution_time:.1f}s)")
        else:
            print(f" {colorize('✗', 'RED')} ({passed}/{len(test_results)} passed, {total_execution_time:.1f}s)")
        
        return failed == 0
    
    def _run_test_step(self, step: dict, executor: str, test_index: int = -1, is_setup: bool = False, test_file_name: str = None, parent_test_name: str = None, collect_results: bool = False) -> dict:
        """Run a single test step"""
        step_name = step.get('name', f'Step {test_index + 1}')
        
        # Show progress dot
        print('.', end='', flush=True)
        
        # Build and execute command
        cmd = self._build_command(step, executor)
        command_display = ' '.join(cmd[2:])  # Skip python and script path
        
        # Command display suppressed for cleaner output
        
        # Store command info for output
        command_info = {
            'command': step.get('command', []),
            'args': self._resolve_variables(step.get('args', {})),
            'full_command': command_display,
            'executor': executor
        }
        
        # Track tested commands for coverage
        if 'command' in step:
            command = step['command']
            command_parts = []
            
            # Handle both array and string format
            if isinstance(command, list):
                command_parts = command
            else:
                command_parts = command.split()
            
            if len(command_parts) >= 1:
                # Extract main command and subcommand (e.g., "create company")
                main_cmd = command_parts[0]
                sub_cmd = None
                
                # Check if this is a dynamic endpoint (starts with uppercase letter)
                if main_cmd and main_cmd[0].isupper():
                    # This is a direct endpoint call
                    self.tested_endpoints.add(main_cmd)
                    # Also track it as a dynamic command
                    self.tested_commands.add(f"dynamic.{main_cmd}")
                # For single commands like "login", "logout"
                elif len(command_parts) == 1:
                    command_key = main_cmd
                    # Check if it's a top-level command in CMD_CONFIG
                    cmd_config = self.cli_config.get('CMD_CONFIG', {})
                    if main_cmd in cmd_config:
                        endpoint = cmd_config[main_cmd].get('endpoint')
                        if endpoint:
                            self.tested_endpoints.add(endpoint)
                            self.tested_commands.add(command_key)
                # For commands with subcommands
                elif len(command_parts) >= 2 and not command_parts[1].startswith('-'):
                    sub_cmd = command_parts[1]
                    command_key = f"{main_cmd}.{sub_cmd}"
                    self.tested_commands.add(command_key)
                    
                    # Track endpoint from CLI config
                    cmd_config = self.cli_config.get('CMD_CONFIG', {})
                    if main_cmd in cmd_config and sub_cmd in cmd_config[main_cmd]:
                        endpoint = cmd_config[main_cmd][sub_cmd].get('endpoint')
                        if endpoint:
                            self.tested_endpoints.add(endpoint)
        
        timeout = step.get('timeout', self.config.get('default_timeout', 30))
        
        # Get stdin data if provided
        stdin_data = step.get('stdin')
        if stdin_data:
            stdin_data = self._resolve_variables(stdin_data)
        
        # Capture start time
        start_time = time.time()
        result = self._execute_command(cmd, timeout, stdin_data)
        # Calculate execution time
        execution_time = time.time() - start_time
        
        # Build comprehensive result
        test_result = {
            'test_name': step_name,
            'timestamp': datetime.now().isoformat(),
            'execution_time_seconds': round(execution_time, 3),
            'command_executed': command_info,
            'result': result,
            'success': True,
            'errors': []
        }
        
        # Validate expectations
        if 'expect' in step:
            expected = self._resolve_variables(step['expect'])
            
            # For raw output (non-JSON), we can only check if command succeeded
            if result.get('raw'):
                output = {'success': result['success']}
            else:
                output = result.get('output', {})
            
            # Validate
            errors = self._validate_expectation(output, expected)
            
            if errors:
                # Validation errors saved but not displayed
                
                test_result['success'] = False
                test_result['errors'] = errors
                
                # Only save individual file when not collecting results
                if not collect_results:
                    auto_filename = self._generate_output_filename(test_file_name, parent_test_name, step_name)
                    self._save_output(step_name, auto_filename, result, command_info)
                    print(f"  {colorize('Output saved:', 'YELLOW')} {auto_filename}")
                
                return test_result
            else:
                # Test passed (expected result matches actual)
                pass
        else:
            # No expectations defined, check if command succeeded
            if result['success']:
                # Test passed
                pass
            else:
                error_msg = result.get('error') or result.get('stderr', 'Unknown error')
                # Test failed
                
                test_result['success'] = False
                test_result['errors'] = [error_msg]
                
                # Only save individual file when not collecting results
                if not collect_results:
                    auto_filename = self._generate_output_filename(test_file_name, parent_test_name, step_name)
                    self._save_output(step_name, auto_filename, result, command_info)
                    print(f"  {colorize('Output saved:', 'YELLOW')} {auto_filename}")
                
                return test_result
        
        # Only save individual file when not collecting results
        if not collect_results:
            auto_filename = self._generate_output_filename(test_file_name, parent_test_name, step_name)
            self._save_output(step_name, auto_filename, result, command_info)
            print(f"  {colorize('Output saved:', 'YELLOW')} {auto_filename}")
        
        return test_result
    
    def _print_tabular_results(self, test_name: str, test_results: List[dict]):
        """Print test results in tabular format"""
        if not test_results:
            return
            
        # Calculate column widths
        name_width = max(len(r['test_name']) for r in test_results)
        name_width = max(name_width, 20)  # Minimum width
        
        # Print header
        print(f"\n{colorize(test_name, 'BOLD')}")
        print("-" * (name_width + 45))
        print(f"{'Test Name':<{name_width}} | {'Status':^10} | {'Time':^8} | {'Endpoint'}")
        print("-" * (name_width + 45))
        
        # Print results
        for result in test_results:
            name = result['test_name']
            if len(name) > name_width:
                name = name[:name_width-3] + '...'
            
            status = 'PASS' if result['success'] else 'FAIL'
            status_color = 'GREEN' if result['success'] else 'RED'
            time_str = f"{result['execution_time_seconds']:.3f}s"
            
            # Extract endpoint/command
            command = result.get('command_executed', {}).get('command', [])
            if isinstance(command, list) and command:
                endpoint = command[0]
            else:
                endpoint = 'N/A'
                
            status_display = colorize(f"{status:^10}", status_color)
            print(f"{name:<{name_width}} | {status_display} | {time_str:^8} | {endpoint}")
        
        print("-" * (name_width + 45))
    
    def _print_consolidated_table(self):
        """Print all test results in a single consolidated table"""
        if not self.all_test_results:
            return
            
        # Calculate column widths
        suite_width = max(len(r['suite_name']) for r in self.all_test_results)
        suite_width = max(suite_width, 15)  # Minimum width
        
        test_width = max(len(r['test_name']) for r in self.all_test_results)
        test_width = max(test_width, 25)  # Minimum width
        
        total_width = suite_width + test_width + 45
        
        # Print header
        print(f"\n{colorize('Test Results Summary', 'BOLD')}")
        print("=" * total_width)
        print(f"{'Test Suite':<{suite_width}} | {'Test Name':<{test_width}} | {'Status':^10} | {'Time':^8} | {'Endpoint'}")
        print("=" * total_width)
        
        # Print results grouped by suite
        current_suite = None
        for result in self.all_test_results:
            suite = result['suite_name']
            if suite != current_suite:
                if current_suite is not None:
                    print("-" * total_width)
                current_suite = suite
            
            # Truncate names if too long
            suite_display = suite if len(suite) <= suite_width else suite[:suite_width-3] + '...'
            test_display = result['test_name'] if len(result['test_name']) <= test_width else result['test_name'][:test_width-3] + '...'
            
            status = 'PASS' if result['success'] else 'FAIL'
            status_color = 'GREEN' if result['success'] else 'RED'
            time_str = f"{result['execution_time_seconds']:.3f}s"
            
            # Extract endpoint/command
            command = result['command']
            if isinstance(command, list) and command:
                endpoint = command[0]
            else:
                endpoint = 'N/A'
                
            status_display = colorize(f"{status:^10}", status_color)
            
            # Only show suite name on first test of each suite
            index = self.all_test_results.index(result)
            if index > 0 and self.all_test_results[index - 1]['suite_name'] == suite:
                suite_display = " " * suite_width
            
            print(f"{suite_display:<{suite_width}} | {test_display:<{test_width}} | {status_display} | {time_str:^8} | {endpoint}")
        
        print("=" * total_width)
        
        # Overall summary
        total_tests = len(self.all_test_results)
        passed_tests = sum(1 for r in self.all_test_results if r['success'])
        failed_tests = total_tests - passed_tests
        total_time = sum(r['execution_time_seconds'] for r in self.all_test_results)
        
        print(f"\nTotal: {total_tests} tests, {colorize(f'{passed_tests} passed', 'GREEN')}, ", end="")
        if failed_tests > 0:
            print(f"{colorize(f'{failed_tests} failed', 'RED')}, ", end="")
        print(f"Time: {total_time:.3f}s")
        
    def generate_coverage_report(self):
        """Generate coverage report showing tested commands and endpoints"""
        print(f"\n{colorize('Test Coverage Report:', 'BOLD')}")
        print(f"{colorize('=' * 60, 'BOLD')}")
        
        # Get all available commands from CLI config
        cmd_config = self.cli_config.get('CMD_CONFIG', {})
        all_commands = set()
        all_endpoints = set()
        
        for main_cmd, sub_cmds in cmd_config.items():
            if isinstance(sub_cmds, dict):
                for sub_cmd, config in sub_cmds.items():
                    if isinstance(config, dict):
                        all_commands.add(f"{main_cmd}.{sub_cmd}")
                        endpoint = config.get('endpoint')
                        if endpoint:
                            all_endpoints.add(endpoint)
        
        # Calculate coverage
        commands_tested = len(self.tested_commands)
        commands_total = len(all_commands)
        commands_coverage = (commands_tested / commands_total * 100) if commands_total > 0 else 0
        
        endpoints_tested = len(self.tested_endpoints)
        endpoints_total = len(all_endpoints)
        endpoints_coverage = (endpoints_tested / endpoints_total * 100) if endpoints_total > 0 else 0
        
        # Print summary
        print(f"\n{colorize('Commands:', 'BLUE')}")
        print(f"  Tested: {commands_tested}/{commands_total} ({commands_coverage:.1f}%)")
        print(f"  Commands tested: {', '.join(sorted(self.tested_commands))}")
        
        print(f"\n{colorize('Stored Procedures:', 'BLUE')}")
        print(f"  Tested: {endpoints_tested}/{endpoints_total} ({endpoints_coverage:.1f}%)")
        print(f"  Endpoints tested: {', '.join(sorted(self.tested_endpoints))}")
        
        # Show untested commands
        untested_commands = all_commands - self.tested_commands
        
        # Show untested endpoints
        untested_endpoints = all_endpoints - self.tested_endpoints
        if untested_endpoints:
            print(f"\n{colorize('Untested Endpoints/Stored Procedures:', 'YELLOW')}")
            for endpoint in sorted(untested_endpoints):
                print(f"  - {endpoint}")
        
        # Save coverage report
        coverage_file = self.output_dir / 'coverage_report.json'
        with open(coverage_file, 'w') as f:
            json.dump({
                'test_id': self.test_id,
                'commands': {
                    'total': commands_total,
                    'tested': commands_tested,
                    'coverage_percentage': commands_coverage,
                    'tested_list': sorted(self.tested_commands),
                    'untested_list': sorted(untested_commands)
                },
                'endpoints': {
                    'total': endpoints_total,
                    'tested': endpoints_tested,
                    'coverage_percentage': endpoints_coverage,
                    'tested_list': sorted(self.tested_endpoints),
                    'untested_list': sorted(untested_endpoints)
                }
            }, f, indent=2)
        
        print(f"\n{colorize('Coverage report saved to:', 'GREEN')} {coverage_file}")
    
    def _load_and_merge_test_files(self, test_file: Path, base_files: List[Path] = None) -> dict:
        """Load and merge test files with inheritance support"""
        # Start with empty spec
        merged_spec = {}
        
        # Load and merge base files in order (lowest to highest tier)
        if base_files:
            for base_file in base_files:
                with open(base_file, 'r') as f:
                    base_spec = yaml.safe_load(f)
                    merged_spec = self._deep_merge(merged_spec, base_spec)
        
        # Load and merge the main file
        with open(test_file, 'r') as f:
            main_spec = yaml.safe_load(f)
            merged_spec = self._deep_merge(merged_spec, main_spec)
        
        return merged_spec
    
    def _deep_merge(self, base: dict, override: dict) -> dict:
        """Deep merge two dictionaries, with override taking precedence"""
        result = base.copy()
        
        for key, value in override.items():
            if key in result:
                if isinstance(result[key], dict) and isinstance(value, dict):
                    # Recursively merge dictionaries
                    result[key] = self._deep_merge(result[key], value)
                elif isinstance(result[key], list) and isinstance(value, list):
                    # For lists, we need special handling
                    if key == 'tests':
                        # For tests, merge by test name
                        result[key] = self._merge_test_lists(result[key], value)
                    else:
                        # For other lists, override completely
                        result[key] = value
                else:
                    # For other types, override
                    result[key] = value
            else:
                result[key] = value
        
        return result
    
    def _merge_test_lists(self, base_tests: list, override_tests: list) -> list:
        """Merge test lists by test name"""
        # Create a map of base tests by name
        base_map = {test.get('name'): test for test in base_tests if isinstance(test, dict)}
        
        # Process override tests
        result = []
        override_names = set()
        
        for test in override_tests:
            if isinstance(test, dict) and 'name' in test:
                test_name = test['name']
                override_names.add(test_name)
                
                if test_name in base_map:
                    # Merge with base test
                    merged_test = self._deep_merge(base_map[test_name], test)
                    result.append(merged_test)
                else:
                    # New test
                    result.append(test)
        
        # Add base tests that weren't overridden
        for test in base_tests:
            if isinstance(test, dict) and test.get('name') not in override_names:
                result.append(test)
        
        return result
    
    def _get_test_hierarchy(self, test_pattern: str) -> Dict[str, List[Path]]:
        """Organize test files by hierarchy (community, advanced, premium, elite)"""
        yaml_dir = Path(__file__).parent / 'yaml'
        hierarchy = {
            'community': [],
            'advanced': [],
            'premium': [],
            'elite': []
        }
        
        # Find all test files based on pattern
        if test_pattern:
            # Check if it's a direct file path
            test_path = Path(test_pattern)
            if test_path.exists() and test_path.is_file():
                test_files = [test_path]
            else:
                # Try as pattern within yaml directory
                test_files = list(yaml_dir.rglob(test_pattern))
        else:
            test_files = list(yaml_dir.rglob('*.yaml'))
        
        # Exclude config.yaml and organize by directory
        for test_file in test_files:
            if test_file.name == 'config.yaml':
                continue
                
            # Determine which tier this test belongs to
            parent_dir = test_file.parent.name
            if parent_dir in hierarchy:
                hierarchy[parent_dir].append(test_file)
            elif test_file.parent == yaml_dir:
                # Files directly in yaml/ are considered community
                hierarchy['community'].append(test_file)
        
        # Sort files within each tier
        for tier in hierarchy:
            hierarchy[tier].sort()
            
        return hierarchy
    
    def _determine_test_tiers(self, test_pattern: str) -> List[str]:
        """Determine which test tiers to run based on pattern"""
        # Map of tier dependencies
        tier_dependencies = {
            'community': ['community'],
            'advanced': ['community', 'advanced'],
            'premium': ['community', 'advanced', 'premium'],
            'elite': ['community', 'advanced', 'premium', 'elite']
        }
        
        if not test_pattern:
            return ['community']  # Default to community only
            
        # Check if pattern specifies a tier
        for tier in ['elite', 'premium', 'advanced', 'community']:
            if tier in test_pattern:
                return tier_dependencies[tier]
                
        # If no tier specified, run only the files matching the pattern
        return ['community', 'advanced', 'premium', 'elite']
    
    def run_all_tests(self, test_pattern: str = None) -> bool:
        """Run all test files matching pattern with hierarchical support"""
        # Determine which tiers to run first
        tiers_to_run = self._determine_test_tiers(test_pattern)
        
        # Get test hierarchy - if we're running multiple tiers due to dependencies,
        # we need to get ALL files for those tiers, not just the ones matching the pattern
        if test_pattern and len(tiers_to_run) > 1:
            # Pattern specified a tier, get all files for dependent tiers
            all_hierarchy = self._get_test_hierarchy(None)  # Get all files
            pattern_hierarchy = self._get_test_hierarchy(test_pattern)  # Get pattern-specific files
            
            # Build the hierarchy we need
            hierarchy = {}
            for tier in tiers_to_run:
                if tier in pattern_hierarchy and pattern_hierarchy[tier]:
                    # Use pattern-specific files for the target tier
                    hierarchy[tier] = pattern_hierarchy[tier]
                else:
                    # Use all files for dependent tiers
                    hierarchy[tier] = all_hierarchy.get(tier, [])
        else:
            # Normal pattern matching
            hierarchy = self._get_test_hierarchy(test_pattern)
        
        # Collect all test files to run with override logic
        # Higher tiers override lower tiers based on filename
        test_files_by_name = {}  # filename -> [(tier, filepath), ...]
        tier_priority = {'community': 0, 'advanced': 1, 'premium': 2, 'elite': 3}
        
        # Collect all files by name, keeping track of all tiers
        for tier in tiers_to_run:
            for test_file in hierarchy.get(tier, []):
                filename = test_file.name
                if filename not in test_files_by_name:
                    test_files_by_name[filename] = []
                test_files_by_name[filename].append((tier, test_file))
        
        # For each filename, determine which files to use (base + override)
        files_to_run = []  # List of (test_file, base_files) tuples
        for filename, tier_files in sorted(test_files_by_name.items()):
            # Sort by tier priority
            tier_files.sort(key=lambda x: tier_priority.get(x[0], 0))
            
            # Collect all files from lowest to highest tier for merging
            base_files = [filepath for tier, filepath in tier_files[:-1]]
            main_file = tier_files[-1][1]  # Highest priority file
            
            files_to_run.append((main_file, base_files))
        
        if not files_to_run:
            print(colorize('No test files found!', 'YELLOW'))
            yaml_dir = Path(__file__).parent / 'yaml'
            print(f"Searched in: {yaml_dir}")
            if test_pattern:
                print(f"Pattern: {test_pattern}")
            return True
        
        print(f"{colorize('Found', 'BOLD')} {len(files_to_run)} test file(s)")
        if len(tiers_to_run) > 1:
            print(f"{colorize('Running tiers:', 'BOLD')} {', '.join(tiers_to_run)}")
            
            # Show merge information
            for main_file, base_files in files_to_run:
                if base_files:
                    base_tiers = []
                    for base_file in base_files:
                        for tier in tiers_to_run:
                            if base_file in hierarchy.get(tier, []):
                                base_tiers.append(tier)
                                break
                    
                    main_tier = None
                    for tier in tiers_to_run:
                        if main_file in hierarchy.get(tier, []):
                            main_tier = tier
                            break
                    
                    if main_tier and base_tiers:
                        print(f"  {colorize('Merge:', 'YELLOW')} {main_file.name} from {main_tier} extends {', '.join(base_tiers)}")
            
            # Debug: show what's in hierarchy (disabled in tabular mode)
        
        # Run each test file with its base files
        all_passed = True
        for test_file, base_files in files_to_run:
            if not self.run_test_file(test_file, base_files):
                all_passed = False
                # Stop on failure if requested
                if self.stop_on_failure:
                    print(f"\n{colorize('STOPPING: Test file failed, halting execution', 'RED')}")
                    break
        
        # Print consolidated table
        self._print_consolidated_table()
        
        # Final summary
        print(f"\n{colorize('=' * 60, 'BOLD')}")
        print(f"{colorize('Overall Results:', 'BOLD')}")
        print(f"  Test ID: {self.test_id}")
        print(f"  Output Directory: {self.output_dir}")
        
        if all_passed:
            print(f"  {colorize('All tests PASSED!', 'GREEN')}")
        else:
            print(f"  {colorize('Some tests FAILED!', 'RED')}")
        
        # Generate coverage report
        self.generate_coverage_report()
        
        return all_passed

def main():
    parser = argparse.ArgumentParser(description='YAML-based test runner for Rediacc CLI')
    parser.add_argument('pattern', nargs='?', help='Test file pattern (e.g., "basic/*.yaml")')
    parser.add_argument('--config', help='Test configuration file')
    parser.add_argument('--output-dir', help='Output directory for test results')
    parser.add_argument('--stop-on-failure', action='store_true', help='Stop execution on first test failure')
    
    args = parser.parse_args()
    
    # Always use the fast test runner (in-memory API client)
    try:
        from run_tests_fast import FastYAMLTestRunner
        runner = FastYAMLTestRunner()
        if args.pattern:
            # Run specific test file
            results = runner.run_test_file(args.pattern)
            success = all(test['success'] for test in results.get('test_results', []))
        else:
            # Run all tests
            success = runner.run_all_tests()
        sys.exit(0 if success else 1)
    except ImportError:
        print("Error: Fast test runner not available. Please ensure run_tests_fast.py is in the tests directory.")
        sys.exit(1)

if __name__ == '__main__':
    main()