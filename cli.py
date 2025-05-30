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
from pathlib import Path
from typing import Dict, Any, Optional

import requests

# Configuration
BASE_URL = os.environ.get('REDIACC_API_URL', 'http://localhost:8080')
API_PREFIX = '/api/StoredProcedure'
CONFIG_DIR = os.path.expanduser('~/.rediacc')
CONFIG_FILE = os.path.join(CONFIG_DIR, 'config.json')
REQUEST_TIMEOUT = 30

# Color codes for terminal output
COLORS = {
    'HEADER': '\033[95m',
    'BLUE': '\033[94m',
    'GREEN': '\033[92m',
    'YELLOW': '\033[93m',
    'RED': '\033[91m',
    'ENDC': '\033[0m',
    'BOLD': '\033[1m',
}

def colorize(text, color):
    """Add color to terminal output if supported"""
    if sys.stdout.isatty():
        return f"{COLORS.get(color, '')}{text}{COLORS['ENDC']}"
    return text

class APIClient:
    """Client for interacting with the Rediacc Middleware API"""
    def __init__(self, config=None):
        self.config = config or {}
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
    
    def request(self, endpoint, data=None, headers=None):
        """Make an API request to the middleware service"""
        url = f"{BASE_URL}{API_PREFIX}/{endpoint}"
        merged_headers = self.session.headers.copy()
        if headers:
            merged_headers.update(headers)
        
        try:
            response = self.session.post(
                url, 
                json=data or {}, 
                headers=merged_headers, 
                timeout=REQUEST_TIMEOUT
            )
            
            if response.status_code != 200:
                error_msg = f"API Error: {response.status_code} - {response.text}"
                return {"error": error_msg, "status_code": response.status_code}
            
            result = response.json()
            # Check for actual failure (failure != 0)
            if result.get('failure') and result.get('failure') != 0:
                error_msg = f"API Error: {result.get('message', 'Unknown error')}"
                return {"error": error_msg, "status_code": 400}
            
            return result
        except requests.exceptions.RequestException as e:
            return {"error": f"Connection error: {str(e)}", "status_code": 500}
    
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
        
        return self.request(endpoint, data, {
            "Rediacc-RequestToken": self.config['token']
        })

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
        self.config.update({
            'email': email,
            'token': token,
            'company': company
        })
        self.save_config()
    
    def clear_auth(self):
        """Clear authentication information"""
        for key in ['email', 'token', 'company']:
            self.config.pop(key, None)
        self.save_config()
    
    def is_authenticated(self):
        """Check if user is authenticated"""
        return bool(self.config.get('token'))

# Utilities
def pwd_hash(pwd):
    """Generate a base64 password hash for authentication"""
    return base64.b64encode(hashlib.sha256(pwd.encode()).digest()).decode()

def pwd_hash_hex(pwd):
    """Generate a hexadecimal password hash for user creation/updates"""
    return "0x" + hashlib.sha256(pwd.encode()).digest().hex()

def format_table(headers, rows):
    """Format data as a table for display"""
    if not rows:
        return "No items found"
    
    # Calculate column widths
    widths = [len(h) for h in headers]
    for row in rows:
        for i, cell in enumerate(row):
            widths[i] = max(widths[i], len(str(cell)))
    
    # Format the headers
    header_line = '  '.join(h.ljust(w) for h, w in zip(headers, widths))
    separator = '-' * len(header_line)
    
    # Format the rows
    formatted_rows = [
        '  '.join(str(cell).ljust(w) for cell, w in zip(row, widths))
        for row in rows
    ]
    
    return '\n'.join([header_line, separator] + formatted_rows)

def load_vault_data(file_path):
    """Load vault data from a file or return empty vault"""
    if not file_path or file_path == '-':
        # Read from stdin
        try:
            return json.loads(sys.stdin.read())
        except json.JSONDecodeError:
            return {}
    
    try:
        with open(file_path, 'r') as f:
            return json.load(f)
    except (IOError, json.JSONDecodeError):
        print(colorize(f"Warning: Could not load vault data from {file_path}. Using empty vault.", 'YELLOW'))
        return {}

def empty_vault():
    """Create an empty vault data structure"""
    return "{}"

def extract_table_data(response, table_index=0):
    """Extract data from API response tables"""
    if not response or 'tables' not in response or len(response['tables']) <= table_index:
        return []
    
    return response['tables'][table_index].get('data', [])

