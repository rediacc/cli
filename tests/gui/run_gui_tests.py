#!/usr/bin/env python3
"""
GUI Test Runner for Rediacc CLI
Runs GUI tests with proper display handling
"""

import sys
import os
import subprocess
from pathlib import Path
import argparse
import json


def check_display():
    """Check if a display is available"""
    display = os.environ.get('DISPLAY')
    if not display:
        return False
    
    # Try to connect to the display
    try:
        import tkinter
        root = tkinter.Tk()
        root.withdraw()
        root.destroy()
        return True
    except:
        return False


def setup_virtual_display():
    """Setup a virtual display using Xvfb if available"""
    try:
        # Check if Xvfb is installed
        subprocess.run(['which', 'Xvfb'], check=True, capture_output=True)
        
        # Start Xvfb on display :99
        print("Starting virtual display with Xvfb...")
        xvfb_process = subprocess.Popen(
            ['Xvfb', ':99', '-screen', '0', '1024x768x24'],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        
        # Set DISPLAY environment variable
        os.environ['DISPLAY'] = ':99'
        
        # Give Xvfb time to start
        import time
        time.sleep(1)
        
        return xvfb_process
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("Warning: Xvfb not available. GUI tests require a display.")
        return None


def run_gui_tests(test_path=None, verbose=False, headless=False):
    """Run GUI tests with pytest or directly"""
    
    # First run terminal command test to catch any errors early
    print("=" * 60)
    print("Pre-flight Check: Terminal Command Functionality")
    print("=" * 60)
    
    gui_test_dir = Path(__file__).parent
    terminal_test_file = gui_test_dir / "test_terminal_imports.py"
    
    if terminal_test_file.exists():
        print("Testing terminal command...")
        terminal_result = subprocess.run(
            [sys.executable, str(terminal_test_file)],
            capture_output=False,  # Show output directly
            text=True
        )
        if terminal_result.returncode != 0:
            print("\n" + "=" * 60)
            print("❌ TERMINAL COMMAND TEST FAILED")
            print("The terminal command has errors that will cause test failures.")
            print("Please fix the errors above before running GUI tests.")
            print("=" * 60)
            return 1
        print("\n✓ Terminal command OK, proceeding with GUI tests...\n")
    
    # Check for display or set up virtual one
    if headless or not check_display():
        xvfb_process = setup_virtual_display()
        if not xvfb_process and not check_display():
            print("Warning: No display available and cannot start virtual display.")
            print("Running basic tests without display...")
    else:
        xvfb_process = None
    
    try:
        # Check if we have the basic test file
        basic_test_file = gui_test_dir / "test_gui_login_basic.py"
        
        if basic_test_file.exists():
            # Run the basic test directly
            print("Running basic GUI tests...")
            cmd = [sys.executable, str(basic_test_file)]
            result = subprocess.run(cmd)
            return result.returncode
        
        # Fall back to pytest if available
        try:
            import pytest
            # Build pytest command
            cmd = [sys.executable, '-m', 'pytest']
            
            if verbose:
                cmd.append('-v')
            
            # Add test path or run all GUI tests
            if test_path:
                cmd.append(test_path)
            else:
                cmd.append(str(gui_test_dir))
            
            # Add pytest options
            cmd.extend([
                '--tb=short',  # Short traceback format
                '--color=yes',  # Colored output
                '-W', 'ignore::DeprecationWarning'  # Ignore deprecation warnings
            ])
            
            # Run tests
            print(f"Running GUI tests: {' '.join(cmd)}")
            result = subprocess.run(cmd)
            
            return result.returncode
        except ImportError:
            print("pytest not available, running basic tests only")
            return 0
        
    finally:
        # Clean up Xvfb if we started it
        if xvfb_process:
            xvfb_process.terminate()
            xvfb_process.wait()


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description='Run GUI tests for Rediacc CLI')
    parser.add_argument('test', nargs='?', help='Specific test file or test to run')
    parser.add_argument('-v', '--verbose', action='store_true', help='Verbose output')
    parser.add_argument('--headless', action='store_true', 
                       help='Force headless mode with virtual display')
    parser.add_argument('--check-deps', action='store_true',
                       help='Check if required dependencies are installed')
    
    args = parser.parse_args()
    
    if args.check_deps:
        # Check for required packages
        required = ['pytest', 'pytest-mock']
        missing = []
        
        for package in required:
            try:
                __import__(package.replace('-', '_'))
            except ImportError:
                missing.append(package)
        
        if missing:
            print(f"Missing packages: {', '.join(missing)}")
            print(f"Install with: pip install {' '.join(missing)}")
            return 1
        else:
            print("All required packages are installed.")
            return 0
    
    # Run tests
    return run_gui_tests(args.test, args.verbose, args.headless)


if __name__ == '__main__':
    sys.exit(main())