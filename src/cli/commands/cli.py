#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Rediacc CLI - Complete command-line interface for Rediacc Middleware API
Includes all functionality from both CLI and test suite with enhanced queue support
"""

import argparse
import getpass
import hashlib
import json
import os
import sys
import base64
from typing import Dict, Any, Optional, List, Union
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cli._version import __version__
from core.config import (
    load_config, get_required, get, get_path, ConfigError,
    TokenManager, api_mutex, setup_logging, get_logger
)

from core.shared import colorize, COLORS
from core.api_client import client
from commands.workflow import WorkflowHandler

try:
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    CRYPTO_AVAILABLE = True
except ImportError:
    CRYPTO_AVAILABLE = False

import time
import datetime

try:
    load_config()
except ConfigError as e:
    print(f"Configuration error: {e}", file=sys.stderr)
    sys.exit(1)

from core.config import get_config_dir, get_main_config_file

HTTP_PORT = get_required('SYSTEM_HTTP_PORT')
BASE_URL = get_required('SYSTEM_API_URL')
API_PREFIX = '/StoredProcedure'
CONFIG_DIR = str(get_config_dir())
CONFIG_FILE = str(get_main_config_file())
REQUEST_TIMEOUT = 30
TEST_ACTIVATION_CODE = get('REDIACC_TEST_ACTIVATION_CODE') or '111111'

if not CRYPTO_AVAILABLE:
    print(colorize("Warning: cryptography library not installed. Vault encryption will not be available.", 'YELLOW'), file=sys.stderr)
    if os.environ.get('MSYSTEM') or (sys.platform == 'win32' and ('/msys' in sys.executable.lower() or '/mingw' in sys.executable.lower())):
        print(colorize("For MSYS2: Run 'pacman -S mingw-w64-x86_64-python-cryptography' or './scripts/install_msys2_packages.sh'", 'YELLOW'), file=sys.stderr)
    else:
        print(colorize("Install with: pip install cryptography", 'YELLOW'), file=sys.stderr)

CLI_CONFIG_PATH = Path(__file__).parent.parent.parent / 'config' / 'rediacc.json'
try:
    with open(CLI_CONFIG_PATH, 'r') as f:
        cli_config = json.load(f)
        QUEUE_FUNCTIONS = cli_config['QUEUE_FUNCTIONS']
        API_ENDPOINTS_JSON = cli_config['API_ENDPOINTS']
        CLI_COMMANDS_JSON = cli_config['CLI_COMMANDS']
except Exception as e:
    print(colorize(f"Error loading CLI configuration from {CLI_CONFIG_PATH}: {e}", 'RED'))
    sys.exit(1)

ITERATIONS = 100000
SALT_SIZE = 16
IV_SIZE = 12
TAG_SIZE = 16
KEY_SIZE = 32

def derive_key(password: str, salt: bytes) -> bytes:
    if not CRYPTO_AVAILABLE:
        raise RuntimeError("Cryptography library not available")
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=KEY_SIZE,
        salt=salt,
        iterations=ITERATIONS,
    )
    return kdf.derive(password.encode('utf-8'))

def encrypt_string(plaintext: str, password: str) -> str:
    if not CRYPTO_AVAILABLE:
        raise RuntimeError("Cryptography library not available")
    salt = os.urandom(SALT_SIZE)
    iv = os.urandom(IV_SIZE)
    key = derive_key(password, salt)
    aesgcm = AESGCM(key)
    ciphertext = aesgcm.encrypt(iv, plaintext.encode('utf-8'), None)
    combined = salt + iv + ciphertext
    return base64.b64encode(combined).decode('ascii')

def decrypt_string(encrypted: str, password: str) -> str:
    if not CRYPTO_AVAILABLE:
        raise RuntimeError("Cryptography library not available")
    combined = base64.b64decode(encrypted)
    salt = combined[:SALT_SIZE]
    iv = combined[SALT_SIZE:SALT_SIZE + IV_SIZE]
    ciphertext = combined[SALT_SIZE + IV_SIZE:]
    key = derive_key(password, salt)
    aesgcm = AESGCM(key)
    plaintext = aesgcm.decrypt(iv, ciphertext, None)
    return plaintext.decode('utf-8')

def is_encrypted(value: str) -> bool:
    if not value or len(value) < 20: return False
    try: json.loads(value); return False
    except:
        import re
        return bool(re.match(r'^[A-Za-z0-9+/]+=*$', value) and len(value) >= 40)

def encrypt_vault_fields(obj: dict, password: str) -> dict:
    if not password or not obj: return obj
    
    def encrypt_field(key: str, value: Any) -> Any:
        if 'vault' in key.lower() and isinstance(value, str) and value and not is_encrypted(value):
            try: return encrypt_string(value, password)
            except Exception as e: print(colorize(f"Warning: Failed to encrypt field {key}: {e}", 'YELLOW'))
        return value
    
    return {
        key: encrypt_field(key, value) if isinstance(value, str)
        else encrypt_vault_fields(value, password) if isinstance(value, dict)
        else [encrypt_vault_fields(item, password) if isinstance(item, dict) else item for item in value] if isinstance(value, list)
        else value
        for key, value in obj.items()
    }

def decrypt_vault_fields(obj: dict, password: str) -> dict:
    if not password or not obj: return obj
    
    def decrypt_field(key: str, value: Any) -> Any:
        if 'vault' in key.lower() and isinstance(value, str) and value and is_encrypted(value):
            try: return decrypt_string(value, password)
            except Exception as e: print(colorize(f"Warning: Failed to decrypt field {key}: {e}", 'YELLOW'))
        return value
    
    return {
        key: decrypt_field(key, value) if isinstance(value, str)
        else decrypt_vault_fields(value, password) if isinstance(value, dict)
        else [decrypt_vault_fields(item, password) if isinstance(item, dict) else item for item in value] if isinstance(value, list)
        else value
        for key, value in obj.items()
    }

def reconstruct_cmd_config():
    def process_value(value):
        if not isinstance(value, dict): return value
        if 'params' in value and isinstance(value['params'], str) and value['params'].startswith('lambda'):
            value = value.copy(); value['params'] = eval(value['params']); return value
        return {k: process_value(v) if isinstance(v, dict) else v for k, v in value.items()}
    return {key: process_value(value) for key, value in API_ENDPOINTS_JSON.items()}

def reconstruct_arg_defs():
    def process_arg(arg):
        if not isinstance(arg, dict) or 'type' not in arg: return arg
        arg = arg.copy()
        if isinstance(arg['type'], str):
            arg['type'] = eval(arg['type']) if arg['type'].startswith('lambda') else int if arg['type'] == 'int' else arg['type']
        return arg
    
    def process_value(value):
        return [process_arg(arg) for arg in value] if isinstance(value, list) else \
               {k: process_value(v) if isinstance(v, (list, dict)) else v for k, v in value.items()} if isinstance(value, dict) else value
    
    return {key: process_value(value) for key, value in CLI_COMMANDS_JSON.items()}

API_ENDPOINTS = reconstruct_cmd_config()
CLI_COMMANDS = reconstruct_arg_defs()

def APIClient(config_manager):
    """Create CLI client instance by setting config manager on singleton"""
    client.set_config_manager(config_manager)
    return client

def format_output(data, format_type, message=None, error=None):
    if format_type in ['json', 'json-full']:
        output = {'success': error is None, 'data': data}
        if message: output['message'] = message
        if error: output['error'] = error
        return json.dumps(output, indent=2)
    return colorize(f"Error: {error}", 'RED') if error else data if data else colorize(message, 'GREEN') if message else "No data available"

STATIC_SALT = 'Rd!@cc111$ecur3P@$$w0rd$@lt#H@$h'

def pwd_hash(pwd):
    salted_password = pwd + STATIC_SALT
    return "0x" + hashlib.sha256(salted_password.encode()).digest().hex()

def extract_table_data(response, table_index=0):
    return response.get('resultSets', [])[table_index].get('data', []) if response and len(response.get('resultSets', [])) > table_index else []

def get_vault_data(args):
    if not (hasattr(args, 'vault_file') and args.vault_file): return getattr(args, 'vault', '{}') or '{}'
    try: return json.dumps(json.loads(sys.stdin.read()) if args.vault_file == '-' else json.load(open(args.vault_file, 'r')))
    except (IOError, json.JSONDecodeError) as e: print(colorize(f"Warning: Could not load vault data: {e}", 'YELLOW')); return '{}'

def get_vault_set_params(args, config_manager=None):
    if args.file and args.file != '-':
        try: vault_data = open(args.file, 'r').read()
        except IOError: print(colorize(f"Error: Could not read file: {args.file}", 'RED')); return None
    else:
        print("Enter JSON vault data (press Ctrl+D when finished):")
        vault_data = sys.stdin.read()
    
    try: json.loads(vault_data)
    except json.JSONDecodeError as e: print(colorize(f"Error: Invalid JSON: {str(e)}", 'RED')); return None
    
    params = {'vaultVersion': args.vault_version or 1}
    
    resource_mappings = {
        'team': {'teamName': args.name, 'teamVault': vault_data},
        'machine': {'teamName': args.team, 'machineName': args.name, 'machineVault': vault_data},
        'region': {'regionName': args.name, 'regionVault': vault_data},
        'bridge': {'regionName': args.region, 'bridgeName': args.name, 'bridgeVault': vault_data},
        'repository': {'teamName': args.team, 'repoName': args.name, 'repoVault': vault_data},
        'storage': {'teamName': args.team, 'storageName': args.name, 'storageVault': vault_data},
        'schedule': {'teamName': args.team, 'scheduleName': args.name, 'scheduleVault': vault_data}
    }
    
    if args.resource_type == 'company':
        if args.name and args.name.strip():
            print(colorize(f"Note: Company name '{args.name}' is ignored. You can only update your own company's vault.", 'YELLOW'))
        params['companyVault'] = vault_data
    else:
        params.update(resource_mappings.get(args.resource_type, {}))
    
    return params

def camel_to_title(name):
    special_cases = {
        'vaultVersion': 'Vault Version', 'vaultContent': 'Vault Content',
        'memberCount': 'Members', 'machineCount': 'Machines',
        'bridgeCount': 'Bridges', 'repoCount': 'Repos',
        'storageCount': 'Storage', 'scheduleCount': 'Schedules',
        'queueCount': 'Queue Items', 'teamName': 'Team',
        'regionName': 'Region', 'bridgeName': 'Bridge',
        'machineName': 'Machine', 'repoName': 'Repository',
        'storageName': 'Storage', 'scheduleName': 'Schedule',
        'userEmail': 'Email', 'companyName': 'Company',
        'hasAccess': 'Access', 'isMember': 'Member',
        'activated': 'Active', 'taskId': 'Task ID',
        'itemCount': 'Count', 'newUserEmail': 'Email',
        'permissionGroupName': 'Permission Group',
        'permissionName': 'Permission', 'subscriptionPlan': 'Plan',
        'maxTeams': 'Max Teams', 'maxRegions': 'Max Regions',
        'maxMachines': 'Max Machines', 'maxStorage': 'Max Storage',
        'sessionName': 'Session', 'createdAt': 'Created',
        'updatedAt': 'Updated', 'lastActive': 'Last Active',
        'auditId': 'Audit ID', 'entityName': 'Entity Name',
        'actionByUser': 'Action By', 'timestamp': 'Timestamp',
        'details': 'Details', 'action': 'Action',
        'entity': 'Entity', 'entityId': 'Entity ID',
        'userId': 'User ID', 'changeType': 'Change Type',
        'previousValue': 'Previous Value', 'newValue': 'New Value',
        'propertyName': 'Property', 'changeDetails': 'Change Details',
        'bridgeCredentialsVersion': 'Bridge Credentials Version',
        'bridgeCredentials': 'Bridge Credentials',
        'bridgeUserEmail': 'Bridge User Email'
    }
    
    return special_cases.get(name, ''.join(' ' + char if char.isupper() and i > 0 else char 
                                          for i, char in enumerate(name)).strip().title())

def format_table(headers, rows):
    if not rows:
        return "No items found"
    
    widths = [max(len(h), max(len(str(row[i])) for row in rows if i < len(row))) for i, h in enumerate(headers)]
    
    header_line = '  '.join(h.ljust(w) for h, w in zip(headers, widths))
    separator = '-' * len(header_line)
    formatted_rows = ['  '.join(str(cell).ljust(w) for cell, w in zip(row, widths)) for row in rows]
    
    return '\n'.join([header_line, separator] + formatted_rows)

def format_dynamic_tables(response, output_format='text', skip_fields=None):
    if not response or 'resultSets' not in response:
        return format_output("No data available", output_format)
    
    resultSets = response.get('resultSets', [])
    if len(resultSets) <= 1:
        return format_output("No records found", output_format)
    
    skip_fields = skip_fields or ['nextRequestToken', 'newUserHash']
    
    def process_table_data(table):
        data = table.get('data', [])
        if not data:
            return None
            
        processed_data = [{k: v for k, v in record.items() if k not in skip_fields} for record in data]
        return processed_data if any(processed_data) else None
    
    if output_format == 'json':
        result = []
        for table in resultSets[1:]:
            processed = process_table_data(table)
            if processed:
                result.extend(processed)
        return format_output(result, output_format)
    
    if output_format == 'json-full':
        # Return the complete response with all resultSets for json-full
        return format_output({'resultSets': resultSets}, output_format)
    
    output_parts = []
    for table in resultSets[1:]:
        data = table.get('data', [])
        if not data:
            continue
        
        all_keys = set().union(*(record.keys() for record in data))
        display_keys = sorted(k for k in all_keys if k not in skip_fields)
        
        if not display_keys:
            continue
        
        headers = [camel_to_title(key) for key in display_keys]
        rows = [[str(record.get(key, '')) for key in display_keys] for record in data]
        
        if rows:
            output_parts.append(format_table(headers, rows))
    
    return format_output('\n\n'.join(output_parts) if output_parts else "No records found", output_format)

def build_queue_vault_data(function_name, args):
    func_def = QUEUE_FUNCTIONS.get(function_name)
    if not func_def:
        return None
    
    params = {}
    for param_name, param_info in func_def.get('params', {}).items():
        value = getattr(args, param_name, param_info.get('default'))
        if value is not None or param_info.get('required', False):
            params[param_name] = value
    
    vault_data = {
        'type': 'bash_function',
        'function': function_name,
        'params': params,
        'description': args.description or func_def.get('description', ''),
        'priority': args.priority,
        'bridge': args.bridge
    }
    
    return json.dumps(vault_data)

def generate_hardware_id():
    """Generate hardware ID using SuperClient"""
    return client.get_hardware_id()

def request_license_from_server(hardware_id, base_url=None):
    """Request license from server using SuperClient"""
    return client.request_license(hardware_id, base_url)

def install_license_file(license_file, target_path=None):
    if not os.path.exists(license_file):
        raise FileNotFoundError(f"License file not found: {license_file}")
    
    if not target_path:
        possible_paths = [
            ".", "./bin", "../middleware",
            "../middleware/bin/Debug/net8.0",
            "../middleware/bin/Release/net8.0",
        ]
        
        target_path = next(
            (path for path in possible_paths if os.path.exists(path) and os.path.isdir(path)),
            "."
        )
    
    os.makedirs(target_path, exist_ok=True)
    
    target_file = os.path.join(target_path, "license.lic")
    import shutil
    shutil.copy2(license_file, target_file)
    
    return target_file

class VaultBuilder:
    """Build queue vault data similar to console's queueDataService"""
    
    def __init__(self, client):
        self.client = client
        self.company_vault = None
        self._vault_fetched = False
        
    def _fetch_company_vault(self):
        """Fetch company vault data from API"""
        if self._vault_fetched:
            return self.company_vault
            
        try:
            response = self.client.token_request("GetCompanyVault", {})
            if response.get('error'):
                return None
                
            # Company vault data might be in first or second table
            resultSets = response.get('resultSets', [])
            for i, table in enumerate(resultSets):
                if table.get('data') and len(table['data']) > 0:
                    vault_data = table['data'][0]
                    if 'vaultContent' in vault_data or 'VaultContent' in vault_data:
                        vault_content = vault_data.get('vaultContent') or vault_data.get('VaultContent', '{}')
                        company_credential = vault_data.get('companyCredential') or vault_data.get('CompanyCredential')
                        try:
                            parsed_vault = json.loads(vault_content) if vault_content and vault_content != '-' else {}
                            # Add the CompanyCredential as COMPANY_ID to the vault data
                            if company_credential:
                                parsed_vault['COMPANY_ID'] = company_credential
                            self.company_vault = parsed_vault
                            break
                        except json.JSONDecodeError:
                            self.company_vault = {}
            self._vault_fetched = True
            return self.company_vault
        except Exception:
            return None
    
    def _parse_vault(self, vault_content):
        """Parse vault content from string to dict"""
        if not vault_content or vault_content == '-':
            return {}
        try:
            return json.loads(vault_content) if isinstance(vault_content, str) else vault_content
        except json.JSONDecodeError:
            return {}
    
    def _build_general_settings(self, context):
        """Build GENERAL_SETTINGS object from context"""
        general_settings = {}
        
        # Add company vault data
        company_vault = context.get('companyVault', {})
        if company_vault:
            for field in ['UNIVERSAL_USER_ID', 'UNIVERSAL_USER_NAME', 'DOCKER_JSON_CONF', 'PLUGINS']:
                if field in company_vault:
                    general_settings[field] = company_vault[field]
            
            # Handle SSH keys
            for ssh_field in ['SSH_PRIVATE_KEY', 'SSH_PUBLIC_KEY']:
                if ssh_field in company_vault:
                    general_settings[ssh_field] = self._ensure_base64(company_vault[ssh_field])
        
        # Add team vault data (overrides company data)
        team_vault = context.get('teamVault', {})
        if team_vault:
            # Debug: print team vault keys
            if os.environ.get('REDIACC_VERBOSE'):
                print(f"DEBUG: Team vault keys: {list(team_vault.keys())}")
            
            for ssh_field in ['SSH_PRIVATE_KEY', 'SSH_PUBLIC_KEY']:
                if ssh_field in team_vault:
                    general_settings[ssh_field] = self._ensure_base64(team_vault[ssh_field])
                    if os.environ.get('REDIACC_VERBOSE'):
                        print(f"DEBUG: Added {ssh_field} to GENERAL_SETTINGS")
                else:
                    if os.environ.get('REDIACC_VERBOSE'):
                        print(f"DEBUG: {ssh_field} not found in team vault")
        
        return general_settings
    
    def _ensure_base64(self, value):
        """Ensure a string is in base64 format"""
        if not value:
            return value
            
        # Check if already base64
        import re
        base64_pattern = r'^[A-Za-z0-9+/]*={0,2}$'
        value_clean = re.sub(r'\s', '', value)  # Remove all whitespace
        
        if re.match(base64_pattern, value_clean) and len(value_clean) % 4 == 0:
            return value
        
        # Encode to base64
        try:
            return base64.b64encode(value.encode('utf-8')).decode('ascii')
        except Exception:
            return value
    
    def _extract_machine_data(self, machine_vault):
        """Extract machine data for general settings"""
        if not machine_vault:
            return {}
            
        vault = self._parse_vault(machine_vault)
        result = {}
        
        # Map fields to expected format
        field_mappings = [
            ('IP', ['ip', 'IP']),
            ('USER', ['user', 'USER']),
            ('DATASTORE', ['datastore', 'DATASTORE']),
            ('HOST_ENTRY', ['host_entry', 'HOST_ENTRY'])
        ]
        
        for target_key, source_keys in field_mappings:
            for source_key in source_keys:
                if source_key in vault:
                    result[target_key] = vault[source_key]
                    break
                    
        return result
    
    def build_for_function(self, function_name, context):
        """Build queue vault for a specific function"""
        # Get function requirements from QUEUE_FUNCTIONS
        func_def = QUEUE_FUNCTIONS.get(function_name, {})
        requirements = func_def.get('requirements', {})
        
        
        # Fetch company vault if not already fetched
        if not self._vault_fetched:
            self._fetch_company_vault()
        
        # Parse all vault data
        vaults = {
            'companyVault': self.company_vault or {},
            'teamVault': self._parse_vault(context.get('teamVault', '{}')),
            'machineVault': self._parse_vault(context.get('machineVault', '{}')),
            'repositoryVault': self._parse_vault(context.get('repositoryVault', '{}')),
            'bridgeVault': self._parse_vault(context.get('bridgeVault', '{}')),
            'storageVault': self._parse_vault(context.get('storageVault', '{}'))
        }
        
        # Build base vault structure
        vault_data = {
            'function': function_name,
            'machine': context.get('machineName', ''),
            'team': context.get('teamName', ''),
            'params': context.get('params', {}),
            'contextData': {
                'GENERAL_SETTINGS': self._build_general_settings(vaults)
            }
        }
        
        # Add machine data if required
        if requirements.get('machine') and context.get('machineName') and vaults['machineVault']:
            if 'MACHINES' not in vault_data['contextData']:
                vault_data['contextData']['MACHINES'] = {}
            vault_data['contextData']['MACHINES'][context['machineName']] = self._extract_machine_data(vaults['machineVault'])
        
        # Add repository credentials if required
        if requirements.get('repository') and context.get('repositoryGuid') and vaults['repositoryVault']:
            repo_vault = vaults['repositoryVault']
            if repo_vault.get('credential'):
                vault_data['contextData']['REPO_CREDENTIALS'] = {
                    context['repositoryGuid']: repo_vault['credential']
                }
        
        # Add plugins for specific functions
        if function_name in ['mount', 'unmount', 'new', 'up'] and self.company_vault and self.company_vault.get('PLUGINS'):
            vault_data['contextData']['PLUGINS'] = self.company_vault['PLUGINS']
        
        # Add company data if required
        if requirements.get('company') and self.company_vault:
            vault_data['contextData']['company'] = {
                'UNIVERSAL_USER_ID': self.company_vault.get('UNIVERSAL_USER_ID'),
                'UNIVERSAL_USER_NAME': self.company_vault.get('UNIVERSAL_USER_NAME'),
                'DOCKER_JSON_CONF': self.company_vault.get('DOCKER_JSON_CONF'),
                'LOG_FILE': self.company_vault.get('LOG_FILE'),
                'REPO_CREDENTIALS': self.company_vault.get('REPO_CREDENTIALS'),
                'PLUGINS': self.company_vault.get('PLUGINS')
            }
        
        # Add bridge data if required
        if requirements.get('bridge') and context.get('bridgeName') and vaults['bridgeVault']:
            vault_data['contextData']['bridge'] = {
                'name': context['bridgeName'],
                **vaults['bridgeVault']
            }
        
        return minifyJSON(json.dumps(vault_data))
    
    def build_for_repo_create(self, team_name, machine_name, repo_name, repo_guid, size='1G', team_vault=None, machine_vault=None):
        """Build vault specifically for repository creation"""
        context = {
            'teamName': team_name,
            'machineName': machine_name,
            'repositoryGuid': repo_guid,
            'teamVault': team_vault or '{}',
            'machineVault': machine_vault or '{}',
            'params': {
                'name': repo_name,
                'size': size,
                'repo': repo_guid
            }
        }
        return self.build_for_function('new', context)
    
    def build_for_repo_push(self, context):
        """Build vault specifically for repository push operation"""
        # Similar to console's push pattern
        params = context['params'].copy()
        
        # Ensure proper GUID handling
        if 'dest' in params and context.get('destinationGuid'):
            params['dest'] = context['destinationGuid']
        if 'repo' in params and context.get('sourceGuid'):
            params['repo'] = context['sourceGuid']
        if context.get('grandGuid'):
            params['grand'] = context['grandGuid']
            
        context['params'] = params
        return self.build_for_function('push', context)
    
    def build_for_ping(self, team_name, machine_name, bridge_name, team_vault=None, machine_vault=None):
        """Build vault specifically for ping connectivity test"""
        context = {
            'teamName': team_name,
            'machineName': machine_name,
            'bridgeName': bridge_name,
            'teamVault': team_vault or '{}',
            'machineVault': machine_vault or '{}',
            'params': {}
        }
        return self.build_for_function('ping', context)
    
    def build_for_hello(self, team_name, machine_name, bridge_name, team_vault=None, machine_vault=None):
        """Build vault specifically for hello test"""
        context = {
            'teamName': team_name,
            'machineName': machine_name,
            'bridgeName': bridge_name,
            'teamVault': team_vault or '{}',
            'machineVault': machine_vault or '{}',
            'params': {}
        }
        return self.build_for_function('hello', context)
    
    def build_for_ssh_test(self, bridge_name, machine_vault, team_name=None, team_vault=None, bridge_vault=None):
        """Build vault specifically for SSH test (bridge-only task)"""
        # Debug: print what team vault we receive
        if os.environ.get('REDIACC_VERBOSE'):
            print(f"DEBUG: build_for_ssh_test received team_vault type: {type(team_vault)}")
            if team_vault:
                print(f"DEBUG: team_vault length: {len(str(team_vault))}")
        
        # Special handling for ssh_test - it can work without a machine name
        context = {
            'teamName': team_name or '',  # Team name for context
            'machineName': '',  # Empty for bridge-only tasks
            'bridgeName': bridge_name,
            'teamVault': team_vault or '{}',  # Team vault for SSH keys
            'machineVault': machine_vault,  # Contains SSH connection details
            'bridgeVault': bridge_vault or '{}',
            'params': {}
        }
        
        # For ssh_test, we need to handle the special case where SSH details
        # are included directly in the vault data
        vault_data = json.loads(self.build_for_function('ssh_test', context))
        
        # The console adds SSH details directly to root for bridge-only tasks
        machine_data = self._extract_machine_data(machine_vault)
        vault = self._parse_vault(machine_vault)
        if vault.get('ssh_password'):
            machine_data['ssh_password'] = vault['ssh_password']
        
        # Merge machine data into root of vault_data
        vault_data.update(machine_data)
        
        return minifyJSON(json.dumps(vault_data))
    
    def build_for_setup(self, team_name, machine_name, bridge_name, params, team_vault=None, machine_vault=None):
        """Build vault for machine setup"""
        context = {
            'teamName': team_name,
            'machineName': machine_name,
            'bridgeName': bridge_name,
            'teamVault': team_vault or '{}',
            'machineVault': machine_vault or '{}',
            'params': params  # datastore_size, source, etc.
        }
        return self.build_for_function('setup', context)

