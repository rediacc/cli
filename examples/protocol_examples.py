#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Example usage of the rediacc:// protocol handler

This script demonstrates how to generate and test rediacc:// URLs
that can be used for browser integration.
"""

import sys
import os

# Add src directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from cli.core.protocol_handler import ProtocolUrlParser, get_protocol_status

def print_separator():
    """Print a separator line"""
    print("=" * 60)

def example_url_generation():
    """Demonstrate URL generation examples"""
    print("rediacc:// URL Examples")
    print_separator()
    
    # Base parameters
    base_params = {
        "token": "abc123-def456-ghi789",
        "team": "Production",
        "machine": "web-server-01",
        "repository": "webapp"
    }
    
    # Sync examples
    print("1. SYNC OPERATIONS:")
    print(f"   Upload: rediacc://{base_params['token']}/{base_params['team']}/{base_params['machine']}/{base_params['repository']}/sync?direction=upload&localPath=C:\\MyProject&mirror=true")
    print(f"   Download: rediacc://{base_params['token']}/{base_params['team']}/{base_params['machine']}/{base_params['repository']}/sync?direction=download&localPath=C:\\Backup&verify=true")
    print()
    
    # Terminal examples
    print("2. TERMINAL ACCESS:")
    print(f"   Repository Terminal: rediacc://{base_params['token']}/{base_params['team']}/{base_params['machine']}/{base_params['repository']}/terminal")
    print(f"   Execute Command: rediacc://{base_params['token']}/{base_params['team']}/{base_params['machine']}/{base_params['repository']}/terminal?command=ls%20-la")
    print(f"   Machine Terminal: rediacc://{base_params['token']}/{base_params['team']}/{base_params['machine']}/{base_params['repository']}/terminal?terminalType=machine")
    print()
    
    # Plugin examples
    print("3. PLUGIN ACCESS:")
    print(f"   Start Plugin: rediacc://{base_params['token']}/{base_params['team']}/{base_params['machine']}/{base_params['repository']}/plugin?name=jupyter&port=8888")
    print()
    
    # Browser examples
    print("4. FILE BROWSER:")
    print(f"   Browse Files: rediacc://{base_params['token']}/{base_params['team']}/{base_params['machine']}/{base_params['repository']}/browser?path=/var/log")
    print()

def example_url_parsing():
    """Demonstrate URL parsing functionality"""
    print("URL Parsing Examples")
    print_separator()
    
    parser = ProtocolUrlParser()
    
    # Test URLs
    test_urls = [
        "rediacc://token123/TeamA/ServerB/RepoC/sync?direction=upload&localPath=C:\\data",
        "rediacc://token456/TeamX/ServerY/RepoZ/terminal?command=ls%20-la",
        "rediacc://token789/TeamQ/ServerP/RepoM/plugin?name=jupyter&port=8888"
    ]
    
    for i, url in enumerate(test_urls, 1):
        print(f"{i}. Parsing URL:")
        print(f"   URL: {url}")
        
        try:
            parsed = parser.parse_url(url)
            print(f"   Token: {parsed['token']}")
            print(f"   Team: {parsed['team']}")
            print(f"   Machine: {parsed['machine']}")
            print(f"   Repository: {parsed['repository']}")
            print(f"   Action: {parsed['action']}")
            print(f"   Parameters: {parsed['params']}")
            
            # Build CLI command
            cmd_args = parser.build_cli_command(parsed)
            print(f"   CLI Command: {' '.join(cmd_args)}")
            
        except Exception as e:
            print(f"   ERROR: {e}")
        
        print()

def example_protocol_status():
    """Demonstrate protocol status checking"""
    print("Protocol Registration Status")
    print_separator()
    
    try:
        status = get_protocol_status()
        
        print(f"Platform: {status.get('platform', 'unknown')}")
        print(f"Supported: {status.get('supported', False)}")
        
        if status.get('supported'):
            print(f"Registered: {status.get('registered', False)}")
            print(f"Admin Privileges: {status.get('admin_privileges', False)}")
            print(f"Python Executable: {status.get('python_executable', 'not found')}")
            print(f"CLI Script: {status.get('cli_script', 'not found')}")
            
            if status.get('registered'):
                current_cmd = status.get('command', 'not found')
                expected_cmd = status.get('expected_command', 'not found')
                print(f"Current Command: {current_cmd}")
                
                if current_cmd != expected_cmd:
                    print(f"Expected Command: {expected_cmd}")
                    print("WARNING: Current registration may be outdated")
        else:
            print(f"Message: {status.get('message', 'Protocol registration not supported')}")
    
    except Exception as e:
        print(f"ERROR: {e}")
    
    print()

def example_cli_integration():
    """Show CLI integration examples"""
    print("CLI Integration Examples")
    print_separator()
    
    print("To register the protocol:")
    print("  rediacc --register-protocol")
    print("  # or")
    print("  .\\rediacc.ps1 -RegisterProtocol")
    print()
    
    print("To check protocol status:")
    print("  rediacc --protocol-status")
    print("  # or")
    print("  .\\rediacc.ps1 -ProtocolStatus")
    print()
    
    print("To unregister the protocol:")
    print("  rediacc --unregister-protocol")
    print("  # or")
    print("  .\\rediacc.ps1 -UnregisterProtocol")
    print()
    
    print("Browser Integration:")
    print("  1. Register the protocol (requires admin privileges on Windows)")
    print("  2. Restart your browser")
    print("  3. Click on any rediacc:// link or paste into address bar")
    print("  4. Browser will automatically launch the appropriate CLI tool")
    print()

def main():
    """Run all examples"""
    print("Rediacc Protocol Handler Examples")
    print("=" * 60)
    print()
    
    example_url_generation()
    print()
    
    example_url_parsing()
    print()
    
    example_protocol_status()
    print()
    
    example_cli_integration()
    
    print("For more information, see:")
    print("- /home/muhammed/monorepo/cli/src/cli/core/protocol_handler.py")
    print("- /home/muhammed/monorepo/cli/tests/test_protocol_handler.py")

if __name__ == "__main__":
    main()