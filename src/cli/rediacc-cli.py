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

# Add parent directory to path for module imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import configuration loader
from config_loader import load_config, get_required, get, get_path, ConfigError

# Import token manager
from token_manager import TokenManager

# Import API mutex for concurrent access safety
from api_mutex import api_mutex

# Import logging configuration
from logging_config import setup_logging, get_logger

# Try to import cryptography library
try:
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    CRYPTO_AVAILABLE = True
except ImportError:
    CRYPTO_AVAILABLE = False
    # Print warning after colorize is defined

# Load configuration
try:
    load_config()
except ConfigError as e:
    print(f"Configuration error: {e}", file=sys.stderr)
    sys.exit(1)

# Configuration
HTTP_PORT = get_required('SYSTEM_HTTP_PORT')
BASE_URL = get_required('REDIACC_API_URL')
API_PREFIX = '/StoredProcedure'
# Use centralized config path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config_path import get_config_dir, get_main_config_file

CONFIG_DIR = str(get_config_dir())
CONFIG_FILE = str(get_main_config_file())
REQUEST_TIMEOUT = 30
TEST_ACTIVATION_CODE = get('REDIACC_TEST_ACTIVATION_CODE') or '111111'

# Color codes for terminal output
COLORS = {
    'HEADER': '\033[95m', 'BLUE': '\033[94m', 'GREEN': '\033[92m',
    'YELLOW': '\033[93m', 'RED': '\033[91m', 'ENDC': '\033[0m', 'BOLD': '\033[1m',
}

def colorize(text, color):
    """Add color to terminal output if supported"""
    return f"{COLORS.get(color, '')}{text}{COLORS['ENDC']}" if sys.stdout.isatty() else text

# Print crypto warning if needed (to stderr to avoid contaminating JSON output)
if not CRYPTO_AVAILABLE:
    print(colorize("Warning: cryptography library not installed. Vault encryption will not be available.", 'YELLOW'), file=sys.stderr)
    # Check if we're in MSYS2 environment
    if os.environ.get('MSYSTEM') or (sys.platform == 'win32' and ('/msys' in sys.executable.lower() or '/mingw' in sys.executable.lower())):
        print(colorize("For MSYS2: Run 'pacman -S mingw-w64-x86_64-python-cryptography' or './scripts/install_msys2_packages.sh'", 'YELLOW'), file=sys.stderr)
    else:
        print(colorize("Install with: pip install cryptography", 'YELLOW'), file=sys.stderr)

# Load CLI configuration from JSON file
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

# Vault Encryption Functions
# Following the same protocol as the web console (AES-256-GCM with PBKDF2)
ITERATIONS = 100000
SALT_SIZE = 16  # 128 bits
IV_SIZE = 12    # 96 bits for GCM
TAG_SIZE = 16   # 128 bits for GCM
KEY_SIZE = 32   # 256 bits

def derive_key(password: str, salt: bytes) -> bytes:
    """Derive a 256-bit key from password using PBKDF2-HMAC-SHA256"""
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
    """Encrypt a string using AES-256-GCM
    Returns base64 encoded string: salt || iv || ciphertext || authTag
    """
    if not CRYPTO_AVAILABLE:
        raise RuntimeError("Cryptography library not available")
    
    # Generate random salt and IV
    salt = os.urandom(SALT_SIZE)
    iv = os.urandom(IV_SIZE)
    
    # Derive key
    key = derive_key(password, salt)
    aesgcm = AESGCM(key)
    
    # Encrypt (ciphertext includes auth tag at the end)
    ciphertext = aesgcm.encrypt(iv, plaintext.encode('utf-8'), None)
    
    # Combine salt + IV + ciphertext (includes auth tag)
    combined = salt + iv + ciphertext
    
    # Return base64 encoded
    return base64.b64encode(combined).decode('ascii')

def decrypt_string(encrypted: str, password: str) -> str:
    """Decrypt a string encrypted with encrypt_string
    Expects base64 encoded string: salt || iv || ciphertext || authTag
    """
    if not CRYPTO_AVAILABLE:
        raise RuntimeError("Cryptography library not available")
    
    # Decode from base64
    combined = base64.b64decode(encrypted)
    
    # Extract components
    salt = combined[:SALT_SIZE]
    iv = combined[SALT_SIZE:SALT_SIZE + IV_SIZE]
    ciphertext = combined[SALT_SIZE + IV_SIZE:]
    
    # Derive key
    key = derive_key(password, salt)
    aesgcm = AESGCM(key)
    
    # Decrypt
    plaintext = aesgcm.decrypt(iv, ciphertext, None)
    return plaintext.decode('utf-8')

def is_encrypted(value: str) -> bool:
    """Check if a value appears to be encrypted
    Encrypted values are base64 encoded and typically longer than the original
    """
    if not value or len(value) < 20:
        return False
    
    # Check if the value is valid JSON (not encrypted)
    try:
        json.loads(value)
        # If it parses as JSON, it's not encrypted
        return False
    except:
        # Not valid JSON, continue checking if it's encrypted
        pass
    
    # Check if it matches base64 pattern and has reasonable length
    # Encrypted values are typically much longer than originals due to IV + encrypted data
    import re
    base64_pattern = re.compile(r'^[A-Za-z0-9+/]+=*$')
    return base64_pattern.match(value) is not None and len(value) >= 40

def encrypt_vault_fields(obj: dict, password: str) -> dict:
    """Recursively encrypt fields containing 'vault' in their name"""
    if not password or not obj:
        return obj
    
    result = {}
    for key, value in obj.items():
        if 'vault' in key.lower() and isinstance(value, str) and value:
            if not is_encrypted(value):
                try:
                    result[key] = encrypt_string(value, password)
                except Exception as e:
                    print(colorize(f"Warning: Failed to encrypt field {key}: {e}", 'YELLOW'))
                    result[key] = value
            else:
                result[key] = value
        elif isinstance(value, dict):
            result[key] = encrypt_vault_fields(value, password)
        elif isinstance(value, list):
            result[key] = [
                encrypt_vault_fields(item, password) if isinstance(item, dict) else item
                for item in value
            ]
        else:
            result[key] = value
    return result

def decrypt_vault_fields(obj: dict, password: str) -> dict:
    """Recursively decrypt fields containing 'vault' in their name"""
    if not password or not obj:
        return obj
    
    result = {}
    for key, value in obj.items():
        if 'vault' in key.lower() and isinstance(value, str) and value:
            if is_encrypted(value):
                try:
                    result[key] = decrypt_string(value, password)
                except Exception as e:
                    print(colorize(f"Warning: Failed to decrypt field {key}: {e}", 'YELLOW'))
                    result[key] = value
            else:
                result[key] = value
        elif isinstance(value, dict):
            result[key] = decrypt_vault_fields(value, password)
        elif isinstance(value, list):
            result[key] = [
                decrypt_vault_fields(item, password) if isinstance(item, dict) else item
                for item in value
            ]
        else:
            result[key] = value
    return result

