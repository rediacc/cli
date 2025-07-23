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
import urllib.request
import urllib.parse
import urllib.error
import base64
from typing import Dict, Any, Optional, List, Union
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core import (
    load_config, get_required, get, get_path, ConfigError,
    TokenManager, api_mutex, setup_logging, get_logger
)

from rediacc_cli_core import colorize, COLORS

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

from core import get_config_dir, get_main_config_file

HTTP_PORT = get_required('SYSTEM_HTTP_PORT')
BASE_URL = get_required('REDIACC_API_URL')
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

CLI_CONFIG_PATH = Path(__file__).parent.parent / 'config' / 'rediacc-cli.json'
try:
    with open(CLI_CONFIG_PATH, 'r') as f:
        cli_config = json.load(f)
        QUEUE_FUNCTIONS = cli_config['QUEUE_FUNCTIONS']
        CMD_CONFIG_JSON = cli_config['CMD_CONFIG']
        ARG_DEFS_JSON = cli_config['ARG_DEFS']
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
    return {key: process_value(value) for key, value in CMD_CONFIG_JSON.items()}

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
    
    return {key: process_value(value) for key, value in ARG_DEFS_JSON.items()}

CMD_CONFIG = reconstruct_cmd_config()
ARG_DEFS = reconstruct_arg_defs()

class APIClient:
    def __init__(self, config_manager):
        if not config_manager: raise ValueError("config_manager is required for APIClient to ensure proper token management")
        self.config_manager = config_manager
        self.config = config_manager.config if hasattr(config_manager, 'config') else {}
        self.base_headers = {"Content-Type": "application/json", "User-Agent": "rediacc-cli/1.0"}
        self.config_manager.load_vault_info_from_config()
    
    def request(self, endpoint, data=None, headers=None):
        url = f"{BASE_URL}{API_PREFIX}/{endpoint}"
        merged_headers = {**self.base_headers, **(headers or {})}
        
        if data and self.config_manager and (master_pwd := self.config_manager.get_master_password()):
            try: data = encrypt_vault_fields(data, master_pwd)
            except Exception as e: print(colorize(f"Warning: Failed to encrypt vault fields: {e}", 'YELLOW'))
        
        req = urllib.request.Request(url, json.dumps(data or {}).encode('utf-8'), merged_headers, method='POST')
        
        try:
            with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as response:
                response_data = response.read().decode('utf-8')
                if response.status != 200: return {"error": f"API Error: {response.status} - {response_data}", "status_code": response.status}
                
                result = json.loads(response_data)
                if result.get('failure') and result.get('failure') != 0:
                    errors = result.get('errors', [])
                    return {"error": f"API Error: {'; '.join(errors) if errors else result.get('message', 'Request failed')}", "status_code": 400}
                
                if self.config_manager and (master_pwd := self.config_manager.get_master_password()):
                    try: result = decrypt_vault_fields(result, master_pwd)
                    except Exception as e: print(colorize(f"Warning: Failed to decrypt vault fields: {e}", 'YELLOW'))
                
                return result
        except urllib.error.HTTPError as e:
            return {"error": f"API Error: {e.code} - {e.read().decode('utf-8') if e.fp else str(e)}", "status_code": e.code}
        except urllib.error.URLError as e:
            return {"error": f"Connection error: {str(e)}", "status_code": 500}
        except Exception as e:
            return {"error": f"Request error: {str(e)}", "status_code": 500}
    
    def auth_request(self, endpoint, email, pwd_hash, data=None):
        return self.request(endpoint, data, {"Rediacc-UserEmail": email, "Rediacc-UserHash": pwd_hash})
    
    def token_request(self, endpoint, data=None, retry_count=0):
        try:
            with api_mutex.acquire(timeout=30.0): return self._token_request_impl(endpoint, data, retry_count)
        except TimeoutError as e: return {"error": f"API call timeout: {str(e)}", "status_code": 408}
        except Exception as e: return {"error": f"API call error: {str(e)}", "status_code": 500}
    
    def _token_request_impl(self, endpoint, data=None, retry_count=0):
        if not (token := TokenManager.get_token()): return {"error": "Not authenticated. Please login first.", "status_code": 401}
        
        if endpoint != 'GetCompanyVault': self._ensure_vault_info(); self._show_vault_warning_if_needed()
        
        response = self.request(endpoint, data, {"Rediacc-RequestToken": token})
        
        if response and response.get('status_code') == 401 and retry_count < 2:
            import time; time.sleep(0.1 * (retry_count + 1))
            if TokenManager.get_token() != token: return self._token_request_impl(endpoint, data, retry_count + 1)
        
        self._update_token_if_needed(response, token)
        return response
    
    def _show_vault_warning_if_needed(self):
        if self.config_manager and self.config_manager.has_vault_encryption() and not self.config_manager.get_master_password() and not hasattr(self, '_vault_warning_shown'):
            print(colorize("Warning: Your company requires vault encryption but no master password is set.", 'YELLOW'))
            print(colorize("Vault fields will not be decrypted. Use 'rediacc vault set-password' to set it.", 'YELLOW'))
            self._vault_warning_shown = True
    
    def _update_token_if_needed(self, response, current_token):
        if not (response and not response.get('error') and self.config_manager): return
        if not (resultSets := response.get('resultSets', [])) or not resultSets[0].get('data'): return
        if not (new_token := resultSets[0]['data'][0].get('nextRequestCredential')) or new_token == current_token: return
        if os.environ.get('REDIACC_TOKEN') or self.config_manager.is_token_overridden(): return
        if TokenManager.get_token() == current_token:
            TokenManager.set_token(
                new_token,
                email=self.config_manager.config.get('email'),
                company=self.config_manager.config.get('company'),
                vault_company=self.config_manager.config.get('vault_company')
            )
    
    def _ensure_vault_info(self):
        if not (self.config_manager and self.config_manager.needs_vault_info_fetch()):
            return
        
        self.config_manager.mark_vault_info_fetched()
        
        company_info = self.get_company_vault()
        if not company_info:
            return
        
        email = self.config_manager.config.get('email')
        token = TokenManager.get_token()
        if email and token:
            self.config_manager.set_auth(
                email,
                token,
                company_info.get('companyName'),
                company_info.get('vaultCompany')
            )
    
    def get_company_vault(self):
        response = self.token_request("GetCompanyVault", {})
        
        if response.get('error'):
            return None
        
        for table in response.get('resultSets', []):
            data = table.get('data', [])
            if not data:
                continue
            
            row = data[0]
            if 'nextRequestCredential' in row:
                continue
            
            company_info = {
                'companyName': row.get('companyName', ''),
                'vaultCompany': row.get('vaultCompany') or row.get('VaultCompany', '')
            }
            
            if company_info['companyName']:
                return company_info
        
        return None

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
    
    skip_fields = skip_fields or ['nextRequestCredential', 'newUserHash']
    
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
    possible_urls = [
        "http://localhost:7322/api/health/hardware-id",
        "http://localhost:5000/api/health/hardware-id",
        "http://localhost:80/api/health/hardware-id",
    ]
    
    last_error = None
    for hardware_id_url in possible_urls:
        try:
            req = urllib.request.Request(hardware_id_url)
            with urllib.request.urlopen(req, timeout=5) as response:
                data = json.loads(response.read().decode('utf-8'))
                return data['hardwareId']
        except (urllib.error.URLError, Exception) as e:
            last_error = e
    
    raise Exception(
        f"Failed to generate hardware ID. Please ensure the middleware is running.\n"
        f"Try: ./go system up middleware\n"
        f"Last error: {str(last_error)}"
    )

