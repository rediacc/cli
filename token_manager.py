#!/usr/bin/env python3
"""
Token Manager for Rediacc CLI
Handles secure token storage and retrieval with proper permissions
"""

import os
import json
import re
from pathlib import Path
from typing import Optional, Dict, Any
from datetime import datetime, timezone
import logging

logger = logging.getLogger(__name__)


class TokenManager:
    """Centralized token management with secure storage"""
    
    def __init__(self, config_dir: str = "~/.rediacc"):
        self.config_dir = Path(config_dir).expanduser()
        self.config_file = self.config_dir / "config.json"
        self._token_cache: Optional[str] = None
        self._config_cache: Optional[Dict[str, Any]] = None
        self._ensure_secure_config()
    
    def _ensure_secure_config(self):
        """Ensure config directory and file have proper permissions"""
        # Create directory with secure permissions
        self.config_dir.mkdir(mode=0o700, exist_ok=True)
        
        # Set secure permissions on existing config file
        if self.config_file.exists():
            try:
                self.config_file.chmod(0o600)
            except OSError as e:
                logger.warning(f"Could not set secure permissions on config file: {e}")
    
    def _load_from_config(self) -> Dict[str, Any]:
        """Load configuration from file"""
        if not self.config_file.exists():
            return {}
        
        try:
            with open(self.config_file, 'r') as f:
                self._config_cache = json.load(f)
                return self._config_cache
        except (json.JSONDecodeError, IOError) as e:
            logger.error(f"Failed to load config: {e}")
            return {}
    
    def _save_config(self, config: Dict[str, Any]):
        """Save configuration to file with secure permissions"""
        self.config_dir.mkdir(mode=0o700, exist_ok=True)
        
        # Write to temporary file first
        temp_file = self.config_file.with_suffix('.tmp')
        try:
            with open(temp_file, 'w') as f:
                json.dump(config, f, indent=2)
            
            # Set secure permissions before moving
            temp_file.chmod(0o600)
            
            # Atomic replace
            temp_file.replace(self.config_file)
            self._config_cache = config
            
        except Exception as e:
            logger.error(f"Failed to save config: {e}")
            if temp_file.exists():
                temp_file.unlink()
            raise
    
    def get_token(self, override_token: Optional[str] = None) -> Optional[str]:
        """
        Get token with clear precedence:
        1. Override token (from command line)
        2. Environment variable (REDIACC_TOKEN)
        3. Cached token (in memory)
        4. Config file
        """
        # 1. Override token has highest priority
        if override_token:
            if TokenManager.validate_token(override_token):
                return override_token
            else:
                logger.warning("Invalid override token format")
                return None
        
        # 2. Check environment variable
        env_token = os.environ.get('REDIACC_TOKEN')
        if env_token:
            if TokenManager.validate_token(env_token):
                self._token_cache = env_token
                return env_token
            else:
                logger.warning("Invalid token in REDIACC_TOKEN environment variable")
        
        # 3. Return cached token if available
        if self._token_cache:
            return self._token_cache
        
        # 4. Load from config file
        config = self._load_from_config()
        token = config.get('token')
        if token and TokenManager.validate_token(token):
            self._token_cache = token
            return token
        
        return None
    
    def set_token(self, token: str, email: Optional[str] = None, 
                  company: Optional[str] = None, vault_company: Optional[str] = None):
        """Store token and related auth info securely"""
        if not TokenManager.validate_token(token):
            raise ValueError("Invalid token format")
        
        config = self._load_from_config()
        
        # Update auth information
        config['token'] = token
        config['token_updated_at'] = datetime.now(timezone.utc).isoformat()
        
        if email:
            config['email'] = email
        if company:
            config['company'] = company
        if vault_company is not None:
            config['vault_company'] = vault_company
        
        self._save_config(config)
        self._token_cache = token
    
    def clear_token(self):
        """Clear token and authentication information"""
        config = self._load_from_config()
        
        # Remove auth-related fields
        auth_fields = ['token', 'token_updated_at', 'email', 'company', 'vault_company']
        for field in auth_fields:
            config.pop(field, None)
        
        self._save_config(config)
        self._token_cache = None
    
    def get_auth_info(self) -> Dict[str, Any]:
        """Get all authentication-related information"""
        config = self._load_from_config()
        return {
            'token': self.mask_token(config.get('token')),
            'email': config.get('email'),
            'company': config.get('company'),
            'has_vault': bool(config.get('vault_company')),
            'token_updated_at': config.get('token_updated_at')
        }
    
    @staticmethod
    def validate_token(token: Optional[str]) -> bool:
        """Validate token format (UUID/GUID)"""
        if not token:
            return False
        
        # GUID pattern: 8-4-4-4-12 hexadecimal digits
        guid_pattern = r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'
        return bool(re.match(guid_pattern, token, re.IGNORECASE))
    
    @staticmethod
    def mask_token(token: Optional[str]) -> Optional[str]:
        """Mask token for display (show only first 8 chars)"""
        if not token or len(token) < 12:
            return None
        return f"{token[:8]}..."
    
    def is_authenticated(self) -> bool:
        """Check if a valid token is available"""
        return self.get_token() is not None
    
    def get_config_value(self, key: str) -> Any:
        """Get any config value"""
        config = self._load_from_config()
        return config.get(key)
    
    def set_config_value(self, key: str, value: Any):
        """Set any config value"""
        config = self._load_from_config()
        config[key] = value
        self._save_config(config)


# Singleton instance
_default_manager = None

def get_default_token_manager() -> TokenManager:
    """Get the default token manager instance"""
    global _default_manager
    if _default_manager is None:
        _default_manager = TokenManager()
    return _default_manager