# Available bash functions for queuing
# Convert lambda functions from JSON strings to actual functions
def reconstruct_cmd_config():
    """Reconstruct CMD_CONFIG with actual lambda functions"""
    cmd_config = {}
    for key, value in CMD_CONFIG_JSON.items():
        if isinstance(value, dict):
            if 'params' in value and isinstance(value['params'], str) and value['params'].startswith('lambda'):
                # Create a new dict with the lambda evaluated
                cmd_config[key] = value.copy()
                cmd_config[key]['params'] = eval(value['params'])
            else:
                # Nested dict (like 'create', 'list', etc.)
                cmd_config[key] = {}
                for sub_key, sub_value in value.items():
                    if isinstance(sub_value, dict) and 'params' in sub_value and isinstance(sub_value['params'], str) and sub_value['params'].startswith('lambda'):
                        cmd_config[key][sub_key] = sub_value.copy()
                        cmd_config[key][sub_key]['params'] = eval(sub_value['params'])
                    else:
                        cmd_config[key][sub_key] = sub_value
        else:
            cmd_config[key] = value
    return cmd_config

# Convert ARG_DEFS type lambdas
def reconstruct_arg_defs():
    """Reconstruct ARG_DEFS with actual type functions"""
    arg_defs = {}
    for key, value in ARG_DEFS_JSON.items():
        if isinstance(value, list):
            arg_defs[key] = []
            for arg in value:
                if isinstance(arg, dict) and 'type' in arg and isinstance(arg['type'], str) and arg['type'].startswith('lambda'):
                    new_arg = arg.copy()
                    new_arg['type'] = eval(arg['type'])
                    arg_defs[key].append(new_arg)
                elif isinstance(arg, dict) and 'type' in arg and arg['type'] == 'int':
                    new_arg = arg.copy()
                    new_arg['type'] = int
                    arg_defs[key].append(new_arg)
                else:
                    arg_defs[key].append(arg)
        elif isinstance(value, dict):
            arg_defs[key] = {}
            for sub_key, sub_value in value.items():
                if isinstance(sub_value, list):
                    arg_defs[key][sub_key] = []
                    for arg in sub_value:
                        if isinstance(arg, dict) and 'type' in arg and isinstance(arg['type'], str) and arg['type'].startswith('lambda'):
                            new_arg = arg.copy()
                            new_arg['type'] = eval(arg['type'])
                            arg_defs[key][sub_key].append(new_arg)
                        elif isinstance(arg, dict) and 'type' in arg and arg['type'] == 'int':
                            new_arg = arg.copy()
                            new_arg['type'] = int
                            arg_defs[key][sub_key].append(new_arg)
                        else:
                            arg_defs[key][sub_key].append(arg)
                else:
                    arg_defs[key][sub_key] = sub_value
        else:
            arg_defs[key] = value
    return arg_defs

# Reconstruct configurations with actual functions
CMD_CONFIG = reconstruct_cmd_config()
ARG_DEFS = reconstruct_arg_defs()

# NOTE: ConfigManager class was removed and consolidated into TokenManager
# All configuration management is now handled by TokenManager in token_manager.py
# This eliminates code duplication and provides better thread safety and token management

class APIClient:
    """Client for interacting with the Rediacc Middleware API"""
    def __init__(self, config_manager):
        """Initialize API client with required config_manager for proper token management"""
        if not config_manager:
            raise ValueError("config_manager is required for APIClient to ensure proper token management")
        
        self.config_manager = config_manager
        self.config = config_manager.config if hasattr(config_manager, 'config') else {}
        self.base_headers = {
            "Content-Type": "application/json",
            "User-Agent": "rediacc-cli/1.0"
        }
        # Load vault info from config
        self.config_manager.load_vault_info_from_config()
    
    def request(self, endpoint, data=None, headers=None):
        """Make an API request to the middleware service"""
        url = f"{BASE_URL}{API_PREFIX}/{endpoint}"
        
        # Merge headers
        merged_headers = self.base_headers.copy()
        if headers:
            merged_headers.update(headers)
        
        # Encrypt vault fields if master password is set
        if data and self.config_manager and self.config_manager.get_master_password():
            try:
                data = encrypt_vault_fields(data, self.config_manager.get_master_password())
            except Exception as e:
                print(colorize(f"Warning: Failed to encrypt vault fields: {e}", 'YELLOW'))
        
        # Prepare the request
        request_data = json.dumps(data or {}).encode('utf-8')
        req = urllib.request.Request(
            url,
            data=request_data,
            headers=merged_headers,
            method='POST'
        )
        
        try:
            # Make the request with timeout
            with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as response:
                response_data = response.read().decode('utf-8')
                
                if response.status != 200:
                    return {"error": f"API Error: {response.status} - {response_data}", 
                            "status_code": response.status}
                
                result = json.loads(response_data)
                
                # Check for actual failure (failure != 0)
                if result.get('failure') and result.get('failure') != 0:
                    errors = result.get('errors', [])
                    if errors and len(errors) > 0:
                        error_msg = f"API Error: {'; '.join(errors)}"
                    else:
                        error_msg = f"API Error: {result.get('message', 'Request failed')}"
                    return {"error": error_msg, "status_code": 400}
                
                # Decrypt vault fields if master password is set
                if self.config_manager and self.config_manager.get_master_password():
                    try:
                        result = decrypt_vault_fields(result, self.config_manager.get_master_password())
                    except Exception as e:
                        print(colorize(f"Warning: Failed to decrypt vault fields: {e}", 'YELLOW'))
                
                return result
                
        except urllib.error.HTTPError as e:
            error_body = e.read().decode('utf-8') if e.fp else str(e)
            return {"error": f"API Error: {e.code} - {error_body}", "status_code": e.code}
        except urllib.error.URLError as e:
            return {"error": f"Connection error: {str(e)}", "status_code": 500}
        except Exception as e:
            return {"error": f"Request error: {str(e)}", "status_code": 500}
    
    def auth_request(self, endpoint, email, pwd_hash, data=None):
        """Make an authenticated request with user credentials"""
        return self.request(endpoint, data, {
            "Rediacc-UserEmail": email,
            "Rediacc-UserHash": pwd_hash
        })
    
    def token_request(self, endpoint, data=None, retry_count=0):
        """Make a request authenticated with a token"""
        # Use mutex to ensure only one API call at a time
        # This prevents token rotation race conditions
        try:
            with api_mutex.acquire(timeout=30.0):
                return self._token_request_impl(endpoint, data, retry_count)
        except TimeoutError as e:
            return {"error": f"API call timeout: {str(e)}", "status_code": 408}
        except Exception as e:
            return {"error": f"API call error: {str(e)}", "status_code": 500}
    
    def _token_request_impl(self, endpoint, data=None, retry_count=0):
        """Implementation of token request (called within mutex)"""
        # Use TokenManager to get token (it handles env vars and file reading)
        token = TokenManager.get_token()
        if not token:
            return {"error": "Not authenticated. Please login first.", "status_code": 401}
        
        # Ensure vault info is fetched before making requests (except for GetCompanyVault itself)
        if endpoint != 'GetCompanyVault':
            self._ensure_vault_info()
            
            # Check if encryption is required but no master password is set
            if self.config_manager and self.config_manager.has_vault_encryption() and not self.config_manager.get_master_password():
                if not hasattr(self, '_vault_warning_shown'):
                    print(colorize("Warning: Your company requires vault encryption but no master password is set.", 'YELLOW'))
                    print(colorize("Vault fields will not be decrypted. Use 'rediacc vault set-password' to set it.", 'YELLOW'))
                    self._vault_warning_shown = True
        
        response = self.request(endpoint, data, {
            "Rediacc-RequestToken": token
        })
        
        # Handle token race condition - retry if we get 401 and token has changed
        if response and response.get('status_code') == 401 and retry_count < 2:
            # Brief delay to let other process complete token rotation
            import time
            time.sleep(0.1 * (retry_count + 1))
            
            # Check if token changed (indicating another process rotated it)
            new_current_token = TokenManager.get_token()
            if new_current_token != token:
                # Token changed, retry with new token
                return self._token_request_impl(endpoint, data, retry_count + 1)
        
        # Update token if a new one is provided (token chain mechanism)
        if response and not response.get('error'):
            tables = response.get('tables', [])
            if tables and tables[0].get('data'):
                new_token = tables[0]['data'][0].get('nextRequestCredential')
                if new_token and new_token != token and self.config_manager:
                    # Don't update if using environment variable or command line override
                    if not os.environ.get('REDIACC_TOKEN') and not self.config_manager.is_token_overridden():
                        # Check if the token we used is still current before updating
                        # This prevents overwriting a token that was already rotated by another process
                        current_token_before_update = TokenManager.get_token()
                        if current_token_before_update == token:
                            # Our token is still current, safe to update
                            TokenManager.set_token(new_token, 
                                                 email=self.config_manager.config.get('email'),
                                                 company=self.config_manager.config.get('company'),
                                                 vault_company=self.config_manager.config.get('vault_company'))
                        # else: Another process already rotated the token, skip our update
        
        return response
    
    def _ensure_vault_info(self):
        """Ensure vault info is fetched if needed"""
        if self.config_manager and self.config_manager.needs_vault_info_fetch():
            # Mark as fetched to avoid infinite recursion
            self.config_manager.mark_vault_info_fetched()
            
            # Fetch company vault info
            company_info = self.get_company_vault()
            if company_info:
                # Update config manager with vault info, but only if we have the required data
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
        """Get company vault information for the current authenticated session"""
        response = self.token_request("GetCompanyVault", {})
        
        if response.get('error'):
            return None
        
        # Extract company information from response
        tables = response.get('tables', [])
        for table in tables:
            data = table.get('data', [])
            if data and len(data) > 0:
                row = data[0]
                # Skip credentials table
                if 'nextRequestCredential' in row:
                    continue
                
                # Extract company info
                company_info = {
                    'companyName': row.get('companyName', ''),
                    'vaultCompany': row.get('vaultCompany') or row.get('VaultCompany', '')
                }
                
                if company_info['companyName']:
                    return company_info
        
        return None

