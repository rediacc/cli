#!/usr/bin/env python3
"""
Rediacc CLI - Docker-like command-line interface for Rediacc Middleware API
"""
import argparse
import base64
import getpass
import hashlib
import json
import os
import sys
import urllib.request
import urllib.parse
import urllib.error
from typing import Dict, Any, Optional, List, Union

# Configuration
BASE_URL = os.environ.get('REDIACC_API_URL', 'http://localhost:8080')
API_PREFIX = '/api/StoredProcedure'
CONFIG_DIR = os.path.expanduser('~/.rediacc')
CONFIG_FILE = os.path.join(CONFIG_DIR, 'config.json')
REQUEST_TIMEOUT = 30

# Color codes for terminal output
COLORS = {
    'HEADER': '\033[95m', 'BLUE': '\033[94m', 'GREEN': '\033[92m',
    'YELLOW': '\033[93m', 'RED': '\033[91m', 'ENDC': '\033[0m', 'BOLD': '\033[1m',
}

def colorize(text, color):
    """Add color to terminal output if supported"""
    return f"{COLORS.get(color, '')}{text}{COLORS['ENDC']}" if sys.stdout.isatty() else text

# Command and API endpoint configuration
CMD_CONFIG = {
    # Authentication commands
    'login': {
        'auth_required': False,
        'endpoint': 'CreateAuthenticationRequest',
        'auth_type': 'credentials',
        'success_msg': 'Successfully logged in as {email}'
    },
    'logout': {
        'auth_required': True,
        'endpoint': 'DeleteUserRequest',
        'auth_type': 'token',
        'success_msg': 'Successfully logged out'
    },
    
    # Create commands
    'create': {
        'company': {
            'endpoint': 'CreateNewCompany',
            'auth_type': 'credentials',
            'params': lambda args: {
                'companyName': args.name,
                'subscriptionPlan': args.plan or 'ELITE'
            },
            'success_msg': 'Successfully created company: {name}'
        },
        'team': {
            'endpoint': 'CreateTeam',
            'params': lambda args: {
                'teamName': args.name,
                'teamVault': get_vault_data(args) or '{}'
            },
            'success_msg': 'Successfully created team: {name}'
        },
        'region': {
            'endpoint': 'CreateRegion',
            'params': lambda args: {
                'regionName': args.name,
                'regionVault': get_vault_data(args) or '{}'
            },
            'success_msg': 'Successfully created region: {name}'
        },
        'bridge': {
            'endpoint': 'CreateBridge',
            'params': lambda args: {
                'regionName': args.region,
                'bridgeName': args.name,
                'bridgeVault': get_vault_data(args) or '{}'
            },
            'success_msg': 'Successfully created bridge: {name} in region {region}'
        },
        'machine': {
            'endpoint': 'CreateMachine',
            'params': lambda args: {
                'teamName': args.team,
                'bridgeName': args.bridge,
                'machineName': args.name,
                'machineVault': get_vault_data(args) or '{}'
            },
            'success_msg': 'Successfully created machine: {name} for team {team}'
        },
        'repository': {
            'endpoint': 'CreateRepository',
            'params': lambda args: {
                'teamName': args.team,
                'repoName': args.name,
                'repoVault': get_vault_data(args) or '{}'
            },
            'success_msg': 'Successfully created repository: {name} for team {team}'
        },
        'storage': {
            'endpoint': 'CreateStorage',
            'params': lambda args: {
                'teamName': args.team,
                'storageName': args.name,
                'storageVault': get_vault_data(args) or '{}'
            },
            'success_msg': 'Successfully created storage: {name} for team {team}'
        },
        'schedule': {
            'endpoint': 'CreateSchedule',
            'params': lambda args: {
                'teamName': args.team,
                'scheduleName': args.name,
                'scheduleVault': get_vault_data(args) or '{}'
            },
            'success_msg': 'Successfully created schedule: {name} for team {team}'
        }
    },
    
    # List commands
    'list': {
        'teams': {
            'endpoint': 'GetCompanyTeams',
            'params': lambda args: {}
        },
        'regions': {
            'endpoint': 'GetCompanyRegions',
            'params': lambda args: {}
        },
        'bridges': {
            'endpoint': 'GetRegionBridges',
            'params': lambda args: {'regionName': args.region}
        },
        'machines': {
            'endpoint': 'GetTeamMachines',
            'params': lambda args: {'teamName': args.team}
        },
        'repositories': {
            'endpoint': 'GetTeamRepositories',
            'params': lambda args: {'teamName': args.team}
        }
    },
    
    # Remove commands
    'rm': {
        'team': {
            'endpoint': 'DeleteTeam',
            'params': lambda args: {'teamName': args.name},
            'confirm_msg': "Are you sure you want to delete team '{name}'? This will remove all resources in the team.",
            'success_msg': 'Successfully deleted team: {name}'
        },
        'machine': {
            'endpoint': 'DeleteMachine',
            'params': lambda args: {'teamName': args.team, 'machineName': args.name},
            'confirm_msg': "Are you sure you want to delete machine '{name}' from team '{team}'?",
            'success_msg': 'Successfully deleted machine: {name}'
        },
        'bridge': {
            'endpoint': 'DeleteBridge',
            'params': lambda args: {'regionName': args.region, 'bridgeName': args.name},
            'confirm_msg': "Are you sure you want to delete bridge '{name}' from region '{region}'?",
            'success_msg': 'Successfully deleted bridge: {name}'
        },
        'region': {
            'endpoint': 'DeleteRegion',
            'params': lambda args: {'regionName': args.name},
            'confirm_msg': "Are you sure you want to delete region '{name}'? This will remove all bridges in the region.",
            'success_msg': 'Successfully deleted region: {name}'
        },
        'repository': {
            'endpoint': 'DeleteRepository',
            'params': lambda args: {'teamName': args.team, 'repoName': args.name},
            'confirm_msg': "Are you sure you want to delete repository '{name}' from team '{team}'?",
            'success_msg': 'Successfully deleted repository: {name}'
        },
        'storage': {
            'endpoint': 'DeleteStorage',
            'params': lambda args: {'teamName': args.team, 'storageName': args.name},
            'confirm_msg': "Are you sure you want to delete storage '{name}' from team '{team}'?",
            'success_msg': 'Successfully deleted storage: {name}'
        },
        'schedule': {
            'endpoint': 'DeleteSchedule',
            'params': lambda args: {'teamName': args.team, 'scheduleName': args.name},
            'confirm_msg': "Are you sure you want to delete schedule '{name}' from team '{team}'?",
            'success_msg': 'Successfully deleted schedule: {name}'
        }
    },
    
    # Vault commands
    'vault': {
        'get': {
            'endpoints': {
                'team': 'GetTeamVault',
                'machine': 'GetMachineVault',
                'region': 'GetRegionVault',
                'bridge': 'GetBridgeVault',
                'company': 'GetCompanyVault'
            },
            'params': lambda args: get_vault_get_params(args)
        },
        'set': {
            'endpoints': {
                'team': 'UpdateTeamVault',
                'machine': 'UpdateMachineVault',
                'region': 'UpdateRegionVault',
                'bridge': 'UpdateBridgeVault',
                'company': 'UpdateCompanyVault'
            },
            'params': lambda args: get_vault_set_params(args),
            'success_msg': 'Successfully updated {resource_type} vault'
        }
    }
}