# Command handlers
class CommandHandler:
    """Base class for command handlers"""
    def __init__(self, config_manager):
        self.config = config_manager.config
        self.client = APIClient(self.config)
    
    def _handle_response(self, response, success_message=None):
        """Handle API response and print appropriate message"""
        if response.get('error'):
            print(colorize(f"Error: {response['error']}", 'RED'))
            return False
        
        if success_message:
            print(colorize(success_message, 'GREEN'))
        
        return True
    
    def _extract_data(self, response, table_index=0):
        """Extract data from response tables"""
        return extract_table_data(response, table_index)

class AuthCommands(CommandHandler):
    """Commands for authentication"""
    def login(self, args):
        """Log in to the Rediacc API"""
        email = args.email
        if not email:
            email = input("Email: ")
        
        password = args.password
        if not password:
            password = getpass.getpass("Password: ")
        
        hash_pwd = pwd_hash(password)
        
        # Try to create authentication request
        response = self.client.auth_request(
            "CreateAuthenticationRequest", 
            email, 
            hash_pwd, 
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
            "GetUserCompany", 
            {}, 
            {"Rediacc-UserEmail": email, "Rediacc-UserHash": hash_pwd}
        )
        
        company = None
        if not company_response.get('error'):
            company_data = self._extract_data(company_response)
            if company_data:
                company = company_data[0].get('name')
        
        # Save authentication data
        config_manager = ConfigManager()
        config_manager.set_auth(email, token, company)
        
        print(colorize(f"Successfully logged in as {email}", 'GREEN'))
        if company:
            print(f"Company: {company}")
        
        return 0
    
    def logout(self, args):
        """Log out from the Rediacc API"""
        # Delete the user request if we have a token
        if self.config.get('token'):
            response = self.client.request(
                "DeleteUserRequest", 
                {}, 
                {"Rediacc-RequestToken": self.config['token']}
            )
            # We don't care too much about the response here
        
        # Clear local auth data
        config_manager = ConfigManager()
        config_manager.clear_auth()
        
        print(colorize("Successfully logged out", 'GREEN'))
        return 0

class CreateCommands(CommandHandler):
    """Commands for creating resources"""
    def company(self, args):
        """Create a new company"""
        email = args.email
        if not email:
            email = input("Admin Email: ")
        
        password = args.password
        if not password:
            password = getpass.getpass("Admin Password: ")
            confirm = getpass.getpass("Confirm Password: ")
            if password != confirm:
                print(colorize("Error: Passwords do not match", 'RED'))
                return 1
        
        p_hash = pwd_hash(password)
        
        response = self.client.auth_request(
            "CreateNewCompany", 
            email, 
            p_hash, 
            {
                "companyName": args.name, 
                "subscriptionPlan": args.plan or "ELITE"
            }
        )
        
        return self._handle_response(
            response,
            f"Successfully created company: {args.name}"
        )
    
    def team(self, args):
        """Create a new team"""
        # Load vault data if provided
        vault_data = args.vault
        if args.vault_file:
            vault_data = json.dumps(load_vault_data(args.vault_file))
        
        response = self.client.token_request(
            "CreateTeam", 
            {
                "teamName": args.name,
                "teamVault": vault_data or empty_vault()
            }
        )
        
        return self._handle_response(
            response,
            f"Successfully created team: {args.name}"
        )
    
    def region(self, args):
        """Create a new region"""
        # Load vault data if provided
        vault_data = args.vault
        if args.vault_file:
            vault_data = json.dumps(load_vault_data(args.vault_file))
        
        response = self.client.token_request(
            "CreateRegion", 
            {
                "regionName": args.name,
                "regionVault": vault_data or empty_vault()
            }
        )
        
        return self._handle_response(
            response,
            f"Successfully created region: {args.name}"
        )
    
    def bridge(self, args):
        """Create a bridge in a region"""
        # Load vault data if provided
        vault_data = args.vault
        if args.vault_file:
            vault_data = json.dumps(load_vault_data(args.vault_file))
        
        response = self.client.token_request(
            "CreateBridge", 
            {
                "regionName": args.region,
                "bridgeName": args.name,
                "bridgeVault": vault_data or empty_vault()
            }
        )
        
        return self._handle_response(
            response,
            f"Successfully created bridge: {args.name} in region {args.region}"
        )
    
    def machine(self, args):
        """Create a machine for a team using a bridge"""
        # Load vault data if provided
        vault_data = args.vault
        if args.vault_file:
            vault_data = json.dumps(load_vault_data(args.vault_file))
        
        response = self.client.token_request(
            "CreateMachine", 
            {
                "teamName": args.team,
                "bridgeName": args.bridge,
                "machineName": args.name,
                "machineVault": vault_data or empty_vault()
            }
        )
        
        return self._handle_response(
            response,
            f"Successfully created machine: {args.name} for team {args.team}"
        )
    
    def repository(self, args):
        """Create a repository for a team"""
        # Load vault data if provided
        vault_data = args.vault
        if args.vault_file:
            vault_data = json.dumps(load_vault_data(args.vault_file))
        
        response = self.client.token_request(
            "CreateRepository", 
            {
                "teamName": args.team,
                "repoName": args.name,
                "repoVault": vault_data or empty_vault()
            }
        )
        
        return self._handle_response(
            response,
            f"Successfully created repository: {args.name} for team {args.team}"
        )
    
    def storage(self, args):
        """Create storage for a team"""
        # Load vault data if provided
        vault_data = args.vault
        if args.vault_file:
            vault_data = json.dumps(load_vault_data(args.vault_file))
        
        response = self.client.token_request(
            "CreateStorage", 
            {
                "teamName": args.team,
                "storageName": args.name,
                "storageVault": vault_data or empty_vault()
            }
        )
        
        return self._handle_response(
            response,
            f"Successfully created storage: {args.name} for team {args.team}"
        )
    
    def schedule(self, args):
        """Create a schedule for a team"""
        # Load vault data if provided
        vault_data = args.vault
        if args.vault_file:
            vault_data = json.dumps(load_vault_data(args.vault_file))
        
        response = self.client.token_request(
            "CreateSchedule", 
            {
                "teamName": args.team,
                "scheduleName": args.name,
                "scheduleVault": vault_data or empty_vault()
            }
        )
        
        return self._handle_response(
            response,
            f"Successfully created schedule: {args.name} for team {args.team}"
        )

