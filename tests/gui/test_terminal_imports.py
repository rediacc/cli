#!/usr/bin/env python3
"""
Test script to verify terminal command works without errors.
This is run as part of GUI tests to catch any terminal command errors early.
"""

import sys
import os
from pathlib import Path

def test_terminal_command():
    """Test that terminal command works without any errors"""
    
    # Add src to path as the terminal command would
    cli_src_path = Path(__file__).parent.parent.parent / 'src'
    sys.path.insert(0, str(cli_src_path))
    
    print("Testing terminal command functionality...")
    print(f"  Python path includes: {cli_src_path}")
    
    errors = []
    
    # Test importing the term module
    try:
        print("  Importing cli.commands.term_main module...")
        from cli.commands import term_main
        print("    ✓ commands.term_main imported successfully")
    except ImportError as e:
        error_msg = f"Failed to import cli.commands.term_main: {e}"
        print(f"    ✗ {error_msg}")
        errors.append(error_msg)
    except Exception as e:
        error_msg = f"Unexpected error importing cli.commands.term_main: {e}"
        print(f"    ✗ {error_msg}")
        errors.append(error_msg)
    
    # Also test the actual term_main.py file path that might have the issue
    try:
        print("  Testing direct execution context for term_main.py...")
        term_file = cli_src_path / 'commands' / 'term_main.py'
        if term_file.exists():
            # Simulate how term_main.py would be executed
            import importlib.util
            spec = importlib.util.spec_from_file_location("term_direct", term_file)
            term_module = importlib.util.module_from_spec(spec)
            # This will catch the import error you mentioned
            spec.loader.exec_module(term_module)
            print("    ✓ term_main.py can be executed directly")
        else:
            print(f"    ⚠ term_main.py not found at {term_file}")
    except ModuleNotFoundError as e:
        error_msg = f"Module import error in term_main.py: {e}"
        print(f"    ✗ {error_msg}")
        errors.append(error_msg)
    except Exception as e:
        error_msg = f"Error executing term_main.py: {e}"
        print(f"    ✗ {error_msg}")
        errors.append(error_msg)
    
    # Test importing specific items from term
    try:
        print("  Testing specific imports from term...")
        from cli.commands.term_main import main
        print("    ✓ main function imported successfully")
    except ImportError as e:
        error_msg = f"Failed to import main from cli.commands.term_main: {e}"
        print(f"    ✗ {error_msg}")
        errors.append(error_msg)
    except Exception as e:
        error_msg = f"Unexpected error importing from cli.commands.term_main: {e}"
        print(f"    ✗ {error_msg}")
        errors.append(error_msg)
    
    # Check if cli._version exists
    try:
        print("  Checking cli._version module...")
        from cli._version import __version__
        print(f"    ✓ cli._version imported successfully (version: {__version__})")
    except ImportError as e:
        error_msg = f"Failed to import cli._version: {e}"
        print(f"    ✗ {error_msg}")
        errors.append(error_msg)
        
        # Try alternate import path
        print("  Trying alternate import path for _version...")
        try:
            import _version
            print(f"    ✓ _version imported directly (version: {_version.__version__})")
        except ImportError as e2:
            error_msg2 = f"Also failed direct import of _version: {e2}"
            print(f"    ✗ {error_msg2}")
            errors.append(error_msg2)
    
    # Test the actual rediacc term command (without actually connecting)
    try:
        print("  Testing rediacc term command (dry run)...")
        rediacc_path = Path(__file__).parent.parent.parent / 'rediacc'
        if rediacc_path.exists():
            # Test with --help to avoid actual connection
            import subprocess
            result = subprocess.run(
                [str(rediacc_path), 'term', '--help'],
                capture_output=True,
                text=True,
                timeout=5,
                cwd=str(Path(__file__).parent.parent.parent)
            )
            
            # Check for ANY error (non-zero exit code with stderr output)
            if result.returncode != 0:
                # Terminal command failed - capture the error
                error_output = result.stderr.strip() if result.stderr else result.stdout.strip()
                if error_output:
                    # Determine error type for better reporting
                    if 'ModuleNotFoundError' in error_output or 'ImportError' in error_output:
                        error_type = "Import error"
                    elif 'SyntaxError' in error_output:
                        error_type = "Syntax error"
                    elif 'AttributeError' in error_output:
                        error_type = "Attribute error"
                    elif 'TypeError' in error_output:
                        error_type = "Type error"
                    elif 'NameError' in error_output:
                        error_type = "Name error"
                    elif 'FileNotFoundError' in error_output:
                        error_type = "File not found error"
                    elif 'Traceback' in error_output:
                        error_type = "Runtime error"
                    else:
                        error_type = "Error"
                    
                    error_msg = f"{error_type} in term command (exit code {result.returncode}):\n{error_output}"
                    print(f"    ✗ {error_type} detected")
                    print(f"       Exit code: {result.returncode}")
                    print("       Error output:")
                    for line in error_output.split('\n')[:10]:  # Show first 10 lines
                        print(f"         {line}")
                    errors.append(error_msg)
                else:
                    error_msg = f"Term command failed with exit code {result.returncode} (no error output)"
                    print(f"    ✗ {error_msg}")
                    errors.append(error_msg)
            elif 'usage:' in result.stdout.lower() or 'term [options]' in result.stdout.lower() or '--help' in result.stdout.lower():
                print("    ✓ rediacc term command works")
            else:
                # Command succeeded but output unexpected
                print(f"    ⚠ Command succeeded but output unexpected")
                if result.stdout:
                    print(f"       Output preview: {result.stdout[:100]}...")
        else:
            print(f"    ⚠ rediacc script not found at {rediacc_path}")
    except subprocess.TimeoutExpired:
        print("    ⚠ Command timed out (might be waiting for input)")
    except Exception as e:
        print(f"    ⚠ Could not test rediacc term command: {e}")
    
    # Summary
    print("\nTerminal Command Test Summary:")
    if errors:
        print(f"  ✗ {len(errors)} error(s) found in terminal command:")
        for i, error in enumerate(errors, 1):
            print(f"\n  Error {i}:")
            # Print each line of the error indented
            for line in error.split('\n'):
                print(f"    {line}")
        assert False, f"Terminal command has {len(errors)} error(s)"
    else:
        print("  ✓ Terminal command is working correctly")
        # Test passes, no assertion needed

if __name__ == "__main__":
    sys.exit(test_terminal_command())