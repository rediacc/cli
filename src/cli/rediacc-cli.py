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

try:
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    CRYPTO_AVAILABLE = True
except ImportError:
    CRYPTO_AVAILABLE = False

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

COLORS = {
    'HEADER': '\033[95m', 'BLUE': '\033[94m', 'GREEN': '\033[92m',
    'YELLOW': '\033[93m', 'RED': '\033[91m', 'ENDC': '\033[0m', 'BOLD': '\033[1m',
}

def colorize(text, color):
    return f"{COLORS.get(color, '')}{text}{COLORS['ENDC']}" if sys.stdout.isatty() else text

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
        if not (tables := response.get('tables', [])) or not tables[0].get('data'): return
        if not (new_token := tables[0]['data'][0].get('nextRequestCredential')) or new_token == current_token: return
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
        
        for table in response.get('tables', []):
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
    if format_type == 'json':
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
    return response.get('tables', [])[table_index].get('data', []) if response and len(response.get('tables', [])) > table_index else []

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

def table_to_dict(headers, rows):
    return [{header: row[i] for i, header in enumerate(headers) if i < len(row)} for row in rows]

def format_dynamic_tables(response, output_format='text', skip_fields=None):
    if not response or 'tables' not in response:
        return format_output("No data available", output_format)
    
    tables = response.get('tables', [])
    if len(tables) <= 1:
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
        for table in tables[1:]:
            processed = process_table_data(table)
            if processed:
                result.extend(processed)
        return format_output(result, output_format)
    
    output_parts = []
    for table in tables[1:]:
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

class CommandHandler:
    def __init__(self, config_manager, output_format='text'):
        self.config = config_manager.config
        self.config_manager = config_manager
        self.client = APIClient(config_manager)
        self.output_format = output_format
    
    def handle_response(self, response, success_message=None, format_args=None):
        if response.get('error'): print(format_output(None, self.output_format, None, response['error'])); return False
        
        if success_message and format_args and '{task_id}' in success_message:
            if (tables := response.get('tables', [])) and len(tables) > 1 and tables[1].get('data'):
                if task_id := tables[1]['data'][0].get('taskId') or tables[1]['data'][0].get('TaskId'):
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
        if not (tables := response.get('tables', [])) or not tables[0].get('data'): print(format_output(None, self.output_format, None, "Login failed: Could not get authentication token")); return 1
        auth_data = tables[0]['data'][0]
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
                
                tables = response.get('tables', [])
                if not tables or not tables[0].get('data'):
                    print(format_output(None, self.output_format, None, "2FA verification failed: Could not get authentication token"))
                    return 1
                
                auth_data = tables[0]['data'][0]
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
        
        tables = response.get('tables', [])
        task_id = None
        if len(tables) > 1 and tables[1].get('data'):
            task_id = tables[1]['data'][0].get('taskId', tables[1]['data'][0].get('TaskId'))
        
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
                        'tables': [
                            response['tables'][0],  # Keep credentials table
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
        if not response or 'tables' not in response:
            return format_output("No trace data available", output_format)
        
        tables = response.get('tables', [])
        if len(tables) < 2:
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
            if len(tables) > 1 and tables[1].get('data'):
                item_data = tables[1]['data'][0] if tables[1]['data'] else {}
                result['queue_item'] = item_data
            
            # Table 2 (index 2): Request Vault
            if len(tables) > 2 and tables[2].get('data'):
                vault_data = tables[2]['data'][0] if tables[2]['data'] else {}
                result['request_vault'] = {
                    'type': vault_data.get('VaultType', 'Request'),
                    'version': vault_data.get('VaultVersion'),
                    'content': vault_data.get('VaultContent'),
                    'has_content': vault_data.get('HasContent', False)
                }
            
            # Table 3 (index 3): Response Vault
            if len(tables) > 3 and tables[3].get('data'):
                vault_data = tables[3]['data'][0] if tables[3]['data'] else {}
                result['response_vault'] = {
                    'type': vault_data.get('VaultType', 'Response'),
                    'version': vault_data.get('VaultVersion'),
                    'content': vault_data.get('VaultContent'),
                    'has_content': vault_data.get('HasContent', False)
                }
            
            # Table 4 (index 4): Timeline
            if len(tables) > 4 and tables[4].get('data'):
                result['timeline'] = tables[4]['data']
            
            return format_output(result, output_format)
        else:
            output_parts = []
            
            if len(tables) > 1 and tables[1].get('data') and tables[1]['data']:
                item_data = tables[1]['data'][0]
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
                
            if len(tables) > 2 and tables[2].get('data') and tables[2]['data']:
                vault_data = tables[2]['data'][0]
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
            
            if len(tables) > 3 and tables[3].get('data') and tables[3]['data']:
                vault_data = tables[3]['data'][0]
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
            
            if len(tables) > 4 and tables[4].get('data') and tables[4]['data']:
                output_parts.append("")
                output_parts.append(colorize("PROCESSING TIMELINE", 'HEADER'))
                output_parts.append("=" * 80)
                
                timeline_data = tables[4]['data']
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

def setup_parser():
    parser = argparse.ArgumentParser(
        description='Rediacc CLI - Complete interface for Rediacc Middleware API with enhanced queue support'
    )
    parser.add_argument('--output', '-o', choices=['text', 'json'], default='text',
                       help='Output format (text or json)')
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
    
    return parser

def main():
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
    
    if args.command == 'login':
        return handler.login(args)
    elif args.command == 'logout':
        return handler.logout(args)
    elif args.command == 'license':
        return handler.handle_license_command(args)
    
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