# Command-line argument definitions
ARG_DEFS = {
    'login': [
        {'name': '--email', 'help': 'User email address'},
        {'name': '--password', 'help': 'User password'},
        {'name': '--session-name', 'help': 'Name for this session'}
    ],
    'logout': [],
    
    'create': {
        'company': [
            {'name': 'name', 'help': 'Company name'},
            {'name': '--email', 'help': 'Admin email address'},
            {'name': '--password', 'help': 'Admin password'},
            {'name': '--plan', 'help': 'Subscription plan', 'choices': ['FREE', 'BASIC', 'PRO', 'ELITE']}
        ],
        'team': [
            {'name': 'name', 'help': 'Team name'},
            {'name': '--vault', 'help': 'JSON vault data'},
            {'name': '--vault-file', 'help': 'File containing JSON vault data'}
        ],
        'region': [
            {'name': 'name', 'help': 'Region name'},
            {'name': '--vault', 'help': 'JSON vault data'},
            {'name': '--vault-file', 'help': 'File containing JSON vault data'}
        ],
        'bridge': [
            {'name': 'region', 'help': 'Region name'},
            {'name': 'name', 'help': 'Bridge name'},
            {'name': '--vault', 'help': 'JSON vault data'},
            {'name': '--vault-file', 'help': 'File containing JSON vault data'}
        ],
        'machine': [
            {'name': 'team', 'help': 'Team name'},
            {'name': 'bridge', 'help': 'Bridge name'},
            {'name': 'name', 'help': 'Machine name'},
            {'name': '--vault', 'help': 'JSON vault data'},
            {'name': '--vault-file', 'help': 'File containing JSON vault data'}
        ],
        'repository': [
            {'name': 'team', 'help': 'Team name'},
            {'name': 'name', 'help': 'Repository name'},
            {'name': '--vault', 'help': 'JSON vault data'},
            {'name': '--vault-file', 'help': 'File containing JSON vault data'}
        ],
        'storage': [
            {'name': 'team', 'help': 'Team name'},
            {'name': 'name', 'help': 'Storage name'},
            {'name': '--vault', 'help': 'JSON vault data'},
            {'name': '--vault-file', 'help': 'File containing JSON vault data'}
        ],
        'schedule': [
            {'name': 'team', 'help': 'Team name'},
            {'name': 'name', 'help': 'Schedule name'},
            {'name': '--vault', 'help': 'JSON vault data'},
            {'name': '--vault-file', 'help': 'File containing JSON vault data'}
        ]
    },
    
    'list': {
        'teams': [],
        'regions': [],
        'bridges': [{'name': 'region', 'help': 'Region name'}],
        'machines': [{'name': 'team', 'help': 'Team name'}],
        'repositories': [{'name': 'team', 'help': 'Team name'}]
    },
    
    'inspect': {
        'team': [{'name': 'name', 'help': 'Team name'}],
        'machine': [
            {'name': 'team', 'help': 'Team name'},
            {'name': 'name', 'help': 'Machine name'}
        ]
    },
    
    'update': {
        'team': [
            {'name': 'name', 'help': 'Team name'},
            {'name': '--new-name', 'help': 'New team name'},
            {'name': '--vault', 'help': 'JSON vault data'},
            {'name': '--vault-file', 'help': 'File containing JSON vault data'},
            {'name': '--vault-version', 'type': int, 'help': 'Vault version'}
        ],
        'machine': [
            {'name': 'team', 'help': 'Team name'},
            {'name': 'name', 'help': 'Machine name'},
            {'name': '--new-name', 'help': 'New machine name'},
            {'name': '--new-bridge', 'help': 'New bridge name'},
            {'name': '--vault', 'help': 'JSON vault data'},
            {'name': '--vault-file', 'help': 'File containing JSON vault data'},
            {'name': '--vault-version', 'type': int, 'help': 'Vault version'}
        ]
    },
    
    'rm': {
        'team': [
            {'name': 'name', 'help': 'Team name'},
            {'name': '--force', 'action': 'store_true', 'help': 'Skip confirmation'}
        ],
        'machine': [
            {'name': 'team', 'help': 'Team name'},
            {'name': 'name', 'help': 'Machine name'},
            {'name': '--force', 'action': 'store_true', 'help': 'Skip confirmation'}
        ],
        'bridge': [
            {'name': 'region', 'help': 'Region name'},
            {'name': 'name', 'help': 'Bridge name'},
            {'name': '--force', 'action': 'store_true', 'help': 'Skip confirmation'}
        ],
        'region': [
            {'name': 'name', 'help': 'Region name'},
            {'name': '--force', 'action': 'store_true', 'help': 'Skip confirmation'}
        ],
        'repository': [
            {'name': 'team', 'help': 'Team name'},
            {'name': 'name', 'help': 'Repository name'},
            {'name': '--force', 'action': 'store_true', 'help': 'Skip confirmation'}
        ],
        'storage': [
            {'name': 'team', 'help': 'Team name'},
            {'name': 'name', 'help': 'Storage name'},
            {'name': '--force', 'action': 'store_true', 'help': 'Skip confirmation'}
        ],
        'schedule': [
            {'name': 'team', 'help': 'Team name'},
            {'name': 'name', 'help': 'Schedule name'},
            {'name': '--force', 'action': 'store_true', 'help': 'Skip confirmation'}
        ]
    },
    
    'vault': {
        'get': [
            {'name': 'resource_type', 'help': 'Resource type',
             'choices': ['team', 'machine', 'region', 'bridge', 'company']},
            {'name': 'name', 'help': 'Resource name'},
            {'name': '--team', 'help': 'Team name (for machine)'},
            {'name': '--region', 'help': 'Region name (for bridge)'}
        ],
        'set': [
            {'name': 'resource_type', 'help': 'Resource type',
             'choices': ['team', 'machine', 'region', 'bridge', 'company']},
            {'name': 'name', 'help': 'Resource name'},
            {'name': 'file', 'nargs': '?', 'help': 'File containing JSON vault data (or - for stdin)'},
            {'name': '--team', 'help': 'Team name (for machine)'},
            {'name': '--region', 'help': 'Region name (for bridge)'},
            {'name': '--vault-version', 'type': int, 'help': 'Vault version'}
        ]
    }
}

