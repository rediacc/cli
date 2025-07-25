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
    def __init__(self, config_file: str = None, output_dir: str = None):
        self.config = self._load_config(config_file)
        self.cli_config = self._load_cli_config()
        self.timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        self.test_id = f"test_{self.timestamp}"
        self.output_dir = Path(output_dir or "test_results")
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
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
        cli_config_file = Path(__file__).parent.parent / 'src' / 'config' / 'rediacc-cli.json'
        
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
                for part in parts:
                    if isinstance(result, dict):
                        result = result.get(part, match.group(0))
                    elif isinstance(result, list):
                        try:
                            idx = int(part)
                            result = result[idx] if idx < len(result) else match.group(0)
                        except (ValueError, IndexError):
                            return match.group(0)
                    else:
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
                if value:
                    cmd.append(f'--{cli_key}')
            # Handle lists
            elif isinstance(value, list):
                cmd.append(f'--{cli_key}')
                cmd.extend([str(v) for v in value])
            # Handle other values
            elif value is not None:
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
        print(f"\n{colorize('Running test file:', 'BOLD')} {test_file}")
        
        # Start timing for entire test file
        file_start_time = time.time()
        
        # Load test file and merge with base files if provided
        test_spec = self._load_and_merge_test_files(test_file, base_files)
        
        # Debug: show if merging happened
        if base_files:
            print(f"  {colorize('Merged with:', 'BLUE')} {', '.join([str(bf.name) for bf in base_files])}")
        
        # Extract configuration
        name = test_spec.get('name', 'Unnamed Test')
        description = test_spec.get('description', '')
        executor = test_spec.get('executor', 'rediacc-cli.py')
        
        print(f"\n{colorize(name, 'BLUE')}")
        if description:
            print(f"{colorize('Description:', 'YELLOW')} {description}")
        print()
        
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
            result = self._run_test_step(test, executor, test_index=i,
                                       test_file_name=test_file_base,
                                       parent_test_name=name,
                                       collect_results=True)
            test_results.append(result)
            test_file_results['test_results'].append(result)
            
            # Stop on first failure
            if not result['success']:
                print(f"\n{colorize('STOPPING: Test failed, halting execution', 'RED')}")
                break
            
            # Store result in context for variable resolution
            if i >= len(self.context['tests']):
                self.context['tests'].append({})
            
            # Extract output from the result.result.output structure
            if result['success'] and 'result' in result and 'output' in result['result']:
                self.context['tests'][i] = result['result']['output']
        
        # Handle chain exports
        if 'chain_export' in test_spec:
            exports = self._resolve_variables(test_spec['chain_export'])
            self.chain_context.update(exports)
            test_file_results['chain_exports'] = exports
            print(f"\n{colorize('Chain exports:', 'BLUE')}")
            for key, value in exports.items():
                print(f"  {key}: {value}")
        
        # Calculate total execution time
        total_execution_time = time.time() - file_start_time
        test_file_results['test_metadata']['total_execution_time_seconds'] = round(total_execution_time, 3)
        
        # Save consolidated results for this test file
        consolidated_filename = self._generate_consolidated_filename(test_file_base, name)
        consolidated_path = self.output_dir / consolidated_filename
        with open(consolidated_path, 'w') as f:
            json.dump(test_file_results, f, indent=2)
        print(f"\n{colorize('Consolidated results saved:', 'GREEN')} {consolidated_filename}")
        
        # Summary
        passed = sum(1 for r in test_results if r['success'])
        failed = len(test_results) - passed
        
        print(f"\n{colorize('Summary:', 'BOLD')}")
        print(f"  {colorize(f'Passed: {passed}', 'GREEN')}")
        if failed > 0:
            print(f"  {colorize(f'Failed: {failed}', 'RED')}")
        print(f"  {colorize(f'Total time: {total_execution_time:.3f}s', 'BLUE')}")
        
        return failed == 0
    
    def _run_test_step(self, step: dict, executor: str, test_index: int = -1, is_setup: bool = False, test_file_name: str = None, parent_test_name: str = None, collect_results: bool = False) -> dict:
        """Run a single test step"""
        step_name = step.get('name', f'Step {test_index + 1}')
        
        if is_setup:
            print(f"\n{colorize('Setup:', 'BOLD')} {step_name}")
        else:
            # Just show the test name without "Test N:" prefix
            print(f"\n{colorize(step_name, 'BOLD')}")
        
        # Build and execute command
        cmd = self._build_command(step, executor)
        command_display = ' '.join(cmd[2:])  # Skip python and script path
        print(f"  {colorize('Command:', 'BLUE')} {command_display}")
        
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
                
                # For single commands like "login", "logout"
                if len(command_parts) == 1:
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
                print(f"  {colorize('FAILED:', 'RED')} Validation errors ({execution_time:.3f}s):")
                for error in errors:
                    print(f"    - {error}")
                
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
                print(f"  {colorize('PASSED', 'GREEN')} ({execution_time:.3f}s)")
        else:
            # No expectations defined, check if command succeeded
            if result['success']:
                print(f"  {colorize('PASSED', 'GREEN')} ({execution_time:.3f}s)")
            else:
                error_msg = result.get('error') or result.get('stderr', 'Unknown error')
                print(f"  {colorize('FAILED:', 'RED')} {error_msg} ({execution_time:.3f}s)")
                
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
        if untested_commands:
            print(f"\n{colorize('Untested Commands:', 'YELLOW')}")
            for cmd in sorted(untested_commands)[:10]:  # Show first 10
                print(f"  - {cmd}")
            if len(untested_commands) > 10:
                print(f"  ... and {len(untested_commands) - 10} more")
        
        # Show untested endpoints
        untested_endpoints = all_endpoints - self.tested_endpoints
        if untested_endpoints:
            print(f"\n{colorize('Untested Endpoints/Stored Procedures:', 'YELLOW')}")
            for endpoint in sorted(untested_endpoints)[:10]:  # Show first 10
                print(f"  - {endpoint}")
            if len(untested_endpoints) > 10:
                print(f"  ... and {len(untested_endpoints) - 10} more")
        
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
            
            # Debug: show what's in hierarchy
            print(f"\n  {colorize('Debug - Files found:', 'BLUE')}")
            for tier in tiers_to_run:
                tier_files = hierarchy.get(tier, [])
                if tier_files:
                    print(f"    {tier}: {', '.join([f.name for f in tier_files])}")
        
        # Run each test file with its base files
        all_passed = True
        for test_file, base_files in files_to_run:
            if not self.run_test_file(test_file, base_files):
                all_passed = False
                print(f"\n{colorize('STOPPING: Halting execution due to test failure', 'RED')}")
                break  # Stop running further test files
        
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
    
    args = parser.parse_args()
    
    runner = TestRunner(config_file=args.config, output_dir=args.output_dir)
    success = runner.run_all_tests(args.pattern)
    
    sys.exit(0 if success else 1)

if __name__ == '__main__':
    main()