def minifyJSON(json_str):
    """Minify JSON string by removing unnecessary whitespace"""
    try:
        return json.dumps(json.loads(json_str), separators=(',', ':'))
    except:
        return json_str

class CommandHandler:
    def __init__(self, config_manager, output_format='text'):
        self.config = config_manager.config
        self.config_manager = config_manager
        self.client = APIClient(config_manager)
        self.output_format = output_format
    
    def handle_response(self, response, success_message=None, format_args=None):
        if response.get('error'): print(format_output(None, self.output_format, None, response['error'])); return False
        
        # Debug: Check if response indicates failure
        if response.get('failure') or response.get('success') == False:
            errors = response.get('errors', [])
            if errors:
                error_msg = '; '.join(errors)
                print(format_output(None, self.output_format, None, f"Operation failed: {error_msg}"))
                return False
        
        if success_message and format_args and '{task_id}' in success_message:
            if (resultSets := response.get('resultSets', [])) and len(resultSets) > 1 and resultSets[1].get('data'):
                if task_id := resultSets[1]['data'][0].get('taskId') or resultSets[1]['data'][0].get('TaskId'):
                    setattr(format_args, 'task_id', task_id)
        
        if not success_message: return True
        
        if format_args:
            format_dict = {k: getattr(format_args, k, '') for k in dir(format_args) if not k.startswith('_')}
            success_message = success_message.format(**format_dict)
        
        if self.output_format in ['json', 'json-full']:
            data = {'task_id': format_args.task_id} if hasattr(format_args, 'task_id') and format_args.task_id else {}
            
            # For json-full, include the complete response data
            if self.output_format == 'json-full' and response.get('resultSets'):
                data['resultSets'] = response['resultSets']
            
            print(format_output(data, self.output_format, success_message))
        else:
            print(colorize(success_message, 'GREEN'))
        return True
    
    def login(self, args):
        # Check for environment variables and use them as defaults
        env_email = os.environ.get('SYSTEM_ADMIN_EMAIL')
        env_password = os.environ.get('SYSTEM_ADMIN_PASSWORD')
        
        email = args.email or env_email or input("Email: ")
        password = args.password or env_password or getpass.getpass("Password: ")
        hash_pwd = pwd_hash(password)
        
        login_params = {'name': args.session_name or "CLI Session"}
        
        for attr, param in [('tfa_code', 'TFACode'), ('permissions', 'requestedPermissions'), ('expiration', 'tokenExpirationHours'), ('target', 'target')]:
            if hasattr(args, attr) and (value := getattr(args, attr)): login_params[param] = value
        
        response = self.client.auth_request("CreateAuthenticationRequest", email, hash_pwd, login_params)
        
        if response.get('error'): print(format_output(None, self.output_format, None, f"Login failed: {response['error']}")); return 1
        if not (resultSets := response.get('resultSets', [])) or not resultSets[0].get('data'): print(format_output(None, self.output_format, None, "Login failed: Could not get authentication token")); return 1
        auth_data = resultSets[0]['data'][0]
        if not (token := auth_data.get('nextRequestToken')): print(format_output(None, self.output_format, None, "Login failed: Invalid authentication token")); return 1
        
        is_authorized = auth_data.get('isAuthorized', True)
        authentication_status = auth_data.get('authenticationStatus', '')
        
        if authentication_status == 'TFA_REQUIRED' and not is_authorized:
            if not hasattr(args, 'tfa_code') or not args.tfa_code:
                if self.output_format not in ['json', 'json-full']:
                    from core.config import I18n
                    i18n = I18n()
                    tfa_code = input(i18n.get('enter_tfa_code'))
                else:
                    print(format_output(None, self.output_format, None, "TFA_REQUIRED. Please provide --tfa-code parameter."))
                    return 1
                
                login_params['TFACode'] = tfa_code
                response = self.client.auth_request("CreateAuthenticationRequest", email, hash_pwd, login_params)
                
                if response.get('error'):
                    print(format_output(None, self.output_format, None, f"TFA verification failed: {response['error']}"))
                    return 1
                
                resultSets = response.get('resultSets', [])
                if not resultSets or not resultSets[0].get('data'):
                    print(format_output(None, self.output_format, None, "TFA verification failed: Could not get authentication token"))
                    return 1
                
                auth_data = resultSets[0]['data'][0]
                token = auth_data.get('nextRequestToken')
                if not token:
                    print(format_output(None, self.output_format, None, "TFA verification failed: Invalid authentication token"))
                    return 1
        
        company = auth_data.get('companyName')
        vault_company = auth_data.get('vaultCompany') or auth_data.get('VaultCompany')
        
        self.config_manager.set_token_with_auth(token, email, company, vault_company)
        
        # Immediately fetch and update vault_company with COMPANY_ID after login
        if company_info := self.client.get_company_vault():
            if updated_vault := company_info.get('vaultCompany'):
                self.config_manager.set_token_with_auth(token, email, company, updated_vault)
        
        # Check if company has vault encryption enabled
        if vault_company and is_encrypted(vault_company):
            # Company requires master password
            master_password = getattr(args, 'master_password', None)
            if not master_password:
                print(colorize("Your company requires a master password for vault encryption.", 'YELLOW'))
                master_password = getpass.getpass("Master Password: ")
            
            if self.config_manager.validate_master_password(master_password):
                self.config_manager.set_master_password(master_password)
                if self.output_format not in ['json', 'json-full']:
                    print(colorize("Master password validated successfully", 'GREEN'))
            else:
                print(format_output(None, self.output_format, None, 
                    "Invalid master password. Please check with your administrator for the correct company master password."))
                if self.output_format not in ['json', 'json-full']:
                    print(colorize("Warning: Logged in but vault data will not be decrypted", 'YELLOW'))
        elif hasattr(args, 'master_password') and args.master_password and self.output_format not in ['json', 'json-full']:
            print(colorize("Note: Your company has not enabled vault encryption. The master password will not be used.", 'YELLOW'))
        
        if self.output_format in ['json', 'json-full']:
            result = {
                'email': email,
                'company': company,
                'vault_encryption_enabled': bool(vault_company and is_encrypted(vault_company)),
                'master_password_set': bool(self.config_manager.get_master_password())
            }
            print(format_output(result, self.output_format, f"Successfully logged in as {email}"))
        else:
            print(colorize(f"Successfully logged in as {email}", 'GREEN'))
            if company:
                print(f"Company: {company}")
            if vault_company and is_encrypted(vault_company):
                print(f"Vault Encryption: Enabled")
                print(f"Master Password: {'Set' if self.config_manager.get_master_password() else 'Not set (vault data will remain encrypted)'}")
        
        return 0
    
    def logout(self, args):
        """Log out from the Rediacc API"""
        # Delete the user request if we have a token
        if TokenManager.get_token():
            self.client.token_request("DeleteUserRequest")
        
        # Clear local auth data
        self.config_manager.clear_auth()
        
        print(format_output({}, self.output_format, "Successfully logged out"))
        return 0
    
    def handle_license_command(self, args):
        """Handle license-related commands"""
        if args.license_command == 'generate-id':
            try:
                if self.output_format != 'json':
                    print(colorize("Connecting to middleware to generate hardware ID...", 'BLUE'))
                
                hardware_id = generate_hardware_id()
                output_file = args.output or 'hardware-id.txt'
                
                # Write to file
                with open(output_file, 'w') as f:
                    f.write(hardware_id)
                
                if self.output_format == 'json':
                    result = {
                        "success": True,
                        "hardware_id": hardware_id,
                        "output_file": output_file
                    }
                    print(json.dumps(result))
                else:
                    print(colorize("Hardware ID generated successfully!", 'GREEN'))
                    print(colorize(f"Hardware ID: {hardware_id}", 'GREEN'))
                    print(colorize(f"Saved to: {output_file}", 'GREEN'))
                    print()
                    print(colorize("Next steps:", 'BLUE'))
                    print("1. Transfer this file to a machine with internet access")
                    print("2. Run: ./rediacc license request --hardware-id " + output_file)
                    print("3. Transfer the resulting license.lic back to this machine")
                    print("4. Run: ./rediacc license install --file license.lic")
                return 0
            except Exception as e:
                error_msg = str(e)
                if self.output_format == 'json':
                    print(json.dumps({"success": False, "error": error_msg}))
                else:
                    print(colorize("Failed to generate hardware ID", 'RED'))
                    print(colorize(error_msg, 'RED'))
                return 1
                
        elif args.license_command == 'request':
            try:
                if os.path.isfile(args.hardware_id):
                    with open(args.hardware_id, 'r') as f:
                        hardware_id = f.read().strip()
                else:
                    hardware_id = args.hardware_id
                
                print(colorize("Requesting license from server...", 'BLUE'))
                license_data = request_license_from_server(hardware_id, args.server_url)
                
                output_file = args.output or 'license.lic'
                with open(output_file, 'w') as f:
                    lic_data = license_data.get('licenseData') or license_data.get('LicenseData')
                    if not lic_data:
                        raise Exception("License data not found in response")
                    f.write(lic_data)
                
                if self.output_format == 'json':
                    result = {
                        "success": True,
                        "license_key": license_data.get('licenseKey') or license_data.get('LicenseKey'),
                        "expiration_date": license_data.get('expirationDate') or license_data.get('ExpirationDate'),
                        "is_new_license": license_data.get('isNewLicense', license_data.get('IsNewLicense', False)),
                        "output_file": output_file
                    }
                    print(json.dumps(result))
                else:
                    print(colorize("License obtained successfully!", 'GREEN'))
                    lic_key = license_data.get('licenseKey') or license_data.get('LicenseKey')
                    exp_date = license_data.get('expirationDate') or license_data.get('ExpirationDate')
                    is_new = license_data.get('isNewLicense', license_data.get('IsNewLicense', False))
                    print(colorize(f"License Key: {lic_key}", 'GREEN'))
                    print(colorize(f"Expires: {exp_date}", 'GREEN'))
                    if is_new:
                        print(colorize("This is a new license", 'BLUE'))
                    print(colorize(f"Saved to: {output_file}", 'GREEN'))
                return 0
            except Exception as e:
                error = f"Failed to request license: {str(e)}"
                if self.output_format == 'json':
                    print(json.dumps({"success": False, "error": error}))
                else:
                    print(colorize(error, 'RED'))
                return 1
                
        elif args.license_command == 'install':
            try:
                target_file = install_license_file(args.file, args.target)
                
                if self.output_format == 'json':
                    result = {
                        "success": True,
                        "installed_to": target_file
                    }
                    print(json.dumps(result))
                else:
                    print(colorize(f"License installed successfully to: {target_file}", 'GREEN'))
                return 0
            except Exception as e:
                error = f"Failed to install license: {str(e)}"
                if self.output_format == 'json':
                    print(json.dumps({"success": False, "error": error}))
                else:
                    print(colorize(error, 'RED'))
                return 1
        
        else:
            error = f"Unknown license command: {args.license_command}"
            if self.output_format == 'json':
                print(json.dumps({"success": False, "error": error}))
            else:
                print(colorize(error, 'RED'))
            return 1
    
    def queue_add(self, args):
        func_def = QUEUE_FUNCTIONS.get(args.function)
        if not func_def:
            print(format_output(None, self.output_format, None, f"Unknown function: {args.function}"))
            return 1
        
        if not self._collect_function_params(args, func_def):
            return 1
        
        vault_data = build_queue_vault_data(args.function, args)
        if not vault_data:
            print(format_output(None, self.output_format, None, "Failed to build queue item data"))
            return 1
        
        response = self.client.token_request(
            "CreateQueueItem",
            {
                'teamName': args.team,
                'machineName': args.machine,
                'bridgeName': args.bridge,
                'queueVault': vault_data
            }
        )
        
        if response.get('error'):
            output = format_output(None, self.output_format, None, response['error'])
            print(output)
            return 1
        
        resultSets = response.get('resultSets', [])
        task_id = None
        if len(resultSets) > 1 and resultSets[1].get('data'):
            task_id = resultSets[1]['data'][0].get('taskId', resultSets[1]['data'][0].get('TaskId'))
        
        if self.output_format in ['json', 'json-full']:
            result = {
                'task_id': task_id,
                'function': args.function,
                'team': args.team,
                'machine': args.machine,
                'bridge': args.bridge
            }
            output = format_output(result, self.output_format, f"Successfully queued {args.function}")
            print(output)
        else:
            print(colorize(f"Successfully queued {args.function} for machine {args.machine}", 'GREEN'))
            if task_id:
                print(f"Task ID: {task_id}")
        
        return 0
    
    def _collect_function_params(self, args, func_def):
        for param_name, param_info in func_def.get('params', {}).items():
            if not hasattr(args, param_name):
                setattr(args, param_name, None)
            
            if param_info.get('required', False) and getattr(args, param_name) is None:
                if self.output_format in ['json', 'json-full']:
                    print(format_output(None, self.output_format, None, f"Missing required parameter: {param_name}"))
                    return False
                
                value = input(f"{param_info.get('help', param_name)}: ")
                setattr(args, param_name, value)
        return True
    
    def queue_list_functions(self, args):
        if self.output_format in ['json', 'json-full']:
            result = {
                func_name: {
                    'description': func_def.get('description', ''),
                    'params': {
                        param_name: {
                            'type': param_info.get('type', 'string'),
                            'required': param_info.get('required', False),
                            'default': param_info.get('default', None),
                            'help': param_info.get('help', '')
                        }
                        for param_name, param_info in func_def.get('params', {}).items()
                    }
                }
                for func_name, func_def in QUEUE_FUNCTIONS.items()
            }
            print(format_output(result, self.output_format))
        else:
            print(colorize("Available Queue Functions", 'HEADER'))
            print("=" * 80)
            
            for func_name, func_def in sorted(QUEUE_FUNCTIONS.items()):
                print(f"\n{colorize(func_name, 'BLUE')}")
                print(f"  {func_def.get('description', 'No description available')}")
                
                params = func_def.get('params', {})
                if not params:
                    print("  No parameters required")
                    continue
                    
                print("  Parameters:")
                for param_name, param_info in params.items():
                    required = "[required]" if param_info.get('required', False) else "[optional]"
                    default = f" (default: {param_info.get('default')})" if 'default' in param_info else ""
                    print(f"    - {param_name} {colorize(required, 'YELLOW')}{default}")
                    if help_text := param_info.get('help', ''):
                        print(f"      {help_text}")
        
        return 0
    
    def generate_dynamic_help(self, cmd_type, resource_type=None):
        """Generate help text dynamically from configuration"""
        if not resource_type:
            # List all resources for command type
            if cmd_type not in API_ENDPOINTS:
                return f"\nNo resources available for command '{cmd_type}'\n"
            
            resources = API_ENDPOINTS.get(cmd_type, {})
            help_text = f"\nAvailable resources for '{colorize(cmd_type, 'BLUE')}':\n\n"
            
            # Calculate max width for alignment
            max_width = max(len(r) for r in resources.keys()) if resources else 0
            
            for resource, config in resources.items():
                help_info = config.get('help', {})
                desc = help_info.get('description', 'No description available')
                help_text += f"  {colorize(resource, 'GREEN'):<{max_width + 10}} {desc}\n"
            
            help_text += f"\nUse '{colorize(f'rediacc {cmd_type} <resource> --help', 'YELLOW')}' for more details on a specific resource.\n"
            return help_text
        
        # Generate help for specific command
        if cmd_type not in API_ENDPOINTS or resource_type not in API_ENDPOINTS[cmd_type]:
            return f"\nNo help available for: {cmd_type} {resource_type}\n"
        
        config = API_ENDPOINTS[cmd_type][resource_type]
        help_info = config.get('help', {})
        
        # Start with command description
        help_text = f"\n{colorize(help_info.get('description', 'No description available'), 'BOLD')}\n"
        
        # Add detailed description
        if details := help_info.get('details'):
            help_text += f"\n{details}\n"
        
        # Add parameters section
        if params := help_info.get('parameters'):
            help_text += f"\n{colorize('Parameters:', 'BLUE')}\n"
            for param_name, param_info in params.items():
                req_text = colorize(" (required)", 'YELLOW') if param_info.get('required') else " (optional)"
                help_text += f"  {colorize(param_name, 'GREEN')}{req_text}: {param_info['description']}\n"
                
                if default := param_info.get('default'):
                    help_text += f"    Default: {default}\n"
                    
                if example := param_info.get('example'):
                    help_text += f"    Example: {example}\n"
        
        # Add examples section
        if examples := help_info.get('examples'):
            help_text += f"\n{colorize('Examples:', 'BLUE')}\n"
            for ex in examples:
                help_text += f"  $ {colorize(ex['command'], 'GREEN')}\n"
                help_text += f"    {ex['description']}\n\n"
        
        # Add notes section
        if notes := help_info.get('notes'):
            help_text += f"{colorize('Notes:', 'BLUE')} {notes}\n"
        
        # Add success message info if available
        if success_msg := config.get('success_msg'):
            help_text += f"\n{colorize('Success message:', 'BLUE')} {success_msg}\n"
        
        return help_text
    
    def generic_command(self, cmd_type, resource_type, args):
        special_handlers = {
            ('queue', 'add'): self.queue_add,
            ('queue', 'list-functions'): self.queue_list_functions,
            ('vault', 'set'): self.vault_set,
            ('vault', 'set-password'): self.vault_set_password,
            ('vault', 'clear-password'): self.vault_clear_password,
            ('vault', 'status'): self.vault_status,
        }
        
        if handler := special_handlers.get((cmd_type, resource_type)):
            return handler(args)
        
        if cmd_type not in API_ENDPOINTS or resource_type not in API_ENDPOINTS[cmd_type]:
            print(format_output(None, self.output_format, None, f"Unsupported command: {cmd_type} {resource_type}"))
            return 1
        
        cmd_config = API_ENDPOINTS[cmd_type][resource_type]
        auth_required = cmd_config.get('auth_required', True)
        
        password_prompts = [
            (cmd_type == 'create' and resource_type == 'user' and not hasattr(args, 'password'), 
             lambda: setattr(args, 'password', getpass.getpass("Password for new user: "))),
            (cmd_type == 'user' and resource_type == 'update-password' and not args.new_password,
             lambda: setattr(args, 'new_password', getpass.getpass("New password: "))),
            (cmd_type == 'user' and resource_type == 'update-tfa' and not hasattr(args, 'password'),
             lambda: setattr(args, 'password', getpass.getpass("Current password: ")))
        ]
        
        for condition, action in password_prompts:
            if condition:
                action()
        
        confirm_msg = cmd_config.get('confirm_msg')
        if confirm_msg and not args.force and self.output_format != 'json':
            confirm_msg = confirm_msg.format(**{k: getattr(args, k, '') 
                                                             for k in dir(args) 
                                                             if not k.startswith('_')})
            confirm = input(f"{confirm_msg} [y/N] ")
            if confirm.lower() != 'y':
                print("Operation cancelled")
                return 0
        
        if cmd_type == 'vault':
            if resource_type == 'set':
                return self.vault_set(args)
            elif resource_type == 'set-password':
                return self.vault_set_password(args)
            elif resource_type == 'clear-password':
                return self.vault_clear_password(args)
            elif resource_type == 'status':
                return self.vault_status(args)
            return 1
        
        params = cmd_config['params'](args) if callable(cmd_config.get('params')) else {}
        
        if cmd_config.get('auth_type') == 'credentials' and hasattr(args, 'email'):
            email = args.email or input("Admin Email: ")
            password = args.password
            if not password:
                password = getpass.getpass("Admin Password: ")
                confirm = getpass.getpass("Confirm Password: ")
                if password != confirm:
                    error = "Passwords do not match"
                    output = format_output(None, self.output_format, None, error)
                    print(output)
                    return 1
            
            response = self.client.auth_request(
                cmd_config['endpoint'], email, pwd_hash(password), params
            )
        elif not auth_required:
            # No authentication required
            response = self.client.request(cmd_config['endpoint'], params)
        else:
            # Use token authentication
            response = self.client.token_request(cmd_config['endpoint'], params)
        
        # For list commands or permission list commands, format the output
        if cmd_type == 'list' or cmd_type == 'inspect' or (cmd_type == 'permission' and resource_type in ['list-groups', 'list-group']) or \
           (cmd_type == 'team-member' and resource_type == 'list') or \
           (cmd_type == 'queue' and resource_type in ['get-next', 'list', 'trace']) or \
           (cmd_type == 'company' and resource_type == 'get-vaults'):
            if response.get('error'):
                output = format_output(None, self.output_format, None, response['error'])
                print(output)
                return 1
            
            # Special handling for queue trace command
            if cmd_type == 'queue' and resource_type == 'trace':
                result = self.format_queue_trace(response, self.output_format)
            elif cmd_type == 'inspect':
                # Apply filter for inspect commands
                if 'filter' in cmd_config:
                    # Extract data from response
                    data = extract_table_data(response, 1)  # Data is in table index 1
                    # Apply filter
                    filter_func = eval(cmd_config['filter'])
                    filtered_data = filter_func(data, args)
                    
                    if cmd_config.get('single_result') and filtered_data:
                        # For single result, show just the first match
                        filtered_data = filtered_data[:1]
                    
                    # Create new response with filtered data
                    filtered_response = {
                        'success': True,
                        'resultSets': [
                            response['resultSets'][0],  # Keep credentials table
                            {'data': filtered_data}  # Replace data with filtered results
                        ]
                    }
                    result = format_dynamic_tables(filtered_response, self.output_format)
                else:
                    result = format_dynamic_tables(response, self.output_format)
            else:
                result = format_dynamic_tables(response, self.output_format)
            print(result)
            return 0
        
        # For create queue-item, handle special response
        if cmd_type == 'create' and resource_type == 'queue-item':
            success_msg = cmd_config.get('success_msg')
            # Create a simple object to hold task_id for format_args
            class Args:
                pass
            format_args = Args()
            for k in dir(args):
                if not k.startswith('_'):
                    setattr(format_args, k, getattr(args, k))
            
            if self.handle_response(response, success_msg, format_args):
                # If we have a task ID, print it
                if hasattr(format_args, 'task_id') and format_args.task_id and self.output_format != 'json':
                    print(f"Task ID: {format_args.task_id}")
                return 0
            return 1
        
        # For other commands, handle the response
        success_msg = cmd_config.get('success_msg')
        if self.handle_response(response, success_msg, args):
            return 0
        return 1
    
    def update_resource(self, resource_type, args):
        """Handle update commands"""
        success = True
        result_data = {}
        
        if resource_type == 'team':
            if args.new_name:
                response = self.client.token_request(
                    "UpdateTeamName", 
                    {"currentTeamName": args.name, "newTeamName": args.new_name}
                )
                
                success_msg = f"Successfully renamed team: {args.name} → {args.new_name}"
                if not self.handle_response(response, success_msg):
                    success = False
                else:
                    result_data['team_name'] = args.new_name
            
            if (args.vault or args.vault_file) and success:
                vault_data = get_vault_data(args)
                team_name = args.new_name if args.new_name else args.name
                
                response = self.client.token_request(
                    "UpdateTeamVault", 
                    {
                        "teamName": team_name,
                        "teamVault": vault_data,
                        "vaultVersion": args.vault_version or 1
                    }
                )
                
                if not self.handle_response(response, "Successfully updated team vault"):
                    success = False
                else:
                    result_data['vault_updated'] = True
                    result_data['vault_version'] = args.vault_version or 1
        
        elif resource_type == 'region':
            if args.new_name:
                # Update region name
                response = self.client.token_request(
                    "UpdateRegionName", 
                    {"currentRegionName": args.name, "newRegionName": args.new_name}
                )
                
                success_msg = f"Successfully renamed region: {args.name} → {args.new_name}"
                if not self.handle_response(response, success_msg):
                    success = False
                else:
                    result_data['region_name'] = args.new_name
            
            if (args.vault or args.vault_file) and success:
                vault_data = get_vault_data(args)
                region_name = args.new_name if args.new_name else args.name
                
                response = self.client.token_request(
                    "UpdateRegionVault", 
                    {
                        "regionName": region_name,
                        "regionVault": vault_data,
                        "vaultVersion": args.vault_version or 1
                    }
                )
                
                if not self.handle_response(response, "Successfully updated region vault"):
                    success = False
                else:
                    result_data['vault_updated'] = True
                    result_data['vault_version'] = args.vault_version or 1
        
        elif resource_type == 'bridge':
            if args.new_name:
                # Update bridge name
                response = self.client.token_request(
                    "UpdateBridgeName", 
                    {
                        "regionName": args.region,
                        "currentBridgeName": args.name,
                        "newBridgeName": args.new_name
                    }
                )
                
                success_msg = f"Successfully renamed bridge: {args.name} → {args.new_name}"
                if not self.handle_response(response, success_msg):
                    success = False
                else:
                    result_data['bridge_name'] = args.new_name
            
            if (args.vault or args.vault_file) and success:
                vault_data = get_vault_data(args)
                bridge_name = args.new_name if args.new_name else args.name
                
                response = self.client.token_request(
                    "UpdateBridgeVault", 
                    {
                        "regionName": args.region,
                        "bridgeName": bridge_name,
                        "bridgeVault": vault_data,
                        "vaultVersion": args.vault_version or 1
                    }
                )
                
                if not self.handle_response(response, "Successfully updated bridge vault"):
                    success = False
                else:
                    result_data['vault_updated'] = True
                    result_data['vault_version'] = args.vault_version or 1
        
        elif resource_type == 'machine':
            team_name = args.team
            result_data['team'] = team_name
            
            if args.new_name:
                # Update machine name
                response = self.client.token_request(
                    "UpdateMachineName", 
                    {
                        "teamName": team_name,
                        "currentMachineName": args.name,
                        "newMachineName": args.new_name
                    }
                )
                
                success_msg = f"Successfully renamed machine: {args.name} → {args.new_name}"
                if not self.handle_response(response, success_msg):
                    success = False
                else:
                    result_data['machine_name'] = args.new_name
            
            # Update bridge if provided
            if args.new_bridge and success:
                machine_name = args.new_name if args.new_name else args.name
                
                response = self.client.token_request(
                    "UpdateMachineAssignedBridge", 
                    {
                        "teamName": team_name,
                        "machineName": machine_name,
                        "newBridgeName": args.new_bridge
                    }
                )
                
                success_msg = f"Successfully updated machine bridge: → {args.new_bridge}"
                if not self.handle_response(response, success_msg):
                    success = False
                else:
                    result_data['bridge'] = args.new_bridge
            
            if (args.vault or args.vault_file) and success:
                vault_data = get_vault_data(args)
                machine_name = args.new_name if args.new_name else args.name
                
                response = self.client.token_request(
                    "UpdateMachineVault", 
                    {
                        "teamName": team_name,
                        "machineName": machine_name,
                        "machineVault": vault_data,
                        "vaultVersion": args.vault_version or 1
                    }
                )
                
                if not self.handle_response(response, "Successfully updated machine vault"):
                    success = False
                else:
                    result_data['vault_updated'] = True
                    result_data['vault_version'] = args.vault_version or 1
        
        elif resource_type == 'repository':
            if args.new_name:
                # Update repository name
                response = self.client.token_request(
                    "UpdateRepositoryName", 
                    {
                        "teamName": args.team,
                        "currentRepoName": args.name,
                        "newRepoName": args.new_name
                    }
                )
                
                success_msg = f"Successfully renamed repository: {args.name} → {args.new_name}"
                if not self.handle_response(response, success_msg):
                    success = False
                else:
                    result_data['repository_name'] = args.new_name
            
            if (args.vault or args.vault_file) and success:
                vault_data = get_vault_data(args)
                repo_name = args.new_name if args.new_name else args.name
                
                response = self.client.token_request(
                    "UpdateRepositoryVault", 
                    {
                        "teamName": args.team,
                        "repoName": repo_name,
                        "repoVault": vault_data,
                        "vaultVersion": args.vault_version or 1
                    }
                )
                
                if not self.handle_response(response, "Successfully updated repository vault"):
                    success = False
                else:
                    result_data['vault_updated'] = True
                    result_data['vault_version'] = args.vault_version or 1
        
        elif resource_type == 'storage':
            if args.new_name:
                # Update storage name
                response = self.client.token_request(
                    "UpdateStorageName", 
                    {
                        "teamName": args.team,
                        "currentStorageName": args.name,
                        "newStorageName": args.new_name
                    }
                )
                
                success_msg = f"Successfully renamed storage: {args.name} → {args.new_name}"
                if not self.handle_response(response, success_msg):
                    success = False
                else:
                    result_data['storage_name'] = args.new_name
            
            if (args.vault or args.vault_file) and success:
                vault_data = get_vault_data(args)
                storage_name = args.new_name if args.new_name else args.name
                
                response = self.client.token_request(
                    "UpdateStorageVault", 
                    {
                        "teamName": args.team,
                        "storageName": storage_name,
                        "storageVault": vault_data,
                        "vaultVersion": args.vault_version or 1
                    }
                )
                
                if not self.handle_response(response, "Successfully updated storage vault"):
                    success = False
                else:
                    result_data['vault_updated'] = True
                    result_data['vault_version'] = args.vault_version or 1
        
        elif resource_type == 'schedule':
            if args.new_name:
                # Update schedule name
                response = self.client.token_request(
                    "UpdateScheduleName", 
                    {
                        "teamName": args.team,
                        "currentScheduleName": args.name,
                        "newScheduleName": args.new_name
                    }
                )
                
                success_msg = f"Successfully renamed schedule: {args.name} → {args.new_name}"
                if not self.handle_response(response, success_msg):
                    success = False
                else:
                    result_data['schedule_name'] = args.new_name
            
            if (args.vault or args.vault_file) and success:
                vault_data = get_vault_data(args)
                schedule_name = args.new_name if args.new_name else args.name
                
                response = self.client.token_request(
                    "UpdateScheduleVault", 
                    {
                        "teamName": args.team,
                        "scheduleName": schedule_name,
                        "scheduleVault": vault_data,
                        "vaultVersion": args.vault_version or 1
                    }
                )
                
                if not self.handle_response(response, "Successfully updated schedule vault"):
                    success = False
                else:
                    result_data['vault_updated'] = True
                    result_data['vault_version'] = args.vault_version or 1
        
        else:
            error = f"Unsupported resource type: {resource_type}"
            output = format_output(None, self.output_format, None, error)
            print(output)
            return 1
        
        # If JSON output and operations were successful, show summary
        if self.output_format == 'json' and success and result_data:
            output = format_output(result_data, self.output_format, "Update completed successfully")
            print(output)
        
        return 0 if success else 1
    
    def vault_set(self, args):
        """Set vault data for a resource"""
        resource_type = args.resource_type
        endpoints = API_ENDPOINTS['vault']['set']['endpoints']
        
        if resource_type not in endpoints:
            print(format_output(None, self.output_format, None, f"Unsupported resource type: {resource_type}"))
            return 1
        
        params = get_vault_set_params(args, self.config_manager)
        if not params:
            return 1
        
        response = self.client.token_request(endpoints[resource_type], params)
        
        success_msg = f"Successfully updated {resource_type} vault"
        if self.handle_response(response, success_msg):
            if self.output_format == 'json':
                result = {
                    'resource_type': resource_type,
                    'vault_version': params.get('vaultVersion', 1)
                }
                if resource_type != 'company':
                    result['name'] = args.name
                if resource_type in ['machine', 'repository', 'storage', 'schedule']:
                    result['team'] = args.team
                if resource_type == 'bridge':
                    result['region'] = args.region
                
                print(format_output(result, self.output_format, success_msg))
            return 0
        return 1
    
    def vault_set_password(self, args):
        """Set master password for vault encryption"""
        if not CRYPTO_AVAILABLE:
            print(format_output(None, self.output_format, None, 
                "Cryptography library not available. Install with: pip install cryptography"))
            return 1
        
        self.client._ensure_vault_info()
        
        if not self.config_manager.has_vault_encryption():
            print(format_output(None, self.output_format, None,
                "Your company has not enabled vault encryption. Contact your administrator to enable it."))
            return 1
        
        master_password = getpass.getpass("Enter master password: ")
        confirm_password = getpass.getpass("Confirm master password: ")
        
        if master_password != confirm_password:
            print(format_output(None, self.output_format, None, "Passwords do not match"))
            return 1
        
        if self.config_manager.validate_master_password(master_password):
            self.config_manager.set_master_password(master_password)
            success_msg = "Master password set successfully"
            print(format_output({'success': True}, self.output_format, success_msg) if self.output_format == 'json' 
                  else colorize(success_msg, 'GREEN'))
            return 0
        else:
            print(format_output(None, self.output_format, None, 
                "Invalid master password. Please check with your administrator for the correct company master password."))
            return 1
    
    def vault_clear_password(self, args):
        """Clear master password from memory"""
        self.config_manager.clear_master_password()
        success_msg = "Master password cleared from memory"
        print(format_output({'success': True}, self.output_format, success_msg) if self.output_format == 'json' 
              else colorize(success_msg, 'GREEN'))
        return 0
    
    def vault_status(self, args):
        """Show vault encryption status"""
        self.client._ensure_vault_info()
        vault_company = self.config_manager.get_vault_company()
        
        status_data = {
            'crypto_available': CRYPTO_AVAILABLE,
            'company': self.config_manager.config.get('company'),
            'vault_encryption_enabled': self.config_manager.has_vault_encryption(),
            'master_password_set': bool(self.config_manager.get_master_password()),
            'vault_company_present': bool(vault_company),
            'vault_company_encrypted': is_encrypted(vault_company) if vault_company else False
        }
        
        if self.output_format == 'json':
            print(format_output(status_data, self.output_format))
        else:
            print(colorize("VAULT ENCRYPTION STATUS", 'HEADER'))
            print("=" * 40)
            print(f"Cryptography Library: {'Available' if status_data['crypto_available'] else 'Not Available'}")
            print(f"Company: {status_data['company'] or 'Not set'}")
            print(f"Vault Company Data: {'Present' if status_data['vault_company_present'] else 'Not fetched'}")
            print(f"Vault Encryption: {'Required' if status_data['vault_encryption_enabled'] else 'Not Required'}")
            print(f"Master Password: {'Set' if status_data['master_password_set'] else 'Not Set'}")
            
            if not status_data['crypto_available']:
                print("\n" + colorize("To enable vault encryption, install the cryptography library:", 'YELLOW'))
                print("  pip install cryptography")
            elif status_data['vault_encryption_enabled'] and not status_data['master_password_set']:
                print("\n" + colorize("Your company requires a master password for vault encryption.", 'YELLOW'))
                print("Use 'rediacc vault set-password' to set it.")
            elif not status_data['vault_company_present']:
                print("\n" + colorize("Note: Vault company information will be fetched on next command.", 'BLUE'))
        
        return 0
    
    def handle_dynamic_endpoint(self, endpoint_name, args):
        """Handle direct endpoint calls without predefined configuration"""
        # Convert CLI args to API parameters
        params = {}
        
        # Get all attributes from args that are not system attributes
        for key in vars(args):
            if key not in ['command', 'output', 'token', 'verbose', 'func', 'help', 'email', 'password']:
                value = getattr(args, key)
                if value is not None:
                    # Handle boolean parameters properly
                    # Check if the value is a string that represents a boolean
                    if isinstance(value, str) and value.lower() in ['true', 'false']:
                        params[key] = value.lower() == 'true'
                    else:
                        params[key] = value
        
        # Check if this endpoint requires special authentication handling
        # Look for it in API_ENDPOINTS to determine auth requirements
        auth_required = True
        auth_type = None
        
        for main_cmd, sub_cmds in API_ENDPOINTS.items():
            if isinstance(sub_cmds, dict):
                # Check top-level commands
                if sub_cmds.get('endpoint') == endpoint_name:
                    auth_required = sub_cmds.get('auth_required', True)
                    auth_type = sub_cmds.get('auth_type')
                    break
                
                # Check sub-commands
                for sub_cmd, config in sub_cmds.items():
                    if isinstance(config, dict) and config.get('endpoint') == endpoint_name:
                        auth_required = config.get('auth_required', True) 
                        auth_type = config.get('auth_type')
                        break
            if not auth_required:
                break
        
        # Debug output if verbose
        if args.verbose:
            print(f"Dynamic endpoint: {endpoint_name}")
            print(f"Parameters: {params}")
            print(f"Auth required: {auth_required}")
            print(f"Auth type: {auth_type}")
        
        # Make API call based on auth requirements
        if not auth_required and auth_type == 'credentials':
            # This endpoint uses email/password authentication
            email = getattr(args, 'email', None)
            password = getattr(args, 'password', None)
            
            if email and password:
                hash_pwd = pwd_hash(password)
                response = self.client.auth_request(endpoint_name, email, hash_pwd, params)
            else:
                print(format_output(None, self.output_format, None, "Email and password required for this endpoint"))
                return 1
        else:
            # Standard token-based authentication
            response = self.client.token_request(endpoint_name, params)
        
        # Handle response
        if response.get('error'):
            print(format_output(None, self.output_format, None, response['error']))
            return 1
        
        # Format success message
        success_msg = f"Successfully executed {endpoint_name}"
        
        # Try to create a more informative success message based on the endpoint name
        if 'Update' in endpoint_name and 'Name' in endpoint_name:
            # Extract what's being updated from the endpoint name
            resource = endpoint_name.replace('Update', '').replace('Name', '')
            if 'currentStorageName' in params and 'newStorageName' in params:
                success_msg = f"Successfully updated {resource.lower()} name: {params['currentStorageName']} → {params['newStorageName']}"
            elif 'current' + resource + 'Name' in params and 'new' + resource + 'Name' in params:
                current_key = 'current' + resource + 'Name'
                new_key = 'new' + resource + 'Name'
                success_msg = f"Successfully updated {resource.lower()} name: {params[current_key]} → {params[new_key]}"
        
        if self.output_format in ['json', 'json-full']:
            # Extract meaningful data from response for JSON output
            result_data = {'endpoint': endpoint_name, 'parameters': params}
            
            # If there's data in the response, include it
            if 'resultSets' in response and len(response['resultSets']) > 1:
                for table in response['resultSets'][1:]:
                    if table.get('data'):
                        result_data['result'] = table['data']
                        break
            
            print(format_output(result_data, self.output_format, success_msg))
        else:
            print(colorize(success_msg, 'GREEN'))
        
        return 0
    
    
    def format_queue_trace(self, response, output_format):
        """Format queue trace response with multiple result sets"""
        if not response or 'resultSets' not in response:
            return format_output("No trace data available", output_format)
        
        resultSets = response.get('resultSets', [])
        if len(resultSets) < 2:
            return format_output("No trace data found", output_format)
        
        if output_format == 'json':
            # For JSON output, organize data into meaningful sections
            result = {
                'queue_item': {},
                'request_vault': {},
                'response_vault': {},
                'timeline': []
            }
            
            # Table 1 (index 1): Queue Item Details
            if len(resultSets) > 1 and resultSets[1].get('data'):
                item_data = resultSets[1]['data'][0] if resultSets[1]['data'] else {}
                result['queue_item'] = item_data
            
            # Table 2 (index 2): Request Vault
            if len(resultSets) > 2 and resultSets[2].get('data'):
                vault_data = resultSets[2]['data'][0] if resultSets[2]['data'] else {}
                result['request_vault'] = {
                    'type': vault_data.get('VaultType', 'Request'),
                    'version': vault_data.get('VaultVersion'),
                    'content': vault_data.get('VaultContent'),
                    'has_content': vault_data.get('HasContent', False)
                }
            
            # Table 3 (index 3): Response Vault
            if len(resultSets) > 3 and resultSets[3].get('data'):
                vault_data = resultSets[3]['data'][0] if resultSets[3]['data'] else {}
                result['response_vault'] = {
                    'type': vault_data.get('VaultType', 'Response'),
                    'version': vault_data.get('VaultVersion'),
                    'content': vault_data.get('VaultContent'),
                    'has_content': vault_data.get('HasContent', False)
                }
            
            # Table 4 (index 4): Timeline
            if len(resultSets) > 4 and resultSets[4].get('data'):
                result['timeline'] = resultSets[4]['data']
            
            return format_output(result, output_format)
        else:
            output_parts = []
            
            if len(resultSets) > 1 and resultSets[1].get('data') and resultSets[1]['data']:
                item_data = resultSets[1]['data'][0]
                output_parts.append(colorize("QUEUE ITEM DETAILS", 'HEADER'))
                output_parts.append("=" * 80)
                
                details = [
                    ('Task ID', item_data.get('TaskId')),
                    ('Status', item_data.get('Status')),
                    ('Health Status', item_data.get('HealthStatus')),
                    ('Created Time', item_data.get('CreatedTime')),
                    ('Assigned Time', item_data.get('AssignedTime')),
                    ('Last Heartbeat', item_data.get('LastHeartbeat')),
                ]
                
                if item_data.get('Priority') is not None:
                    details.append(('Priority', f"{item_data.get('Priority')} ({item_data.get('PriorityLabel')})"))
                
                details.extend([
                    ('Seconds to Assignment', item_data.get('SecondsToAssignment')),
                    ('Processing Duration (seconds)', item_data.get('ProcessingDurationSeconds')),
                    ('Total Duration (seconds)', item_data.get('TotalDurationSeconds')),
                ])
                
                details.extend([
                    ('Company', f"{item_data.get('CompanyName')} (ID: {item_data.get('CompanyId')})"),
                    ('Team', f"{item_data.get('TeamName')} (ID: {item_data.get('TeamId')})"),
                    ('Region', f"{item_data.get('RegionName')} (ID: {item_data.get('RegionId')})"),
                    ('Bridge', f"{item_data.get('BridgeName')} (ID: {item_data.get('BridgeId')})"),
                    ('Machine', f"{item_data.get('MachineName')} (ID: {item_data.get('MachineId')})"),
                ])
                
                if item_data.get('IsStale'):
                    details.append(('Warning', colorize('This queue item is STALE', 'YELLOW')))
                
                max_label_width = max(len(label) for label, _ in details)
                output_parts.extend(f"{label.ljust(max_label_width)} : {value}" for label, value in details if value is not None)
                
            if len(resultSets) > 2 and resultSets[2].get('data') and resultSets[2]['data']:
                vault_data = resultSets[2]['data'][0]
                if vault_data.get('HasContent'):
                    output_parts.append("")
                    output_parts.append(colorize("REQUEST VAULT", 'HEADER'))
                    output_parts.append("=" * 80)
                    output_parts.append(f"Version: {vault_data.get('VaultVersion', 'N/A')}")
                    try:
                        vault_content = json.loads(vault_data.get('VaultContent', '{}'))
                        output_parts.append(json.dumps(vault_content, indent=2))
                    except:
                        output_parts.append(vault_data.get('VaultContent', 'No content'))
            
            if len(resultSets) > 3 and resultSets[3].get('data') and resultSets[3]['data']:
                vault_data = resultSets[3]['data'][0]
                if vault_data.get('HasContent'):
                    output_parts.append("")
                    output_parts.append(colorize("RESPONSE VAULT", 'HEADER'))
                    output_parts.append("=" * 80)
                    output_parts.append(f"Version: {vault_data.get('VaultVersion', 'N/A')}")
                    try:
                        vault_content = json.loads(vault_data.get('VaultContent', '{}'))
                        output_parts.append(json.dumps(vault_content, indent=2))
                    except:
                        output_parts.append(vault_data.get('VaultContent', 'No content'))
            
            if len(resultSets) > 4 and resultSets[4].get('data') and resultSets[4]['data']:
                output_parts.append("")
                output_parts.append(colorize("PROCESSING TIMELINE", 'HEADER'))
                output_parts.append("=" * 80)
                
                timeline_data = resultSets[4]['data']
                if timeline_data:
                    headers = ['Time', 'Status', 'Description']
                    rows = [
                        [event.get('Timestamp', 'N/A'),
                         event.get('NewValue', event.get('Status', 'N/A')),
                         event.get('ChangeDetails', event.get('Action', 'Status change'))]
                        for event in timeline_data
                    ]
                    
                    if rows:
                        output_parts.append(format_table(headers, rows))
                else:
                    output_parts.append("No timeline events recorded")
            
            return '\n'.join(output_parts)
    
    # Workflow delegate methods
    def workflow_repo_create(self, args):
        """Delegate to workflow handler"""
        workflow = WorkflowHandler(self)
        return workflow.workflow_repo_create(args)
    
    def workflow_repo_push(self, args):
        """Delegate to workflow handler"""
        workflow = WorkflowHandler(self)
        return workflow.workflow_repo_push(args)
    
    def workflow_connectivity_test(self, args):
        """Delegate to workflow handler"""
        workflow = WorkflowHandler(self)
        return workflow.workflow_connectivity_test(args)
    
    def workflow_hello_test(self, args):
        """Delegate to workflow handler"""
        workflow = WorkflowHandler(self)
        return workflow.workflow_hello_test(args)
    
    def workflow_ssh_test(self, args):
        """Delegate to workflow handler"""
        workflow = WorkflowHandler(self)
        return workflow.workflow_ssh_test(args)
    
    def workflow_machine_setup(self, args):
        """Delegate to workflow handler"""
        workflow = WorkflowHandler(self)
        return workflow.workflow_machine_setup(args)
    
    def workflow_add_machine(self, args):
        """Delegate to workflow handler"""
        workflow = WorkflowHandler(self)
        return workflow.workflow_add_machine(args)