class ConfigManager:
    """Manages configuration and authentication state"""
    def __init__(self):
        self.config = self._load_config()
    
    def _load_config(self):
        """Load configuration from file"""
        if not os.path.exists(CONFIG_FILE):
            return {}
        try:
            with open(CONFIG_FILE, 'r') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return {}
    
    def save_config(self):
        """Save current configuration to file"""
        os.makedirs(CONFIG_DIR, exist_ok=True)
        with open(CONFIG_FILE, 'w') as f:
            json.dump(self.config, f, indent=2)
    
    def set_auth(self, email, token, company=None):
        """Update authentication information"""
        self.config.update({'email': email, 'token': token, 'company': company})
        self.save_config()
    
    def clear_auth(self):
        """Clear authentication information"""
        for key in ['email', 'token', 'company']:
            self.config.pop(key, None)
        self.save_config()
    
    def is_authenticated(self):
        """Check if user is authenticated"""
        return bool(self.config.get('token'))

class APIClient:
    """Client for interacting with the Rediacc Middleware API"""
    def __init__(self, config=None, config_manager=None):
        self.config = config or {}
        self.config_manager = config_manager
        self.base_headers = {"Content-Type": "application/json"}
    
    def request(self, endpoint, data=None, headers=None):
        """Make an API request to the middleware service"""
        url = f"{BASE_URL}{API_PREFIX}/{endpoint}"
        
        # Merge headers
        merged_headers = self.base_headers.copy()
        if headers:
            merged_headers.update(headers)
        
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
    
    def token_request(self, endpoint, data=None):
        """Make a request authenticated with a token"""
        if not self.config.get('token'):
            return {"error": "Not authenticated. Please login first.", "status_code": 401}
        
        response = self.request(endpoint, data, {
            "Rediacc-RequestToken": self.config['token']
        })
        
        # Update token if a new one is provided (token chain mechanism)
        if response and not response.get('error'):
            tables = response.get('tables', [])
            if tables and tables[0].get('data'):
                new_token = tables[0]['data'][0].get('nextRequestCredential')
                if new_token and self.config_manager:
                    self.config['token'] = new_token
                    self.config_manager.config['token'] = new_token
                    self.config_manager.save_config()
        
        return response