class ListCommands(CommandHandler):
    """Commands for listing resources"""
    def teams(self, args):
        """List all teams"""
        response = self.client.token_request("GetCompanyTeams")
        
        if response.get('error'):
            print(colorize(f"Error: {response['error']}", 'RED'))
            return 1
        
        teams = self._extract_data(response)
        if not teams:
            print("No teams found")
            return 0
        
        headers = ["NAME", "CREATED", "USERS"]
        rows = [
            [
                team.get('name', 'N/A'),
                team.get('created', 'N/A'),
                team.get('memberCount', 'N/A')
            ]
            for team in teams
        ]
        
        print(format_table(headers, rows))
        return 0
    
    def regions(self, args):
        """List all regions"""
        response = self.client.token_request("GetCompanyRegions")
        
        if response.get('error'):
            print(colorize(f"Error: {response['error']}", 'RED'))
            return 1
        
        regions = self._extract_data(response)
        if not regions:
            print("No regions found")
            return 0
        
        headers = ["NAME", "CREATED", "BRIDGES"]
        rows = [
            [
                region.get('name', 'N/A'),
                region.get('created', 'N/A'),
                region.get('bridgeCount', 0)
            ]
            for region in regions
        ]
        
        print(format_table(headers, rows))
        return 0
    
    def bridges(self, args):
        """List bridges in a region"""
        response = self.client.token_request(
            "GetRegionBridges", 
            {"regionName": args.region}
        )
        
        if response.get('error'):
            print(colorize(f"Error: {response['error']}", 'RED'))
            return 1
        
        bridges = self._extract_data(response)
        if not bridges:
            print(f"No bridges found in region {args.region}")
            return 0
        
        headers = ["NAME", "CREATED", "MACHINES"]
        rows = [
            [
                bridge.get('name', 'N/A'),
                bridge.get('created', 'N/A'),
                bridge.get('machineCount', 0)
            ]
            for bridge in bridges
        ]
        
        print(format_table(headers, rows))
        return 0
    
    def machines(self, args):
        """List machines in a team"""
        response = self.client.token_request(
            "GetTeamMachines", 
            {"teamName": args.team}
        )
        
        if response.get('error'):
            print(colorize(f"Error: {response['error']}", 'RED'))
            return 1
        
        machines = self._extract_data(response)
        if not machines:
            print(f"No machines found in team {args.team}")
            return 0
        
        headers = ["NAME", "BRIDGE", "CREATED", "STATUS"]
        rows = [
            [
                machine.get('name', 'N/A'),
                machine.get('bridgeName', 'N/A'),
                machine.get('created', 'N/A'),
                machine.get('status', 'N/A')
            ]
            for machine in machines
        ]
        
        print(format_table(headers, rows))
        return 0
    
    def repositories(self, args):
        """List repositories in a team"""
        response = self.client.token_request(
            "GetTeamRepositories", 
            {"teamName": args.team}
        )
        
        if response.get('error'):
            print(colorize(f"Error: {response['error']}", 'RED'))
            return 1
        
        repos = self._extract_data(response)
        if not repos:
            print(f"No repositories found in team {args.team}")
            return 0
        
        headers = ["NAME", "CREATED", "VAULT VERSION"]
        rows = [
            [
                repo.get('name', 'N/A'),
                repo.get('created', 'N/A'),
                repo.get('vaultVersion', 0)
            ]
            for repo in repos
        ]
        
        print(format_table(headers, rows))
        return 0

