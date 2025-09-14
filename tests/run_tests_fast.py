#!/usr/bin/env python3
"""
Fast YAML-based test runner for Rediacc CLI using in-memory token management
Eliminates subprocess overhead and disk I/O for improved performance
"""
import argparse
import json
import os
import re
import sys
import time
import yaml
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional, Union

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))
sys.path.insert(0, str(Path(__file__).parent))  # For helpers

# Import API client and helpers
from cli.core.api_client import SuperClient
from totp_helper import generate_totp_code, hash_password

# Load environment variables from parent .env file
env_file = Path(__file__).parent.parent.parent / '.env'
if env_file.exists():
    with open(env_file) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
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

# Use colors unless disabled
USE_COLORS = os.environ.get('NO_COLOR') is None


def colored(text: str, color: str = 'RESET') -> str:
    """Apply color to text if colors are enabled"""
    if USE_COLORS and color in COLORS:
        return f"{COLORS[color]}{text}{COLORS['RESET']}"
    return text


class FastYAMLTestRunner:
    """Fast test runner using in-memory API client"""
    
    def __init__(self, base_url: str = None):
        self.base_url = base_url or os.environ.get('REDIACC_API_URL', 'http://localhost:7322')
        
        # Set environment variable for base URL if provided
        if base_url:
            os.environ['SYSTEM_API_URL'] = base_url
        
        self.api_client = SuperClient()
        
        # Test context
        self.test_dir = Path(__file__).parent
        self.yaml_dir = self.test_dir / 'yaml'
        self.results_dir = self.test_dir / 'test_results'
        
        # Create results directory
        self.results_dir.mkdir(exist_ok=True)
        
        # Test state
        self.test_id = f"test_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        self.timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        self.config = self.load_config()  # Load config immediately
        self.chain_context = {}
        self.test_results = []
        self.command_coverage = set()
        self.endpoint_coverage = set()
        self.test_counter = 0  # Counter for unique test identification
        
    def load_config(self) -> dict:
        """Load test configuration"""
        config_file = self.test_dir / 'config.yaml'
        if config_file.exists():
            with open(config_file) as f:
                config = yaml.safe_load(f)
                return config
        
        # Default config
        return {
            'test_environment': {
                'activation_code': '111111',
                'master_password': 'TestMasterPassword123!'
            },
            'test_data': {
                'company': {
                    'name_pattern': f'TestCompany-{self.timestamp}',
                    'admin_email_pattern': f'admin-{self.timestamp}@test.com',
                    'admin_password': 'Test@Pass123!'
                },
                'team': {
                    'name_pattern': f'TestTeam-{self.timestamp}'
                },
                'machine': {
                    'name_pattern': f'TestMachine-{self.timestamp}_{self.test_id}'
                },
                'storage': {
                    'name_pattern': f'TestStorage-{self.timestamp}_{self.test_id}'
                },
                'schedule': {
                    'name_pattern': f'TestSchedule-{self.timestamp}_{self.test_id}'
                },
                'repository': {
                    'name_pattern': f'TestRepo-{self.timestamp}_{self.test_id}'
                }
            }
        }
        
    def resolve_variables(self, value: Any) -> Any:
        """Resolve variables in test data"""
        if isinstance(value, str):
            # Pattern to match ${...} variables
            pattern = r'\$\{([^}]+)\}'
            
            def replacer(match):
                var_path = match.group(1)
                
                # Special variables
                if var_path == 'TIMESTAMP':
                    return self.timestamp
                elif var_path == 'TEST_ID':
                    return self.test_id
                elif var_path.startswith('totp(') and var_path.endswith(')'):
                    # Extract secret from totp(secret)
                    secret = var_path[5:-1]
                    # Only resolve if it looks like a variable reference
                    if secret.startswith('$') or secret.startswith('chain.') or '${' in secret:
                        resolved_secret = self.resolve_variables(f'${{{secret}}}')
                    else:
                        resolved_secret = secret
                    return generate_totp_code(resolved_secret)
                elif var_path.startswith('hash(') and var_path.endswith(')'):
                    # Extract password from hash(password)
                    password = var_path[5:-1]
                    # Only resolve if it looks like a variable reference
                    if password.startswith('$') or '.' in password:
                        resolved_password = self.resolve_variables(f'${{{password}}}')
                    else:
                        resolved_password = password
                    hash_result = hash_password(resolved_password)
                    return hash_result
                
                # Navigate variable path
                parts = var_path.split('.')
                result = None
                
                if parts[0] == 'config':
                    result = self.config
                    parts = parts[1:]
                elif parts[0] == 'chain':
                    result = self.chain_context
                    parts = parts[1:]
                elif parts[0] == 'result' and hasattr(self, 'test_result'):
                    result = {'data': {'result': self.test_result}}
                    parts = parts[1:]
                    
                for part in parts:
                    # Handle array indexing like result[0]
                    if '[' in part and ']' in part:
                        key = part[:part.index('[')]
                        index_str = part[part.index('[')+1:part.index(']')]
                        try:
                            index = int(index_str)
                            if isinstance(result, dict) and key in result:
                                result = result[key]
                                if isinstance(result, list) and 0 <= index < len(result):
                                    result = result[index]
                                else:
                                    return match.group(0)
                            else:
                                return match.group(0)
                        except (ValueError, IndexError):
                            return match.group(0)
                    elif isinstance(result, dict) and part in result:
                        result = result[part]
                    else:
                        return match.group(0)  # Return unchanged if not found
                        
                return str(result) if result is not None else match.group(0)
            
            return re.sub(pattern, replacer, value)
            
        elif isinstance(value, dict):
            return {k: self.resolve_variables(v) for k, v in value.items()}
        elif isinstance(value, list):
            return [self.resolve_variables(v) for v in value]
            
        return value
        
    def execute_test(self, test_spec: dict, test_name: str) -> dict:
        """Execute a single test using direct API calls"""
        start_time = time.time()
        
        # Resolve variables in test spec
        resolved_spec = self.resolve_variables(test_spec)
        
        # Extract command and args
        command = resolved_spec.get('command', [])
        if isinstance(command, list) and command:
            command = command[0]
            
        args = resolved_spec.get('args', {})
        
        # Track coverage
        self.command_coverage.add(f"dynamic.{command}")
        self.endpoint_coverage.add(command)
        
        # Execute via API client
        try:
            result = self.api_client.execute_command(command, args)
            
            # Format result for compatibility
            formatted_result = {
                'success': result.get('success', False),
                'output': {
                    'success': result.get('success', False),
                    'data': {
                        'endpoint': command,
                        'parameters': args,
                        'result': result.get('data', [])
                    },
                    'message': f"Successfully executed {command}" if result.get('success') else None,
                    'error': result.get('error') if not result.get('success') else None
                },
                'stderr': '',
                'returncode': 0 if result.get('success') else 1
            }
            
            # Handle special formatting for certain responses
            if command == 'login' and result.get('success'):
                # Format login response
                formatted_result['output']['data'] = {
                    'email': args.get('email'),
                    'company': None,
                    'vault_encryption_enabled': False,
                    'master_password_set': False
                }
                formatted_result['output']['message'] = f"Successfully logged in as {args.get('email')}"
                
            elif command == 'logout' and result.get('success'):
                formatted_result['output']['data'] = {}
                formatted_result['output']['message'] = "Successfully logged out"
                
        except Exception as e:
            formatted_result = {
                'success': False,
                'output': {
                    'success': False,
                    'error': str(e)
                },
                'stderr': str(e),
                'returncode': 1
            }
            
        # Validate expectations
        errors = []
        expected = resolved_spec.get('expect', {})
        if 'success' in expected:
            actual_success = formatted_result['success']
            expected_success = expected['success']
            if actual_success != expected_success:
                errors.append(f"Expected success: {expected_success} but got success: {actual_success}")
        
        # Check error_contains expectation
        if 'error_contains' in expected and not formatted_result['success']:
            expected_error = expected['error_contains']
            actual_error = formatted_result['output'].get('error', '')
            # Handle both string and list cases
            if isinstance(expected_error, list):
                # Check if any of the expected errors is in the actual error
                if not any(err in actual_error for err in expected_error):
                    errors.append(f"Expected error to contain one of {expected_error} but got: {actual_error}")
            else:
                if expected_error not in actual_error:
                    errors.append(f"Expected error to contain '{expected_error}' but got: {actual_error}")
                
        execution_time = time.time() - start_time
        
        # Build result
        test_result = {
            'test_name': test_name,
            'timestamp': datetime.now().isoformat(),
            'execution_time_seconds': round(execution_time, 3),
            'command_executed': {
                'command': [command] if command else [],
                'args': args,
                'full_command': self._build_command_string(command, args)
            },
            'result': formatted_result,
            'success': len(errors) == 0,
            'errors': errors
        }
        
        return test_result
        
    def _build_command_string(self, command: str, args: dict) -> str:
        """Build command string for display"""
        cmd_parts = [command, '--output', 'json-full']
        
        for key, value in args.items():
            cli_key = key.replace('_', '-')
            if isinstance(value, bool):
                cmd_parts.extend([f'--{cli_key}', str(value).lower()])
            elif isinstance(value, list):
                cmd_parts.append(f'--{cli_key}')
                cmd_parts.extend([str(v) for v in value])
            elif value is not None:
                cmd_parts.extend([f'--{cli_key}', str(value)])
                
        return ' '.join(cmd_parts)
        
    def run_test_file(self, test_file: Union[str, Path]) -> bool:
        """Run a single test file"""
        test_file = Path(test_file) if isinstance(test_file, str) else test_file
        
        # Increment counter for unique identification
        self.test_counter += 1
        
        # Generate unique timestamp for each test file using counter and file name
        now = datetime.now()
        base_timestamp = now.strftime('%Y%m%d_%H%M%S')
        # Use counter and first 4 chars of filename for uniqueness
        file_prefix = test_file.stem[:4] if test_file.stem else 'test'
        self.timestamp = f"{base_timestamp}_{self.test_counter:03d}_{file_prefix}"
        self.test_id = f"test_{self.timestamp}"
        self.chain_context = {}  # Clear chain context between files
        
        # Update config with new timestamp
        self.config['test_data']['company']['name_pattern'] = f'TestCompany-{self.timestamp}'
        self.config['test_data']['company']['admin_email_pattern'] = f'admin-{self.timestamp}@test.com'
        self.config['test_data']['team']['name_pattern'] = f'TestTeam-{self.timestamp}'
        self.config['test_data']['machine']['name_pattern'] = f'TestMachine-{self.timestamp}_{self.test_id}'
        self.config['test_data']['storage']['name_pattern'] = f'TestStorage-{self.timestamp}_{self.test_id}'
        self.config['test_data']['schedule']['name_pattern'] = f'TestSchedule-{self.timestamp}_{self.test_id}'
        self.config['test_data']['repository']['name_pattern'] = f'TestRepo-{self.timestamp}_{self.test_id}'
        
        # Removed verbose output per user request
        
        # Load test file
        with open(test_file) as f:
            test_data = yaml.safe_load(f)
            
        file_start_time = time.time()
        
        # Extract metadata
        file_test_name = test_data.get('name', test_file.stem)
        description = test_data.get('description', '')
        
        # Get relative path for display
        try:
            relative_path = str(test_file.relative_to(self.test_dir))
        except ValueError:
            # If not relative to test_dir, try to make it relative to cwd
            try:
                relative_path = str(test_file.relative_to(Path.cwd()))
            except ValueError:
                relative_path = str(test_file)
        
        # Results container
        results = {
            'test_metadata': {
                'test_file': relative_path,
                'test_name': file_test_name,
                'description': description,
                'timestamp': datetime.now().isoformat(),
                'test_id': self.test_id,
                'total_execution_time_seconds': 0
            },
            'setup_results': [],
            'test_results': [],
            'chain_exports': {}
        }
        
        # Run setup if present
        if 'setup' in test_data:
            # Removed verbose setup output
            for setup_spec in test_data['setup']:
                setup_name = setup_spec.get('name', 'setup')
                result = self.execute_test(setup_spec, setup_name)
                results['setup_results'].append(result)
                # Removed progress dots
                
                if not result['success']:
                    # Extract error message for debugging
                    error_msg = result.get('result', {}).get('output', {}).get('error', 'Unknown error')
                    # Keep minimal error output for critical failures
                    print(f"\nSetup failed: {setup_name} - {error_msg}")
                    return results
                    
        # Run tests
        passed = 0
        failed = 0
        
        for test_spec in test_data.get('tests', []):
            test_name = test_spec.get('name', 'test')
            result = self.execute_test(test_spec, test_name)
            results['test_results'].append(result)
            
            if result['success']:
                # Removed success dots
                passed += 1
            else:
                # Removed failure markers
                failed += 1
                
            # Handle chain exports
            if 'chain_export' in test_spec and result['success']:
                # Add the test result to the variable context temporarily
                self.test_result = result['result']['output']['data'].get('result', [])
                exports = self.resolve_variables(test_spec['chain_export'])
                self.chain_context.update(exports)
                results['chain_exports'].update(exports)
                # Clean up temporary variable
                delattr(self, 'test_result')
                
                # Show exports
                for key, value in exports.items():
                    # Removed chain export logging
                    pass
                    
        # Update execution time
        results['test_metadata']['total_execution_time_seconds'] = round(
            time.time() - file_start_time, 3
        )
        
        # Summary
        total = passed + failed
        if failed == 0:
            # Removed per-file success summary
            pass
        else:
            # Removed per-file failure summary
            pass
            
        # Save results
        result_file = self.results_dir / f"{test_file.stem}.json"
        with open(result_file, 'w') as f:
            json.dump(results, f, indent=2)
            
        return results
        
    def run_all_tests(self, pattern: str = '*.yaml') -> bool:
        """Run all test files matching pattern"""
        # Clean results directory
        for old_file in self.results_dir.glob('*.json'):
            old_file.unlink()
        # Removed cleanup message
        
        # Find test files
        test_files = []
        for subdir in ['community', 'enterprise']:
            subdir_path = self.yaml_dir / subdir
            if subdir_path.exists():
                test_files.extend(sorted(subdir_path.glob(pattern)))
                
        if not test_files:
            # Keep critical error message
            print(f"No test files found matching pattern: {pattern}")
            return False
            
        # Removed file count message
        
        # Load config
        self.config = self.load_config()
        
        # Run tests
        all_passed = True
        file_results = []
        
        for test_file in test_files:
            result = self.run_test_file(test_file)
            file_results.append(result)
            
            # Check if all tests passed
            for test_result in result['test_results']:
                if not test_result['success']:
                    all_passed = False
                    
        # Print summary
        self._print_summary(file_results)
        
        # Save coverage report
        self._save_coverage_report()
        
        return all_passed
        
    def _print_summary(self, file_results: List[dict]):
        """Print test summary in consolidated table format"""
        if not file_results:
            return
            
        # Collect all individual test results
        all_test_results = []
        for file_result in file_results:
            test_file = Path(file_result['test_metadata']['test_file']).name
            suite_name = file_result['test_metadata']['test_name']
            
            # Add each individual test result
            for test in file_result.get('test_results', []):
                all_test_results.append({
                    'suite_file': test_file,
                    'suite_name': suite_name,
                    'test_name': test['test_name'],
                    'success': test['success'],
                    'execution_time_seconds': test['execution_time_seconds'],
                    'endpoint': test['command_executed']['command'][0] if test['command_executed']['command'] else 'N/A'
                })
        
        if not all_test_results:
            print("\nNo test results to display.")
            return
            
        # Calculate column widths
        suite_width = max(len(r['suite_name']) for r in all_test_results)
        suite_width = max(suite_width, 15)  # Minimum width
        
        test_width = max(len(r['test_name']) for r in all_test_results)
        test_width = max(test_width, 25)  # Minimum width
        
        total_width = suite_width + test_width + 50
        
        # Print header
        print(f"\n{colored('Test Results Summary', 'BOLD')}")
        print("=" * total_width)
        print(f"{'Test Suite':<{suite_width}} | {'Test Name':<{test_width}} | {'Status':^10} | {'Time':^8} | {'Endpoint'}")
        print("=" * total_width)
        
        # Print results grouped by suite
        current_suite = None
        suite_totals = {}  # Track totals per suite
        
        for result in all_test_results:
            suite = result['suite_name']
            
            # Initialize suite totals
            if suite not in suite_totals:
                suite_totals[suite] = {'passed': 0, 'failed': 0, 'time': 0}
            
            # Update totals
            if result['success']:
                suite_totals[suite]['passed'] += 1
            else:
                suite_totals[suite]['failed'] += 1
            suite_totals[suite]['time'] += result['execution_time_seconds']
            
            # Print separator between suites
            if suite != current_suite:
                if current_suite is not None:
                    print("-" * total_width)
                current_suite = suite
            
            # Format display values
            suite_display = suite if len(suite) <= suite_width else suite[:suite_width-3] + '...'
            test_display = result['test_name'] if len(result['test_name']) <= test_width else result['test_name'][:test_width-3] + '...'
            
            status = 'PASS' if result['success'] else 'FAIL'
            status_color = 'GREEN' if result['success'] else 'RED'
            time_str = f"{result['execution_time_seconds']:.3f}s"
            endpoint = result['endpoint']
            
            status_display = colored(f"{status:^10}", status_color)
            
            # Only show suite name on first test of each suite
            index = all_test_results.index(result)
            if index > 0 and all_test_results[index - 1]['suite_name'] == suite:
                suite_display = " " * suite_width
            
            print(f"{suite_display:<{suite_width}} | {test_display:<{test_width}} | {status_display} | {time_str:^8} | {endpoint}")
        
        print("=" * total_width)
        
        # Overall summary
        total_tests = len(all_test_results)
        passed_tests = sum(1 for r in all_test_results if r['success'])
        failed_tests = total_tests - passed_tests
        total_time = sum(r['execution_time_seconds'] for r in all_test_results)
        
        print(f"\nTotal: {total_tests} tests, {colored(f'{passed_tests} passed', 'GREEN')}, ", end="")
        if failed_tests > 0:
            print(f"{colored(f'{failed_tests} failed', 'RED')}, ", end="")
        print(f"Time: {total_time:.3f}s")
        
        # Suite summary
        print(f"\n{colored('Suite Summary:', 'BOLD')}")
        for suite_name, totals in suite_totals.items():
            total = totals['passed'] + totals['failed']
            if totals['failed'] == 0:
                status = colored(f"{totals['passed']}/{total} passed", 'GREEN')
            else:
                status = f"{colored(str(totals['passed']), 'GREEN')}/{total} passed, {colored(str(totals['failed']), 'RED')} failed"
            print(f"  {suite_name}: {status} ({totals['time']:.3f}s)")
        
        # Coverage summary
        print(f"\n{colored('Test Coverage Report:', 'BOLD')}")
        print("=" * 60)
        
        # Commands coverage
        commands_tested = len(self.command_coverage)
        commands_total = 121  # Approximate from previous runs
        commands_coverage = (commands_tested / commands_total * 100) if commands_total > 0 else 0
        
        print(f"\n{colored('Commands:', 'BLUE')}")
        print(f"  Tested: {commands_tested}/{commands_total} ({commands_coverage:.1f}%)")
        
        # Endpoints coverage
        endpoints_tested = len(self.endpoint_coverage)
        endpoints_total = 111  # Approximate from previous runs
        endpoints_coverage = (endpoints_tested / endpoints_total * 100) if endpoints_total > 0 else 0
        
        print(f"\n{colored('Stored Procedures:', 'BLUE')}")
        print(f"  Tested: {endpoints_tested}/{endpoints_total} ({endpoints_coverage:.1f}%)")
            
    def _save_coverage_report(self):
        """Save test coverage report"""
        # Get all possible commands and endpoints
        all_commands = set()
        all_endpoints = set()
        
        # This would need to be populated with all available commands/endpoints
        # For now, we'll use what we've seen
        
        coverage = {
            'test_id': self.test_id,
            'commands': {
                'total': 121,  # Approximate from previous runs
                'tested': len(self.command_coverage),
                'coverage_percentage': round(len(self.command_coverage) / 121 * 100, 2),
                'tested_list': sorted(list(self.command_coverage))
            },
            'endpoints': {
                'total': 111,  # Approximate from previous runs
                'tested': len(self.endpoint_coverage),
                'coverage_percentage': round(len(self.endpoint_coverage) / 111 * 100, 2),
                'tested_list': sorted(list(self.endpoint_coverage))
            }
        }
        
        coverage_file = self.results_dir / 'coverage_report.json'
        with open(coverage_file, 'w') as f:
            json.dump(coverage, f, indent=2)
            
        # Removed coverage report message


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description='Fast YAML test runner for Rediacc CLI'
    )
    parser.add_argument(
        'test_files',
        nargs='*',
        help='Specific test files to run (runs all if not specified)'
    )
    parser.add_argument(
        '--url',
        default=None,
        help='API base URL (default: http://localhost:7322)'
    )
    parser.add_argument(
        '--no-color',
        action='store_true',
        help='Disable colored output'
    )
    
    args = parser.parse_args()
    
    if args.no_color:
        global USE_COLORS
        USE_COLORS = False
        
    # Create runner
    runner = FastYAMLTestRunner(args.url)
    
    # Run tests
    if args.test_files:
        # Run specific files
        all_passed = True
        for test_file in args.test_files:
            path = Path(test_file)
            if path.exists():
                result = runner.run_test_file(path)
                # Check results
                for test_result in result['test_results']:
                    if not test_result['success']:
                        all_passed = False
            else:
                # Keep critical error message
                print(f"Test file not found: {test_file}")
                all_passed = False
    else:
        # Run all tests
        all_passed = runner.run_all_tests()
        
    # Exit with appropriate code
    sys.exit(0 if all_passed else 1)


if __name__ == '__main__':
    main()