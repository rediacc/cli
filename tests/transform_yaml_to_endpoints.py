#!/usr/bin/env python3
"""
Transform YAML test files to use endpoint style instead of CLI commands
"""
import yaml
import json
from pathlib import Path
import re

# Load procedures.json to get endpoint names
procedures_path = Path(__file__).parent.parent.parent / 'middleware/AppData/procedures.json'
with open(procedures_path) as f:
    procedures = json.load(f)

# Known command mappings
COMMAND_MAPPINGS = {
    # Simple mappings
    'login': 'CreateAuthenticationRequest',
    'logout': 'DeleteUserRequest',
    
    # Multi-part command mappings
    ('company', 'block-user-requests'): 'UpdateCompanyBlockUserRequests',
    ('company', 'update-vault'): 'UpdateCompanyVault',
    ('user', 'delete'): 'DeleteUser',
    ('user', 'update-password'): 'UpdateUserPassword',
    ('user', 'tfa'): 'UpdateUserTFA',
    ('team', 'create'): 'CreateTeam',
    ('team', 'delete'): 'DeleteTeam',
    ('team', 'update-vault'): 'UpdateTeamVault',
    ('machine', 'create'): 'CreateMachine',
    ('machine', 'delete'): 'DeleteMachine',
    ('machine', 'update-vault'): 'UpdateMachineVault',
    ('bridge', 'create'): 'CreateBridge',
    ('bridge', 'delete'): 'DeleteBridge',
    ('repository', 'create'): 'CreateRepository',
    ('repository', 'delete'): 'DeleteRepository',
    ('queue', 'create'): 'CreateQueueItem',
    ('queue', 'cancel'): 'CancelQueueItem',
    ('storage', 'create'): 'CreateStorageSystem',
    ('storage', 'delete'): 'DeleteStorageSystem',
    ('schedule', 'create'): 'CreateSchedule',
    ('schedule', 'delete'): 'DeleteSchedule',
}

def transform_command(command, args=None):
    """Transform a command to endpoint style"""
    if isinstance(command, list):
        # Check for multi-part command mapping
        if len(command) >= 2:
            key = tuple(command[:2])
            if key in COMMAND_MAPPINGS:
                endpoint = COMMAND_MAPPINGS[key]
                # Handle special cases where additional args come from command parts
                if key == ('company', 'block-user-requests') and len(command) > 2:
                    if args is None:
                        args = {}
                    args['blockUserRequests'] = command[2].lower() == 'true'
                elif key == ('user', 'tfa') and len(command) > 2:
                    if args is None:
                        args = {}
                    # Handle enable/disable
                    if command[2] == 'enable':
                        args['enable'] = True
                    elif command[2] == 'disable':
                        args['enable'] = False
                return endpoint, args
        
        # Single command
        cmd = command[0]
    else:
        cmd = command
    
    # Check simple mappings
    if cmd in COMMAND_MAPPINGS:
        return COMMAND_MAPPINGS[cmd], args
    
    # Check if it's already an endpoint
    if cmd in procedures:
        return cmd, args
    
    # Try to find a matching endpoint by name similarity
    # Convert kebab-case to PascalCase
    pascal_case = ''.join(word.capitalize() for word in cmd.split('-'))
    if pascal_case in procedures:
        return pascal_case, args
    
    # Try with common prefixes
    for prefix in ['Get', 'Create', 'Update', 'Delete', 'List']:
        endpoint = prefix + pascal_case
        if endpoint in procedures:
            return endpoint, args
    
    # Return as-is if no mapping found
    print(f"Warning: No endpoint mapping found for command: {command}")
    return cmd, args

def transform_test_spec(spec):
    """Transform a test specification"""
    if 'command' in spec:
        endpoint, new_args = transform_command(spec['command'], spec.get('args'))
        spec['command'] = [endpoint] if isinstance(endpoint, str) else endpoint
        if new_args is not None:
            spec['args'] = new_args
    return spec

def transform_yaml_file(file_path):
    """Transform a single YAML file"""
    print(f"Transforming {file_path}...")
    
    with open(file_path) as f:
        data = yaml.safe_load(f)
    
    # Transform setup commands
    if 'setup' in data:
        for i, setup in enumerate(data['setup']):
            data['setup'][i] = transform_test_spec(setup)
    
    # Transform test commands
    if 'tests' in data:
        for i, test in enumerate(data['tests']):
            data['tests'][i] = transform_test_spec(test)
    
    # Save the transformed file
    with open(file_path, 'w') as f:
        yaml.dump(data, f, default_flow_style=False, sort_keys=False, allow_unicode=True)
    
    print(f"  ✓ Transformed {file_path.name}")

def main():
    """Transform all YAML test files"""
    yaml_dir = Path(__file__).parent / 'yaml/community'
    
    for yaml_file in sorted(yaml_dir.glob('*.yaml')):
        try:
            transform_yaml_file(yaml_file)
        except Exception as e:
            print(f"  ✗ Error transforming {yaml_file.name}: {e}")

if __name__ == '__main__':
    main()