def setup_parser():
    parser = argparse.ArgumentParser(
        description='Rediacc CLI - Complete interface for Rediacc Middleware API with enhanced queue support'
    )
    parser.add_argument('--version', action='version', 
                       version=f'Rediacc CLI v{__version__}' if __version__ != 'dev' else 'Rediacc CLI Development')
    parser.add_argument('--output', '-o', choices=['text', 'json', 'json-full'], default='text',
                       help='Output format: text, json (concise), or json-full (comprehensive)')
    parser.add_argument('--token', '-t', help='Authentication token (overrides saved token)')
    parser.add_argument('--verbose', '-v', action='store_true',
                       help='Enable verbose logging output')
    
    subparsers = parser.add_subparsers(dest='command', help='Command')
    
    for cmd_name, cmd_def in CLI_COMMANDS.items():
        # Skip individual parameter definitions (they have 'type' and 'help' but no subcommands)
        if isinstance(cmd_def, dict) and 'type' in cmd_def and 'help' in cmd_def and len(cmd_def) <= 3:
            continue
        
        # Skip commands that have subcommands (they're handled in the CLI_COMMANDS section above)
        if isinstance(cmd_def, dict) and 'subcommands' in cmd_def:
            continue
            
        if isinstance(cmd_def, list):
            cmd_parser = subparsers.add_parser(cmd_name, help=f"{cmd_name} command")
            for arg in cmd_def:
                kwargs = {k: v for k, v in arg.items() if k != 'name'}
                cmd_parser.add_argument(arg['name'], **kwargs)
        else:
            cmd_parser = subparsers.add_parser(cmd_name, help=f"{cmd_name} command")
            subcmd_parsers = cmd_parser.add_subparsers(dest='resource', help='Resource')
            
            for subcmd_name, subcmd_def in cmd_def.items():
                subcmd_parser = subcmd_parsers.add_parser(subcmd_name, help=f"{subcmd_name} resource")
                
                if cmd_name == 'queue' and subcmd_name == 'add':
                    for arg in subcmd_def:
                        kwargs = {k: v for k, v in arg.items() if k != 'name'}
                        subcmd_parser.add_argument(arg['name'], **kwargs)
                    
                    all_params = {}
                    for func_def in QUEUE_FUNCTIONS.values():
                        for param_name, param_info in func_def.get('params', {}).items():
                            if param_name not in all_params or len(param_info.get('help', '')) > len(all_params[param_name]):
                                all_params[param_name] = param_info.get('help', f'Parameter for function')
                    
                    for param_name, help_text in sorted(all_params.items()):
                        if param_name.replace('-', '_').replace('_', '').isidentifier():
                            subcmd_parser.add_argument(f'--{param_name.replace("_", "-")}', 
                                                     dest=param_name,
                                                     help=help_text)
                else:
                    if isinstance(subcmd_def, list):
                        for arg in subcmd_def:
                            if isinstance(arg, dict):
                                kwargs = {k: v for k, v in arg.items() if k != 'name'}
                                subcmd_parser.add_argument(arg['name'], **kwargs)
                            else:
                                # Handle string arguments
                                subcmd_parser.add_argument(arg)
                    elif isinstance(subcmd_def, dict):
                        for arg_name, arg_def in subcmd_def.items():
                            if isinstance(arg_def, dict):
                                kwargs = {k: v for k, v in arg_def.items() if k != 'name'}
                                subcmd_parser.add_argument(arg_name, **kwargs)
                            else:
                                subcmd_parser.add_argument(arg_name, help=str(arg_def))
                    
                    if cmd_name == 'update' and subcmd_name in ['team', 'region', 'bridge', 'machine', 'repository', 'storage', 'schedule']:
                        subcmd_parser.add_argument('--vault', help='JSON vault data')
                        subcmd_parser.add_argument('--vault-file', help='File containing JSON vault data')
                        subcmd_parser.add_argument('--vault-version', type=int, help='Vault version')
                        
                        if subcmd_name == 'machine':
                            subcmd_parser.add_argument('--new-bridge', help='New bridge name for machine')
    
    # Add CLI commands from JSON configuration
    if 'CLI_COMMANDS' in cli_config:
        for cmd_name, cmd_def in cli_config['CLI_COMMANDS'].items():
            # Only process commands with subcommands structure (license, workflow)
            if isinstance(cmd_def, dict) and 'subcommands' in cmd_def:
                cmd_parser = subparsers.add_parser(cmd_name, help=cmd_def.get('description', f'{cmd_name} commands'))
                
                cmd_subparsers = cmd_parser.add_subparsers(
                    dest=f'{cmd_name}_command' if cmd_name == 'license' else f'{cmd_name}_type',
                    help=f'{cmd_name.title()} commands'
                )
                
                for subcmd_name, subcmd_def in cmd_def['subcommands'].items():
                    subcmd_parser = cmd_subparsers.add_parser(
                        subcmd_name, 
                        help=subcmd_def.get('description', f'{subcmd_name} command')
                    )
                    
                    # Add parameters for this subcommand
                    if 'parameters' in subcmd_def:
                        for param_name, param_def in subcmd_def['parameters'].items():
                            # Convert parameter name to CLI format
                            cli_param_name = f'--{param_name}'
                            
                            # Build argument kwargs
                            kwargs = {}
                            
                            # Add short form if specified
                            if 'short' in param_def:
                                args = [param_def['short'], cli_param_name]
                            else:
                                args = [cli_param_name]
                            
                            # Convert parameter definition to argparse kwargs
                            if 'help' in param_def:
                                kwargs['help'] = param_def['help']
                            if 'required' in param_def:
                                kwargs['required'] = param_def['required']
                            if 'default' in param_def:
                                kwargs['default'] = param_def['default']
                            if 'type' in param_def:
                                if param_def['type'] == 'int':
                                    kwargs['type'] = int
                            if 'action' in param_def:
                                kwargs['action'] = param_def['action']
                            if 'choices' in param_def:
                                kwargs['choices'] = param_def['choices']
                            if 'nargs' in param_def:
                                kwargs['nargs'] = param_def['nargs']
                            
                            # Set destination to replace hyphens with underscores
                            kwargs['dest'] = param_name.replace('-', '_')
                            
                            subcmd_parser.add_argument(*args, **kwargs)
    
    return parser