# Output format handler
def format_output(data, format_type, message=None, error=None):
    """Format output based on the specified format type"""
    if format_type == 'json':
        output = {
            'success': error is None,
            'data': data
        }
        if message:
            output['message'] = message
        if error:
            output['error'] = error
        return json.dumps(output, indent=2)
    else:
        # Text format (default)
        if error:
            return colorize(f"Error: {error}", 'RED')
        elif data:
            return data
        elif message:
            return colorize(message, 'GREEN')
        else:
            return "No data available"

# Utility functions

# Static salt for password hashing - provides additional protection against dictionary attacks
# This salt is concatenated with the password before hashing to ensure even common passwords
# produce unique hashes. The salt value must be consistent across all components.
STATIC_SALT = 'Rd!@cc111$ecur3P@$$w0rd$@lt#H@$h'

def pwd_hash(pwd):
    """Generate a hexadecimal password hash for authentication and user operations"""
    # Concatenate password with static salt before hashing
    salted_password = pwd + STATIC_SALT
    return "0x" + hashlib.sha256(salted_password.encode()).digest().hex()

def extract_table_data(response, table_index=0):
    """Extract data from API response tables"""
    if not response or 'tables' not in response or len(response['tables']) <= table_index:
        return []
    return response['tables'][table_index].get('data', [])

def get_vault_data(args):
    """Get vault data from arguments"""
    if hasattr(args, 'vault_file') and args.vault_file:
        try:
            if args.vault_file == '-':
                return json.dumps(json.loads(sys.stdin.read()))
            with open(args.vault_file, 'r') as f:
                return json.dumps(json.load(f))
        except (IOError, json.JSONDecodeError) as e:
            print(colorize(f"Warning: Could not load vault data: {e}", 'YELLOW'))
            return '{}'
    return args.vault if hasattr(args, 'vault') and args.vault else '{}'

def get_vault_set_params(args, config_manager=None):
    """Generate params for vault set commands"""
    # Load vault data
    vault_data = None
    if args.file and args.file != '-':
        try:
            with open(args.file, 'r') as f:
                vault_data = f.read()
        except IOError:
            print(colorize(f"Error: Could not read file: {args.file}", 'RED'))
            return None
    else:
        # Read from stdin
        print("Enter JSON vault data (press Ctrl+D when finished):")
        vault_data = sys.stdin.read()
    
    # Validate JSON
    try:
        json.loads(vault_data)
    except json.JSONDecodeError as e:
        print(colorize(f"Error: Invalid JSON: {str(e)}", 'RED'))
        return None
    
    # Base params
    params = {'vaultVersion': args.vault_version or 1}
    
    # Resource-specific params
    if args.resource_type == 'team':
        params.update({'teamName': args.name, 'teamVault': vault_data})
    elif args.resource_type == 'machine':
        params.update({'teamName': args.team, 'machineName': args.name, 'machineVault': vault_data})
    elif args.resource_type == 'region':
        params.update({'regionName': args.name, 'regionVault': vault_data})
    elif args.resource_type == 'bridge':
        params.update({'regionName': args.region, 'bridgeName': args.name, 'bridgeVault': vault_data})
    elif args.resource_type == 'company':
        # Note: The server validates that users can only update their own company's vault
        # The company name parameter is ignored by the server
        if args.name and args.name.strip():
            print(colorize(f"Note: Company name '{args.name}' is ignored. You can only update your own company's vault.", 'YELLOW'))
        params['companyVault'] = vault_data
    elif args.resource_type == 'repository':
        params.update({'teamName': args.team, 'repoName': args.name, 'repoVault': vault_data})
    elif args.resource_type == 'storage':
        params.update({'teamName': args.team, 'storageName': args.name, 'storageVault': vault_data})
    elif args.resource_type == 'schedule':
        params.update({'teamName': args.team, 'scheduleName': args.name, 'scheduleVault': vault_data})
    
    return params

