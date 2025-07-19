#!/usr/bin/env python3
"""
Main test runner for the Rediacc CLI test framework.
"""

import argparse
import asyncio
import json
import logging
import sys
import os
from pathlib import Path
from typing import List, Optional

# Add the parent directory to the path to allow imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Load .env file if it exists
def load_env_file():
    """Simple .env file loader"""
    env_path = Path(__file__).parent.parent / '.env'
    if env_path.exists():
        with open(env_path, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    os.environ[key.strip()] = value.strip()

load_env_file()

from framework.base import TestContext, TestStatus
from framework.runner import TestRunner
from framework.loader import TestLoader
from framework.cli_wrapper import CLIWrapper
from framework.fixtures import TestFixtures


def setup_logging(verbose: bool = False):
    """Configure logging"""
    level = logging.DEBUG if verbose else logging.INFO
    
    # Configure root logger
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Reduce noise from some loggers
    if not verbose:
        logging.getLogger('urllib3').setLevel(logging.WARNING)
        logging.getLogger('asyncio').setLevel(logging.WARNING)


def print_results(results):
    """Print test results summary"""
    total = len(results)
    passed = sum(1 for r in results.values() if r.status == TestStatus.PASSED)
    failed = sum(1 for r in results.values() if r.status == TestStatus.FAILED)
    skipped = sum(1 for r in results.values() if r.status == TestStatus.SKIPPED)
    
    print("\n" + "=" * 60)
    print("TEST RESULTS SUMMARY")
    print("=" * 60)
    
    # Summary stats
    print(f"Total:   {total}")
    print(f"Passed:  {passed} ({passed/total*100:.1f}%)")
    print(f"Failed:  {failed} ({failed/total*100:.1f}%)")
    print(f"Skipped: {skipped} ({skipped/total*100:.1f}%)")
    
    # Failed tests details
    if failed > 0:
        print("\nFAILED TESTS:")
        print("-" * 60)
        for test_id, result in results.items():
            if result.status == TestStatus.FAILED:
                print(f"\n{result.name} ({test_id}):")
                print(f"  Error: {result.message}")
                if result.error:
                    print(f"  Exception: {type(result.error).__name__}: {result.error}")
    
    # Performance summary
    print("\nPERFORMANCE:")
    print("-" * 60)
    
    # Find slowest tests
    sorted_results = sorted(
        results.values(), 
        key=lambda r: r.metrics.duration, 
        reverse=True
    )
    
    print("Slowest tests:")
    for result in sorted_results[:5]:
        if result.metrics.duration > 0:
            print(f"  {result.name}: {result.metrics.duration:.2f}s")
    
    # Total time
    total_time = sum(r.metrics.duration for r in results.values())
    print(f"\nTotal execution time: {total_time:.2f}s")
    
    print("=" * 60)
    
    return failed == 0


def generate_report(results, output_format: str, output_file: Optional[str] = None):
    """Generate test report in various formats"""
    
    if output_format == 'json':
        report = {
            'summary': {
                'total': len(results),
                'passed': sum(1 for r in results.values() if r.status == TestStatus.PASSED),
                'failed': sum(1 for r in results.values() if r.status == TestStatus.FAILED),
                'skipped': sum(1 for r in results.values() if r.status == TestStatus.SKIPPED),
            },
            'tests': {
                test_id: result.to_dict() 
                for test_id, result in results.items()
            }
        }
        
        content = json.dumps(report, indent=2)
        
    elif output_format == 'junit':
        # Generate JUnit XML format
        from xml.etree.ElementTree import Element, SubElement, tostring
        
        testsuites = Element('testsuites')
        testsuite = SubElement(testsuites, 'testsuite')
        testsuite.set('name', 'Rediacc CLI Tests')
        testsuite.set('tests', str(len(results)))
        testsuite.set('failures', str(sum(1 for r in results.values() if r.status == TestStatus.FAILED)))
        testsuite.set('skipped', str(sum(1 for r in results.values() if r.status == TestStatus.SKIPPED)))
        
        for test_id, result in results.items():
            testcase = SubElement(testsuite, 'testcase')
            testcase.set('classname', 'RediaccCLI')
            testcase.set('name', result.name)
            testcase.set('time', str(result.metrics.duration))
            
            if result.status == TestStatus.FAILED:
                failure = SubElement(testcase, 'failure')
                failure.set('message', result.message)
                if result.error:
                    failure.text = str(result.error)
            elif result.status == TestStatus.SKIPPED:
                skipped = SubElement(testcase, 'skipped')
                skipped.set('message', result.message)
        
        content = tostring(testsuites, encoding='unicode')
        
    elif output_format == 'html':
        # Generate HTML report
        html = f"""
<!DOCTYPE html>
<html>
<head>
    <title>Rediacc CLI Test Report</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; }}
        .summary {{ background: #f0f0f0; padding: 15px; border-radius: 5px; }}
        .passed {{ color: green; }}
        .failed {{ color: red; }}
        .skipped {{ color: orange; }}
        table {{ border-collapse: collapse; width: 100%; margin-top: 20px; }}
        th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
        th {{ background: #f0f0f0; }}
        tr:nth-child(even) {{ background: #f9f9f9; }}
    </style>
</head>
<body>
    <h1>Rediacc CLI Test Report</h1>
    <div class="summary">
        <h2>Summary</h2>
        <p>Total: {len(results)}</p>
        <p class="passed">Passed: {sum(1 for r in results.values() if r.status == TestStatus.PASSED)}</p>
        <p class="failed">Failed: {sum(1 for r in results.values() if r.status == TestStatus.FAILED)}</p>
        <p class="skipped">Skipped: {sum(1 for r in results.values() if r.status == TestStatus.SKIPPED)}</p>
    </div>
    
    <h2>Test Results</h2>
    <table>
        <tr>
            <th>Test Name</th>
            <th>Status</th>
            <th>Duration</th>
            <th>Message</th>
        </tr>
"""
        
        for test_id, result in results.items():
            status_class = result.status.value
            html += f"""
        <tr>
            <td>{result.name}</td>
            <td class="{status_class}">{result.status.value}</td>
            <td>{result.metrics.duration:.2f}s</td>
            <td>{result.message}</td>
        </tr>
"""
        
        html += """
    </table>
</body>
</html>
"""
        content = html
    
    else:
        raise ValueError(f"Unknown report format: {output_format}")
    
    # Write to file or stdout
    if output_file:
        with open(output_file, 'w') as f:
            f.write(content)
        print(f"Report written to: {output_file}")
    else:
        print(content)


async def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description='Rediacc CLI Test Runner')
    
    # Test selection
    parser.add_argument('--test', help='Run specific test by name or ID')
    parser.add_argument('--suite', help='Run specific test suite (basic, complex, negative)')
    parser.add_argument('--tags', nargs='+', help='Run tests with specific tags')
    parser.add_argument('--test-dir', help='Directory containing tests', 
                       default=str(Path(__file__).parent / 'tests'))
    
    # Execution options
    parser.add_argument('--parallel', type=int, default=4, 
                       help='Number of parallel workers (default: 4)')
    parser.add_argument('--continue-on-failure', action='store_true',
                       help='Continue running tests after failures')
    parser.add_argument('--no-cleanup', action='store_true',
                       help='Skip cleanup phase')
    parser.add_argument('--keep-on-failure', action='store_true',
                       help='Keep resources if test fails')
    
    # Configuration
    parser.add_argument('--config', help='Configuration file path')
    parser.add_argument('--api-url', help='API URL to test against')
    parser.add_argument('--username', help='Username for authentication')
    parser.add_argument('--password', help='Password for authentication')
    parser.add_argument('--master-password', help='Master password for vault encryption')
    
    # Output options
    parser.add_argument('--verbose', '-v', action='store_true',
                       help='Enable verbose logging')
    parser.add_argument('--verbose-on-error', action='store_true',
                       help='Re-run failed tests with verbose output for debugging')
    parser.add_argument('--report', choices=['json', 'junit', 'html'],
                       help='Generate report in specified format')
    parser.add_argument('--output', help='Output file for report')
    
    # Special modes
    parser.add_argument('--mock', action='store_true',
                       help='Run in mock mode without real API calls')
    parser.add_argument('--list-tests', action='store_true',
                       help='List available tests without running')
    
    args = parser.parse_args()
    
    # Setup logging
    setup_logging(args.verbose)
    
    # Load configuration
    config = TestFixtures.get_test_config()
    
    if args.config:
        with open(args.config, 'r') as f:
            config.update(json.load(f))
    
    # Override with command line options
    if args.api_url:
        config['api_url'] = args.api_url
    if args.username:
        config['auth']['username'] = args.username
    if args.password:
        config['auth']['password'] = args.password
    
    # Use environment variables if available
    if not args.username and os.environ.get('REDIACC_TEST_USERNAME'):
        config['auth']['username'] = os.environ['REDIACC_TEST_USERNAME']
    if not args.password and os.environ.get('REDIACC_TEST_PASSWORD'):
        config['auth']['password'] = os.environ['REDIACC_TEST_PASSWORD']
    if not args.api_url and os.environ.get('REDIACC_API_URL'):
        config['api_url'] = os.environ['REDIACC_API_URL']
    
    # Create test context
    context = TestContext(config)
    
    # Generate unique test run identifier
    import time
    import random
    test_run_id = random.randint(1000, 9999)
    
    # Set the test run ID as a global variable
    context.set_var('test_run_id', test_run_id)
    
    # Initialize counters for different entity types
    context.set_var('team_counter', 0)
    context.set_var('machine_counter', 0)
    context.set_var('region_counter', 0)
    context.set_var('bridge_counter', 0)
    context.set_var('repository_counter', 0)
    context.set_var('storage_counter', 0)
    context.set_var('schedule_counter', 0)
    context.set_var('user_counter', 0)
    
    # Set company name using the test run ID
    unique_company = f"TestCompany_{test_run_id}"
    
    # Set default dependencies
    context.set_var('company', unique_company)
    context.set_var('region', 'us-east-1')
    context.set_var('team', 'TestTeam')
    
    # Log the test run ID for debugging
    print(f"\nTest Run ID: {test_run_id}")
    print(f"Company: {unique_company}")
    
    # Create CLI wrapper
    cli = CLIWrapper(mock_mode=args.mock, verbose=False)
    
    if args.master_password:
        cli.set_master_password(args.master_password)
    
    # Store test credentials for final output
    test_credentials = None
    
    # Authenticate unless in mock mode
    if not args.mock:
        # Check if we have credentials provided (must be non-None and non-empty)
        if config['auth'].get('username') is not None and config['auth'].get('password') is not None:
            # Use provided credentials
            print(f"\nUsing provided credentials: {config['auth']['username']}")
            
            # Login with provided credentials
            auth_result = cli.login(
                config['auth']['username'],
                config['auth']['password']
            )
            
            if not auth_result.get('success'):
                print(f"Authentication failed: {auth_result.get('error')}")
                print("\nTIP: Use --mock flag to run tests without real API")
                return 1
            
            print("Authentication successful")
            
            # Get the actual company name from the API
            print("Fetching company information...")
            dashboard_result = cli.execute_raw(["list", "resource-limits"])
            
            actual_company_name = unique_company  # Default to generated name
            if dashboard_result.get('success'):
                try:
                    # Parse the GetCompanyDashboardJson response
                    if 'tables' in dashboard_result:
                        for table in dashboard_result['tables']:
                            if 'data' in table and len(table['data']) > 0:
                                for row in table['data']:
                                    if 'subscriptionAndResourcesJson' in row:
                                        import json as json_lib
                                        sub_data = json_lib.loads(row['subscriptionAndResourcesJson'])
                                        company_info = json_lib.loads(sub_data['companyInfo'])
                                        actual_company_name = company_info['CompanyName']
                                        print(f"Using existing company: {actual_company_name}")
                                        break
                except Exception as e:
                    print(f"Warning: Could not parse company name: {e}")
                    print("Using generated company name for tests")
            
            # Update context with actual company name
            context.set_var('company', actual_company_name)
            
            # Store the provided credentials for display
            test_credentials = {
                'email': config['auth']['username'],
                'password': config['auth']['password'],
                'company': actual_company_name,
                'provided': True  # Flag to indicate these were provided
            }
        else:
            # No credentials provided - try to create a new company
            print("\nNo credentials provided. Creating a new test company...")
            
            # Generate unique credentials using test_run_id
            unique_email = f"test_{test_run_id}@example.com"
            unique_password = f"TestPass{test_run_id}!"
            activation_code = os.environ.get('REDIACC_TEST_ACTIVATION_CODE', '111111')
            
            # Create company
            print(f"Creating company: {unique_company}")
            print(f"Admin email: {unique_email}")
            
            create_result = cli.execute_raw([
                "create", "company",
                unique_company,
                "--email", unique_email,
                "--password", unique_password,
                "--activation-code", activation_code,
                "--plan", "ELITE"
            ])
            
            if not create_result.get('success'):
                error_msg = create_result.get('error', '')
                if "403" in error_msg or "Access denied" in error_msg:
                    print("\nERROR: Cannot create company - admin privileges required")
                    print("Please either:")
                    print("  1. Use --mock flag for mock testing")
                    print("  2. Provide existing credentials with --username and --password")
                    print("  3. Run setup_test_company.py with admin privileges first")
                    return 1
                else:
                    print(f"Failed to create company: {error_msg}")
                    return 1
            
            print("Company created successfully!")
            
            # Activate the user account
            print(f"Activating user account with code: {activation_code}")
            activate_result = cli.execute_raw([
                "user", "activate",
                unique_email,
                "--code", activation_code,
                "--password", unique_password
            ])
            
            if not activate_result.get('success'):
                print(f"Failed to activate user: {activate_result.get('error')}")
                return 1
            
            print("User activated successfully!")
            
            # Now login with the new credentials
            config['auth']['username'] = unique_email
            config['auth']['password'] = unique_password
            
            auth_result = cli.login(unique_email, unique_password)
            
            if not auth_result.get('success'):
                print(f"Authentication failed: {auth_result.get('error')}")
                return 1
            
            print("Authentication successful")
            
            test_credentials = {
                'email': unique_email,
                'password': unique_password,
                'company': unique_company,
                'created': True  # Flag to indicate we created these
            }
    
    # Load tests
    loader = TestLoader([Path(args.test_dir)])
    
    if args.suite:
        # Load specific suite
        suite_path = Path(args.test_dir) / args.suite
        if suite_path.exists():
            # Load all tests and filter by suite tag or directory
            tests = loader.load_all_tests()
            # Filter by either the suite tag or tests in the suite directory
            tests = [t for t in tests if args.suite in t.tags or 
                     any(args.suite in tag for tag in t.tags if tag.startswith('source:'))]
        else:
            print(f"Suite not found: {args.suite}")
            return 1
    elif args.test:
        # Load specific test
        if args.test.endswith('.yaml') or args.test.endswith('.yml'):
            tests = loader.load_test_file(args.test)
        else:
            all_tests = loader.load_all_tests()
            tests = [t for t in all_tests if t.name == args.test or t.id == args.test]
            
            if not tests:
                print(f"Test not found: {args.test}")
                return 1
    else:
        # Load all tests
        tests = loader.load_all_tests(tags=args.tags)
    
    if not tests:
        print("No tests found")
        return 1
    
    # List tests mode
    if args.list_tests:
        print(f"Found {len(tests)} tests:\n")
        for test in tests:
            print(f"  {test.name} ({test.id})")
            print(f"    Tags: {', '.join(test.tags)}")
            if test.description:
                print(f"    Description: {test.description}")
            print()
        return 0
    
    # Create test runner
    runner = TestRunner(
        context=context,
        cli_wrapper=cli,
        parallel_workers=args.parallel,
        continue_on_failure=args.continue_on_failure,
        cleanup_on_failure=not args.keep_on_failure,
        verbose_on_error=args.verbose_on_error
    )
    
    # Run tests
    print(f"Running {len(tests)} tests...")
    
    try:
        results = await runner.run_tests(tests)
    except KeyboardInterrupt:
        print("\nTest run interrupted")
        return 1
    
    # Print results
    success = print_results(results)
    
    # Generate report if requested
    if args.report:
        generate_report(results, args.report, args.output)
    
    # Cleanup
    cli.cleanup()
    
    # Display test credentials at the end
    if test_credentials:
        print("\n" + "=" * 60)
        if test_credentials.get('created'):
            print("TEST CREDENTIALS CREATED")
        else:
            print("TEST CREDENTIALS USED")
        print("=" * 60)
        print(f"Company Name: {test_credentials['company']}")
        print(f"Email: {test_credentials['email']}")
        print(f"Password: {test_credentials['password']}")
        if test_credentials.get('provided'):
            print("Note: Used existing credentials (company from API)")
        print("=" * 60)
        if test_credentials.get('created'):
            print("\nTo run tests again with these credentials:")
            print(f"python3 -m tests_yaml.run --username '{test_credentials['email']}' --password '{test_credentials['password']}'")
    elif args.mock:
        print("\n" + "=" * 60)
        print("MOCK MODE - No real credentials used")
        print(f"Mock Company: {unique_company}")
        print("=" * 60)
    
    return 0 if success else 1


if __name__ == '__main__':
    sys.exit(asyncio.run(main()))