class InspectCommands(CommandHandler):
    """Commands for inspecting resources"""
    def team(self, args):
        """Inspect a team"""
        # First get team details
        response = self.client.token_request(
            "GetTeamMembers", 
            {"teamName": args.name}
        )
        
        if response.get('error'):
            print(colorize(f"Error: {response['error']}", 'RED'))
            return 1
        
        members = self._extract_data(response)
        
        # Get team machines
        machines_response = self.client.token_request(
            "GetTeamMachines", 
            {"teamName": args.name}
        )
        
        machines = []
        if not machines_response.get('error'):
            machines = self._extract_data(machines_response)
        
        # Print team details
        print(colorize(f"Team: {args.name}", 'HEADER'))
        print(f"Members: {len(members)}")
        print(f"Machines: {len(machines)}")
        
        # Print member details if any
        if members:
            print("\nMembers:")
            for member in members:
                print(f"  - {member.get('email', 'N/A')}")
        
        # Print machine details if any
        if machines:
            print("\nMachines:")
            for machine in machines:
                print(f"  - {machine.get('name', 'N/A')} ({machine.get('bridgeName', 'N/A')})")
        
        return 0
    
    def machine(self, args):
        """Inspect a machine"""
        # Get team machines to find the specific one
        response = self.client.token_request(
            "GetTeamMachines", 
            {"teamName": args.team}
        )
        
        if response.get('error'):
            print(colorize(f"Error: {response['error']}", 'RED'))
            return 1
        
        machines = self._extract_data(response)
        target_machine = next((m for m in machines if m.get('name') == args.name), None)
        
        if not target_machine:
            print(colorize(f"Machine not found: {args.name}", 'RED'))
            return 1
        
        # Print machine details
        print(colorize(f"Machine: {args.name}", 'HEADER'))
        print(f"Team: {args.team}")
        print(f"Bridge: {target_machine.get('bridgeName', 'N/A')}")
        print(f"Created: {target_machine.get('created', 'N/A')}")
        print(f"Status: {target_machine.get('status', 'N/A')}")
        print(f"Vault Version: {target_machine.get('vaultVersion', 0)}")
        
        # Get queue items if any
        queue_response = self.client.token_request(
            "GetQueueItemsNext", 
            {"machineName": args.name, "itemCount": 5}
        )
        
        if not queue_response.get('error'):
            queue_items = self._extract_data(queue_response)
            if queue_items:
                print(f"\nQueue Items: {len(queue_items)}")
                for item in queue_items:
                    print(f"  - {item.get('taskId', 'N/A')}")
        
        return 0