# Utility functions
def pwd_hash(pwd):
    """Generate a base64 password hash for authentication"""
    return base64.b64encode(hashlib.sha256(pwd.encode()).digest()).decode()

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

def get_vault_get_params(args):
    """Generate params for vault get commands"""
    params = {}
    if args.resource_type == 'team':
        params['teamName'] = args.name
    elif args.resource_type == 'machine':
        params.update({'teamName': args.team, 'machineName': args.name})
    elif args.resource_type == 'region':
        params['regionName'] = args.name
    elif args.resource_type == 'bridge':
        params.update({'regionName': args.region, 'bridgeName': args.name})
    return params

def get_vault_set_params(args):
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
        params['companyVault'] = vault_data
    
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
        'activated': 'Active'
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

def format_dynamic_tables(response, skip_fields=None):
    """Format all tables from response dynamically, skipping table index 0"""
    if not response or 'tables' not in response:
        return "No data available"
    
    tables = response.get('tables', [])
    if len(tables) <= 1:
        return "No records found"
    
    # Fields to skip in output
    if skip_fields is None:
        skip_fields = ['vaultContent', 'nextRequestCredential', 'vaultVersion']
    
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
    
    return '\n\n'.join(output_parts) if output_parts else "No records found"

class CommandHandler:
    """Unified command handler"""
    def __init__(self, config_manager):
        self.config = config_manager.config
        self.config_manager = config_manager
        self.client = APIClient(self.config, config_manager)
    
    def handle_response(self, response, success_message=None, format_args=None):
        """Handle API response and print appropriate message"""
        if response.get('error'):
            print(colorize(f"Error: {response['error']}", 'RED'))
            return False
        
        if success_message:
            if format_args:
                success_message = success_message.format(**{k: getattr(format_args, k, '') 
                                                           for k in dir(format_args) 
                                                           if not k.startswith('_')})
            print(colorize(success_message, 'GREEN'))
        
        return True
    
    def login(self, args):
        """Log in to the Rediacc API"""
        email = args.email or input("Email: ")
        password = args.password or getpass.getpass("Password: ")
        
        hash_pwd = pwd_hash(password)
        
        # Try to create authentication request
        response = self.client.auth_request(
            "CreateAuthenticationRequest", 
            email, hash_pwd, 
            {"name": args.session_name or "CLI Session"}
        )
        
        if response.get('error'):
            print(colorize(f"Login failed: {response['error']}", 'RED'))
            return 1
        
        # Extract token from response
        tables = response.get('tables', [])
        if not tables or not tables[0].get('data'):
            print(colorize("Login failed: Could not get authentication token", 'RED'))
            return 1
        
        token = tables[0]['data'][0].get('nextRequestCredential')
        if not token:
            print(colorize("Login failed: Invalid authentication token", 'RED'))
            return 1
        
        # Get company info
        company_response = self.client.request(
            "GetUserCompany", {}, 
            {"Rediacc-UserEmail": email, "Rediacc-UserHash": hash_pwd}
        )
        
        company = None
        if not company_response.get('error'):
            company_data = extract_table_data(company_response)
            if company_data:
                company = company_data[0].get('name')
        
        # Save authentication data
        self.config_manager.set_auth(email, token, company)
        
        print(colorize(f"Successfully logged in as {email}", 'GREEN'))
        if company:
            print(f"Company: {company}")
        
        return 0
    
    def logout(self, args):
        """Log out from the Rediacc API"""
        # Delete the user request if we have a token
        if self.config.get('token'):
            self.client.token_request("DeleteUserRequest")
        
        # Clear local auth data
        self.config_manager.clear_auth()
        print(colorize("Successfully logged out", 'GREEN'))
        return 0
    
    def generic_command(self, cmd_type, resource_type, args):
        """Handle generic commands using configuration"""
        if cmd_type not in CMD_CONFIG or resource_type not in CMD_CONFIG[cmd_type]:
            print(colorize(f"Error: Unsupported command: {cmd_type} {resource_type}", 'RED'))
            return 1
        
        cmd_config = CMD_CONFIG[cmd_type][resource_type]
        
        # For remove commands, confirm before proceeding
        if cmd_type == 'rm' and not args.force and 'confirm_msg' in cmd_config:
            confirm_msg = cmd_config['confirm_msg'].format(**{k: getattr(args, k, '') 
                                                             for k in dir(args) 
                                                             if not k.startswith('_')})
            confirm = input(f"{confirm_msg} [y/N] ")
            if confirm.lower() != 'y':
                print("Operation cancelled")
                return 0
        
        # Handle vault commands specially
        if cmd_type == 'vault':
            if resource_type == 'get':
                return self.vault_get(args)
            elif resource_type == 'set':
                return self.vault_set(args)
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
                    print(colorize("Error: Passwords do not match", 'RED'))
                    return 1
            
            response = self.client.auth_request(
                cmd_config['endpoint'], email, pwd_hash(password), params
            )
        else:
            # Use token authentication
            response = self.client.token_request(cmd_config['endpoint'], params)
        
        # For list commands, format the output
        if cmd_type == 'list':
            if response.get('error'):
                print(colorize(f"Error: {response['error']}", 'RED'))
                return 1
            
            result = format_dynamic_tables(response)
            if result == "No records found":
                if resource_type == 'bridges' and hasattr(args, 'region'):
                    print(f"No bridges found in region '{args.region}'")
                elif resource_type in ['machines', 'repositories'] and hasattr(args, 'team'):
                    print(f"No {resource_type} found in team '{args.team}'")
                else:
                    print(f"No {resource_type} found")
            else:
                print(result)
            return 0
        
        # For other commands, handle the response
        success_msg = cmd_config.get('success_msg')
        if self.handle_response(response, success_msg, args):
            return 0
        return 1
    
    def inspect_resource(self, resource_type, args):
        """Handle inspect commands"""
        if resource_type == 'team':
            # Get team details and members
            response = self.client.token_request("GetTeamMembers", {"teamName": args.name})
            
            if response.get('error'):
                print(colorize(f"Error: {response['error']}", 'RED'))
                return 1
            
            members = extract_table_data(response, table_index=1)
            
            # Get team machines
            machines_response = self.client.token_request("GetTeamMachines", {"teamName": args.name})
            
            machines = []
            if not machines_response.get('error'):
                machines = extract_table_data(machines_response, table_index=1)
            
            # Print team details
            print(colorize(f"Team: {args.name}", 'HEADER'))
            print(f"Members: {len(members)}")
            print(f"Machines: {len(machines)}")
            
            # Print member and machine details
            if members:
                print("\nMembers:")
                for member in members:
                    print(f"  - {member.get('userEmail', 'N/A')}")
            
            if machines:
                print("\nMachines:")
                for machine in machines:
                    print(f"  - {machine.get('machineName', 'N/A')} ({machine.get('bridgeName', 'N/A')})")
            
            return 0
            
        elif resource_type == 'machine':
            # Get machine details
            response = self.client.token_request("GetTeamMachines", {"teamName": args.team})
            
            if response.get('error'):
                print(colorize(f"Error: {response['error']}", 'RED'))
                return 1
            
            machines = extract_table_data(response, table_index=1)
            target_machine = next((m for m in machines if m.get('machineName') == args.name), None)
            
            if not target_machine:
                print(colorize(f"Machine not found: {args.name}", 'RED'))
                return 1
            
            # Print machine details
            print(colorize(f"Machine: {args.name}", 'HEADER'))
            print(f"Team: {args.team}")
            print(f"Bridge: {target_machine.get('bridgeName', 'N/A')}")
            print(f"Region: {target_machine.get('regionName', 'N/A')}")
            print(f"Queue Count: {target_machine.get('queueCount', 0)}")
            print(f"Vault Version: {target_machine.get('vaultVersion', 0)}")
            
            # Get queue items
            queue_response = self.client.token_request(
                "GetQueueItemsNext", {"machineName": args.name, "itemCount": 5}
            )
            
            if not queue_response.get('error'):
                queue_items = extract_table_data(queue_response, table_index=1)
                if queue_items:
                    print(f"\nQueue Items: {len(queue_items)}")
                    for item in queue_items:
                        print(f"  - {item.get('taskId', 'N/A')}")
            
            return 0
        
        print(colorize(f"Error: Unsupported resource type: {resource_type}", 'RED'))
        return 1
    
    def update_resource(self, resource_type, args):
        """Handle update commands"""
        success = True
        
        if resource_type == 'team':
            if args.new_name:
                # Update team name
                response = self.client.token_request(
                    "UpdateTeamName", 
                    {"currentTeamName": args.name, "newTeamName": args.new_name}
                )
                
                if not self.handle_response(
                    response, f"Successfully renamed team: {args.name} → {args.new_name}"
                ):
                    success = False
            
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
        
        elif resource_type == 'machine':
            team_name = args.team
            
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
                
                if not self.handle_response(
                    response, f"Successfully renamed machine: {args.name} → {args.new_name}"
                ):
                    success = False
            
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
                
                if not self.handle_response(
                    response, f"Successfully updated machine bridge: → {args.new_bridge}"
                ):
                    success = False
            
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
            print(colorize(f"Error: Unsupported resource type: {resource_type}", 'RED'))
            return 1
        
        return 0 if success else 1
    
    def vault_get(self, args):
        """Get vault data for a resource"""
        resource_type = args.resource_type
        endpoints = CMD_CONFIG['vault']['get']['endpoints']
        
        if resource_type not in endpoints:
            print(colorize(f"Error: Unsupported resource type: {resource_type}", 'RED'))
            return 1
        
        params = get_vault_get_params(args)
        response = self.client.token_request(endpoints[resource_type], params)
        
        if response.get('error'):
            print(colorize(f"Error: {response['error']}", 'RED'))
            return 1
        
        data = extract_table_data(response)
        if not data:
            print(colorize(f"No vault data found", 'YELLOW'))
            return 0
        
        # Extract vault data and print as JSON
        vault_data = data[0].get('vault', '{}')
        try:
            parsed = json.loads(vault_data)
            print(json.dumps(parsed, indent=2))
        except json.JSONDecodeError:
            print(vault_data)
        
        return 0
    
    def vault_set(self, args):
        """Set vault data for a resource"""
        resource_type = args.resource_type
        endpoints = CMD_CONFIG['vault']['set']['endpoints']
        
        if resource_type not in endpoints:
            print(colorize(f"Error: Unsupported resource type: {resource_type}", 'RED'))
            return 1
        
        params = get_vault_set_params(args)
        if not params:
            return 1
        
        response = self.client.token_request(endpoints[resource_type], params)
        
        if self.handle_response(response, f"Successfully updated {resource_type} vault"):
            return 0
        return 1