def request_license_from_server(hardware_id, base_url=None):
    base_url = base_url or BASE_URL
    
    base_url = base_url.removesuffix('/api/StoredProcedure').removesuffix('/api')
    license_url = f"{base_url}/api/license/request"
    
    data = json.dumps({"HardwareId": hardware_id})
    req = urllib.request.Request(
        license_url,
        data=data.encode('utf-8'),
        headers={'Content-Type': 'application/json'}
    )
    
    try:
        with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as response:
            return json.loads(response.read().decode('utf-8'))
    except urllib.error.HTTPError as e:
        error_body = e.read().decode('utf-8')
        raise Exception(f"License server error {e.code}: {error_body}")
    except Exception as e:
        raise Exception(f"Failed to connect to license server: {str(e)}")

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
                    if 'vaultContent' in vault_data:
                        vault_content = vault_data.get('vaultContent', '{}')
                        try:
                            self.company_vault = json.loads(vault_content) if vault_content and vault_content != '-' else {}
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
        
        # Hardcode requirements for known functions until we update the config
        # Based on console's functions.json
        known_requirements = {
            'hello': {'machine': True, 'team': True},
            'ping': {'machine': True, 'team': True},
            'setup': {'machine': True, 'team': True},
            'new': {'machine': True, 'team': True},  # new doesn't need repository requirement during init
            'push': {'machine': True, 'team': True, 'repository': True},
            'pull': {'machine': True, 'team': True, 'repository': True},
            'mount': {'machine': True, 'team': True, 'repository': True},
            'unmount': {'machine': True, 'team': True, 'repository': True},
            'up': {'machine': True, 'team': True, 'repository': True},
            'down': {'machine': True, 'team': True, 'repository': True},
            'ssh_test': {'team': True}  # Bridge-only, no specific machine
        }
        
        if function_name in known_requirements:
            requirements = known_requirements[function_name]
        
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
        
        if self.output_format == 'json':
            data = {'task_id': format_args.task_id} if hasattr(format_args, 'task_id') and format_args.task_id else {}
            print(format_output(data, self.output_format, success_message))
        else:
            print(colorize(success_message, 'GREEN'))
        return True
    
    def login(self, args):
        email = args.email or input("Email: ")
        password = args.password or getpass.getpass("Password: ")
        hash_pwd = pwd_hash(password)
        
        login_params = {'name': args.session_name or "CLI Session"}
        
        for attr, param in [('tfa_code', '2FACode'), ('permissions', 'requestedPermissions'), ('expiration', 'tokenExpirationHours'), ('target', 'target')]:
            if hasattr(args, attr) and (value := getattr(args, attr)): login_params[param] = value
        
        response = self.client.auth_request("CreateAuthenticationRequest", email, hash_pwd, login_params)
        
        if response.get('error'): print(format_output(None, self.output_format, None, f"Login failed: {response['error']}")); return 1
        if not (resultSets := response.get('resultSets', [])) or not resultSets[0].get('data'): print(format_output(None, self.output_format, None, "Login failed: Could not get authentication token")); return 1
        auth_data = resultSets[0]['data'][0]
        if not (token := auth_data.get('nextRequestCredential')): print(format_output(None, self.output_format, None, "Login failed: Invalid authentication token")); return 1
        
        is_authorized = auth_data.get('isAuthorized', True)
        authentication_status = auth_data.get('authenticationStatus', '')
        
        if authentication_status == '2FA_REQUIRED' and not is_authorized:
            if not hasattr(args, 'tfa_code') or not args.tfa_code:
                if self.output_format != 'json':
                    from core import I18n
                    i18n = I18n()
                    tfa_code = input(i18n.get('enter_tfa_code'))
                else:
                    print(format_output(None, self.output_format, None, "2FA_REQUIRED. Please provide --tfa-code parameter."))
                    return 1
                
                login_params['2FACode'] = tfa_code
                response = self.client.auth_request("CreateAuthenticationRequest", email, hash_pwd, login_params)
                
                if response.get('error'):
                    print(format_output(None, self.output_format, None, f"2FA verification failed: {response['error']}"))
                    return 1
                
                resultSets = response.get('resultSets', [])
                if not resultSets or not resultSets[0].get('data'):
                    print(format_output(None, self.output_format, None, "2FA verification failed: Could not get authentication token"))
                    return 1
                
                auth_data = resultSets[0]['data'][0]
                token = auth_data.get('nextRequestCredential')
                if not token:
                    print(format_output(None, self.output_format, None, "2FA verification failed: Invalid authentication token"))
                    return 1
        
        company = auth_data.get('companyName')
        vault_company = auth_data.get('vaultCompany') or auth_data.get('VaultCompany')
        
        self.config_manager.set_token_with_auth(token, email, company, vault_company)
        
        # Check if company has vault encryption enabled
        if vault_company and is_encrypted(vault_company):
            # Company requires master password
            master_password = getattr(args, 'master_password', None)
            if not master_password:
                print(colorize("Your company requires a master password for vault encryption.", 'YELLOW'))
                master_password = getpass.getpass("Master Password: ")
            
            if self.config_manager.validate_master_password(master_password):
                self.config_manager.set_master_password(master_password)
                if self.output_format != 'json':
                    print(colorize("Master password validated successfully", 'GREEN'))
            else:
                print(format_output(None, self.output_format, None, 
                    "Invalid master password. Please check with your administrator for the correct company master password."))
                if self.output_format != 'json':
                    print(colorize("Warning: Logged in but vault data will not be decrypted", 'YELLOW'))
        elif hasattr(args, 'master_password') and args.master_password and self.output_format != 'json':
            print(colorize("Note: Your company has not enabled vault encryption. The master password will not be used.", 'YELLOW'))
        
        if self.output_format == 'json':
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
        
        if self.output_format == 'json':
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
                if self.output_format == 'json':
                    print(format_output(None, self.output_format, None, f"Missing required parameter: {param_name}"))
                    return False
                
                value = input(f"{param_info.get('help', param_name)}: ")
                setattr(args, param_name, value)
        return True
    
    def queue_list_functions(self, args):
        if self.output_format == 'json':
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
            if cmd_type not in CMD_CONFIG:
                return f"\nNo resources available for command '{cmd_type}'\n"
            
            resources = CMD_CONFIG.get(cmd_type, {})
            help_text = f"\nAvailable resources for '{colorize(cmd_type, 'BLUE')}':\n\n"
            
            # Calculate max width for alignment
            max_width = max(len(r) for r in resources.keys()) if resources else 0
            
            for resource, config in resources.items():
                help_info = config.get('help', {})
                desc = help_info.get('description', 'No description available')
                help_text += f"  {colorize(resource, 'GREEN'):<{max_width + 10}} {desc}\n"
            
            help_text += f"\nUse '{colorize(f'rediacc-cli {cmd_type} <resource> --help', 'YELLOW')}' for more details on a specific resource.\n"
            return help_text
        
        # Generate help for specific command
        if cmd_type not in CMD_CONFIG or resource_type not in CMD_CONFIG[cmd_type]:
            return f"\nNo help available for: {cmd_type} {resource_type}\n"
        
        config = CMD_CONFIG[cmd_type][resource_type]
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
        
        if cmd_type not in CMD_CONFIG or resource_type not in CMD_CONFIG[cmd_type]:
            print(format_output(None, self.output_format, None, f"Unsupported command: {cmd_type} {resource_type}"))
            return 1
        
        cmd_config = CMD_CONFIG[cmd_type][resource_type]
        auth_required = cmd_config.get('auth_required', True)
        
        password_prompts = [
            (cmd_type == 'create' and resource_type == 'user' and not hasattr(args, 'password'), 
             lambda: setattr(args, 'password', getpass.getpass("Password for new user: "))),
            (cmd_type == 'user' and resource_type == 'update-password' and not args.new_password,
             lambda: setattr(args, 'new_password', getpass.getpass("New password: "))),
            (cmd_type == 'user' and resource_type == 'update-2fa' and not hasattr(args, 'password'),
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
           (cmd_type == 'queue' and resource_type in ['get-next', 'list', 'trace']):
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
        endpoints = CMD_CONFIG['vault']['set']['endpoints']
        
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
    
    def workflow_repo_create(self, args):
        """Create repository and initialize it on machine"""
        try:
            # Step 1: Create repository record in database
            # Handle vault data - if not provided or empty, create with random credential
            vault_data = getattr(args, 'vault', '{}')
            if vault_data == '{}' or not vault_data:
                # Generate a random credential
                import secrets
                import string
                alphabet = string.ascii_letters + string.digits + string.punctuation
                random_credential = ''.join(secrets.choice(alphabet) for i in range(32))
                vault_data = json.dumps({"credential": random_credential})
            
            create_params = {
                'teamName': args.team,
                'repoName': args.name,
                'repoVault': vault_data
            }
            # Only add parentRepoName if provided
            if hasattr(args, 'parent') and args.parent:
                create_params['parentRepoName'] = args.parent
                
            repo_response = self.client.token_request("CreateRepository", create_params)
            
            if repo_response.get('error'):
                print(format_output(None, self.output_format, None, f"Failed to create repository: {repo_response['error']}"))
                return 1
            
            # Step 2: Get repository GUID by fetching team repositories
            repos_response = self.client.token_request("GetTeamRepositories", {
                'teamName': args.team
            })
            
            if repos_response.get('error'):
                # Rollback repository creation
                self._cleanup_repository(args.team, args.name)
                print(format_output(None, self.output_format, None, f"Failed to get repository list: {repos_response['error']}"))
                return 1
            
            # Find our repository and extract GUID
            repo_guid = None
            if len(repos_response.get('resultSets', [])) > 1:
                repos = repos_response['resultSets'][1].get('data', [])
                for repo in repos:
                    if repo.get('repoName') == args.name or repo.get('repositoryName') == args.name:
                        repo_guid = repo.get('repoGuid') or repo.get('repositoryGuid')
                        break
            
            if not repo_guid:
                # Rollback repository creation
                self._cleanup_repository(args.team, args.name)
                print(format_output(None, self.output_format, None, "Failed to get repository GUID"))
                return 1
            
            # Get machine data using helper method
            machine_data = self._get_machine_data(args.team, args.machine)
            if not machine_data:
                # Rollback repository creation
                self._cleanup_repository(args.team, args.name)
                return 1
            
            bridge_name = machine_data.get('bridgeName')
            machine_vault = machine_data.get('vaultContent', '{}')
            
            if not bridge_name:
                # Rollback repository creation
                self.client.token_request("DeleteRepository", {
                    'teamName': args.team,
                    'repoName': args.name
                })
                print(format_output(None, self.output_format, None, "Machine does not have an assigned bridge"))
                return 1
            
            # Get team vault data with SSH keys
            team_vault = self._get_team_vault(args.team)
            
            # Step 2: Build queue vault for 'new' function
            vault_builder = VaultBuilder(self.client)
            queue_vault = vault_builder.build_for_repo_create(
                team_name=args.team,
                machine_name=args.machine,
                repo_name=args.name,
                repo_guid=repo_guid,
                size=args.size,
                team_vault=team_vault,
                machine_vault=machine_vault
            )
            
            # Step 3: Create queue item to initialize repository on machine
            queue_response = self.client.token_request("CreateQueueItem", {
                'teamName': args.team,
                'machineName': args.machine,
                'bridgeName': bridge_name,
                'queueVault': queue_vault
            })
            
            if queue_response.get('error'):
                # Rollback repository creation
                self.client.token_request("DeleteRepository", {
                    'teamName': args.team,
                    'repoName': args.name
                })
                print(format_output(None, self.output_format, None, f"Failed to create queue item: {queue_response['error']}"))
                return 1
            
            # Extract task ID
            task_id = None
            if len(queue_response.get('resultSets', [])) > 1 and queue_response['resultSets'][1].get('data'):
                task_id = queue_response['resultSets'][1]['data'][0].get('taskId') or queue_response['resultSets'][1]['data'][0].get('TaskId')
            
            # Prepare result data
            result = {
                'repository_name': args.name,
                'repository_guid': repo_guid,
                'task_id': task_id,
                'team': args.team,
                'machine': args.machine,
                'size': args.size
            }
            
            # Output results
            if self.output_format in ['json', 'json-full']:
                if not getattr(args, 'wait', False):
                    print(format_output(result, self.output_format, f"Repository '{args.name}' created and initialization queued"))
            else:
                print(colorize(f"Repository '{args.name}' created successfully", 'GREEN'))
                print(f"Repository GUID: {repo_guid}")
                if task_id:
                    print(f"Initialization Task ID: {task_id}")
                    if getattr(args, 'trace', False):
                        print(colorize("Use 'rediacc queue trace' command to track progress", 'BLUE'))
            
            # Wait for completion if requested
            if getattr(args, 'wait', False) and task_id:
                if self.output_format != 'json':
                    print(colorize("Waiting for repository initialization...", 'BLUE'))
                poll_interval = getattr(args, 'poll_interval', 2)
                wait_timeout = getattr(args, 'wait_timeout', 300)
                completion_result = self._wait_for_task_completion(task_id, args.team, timeout=wait_timeout, poll_interval=poll_interval)
                
                if self.output_format in ['json', 'json-full']:
                    result = self._format_completion_result(result, completion_result)
                    print(format_output(result, self.output_format))
                else:
                    if completion_result['completed']:
                        print(colorize("Repository initialization completed successfully", 'GREEN'))
                        # Display command output if available
                        command_output = self._extract_command_output(completion_result)
                        if command_output:
                            print(colorize("\nCommand Output:", 'BLUE'))
                            # Clean up the output (replace \n with actual newlines)
                            clean_output = command_output.replace('\\n', '\n')
                            print(clean_output)
                    else:
                        print(colorize(f"Repository initialization {completion_result['status'].lower()}", 'RED'))
                        if completion_result.get('error'):
                            print(f"Error: {completion_result['error']}")
                        # Try to show command output even for failed tasks
                        command_output = self._extract_command_output(completion_result)
                        if command_output:
                            print(colorize("\nCommand Output:", 'YELLOW'))
                            clean_output = command_output.replace('\\n', '\n')
                            print(clean_output)
                        return 1
            
            return 0
            
        except Exception as e:
            print(format_output(None, self.output_format, None, f"Workflow error: {str(e)}"))
            return 1
    
    def workflow_repo_push(self, args):
        """Push repository with automatic destination creation"""
        try:
            # Get source repository data
            source_repo_response = self.client.token_request("GetTeamRepositories", {'teamName': args.source_team})
            if source_repo_response.get('error'):
                print(format_output(None, self.output_format, None, f"Failed to get source repositories: {source_repo_response['error']}"))
                return 1
            
            source_repo = None
            if len(source_repo_response.get('resultSets', [])) > 1:
                repos = source_repo_response['resultSets'][1].get('data', [])
                source_repo = next((r for r in repos if r.get('repoName') == args.source_repo), None)
            
            if not source_repo:
                print(format_output(None, self.output_format, None, f"Source repository '{args.source_repo}' not found"))
                return 1
            
            source_guid = source_repo.get('repoGuid')
            grand_guid = source_repo.get('grandGuid', source_guid)
            
            # Check if destination is machine or storage
            dest_type = getattr(args, 'dest_type', 'machine')
            dest_guid = None
            created_repo_name = None
            
            if dest_type == 'machine':
                # Check if destination repository exists
                dest_repo_response = self.client.token_request("GetTeamRepositories", {'teamName': args.dest_team})
                dest_repo = None
                if not dest_repo_response.get('error') and len(dest_repo_response.get('resultSets', [])) > 1:
                    repos = dest_repo_response['resultSets'][1].get('data', [])
                    dest_repo = next((r for r in repos if r.get('repoName') == args.dest_repo), None)
                
                if not dest_repo:
                    # Create destination repository
                    create_response = self.client.token_request("CreateRepository", {
                        'teamName': args.dest_team,
                        'repoName': args.dest_repo,
                        'repoVault': '{}',
                        'parentRepoName': args.source_repo
                    })
                    
                    if create_response.get('error'):
                        print(format_output(None, self.output_format, None, f"Failed to create destination repository: {create_response['error']}"))
                        return 1
                    
                    created_repo_name = args.dest_repo
                    
                    # Refetch to get the new repository GUID
                    dest_repo_response = self.client.token_request("GetTeamRepositories", {'teamName': args.dest_team})
                    if not dest_repo_response.get('error') and len(dest_repo_response.get('resultSets', [])) > 1:
                        repos = dest_repo_response['resultSets'][1].get('data', [])
                        dest_repo = next((r for r in repos if r.get('repoName') == args.dest_repo), None)
                
                if dest_repo:
                    dest_guid = dest_repo.get('repoGuid')
            
            # Get machine and vault data
            source_machine_data = self._get_machine_data(args.source_team, args.source_machine)
            if not source_machine_data:
                if created_repo_name:
                    self._cleanup_repository(args.dest_team, created_repo_name)
                return 1
            
            # Build push parameters
            push_params = {
                'src': args.source_path or '/',
                'dest': dest_guid if dest_type == 'machine' else args.dest_repo,
                'repo': source_guid,
                'grand': grand_guid,
                'destinationType': dest_type,
                'to': args.dest_machine if dest_type == 'machine' else args.dest_storage
            }
            
            # Get additional vault data if needed
            team_vault = self._get_team_vault(args.source_team)
            dest_machine_vault = None
            dest_storage_vault = None
            
            if dest_type == 'machine':
                dest_machine_data = self._get_machine_data(args.dest_team, args.dest_machine)
                if dest_machine_data:
                    dest_machine_vault = dest_machine_data.get('vaultContent', '{}')
            else:
                # Get storage vault data
                dest_storage_vault = self._get_storage_vault(args.dest_team, args.dest_storage)
            
            # Build queue vault
            vault_builder = VaultBuilder(self.client)
            context = {
                'teamName': args.source_team,
                'machineName': args.source_machine,
                'params': push_params,
                'teamVault': team_vault,
                'machineVault': source_machine_data.get('vaultContent', '{}'),
                'repositoryGuid': source_guid,
                'repositoryVault': source_repo.get('vaultContent', '{}'),
                'destinationGuid': dest_guid,
                'grandGuid': grand_guid
            }
            
            if dest_machine_vault:
                context['destinationMachineVault'] = dest_machine_vault
            if dest_storage_vault:
                context['destinationStorageVault'] = dest_storage_vault
            
            queue_vault = vault_builder.build_for_repo_push(context)
            
            # Create queue item
            queue_response = self.client.token_request("CreateQueueItem", {
                'teamName': args.source_team,
                'machineName': args.source_machine,
                'bridgeName': source_machine_data['bridgeName'],
                'queueVault': queue_vault
            })
            
            if queue_response.get('error'):
                if created_repo_name:
                    self._cleanup_repository(args.dest_team, created_repo_name)
                print(format_output(None, self.output_format, None, f"Failed to create queue item: {queue_response['error']}"))
                return 1
            
            # Extract task ID
            task_id = None
            if len(queue_response.get('resultSets', [])) > 1 and queue_response['resultSets'][1].get('data'):
                task_id = queue_response['resultSets'][1]['data'][0].get('taskId') or queue_response['resultSets'][1]['data'][0].get('TaskId')
            
            # Prepare result data
            result = {
                'source': f"{args.source_team}/{args.source_machine}/{args.source_repo}",
                'destination': f"{args.dest_team}/{args.dest_machine if dest_type == 'machine' else args.dest_storage}/{args.dest_repo}",
                'task_id': task_id,
                'created_destination': bool(created_repo_name)
            }
            
            # Output results
            if self.output_format in ['json', 'json-full']:
                if not getattr(args, 'wait', False):
                    print(format_output(result, self.output_format, "Repository push queued successfully"))
            else:
                print(colorize("Repository push queued successfully", 'GREEN'))
                print(f"Source: {args.source_team}/{args.source_machine}/{args.source_repo}")
                print(f"Destination: {args.dest_team}/{args.dest_machine if dest_type == 'machine' else args.dest_storage}/{args.dest_repo}")
                if created_repo_name:
                    print(colorize(f"Created destination repository: {created_repo_name}", 'BLUE'))
                if task_id:
                    print(f"Push Task ID: {task_id}")
                    if getattr(args, 'trace', False):
                        print(colorize("Use 'rediacc queue trace' command to track progress", 'BLUE'))
            
            # Wait for completion if requested
            if getattr(args, 'wait', False) and task_id:
                if self.output_format != 'json':
                    print(colorize("Waiting for push operation...", 'BLUE'))
                poll_interval = getattr(args, 'poll_interval', 2)
                wait_timeout = getattr(args, 'wait_timeout', 300)
                completion_result = self._wait_for_task_completion(task_id, args.source_team, timeout=wait_timeout, poll_interval=poll_interval)
                
                if self.output_format in ['json', 'json-full']:
                    result = self._format_completion_result(result, completion_result)
                    print(format_output(result, self.output_format))
                else:
                    if completion_result['completed']:
                        print(colorize("Push operation completed successfully", 'GREEN'))
                        # Display command output if available
                        command_output = self._extract_command_output(completion_result)
                        if command_output:
                            print("\nCommand output:")
                            print("-" * 50)
                            # Clean up the output (replace \n with actual newlines)
                            clean_output = command_output.replace('\\n', '\n')
                            print(clean_output)
                    else:
                        print(colorize(f"Push operation {completion_result['status'].lower()}", 'RED'))
                        if completion_result.get('error'):
                            print(f"Error: {completion_result['error']}")
                        return 1
            
            return 0
            
        except Exception as e:
            print(format_output(None, self.output_format, None, f"Workflow error: {str(e)}"))
            return 1
    
    def _get_machine_data(self, team_name, machine_name):
        """Helper to get machine data including bridge and vault"""
        # Get all machines for the team and find the specific one
        response = self.client.token_request("GetTeamMachines", {'teamName': team_name})
        
        if response.get('error'):
            print(format_output(None, self.output_format, None, f"Failed to get machine data: {response['error']}"))
            return None
        
        if len(response.get('resultSets', [])) > 1 and response['resultSets'][1].get('data'):
            machines = response['resultSets'][1]['data']
            machine_data = next((m for m in machines if m.get('machineName') == machine_name), None)
            
            if not machine_data:
                print(format_output(None, self.output_format, None, f"Machine '{machine_name}' not found in team '{team_name}'"))
                return None
                
            if not machine_data.get('bridgeName'):
                print(format_output(None, self.output_format, None, f"Machine '{machine_name}' does not have an assigned bridge"))
                return None
            return machine_data
        
        print(format_output(None, self.output_format, None, f"No machines found for team '{team_name}'"))
        return None
    
    def _get_team_vault(self, team_name):
        """Helper to get team vault data"""
        # Use GetCompanyTeams which returns teams with vaultContent
        response = self.client.token_request("GetCompanyTeams", {})
        if not response.get('error') and len(response.get('resultSets', [])) > 1:
            teams = response['resultSets'][1].get('data', [])
            for team in teams:
                if team.get('teamName') == team_name:
                    vault = team.get('vaultContent') or team.get('teamVault', '{}')
                    if os.environ.get('REDIACC_VERBOSE'):
                        print(f"DEBUG: _get_team_vault found team '{team_name}'")
                        print(f"DEBUG: Team vault length: {len(str(vault))}")
                        # Parse and check for SSH keys
                        try:
                            parsed = json.loads(vault) if isinstance(vault, str) else vault
                            print(f"DEBUG: Team vault has SSH_PRIVATE_KEY: {'SSH_PRIVATE_KEY' in parsed}")
                            print(f"DEBUG: Team vault has SSH_PUBLIC_KEY: {'SSH_PUBLIC_KEY' in parsed}")
                        except:
                            print("DEBUG: Failed to parse team vault")
                    return vault
        
        return '{}'
    
    def _get_storage_vault(self, team_name, storage_name):
        """Helper to get storage vault data"""
        response = self.client.token_request("GetTeamStorageSystems", {'teamName': team_name})
        if not response.get('error') and len(response.get('resultSets', [])) > 1:
            storages = response['resultSets'][1].get('data', [])
            storage = next((s for s in storages if s.get('storageName') == storage_name), None)
            if storage:
                return storage.get('vaultContent') or storage.get('storageVault', '{}')
        return None
    
    def _cleanup_repository(self, team_name, repo_name):
        """Helper to cleanup created repository on error"""
        try:
            self.client.token_request("DeleteRepository", {
                'teamName': team_name,
                'repoName': repo_name
            })
        except:
            pass
    
    def _extract_command_output(self, completion_result):
        """Extract command output from completion result"""
        # Don't check for completed status - we want output even for failed tasks
        if not completion_result.get('resultSets'):
            return None
            
        # Response vault is at table index 2 (resultSets array index 2)
        if len(completion_result['resultSets']) > 2:
            response_vault = completion_result['resultSets'][2]
            if response_vault and len(response_vault) > 0:
                vault_data = response_vault[0]
                if vault_data.get('vaultContent'):
                    try:
                        vault_content = json.loads(vault_data['vaultContent'])
                        if vault_content.get('result'):
                            result_data = json.loads(vault_content['result'])
                            return result_data.get('command_output', '')
                    except json.JSONDecodeError:
                        pass
        return None
    
    def _extract_bridge_result(self, completion_result):
        """Extract structured result data from bridge-only task completion"""
        if not completion_result.get('completed') or not completion_result.get('resultSets'):
            return None
            
        # Response vault is at table index 2 (resultSets array index 2)
        if len(completion_result['resultSets']) > 2:
            response_vault = completion_result['resultSets'][2]
            if response_vault and len(response_vault) > 0:
                vault_data = response_vault[0]
                if vault_data.get('vaultContent'):
                    try:
                        vault_content = json.loads(vault_data['vaultContent'])
                        if vault_content.get('result'):
                            return json.loads(vault_content['result'])
                    except json.JSONDecodeError:
                        pass
        return None
    
    def _format_completion_result(self, result, completion_result):
        """Format completion result based on output format"""
        if self.output_format == 'json-full':
            # Full output with all server resultSets
            result['completed'] = completion_result['completed']
            result['final_status'] = completion_result['status'].lower()
            result['server_tables'] = completion_result['resultSets']
            if completion_result.get('error'):
                result['error'] = completion_result['error']
        elif self.output_format == 'json':
            # Concise output with just essential info
            result['completed'] = completion_result['completed']
            result['final_status'] = completion_result['status'].lower()
            if completion_result.get('error'):
                result['error'] = completion_result['error']
            
            # Add command output or bridge result if available
            command_output = self._extract_command_output(completion_result)
            if command_output:
                result['command_output'] = command_output
            else:
                # Check for bridge result (structured data)
                bridge_result = self._extract_bridge_result(completion_result)
                if bridge_result:
                    result['result'] = bridge_result
        
        return result
    
    def _wait_for_task_completion(self, task_id, team_name, timeout=300, poll_interval=2):
        """Wait for a task to complete with timeout, returning full response data"""
        start_time = time.time()
        last_status = None
        
        while time.time() - start_time < timeout:
            # Use GetQueueItemTrace to get status of specific task
            response = self.client.token_request("GetQueueItemTrace", {
                'taskId': task_id
            })
            
            if response.get('error'):
                if os.environ.get('REDIACC_VERBOSE'):
                    print(f"DEBUG: Error getting queue trace: {response.get('error')}")
                # Continue polling even on error - task might still be running
                time.sleep(poll_interval)
                continue
            
            # GetQueueItemTrace returns multiple resultSets
            # We include all resultSets except table 0 (which contains nextRequestCredential)
            resultSets = response.get('resultSets', [])
            if len(resultSets) > 1:
                # Get status from table 1 (queue details)
                task_data = resultSets[1].get('data', [{}])[0] if resultSets[1].get('data') else {}
                status = task_data.get('status', '').upper()
                
                if status != last_status:
                    last_status = status
                    if self.output_format not in ['json', 'json-full']:
                        print(f"  Status: {status}")
                
                # Check if task is done
                if status in ['COMPLETED', 'FAILED', 'CANCELLED', 'ERROR']:
                    # Return all resultSets except table 0
                    result = {
                        'completed': status == 'COMPLETED',
                        'status': status,
                        'resultSets': []
                    }
                    
                    # Include all resultSets except table 0 (credentials)
                    for i in range(1, len(resultSets)):
                        result['resultSets'].append(resultSets[i].get('data', []))
                    
                    return result
            
            time.sleep(poll_interval)  # Poll at specified interval
        
        if os.environ.get('REDIACC_VERBOSE'):
            print(f"DEBUG: Task timed out after {timeout} seconds")
        
        # Return timeout result
        return {
            'completed': False,
            'status': 'TIMEOUT',
            'resultSets': [],
            'error': f'Task timed out after {timeout} seconds'
        }
    
    def workflow_connectivity_test(self, args):
        """Test connectivity for multiple machines"""
        try:
            # Get machines for the specified team(s)
            team_filter = getattr(args, 'team', None)
            if isinstance(team_filter, str):
                teams = [team_filter]
            else:
                teams = team_filter if team_filter else []
            
            all_machines = []
            for team in teams:
                machines_response = self.client.token_request("GetTeamMachines", {'teamName': team})
                if not machines_response.get('error') and len(machines_response.get('resultSets', [])) > 1:
                    machines = machines_response['resultSets'][1].get('data', [])
                    all_machines.extend(machines)
            
            if not all_machines:
                print(format_output(None, self.output_format, None, "No machines found for the specified team(s)"))
                return 1
            
            # Filter by specific machines if provided
            if hasattr(args, 'machines') and args.machines:
                machine_names = args.machines if isinstance(args.machines, list) else args.machines.split(',')
                all_machines = [m for m in all_machines if m.get('machineName') in machine_names]
            
            results = []
            total = len(all_machines)
            
            if self.output_format not in ['json', 'json-full']:
                print(colorize(f"Testing connectivity for {total} machine(s)...", 'BLUE'))
            
            # Test each machine sequentially
            for i, machine in enumerate(all_machines):
                machine_name = machine.get('machineName')
                team_name = machine.get('teamName')
                bridge_name = machine.get('bridgeName')
                
                if not bridge_name:
                    results.append({
                        'machineName': machine_name,
                        'teamName': team_name,
                        'status': 'failed',
                        'message': 'No bridge assigned',
                        'duration': 0
                    })
                    continue
                
                start_time = time.time()
                
                if self.output_format not in ['json', 'json-full']:
                    print(f"\n[{i+1}/{total}] Testing {machine_name}...")
                
                # Get machine vault data
                machine_vault = machine.get('vaultContent', '{}')
                team_vault = self._get_team_vault(team_name)
                
                # Build ping vault
                vault_builder = VaultBuilder(self.client)
                queue_vault = vault_builder.build_for_ping(
                    team_name=team_name,
                    machine_name=machine_name,
                    bridge_name=bridge_name,
                    team_vault=team_vault,
                    machine_vault=machine_vault
                )
                
                # Create queue item
                queue_response = self.client.token_request("CreateQueueItem", {
                    'teamName': team_name,
                    'machineName': machine_name,
                    'bridgeName': bridge_name,
                    'queueVault': queue_vault
                })
                
                if queue_response.get('error'):
                    results.append({
                        'machineName': machine_name,
                        'teamName': team_name,
                        'status': 'failed',
                        'message': queue_response['error'],
                        'duration': time.time() - start_time
                    })
                    continue
                
                # Get task ID
                task_id = None
                if len(queue_response.get('resultSets', [])) > 1 and queue_response['resultSets'][1].get('data'):
                    task_id = queue_response['resultSets'][1]['data'][0].get('taskId') or queue_response['resultSets'][1]['data'][0].get('TaskId')
                
                if not task_id:
                    results.append({
                        'machineName': machine_name,
                        'teamName': team_name,
                        'status': 'failed',
                        'message': 'No task ID returned',
                        'duration': time.time() - start_time
                    })
                    continue
                
                # Wait for completion
                if getattr(args, 'wait', True):  # Default to waiting
                    poll_interval = getattr(args, 'poll_interval', 1)  # Faster polling for connectivity tests
                    wait_timeout = getattr(args, 'wait_timeout', 30)  # Shorter timeout for ping
                    
                    completion_result = self._wait_for_task_completion(task_id, team_name, timeout=wait_timeout, poll_interval=poll_interval)
                    
                    results.append({
                        'machineName': machine_name,
                        'teamName': team_name,
                        'bridgeName': bridge_name,
                        'taskId': task_id,
                        'status': 'success' if completion_result['completed'] else 'failed',
                        'message': 'Connected' if completion_result['completed'] else completion_result.get('error', 'Connection failed'),
                        'duration': time.time() - start_time,
                        'server_tables': completion_result.get('resultSets', []) if getattr(args, 'wait', False) else None
                    })
                else:
                    results.append({
                        'machineName': machine_name,
                        'teamName': team_name,
                        'bridgeName': bridge_name,
                        'taskId': task_id,
                        'status': 'queued',
                        'message': 'Test queued',
                        'duration': time.time() - start_time
                    })
            
            # Output results
            if self.output_format in ['json', 'json-full']:
                successful = len([r for r in results if r['status'] == 'success'])
                failed = len([r for r in results if r['status'] == 'failed'])
                output = {
                    'total': total,
                    'successful': successful,
                    'failed': failed,
                    'results': results
                }
                # For concise JSON, remove server_tables from results
                if self.output_format == 'json':
                    for result in output['results']:
                        if 'server_tables' in result:
                            # Extract command output if available
                            if result.get('server_tables'):
                                # Try to extract command output
                                command_output = None
                                if len(result['server_tables']) > 2:
                                    response_vault = result['server_tables'][2]
                                    if response_vault and len(response_vault) > 0:
                                        vault_data = response_vault[0]
                                        if vault_data.get('vaultContent'):
                                            try:
                                                vault_content = json.loads(vault_data['vaultContent'])
                                                if vault_content.get('result'):
                                                    result_data = json.loads(vault_content['result'])
                                                    command_output = result_data.get('command_output', '')
                                            except json.JSONDecodeError:
                                                pass
                                if command_output:
                                    result['command_output'] = command_output
                            del result['server_tables']
                print(format_output(output, self.output_format))
            else:
                # Summary
                print(colorize("\nConnectivity Test Results", 'HEADER'))
                print("=" * 50)
                
                # Table format
                successful = 0
                failed = 0
                for result in results:
                    status_color = 'GREEN' if result['status'] == 'success' else 'RED'
                    status_text = '✓' if result['status'] == 'success' else '✗'
                    duration = f"{result['duration']:.1f}s" if result['duration'] < 10 else f"{result['duration']:.0f}s"
                    
                    print(f"{colorize(status_text, status_color)} {result['machineName']:<20} {result['teamName']:<15} {duration:<6} {result['message']}")
                    
                    if result['status'] == 'success':
                        successful += 1
                    elif result['status'] == 'failed':
                        failed += 1
                
                print("\n" + "-" * 50)
                print(f"Total: {total} | " + 
                      colorize(f"Success: {successful}", 'GREEN') + " | " +
                      colorize(f"Failed: {failed}", 'RED'))
                
                # Average response time for successful tests
                successful_results = [r for r in results if r['status'] == 'success']
                if successful_results:
                    avg_duration = sum(r['duration'] for r in successful_results) / len(successful_results)
                    print(f"Average response time: {avg_duration:.1f}s")
            
            return 0
            
        except Exception as e:
            print(format_output(None, self.output_format, None, f"Workflow error: {str(e)}"))
            return 1
    
    def workflow_hello_test(self, args):
        """Simple hello test for machine connectivity"""
        try:
            # Get machine data
            machine_data = self._get_machine_data(args.team, args.machine)
            if not machine_data:
                return 1
            
            # Get vault data
            team_vault = self._get_team_vault(args.team)
            machine_vault = machine_data.get('vaultContent', '{}')
            bridge_name = machine_data.get('bridgeName')
            
            # Build hello vault
            vault_builder = VaultBuilder(self.client)
            queue_vault = vault_builder.build_for_hello(
                team_name=args.team,
                machine_name=args.machine,
                bridge_name=bridge_name,
                team_vault=team_vault,
                machine_vault=machine_vault
            )
            
            # Create queue item
            queue_response = self.client.token_request("CreateQueueItem", {
                'teamName': args.team,
                'machineName': args.machine,
                'bridgeName': bridge_name,
                'queueVault': queue_vault
            })
            
            if queue_response.get('error'):
                print(format_output(None, self.output_format, None, f"Failed to create queue item: {queue_response['error']}"))
                return 1
            
            # Extract task ID
            task_id = None
            if len(queue_response.get('resultSets', [])) > 1 and queue_response['resultSets'][1].get('data'):
                task_id = queue_response['resultSets'][1]['data'][0].get('taskId') or queue_response['resultSets'][1]['data'][0].get('TaskId')
            
            # Prepare result data
            result = {
                'machine': args.machine,
                'team': args.team,
                'task_id': task_id
            }
            
            # Output results
            if self.output_format in ['json', 'json-full']:
                if not getattr(args, 'wait', False):
                    print(format_output(result, self.output_format, "Hello test queued successfully"))
            else:
                print(colorize(f"Hello test queued for machine '{args.machine}'", 'GREEN'))
                if task_id:
                    print(f"Task ID: {task_id}")
            
            # Wait for completion if requested
            if getattr(args, 'wait', False) and task_id:
                if self.output_format not in ['json', 'json-full']:
                    print(colorize("Waiting for hello response...", 'BLUE'))
                poll_interval = getattr(args, 'poll_interval', 2)
                wait_timeout = getattr(args, 'wait_timeout', 30)
                
                completion_result = self._wait_for_task_completion(task_id, args.team, timeout=wait_timeout, poll_interval=poll_interval)
                
                if self.output_format in ['json', 'json-full']:
                    result = self._format_completion_result(result, completion_result)
                    print(format_output(result, self.output_format))
                else:
                    if completion_result['completed']:
                        print(colorize("Hello test completed successfully", 'GREEN'))
                        # Display command output if available
                        command_output = self._extract_command_output(completion_result)
                        if command_output:
                            print("\nCommand output:")
                            print("-" * 50)
                            # Clean up the output (replace \n with actual newlines)
                            clean_output = command_output.replace('\\n', '\n')
                            print(clean_output)
                    else:
                        print(colorize(f"Hello test {completion_result['status'].lower()}", 'RED'))
                        if completion_result.get('error'):
                            print(f"Error: {completion_result['error']}")
                        return 1
            
            return 0
            
        except Exception as e:
            print(format_output(None, self.output_format, None, f"Workflow error: {str(e)}"))
            return 1
    
    def workflow_ssh_test(self, args):
        """Test SSH connectivity for bridge"""
        try:
            # For SSH test, we need bridge information and SSH credentials
            # This is a special case where we might not need a specific machine
            
            # Build machine vault with SSH credentials
            machine_vault = {
                'ip': args.host,
                'user': args.user,
                'datastore': getattr(args, 'datastore', '/mnt/datastore')
            }
            
            # Add SSH password if provided
            if hasattr(args, 'password') and args.password:
                machine_vault['ssh_password'] = args.password
            
            machine_vault_str = json.dumps(machine_vault)
            
            # Get team vault for SSH keys
            team_vault = self._get_team_vault(args.team) if hasattr(args, 'team') and args.team else '{}'
            
            # Build SSH test vault with team context for SSH keys
            vault_builder = VaultBuilder(self.client)
            queue_vault = vault_builder.build_for_ssh_test(
                bridge_name=args.bridge,
                machine_vault=machine_vault_str,
                team_name=args.team,
                team_vault=team_vault
            )
            
            # Debug: Print the generated vault length only
            if os.environ.get('REDIACC_VERBOSE') and self.output_format != 'json':
                print(f"DEBUG: Generated vault length: {len(queue_vault)} characters")
            
            # Create queue item (bridge-only, no machine specified)
            # Note: API still requires teamName even for bridge-only tasks
            if not hasattr(args, 'team') or not args.team:
                print(format_output(None, self.output_format, None, "Error: --team is required for ssh-test workflow"))
                return 1
            
            queue_response = self.client.token_request("CreateQueueItem", {
                'teamName': args.team,
                'bridgeName': args.bridge,
                'queueVault': queue_vault
            })
            
            if queue_response.get('error'):
                print(format_output(None, self.output_format, None, f"Failed to create queue item: {queue_response['error']}"))
                return 1
            
            # Extract task ID
            task_id = None
            if len(queue_response.get('resultSets', [])) > 1 and queue_response['resultSets'][1].get('data'):
                task_id = queue_response['resultSets'][1]['data'][0].get('taskId') or queue_response['resultSets'][1]['data'][0].get('TaskId')
            
            # Prepare result data
            result = {
                'bridge': args.bridge,
                'host': args.host,
                'user': args.user,
                'task_id': task_id
            }
            
            # Output results
            if self.output_format in ['json', 'json-full']:
                if not getattr(args, 'wait', False):
                    print(format_output(result, self.output_format, "SSH test queued successfully"))
            else:
                print(colorize(f"SSH test queued for {args.user}@{args.host} via bridge '{args.bridge}'", 'GREEN'))
                if task_id:
                    print(f"Task ID: {task_id}")
            
            # Wait for completion if requested
            if getattr(args, 'wait', False) and task_id:
                if self.output_format not in ['json', 'json-full']:
                    print(colorize("Waiting for SSH test...", 'BLUE'))
                poll_interval = getattr(args, 'poll_interval', 2)
                wait_timeout = getattr(args, 'wait_timeout', 30)
                
                # For bridge-only tasks, we might not have a team name
                team_name = getattr(args, 'team', '')
                
                completion_result = self._wait_for_task_completion(task_id, team_name, timeout=wait_timeout, poll_interval=poll_interval)
                
                if self.output_format in ['json', 'json-full']:
                    result = self._format_completion_result(result, completion_result)
                    print(format_output(result, self.output_format))
                else:
                    if completion_result['completed']:
                        print(colorize("SSH test completed successfully", 'GREEN'))
                        # For bridge-only tasks, display structured result data
                        bridge_result = self._extract_bridge_result(completion_result)
                        if bridge_result:
                            print("\nSSH Test Results:")
                            print("-" * 50)
                            print(f"Status: {bridge_result.get('status', 'unknown')}")
                            print(f"Message: {bridge_result.get('message', 'No message')}")
                            print(f"Auth Method: {bridge_result.get('auth_method', 'unknown')}")
                            if 'kernel_compatibility' in bridge_result:
                                kernel_info = bridge_result['kernel_compatibility']
                                if 'os_info' in kernel_info:
                                    print(f"OS: {kernel_info['os_info'].get('pretty_name', 'Unknown')}")
                                print(f"Kernel: {kernel_info.get('kernel_version', 'Unknown')}")
                                print(f"Compatibility: {kernel_info.get('compatibility_status', 'unknown')}")
                    else:
                        print(colorize(f"SSH test {completion_result['status'].lower()}", 'RED'))
                        if completion_result.get('error'):
                            print(f"Error: {completion_result['error']}")
                        return 1
            
            return 0
            
        except Exception as e:
            print(format_output(None, self.output_format, None, f"Workflow error: {str(e)}"))
            return 1
    
    def workflow_machine_setup(self, args):
        """Setup a new machine with datastore and dependencies"""
        try:
            # Get machine data
            machine_data = self._get_machine_data(args.team, args.machine)
            if not machine_data:
                return 1
            
            # Get vault data
            team_vault = self._get_team_vault(args.team)
            machine_vault = machine_data.get('vaultContent', '{}')
            bridge_name = machine_data.get('bridgeName')
            
            # Build setup parameters
            setup_params = {
                'datastore_size': getattr(args, 'datastore_size', '95%'),
                'source': getattr(args, 'source', 'apt-repo'),
                'rclone_source': getattr(args, 'rclone_source', 'install-script'),
                'docker_source': getattr(args, 'docker_source', 'docker-repo'),
                'install_amd_driver': getattr(args, 'install_amd_driver', 'auto'),
                'install_nvidia_driver': getattr(args, 'install_nvidia_driver', 'auto'),
                'kernel_module_mode': getattr(args, 'kernel_module_mode', 'auto')
            }
            
            # Build setup vault
            vault_builder = VaultBuilder(self.client)
            queue_vault = vault_builder.build_for_setup(
                team_name=args.team,
                machine_name=args.machine,
                bridge_name=bridge_name,
                params=setup_params,
                team_vault=team_vault,
                machine_vault=machine_vault
            )
            
            # Create queue item
            queue_response = self.client.token_request("CreateQueueItem", {
                'teamName': args.team,
                'machineName': args.machine,
                'bridgeName': bridge_name,
                'queueVault': queue_vault
            })
            
            if queue_response.get('error'):
                print(format_output(None, self.output_format, None, f"Failed to create queue item: {queue_response['error']}"))
                return 1
            
            # Extract task ID
            task_id = None
            if len(queue_response.get('resultSets', [])) > 1 and queue_response['resultSets'][1].get('data'):
                task_id = queue_response['resultSets'][1]['data'][0].get('taskId') or queue_response['resultSets'][1]['data'][0].get('TaskId')
            
            # Prepare result data
            result = {
                'machine': args.machine,
                'team': args.team,
                'task_id': task_id,
                'datastore_size': setup_params['datastore_size']
            }
            
            # Output results
            if self.output_format in ['json', 'json-full']:
                if not getattr(args, 'wait', False):
                    print(format_output(result, self.output_format, "Machine setup queued successfully"))
            else:
                print(colorize(f"Machine setup queued for '{args.machine}'", 'GREEN'))
                print(f"Datastore size: {setup_params['datastore_size']}")
                if task_id:
                    print(f"Task ID: {task_id}")
                    if getattr(args, 'trace', False):
                        print(colorize("Use 'rediacc queue trace' command to track progress", 'BLUE'))
            
            # Wait for completion if requested
            if getattr(args, 'wait', False) and task_id:
                if self.output_format != 'json':
                    print(colorize("Waiting for machine setup... (this may take several minutes)", 'BLUE'))
                poll_interval = getattr(args, 'poll_interval', 5)  # Slower polling for long operations
                wait_timeout = getattr(args, 'wait_timeout', 600)  # 10 minutes default for setup
                
                completion_result = self._wait_for_task_completion(task_id, args.team, timeout=wait_timeout, poll_interval=poll_interval)
                
                if self.output_format in ['json', 'json-full']:
                    result = self._format_completion_result(result, completion_result)
                    print(format_output(result, self.output_format))
                else:
                    if completion_result['completed']:
                        print(colorize("Machine setup completed successfully", 'GREEN'))
                        # Display command output if available
                        command_output = self._extract_command_output(completion_result)
                        if command_output:
                            print("\nCommand output:")
                            print("-" * 50)
                            # Clean up the output (replace \n with actual newlines)
                            clean_output = command_output.replace('\\n', '\n')
                            print(clean_output)
                    else:
                        print(colorize(f"Machine setup {completion_result['status'].lower()}", 'RED'))
                        if completion_result.get('error'):
                            print(f"Error: {completion_result['error']}")
                        return 1
            
            return 0
            
        except Exception as e:
            print(format_output(None, self.output_format, None, f"Workflow error: {str(e)}"))
            return 1
    
    def workflow_add_machine(self, args):
        """Create machine and test SSH connection"""
        try:
            # Step 1: Create machine record in database using existing create command infrastructure
            vault_data = getattr(args, 'vault', '{}')
            if vault_data == '{}' or not vault_data:
                # Create basic machine vault with common fields
                vault_data = json.dumps({
                    "ip": "",
                    "user": "",
                    "datastore": "/mnt/datastore"
                })
            
            # Create a fake args object for the create machine command
            class CreateArgs:
                def __init__(self, team, bridge, name, vault):
                    self.team = team
                    self.bridge = bridge
                    self.name = name
                    self.vault = vault
                    self.vault_file = None
            
            create_args = CreateArgs(args.team, args.bridge, args.name, vault_data)
            
            # Use the existing create machine command
            create_result = self.generic_command('create', 'machine', create_args)
            
            if create_result != 0:
                print(format_output(None, self.output_format, None, f"Failed to create machine: {args.name}"))
                return 1
            
            # Log machine creation success
            if self.output_format not in ['json', 'json-full']:
                print(colorize(f"Machine '{args.name}' created in team '{args.team}'", 'GREEN'))
            
            # Step 2: Test connection if not skipped and SSH credentials are available
            test_connection_success = False
            ssh_test_task_id = None
            
            if not getattr(args, 'no_test', False):
                # Parse vault data to check for SSH credentials
                try:
                    vault_json = json.loads(vault_data)
                    has_ssh_creds = vault_json.get('ip') and vault_json.get('user')
                    
                    if has_ssh_creds:
                        # Get team vault for SSH keys
                        team_vault = self._get_team_vault(args.team)
                        
                        # Build SSH test vault
                        vault_builder = VaultBuilder(self.client)
                        ssh_queue_vault = vault_builder.build_for_ssh_test(
                            bridge_name=args.bridge,
                            machine_vault=vault_data,
                            team_name=args.team,
                            team_vault=team_vault
                        )
                        
                        # Create SSH test queue item
                        ssh_response = self.client.token_request("CreateQueueItem", {
                            'teamName': args.team,
                            'bridgeName': args.bridge,
                            'queueVault': ssh_queue_vault
                        })
                        
                        if ssh_response.get('error'):
                            if self.output_format not in ['json', 'json-full']:
                                print(colorize(f"Warning: SSH test failed to queue: {ssh_response['error']}", 'YELLOW'))
                        else:
                            # Extract SSH test task ID
                            if len(ssh_response.get('resultSets', [])) > 1 and ssh_response['resultSets'][1].get('data'):
                                ssh_test_task_id = ssh_response['resultSets'][1]['data'][0].get('taskId') or ssh_response['resultSets'][1]['data'][0].get('TaskId')
                            
                            if self.output_format not in ['json', 'json-full']:
                                print(colorize("SSH connectivity test queued", 'BLUE'))
                                if ssh_test_task_id:
                                    print(f"SSH Test Task ID: {ssh_test_task_id}")
                            
                            # Wait for SSH test if requested
                            if getattr(args, 'wait', False) and ssh_test_task_id:
                                if self.output_format not in ['json', 'json-full']:
                                    print(colorize("Waiting for SSH test...", 'BLUE'))
                                
                                ssh_completion = self._wait_for_task_completion(
                                    ssh_test_task_id, 
                                    args.team, 
                                    timeout=getattr(args, 'wait_timeout', 30),
                                    poll_interval=getattr(args, 'poll_interval', 2)
                                )
                                
                                if ssh_completion['completed']:
                                    test_connection_success = True
                                    if self.output_format not in ['json', 'json-full']:
                                        print(colorize("SSH test completed successfully", 'GREEN'))
                                        
                                        # Display SSH test results
                                        bridge_result = self._extract_bridge_result(ssh_completion)
                                        if bridge_result:
                                            print("\nSSH Test Results:")
                                            print("-" * 50)
                                            print(f"Status: {bridge_result.get('status', 'unknown')}")
                                            print(f"Auth Method: {bridge_result.get('auth_method', 'unknown')}")
                                            if 'kernel_compatibility' in bridge_result:
                                                kernel_info = bridge_result['kernel_compatibility']
                                                if 'os_info' in kernel_info:
                                                    print(f"OS: {kernel_info['os_info'].get('pretty_name', 'Unknown')}")
                                                print(f"Kernel: {kernel_info.get('kernel_version', 'Unknown')}")
                                                print(f"Compatibility: {kernel_info.get('compatibility_status', 'unknown')}")
                                else:
                                    if self.output_format not in ['json', 'json-full']:
                                        print(colorize(f"SSH test {ssh_completion['status'].lower()}", 'YELLOW'))
                                        if ssh_completion.get('error'):
                                            print(f"SSH Test Error: {ssh_completion['error']}")
                    else:
                        if self.output_format not in ['json', 'json-full']:
                            print(colorize("SSH test skipped: No SSH credentials in machine vault", 'YELLOW'))
                        
                except json.JSONDecodeError:
                    if self.output_format not in ['json', 'json-full']:
                        print(colorize("SSH test skipped: Invalid vault JSON", 'YELLOW'))
            else:
                if self.output_format not in ['json', 'json-full']:
                    print(colorize("SSH test skipped (--no-test specified)", 'YELLOW'))
            
            # Step 3: Run machine setup if connection test succeeded and auto-setup requested
            setup_task_id = None
            if test_connection_success and getattr(args, 'auto_setup', False):
                if self.output_format not in ['json', 'json-full']:
                    print(colorize("Starting automatic machine setup...", 'BLUE'))
                
                # Build setup parameters
                setup_params = {
                    'datastore_size': getattr(args, 'datastore_size', '95%'),
                    'source': 'apt-repo',
                    'rclone_source': 'install-script',
                    'docker_source': 'docker-repo',
                    'install_amd_driver': 'auto',
                    'install_nvidia_driver': 'auto',
                    'kernel_module_mode': 'auto'
                }
                
                # Get machine and team vault data  
                team_vault = self._get_team_vault(args.team)
                
                # Build setup vault
                vault_builder = VaultBuilder(self.client)
                setup_queue_vault = vault_builder.build_for_setup(
                    team_name=args.team,
                    machine_name=args.name,
                    bridge_name=args.bridge,
                    params=setup_params,
                    team_vault=team_vault,
                    machine_vault=vault_data
                )
                
                # Create setup queue item
                setup_response = self.client.token_request("CreateQueueItem", {
                    'teamName': args.team,
                    'machineName': args.name,
                    'bridgeName': args.bridge,
                    'queueVault': setup_queue_vault
                })
                
                if setup_response.get('error'):
                    if self.output_format not in ['json', 'json-full']:
                        print(colorize(f"Warning: Machine setup failed to queue: {setup_response['error']}", 'YELLOW'))
                else:
                    # Extract setup task ID
                    if len(setup_response.get('resultSets', [])) > 1 and setup_response['resultSets'][1].get('data'):
                        setup_task_id = setup_response['resultSets'][1]['data'][0].get('taskId') or setup_response['resultSets'][1]['data'][0].get('TaskId')
                    
                    if self.output_format not in ['json', 'json-full']:
                        print(colorize("Machine setup queued", 'GREEN'))
                        if setup_task_id:
                            print(f"Setup Task ID: {setup_task_id}")
            
            # Prepare result data
            result = {
                'machine': args.name,
                'team': args.team,
                'bridge': args.bridge,
                'ssh_test_success': test_connection_success,
                'ssh_test_task_id': ssh_test_task_id,
                'setup_task_id': setup_task_id
            }
            
            # Output final results
            if self.output_format in ['json', 'json-full']:
                print(format_output(result, self.output_format, "Machine creation workflow completed"))
            else:
                print(colorize("\nMachine Creation Workflow Summary:", 'HEADER'))
                print("=" * 50)
                print(f"Machine: {args.name}")
                print(f"Team: {args.team}")
                print(f"Bridge: {args.bridge}")
                print(f"SSH Test: {'Passed' if test_connection_success else 'Skipped/Failed'}")
                if ssh_test_task_id:
                    print(f"SSH Test Task ID: {ssh_test_task_id}")
                if setup_task_id:
                    print(f"Setup Task ID: {setup_task_id}")
                    print(colorize("Tip: Use 'rediacc queue trace' to monitor setup progress", 'BLUE'))
            
            return 0
            
        except Exception as e:
            print(format_output(None, self.output_format, None, f"Workflow error: {str(e)}"))
            return 1

def setup_parser():
    parser = argparse.ArgumentParser(
        description='Rediacc CLI - Complete interface for Rediacc Middleware API with enhanced queue support'
    )
    parser.add_argument('--output', '-o', choices=['text', 'json', 'json-full'], default='text',
                       help='Output format: text, json (concise), or json-full (comprehensive)')
    parser.add_argument('--token', '-t', help='Authentication token (overrides saved token)')
    parser.add_argument('--verbose', '-v', action='store_true',
                       help='Enable verbose logging output')
    
    subparsers = parser.add_subparsers(dest='command', help='Command')
    
    for cmd_name, cmd_def in ARG_DEFS.items():
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
                    for arg in subcmd_def:
                        kwargs = {k: v for k, v in arg.items() if k != 'name'}
                        subcmd_parser.add_argument(arg['name'], **kwargs)
                    
                    if cmd_name == 'update' and subcmd_name in ['team', 'region', 'bridge', 'machine', 'repository', 'storage', 'schedule']:
                        subcmd_parser.add_argument('--vault', help='JSON vault data')
                        subcmd_parser.add_argument('--vault-file', help='File containing JSON vault data')
                        subcmd_parser.add_argument('--vault-version', type=int, help='Vault version')
                        
                        if subcmd_name == 'machine':
                            subcmd_parser.add_argument('--new-bridge', help='New bridge name for machine')
    
    license_parser = subparsers.add_parser('license', help='License management commands')
    license_subparsers = license_parser.add_subparsers(dest='license_command', help='License commands')
    
    generate_id_parser = license_subparsers.add_parser('generate-id', help='Generate hardware ID for offline licensing')
    generate_id_parser.add_argument('--output', '-o', help='Output file (default: hardware-id.txt)')
    
    request_parser = license_subparsers.add_parser('request', help='Request license using hardware ID')
    request_parser.add_argument('--hardware-id', '-i', required=True, help='Hardware ID or file containing it')
    request_parser.add_argument('--output', '-o', help='Output file (default: license.lic)')
    request_parser.add_argument('--server-url', '-s', help='License server URL (optional)')
    
    install_parser = license_subparsers.add_parser('install', help='Install license file')
    install_parser.add_argument('--file', '-f', required=True, help='License file to install')
    install_parser.add_argument('--target', '-t', help='Target directory (default: auto-detect)')
    
    # Add workflow commands
    workflow_parser = subparsers.add_parser('workflow', help='High-level workflow commands')
    workflow_subparsers = workflow_parser.add_subparsers(dest='workflow_type', help='Workflow commands')
    
    # Repository creation workflow
    repo_create_parser = workflow_subparsers.add_parser('repo-create', help='Create and initialize repository on machine')
    repo_create_parser.add_argument('--team', required=True, help='Team name')
    repo_create_parser.add_argument('--name', required=True, help='Repository name')
    repo_create_parser.add_argument('--machine', required=True, help='Machine to initialize repository on')
    repo_create_parser.add_argument('--size', required=True, help='Repository size (e.g., 1G, 500M, 10G)')
    repo_create_parser.add_argument('--vault', help='Repository vault data (JSON)')
    repo_create_parser.add_argument('--parent', help='Parent repository name')
    repo_create_parser.add_argument('--trace', action='store_true', help='Show task ID for tracking')
    repo_create_parser.add_argument('--wait', action='store_true', help='Wait for completion')
    repo_create_parser.add_argument('--poll-interval', type=int, default=2, help='Polling interval in seconds when waiting (default: 2)')
    repo_create_parser.add_argument('--wait-timeout', type=int, default=300, help='Timeout in seconds when waiting (default: 300)')
    
    # Repository push workflow
    repo_push_parser = workflow_subparsers.add_parser('repo-push', help='Push repository with automatic destination creation')
    repo_push_parser.add_argument('--source-team', required=True, help='Source team name')
    repo_push_parser.add_argument('--source-machine', required=True, help='Source machine name')
    repo_push_parser.add_argument('--source-repo', required=True, help='Source repository name')
    repo_push_parser.add_argument('--source-path', default='/', help='Source path within repository (default: /)')
    repo_push_parser.add_argument('--dest-team', required=True, help='Destination team name')
    repo_push_parser.add_argument('--dest-repo', required=True, help='Destination repository name')
    repo_push_parser.add_argument('--dest-type', choices=['machine', 'storage'], default='machine', help='Destination type')
    repo_push_parser.add_argument('--dest-machine', help='Destination machine name (required for machine destination)')
    repo_push_parser.add_argument('--dest-storage', help='Destination storage name (required for storage destination)')
    repo_push_parser.add_argument('--trace', action='store_true', help='Show task ID for tracking')
    repo_push_parser.add_argument('--wait', action='store_true', help='Wait for completion')
    repo_push_parser.add_argument('--poll-interval', type=int, default=2, help='Polling interval in seconds when waiting (default: 2)')
    repo_push_parser.add_argument('--wait-timeout', type=int, default=300, help='Timeout in seconds when waiting (default: 300)')
    
    # Connectivity test workflow
    connectivity_parser = workflow_subparsers.add_parser('connectivity-test', help='Test connectivity to multiple machines')
    connectivity_parser.add_argument('--team', required=True, help='Team name')
    connectivity_parser.add_argument('--machines', nargs='+', required=True, help='Machine names to test')
    connectivity_parser.add_argument('--wait', action='store_true', help='Wait for completion')
    connectivity_parser.add_argument('--poll-interval', type=int, default=2, help='Polling interval in seconds when waiting (default: 2)')
    connectivity_parser.add_argument('--wait-timeout', type=int, default=30, help='Timeout in seconds per machine when waiting (default: 30)')
    
    # Hello test workflow
    hello_parser = workflow_subparsers.add_parser('hello-test', help='Execute hello function on machine')
    hello_parser.add_argument('--team', required=True, help='Team name')
    hello_parser.add_argument('--machine', required=True, help='Machine name')
    hello_parser.add_argument('--wait', action='store_true', help='Wait for completion')
    hello_parser.add_argument('--poll-interval', type=int, default=2, help='Polling interval in seconds when waiting (default: 2)')
    hello_parser.add_argument('--wait-timeout', type=int, default=30, help='Timeout in seconds when waiting (default: 30)')
    
    # SSH test workflow
    ssh_test_parser = workflow_subparsers.add_parser('ssh-test', help='Test SSH connectivity through bridge')
    ssh_test_parser.add_argument('--team', required=True, help='Team name (required by API)')
    ssh_test_parser.add_argument('--bridge', required=True, help='Bridge name')
    ssh_test_parser.add_argument('--host', required=True, help='Target host to test')
    ssh_test_parser.add_argument('--user', required=True, help='SSH username')
    ssh_test_parser.add_argument('--password', help='SSH password (optional)')
    ssh_test_parser.add_argument('--wait', action='store_true', help='Wait for completion')
    ssh_test_parser.add_argument('--poll-interval', type=int, default=2, help='Polling interval in seconds when waiting (default: 2)')
    ssh_test_parser.add_argument('--wait-timeout', type=int, default=30, help='Timeout in seconds when waiting (default: 30)')
    
    # Machine setup workflow
    setup_parser = workflow_subparsers.add_parser('machine-setup', help='Setup machine with datastore')
    setup_parser.add_argument('--team', required=True, help='Team name')
    setup_parser.add_argument('--machine', required=True, help='Machine name')
    setup_parser.add_argument('--datastore-size', default='default', help='Datastore size (default: default)')
    setup_parser.add_argument('--wait', action='store_true', help='Wait for completion')
    setup_parser.add_argument('--poll-interval', type=int, default=2, help='Polling interval in seconds when waiting (default: 2)')
    setup_parser.add_argument('--wait-timeout', type=int, default=300, help='Timeout in seconds when waiting (default: 300)')
    
    # Add machine workflow
    add_machine_parser = workflow_subparsers.add_parser('add-machine', help='Create machine with SSH connection test')
    add_machine_parser.add_argument('--team', required=True, help='Team name')
    add_machine_parser.add_argument('--name', required=True, help='Machine name')
    add_machine_parser.add_argument('--bridge', required=True, help='Bridge name')
    add_machine_parser.add_argument('--vault', help='Machine vault data (JSON) with ip, user, ssh_password, etc.')
    add_machine_parser.add_argument('--no-test', action='store_true', help='Skip SSH connection test')
    add_machine_parser.add_argument('--auto-setup', action='store_true', help='Automatically run machine setup if SSH test passes')
    add_machine_parser.add_argument('--datastore-size', default='95%', help='Datastore size for auto-setup (default: 95%%)')
    add_machine_parser.add_argument('--wait', action='store_true', help='Wait for SSH test completion')
    add_machine_parser.add_argument('--trace', action='store_true', help='Show task IDs for tracking')
    add_machine_parser.add_argument('--poll-interval', type=int, default=2, help='Polling interval in seconds when waiting (default: 2)')
    add_machine_parser.add_argument('--wait-timeout', type=int, default=30, help='Timeout in seconds when waiting for SSH test (default: 30)')
    
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

def main():
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
    if hasattr(args, 'help') and args.help and args.command in CMD_CONFIG:
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
        if args.command in CMD_CONFIG:
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
    else:
        return handler.generic_command(args.command, args.resource, args)

if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\nOperation cancelled by user")
        sys.exit(130)