class UpdateCommands(CommandHandler):
    """Commands for updating resources"""
    def team(self, args):
        """Update a team"""
        if args.new_name:
            # Update team name
            response = self.client.token_request(
                "UpdateTeamName", 
                {
                    "currentTeamName": args.name,
                    "newTeamName": args.new_name
                }
            )
            
            if not self._handle_response(
                response,
                f"Successfully renamed team: {args.name} → {args.new_name}"
            ):
                return 1
        
        # Update vault if provided
        if args.vault or args.vault_file:
            vault_data = args.vault
            if args.vault_file:
                vault_data = json.dumps(load_vault_data(args.vault_file))
            
            # Use new name if we just renamed the team
            team_name = args.new_name if args.new_name else args.name
            
            response = self.client.token_request(
                "UpdateTeamVault", 
                {
                    "teamName": team_name,
                    "teamVault": vault_data,
                    "vaultVersion": args.vault_version or 1
                }
            )
            
            if not self._handle_response(
                response,
                f"Successfully updated team vault"
            ):
                return 1
        
        return 0
    
    def machine(self, args):
        """Update a machine"""
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
            
            if not self._handle_response(
                response,
                f"Successfully renamed machine: {args.name} → {args.new_name}"
            ):
                return 1
        
        # Update bridge if provided
        if args.new_bridge:
            # Use new name if we just renamed the machine
            machine_name = args.new_name if args.new_name else args.name
            
            response = self.client.token_request(
                "UpdateMachineAssignedBridge", 
                {
                    "teamName": team_name,
                    "machineName": machine_name,
                    "newBridgeName": args.new_bridge
                }
            )
            
            if not self._handle_response(
                response,
                f"Successfully updated machine bridge: → {args.new_bridge}"
            ):
                return 1
        
        # Update vault if provided
        if args.vault or args.vault_file:
            vault_data = args.vault
            if args.vault_file:
                vault_data = json.dumps(load_vault_data(args.vault_file))
            
            # Use new name if we just renamed the machine
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
            
            if not self._handle_response(
                response,
                f"Successfully updated machine vault"
            ):
                return 1
        
        return 0

class RemoveCommands(CommandHandler):
    """Commands for removing resources"""
    def team(self, args):
        """Remove a team"""
        if not args.force:
            confirm = input(f"Are you sure you want to delete team '{args.name}'? This will remove all resources in the team. [y/N] ")
            if confirm.lower() != 'y':
                print("Operation cancelled")
                return 0
        
        response = self.client.token_request(
            "DeleteTeam", 
            {"teamName": args.name}
        )
        
        return self._handle_response(
            response,
            f"Successfully deleted team: {args.name}"
        )
    
    def machine(self, args):
        """Remove a machine"""
        if not args.force:
            confirm = input(f"Are you sure you want to delete machine '{args.name}' from team '{args.team}'? [y/N] ")
            if confirm.lower() != 'y':
                print("Operation cancelled")
                return 0
        
        response = self.client.token_request(
            "DeleteMachine", 
            {
                "teamName": args.team,
                "machineName": args.name
            }
        )
        
        return self._handle_response(
            response,
            f"Successfully deleted machine: {args.name}"
        )
    
    def bridge(self, args):
        """Remove a bridge"""
        if not args.force:
            confirm = input(f"Are you sure you want to delete bridge '{args.name}' from region '{args.region}'? [y/N] ")
            if confirm.lower() != 'y':
                print("Operation cancelled")
                return 0
        
        response = self.client.token_request(
            "DeleteBridge", 
            {
                "regionName": args.region,
                "bridgeName": args.name
            }
        )
        
        return self._handle_response(
            response,
            f"Successfully deleted bridge: {args.name}"
        )
    
    def region(self, args):
        """Remove a region"""
        if not args.force:
            confirm = input(f"Are you sure you want to delete region '{args.name}'? This will remove all bridges in the region. [y/N] ")
            if confirm.lower() != 'y':
                print("Operation cancelled")
                return 0
        
        response = self.client.token_request(
            "DeleteRegion", 
            {"regionName": args.name}
        )
        
        return self._handle_response(
            response,
            f"Successfully deleted region: {args.name}"
        )