def camel_to_title(name):
    """Convert camelCase or PascalCase to Title Case"""
    # Handle special cases
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
    
    if name in special_cases:
        return special_cases[name]
    
    # Insert spaces before capital letters
    result = name[0].upper()
    for char in name[1:]:
        if char.isupper():
            result += ' ' + char
        else:
            result += char
    
    return result

def format_table(headers, rows):
    """Format data as a table for display"""
    if not rows:
        return "No items found"
    
    # Calculate column widths
    widths = [len(h) for h in headers]
    for row in rows:
        for i, cell in enumerate(row):
            widths[i] = max(widths[i], len(str(cell)))
    
    # Format the headers and rows
    header_line = '  '.join(h.ljust(w) for h, w in zip(headers, widths))
    separator = '-' * len(header_line)
    formatted_rows = [
        '  '.join(str(cell).ljust(w) for cell, w in zip(row, widths))
        for row in rows
    ]
    
    return '\n'.join([header_line, separator] + formatted_rows)

def table_to_dict(headers, rows):
    """Convert table data to a list of dictionaries for JSON output"""
    result = []
    for row in rows:
        item = {}
        for i, header in enumerate(headers):
            if i < len(row):
                item[header] = row[i]
        result.append(item)
    return result

def format_dynamic_tables(response, output_format='text', skip_fields=None):
    """Format all tables from response dynamically, skipping table index 0"""
    if not response or 'tables' not in response:
        return format_output("No data available", output_format)
    
    tables = response.get('tables', [])
    if len(tables) <= 1:
        return format_output("No records found", output_format)
    
    # Fields to skip in output
    if skip_fields is None:
        skip_fields = ['nextRequestCredential', 'newUserHash']
    
    
    if output_format == 'json':
        # For JSON output, convert all tables to lists of dictionaries
        result = []
        for table_idx in range(1, len(tables)):
            table = tables[table_idx]
            data = table.get('data', [])
            
            if not data:
                continue
                
            # Process each record, removing fields we want to skip
            processed_data = []
            for record in data:
                processed_record = {k: v for k, v in record.items() if k not in skip_fields}
                processed_data.append(processed_record)
            
            result.extend(processed_data)
        
        return format_output(result, output_format)
    else:
        # For text output, format as before
        output_parts = []
        
        # Process each table (skip index 0 which contains credentials)
        for table_idx in range(1, len(tables)):
            table = tables[table_idx]
            data = table.get('data', [])
            
            if not data:
                continue
            
            # Get all unique keys from all records
            all_keys = set()
            for record in data:
                all_keys.update(record.keys())
            
            # Remove fields we want to skip
            display_keys = [k for k in sorted(all_keys) if k not in skip_fields]
            
            if not display_keys:
                continue
            
            # Create headers and rows
            headers = [camel_to_title(key) for key in display_keys]
            rows = [[str(record.get(key, '')) for key in display_keys] for record in data]
            
            # Format this table
            if rows:
                table_output = format_table(headers, rows)
                output_parts.append(table_output)
        
        return format_output('\n\n'.join(output_parts) if output_parts else "No records found", output_format)

def build_queue_vault_data(function_name, args):
    """Build vault data for queue item based on function and arguments"""
    func_def = QUEUE_FUNCTIONS.get(function_name)
    if not func_def:
        return None
    
    # Build parameters from provided arguments
    params = {}
    for param_name, param_info in func_def.get('params', {}).items():
        # Get parameter value from args
        value = getattr(args, param_name, None)
        
        # Use default if available and value not provided
        if value is None and 'default' in param_info:
            value = param_info['default']
        
        # Skip if not required and not provided
        if value is None and not param_info.get('required', False):
            continue
        
        # Add to params if we have a value
        if value is not None:
            params[param_name] = value
    
    # Create vault data structure
    vault_data = {
        'type': 'bash_function',
        'function': function_name,
        'params': params,
        'description': args.description or func_def.get('description', ''),
        'priority': args.priority,
        'bridge': args.bridge
    }
    
    return json.dumps(vault_data)

# License Management Functions
def generate_hardware_id():
    """Generate hardware ID by calling the middleware API"""
    # Try multiple possible middleware URLs
    possible_urls = [
        "http://localhost:7322/api/health/hardware-id",  # Default local with nginx
        "http://localhost:5000/api/health/hardware-id",  # Direct middleware port
        "http://localhost:80/api/health/hardware-id",    # Alternative port
    ]
    
    last_error = None
    for hardware_id_url in possible_urls:
        try:
            req = urllib.request.Request(hardware_id_url)
            with urllib.request.urlopen(req, timeout=5) as response:
                data = json.loads(response.read().decode('utf-8'))
                return data['hardwareId']
        except urllib.error.URLError as e:
            last_error = e
            continue
        except Exception as e:
            last_error = e
            continue
    
    # If all URLs failed, provide helpful error message
    raise Exception(
        f"Failed to generate hardware ID. Please ensure the middleware is running.\n"
        f"Try: ./go system up middleware\n"
        f"Last error: {str(last_error)}"
    )

def request_license_from_server(hardware_id, base_url=None):
    """Request license from the license server"""
    if not base_url:
        base_url = BASE_URL
    
    # Remove /api/StoredProcedure suffix if present
    if base_url.endswith('/api/StoredProcedure'):
        base_url = base_url[:-len('/api/StoredProcedure')]
    elif base_url.endswith('/api'):
        base_url = base_url[:-4]
    
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
    """Install license file to the specified location"""
    if not os.path.exists(license_file):
        raise FileNotFoundError(f"License file not found: {license_file}")
    
    # If no target specified, try to detect middleware directory
    if not target_path:
        # Check common locations
        possible_paths = [
            ".",  # Current directory
            "./bin",  # Binary directory
            "../middleware",  # Sibling middleware directory
            "../middleware/bin/Debug/net8.0",
            "../middleware/bin/Release/net8.0",
        ]
        
        # Find a suitable location
        for path in possible_paths:
            if os.path.exists(path) and os.path.isdir(path):
                target_path = path
                break
        
        if not target_path:
            target_path = "."  # Default to current directory
    
    # Ensure target directory exists
    os.makedirs(target_path, exist_ok=True)
    
    # Copy license file
    target_file = os.path.join(target_path, "license.lic")
    import shutil
    shutil.copy2(license_file, target_file)
    
    return target_file

