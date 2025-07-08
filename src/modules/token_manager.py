#!/usr/bin/env python3
"""
Token Manager for Rediacc CLI
Handles secure token storage and retrieval with proper permissions
Uses singleton pattern to ensure consistent token management across the application
"""

import os
import json
import re
import fcntl
import time
import threading
from pathlib import Path
from typing import Optional, Dict, Any
from datetime import datetime, timezone
import logging

# Import configuration loader
from config_loader import get_path

logger = logging.getLogger(__name__)


class TokenManager:
    """Centralized token management with secure storage - Singleton implementation"""
    
    # Class-level attributes for singleton
    _instance = None
    _lock = threading.Lock()
    _initialized = False
    
    # Static attributes
    _config_dir: Optional[Path] = None
    _config_file: Optional[Path] = None
    _lock_file: Optional[Path] = None
    
    def __new__(cls):
        """Ensure only one instance exists"""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        """Initialize only once"""
        if not TokenManager._initialized:
            with TokenManager._lock:
                if not TokenManager._initialized:
                    self._initialize()
                    TokenManager._initialized = True
    
    @classmethod
    def _initialize(cls):
        """Initialize static configuration"""
        config_dir = str(get_path('REDIACC_CONFIG_DIR') or Path.home() / '.rediacc')
        cls._config_dir = Path(config_dir).expanduser()
        cls._config_file = cls._config_dir / "config.json"
        cls._lock_file = cls._config_dir / ".config.lock"
        cls._ensure_secure_config()
    
    @classmethod
    def _ensure_secure_config(cls):
        """Ensure config directory and file have proper permissions"""
        # Create directory with secure permissions
        cls._config_dir.mkdir(mode=0o700, exist_ok=True)
        
        # Set secure permissions on existing config file
        if cls._config_file.exists():
            try:
                cls._config_file.chmod(0o600)
            except OSError as e:
                logger.warning(f"Could not set secure permissions on config file: {e}")
    
    @classmethod
    def _load_from_config(cls) -> Dict[str, Any]:
        """Load configuration from file with thread safety - NO CACHING"""
        with cls._lock:
            if not cls._config_file.exists():
                return {}
            
            try:
                with open(cls._config_file, 'r') as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError) as e:
                logger.error(f"Failed to load config: {e}")
                return {}
    
    @classmethod
    def _save_config(cls, config: Dict[str, Any]):
        """Save configuration to file with secure permissions and thread safety"""
        with cls._lock:
            cls._config_dir.mkdir(mode=0o700, exist_ok=True)
            
            # Write to temporary file first
            temp_file = cls._config_file.with_suffix('.tmp')
            try:
                with open(temp_file, 'w') as f:
                    json.dump(config, f, indent=2)
                
                # Set secure permissions before moving
                temp_file.chmod(0o600)
                
                # Atomic replace
                temp_file.replace(cls._config_file)
                
            except Exception as e:
                logger.error(f"Failed to save config: {e}")
                if temp_file.exists():
                    temp_file.unlink()
                raise
    
    @classmethod
    def get_token(cls, override_token: Optional[str] = None) -> Optional[str]:
        """
        Get token with clear precedence - ALWAYS READ FROM FILE:
        1. Override token (from command line)
        2. Environment variable (REDIACC_TOKEN)
        3. Config file (always read fresh)
        """
        # Ensure initialization
        if not cls._initialized:
            TokenManager()
        
        # 1. Override token has highest priority
        if override_token:
            if cls.validate_token(override_token):
                return override_token
            else:
                logger.warning("Invalid override token format")
                return None
        
        # 2. Check environment variable
        env_token = os.environ.get('REDIACC_TOKEN')
        if env_token:
            if cls.validate_token(env_token):
                return env_token
            else:
                logger.warning("Invalid token in REDIACC_TOKEN environment variable")
        
        # 3. Always load fresh from config file - NO CACHING
        config = cls._load_from_config()
        token = config.get('token')
        if token and cls.validate_token(token):
            return token
        
        return None
    
    @classmethod
    def set_token(cls, token: str, email: Optional[str] = None, 
                  company: Optional[str] = None, vault_company: Optional[str] = None):
        """Store token and related auth info securely"""
        # Ensure initialization
        if not cls._initialized:
            TokenManager()
            
        if not cls.validate_token(token):
            raise ValueError("Invalid token format")
        
        config = cls._load_from_config()
        
        # Update auth information
        config['token'] = token
        config['token_updated_at'] = datetime.now(timezone.utc).isoformat()
        
        if email:
            config['email'] = email
        if company:
            config['company'] = company
        if vault_company is not None:
            config['vault_company'] = vault_company
        
        cls._save_config(config)
    
    @classmethod
    def clear_token(cls):
        """Clear token and authentication information"""
        # Ensure initialization
        if not cls._initialized:
            TokenManager()
            
        config = cls._load_from_config()
        
        # Remove auth-related fields
        auth_fields = ['token', 'token_updated_at', 'email', 'company', 'vault_company']
        for field in auth_fields:
            config.pop(field, None)
        
        cls._save_config(config)
    
    @classmethod
    def get_auth_info(cls) -> Dict[str, Any]:
        """Get all authentication-related information"""
        # Ensure initialization
        if not cls._initialized:
            TokenManager()
            
        config = cls._load_from_config()
        return {
            'token': cls.mask_token(config.get('token')),
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
    
    @classmethod
    def is_authenticated(cls) -> bool:
        """Check if a valid token is available"""
        return cls.get_token() is not None
    
    @classmethod
    def get_config_value(cls, key: str) -> Any:
        """Get any config value"""
        # Ensure initialization
        if not cls._initialized:
            TokenManager()
            
        config = cls._load_from_config()
        return config.get(key)
    
    @classmethod
    def set_config_value(cls, key: str, value: Any):
        """Set any config value"""
        # Ensure initialization
        if not cls._initialized:
            TokenManager()
            
        config = cls._load_from_config()
        config[key] = value
        cls._save_config(config)


# For backward compatibility - these functions now use the singleton
def get_default_token_manager() -> TokenManager:
    """Get the default token manager instance"""
    return TokenManager()