def reorder_args(argv):
    """Move global options after the command to handle argparse limitations"""
    if len(argv) < 2:
        return argv
    
    # Global options that should be moved
    global_opts = {'--output', '-o', '--token', '-t', '--verbose', '-v'}
    
    # Commands that have subcommands
    subcommand_cmds = {'create', 'list', 'update', 'rm', 'vault', 'permission', 'user', 
                       'team-member', 'bridge', 'queue', 'company', 'audit', 'inspect', 
                       'distributed-storage', 'auth', 'workflow'}
    
    # Separate script name, global options, and command/args
    script_name = argv[0]
    global_args = []
    command = None
    command_args = []
    
    i = 1
    skip_next = False
    
    while i < len(argv):
        if skip_next:
            skip_next = False
            i += 1
            continue
            
        arg = argv[i]
        
        # Check if this is a global option
        if arg in global_opts:
            global_args.append(arg)
            # Check if the option has a value
            if i + 1 < len(argv) and not argv[i + 1].startswith('-'):
                if arg not in ['--verbose', '-v']:  # verbose is a flag, no value
                    global_args.append(argv[i + 1])
                    skip_next = True
        elif not arg.startswith('-') and command is None:
            # This is the command
            command = arg
        elif command is not None:
            # Everything after the command goes to command_args
            command_args.append(arg)
        
        i += 1
    
    # Reconstruct the arguments in the correct order
    result = [script_name]
    
    # Add global options first (they go at the root level)
    result.extend(global_args)
    
    # Then add command
    if command:
        result.append(command)
    
    # Then all command args
    result.extend(command_args)
    
    return result