class CommandHandler:
    """Unified command handler"""
    def __init__(self, config_manager, output_format='text'):
        self.config = config_manager.config
        self.config_manager = config_manager
        self.client = APIClient(config_manager)
        self.output_format = output_format
    
    def handle_response(self, response, success_message=None, format_args=None):
        """Handle API response and print appropriate message"""
        if response.get('error'):
            output = format_output(None, self.output_format, None, response['error'])
            print(output)
            return False
        
        # Extract task ID if present for queue operations
        if success_message and format_args and '{task_id}' in success_message:
            tables = response.get('tables', [])
            if len(tables) > 1 and tables[1].get('data'):
                task_id = tables[1]['data'][0].get('taskId', tables[1]['data'][0].get('TaskId'))
                if task_id:
                    setattr(format_args, 'task_id', task_id)
        
        if success_message and self.output_format != 'json':
            if format_args:
                success_message = success_message.format(**{k: getattr(format_args, k, '') 
                                                           for k in dir(format_args) 
                                                           if not k.startswith('_')})
            print(colorize(success_message, 'GREEN'))
        elif success_message and self.output_format == 'json':
            if format_args:
                success_message = success_message.format(**{k: getattr(format_args, k, '') 
                                                           for k in dir(format_args) 
                                                           if not k.startswith('_')})
            # For create queue item, include task ID in response
            data = {}
            if hasattr(format_args, 'task_id') and format_args.task_id:
                data['task_id'] = format_args.task_id
            output = format_output(data, self.output_format, success_message)
            print(output)
            
        return True
    
    def login(self, args):
        """Log in to the Rediacc API"""
        email = args.email or input("Email: ")
        password = args.password or getpass.getpass("Password: ")
        
        hash_pwd = pwd_hash(password)
        
        # Prepare login parameters
        login_params = {
            'name': args.session_name or "CLI Session"
        }
        
        # Add optional parameters if provided
        if hasattr(args, 'tfa_code') and args.tfa_code:
            login_params['2FACode'] = args.tfa_code
        if hasattr(args, 'permissions') and args.permissions:
            login_params['requestedPermissions'] = args.permissions
        if hasattr(args, 'expiration') and args.expiration:
            login_params['tokenExpirationHours'] = args.expiration
        if hasattr(args, 'target') and args.target:
            login_params['target'] = args.target
        
        # Try to create authentication request
        response = self.client.auth_request(
            "CreateAuthenticationRequest", 
            email, hash_pwd, 
            login_params
        )
        
        if response.get('error'):
            output = format_output(None, self.output_format, None, f"Login failed: {response['error']}")
            print(output)
            return 1
        
        # Extract token and company info from response
        tables = response.get('tables', [])
        if not tables or not tables[0].get('data'):
            error_msg = "Login failed: Could not get authentication token"
            output = format_output(None, self.output_format, None, error_msg)
            print(output)
            return 1
        
        auth_data = tables[0]['data'][0]
        token = auth_data.get('nextRequestCredential')
        if not token:
            error_msg = "Login failed: Invalid authentication token"
            output = format_output(None, self.output_format, None, error_msg)
            print(output)
            return 1
        
        # Check if 2FA is required
        is_authorized = auth_data.get('isAuthorized', True)
        authentication_status = auth_data.get('authenticationStatus', '')
        
        if authentication_status == '2FA_REQUIRED' and not is_authorized:
            # 2FA is required
            if not hasattr(args, 'tfa_code') or not args.tfa_code:
                # No TFA code provided, prompt for it
                if self.output_format != 'json':
                    # Import i18n module for translation
                    from i18n import I18n
                    i18n = I18n()
                    tfa_code = input(i18n.get('enter_tfa_code'))
                else:
                    error_msg = "2FA_REQUIRED. Please provide --tfa-code parameter."
                    output = format_output(None, self.output_format, None, error_msg)
                    print(output)
                    return 1
                
                # Retry login with 2FA code
                login_params['2FACode'] = tfa_code
                response = self.client.auth_request(
                    "CreateAuthenticationRequest", 
                    email, hash_pwd, 
                    login_params
                )
                
                if response.get('error'):
                    output = format_output(None, self.output_format, None, f"2FA verification failed: {response['error']}")
                    print(output)
                    return 1
                
                # Extract updated token after 2FA
                tables = response.get('tables', [])
                if not tables or not tables[0].get('data'):
                    error_msg = "2FA verification failed: Could not get authentication token"
                    output = format_output(None, self.output_format, None, error_msg)
                    print(output)
                    return 1
                
                auth_data = tables[0]['data'][0]
                token = auth_data.get('nextRequestCredential')
                if not token:
                    error_msg = "2FA verification failed: Invalid authentication token"
                    output = format_output(None, self.output_format, None, error_msg)
                    print(output)
                    return 1
        
        # Extract company information and VaultCompany from the response
        company = auth_data.get('companyName')
        vault_company = auth_data.get('vaultCompany') or auth_data.get('VaultCompany')
        
        # Save authentication data first (without master password)
        self.config_manager.set_token_with_auth(token, email, company, vault_company)
        
        # Check if company has vault encryption enabled
        if vault_company and is_encrypted(vault_company):
            # Company requires master password
            master_password = getattr(args, 'master_password', None)
            if not master_password:
                print(colorize("Your company requires a master password for vault encryption.", 'YELLOW'))
                master_password = getpass.getpass("Master Password: ")
            
            # Validate master password
            if self.config_manager.validate_master_password(master_password):
                self.config_manager.set_master_password(master_password)
                if self.output_format != 'json':
                    print(colorize("Master password validated successfully", 'GREEN'))
            else:
                error_msg = "Invalid master password. Please check with your administrator for the correct company master password."
                output = format_output(None, self.output_format, None, error_msg)
                print(output)
                # Still logged in but without vault decryption capability
                if self.output_format != 'json':
                    print(colorize("Warning: Logged in but vault data will not be decrypted", 'YELLOW'))
        elif hasattr(args, 'master_password') and args.master_password:
            # User provided master password but company doesn't have encryption enabled
            if self.output_format != 'json':
                print(colorize("Note: Your company has not enabled vault encryption. The master password will not be used.", 'YELLOW'))
        
        # Generate output based on format
        if self.output_format == 'json':
            result = {
                'email': email,
                'company': company,
                'vault_encryption_enabled': bool(vault_company and is_encrypted(vault_company)),
                'master_password_set': bool(self.config_manager.get_master_password())
            }
            output = format_output(result, self.output_format, f"Successfully logged in as {email}")
            print(output)
        else:
            print(colorize(f"Successfully logged in as {email}", 'GREEN'))
            if company:
                print(f"Company: {company}")
            if vault_company and is_encrypted(vault_company):
                print(f"Vault Encryption: Enabled")
                if self.config_manager.get_master_password():
                    print(f"Master Password: Set")
                else:
                    print(f"Master Password: Not set (vault data will remain encrypted)")
        
        return 0
    
    def logout(self, args):
        """Log out from the Rediacc API"""
        # Delete the user request if we have a token
        if TokenManager.get_token():
            self.client.token_request("DeleteUserRequest")
        
        # Clear local auth data
        self.config_manager.clear_auth()
        
        output = format_output({}, self.output_format, "Successfully logged out")
        print(output)
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
                # Read hardware ID from file or argument
                if os.path.isfile(args.hardware_id):
                    with open(args.hardware_id, 'r') as f:
                        hardware_id = f.read().strip()
                else:
                    hardware_id = args.hardware_id
                
                # Request license from server
                print(colorize("Requesting license from server...", 'BLUE'))
                license_data = request_license_from_server(hardware_id, args.server_url)
                
                # Save license
                output_file = args.output or 'license.lic'
                with open(output_file, 'w') as f:
                    # Handle both uppercase and lowercase field names
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
                # Install license file
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
        """Add a bash function to the queue"""
        # Validate function exists
        func_def = QUEUE_FUNCTIONS.get(args.function)
        if not func_def:
            error = f"Unknown function: {args.function}"
            output = format_output(None, self.output_format, None, error)
            print(output)
            return 1
        
        # Collect parameters for the function
        for param_name, param_info in func_def.get('params', {}).items():
            if not hasattr(args, param_name):
                setattr(args, param_name, None)
            
            # Prompt for required parameters if not provided
            if param_info.get('required', False) and getattr(args, param_name) is None:
                if self.output_format == 'json':
                    error = f"Missing required parameter: {param_name}"
                    output = format_output(None, self.output_format, None, error)
                    print(output)
                    return 1
                else:
                    value = input(f"{param_info.get('help', param_name)}: ")
                    setattr(args, param_name, value)
        
        # Build vault data
        vault_data = build_queue_vault_data(args.function, args)
        if not vault_data:
            error = "Failed to build queue item data"
            output = format_output(None, self.output_format, None, error)
            print(output)
            return 1
        
        # Create the queue item
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
        
        # Extract task ID
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
    
    def queue_list_functions(self, args):
        """List available functions that can be queued"""
        if self.output_format == 'json':
            # JSON output with full function details
            result = {}
            for func_name, func_def in QUEUE_FUNCTIONS.items():
                result[func_name] = {
                    'description': func_def.get('description', ''),
                    'params': {}
                }
                for param_name, param_info in func_def.get('params', {}).items():
                    result[func_name]['params'][param_name] = {
                        'type': param_info.get('type', 'string'),
                        'required': param_info.get('required', False),
                        'default': param_info.get('default', None),
                        'help': param_info.get('help', '')
                    }
            output = format_output(result, self.output_format)
            print(output)
        else:
            # Text output with formatted table
            print(colorize("Available Queue Functions", 'HEADER'))
            print("=" * 80)
            
            for func_name, func_def in sorted(QUEUE_FUNCTIONS.items()):
                print(f"\n{colorize(func_name, 'BLUE')}")
                print(f"  {func_def.get('description', 'No description available')}")
                
                params = func_def.get('params', {})
                if params:
                    print("  Parameters:")
                    for param_name, param_info in params.items():
                        required = "[required]" if param_info.get('required', False) else "[optional]"
                        default = f" (default: {param_info.get('default')})" if 'default' in param_info else ""
                        help_text = param_info.get('help', '')
                        print(f"    - {param_name} {colorize(required, 'YELLOW')}{default}")
                        if help_text:
                            print(f"      {help_text}")
                else:
                    print("  No parameters required")
        
        return 0
    
    def generic_command(self, cmd_type, resource_type, args):
        """Handle generic commands using configuration"""
        # Special handling for queue commands
        if cmd_type == 'queue':
            if resource_type == 'add':
                return self.queue_add(args)
            elif resource_type == 'list-functions':
                return self.queue_list_functions(args)
        
        if cmd_type not in CMD_CONFIG or resource_type not in CMD_CONFIG[cmd_type]:
            error = f"Unsupported command: {cmd_type} {resource_type}"
            output = format_output(None, self.output_format, None, error)
            print(output)
            return 1
        
        cmd_config = CMD_CONFIG[cmd_type][resource_type]
        
        # Check if auth is required (default is True unless specified otherwise)
        auth_required = cmd_config.get('auth_required', True)
        
        # Handle special case for user create which needs a password prompt
        if cmd_type == 'create' and resource_type == 'user' and not hasattr(args, 'password'):
            args.password = getpass.getpass("Password for new user: ")
        
        # Handle special case for user update-password which needs a password prompt
        if cmd_type == 'user' and resource_type == 'update-password' and not args.new_password:
            args.new_password = getpass.getpass("New password: ")
        
        # Handle special case for user update-2fa which needs a password prompt
        if cmd_type == 'user' and resource_type == 'update-2fa' and not hasattr(args, 'password'):
            args.password = getpass.getpass("Current password: ")
        
        # For remove commands, confirm before proceeding (unless JSON output or force flag)
        confirm_msg = cmd_config.get('confirm_msg')
        if confirm_msg and not args.force and self.output_format != 'json':
            confirm_msg = confirm_msg.format(**{k: getattr(args, k, '') 
                                                             for k in dir(args) 
                                                             if not k.startswith('_')})
            confirm = input(f"{confirm_msg} [y/N] ")
            if confirm.lower() != 'y':
                print("Operation cancelled")
                return 0
        
        # Handle vault commands specially
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
        
        # Prepare parameters
        params = cmd_config['params'](args) if callable(cmd_config.get('params')) else {}
        
        # Execute API request
        if cmd_config.get('auth_type') == 'credentials' and hasattr(args, 'email'):
            # Use credential authentication (for company creation)
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
                # Update team name
                response = self.client.token_request(
                    "UpdateTeamName", 
                    {"currentTeamName": args.name, "newTeamName": args.new_name}
                )
                
                success_msg = f"Successfully renamed team: {args.name} → {args.new_name}"
                if not self.handle_response(response, success_msg):
                    success = False
                else:
                    result_data['team_name'] = args.new_name
            
            # Update vault if provided
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
            
            # Update vault if provided
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
            
            # Update vault if provided
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
            
            # Update vault if provided
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
            
            # Update vault if provided
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
            
            # Update vault if provided
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
            
            # Update vault if provided
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
            error = f"Unsupported resource type: {resource_type}"
            output = format_output(None, self.output_format, None, error)
            print(output)
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
                
                output = format_output(result, self.output_format, success_msg)
                print(output)
            return 0
        return 1
    
    def vault_set_password(self, args):
        """Set master password for vault encryption"""
        if not CRYPTO_AVAILABLE:
            error = "Cryptography library not available. Install with: pip install cryptography"
            output = format_output(None, self.output_format, None, error)
            print(output)
            return 1
        
        # Ensure vault info is current
        self.client._ensure_vault_info()
        
        # Check if company has vault encryption enabled
        if not self.config_manager.has_vault_encryption():
            error = "Your company has not enabled vault encryption. Contact your administrator to enable it."
            output = format_output(None, self.output_format, None, error)
            print(output)
            return 1
        
        # Prompt for master password
        master_password = getpass.getpass("Enter master password: ")
        confirm_password = getpass.getpass("Confirm master password: ")
        
        if master_password != confirm_password:
            error = "Passwords do not match"
            output = format_output(None, self.output_format, None, error)
            print(output)
            return 1
        
        # Validate master password
        if self.config_manager.validate_master_password(master_password):
            self.config_manager.set_master_password(master_password)
            success_msg = "Master password set successfully"
            if self.output_format == 'json':
                output = format_output({'success': True}, self.output_format, success_msg)
            else:
                output = colorize(success_msg, 'GREEN')
            print(output)
            return 0
        else:
            error = "Invalid master password. Please check with your administrator for the correct company master password."
            output = format_output(None, self.output_format, None, error)
            print(output)
            return 1
    
    def vault_clear_password(self, args):
        """Clear master password from memory"""
        self.config_manager.clear_master_password()
        success_msg = "Master password cleared from memory"
        if self.output_format == 'json':
            output = format_output({'success': True}, self.output_format, success_msg)
        else:
            output = colorize(success_msg, 'GREEN')
        print(output)
        return 0
    
    def vault_status(self, args):
        """Show vault encryption status"""
        # Ensure vault info is current
        self.client._ensure_vault_info()
        
        # Get vault company value
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
            output = format_output(status_data, self.output_format)
            print(output)
        else:
            print(colorize("VAULT ENCRYPTION STATUS", 'HEADER'))
            print("=" * 40)
            print(f"Cryptography Library: {'Available' if status_data['crypto_available'] else 'Not Available'}")
            print(f"Company: {status_data['company'] or 'Not set'}")
            print(f"Vault Company Data: {'Present' if status_data['vault_company_present'] else 'Not fetched'}")
            print(f"Vault Encryption: {'Required' if status_data['vault_encryption_enabled'] else 'Not Required'}")
            print(f"Master Password: {'Set' if status_data['master_password_set'] else 'Not Set'}")
            
            if not status_data['crypto_available']:
                print("")
                print(colorize("To enable vault encryption, install the cryptography library:", 'YELLOW'))
                print("  pip install cryptography")
            elif status_data['vault_encryption_enabled'] and not status_data['master_password_set']:
                print("")
                print(colorize("Your company requires a master password for vault encryption.", 'YELLOW'))
                print("Use 'rediacc vault set-password' to set it.")
            elif not status_data['vault_company_present']:
                print("")
                print(colorize("Note: Vault company information will be fetched on next command.", 'BLUE'))
        
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
            # For text output, format each section separately
            output_parts = []
            
            # Queue Item Details
            if len(tables) > 1 and tables[1].get('data') and tables[1]['data']:
                item_data = tables[1]['data'][0]
                output_parts.append(colorize("QUEUE ITEM DETAILS", 'HEADER'))
                output_parts.append("=" * 80)
                
                # Core details
                details = [
                    ('Task ID', item_data.get('TaskId')),
                    ('Status', item_data.get('Status')),
                    ('Health Status', item_data.get('HealthStatus')),
                    ('Created Time', item_data.get('CreatedTime')),
                    ('Assigned Time', item_data.get('AssignedTime')),
                    ('Last Heartbeat', item_data.get('LastHeartbeat')),
                ]
                
                # Add priority if available
                if item_data.get('Priority') is not None:
                    details.extend([
                        ('Priority', f"{item_data.get('Priority')} ({item_data.get('PriorityLabel')})"),
                    ])
                
                # Time calculations
                details.extend([
                    ('Seconds to Assignment', item_data.get('SecondsToAssignment')),
                    ('Processing Duration (seconds)', item_data.get('ProcessingDurationSeconds')),
                    ('Total Duration (seconds)', item_data.get('TotalDurationSeconds')),
                ])
                
                # Resource hierarchy
                details.extend([
                    ('Company', f"{item_data.get('CompanyName')} (ID: {item_data.get('CompanyId')})"),
                    ('Team', f"{item_data.get('TeamName')} (ID: {item_data.get('TeamId')})"),
                    ('Region', f"{item_data.get('RegionName')} (ID: {item_data.get('RegionId')})"),
                    ('Bridge', f"{item_data.get('BridgeName')} (ID: {item_data.get('BridgeId')})"),
                    ('Machine', f"{item_data.get('MachineName')} (ID: {item_data.get('MachineId')})"),
                ])
                
                # Flags
                if item_data.get('IsStale'):
                    details.append(('Warning', colorize('This queue item is STALE', 'YELLOW')))
                
                # Format details
                max_label_width = max(len(label) for label, _ in details)
                for label, value in details:
                    if value is not None:
                        output_parts.append(f"{label.ljust(max_label_width)} : {value}")
                
            # Request Vault
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
            
            # Response Vault
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
            
            # Timeline
            if len(tables) > 4 and tables[4].get('data') and tables[4]['data']:
                output_parts.append("")
                output_parts.append(colorize("PROCESSING TIMELINE", 'HEADER'))
                output_parts.append("=" * 80)
                
                timeline_data = tables[4]['data']
                if timeline_data:
                    # Format timeline as a table
                    headers = ['Time', 'Status', 'Description']
                    rows = []
                    for event in timeline_data:
                        time = event.get('Timestamp', 'N/A')
                        status = event.get('NewValue', event.get('Status', 'N/A'))
                        desc = event.get('ChangeDetails', event.get('Action', 'Status change'))
                        rows.append([time, status, desc])
                    
                    if rows:
                        output_parts.append(format_table(headers, rows))
                else:
                    output_parts.append("No timeline events recorded")
            
            return '\n'.join(output_parts)