def setup_parser():
    """Create and configure the argument parser from definitions"""
    parser = argparse.ArgumentParser(
        description='Rediacc CLI - Docker-like interface for Rediacc Middleware API'
    )
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
                for arg in subcmd_def:
                    kwargs = {k: v for k, v in arg.items() if k != 'name'}
                    subcmd_parser.add_argument(arg['name'], **kwargs)
    
    return parser

def main():
    """Main CLI entry point"""
    parser = setup_parser()
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return 1
    
    # Load configuration
    config_manager = ConfigManager()
    handler = CommandHandler(config_manager)
    
    # Handle authentication commands directly
    if args.command == 'login':
        return handler.login(args)
    elif args.command == 'logout':
        return handler.logout(args)
    
    # Check if authenticated for other commands
    if not config_manager.is_authenticated():
        print(colorize("Error: Not authenticated. Please login first.", 'RED'))
        return 1
    
    # Handle other commands with resource types
    if not hasattr(args, 'resource') or not args.resource:
        print(colorize(f"Error: No resource specified for command: {args.command}", 'RED'))
        return 1
    
    # Special handling for certain commands
    if args.command == 'inspect':
        return handler.inspect_resource(args.resource, args)
    elif args.command == 'update':
        return handler.update_resource(args.resource, args)
    else:
        # Generic command handling for create, list, rm, vault
        return handler.generic_command(args.command, args.resource, args)

if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\nOperation cancelled by user")
        sys.exit(130)