class VaultCommands(CommandHandler):
    """Commands for managing vault data"""
    def get(self, args):
        """Get vault data for a resource"""
        resource_type = args.resource_type
        
        if resource_type == "team":
            response = self.client.token_request(
                "GetTeamVault", 
                {"teamName": args.name}
            )
        elif resource_type == "machine":
            response = self.client.token_request(
                "GetMachineVault", 
                {
                    "teamName": args.team,
                    "machineName": args.name
                }
            )
        elif resource_type == "region":
            response = self.client.token_request(
                "GetRegionVault", 
                {"regionName": args.name}
            )
        elif resource_type == "bridge":
            response = self.client.token_request(
                "GetBridgeVault", 
                {
                    "regionName": args.region,
                    "bridgeName": args.name
                }
            )
        elif resource_type == "company":
            response = self.client.token_request("GetCompanyVault")
        else:
            print(colorize(f"Error: Unsupported resource type: {resource_type}", 'RED'))
            return 1
        
        if response.get('error'):
            print(colorize(f"Error: {response['error']}", 'RED'))
            return 1
        
        data = self._extract_data(response)
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
    
    def set(self, args):
        """Set vault data for a resource"""
        resource_type = args.resource_type
        
        # Load vault data
        vault_data = None
        if args.file and args.file != '-':
            try:
                with open(args.file, 'r') as f:
                    vault_data = f.read()
            except IOError:
                print(colorize(f"Error: Could not read file: {args.file}", 'RED'))
                return 1
        else:
            # Read from stdin
            print("Enter JSON vault data (press Ctrl+D when finished):")
            vault_data = sys.stdin.read()
        
        # Validate JSON
        try:
            json.loads(vault_data)
        except json.JSONDecodeError as e:
            print(colorize(f"Error: Invalid JSON: {str(e)}", 'RED'))
            return 1
        
        # Update vault based on resource type
        if resource_type == "team":
            response = self.client.token_request(
                "UpdateTeamVault", 
                {
                    "teamName": args.name,
                    "teamVault": vault_data,
                    "vaultVersion": args.vault_version or 1
                }
            )
        elif resource_type == "machine":
            response = self.client.token_request(
                "UpdateMachineVault", 
                {
                    "teamName": args.team,
                    "machineName": args.name,
                    "machineVault": vault_data,
                    "vaultVersion": args.vault_version or 1
                }
            )
        elif resource_type == "region":
            response = self.client.token_request(
                "UpdateRegionVault", 
                {
                    "regionName": args.name,
                    "regionVault": vault_data,
                    "vaultVersion": args.vault_version or 1
                }
            )
        elif resource_type == "bridge":
            response = self.client.token_request(
                "UpdateBridgeVault", 
                {
                    "regionName": args.region,
                    "bridgeName": args.name,
                    "bridgeVault": vault_data,
                    "vaultVersion": args.vault_version or 1
                }
            )
        elif resource_type == "company":
            response = self.client.token_request(
                "UpdateCompanyVault", 
                {
                    "companyVault": vault_data,
                    "vaultVersion": args.vault_version or 1
                }
            )
        else:
            print(colorize(f"Error: Unsupported resource type: {resource_type}", 'RED'))
            return 1
        
        return self._handle_response(
            response,
            f"Successfully updated {resource_type} vault"
        )

def setup_auth_parser(subparsers):
    """Set up authentication command parsers"""
    # Login command
    login_parser = subparsers.add_parser('login', help='Authenticate with the Rediacc API')
    login_parser.add_argument('--email', help='User email address')
    login_parser.add_argument('--password', help='User password')
    login_parser.add_argument('--session-name', help='Name for this session')
    
    # Logout command
    logout_parser = subparsers.add_parser('logout', help='End the current session')

def setup_create_parser(subparsers):
    """Set up create command parsers"""
    create_parser = subparsers.add_parser('create', help='Create resources')
    create_subparsers = create_parser.add_subparsers(dest='resource', help='Resource to create')
    
    # Company creation
    company_parser = create_subparsers.add_parser('company', help='Create a new company')
    company_parser.add_argument('name', help='Company name')
    company_parser.add_argument('--email', help='Admin email address')
    company_parser.add_argument('--password', help='Admin password')
    company_parser.add_argument('--plan', help='Subscription plan', choices=['FREE', 'BASIC', 'PRO', 'ELITE'])
    
    # Team creation
    team_parser = create_subparsers.add_parser('team', help='Create a new team')
    team_parser.add_argument('name', help='Team name')
    team_parser.add_argument('--vault', help='JSON vault data')
    team_parser.add_argument('--vault-file', help='File containing JSON vault data')
    
    # Region creation
    region_parser = create_subparsers.add_parser('region', help='Create a new region')
    region_parser.add_argument('name', help='Region name')
    region_parser.add_argument('--vault', help='JSON vault data')
    region_parser.add_argument('--vault-file', help='File containing JSON vault data')
    
    # Bridge creation
    bridge_parser = create_subparsers.add_parser('bridge', help='Create a new bridge')
    bridge_parser.add_argument('region', help='Region name')
    bridge_parser.add_argument('name', help='Bridge name')
    bridge_parser.add_argument('--vault', help='JSON vault data')
    bridge_parser.add_argument('--vault-file', help='File containing JSON vault data')
    
    # Machine creation
    machine_parser = create_subparsers.add_parser('machine', help='Create a new machine')
    machine_parser.add_argument('team', help='Team name')
    machine_parser.add_argument('bridge', help='Bridge name')
    machine_parser.add_argument('name', help='Machine name')
    machine_parser.add_argument('--vault', help='JSON vault data')
    machine_parser.add_argument('--vault-file', help='File containing JSON vault data')
    
    # Repository creation
    repo_parser = create_subparsers.add_parser('repository', help='Create a new repository')
    repo_parser.add_argument('team', help='Team name')
    repo_parser.add_argument('name', help='Repository name')
    repo_parser.add_argument('--vault', help='JSON vault data')
    repo_parser.add_argument('--vault-file', help='File containing JSON vault data')
    
    # Storage creation
    storage_parser = create_subparsers.add_parser('storage', help='Create new storage')
    storage_parser.add_argument('team', help='Team name')
    storage_parser.add_argument('name', help='Storage name')
    storage_parser.add_argument('--vault', help='JSON vault data')
    storage_parser.add_argument('--vault-file', help='File containing JSON vault data')
    
    # Schedule creation
    schedule_parser = create_subparsers.add_parser('schedule', help='Create a new schedule')
    schedule_parser.add_argument('team', help='Team name')
    schedule_parser.add_argument('name', help='Schedule name')
    schedule_parser.add_argument('--vault', help='JSON vault data')
    schedule_parser.add_argument('--vault-file', help='File containing JSON vault data')