def setup_parser():
    """Create and configure the argument parser from definitions"""
    parser = argparse.ArgumentParser(
        description='Rediacc CLI - Complete interface for Rediacc Middleware API with enhanced queue support'
    )
    # Add global output format option
    parser.add_argument('--output', '-o', choices=['text', 'json'], default='text',
                       help='Output format (text or json)')
    # Add global token option to override config
    parser.add_argument('--token', '-t', help='Authentication token (overrides saved token)')
    # Add verbose logging option
    parser.add_argument('--verbose', '-v', action='store_true',
                       help='Enable verbose logging output')
    # Add GUI option
    parser.add_argument('--gui', nargs='?', const='native', choices=['native', 'docker', 'docker-build'],
                       help='Launch graphical user interface (native/docker/docker-build)')
    
    subparsers = parser.add_subparsers(dest='command', help='Command')
    
    # Add command parsers
    for cmd_name, cmd_def in ARG_DEFS.items():
        if isinstance(cmd_def, list):  # Simple command without subcommands
            cmd_parser = subparsers.add_parser(cmd_name, help=f"{cmd_name} command")
            for arg in cmd_def:
                kwargs = {k: v for k, v in arg.items() if k != 'name'}
                cmd_parser.add_argument(arg['name'], **kwargs)
        else:  # Command with subcommands
            cmd_parser = subparsers.add_parser(cmd_name, help=f"{cmd_name} command")
            subcmd_parsers = cmd_parser.add_subparsers(dest='resource', help='Resource')
            
            for subcmd_name, subcmd_def in cmd_def.items():
                subcmd_parser = subcmd_parsers.add_parser(subcmd_name, help=f"{subcmd_name} resource")
                
                # Special handling for queue add command - add function-specific arguments
                if cmd_name == 'queue' and subcmd_name == 'add':
                    # Add the basic arguments
                    for arg in subcmd_def:
                        kwargs = {k: v for k, v in arg.items() if k != 'name'}
                        subcmd_parser.add_argument(arg['name'], **kwargs)
                    
                    # Add all possible function parameters as optional arguments
                    # Use a dict to ensure unique parameter names
                    all_params = {}
                    for func_def in QUEUE_FUNCTIONS.values():
                        for param_name, param_info in func_def.get('params', {}).items():
                            # Only add if not already present or update with more descriptive help
                            if param_name not in all_params or len(param_info.get('help', '')) > len(all_params[param_name]):
                                all_params[param_name] = param_info.get('help', f'Parameter for function')
                    
                    # Add each unique parameter
                    for param_name, help_text in sorted(all_params.items()):
                        # Skip parameters that might conflict with Python keywords or argparse
                        if param_name.replace('-', '_').replace('_', '').isidentifier():
                            subcmd_parser.add_argument(f'--{param_name.replace("_", "-")}', 
                                                     dest=param_name,
                                                     help=help_text)
                else:
                    # Normal argument handling
                    for arg in subcmd_def:
                        kwargs = {k: v for k, v in arg.items() if k != 'name'}
                        subcmd_parser.add_argument(arg['name'], **kwargs)
                    
                    # Special handling for update commands - add vault arguments
                    if cmd_name == 'update' and subcmd_name in ['team', 'region', 'bridge', 'machine', 'repository', 'storage', 'schedule']:
                        subcmd_parser.add_argument('--vault', help='JSON vault data')
                        subcmd_parser.add_argument('--vault-file', help='File containing JSON vault data')
                        subcmd_parser.add_argument('--vault-version', type=int, help='Vault version')
                        
                        # Add new_bridge for machine updates
                        if subcmd_name == 'machine':
                            subcmd_parser.add_argument('--new-bridge', help='New bridge name for machine')
    
    # Add license command
    license_parser = subparsers.add_parser('license', help='License management commands')
    license_subparsers = license_parser.add_subparsers(dest='license_command', help='License commands')
    
    # generate-id command
    generate_id_parser = license_subparsers.add_parser('generate-id', help='Generate hardware ID for offline licensing')
    generate_id_parser.add_argument('--output', '-o', help='Output file (default: hardware-id.txt)')
    
    # request command
    request_parser = license_subparsers.add_parser('request', help='Request license using hardware ID')
    request_parser.add_argument('--hardware-id', '-i', required=True, help='Hardware ID or file containing it')
    request_parser.add_argument('--output', '-o', help='Output file (default: license.lic)')
    request_parser.add_argument('--server-url', '-s', help='License server URL (optional)')
    
    # install command
    install_parser = license_subparsers.add_parser('install', help='Install license file')
    install_parser.add_argument('--file', '-f', required=True, help='License file to install')
    install_parser.add_argument('--target', '-t', help='Target directory (default: auto-detect)')
    
    return parser

