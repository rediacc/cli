#!/usr/bin/env python3
"""
Configuration loader for Rediacc CLI
Loads configuration from .env files and environment variables
"""
import os
import sys
import json
from pathlib import Path
from typing import Dict, Optional

class ConfigError(Exception):
    """Raised when required configuration is missing"""
    pass

class Config:
    """Configuration manager for Rediacc CLI"""
    
    # Required configuration keys
    REQUIRED_KEYS = {
        'SYSTEM_HTTP_PORT': 'Port for the Rediacc API server',
        'REDIACC_API_URL': 'Full URL to the Rediacc API endpoint',
    }
    
    # Optional configuration keys with descriptions
    OPTIONAL_KEYS = {
        'REDIACC_DATASTORE_PATH': 'Path to the datastore directory',
        'REDIACC_INTERIM_FOLDER': 'Name of the interim folder',
        'REDIACC_MOUNTS_FOLDER': 'Name of the mounts folder',
        'REDIACC_REPOS_FOLDER': 'Name of the repos folder',
        'REDIACC_LINUX_USER': 'Linux user for Docker containers',
        'REDIACC_LINUX_GROUP': 'Linux group for Docker containers',
        'REDIACC_USER_UID': 'UID for the Linux user',
        'REDIACC_USER_GID': 'GID for the Linux group',
        'REDIACC_CONFIG_DIR': 'Directory for CLI configuration files',
        'REDIACC_TEST_ACTIVATION_CODE': 'Test activation code for development',
        'REDIACC_DEFAULT_THEME': 'Default theme for GUI (dark/light)',
        'REDIACC_TEMP_DIR': 'Temporary directory (Windows)',
        'REDIACC_MSYS2_ROOT': 'MSYS2 installation directory (Windows)',
        'REDIACC_PYTHON_PATH': 'Python interpreter path',
    }
    
    def __init__(self):
        self._config = {}
        self._loaded = False
    
    def load(self, env_file: Optional[str] = None):
        """Load configuration from environment and .env files"""
        if self._loaded:
            return
        
        # Load from .env file if it exists
        self._load_env_file(env_file)
        
        # Load from environment variables (overrides .env)
        self._load_from_environment()
        
        # Validate required configuration
        self._validate()
        
        self._loaded = True
    
    def _find_env_file(self) -> Optional[Path]:
        """Find .env file in current, parent directories, or home"""
        # Check current directory
        current = Path.cwd()
        if (current / '.env').exists():
            return current / '.env'
        
        # Check parent directories up to the monorepo root
        for parent in current.parents:
            env_path = parent / '.env'
            if env_path.exists():
                return env_path
            # Stop at monorepo root (has a 'cli' directory)
            if (parent / 'cli').is_dir() and (parent / 'middleware').is_dir():
                break
        
        # Check home directory
        home_env = Path.home() / '.rediacc' / '.env'
        if home_env.exists():
            return home_env
        
        return None
    
    def _load_env_file(self, env_file: Optional[str] = None):
        """Load configuration from .env file"""
        if env_file:
            env_path = Path(env_file)
        else:
            env_path = self._find_env_file()
        
        if not env_path or not env_path.exists():
            return
        
        try:
            with open(env_path, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#'):
                        if '=' in line:
                            key, value = line.split('=', 1)
                            key = key.strip()
                            value = value.strip().strip('"\'')
                            self._config[key] = value
        except Exception as e:
            print(f"Warning: Failed to load .env file: {e}", file=sys.stderr)
    
    def _load_from_environment(self):
        """Load configuration from environment variables"""
        all_keys = list(self.REQUIRED_KEYS.keys()) + list(self.OPTIONAL_KEYS.keys())
        for key in all_keys:
            if key in os.environ:
                self._config[key] = os.environ[key]
        
        # Try to load API URL from shared config file if not set
        if 'REDIACC_API_URL' not in self._config:
            api_url = self._load_api_url_from_shared_config()
            if api_url:
                self._config['REDIACC_API_URL'] = api_url
    
    def _load_api_url_from_shared_config(self) -> Optional[str]:
        """Load API URL from shared config file (same as desktop app)"""
        try:
            config_path = Path.home() / '.rediacc' / 'config.json'
            if config_path.exists():
                with open(config_path, 'r') as f:
                    config = json.load(f)
                    # Support both snake_case and camelCase
                    return config.get('api_url') or config.get('apiUrl')
        except Exception:
            # Silently ignore errors
            pass
        return None
    
    def _validate(self):
        """Validate that all required configuration is present"""
        missing = []
        for key, description in self.REQUIRED_KEYS.items():
            if key not in self._config:
                missing.append(f"  {key}: {description}")
        
        if missing:
            msg = "Missing required configuration:\n" + "\n".join(missing)
            msg += "\n\nPlease set these environment variables or create a .env file."
            msg += "\nSee .env.example for a template."
            raise ConfigError(msg)
    
    def get(self, key: str, default: Optional[str] = None) -> Optional[str]:
        """Get a configuration value"""
        if not self._loaded:
            self.load()
        return self._config.get(key, default)
    
    def get_required(self, key: str) -> str:
        """Get a required configuration value"""
        value = self.get(key)
        if value is None:
            raise ConfigError(f"Required configuration '{key}' is not set")
        return value
    
    def get_int(self, key: str, default: Optional[int] = None) -> Optional[int]:
        """Get a configuration value as integer"""
        value = self.get(key)
        if value is None:
            return default
        try:
            return int(value)
        except ValueError:
            raise ConfigError(f"Configuration '{key}' must be an integer, got: {value}")
    
    def get_bool(self, key: str, default: bool = False) -> bool:
        """Get a configuration value as boolean"""
        value = self.get(key)
        if value is None:
            return default
        return value.lower() in ('true', '1', 'yes', 'on')
    
    def get_path(self, key: str, default: Optional[str] = None) -> Optional[Path]:
        """Get a configuration value as Path, expanding ~ and variables"""
        value = self.get(key, default)
        if value is None:
            return None
        # Expand user home directory
        value = os.path.expanduser(value)
        # Expand environment variables
        value = os.path.expandvars(value)
        return Path(value)
    
    def print_config(self):
        """Print current configuration (for debugging)"""
        if not self._loaded:
            self.load()
        
        print("Current configuration:")
        print("-" * 40)
        
        # Print required configs
        print("Required:")
        for key in self.REQUIRED_KEYS:
            value = self._config.get(key, '<NOT SET>')
            print(f"  {key}={value}")
        
        # Print optional configs that are set
        print("\nOptional (set):")
        for key in self.OPTIONAL_KEYS:
            if key in self._config:
                print(f"  {key}={self._config[key]}")
        
        # Print optional configs that are not set
        unset = [k for k in self.OPTIONAL_KEYS if k not in self._config]
        if unset:
            print("\nOptional (not set):")
            for key in unset:
                print(f"  {key}")

# Global config instance
_config = Config()

def get_config() -> Config:
    """Get the global configuration instance"""
    return _config

def load_config(env_file: Optional[str] = None):
    """Load configuration (safe to call multiple times)"""
    _config.load(env_file)

# Convenience functions
def get(key: str, default: Optional[str] = None) -> Optional[str]:
    """Get a configuration value"""
    return _config.get(key, default)

def get_required(key: str) -> str:
    """Get a required configuration value"""
    return _config.get_required(key)

def get_int(key: str, default: Optional[int] = None) -> Optional[int]:
    """Get a configuration value as integer"""
    return _config.get_int(key, default)

def get_bool(key: str, default: bool = False) -> bool:
    """Get a configuration value as boolean"""
    return _config.get_bool(key, default)

def get_path(key: str, default: Optional[str] = None) -> Optional[Path]:
    """Get a configuration value as Path"""
    return _config.get_path(key, default)