def setup_list_parser(subparsers):
    """Set up list command parsers"""
    list_parser = subparsers.add_parser('list', help='List resources')
    list_subparsers = list_parser.add_subparsers(dest='resource', help='Resource to list')
    
    # List teams
    teams_parser = list_subparsers.add_parser('teams', help='List all teams')
    
    # List regions
    regions_parser = list_subparsers.add_parser('regions', help='List all regions')
    
    # List bridges
    bridges_parser = list_subparsers.add_parser('bridges', help='List bridges in a region')
    bridges_parser.add_argument('region', help='Region name')
    
    # List machines
    machines_parser = list_subparsers.add_parser('machines', help='List machines in a team')
    machines_parser.add_argument('team', help='Team name')
    
    # List repositories
    repos_parser = list_subparsers.add_parser('repositories', help='List repositories in a team')
    repos_parser.add_argument('team', help='Team name')

def setup_inspect_parser(subparsers):
    """Set up inspect command parsers"""
    inspect_parser = subparsers.add_parser('inspect', help='Inspect resources')
    inspect_subparsers = inspect_parser.add_subparsers(dest='resource', help='Resource to inspect')
    
    # Inspect team
    team_parser = inspect_subparsers.add_parser('team', help='Inspect a team')
    team_parser.add_argument('name', help='Team name')
    
    # Inspect machine
    machine_parser = inspect_subparsers.add_parser('machine', help='Inspect a machine')
    machine_parser.add_argument('team', help='Team name')
    machine_parser.add_argument('name', help='Machine name')

def setup_update_parser(subparsers):
    """Set up update command parsers"""
    update_parser = subparsers.add_parser('update', help='Update resources')
    update_subparsers = update_parser.add_subparsers(dest='resource', help='Resource to update')
    
    # Update team
    team_parser = update_subparsers.add_parser('team', help='Update a team')
    team_parser.add_argument('name', help='Team name')
    team_parser.add_argument('--new-name', help='New team name')
    team_parser.add_argument('--vault', help='JSON vault data')
    team_parser.add_argument('--vault-file', help='File containing JSON vault data')
    team_parser.add_argument('--vault-version', type=int, help='Vault version')
    
    # Update machine
    machine_parser = update_subparsers.add_parser('machine', help='Update a machine')
    machine_parser.add_argument('team', help='Team name')
    machine_parser.add_argument('name', help='Machine name')
    machine_parser.add_argument('--new-name', help='New machine name')
    machine_parser.add_argument('--new-bridge', help='New bridge name')
    machine_parser.add_argument('--vault', help='JSON vault data')
    machine_parser.add_argument('--vault-file', help='File containing JSON vault data')
    machine_parser.add_argument('--vault-version', type=int, help='Vault version')