def main():
    """Main CLI entry point"""
    parser = setup_parser()
    args = parser.parse_args()
    
    # Setup logging based on verbose flag
    setup_logging(verbose=args.verbose)
    logger = get_logger(__name__)
    
    # Log startup information in verbose mode
    if args.verbose:
        logger.debug("Rediacc CLI starting up")
        logger.debug(f"Command: {args.command}")
        logger.debug(f"Arguments: {vars(args)}")
    
    # Check if GUI mode is requested
    if args.gui:
        gui_mode = args.gui  # Will be 'native', 'docker', or 'docker-build'
        
        if gui_mode == 'docker-build':
            # Build Docker image for GUI
            try:
                import subprocess
                cli_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                cmd = [os.path.join(cli_root, '..', 'rediacc'), 'desktop-docker-build']
                result = subprocess.run(cmd, cwd=cli_root)
                return result.returncode
            except Exception as e:
                print(colorize(f"Error building Docker GUI image: {str(e)}", 'RED'))
                return 1
                
        elif gui_mode == 'docker':
            # Run GUI in Docker
            try:
                import subprocess
                cli_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                cmd = [os.path.join(cli_root, '..', 'rediacc'), 'desktop-docker']
                result = subprocess.run(cmd, cwd=cli_root)
                return result.returncode
            except Exception as e:
                print(colorize(f"Error running GUI in Docker: {str(e)}", 'RED'))
                return 1
                
        else:  # native mode (default)
            # Import and launch GUI natively
            try:
                # Import from current directory (already in sys.path)
                import rediacc_cli_gui
                rediacc_cli_gui.launch_gui()
                return 0
            except ImportError as e:
                print(colorize("Error: Failed to launch GUI. Make sure tkinter is installed.", 'RED'))
                print(colorize(f"Details: {str(e)}", 'RED'))
                # Additional help for module import errors
                if "No module named 'modules'" in str(e):
                    print(colorize("The modules directory was not found. Check your installation.", 'YELLOW'))
                    modules_path = os.path.dirname(os.path.abspath(__file__))
                    print(colorize(f"Expected modules path: {modules_path}", 'YELLOW'))
                    print(colorize(f"Path exists: {os.path.exists(modules_path)}", 'YELLOW'))
                return 1
            except Exception as e:
                print(colorize(f"Error launching GUI: {str(e)}", 'RED'))
                return 1
    
    if not args.command:
        parser.print_help()
        return 1
    
    # Get output format
    output_format = args.output
    
    # Load configuration - use TokenManager instead of ConfigManager
    config_manager = TokenManager()
    # Load vault info from config for compatibility
    config_manager.load_vault_info_from_config()
    
    # Handle --token override
    if args.token:
        # Validate the override token
        if not TokenManager.validate_token(args.token):
            error = f"Invalid token format: {TokenManager.mask_token(args.token)}"
            output = format_output(None, output_format, None, error)
            print(output)
            return 1
        # Set override token in environment variable so TokenManager will use it
        os.environ['REDIACC_TOKEN'] = args.token
        config_manager.set_token_overridden(True)
    
    handler = CommandHandler(config_manager, output_format)
    
    # Handle authentication commands directly
    if args.command == 'login':
        return handler.login(args)
    elif args.command == 'logout':
        return handler.logout(args)
    elif args.command == 'license':
        # License commands don't require authentication
        return handler.handle_license_command(args)
    
    # Check if command requires authentication
    auth_not_required_commands = {
        ('user', 'activate'),
        ('create', 'company'),
        ('queue', 'list-functions')
    }
    
    # Check if it's a standalone command (like 'bridge')
    standalone_commands = ['bridge']
    
    # Check if authenticated for commands that require it
    if (args.command, getattr(args, 'resource', None)) not in auth_not_required_commands:
        if not config_manager.is_authenticated():
            error = "Not authenticated. Please login first."
            output = format_output(None, output_format, None, error)
            print(output)
            return 1
    
    # Handle other commands with resource types
    if not hasattr(args, 'resource') or not args.resource:
        error = f"No resource specified for command: {args.command}"
        output = format_output(None, output_format, None, error)
        print(output)
        return 1
    
    # Special handling for certain commands
    if args.command == 'update':
        return handler.update_resource(args.resource, args)
    elif args.command in standalone_commands:
        # Handle standalone commands (like bridge)
        return handler.generic_command(args.command, args.resource, args)
    else:
        # Generic command handling for create, list, rm, vault, permission, user, team-member, queue
        return handler.generic_command(args.command, args.resource, args)

if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\nOperation cancelled by user")
        sys.exit(130)