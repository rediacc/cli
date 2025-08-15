#!/usr/bin/env python3
"""
Centralized environment configuration module for Rediacc CLI.
Handles all environment variable parsing and provides defaults.
"""

import os
import json
from typing import Tuple, Optional, Dict, Any


class EnvironmentConfig:
    """Centralized environment configuration manager"""
    
    # Default values from typical .env file
    ENV_DEFAULTS = {
        'SYSTEM_DOMAIN': 'localhost',
        'SYSTEM_COMPANY_NAME': 'REDIACC.IO',
        'SYSTEM_ADMIN_EMAIL': 'admin@rediacc.io',
        'SYSTEM_ADMIN_PASSWORD': 'admin',
        'SYSTEM_DEFAULT_TEAM_NAME': 'Private Team',
        'SYSTEM_DEFAULT_REGION_NAME': 'Default Region',
        'SYSTEM_DEFAULT_BRIDGE_NAME': 'Global Bridges',
        'SYSTEM_SELF_MANAGED_BRIDGE_NAME': 'My Bridge',
        'SYSTEM_HTTP_PORT': '7322',
        'SYSTEM_SQL_PORT': '1433',
        'SYSTEM_API_URL': 'http://localhost:7322/api',
        'PUBLIC_API_URL': 'https://www.rediacc.com/api',
        'SYSTEM_BASE_IMAGE': 'ubuntu:24.04',
        'DOCKER_REGISTRY': '192.168.111.1:5000',
        'PROVISION_CEPH_CLUSTER': 'false',
        'PROVISION_KVM_MACHINES': 'true',
        'EMAIL_SERVICE_TYPE': 'EXCHANGE',
        'SYSTEM_COMPANY_VAULT_DEFAULTS': '{"UNIVERSAL_USER_ID":"7111","UNIVERSAL_USER_NAME":"rediacc","PLUGINS":{},"DOCKER_JSON_CONF":{}}',
    }
    
    # Default company vault structure
    DEFAULT_COMPANY_VAULT = {
        'UNIVERSAL_USER_ID': '7111',
        'UNIVERSAL_USER_NAME': 'rediacc',
        'PLUGINS': {
            'Terminal': {
                'image': '${DOCKER_REGISTRY}/rediacc/plugin-terminal:latest',
                'active': True
            },
            'Browser': {
                'image': '${DOCKER_REGISTRY}/rediacc/plugin-browser:latest',
                'active': True
            }
        },
        'DOCKER_JSON_CONF': {
            'insecure-registries': ['${DOCKER_REGISTRY}'],
            'registry-mirrors': ['http://${DOCKER_REGISTRY}']
        }
    }
    
    @classmethod
    def get_env(cls, key: str, default: Optional[str] = None) -> Optional[str]:
        """Get environment variable with fallback to defaults"""
        # First check actual environment
        if value := os.environ.get(key):
            return value
        # Then check our defaults
        return cls.ENV_DEFAULTS.get(key, default)
    
    @classmethod
    def get_company_vault_defaults(cls) -> Dict[str, Any]:
        """Parse SYSTEM_COMPANY_VAULT_DEFAULTS from environment or use defaults"""
        vault_json = cls.get_env('SYSTEM_COMPANY_VAULT_DEFAULTS')
        
        if not vault_json:
            return cls.DEFAULT_COMPANY_VAULT.copy()
        
        try:
            # Handle escaped JSON strings (e.g., from shell escaping)
            if vault_json.startswith('{') and '\\' in vault_json:
                # Remove escape characters from the JSON string
                vault_json = vault_json.replace('\\"', '"')
                vault_json = vault_json.replace('\\\\', '\\')
            
            # Parse the JSON string
            vault_data = json.loads(vault_json)
            
            # Ensure essential fields exist with defaults
            if 'UNIVERSAL_USER_ID' not in vault_data:
                vault_data['UNIVERSAL_USER_ID'] = cls.DEFAULT_COMPANY_VAULT['UNIVERSAL_USER_ID']
            if 'UNIVERSAL_USER_NAME' not in vault_data:
                vault_data['UNIVERSAL_USER_NAME'] = cls.DEFAULT_COMPANY_VAULT['UNIVERSAL_USER_NAME']
            
            # Handle variable substitution (e.g., ${DOCKER_REGISTRY})
            docker_registry = cls.get_env('DOCKER_REGISTRY', '192.168.111.1:5000')
            vault_str = json.dumps(vault_data)
            vault_str = vault_str.replace('${DOCKER_REGISTRY}', docker_registry)
            
            return json.loads(vault_str)
        except (json.JSONDecodeError, TypeError) as e:
            # If parsing fails, return defaults
            import sys
            print(f"Warning: Failed to parse SYSTEM_COMPANY_VAULT_DEFAULTS: {e}", file=sys.stderr)
            print(f"Debug: The string that failed to parse was: {repr(vault_json)}", file=sys.stderr)
            return cls.DEFAULT_COMPANY_VAULT.copy()
    
    @classmethod
    def get_universal_user_info(cls) -> Tuple[str, str, Optional[str]]:
        """
        Get universal user info from environment or defaults.
        Returns: (universal_user_name, universal_user_id, company_id)
        """
        vault_defaults = cls.get_company_vault_defaults()
        
        # Get values with fallbacks
        universal_user_name = vault_defaults.get('UNIVERSAL_USER_NAME', 'rediacc')
        universal_user_id = vault_defaults.get('UNIVERSAL_USER_ID', '7111')
        company_id = vault_defaults.get('COMPANY_ID')  # May be None
        
        return (universal_user_name, universal_user_id, company_id)
    
    @classmethod
    def get_universal_user_name(cls) -> str:
        """Get universal user name with guaranteed fallback"""
        name, _, _ = cls.get_universal_user_info()
        return name or 'rediacc'
    
    @classmethod
    def get_universal_user_id(cls) -> str:
        """Get universal user ID with guaranteed fallback"""
        _, uid, _ = cls.get_universal_user_info()
        return uid or '7111'
    
    @classmethod
    def get_system_defaults(cls) -> Dict[str, str]:
        """Get all system default values"""
        defaults = {}
        for key in cls.ENV_DEFAULTS:
            defaults[key] = cls.get_env(key)
        return defaults
    
    @classmethod
    def get_important_env_vars(cls) -> Dict[str, str]:
        """Get environment variables that should be exported to subprocesses"""
        important_vars = [
            'SYSTEM_API_URL',
            'SYSTEM_ADMIN_EMAIL',
            'SYSTEM_ADMIN_PASSWORD',
            'SYSTEM_MASTER_PASSWORD',
            'SYSTEM_HTTP_PORT',
            'SYSTEM_COMPANY_ID',
            'SYSTEM_COMPANY_VAULT_DEFAULTS',
            'SYSTEM_COMPANY_NAME',
            'SYSTEM_DEFAULT_TEAM_NAME',
            'SYSTEM_DEFAULT_REGION_NAME',
            'SYSTEM_DEFAULT_BRIDGE_NAME',
            'DOCKER_REGISTRY',
        ]
        
        env_vars = {}
        for var in important_vars:
            if value := cls.get_env(var):
                env_vars[var] = value
        
        return env_vars


# Convenience functions for backward compatibility
def get_universal_user_info() -> Tuple[str, str, Optional[str]]:
    """Get universal user info from environment"""
    return EnvironmentConfig.get_universal_user_info()


def get_universal_user_name() -> str:
    """Get universal user name with fallback"""
    return EnvironmentConfig.get_universal_user_name()


def get_universal_user_id() -> str:
    """Get universal user ID with fallback"""
    return EnvironmentConfig.get_universal_user_id()


def get_company_vault_defaults() -> Dict[str, Any]:
    """Get company vault defaults from environment"""
    return EnvironmentConfig.get_company_vault_defaults()