#!/usr/bin/env python3
"""
Token Manager for Rediacc CLI
Handles secure token storage and retrieval with proper permissions
Uses singleton pattern to ensure consistent token management across the application
"""

import os
import json
import re
import time
import threading
import base64
from pathlib import Path
from typing import Optional, Dict, Any
from datetime import datetime, timezone
import logging

# Import configuration loader
from config_loader import get_path

# Try to import cryptography library for vault operations
try:
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
    from cryptography.hazmat.backends import default_backend
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    CRYPTO_AVAILABLE = True
except ImportError:
    CRYPTO_AVAILABLE = False

logger = logging.getLogger(__name__)


def is_encrypted(value: str) -> bool:
    """Check if a value appears to be encrypted
    Encrypted values are base64 encoded and typically longer than the original
    """
    if not value or len(value) < 20:
        return False
    
    try:
        # Try to decode as base64
        decoded = base64.b64decode(value)
        # Encrypted values should be at least 32 bytes (salt + iv + minimal ciphertext)
        return len(decoded) >= 32
    except:
        return False


def decrypt_string(encrypted: str, password: str) -> str:
    """Decrypt a string encrypted with encrypt_string
    Expects base64 encoded string: salt || iv || ciphertext || authTag
    """
    if not CRYPTO_AVAILABLE:
        raise RuntimeError("Cryptography library not available")
    
    # Decode from base64
    combined = base64.b64decode(encrypted)
    
    # Extract components (16 bytes salt, 12 bytes IV, rest is ciphertext + 16 bytes auth tag)
    salt = combined[:16]
    iv = combined[16:28]
    ciphertext_and_tag = combined[28:]
    
    # Derive key from password and salt
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,  # 256 bits
        salt=salt,
        iterations=100000,
        backend=default_backend()
    )
    key = kdf.derive(password.encode('utf-8'))
    
    # Decrypt using AES-GCM
    aesgcm = AESGCM(key)
    try:
        plaintext = aesgcm.decrypt(iv, ciphertext_and_tag, None)
        return plaintext.decode('utf-8')
    except Exception as e:
        raise ValueError(f"Decryption failed: {e}")


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
                    # Session state variables (not persisted)
                    self._master_password = None
                    self._vault_company = None
                    self._company_name = None
                    self._vault_info_fetched = False
                    self._token_overridden = False
                    TokenManager._initialized = True
    
    @classmethod
    def _initialize(cls):
        """Initialize static configuration"""
        # First check if REDIACC_CONFIG_DIR is explicitly set
        explicit_config_dir = get_path('REDIACC_CONFIG_DIR')
        
        if explicit_config_dir:
            # Use explicitly configured directory
            config_dir = str(explicit_config_dir)
        else:
            # Use local config directory in CLI folder
            # Find the CLI root directory (parent of src/modules)
            current_file = Path(__file__).resolve()
            cli_root = current_file.parent.parent.parent  # src/modules -> src -> cli
            config_dir = cli_root / '.rediacc'
            
            # Handle MSYS2 path resolution - try both Windows and MSYS2 formats
            if 'MSYSTEM' in os.environ:
                config_dir_str = str(config_dir)
                
                # First try the Windows path as-is (might work in some MSYS2 setups)
                if config_dir.exists():
                    logger.debug(f"MSYS2: Using Windows path: {config_dir}")
                else:
                    # Try MSYS2 format conversion
                    if config_dir_str.startswith('C:') or config_dir_str.startswith('c:'):
                        drive = config_dir_str[0].lower()
                        rest = config_dir_str[2:].replace('\\', '/')
                        msys2_path = f'/{drive}{rest}'
                        msys2_config_dir = Path(msys2_path)
                        
                        if msys2_config_dir.exists():
                            config_dir = msys2_config_dir
                            logger.debug(f"MSYS2: Using converted path: {msys2_path}")
                        else:
                            # Try WSL format as fallback
                            wsl_path = f'/mnt/{drive}{rest}'
                            wsl_config_dir = Path(wsl_path)
                            if wsl_config_dir.exists():
                                config_dir = wsl_config_dir
                                logger.debug(f"MSYS2: Using WSL fallback path: {wsl_path}")
                            else:
                                logger.debug(f"MSYS2: No valid path found, using original: {config_dir}")
                    else:
                        logger.debug(f"MSYS2: Using original path: {config_dir}")
            
            # Debug: ensure we found the right path
            logger.debug(f"TokenManager using local config: {config_dir}")
            logger.debug(f"CLI root detected as: {cli_root}")
            logger.debug(f"Current file: {current_file}")
            logger.debug(f"MSYSTEM env: {os.environ.get('MSYSTEM', 'Not set')}")
        
        cls._config_dir = Path(config_dir)
        cls._config_file = cls._config_dir / "config.json"
        cls._lock_file = cls._config_dir / ".config.lock"
        cls._ensure_secure_config()
    
    @classmethod
    def _ensure_secure_config(cls):
        """Ensure config directory and file have proper permissions"""
        # Create directory with secure permissions (Unix systems only)
        try:
            cls._config_dir.mkdir(mode=0o700, exist_ok=True)
        except OSError:
            # Fallback for Windows or systems that don't support mode
            cls._config_dir.mkdir(exist_ok=True)
        
        # Set secure permissions on existing config file (Unix systems only)
        if cls._config_file.exists():
            try:
                cls._config_file.chmod(0o600)
            except (OSError, NotImplementedError) as e:
                # Windows or other systems may not support chmod
                logger.debug(f"Could not set secure permissions on config file: {e}")
    
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
        import time
        import platform
        
        with cls._lock:
            cls._config_dir.mkdir(mode=0o700, exist_ok=True)
            
            # On Windows/MSYS2, use more robust file handling
            is_windows = platform.system() == 'Windows' or 'MSYSTEM' in os.environ
            max_retries = 3 if is_windows else 1
            
            for attempt in range(max_retries):
                temp_file = cls._config_file.with_suffix(f'.tmp.{attempt}.{int(time.time())}')
                try:
                    # Write to unique temporary file
                    with open(temp_file, 'w') as f:
                        json.dump(config, f, indent=2)
                    
                    # Set secure permissions if not Windows
                    if not is_windows:
                        temp_file.chmod(0o600)
                    
                    # Try to replace the config file
                    if is_windows and cls._config_file.exists():
                        # On Windows, remove target first if it exists
                        try:
                            cls._config_file.unlink()
                        except OSError:
                            pass  # File might not exist or be locked
                    
                    # Move temp file to final location
                    if is_windows:
                        # Use shutil.move for better Windows compatibility
                        import shutil
                        shutil.move(str(temp_file), str(cls._config_file))
                    else:
                        temp_file.replace(cls._config_file)
                    
                    # Success - set final permissions
                    if not is_windows:
                        cls._config_file.chmod(0o600)
                    
                    return  # Success
                    
                except OSError as e:
                    logger.warning(f"Config save attempt {attempt + 1} failed: {e}")
                    # Clean up temp file
                    if temp_file.exists():
                        try:
                            temp_file.unlink()
                        except OSError:
                            pass
                    
                    if attempt < max_retries - 1:
                        # Wait before retry
                        time.sleep(0.1 * (attempt + 1))
                    else:
                        logger.error(f"Failed to save config after {max_retries} attempts: {e}")
                        raise
                except Exception as e:
                    logger.error(f"Failed to save config: {e}")
                    if temp_file.exists():
                        try:
                            temp_file.unlink()
                        except OSError:
                            pass
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
        try:
            config = cls._load_from_config()
            token = config.get('token')
            if token and cls.validate_token(token):
                return token
            else:
                logger.debug(f"No valid token found in config file")
                logger.debug(f"Config contains: {list(config.keys())}")
                if token:
                    logger.debug(f"Token validation failed for token: {token[:8]}...")
        except Exception as e:
            logger.error(f"Error loading config: {e}")
            import traceback
            traceback.print_exc()
        
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
    
    @classmethod
    def set_api_url(cls, api_url: str):
        """Set API URL in config (compatible with desktop app)"""
        # Ensure initialization
        if not cls._initialized:
            TokenManager()
            
        config = cls._load_from_config()
        # Save in snake_case for CLI compatibility
        config['api_url'] = api_url
        cls._save_config(config)
    
    @classmethod
    def get_api_url(cls) -> Optional[str]:
        """Get API URL from config"""
        # Ensure initialization
        if not cls._initialized:
            TokenManager()
            
        config = cls._load_from_config()
        # Support both snake_case and camelCase
        return config.get('api_url') or config.get('apiUrl')
    
    # Master Password Management (in-memory only)
    def set_master_password(self, password: str):
        """Set master password in memory only"""
        self._master_password = password
    
    def get_master_password(self) -> Optional[str]:
        """Get master password from memory"""
        return self._master_password
    
    def clear_master_password(self):
        """Clear master password from memory"""
        self._master_password = None
    
    # Vault Management
    def has_vault_encryption(self) -> bool:
        """Check if company has vault encryption enabled"""
        # Try to get vault company from memory first, then config
        vault_company = self._vault_company or self.get_config_value('vault_company')
        return vault_company and is_encrypted(vault_company)
    
    def get_vault_company(self) -> Optional[str]:
        """Get vault company value"""
        return self._vault_company or self.get_config_value('vault_company')
    
    def validate_master_password(self, password: str) -> bool:
        """Validate master password against VaultCompany"""
        vault_company = self.get_vault_company()
        
        if not vault_company:
            return False
        
        if not is_encrypted(vault_company):
            return True  # No encryption required
        
        try:
            # Try to decrypt the vault content
            decrypted = decrypt_string(vault_company, password)
            # If decryption succeeds, the password is valid
            # The decrypted content should be valid JSON (even if it's just {})
            json.loads(decrypted)
            return True
        except:
            # Decryption failed or result is not valid JSON - wrong password
            return False
    
    # Session State Management
    def needs_vault_info_fetch(self) -> bool:
        """Check if we need to fetch vault info"""
        # Need to fetch if authenticated but don't have vault info
        return self.is_authenticated() and not self._vault_info_fetched and not self.get_vault_company()
    
    def mark_vault_info_fetched(self):
        """Mark that we've attempted to fetch vault info this session"""
        self._vault_info_fetched = True
    
    def load_vault_info_from_config(self):
        """Load vault info from saved config"""
        config = self._load_from_config()
        if 'vault_company' in config:
            self._vault_company = config['vault_company']
        if 'company' in config:
            self._company_name = config['company']
    
    def set_token_overridden(self, overridden: bool = True):
        """Mark that token was overridden via command line"""
        self._token_overridden = overridden
    
    def is_token_overridden(self) -> bool:
        """Check if token was overridden via command line"""
        return self._token_overridden
    
    # Enhanced set_token to update internal state
    @classmethod
    def set_token_with_auth(cls, token: str, email: Optional[str] = None, 
                           company: Optional[str] = None, vault_company: Optional[str] = None):
        """Set token and authentication information (ConfigManager compatibility)"""
        instance = cls()
        cls.set_token(token, email, company, vault_company)
        
        # Update instance state
        if company:
            instance._company_name = company
        if vault_company:
            instance._vault_company = vault_company
    
    # Enhanced clear method
    @classmethod 
    def clear_auth(cls):
        """Clear all authentication information (ConfigManager compatibility)"""
        instance = cls()
        cls.clear_token()
        
        # Clear instance state
        instance._master_password = None
        instance._vault_company = None
        instance._company_name = None
        instance._vault_info_fetched = False
    
    # ConfigManager compatibility property
    @property
    def config(self) -> Dict[str, Any]:
        """Get current configuration dict (ConfigManager compatibility)"""
        return self._load_from_config()


# For backward compatibility - these functions now use the singleton
def get_default_token_manager() -> TokenManager:
    """Get the default token manager instance"""
    return TokenManager()