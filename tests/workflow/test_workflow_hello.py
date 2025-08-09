#!/usr/bin/env python3
"""
Test script for workflow hello-test command
Tests the hello function on Private Team's rediacc11 machine
"""

import json
import os
import subprocess
import sys
import time
import pytest
from pathlib import Path
from datetime import datetime

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

def colorize(text, color):
    """Add color to text for terminal output"""
    if color in COLORS:
        return f"{COLORS[color]}{text}{COLORS['RESET']}"
    return text

def run_command(cmd, capture_output=True, check=True):
    """Run a shell command and return the result"""
    print(colorize(f"Running: {' '.join(cmd)}", 'BLUE'))
    
    try:
        if capture_output:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=check
            )
            return result.stdout, result.stderr, result.returncode
        else:
            result = subprocess.run(cmd, check=check)
            return None, None, result.returncode
    except subprocess.CalledProcessError as e:
        if check:
            print(colorize(f"Command failed with exit code {e.returncode}", 'RED'))
            if e.stderr:
                print(colorize(f"Error: {e.stderr}", 'RED'))
        return e.stdout if hasattr(e, 'stdout') else None, \
               e.stderr if hasattr(e, 'stderr') else None, \
               e.returncode

@pytest.fixture(scope="module", autouse=True)
def check_prerequisites():
    """Check if required configuration is present"""
    print(colorize("Checking prerequisites...", 'BOLD'))
    
    # Check if CLI is accessible
    cli_path = Path(__file__).parent.parent.parent / 'rediacc'
    if not cli_path.exists():
        pytest.skip(f"CLI wrapper not found at {cli_path}")
    
    # Check if we have a token
    config_path = Path.home() / '.rediacc' / 'config.json'
    if not config_path.exists():
        pytest.skip("No saved token found. Please login first with: ./rediacc login")
    
    try:
        with open(config_path) as f:
            config = json.load(f)
            if not config.get('token'):
                pytest.skip("No token in config. Please login first.")
    except Exception as e:
        pytest.skip(f"Error reading config: {e}")
    
    print(colorize("✓ Prerequisites check passed", 'GREEN'))
    yield  # This makes it a fixture

def test_hello_workflow():
    """Test the workflow hello-test command"""
    print(colorize("\n=== Testing Workflow Hello Command ===", 'BOLD'))
    
    # Configuration
    team_name = "Private Team"
    machine_name = "rediacc11"
    cli_path = str(Path(__file__).parent.parent.parent / 'rediacc')
    
    print(f"Team: {colorize(team_name, 'YELLOW')}")
    print(f"Machine: {colorize(machine_name, 'YELLOW')}")
    
    # Test 1: Run hello-test without waiting
    print(colorize("\nTest 1: Running hello-test (no wait)...", 'BOLD'))
    cmd = [
        cli_path, 'workflow', 'hello-test',
        '--team', team_name,
        '--machine', machine_name,
        '--output', 'json'
    ]
    
    stdout, stderr, returncode = run_command(cmd, check=False)
    
    assert returncode == 0, f"Test 1 failed with exit code {returncode}. Error: {stderr}"
    
    # Parse the output to get task ID if available
    task_id = None
    result = json.loads(stdout)
    assert result.get('success'), f"Test 1 failed: {result.get('error', 'Unknown error')}"
    
    task_id = result.get('data', {}).get('task_id')
    if task_id:
        print(colorize(f"✓ Test 1 passed - Task ID: {task_id}", 'GREEN'))
    else:
        print(colorize("✓ Test 1 passed - Task queued", 'GREEN'))
    
    # Test 2: Run hello-test with wait
    print(colorize("\nTest 2: Running hello-test (with wait)...", 'BOLD'))
    cmd = [
        cli_path, 'workflow', 'hello-test',
        '--team', team_name,
        '--machine', machine_name,
        '--wait',
        '--poll-interval', '2',
        '--wait-timeout', '30',
        '--output', 'json'
    ]
    
    start_time = time.time()
    stdout, stderr, returncode = run_command(cmd, check=False)
    elapsed_time = time.time() - start_time
    
    assert returncode == 0, f"Test 2 failed with exit code {returncode}. Error: {stderr}"
    
    result = json.loads(stdout)
    assert result.get('success'), f"Test 2 failed: {result.get('error', 'Unknown error')}"
    
    print(colorize(f"✓ Test 2 passed - Completed in {elapsed_time:.2f} seconds", 'GREEN'))
    
    # Check if we got the expected output
    message = result.get('message', '')
    if 'completed' in message.lower() or 'success' in message.lower():
        print(colorize("✓ Hello test completed successfully", 'GREEN'))
    else:
        print(colorize(f"Note: {message}", 'YELLOW'))
    
    # Test 3: Test with invalid machine (negative test)
    print(colorize("\nTest 3: Testing with invalid machine (negative test)...", 'BOLD'))
    cmd = [
        cli_path, 'workflow', 'hello-test',
        '--team', team_name,
        '--machine', 'nonexistent-machine',
        '--output', 'json'
    ]
    
    stdout, stderr, returncode = run_command(cmd, check=False)
    
    # We expect this to fail
    if returncode == 0:
        result = json.loads(stdout)
        assert not result.get('success'), "Test 3 failed - Should have failed for invalid machine"
        print(colorize("✓ Test 3 passed - Correctly failed for invalid machine", 'GREEN'))
    else:
        # Command failed at CLI level, which is also acceptable
        print(colorize("✓ Test 3 passed - Command rejected invalid machine", 'GREEN'))
    
    print(colorize("\n✓ All workflow tests passed!", 'GREEN'))

def main():
    """Main test execution for standalone run"""
    print(colorize("=== Rediacc Workflow Hello Test Suite ===", 'BOLD'))
    print(f"Test Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Check prerequisites manually for standalone run
    cli_path = Path(__file__).parent.parent.parent / 'rediacc'
    if not cli_path.exists():
        print(colorize(f"\n✗ CLI wrapper not found at {cli_path}", 'RED'))
        sys.exit(1)
    
    config_path = Path.home() / '.rediacc' / 'config.json'
    if not config_path.exists():
        print(colorize("\n✗ No saved token found. Please login first with: ./rediacc login", 'RED'))
        sys.exit(1)
    
    try:
        with open(config_path) as f:
            config = json.load(f)
            if not config.get('token'):
                print(colorize("\n✗ No token in config. Please login first.", 'RED'))
                sys.exit(1)
    except Exception as e:
        print(colorize(f"\n✗ Error reading config: {e}", 'RED'))
        sys.exit(1)
    
    print(colorize("✓ Prerequisites check passed", 'GREEN'))
    
    # Run tests
    try:
        test_hello_workflow()
        print(colorize("\n=== Test Summary ===", 'BOLD'))
        print(colorize("✓ All tests passed!", 'GREEN'))
        sys.exit(0)
    except AssertionError as e:
        print(colorize("\n=== Test Summary ===", 'BOLD'))
        print(colorize(f"✗ Test failed: {e}", 'RED'))
        sys.exit(1)
    except Exception as e:
        print(colorize("\n=== Test Summary ===", 'BOLD'))
        print(colorize(f"✗ Unexpected error: {e}", 'RED'))
        sys.exit(1)

if __name__ == "__main__":
    main()