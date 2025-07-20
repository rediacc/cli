#!/usr/bin/env python3
"""Debug bridge operations"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Load env
from tests_yaml.run import load_env_file
load_env_file()

from tests_yaml.framework.cli_wrapper import CLIWrapper

# Create wrapper
cli = CLIWrapper(verbose=True)

# Login
result = cli.login('test_3223@example.com', 'TestPass3223!')
print(f"Login result: {result.get('success')}")

if result.get('success'):
    # Create a test region
    region_result = cli.create('region', name='test-region-debug', vault={'config': 'test'})
    print(f"Region creation: {region_result.get('success')}")
    
    if region_result.get('success'):
        # Create bridge
        bridge_result = cli.create('bridge', region='test-region-debug', name='test-bridge-debug', vault={'config': 'test'})
        print(f"\nBridge creation: {bridge_result}")
        
        # Inspect bridge
        inspect_result = cli.get('bridge', 'test-bridge-debug', region='test-region-debug')
        print(f"\nBridge inspection: {inspect_result}")
        
        # Cleanup
        cli.delete('bridge', 'test-bridge-debug')
        cli.delete('region', 'test-region-debug')