def setup_remove_parser(subparsers):
    """Set up remove command parsers"""
    remove_parser = subparsers.add_parser('rm', help='Remove resources')
    remove_subparsers = remove_parser.add_subparsers(dest='resource', help='Resource to remove')
    
    # Remove team
    team_parser = remove_subparsers.add_parser('team', help='Remove a team')
    team_parser.add_argument('name', help='Team name')
    team_parser.add_argument('--force', action='store_true', help='Skip confirmation')
    
    # Remove machine
    machine_parser = remove_subparsers.add_parser('machine', help='Remove a machine')
    machine_parser.add_argument('team', help='Team name')
    machine_parser.add_argument('name', help='Machine name')
    machine_parser.add_argument('--force', action='store_true', help='Skip confirmation')
    
    # Remove bridge
    bridge_parser = remove_subparsers.add_parser('bridge', help='Remove a bridge')
    bridge_parser.add_argument('region', help='Region name')
    bridge_parser.add_argument('name', help='Bridge name')
    bridge_parser.add_argument('--force', action='store_true', help='Skip confirmation')
    
    # Remove region
    region_parser = remove_subparsers.add_parser('region', help='Remove a region')
    region_parser.add_argument('name', help='Region name')
    region_parser.add_argument('--force', action='store_true', help='Skip confirmation')

def setup_vault_parser(subparsers):
    """Set up vault command parsers"""
    vault_parser = subparsers.add_parser('vault', help='Manage vault data')
    vault_subparsers = vault_parser.add_subparsers(dest='action', help='Vault action')
    
    # Get vault data
    get_parser = vault_subparsers.add_parser('get', help='Get vault data')
    get_parser.add_argument('resource_type', help='Resource type', 
                           choices=['team', 'machine', 'region', 'bridge', 'company'])
    get_parser.add_argument('name', help='Resource name')
    get_parser.add_argument('--team', help='Team name (for machine)')
    get_parser.add_argument('--region', help='Region name (for bridge)')
    
    # Set vault data
    set_parser = vault_subparsers.add_parser('set', help='Set vault data')
    set_parser.add_argument('resource_type', help='Resource type', 
                           choices=['team', 'machine', 'region', 'bridge', 'company'])
    set_parser.add_argument('name', help='Resource name')
    set_parser.add_argument('file', nargs='?', help='File containing JSON vault data (or - for stdin)')
    set_parser.add_argument('--team', help='Team name (for machine)')
    set_parser.add_argument('--region', help='Region name (for bridge)')
    set_parser.add_argument('--vault-version', type=int, help='Vault version')

def main():
    """Main CLI entry point"""
    parser = argparse.ArgumentParser(description='Rediacc CLI - Docker-like interface for Rediacc Middleware API')
    subparsers = parser.add_subparsers(dest='command', help='Command')
    
    # Set up command parsers
    setup_auth_parser(subparsers)
    setup_create_parser(subparsers)
    setup_list_parser(subparsers)
    setup_inspect_parser(subparsers)
    setup_update_parser(subparsers)
    setup_remove_parser(subparsers)
    setup_vault_parser(subparsers)
    
    # Parse arguments
    args = parser.parse_args()
    
    # Load configuration
    config_manager = ConfigManager()
    
    # Handle commands
    if args.command == 'login':
        handler = AuthCommands(config_manager)
        return handler.login(args)
    elif args.command == 'logout':
        handler = AuthCommands(config_manager)
        return handler.logout(args)
    
    # Check if authenticated for other commands
    if args.command not in ['login', 'logout'] and not config_manager.is_authenticated():
        print(colorize("Error: Not authenticated. Please login first.", 'RED'))
        return 1
    
    # Handle resource commands
    if args.command == 'create' and args.resource:
        handler = CreateCommands(config_manager)
        if hasattr(handler, args.resource):
            return getattr(handler, args.resource)(args)
    elif args.command == 'list' and args.resource:
        handler = ListCommands(config_manager)
        if hasattr(handler, args.resource):
            return getattr(handler, args.resource)(args)
    elif args.command == 'inspect' and args.resource:
        handler = InspectCommands(config_manager)
        if hasattr(handler, args.resource):
            return getattr(handler, args.resource)(args)
    elif args.command == 'update' and args.resource:
        handler = UpdateCommands(config_manager)
        if hasattr(handler, args.resource):
            return getattr(handler, args.resource)(args)
    elif args.command == 'rm' and args.resource:
        handler = RemoveCommands(config_manager)
        if hasattr(handler, args.resource):
            return getattr(handler, args.resource)(args)
    elif args.command == 'vault' and args.action:
        handler = VaultCommands(config_manager)
        if hasattr(handler, args.action):
            return getattr(handler, args.action)(args)
    
    # If we get here, either no command was specified or the command was invalid
    if not args.command:
        parser.print_help()
    else:
        print(colorize(f"Error: Invalid command or missing subcommand: {args.command}", 'RED'))
    
    return 1

if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\nOperation cancelled by user")
        sys.exit(130)