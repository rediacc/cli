#!/usr/bin/env python3
"""
Migration script to convert test YAML files to use dynamic endpoint syntax
"""
import argparse
import json
import os
import re
import sys
import yaml
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

class TestMigrator:
    def __init__(self):
        self.cli_config = self._load_cli_config()
        self.command_to_endpoint_map = self._build_command_map()
        self.migrated_count = 0
        self.skipped_count = 0
        
    def _load_cli_config(self) -> dict:
        """Load CLI configuration with command endpoints"""
        cli_config_file = Path(__file__).parent.parent / 'src' / 'config' / 'rediacc-cli.json'
        
        if cli_config_file.exists():
            with open(cli_config_file, 'r') as f:
                return json.load(f) or {}
        return {}
    
    def _build_command_map(self) -> Dict[str, Tuple[str, Dict[str, str]]]:
        """Build mapping from command to endpoint and parameter mapping"""
        command_map = {}
        cmd_config = self.cli_config.get('CMD_CONFIG', {})
        
        for main_cmd, sub_cmds in cmd_config.items():
            if isinstance(sub_cmds, dict):
                # Handle top-level commands
                if 'endpoint' in sub_cmds:
                    command_map[main_cmd] = (sub_cmds['endpoint'], self._extract_param_mapping(sub_cmds))
                
                # Handle sub-commands
                for sub_cmd, config in sub_cmds.items():
                    if isinstance(config, dict) and 'endpoint' in config:
                        command_key = f"{main_cmd}.{sub_cmd}"
                        command_map[command_key] = (config['endpoint'], self._extract_param_mapping(config))
        
        return command_map
    
    def _extract_param_mapping(self, config: dict) -> Dict[str, str]:
        """Extract parameter mapping from lambda string"""
        param_mapping = {}
        params_str = config.get('params', '')
        
        # Parse lambda expressions like:
        # lambda args: {'teamName': args.team, 'currentStorageName': args.current_storage_name}
        if 'lambda args:' in params_str:
            # Extract the dictionary part
            dict_match = re.search(r'{([^}]+)}', params_str)
            if dict_match:
                dict_content = dict_match.group(1)
                # Parse each mapping
                mappings = re.findall(r"'(\w+)':\s*args\.(\w+)", dict_content)
                for api_param, cli_param in mappings:
                    param_mapping[cli_param] = api_param
        
        return param_mapping
    
    def _migrate_test_step(self, step: dict) -> Tuple[dict, bool]:
        """Migrate a single test step to dynamic endpoint format"""
        if 'command' not in step:
            return step, False
        
        command = step['command']
        if not isinstance(command, list) or len(command) < 2:
            return step, False
        
        # Build command key
        main_cmd = command[0]
        
        # Skip if already using dynamic endpoint (starts with uppercase)
        if main_cmd and main_cmd[0].isupper():
            return step, False
        
        # Try to find the endpoint
        endpoint_info = None
        command_key = None
        positional_args = []
        
        if len(command) >= 2 and not command[1].startswith('-'):
            sub_cmd = command[1]
            command_key = f"{main_cmd}.{sub_cmd}"
            positional_args = command[2:] if len(command) > 2 else []
        else:
            command_key = main_cmd
            positional_args = command[1:] if len(command) > 1 else []
        
        if command_key not in self.command_to_endpoint_map:
            return step, False
        
        endpoint, param_mapping = self.command_to_endpoint_map[command_key]
        
        # Create new step with dynamic endpoint
        new_step = step.copy()
        new_step['command'] = [endpoint]
        
        # Migrate positional arguments based on command type
        new_args = step.get('args', {}).copy()
        
        # Handle specific command patterns
        if command_key == "update.storage":
            # update storage <team> <current_name> <new_name>
            if len(positional_args) >= 3:
                new_args['teamName'] = positional_args[0]
                new_args['currentStorageName'] = positional_args[1]  
                new_args['newStorageName'] = positional_args[2]
        elif command_key == "update.machine":
            # update machine <team> <current_name> <new_name>
            if len(positional_args) >= 3:
                new_args['teamName'] = positional_args[0]
                new_args['currentMachineName'] = positional_args[1]
                new_args['newMachineName'] = positional_args[2]
        elif command_key == "update.team":
            # update team <current_name> <new_name>
            if len(positional_args) >= 2:
                new_args['currentTeamName'] = positional_args[0]
                new_args['newTeamName'] = positional_args[1]
        elif command_key == "create.storage":
            # create storage <team> <name>
            if len(positional_args) >= 2:
                new_args['teamName'] = positional_args[0]
                new_args['storageName'] = positional_args[1]
        elif command_key == "create.machine":
            # create machine <team> <bridge> <name>
            if len(positional_args) >= 3:
                new_args['teamName'] = positional_args[0]
                new_args['bridgeName'] = positional_args[1]
                new_args['machineName'] = positional_args[2]
        elif command_key == "create.team":
            # create team <name>
            if len(positional_args) >= 1:
                new_args['teamName'] = positional_args[0]
        elif command_key in ["list.team-storages", "list.team-machines"]:
            # list team-storages <team>
            if len(positional_args) >= 1:
                new_args['teamName'] = positional_args[0]
        elif command_key.startswith("rm."):
            # rm storage <team> <name>
            if len(positional_args) >= 2:
                new_args['teamName'] = positional_args[0]
                if command_key == "rm.storage":
                    new_args['storageName'] = positional_args[1]
                elif command_key == "rm.machine":
                    new_args['machineName'] = positional_args[1]
        
        # Update args if we added any
        if new_args != step.get('args', {}):
            new_step['args'] = new_args
        elif 'args' in new_step and not new_args:
            # Remove empty args
            del new_step['args']
        
        return new_step, True
    
    def migrate_test_file(self, file_path: Path, dry_run: bool = False) -> bool:
        """Migrate a single test YAML file"""
        print(f"\nProcessing: {file_path}")
        
        try:
            with open(file_path, 'r') as f:
                content = yaml.safe_load(f)
            
            if not content:
                print(f"  Skip: Empty file")
                return False
            
            modified = False
            
            # Migrate setup steps
            if 'setup' in content and isinstance(content['setup'], list):
                for i, step in enumerate(content['setup']):
                    new_step, migrated = self._migrate_test_step(step)
                    if migrated:
                        content['setup'][i] = new_step
                        modified = True
                        print(f"  Migrated setup step: {step.get('name', f'Step {i}')}")
            
            # Migrate test steps
            if 'tests' in content and isinstance(content['tests'], list):
                for i, step in enumerate(content['tests']):
                    new_step, migrated = self._migrate_test_step(step)
                    if migrated:
                        content['tests'][i] = new_step
                        modified = True
                        print(f"  Migrated test: {step.get('name', f'Test {i}')}")
            
            if modified:
                self.migrated_count += 1
                if not dry_run:
                    # Create backup
                    backup_path = file_path.with_suffix('.yaml.bak')
                    with open(backup_path, 'w') as f:
                        with open(file_path, 'r') as orig:
                            f.write(orig.read())
                    
                    # Write migrated content
                    with open(file_path, 'w') as f:
                        yaml.dump(content, f, default_flow_style=False, sort_keys=False)
                    
                    print(f"  ✓ Migrated successfully (backup: {backup_path.name})")
                else:
                    print(f"  ✓ Would migrate (dry run)")
            else:
                self.skipped_count += 1
                print(f"  - No changes needed")
            
            return modified
            
        except Exception as e:
            print(f"  ✗ Error: {e}")
            return False
    
    def migrate_directory(self, directory: Path, pattern: str = "*.yaml", dry_run: bool = False):
        """Migrate all test files in a directory"""
        test_files = list(directory.rglob(pattern))
        
        # Exclude config.yaml
        test_files = [f for f in test_files if f.name != 'config.yaml']
        
        print(f"Found {len(test_files)} test files to process")
        
        for test_file in sorted(test_files):
            self.migrate_test_file(test_file, dry_run)
        
        print(f"\n{'='*60}")
        print(f"Migration Summary:")
        print(f"  Files migrated: {self.migrated_count}")
        print(f"  Files unchanged: {self.skipped_count}")
        print(f"  Total processed: {self.migrated_count + self.skipped_count}")
        
        if dry_run:
            print(f"\nThis was a DRY RUN. No files were modified.")
            print(f"Run without --dry-run to apply changes.")

def main():
    parser = argparse.ArgumentParser(description='Migrate test YAML files to use dynamic endpoint syntax')
    parser.add_argument('path', nargs='?', default='yaml',
                        help='Test file or directory path (default: yaml)')
    parser.add_argument('--dry-run', action='store_true',
                        help='Show what would be changed without modifying files')
    parser.add_argument('--pattern', default='*.yaml',
                        help='File pattern to match (default: *.yaml)')
    
    args = parser.parse_args()
    
    # Resolve path
    path = Path(args.path)
    if not path.is_absolute():
        path = Path(__file__).parent / path
    
    if not path.exists():
        print(f"Error: Path not found: {path}")
        sys.exit(1)
    
    migrator = TestMigrator()
    
    if path.is_file():
        success = migrator.migrate_test_file(path, args.dry_run)
        sys.exit(0 if success else 1)
    elif path.is_dir():
        migrator.migrate_directory(path, args.pattern, args.dry_run)
    else:
        print(f"Error: Invalid path: {path}")
        sys.exit(1)

if __name__ == '__main__':
    main()