def parse_dynamic_command(argv):
    """Parse command line for dynamic endpoint calls"""
    # Create a simple parser for global options
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument('--output', '-o', choices=['text', 'json', 'json-full'], default='text')
    parser.add_argument('--token', '-t')
    parser.add_argument('--verbose', '-v', action='store_true')
    
    # Find the command (first non-option argument)
    command = None
    remaining_args = []
    i = 1  # Skip script name
    while i < len(argv):
        arg = argv[i]
        if not arg.startswith('-'):
            command = arg
            # Collect remaining arguments after command
            remaining_args = argv[i+1:]
            break
        else:
            # Skip option and its value if needed
            if arg in ['--output', '-o', '--token', '-t'] and i + 1 < len(argv):
                i += 2
            else:
                i += 1
    
    # Parse global options from original argv
    global_args, _ = parser.parse_known_args(argv[1:])
    
    # Create dynamic args object
    class DynamicArgs:
        def __init__(self):
            self.command = command
            self.output = global_args.output
            self.token = global_args.token
            self.verbose = global_args.verbose
    
    args = DynamicArgs()
    
    # Parse remaining arguments as key-value pairs
    i = 0
    while i < len(remaining_args):
        arg = remaining_args[i]
        if arg.startswith('--'):
            key = arg[2:].replace('-', '_')
            # Check if next arg is a value or another option
            if i + 1 < len(remaining_args) and not remaining_args[i + 1].startswith('--'):
                value = remaining_args[i + 1]
                # Try to parse as integer if it looks like one
                if value.isdigit() or (value.startswith('-') and value[1:].isdigit()):
                    try:
                        value = int(value)
                    except ValueError:
                        pass  # Keep as string
                # Handle boolean values explicitly
                elif value.lower() in ['true', 'false']:
                    value = value.lower() == 'true'
                setattr(args, key, value)
                i += 2
            else:
                # Boolean flag
                setattr(args, key, True)
                i += 1
        else:
            i += 1
    
    return args, command

