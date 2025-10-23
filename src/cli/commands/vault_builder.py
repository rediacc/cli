#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Rediacc CLI - VaultBuilder Utility

Shared utility for building queue vault data for workflow and queue operations.
This class builds vault data similar to console's queueDataService.
"""

import json
import os
import base64
from cli.config import CLI_CONFIG_FILE


def minifyJSON(json_str):
    """Minify JSON string by removing unnecessary whitespace"""
    try:
        return json.dumps(json.loads(json_str), separators=(',', ':'))
    except:
        return json_str


class VaultBuilder:
    """Build queue vault data similar to console's queueDataService"""

    def __init__(self, client, queue_functions=None):
        self.client = client
        self.company_vault = None
        self._vault_fetched = False

        # Load QUEUE_FUNCTIONS from config if not provided
        if queue_functions is None:
            try:
                with open(CLI_CONFIG_FILE, 'r', encoding='utf-8') as f:
                    cli_config = json.load(f)
                    self.queue_functions = cli_config.get('QUEUE_FUNCTIONS', {})
            except Exception:
                self.queue_functions = {}
        else:
            self.queue_functions = queue_functions

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

        # Map fields to expected format (always use lowercase with underscores)
        field_mappings = [
            ('IP', 'ip'),
            ('USER', 'user'),
            ('DATASTORE', 'datastore'),
            ('HOST_ENTRY', 'host_entry')
        ]

        for target_key, source_key in field_mappings:
            if source_key in vault:
                result[target_key] = vault[source_key]

        return result

    def build_for_function(self, function_name, context):
        """Build queue vault for a specific function"""
        # Get function requirements from QUEUE_FUNCTIONS
        func_def = self.queue_functions.get(function_name, {})
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