def main():
    # Debug output
    if os.environ.get('REDIACC_DEBUG_ARGS'):
        print(f"DEBUG: sys.argv = {sys.argv}", file=sys.stderr)
    
    # Check if this might be a dynamic command
    if len(sys.argv) > 1:
        # Get the first non-option argument (skip option values)
        potential_command = None
        skip_next = False
        for i, arg in enumerate(sys.argv[1:], 1):
            if skip_next:
                skip_next = False
                continue
            if arg.startswith('-'):
                # If this is an option that takes a value, skip the next arg
                if arg in ['--output', '-o', '--token', '-t'] and i < len(sys.argv) - 1:
                    skip_next = True
            else:
                # This is the command
                potential_command = arg
                break
        
        # Check if it's a known command
        known_commands = set(API_ENDPOINTS.keys()) | {'login', 'logout', 'license', 'workflow'}
        
        if potential_command and potential_command not in known_commands and potential_command not in CLI_COMMANDS:
            # This might be a dynamic endpoint
            args, command = parse_dynamic_command(sys.argv)
            
            if command:
                # Set up logging
                setup_logging(verbose=args.verbose)
                logger = get_logger(__name__)
                
                if args.verbose:
                    logger.debug("Dynamic endpoint detected")
                    logger.debug(f"Command: {command}")
                    logger.debug(f"Arguments: {vars(args)}")
                
                # Set up config manager
                config_manager = TokenManager()
                config_manager.load_vault_info_from_config()
                
                if args.token:
                    if not TokenManager.validate_token(args.token):
                        error = f"Invalid token format: {TokenManager.mask_token(args.token)}"
                        print(format_output(None, args.output, None, error))
                        return 1
                    os.environ['REDIACC_TOKEN'] = args.token
                    config_manager.set_token_overridden(True)
                
                handler = CommandHandler(config_manager, args.output)
                
                # Handle the dynamic endpoint (it will check auth requirements internally)
                return handler.handle_dynamic_endpoint(command, args)
    
    # Normal flow for known commands
    # Reorder arguments to handle global options before command
    sys.argv = reorder_args(sys.argv)
    
    parser = setup_parser()
    args = parser.parse_args()
    
    setup_logging(verbose=args.verbose)
    logger = get_logger(__name__)
    
    if args.verbose:
        logger.debug("Rediacc CLI starting up")
        logger.debug(f"Command: {args.command}")
        logger.debug(f"Arguments: {vars(args)}")
    
    if not args.command:
        parser.print_help()
        return 1
    
    output_format = args.output
    
    config_manager = TokenManager()
    config_manager.load_vault_info_from_config()
    
    if args.token:
        if not TokenManager.validate_token(args.token):
            error = f"Invalid token format: {TokenManager.mask_token(args.token)}"
            output = format_output(None, output_format, None, error)
            print(output)
            return 1
        os.environ['REDIACC_TOKEN'] = args.token
        config_manager.set_token_overridden(True)
    
    handler = CommandHandler(config_manager, output_format)
    
    # Check if user is requesting help for a generic command
    if hasattr(args, 'help') and args.help and args.command in API_ENDPOINTS:
        # Show help for command or resource
        resource = getattr(args, 'resource', None)
        help_text = handler.generate_dynamic_help(args.command, resource)
        print(help_text)
        return 0
    
    if args.command == 'login':
        return handler.login(args)
    elif args.command == 'logout':
        return handler.logout(args)
    elif args.command == 'license':
        return handler.handle_license_command(args)
    elif args.command == 'workflow':
        # Handle workflow commands
        if not hasattr(args, 'workflow_type') or not args.workflow_type:
            error = "No workflow type specified. Use 'rediacc workflow --help' to see available workflows."
            output = format_output(None, output_format, None, error)
            print(output)
            return 1
        
        # All workflow commands require authentication
        if not config_manager.is_authenticated():
            error = "Not authenticated. Please login first."
            output = format_output(None, output_format, None, error)
            print(output)
            return 1
        
        if args.workflow_type == 'repo-create':
            return handler.workflow_repo_create(args)
        elif args.workflow_type == 'repo-push':
            # Validate destination type requirements
            if args.dest_type == 'machine' and not args.dest_machine:
                error = "--dest-machine is required when --dest-type is 'machine'"
                output = format_output(None, output_format, None, error)
                print(output)
                return 1
            elif args.dest_type == 'storage' and not args.dest_storage:
                error = "--dest-storage is required when --dest-type is 'storage'"
                output = format_output(None, output_format, None, error)
                print(output)
                return 1
            return handler.workflow_repo_push(args)
        elif args.workflow_type == 'connectivity-test':
            return handler.workflow_connectivity_test(args)
        elif args.workflow_type == 'hello-test':
            return handler.workflow_hello_test(args)
        elif args.workflow_type == 'ssh-test':
            return handler.workflow_ssh_test(args)
        elif args.workflow_type == 'machine-setup':
            return handler.workflow_machine_setup(args)
        elif args.workflow_type == 'add-machine':
            return handler.workflow_add_machine(args)
        else:
            error = f"Unknown workflow type: {args.workflow_type}"
            output = format_output(None, output_format, None, error)
            print(output)
            return 1
    
    auth_not_required_commands = {
        ('login', None),  # Login doesn't require authentication
        ('user', 'activate'),
        ('create', 'company'),
        ('queue', 'list-functions')
    }
    
    standalone_commands = ['bridge']
    
    if (args.command, getattr(args, 'resource', None)) not in auth_not_required_commands:
        if not config_manager.is_authenticated():
            error = "Not authenticated. Please login first."
            output = format_output(None, output_format, None, error)
            print(output)
            return 1
    
    if not hasattr(args, 'resource') or not args.resource:
        # Show available resources for the command if no resource specified
        if args.command in API_ENDPOINTS:
            help_text = handler.generate_dynamic_help(args.command)
            print(help_text)
            return 0
        else:
            error = f"No resource specified for command: {args.command}"
            output = format_output(None, output_format, None, error)
            print(output)
            return 1
    
    if args.command == 'update':
        return handler.update_resource(args.resource, args)
    elif args.command in standalone_commands:
        return handler.generic_command(args.command, args.resource, args)
    elif args.command in API_ENDPOINTS:
        return handler.generic_command(args.command, args.resource, args)
    else:
        # Check if this could be a direct endpoint call
        # If command is not in API_ENDPOINTS and doesn't have a resource, treat as endpoint
        if not hasattr(args, 'resource') or not args.resource:
            return handler.handle_dynamic_endpoint(args.command, args)
        else:
            return handler.generic_command(args.command, args.resource, args)

if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\nOperation cancelled by user")
        sys.exit(130)