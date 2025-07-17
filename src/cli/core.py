#!/usr/bin/env python3
"""
Rediacc CLI Core Utilities - Consolidated module containing all core functionality
This module combines all the utility modules that were previously separate files.
"""

import os
import sys
import json
import time
import errno
import threading
import subprocess
import tempfile
import platform
import base64
import re
import logging
from pathlib import Path
from typing import Dict, Optional, Any, List, Tuple
from datetime import datetime, timedelta, timezone
from contextlib import contextmanager

# ============================================================================
# CONFIG PATH MODULE (from config_path.py)
# ============================================================================

def get_cli_root() -> Path:
    """
    Get the CLI root directory (where src, scripts, tests, etc. are located)
    
    Returns:
        Path: The absolute path to the CLI root directory
    """
    # This module is in cli/src/cli, so go up 2 levels
    current_file = Path(__file__).resolve()
    cli_root = current_file.parent.parent.parent  # cli -> src -> cli
    return cli_root


def get_config_dir() -> Path:
    """
    Get the configuration directory path (.rediacc)
    
    Checks in order:
    1. REDIACC_CONFIG_DIR environment variable (for Docker containers)
    2. Local CLI directory (.rediacc in the CLI root)
    
    The directory is created if it doesn't exist.
    
    Returns:
        Path: The absolute path to the configuration directory
    """
    # First check if REDIACC_CONFIG_DIR is explicitly set
    config_dir_env = os.environ.get('REDIACC_CONFIG_DIR')
    
    if config_dir_env:
        # Use explicitly configured directory (e.g., in Docker)
        config_dir = Path(config_dir_env).resolve()
    else:
        # Use local config directory in CLI folder
        cli_root = get_cli_root()
        config_dir = cli_root / '.config'
    
    # Create directory if it doesn't exist
    config_dir.mkdir(exist_ok=True)
    
    return config_dir


def get_config_file(filename: str) -> Path:
    """
    Get the full path to a configuration file
    
    Args:
        filename: The name of the config file (e.g., 'config.json', 'language_preference.json')
    
    Returns:
        Path: The absolute path to the configuration file
    """
    config_dir = get_config_dir()
    return config_dir / filename


# Convenience functions for common config files
def get_main_config_file() -> Path:
    """Get the path to the main config.json file"""
    return get_config_file('config.json')


def get_language_config_file() -> Path:
    """Get the path to the language preference file"""
    return get_config_file('language_preference.json')


def get_plugin_connections_file() -> Path:
    """Get the path to the plugin connections file"""
    return get_config_file('plugin-connections.json')


def get_terminal_cache_file() -> Path:
    """Get the path to the terminal cache file"""
    return get_config_file('terminal_cache.json')


def get_terminal_detector_cache_file() -> Path:
    """Get the path to the terminal detector cache file"""
    return get_config_file('terminal_detector_cache.json')


def get_api_lock_file() -> Path:
    """Get the path to the API mutex lock file"""
    return get_config_file('api_call.lock')


def get_token_lock_file() -> Path:
    """Get the path to the token manager lock file"""
    return get_config_file('.config.lock')


def get_ssh_control_dir() -> Path:
    """Get the SSH control directory for plugin connections"""
    ssh_dir = get_config_dir() / 'ssh-control'
    ssh_dir.mkdir(exist_ok=True)
    return ssh_dir


# ============================================================================
# LOGGING CONFIG MODULE (from logging_config.py)
# ============================================================================

def setup_logging(verbose: bool = False, log_file: Optional[str] = None) -> None:
    """
    Configure logging for the CLI application.
    
    Args:
        verbose: Enable verbose (DEBUG) logging
        log_file: Optional file path to write logs to
    """
    log_level = logging.DEBUG if verbose else logging.INFO
    
    # Define log format
    if verbose:
        log_format = '%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s'
    else:
        log_format = '%(levelname)s: %(message)s'
    
    # Configure handlers
    handlers = []
    
    # Console handler (stderr to avoid contaminating stdout)
    console_handler = logging.StreamHandler(sys.stderr)
    console_handler.setFormatter(logging.Formatter(log_format))
    handlers.append(console_handler)
    
    # File handler if specified
    if log_file:
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s'
        ))
        handlers.append(file_handler)
    
    # Configure root logger
    logging.basicConfig(
        level=log_level,
        handlers=handlers,
        force=True  # Force reconfiguration if already configured
    )
    
    # Set specific loggers that might be too verbose
    if not verbose:
        # Suppress verbose output from third-party libraries
        logging.getLogger('urllib3').setLevel(logging.WARNING)
        logging.getLogger('requests').setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance for the specified module.
    
    Args:
        name: Name of the logger (typically __name__)
        
    Returns:
        Logger instance
    """
    return logging.getLogger(name)


def is_verbose_enabled() -> bool:
    """
    Check if verbose logging is enabled.
    
    Returns:
        True if root logger is set to DEBUG level
    """
    return logging.getLogger().isEnabledFor(logging.DEBUG)


# ============================================================================
# CONFIG LOADER MODULE (from config_loader.py)
# ============================================================================

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
        self.logger = get_logger(__name__)
    
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
        
        # Check local CLI directory
        config_dir = get_config_dir()
        local_env = config_dir / '.env'
        if local_env.exists():
            return local_env
        
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
            self.logger.warning(f"Failed to load .env file: {e}")
    
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
            # Use config directory
            config_dir = get_config_dir()
            config_path = config_dir / 'config.json'
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
        
        self.logger.debug("Current configuration:")
        self.logger.debug("-" * 40)
        
        # Print required configs
        self.logger.debug("Required:")
        for key in self.REQUIRED_KEYS:
            value = self._config.get(key, '<NOT SET>')
            self.logger.debug(f"  {key}={value}")
        
        # Print optional configs that are set
        self.logger.debug("\nOptional (set):")
        for key in self.OPTIONAL_KEYS:
            if key in self._config:
                self.logger.debug(f"  {key}={self._config[key]}")
        
        # Print optional configs that are not set
        unset = [k for k in self.OPTIONAL_KEYS if k not in self._config]
        if unset:
            self.logger.debug("\nOptional (not set):")
            for key in unset:
                self.logger.debug(f"  {key}")

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


# ============================================================================
# API MUTEX MODULE (from api_mutex.py)
# ============================================================================

# Try to import fcntl (Unix/Linux/MSYS2)
try:
    import fcntl
    HAS_FCNTL = True
except ImportError:
    HAS_FCNTL = False

# Try to import msvcrt (Windows)
try:
    import msvcrt
    HAS_MSVCRT = True
except ImportError:
    HAS_MSVCRT = False

class APIMutex:
    """Simple file-based mutex for API calls"""
    
    def __init__(self, lock_file: Path = None):
        if lock_file is None:
            # Use centralized lock file path
            lock_file = get_api_lock_file()
        
        self.lock_file = str(lock_file)
    
    @contextmanager
    def acquire(self, timeout: float = 30.0):
        """Acquire exclusive lock for API call"""
        start_time = time.time()
        lock_fd = None
        
        try:
            # Open or create lock file
            lock_fd = os.open(self.lock_file, os.O_CREAT | os.O_WRONLY)
            
            # Try to acquire exclusive lock with timeout
            while True:
                try:
                    fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    break
                except IOError as e:
                    if e.errno != errno.EAGAIN:
                        raise
                    
                    # Check timeout
                    if time.time() - start_time > timeout:
                        raise TimeoutError(f"Could not acquire API lock after {timeout}s")
                    
                    # Brief sleep before retry
                    time.sleep(0.05)
            
            # Lock acquired, yield control
            yield
            
        finally:
            # Release lock and close file
            if lock_fd is not None:
                try:
                    fcntl.flock(lock_fd, fcntl.LOCK_UN)
                except:
                    pass
                try:
                    os.close(lock_fd)
                except:
                    pass

# For Windows compatibility when fcntl is not available
if not HAS_FCNTL and HAS_MSVCRT:
    class APIMutexWindows:
        """Windows-compatible mutex using msvcrt"""
        
        def __init__(self, lock_file: Path = None):
            if lock_file is None:
                # Use centralized lock file path
                lock_file = get_api_lock_file()
            
            self.lock_file = str(lock_file)
        
        @contextmanager
        def acquire(self, timeout: float = 30.0):
            """Acquire exclusive lock for API call on Windows"""
            start_time = time.time()
            file_handle = None
            
            try:
                # Ensure directory exists
                os.makedirs(os.path.dirname(self.lock_file), exist_ok=True)
                
                # Try to open/create the lock file
                while True:
                    try:
                        # Open file in binary write mode
                        file_handle = open(self.lock_file, 'wb')
                        
                        # Try to acquire exclusive lock
                        msvcrt.locking(file_handle.fileno(), msvcrt.LK_NBLCK, 1)
                        break
                    except IOError:
                        # Lock is held by another process
                        if file_handle:
                            file_handle.close()
                            file_handle = None
                        
                        # Check timeout
                        if time.time() - start_time > timeout:
                            raise TimeoutError(f"Could not acquire API lock after {timeout}s")
                        
                        # Brief sleep before retry
                        time.sleep(0.05)
                
                # Lock acquired, yield control
                yield
                
            finally:
                # Release lock and close file
                if file_handle:
                    try:
                        # Unlock the file
                        msvcrt.locking(file_handle.fileno(), msvcrt.LK_UNLCK, 1)
                    except:
                        pass
                    try:
                        file_handle.close()
                    except:
                        pass

# Create the appropriate mutex instance based on platform capabilities
if HAS_FCNTL:
    # Use fcntl-based locking (Unix/Linux/MSYS2 with POSIX support)
    api_mutex = APIMutex()
elif HAS_MSVCRT:
    # Use msvcrt-based locking (Native Windows)
    api_mutex = APIMutexWindows()
else:
    # Fallback: No locking available
    class APIMutexNoOp:
        """No-op mutex when no locking mechanism is available"""
        def __init__(self, lock_file: Path = None):
            pass
        
        @contextmanager
        def acquire(self, timeout: float = 30.0):
            yield
    
    api_mutex = APIMutexNoOp()
    print("Warning: No file locking mechanism available", file=sys.stderr)


# ============================================================================
# TOKEN MANAGER MODULE (from token_manager.py)
# ============================================================================

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

# Get logger
logger = get_logger(__name__)


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
        # Get config directory from centralized function
        # This already checks REDIACC_CONFIG_DIR environment variable
        config_dir = get_config_dir()
        
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
        
        cls._config_dir = Path(config_dir)
        cls._config_file = get_main_config_file()
        cls._lock_file = get_token_lock_file()
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


# ============================================================================
# I18N MODULE (from i18n.py)
# ============================================================================

class I18n:
    """Internationalization manager for GUI application"""
    
    def __init__(self):
        # Load configuration from JSON file
        self._load_config()
        self.current_language = self.DEFAULT_LANGUAGE
        self._observers = []
    
    def _load_config(self):
        """Load languages and translations from JSON configuration file"""
        config_path = Path(__file__).parent.parent / 'config' / 'rediacc-gui.json'
        
        if not config_path.exists():
            raise FileNotFoundError(f"Translation configuration file not found: {config_path}")
        
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
            
            self.LANGUAGES = config.get('languages', {})
            self.DEFAULT_LANGUAGE = config.get('default_language', 'en')
            self.translations = config.get('translations', {})
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in translation configuration: {e}")
        except Exception as e:
            raise RuntimeError(f"Failed to load translation configuration: {e}")
    
    
    def get_language_config_path(self) -> Path:
        """Get the path to the language configuration file"""
        # Use centralized config directory
        config_dir = get_config_dir()
        return config_dir / 'language_preference.json'
    
    def load_language_preference(self) -> str:
        """Load the saved language preference"""
        config_path = self.get_language_config_path()
        if config_path.exists():
            try:
                with open(config_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    lang = data.get('language', self.DEFAULT_LANGUAGE)
                    if lang in self.LANGUAGES:
                        return lang
            except:
                pass
        return self.DEFAULT_LANGUAGE
    
    def save_language_preference(self, language: str):
        """Save the language preference"""
        if language not in self.LANGUAGES:
            return
        
        config_path = self.get_language_config_path()
        try:
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump({'language': language}, f, ensure_ascii=False, indent=2)
        except:
            pass
    
    def set_language(self, language: str):
        """Set the current language"""
        if language in self.LANGUAGES:
            self.current_language = language
            self.save_language_preference(language)
            self._notify_observers()
    
    def get(self, key: str, fallback: str = None, **kwargs) -> str:
        """Get a translated string for the current language
        
        Args:
            key: The translation key
            fallback: Optional fallback value if key not found
            **kwargs: Format arguments for the translation string
        """
        translation = self.translations.get(self.current_language, {}).get(key)
        if not translation:
            # Fallback to English
            translation = self.translations.get('en', {}).get(key)
            if not translation:
                # Use provided fallback or key as last resort
                translation = fallback if fallback is not None else key
        
        # Format with provided arguments
        if kwargs:
            try:
                translation = translation.format(**kwargs)
            except:
                pass
        
        return translation
    
    def register_observer(self, callback):
        """Register a callback to be called when language changes"""
        self._observers.append(callback)
    
    def unregister_observer(self, callback):
        """Unregister a language change callback"""
        if callback in self._observers:
            self._observers.remove(callback)
    
    def _notify_observers(self):
        """Notify all observers of language change"""
        for callback in self._observers:
            try:
                callback()
            except:
                pass
    
    def get_language_name(self, code: str) -> str:
        """Get the display name for a language code"""
        return self.LANGUAGES.get(code, code)
    
    def get_language_codes(self) -> list:
        """Get list of available language codes"""
        return list(self.LANGUAGES.keys())
    
    def get_language_names(self) -> list:
        """Get list of language display names"""
        return list(self.LANGUAGES.values())


# Singleton instance
i18n = I18n()


# ============================================================================
# SUBPROCESS RUNNER MODULE (from subprocess_runner.py)
# ============================================================================

class SubprocessRunner:
    """Runs CLI commands and captures output"""
    
    def __init__(self):
        self.logger = get_logger(__name__)
        # Store original Windows paths
        self.cli_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.cli_path = os.path.join(self.cli_dir, 'cli', 'rediacc-cli.py')
        self.sync_path = os.path.join(self.cli_dir, 'cli', 'rediacc-cli-sync.py')
        self.term_path = os.path.join(self.cli_dir, 'cli', 'rediacc-cli-term.py')
        self.plugin_path = os.path.join(self.cli_dir, 'cli', 'rediacc-cli-plugin.py')
        self.wrapper_path = os.path.join(os.path.dirname(self.cli_dir), 'rediacc')
        
        # Check for MSYS2 on Windows for better compatibility
        self.msys2_path = None
        self.use_msys2_python = False
        if platform.system().lower() == 'windows':
            self.msys2_path = self._find_msys2_installation()
            
        self.python_cmd = self._find_python()
        
        # If using MSYS2 Python, convert paths to MSYS2 format
        if self.use_msys2_python:
            self.cli_dir_msys2 = self._windows_to_msys2_path(self.cli_dir)
            self.cli_path_msys2 = self._windows_to_msys2_path(self.cli_path)
            self.sync_path_msys2 = self._windows_to_msys2_path(self.sync_path)
            self.term_path_msys2 = self._windows_to_msys2_path(self.term_path)
            self.plugin_path_msys2 = self._windows_to_msys2_path(self.plugin_path)
        else:
            # Use original paths
            self.cli_dir_msys2 = self.cli_dir
            self.cli_path_msys2 = self.cli_path
            self.sync_path_msys2 = self.sync_path
            self.term_path_msys2 = self.term_path
            self.plugin_path_msys2 = self.plugin_path
    
    def _find_msys2_installation(self):
        """Find MSYS2 installation path on Windows"""
        msys2_paths = [
            'C:\\msys64',
            'C:\\msys2',
            os.path.expanduser('~\\msys64'),
            os.path.expanduser('~\\msys2'),
        ]
        
        # Check MSYS2_ROOT environment variable
        msys2_root = os.environ.get('MSYS2_ROOT')
        if msys2_root:
            msys2_paths.insert(0, msys2_root)
        
        for path in msys2_paths:
            if os.path.exists(path):
                return path
        return None

    def _windows_to_msys2_path(self, windows_path):
        """Convert Windows path to MSYS2 format"""
        if not windows_path:
            return windows_path
            
        # Convert C:\path\to\file to /c/path/to/file
        if len(windows_path) >= 2 and windows_path[1] == ':':
            drive = windows_path[0].lower()
            rest = windows_path[2:].replace('\\', '/')
            return f'/{drive}{rest}'
        return windows_path.replace('\\', '/')

    def _find_python(self) -> str:
        """Find the correct Python command to use"""
        self.logger.debug("Finding Python command...")
        self.logger.debug(f"MSYS2 path: {self.msys2_path}")
        
        # On Windows with MSYS2, prefer MSYS2 python3
        if self.msys2_path:
            msys2_python = os.path.join(self.msys2_path, 'usr', 'bin', 'python3.exe')
            self.logger.debug(f"Checking MSYS2 Python: {msys2_python}")
            if os.path.exists(msys2_python):
                self.logger.debug(f"Using MSYS2 Python: {msys2_python}")
                self.use_msys2_python = True
                return msys2_python
            else:
                self.logger.debug("MSYS2 Python not found")
        
        # Try different Python commands in order of preference
        python_commands = ['python3', 'python', 'py']
        self.logger.debug(f"Trying Python commands: {python_commands}")
        
        for cmd in python_commands:
            import shutil
            self.logger.debug(f"Testing command: {cmd}")
            if shutil.which(cmd):
                try:
                    # Test if it actually works and is Python 3+
                    result = subprocess.run([cmd, '--version'], 
                                          capture_output=True, text=True, timeout=5)
                    self.logger.debug(f"{cmd} version check: returncode={result.returncode}, stdout='{result.stdout.strip()}'")
                    if result.returncode == 0 and 'Python 3' in result.stdout:
                        self.logger.debug(f"Using Python command: {cmd}")
                        return cmd
                except Exception as e:
                    self.logger.debug(f"Error testing {cmd}: {e}")
                    continue
            else:
                self.logger.debug(f"{cmd} not found in PATH")
        
        # Fallback to python3 if nothing found (will fail gracefully)
        self.logger.debug("No suitable Python found, falling back to 'python3'")
        return 'python3'
    
    def run_command(self, args: List[str], timeout: Optional[int] = None) -> Dict[str, Any]:
        """Run a command and return output"""
        try:
            # Set up environment for MSYS2 if available
            env = os.environ.copy()
            if self.msys2_path and platform.system().lower() == 'windows':
                # Add MSYS2 paths to environment
                msys2_bin = os.path.join(self.msys2_path, 'usr', 'bin')
                mingw64_bin = os.path.join(self.msys2_path, 'mingw64', 'bin')
                if 'PATH' in env:
                    env['PATH'] = f"{msys2_bin};{mingw64_bin};{env['PATH']}"
                else:
                    env['PATH'] = f"{msys2_bin};{mingw64_bin}"
            
            if args[0] == 'sync':
                # Don't add token - let sync tool read from TokenManager
                sync_args = args[1:]
                cmd = [self.python_cmd, self.sync_path_msys2] + sync_args
                self.logger.debug(f"Sync command: {cmd}")
            elif args[0] == 'term':
                # Don't add token for term command - let it read from config
                # to avoid token rotation issues between API calls
                term_args = args[1:]
                cmd = [self.python_cmd, self.term_path_msys2] + term_args
                self.logger.debug(f"Term command: {cmd}")
            elif args[0] == 'plugin':
                # Don't add token - let plugin tool read from TokenManager
                plugin_args = args[1:]
                cmd = [self.python_cmd, self.plugin_path_msys2] + plugin_args
                self.logger.debug(f"Plugin command: {cmd}")
            else:
                cmd = [self.wrapper_path] + args
                self.logger.debug(f"Wrapper command: {cmd}")
            
            self.logger.debug(f"Executing command in directory: {self.cli_dir}")
            self.logger.debug(f"Environment PATH includes: {env.get('PATH', 'Not set')[:200]}...")
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, cwd=self.cli_dir, env=env)
            
            self.logger.debug(f"Command completed with return code: {result.returncode}")
            if result.stdout:
                self.logger.debug(f"STDOUT: {result.stdout[:500]}...")
            if result.stderr:
                self.logger.debug(f"STDERR: {result.stderr[:500]}...")
            
            return {
                'success': result.returncode == 0,
                'output': result.stdout,
                'error': result.stderr,
                'returncode': result.returncode
            }
        except subprocess.TimeoutExpired:
            self.logger.error(f"Command timed out: {cmd}")
            return {'success': False, 'output': '', 'error': 'Command timed out', 'returncode': -1}
        except Exception as e:
            self.logger.error(f"Error executing command: {cmd}")
            self.logger.error(f"Exception: {e}")
            import traceback
            traceback.print_exc()
            return {'success': False, 'output': '', 'error': str(e), 'returncode': -1}
    
    def run_cli_command(self, args: List[str], timeout: Optional[int] = None) -> Dict[str, Any]:
        """Run rediacc-cli command and parse JSON output if applicable"""
        try:
            # Don't pass token via command line - let rediacc-cli read it from TokenManager
            # This avoids issues with token rotation and ensures fresh tokens are always used
            
            cli_cmd = [self.python_cmd, self.cli_path_msys2] + args
            self.logger.debug(f"Executing CLI command: {cli_cmd}")
            self.logger.debug(f"Working directory: {self.cli_dir}")
            
            result = subprocess.run(cli_cmd, capture_output=True, text=True, timeout=timeout, cwd=self.cli_dir)
            
            self.logger.debug(f"CLI command completed with return code: {result.returncode}")
            if result.stdout:
                self.logger.debug(f"CLI STDOUT: {result.stdout[:500]}...")
            if result.stderr:
                self.logger.debug(f"CLI STDERR: {result.stderr[:500]}...")
            output = result.stdout.strip()
            
            if '--output' in args and 'json' in args:
                try:
                    data = json.loads(output) if output else {}
                    
                    # Token rotation is already handled by rediacc-cli itself
                    # No need to handle it here as it would cause duplicate saves
                    
                    # Extract data from tables format
                    response_data = data.get('data')
                    if not response_data and data.get('tables'):
                        for table in data.get('tables', []):
                            table_data = table.get('data', [])
                            if table_data and not any('nextRequestCredential' in row for row in table_data):
                                response_data = table_data
                                break
                    
                    return {
                        'success': result.returncode == 0 and data.get('success', False),
                        'data': response_data,
                        'error': data.get('error', result.stderr),
                        'raw_output': output
                    }
                except json.JSONDecodeError:
                    pass
            
            return {
                'success': result.returncode == 0,
                'output': output,
                'error': result.stderr,
                'returncode': result.returncode
            }
        except Exception as e:
            self.logger.error(f"Error executing CLI command: {[self.python_cmd, self.cli_path_msys2] + args}")
            self.logger.error(f"Exception: {e}")
            import traceback
            traceback.print_exc()
            return {'success': False, 'output': '', 'error': str(e), 'returncode': -1}
    
    def run_command_streaming(self, args: List[str], output_callback=None) -> Dict[str, Any]:
        """Run a command and stream output line by line"""
        # Choose the appropriate CLI script based on command
        if args[0] == 'sync':
            cli_script = self.sync_path_msys2
            args = args[1:]  # Remove 'sync' from args
        elif args[0] == 'term':
            cli_script = self.term_path_msys2
            args = args[1:]  # Remove 'term' from args
        elif args[0] == 'plugin':
            cli_script = self.plugin_path_msys2
            args = args[1:]  # Remove 'plugin' from args
        else:
            cli_script = self.cli_path_msys2
        
        cmd = [self.python_cmd, cli_script] + args
        self.logger.debug(f"Streaming command: {cmd}")
        
        try:
            # Start process with pipes
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,  # Merge stderr into stdout
                text=True,
                bufsize=1,  # Line buffered
                universal_newlines=True,
                env=os.environ.copy()
            )
            
            output_lines = []
            
            # Read output line by line
            for line in iter(process.stdout.readline, ''):
                if line:
                    output_lines.append(line)
                    if output_callback:
                        output_callback(line)
            
            # Wait for process to complete
            process.wait()
            
            # Get the return code
            returncode = process.returncode
            
            # Join all output
            full_output = ''.join(output_lines)
            
            return {
                'success': returncode == 0,
                'output': full_output,
                'error': '' if returncode == 0 else full_output,
                'returncode': returncode
            }
            
        except Exception as e:
            self.logger.error(f"Error in streaming command: {e}")
            return {
                'success': False,
                'output': '',
                'error': str(e),
                'returncode': -1
            }


# ============================================================================
# TERMINAL DETECTOR MODULE (from terminal_detector.py)
# ============================================================================

class TerminalDetector:
    """Detects and caches working terminal launch methods for the current system"""
    
    # Use centralized config directory
    CACHE_FILE = str(get_config_file("terminal_detector_cache.json"))
    CACHE_DURATION = timedelta(days=7)  # Re-test methods after a week
    
    def __init__(self):
        self.logger = get_logger(__name__)
        self.cache_dir = os.path.dirname(self.CACHE_FILE)
        if not os.path.exists(self.cache_dir):
            os.makedirs(self.cache_dir, exist_ok=True)
        
        # Check if running in WSL
        is_wsl = self._is_wsl()
        
        self.methods = {
            'win32': [
                ('msys2_mintty', self._test_msys2_mintty),
                ('wsl_wt', self._test_wsl_windows_terminal),
                ('wsl_powershell', self._test_wsl_powershell),
                ('msys2_wt', self._test_msys2_windows_terminal),
                ('msys2_bash', self._test_msys2_bash_direct),
                ('powershell', self._test_powershell_direct),
                ('cmd', self._test_cmd_direct)
            ],
            'darwin': [
                ('terminal_app', self._test_macos_terminal)
            ],
            'linux': [
                # If in WSL, prioritize Windows terminal methods
                ('wsl_wt', self._test_wsl_windows_terminal),
                ('wsl_powershell', self._test_wsl_powershell),
                ('wsl_cmd', self._test_wsl_cmd),
                ('gnome_terminal', self._test_gnome_terminal),
                ('konsole', self._test_konsole),
                ('xfce4_terminal', self._test_xfce4_terminal),
                ('mate_terminal', self._test_mate_terminal),
                ('terminator', self._test_terminator),
                ('xterm', self._test_xterm)
            ] if is_wsl else [
                # Regular Linux
                ('gnome_terminal', self._test_gnome_terminal),
                ('konsole', self._test_konsole),
                ('xfce4_terminal', self._test_xfce4_terminal),
                ('mate_terminal', self._test_mate_terminal),
                ('terminator', self._test_terminator),
                ('xterm', self._test_xterm)
            ]
        }
        
        # Load cache
        self.cache = self._load_cache()
    
    def _load_cache(self) -> Dict:
        """Load cached detection results"""
        try:
            if os.path.exists(self.CACHE_FILE):
                with open(self.CACHE_FILE, 'r') as f:
                    return json.load(f)
        except Exception as e:
            self.logger.debug(f"Failed to load cache: {e}")
        return {}
    
    def _save_cache(self):
        """Save detection results to cache"""
        try:
            with open(self.CACHE_FILE, 'w') as f:
                json.dump(self.cache, f, indent=2)
        except Exception as e:
            self.logger.error(f"Failed to save cache: {e}")
    
    def _is_cache_valid(self, platform: str) -> bool:
        """Check if cached results are still valid"""
        if platform not in self.cache:
            return False
        
        cached_time = self.cache[platform].get('timestamp')
        if not cached_time:
            return False
        
        try:
            cached_datetime = datetime.fromisoformat(cached_time)
            return datetime.now() - cached_datetime < self.CACHE_DURATION
        except:
            return False
    
    def _find_msys2_installation(self) -> Optional[str]:
        """Find MSYS2 installation path"""
        msys2_paths = [
            'C:\\msys64',
            'C:\\msys2',
            os.path.expanduser('~\\msys64'),
            os.path.expanduser('~\\msys2'),
        ]
        
        # Check MSYS2_ROOT environment variable
        msys2_root = os.environ.get('MSYS2_ROOT')
        if msys2_root:
            msys2_paths.insert(0, msys2_root)
        
        for path in msys2_paths:
            if os.path.exists(path):
                return path
        return None
    
    def _is_wsl(self) -> bool:
        """Check if running in WSL"""
        try:
            with open('/proc/version', 'r') as f:
                return 'microsoft' in f.read().lower()
        except:
            return False
    
    def _test_command(self, cmd: List[str], timeout: float = 3.0, 
                     expect_running: bool = True) -> Tuple[bool, str]:
        """Test if a command works
        
        Args:
            cmd: Command to test
            timeout: How long to wait for the command
            expect_running: If True, command should still be running after timeout
                          If False, command should complete successfully
        
        Returns:
            Tuple of (success, method_description)
        """
        try:
            # Create a test script that exits cleanly
            # Use .bat on Windows for methods that don't use bash
            is_bash_method = any(x in str(cmd) for x in ['bash', 'msys', 'wsl'])
            suffix = '.sh' if is_bash_method else ('.bat' if sys.platform == 'win32' else '.sh')
            
            with tempfile.NamedTemporaryFile(mode='w', suffix=suffix, delete=False) as f:
                if suffix == '.bat':
                    f.write('@echo off\necho Terminal detection test successful\nexit /b 0\n')
                else:
                    f.write('#!/bin/bash\necho "Terminal detection test successful"\nexit 0\n')
                test_script = f.name
            
            os.chmod(test_script, 0o755)
            
            # Replace placeholder in command with actual test script
            test_cmd = []
            for arg in cmd:
                if 'TEST_SCRIPT' in arg:
                    # Check if this is for MSYS2 and needs path conversion
                    if ('msys' in cmd[0].lower() or 
                        (len(cmd) > 2 and 'bash' in cmd[0] and '/msys' in cmd[0])):
                        # Convert to MSYS2 path format
                        msys2_path = self._windows_to_msys2_path(test_script)
                        test_cmd.append(arg.replace('TEST_SCRIPT', msys2_path))
                    else:
                        test_cmd.append(arg.replace('TEST_SCRIPT', test_script))
                else:
                    test_cmd.append(arg)
            
            self.logger.debug(f"Testing command: {' '.join(test_cmd[:3])}...")
            
            process = subprocess.Popen(
                test_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0
            )
            
            try:
                stdout, stderr = process.communicate(timeout=timeout)
                
                # Clean up test script
                try:
                    os.unlink(test_script)
                except:
                    pass
                
                if expect_running:
                    # Process should have timed out (still running)
                    return (False, "Process completed when it should be running")
                else:
                    # Process should have completed successfully
                    if process.returncode == 0:
                        return (True, "Command executed successfully")
                    else:
                        error_info = f"Command failed with code {process.returncode}"
                        if stderr:
                            error_info += f" - stderr: {stderr.decode()[:100]}"
                        return (False, error_info)
                        
            except subprocess.TimeoutExpired:
                # Kill the process
                process.kill()
                
                # Schedule cleanup for later (in case file is in use)
                self._schedule_cleanup(test_script)
                
                if expect_running:
                    # This is expected - terminal is running
                    return (True, "Terminal launched successfully")
                else:
                    # This is unexpected - command should have completed
                    return (False, "Command timed out unexpectedly")
                    
        except Exception as e:
            # Clean up test script if it exists
            if 'test_script' in locals():
                self._schedule_cleanup(test_script)
            return (False, f"Exception: {str(e)}")
    
    def _schedule_cleanup(self, filepath: str):
        """Schedule file cleanup after a delay"""
        def cleanup():
            time.sleep(5)
            try:
                if os.path.exists(filepath):
                    os.unlink(filepath)
            except:
                pass
        
        import threading
        cleanup_thread = threading.Thread(target=cleanup)
        cleanup_thread.daemon = True
        cleanup_thread.start()
    
    # Windows terminal tests
    def _test_msys2_mintty(self) -> Tuple[bool, str]:
        """Test MSYS2 mintty terminal"""
        msys2_path = self._find_msys2_installation()
        if not msys2_path:
            return (False, "MSYS2 not found")
        
        mintty_exe = os.path.join(msys2_path, 'usr', 'bin', 'mintty.exe')
        if not os.path.exists(mintty_exe):
            return (False, "mintty.exe not found")
        
        # Simple test: just check if mintty can be launched
        # We can't reliably test if it stays open, so just verify it starts
        try:
            # Test with a simple echo command
            bash_exe = os.path.join(msys2_path, 'usr', 'bin', 'bash.exe')
            test_cmd = [mintty_exe, '--version']
            process = subprocess.Popen(
                test_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0
            )
            stdout, stderr = process.communicate(timeout=2)
            if process.returncode == 0:
                return (True, "mintty is available")
            else:
                return (False, f"mintty test failed with code {process.returncode}")
        except Exception as e:
            return (False, f"Failed to test mintty: {str(e)}")
    
    def _test_wsl_windows_terminal(self) -> Tuple[bool, str]:
        """Test WSL with Windows Terminal"""
        # Check if Windows Terminal is available
        try:
            test_cmd = ['cmd.exe', '/c', 'where', 'wt.exe']
            process = subprocess.Popen(
                test_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            stdout, stderr = process.communicate(timeout=2)
            if process.returncode == 0:
                return (True, "Windows Terminal is available in WSL")
            else:
                return (False, "Windows Terminal not found in WSL")
        except Exception as e:
            return (False, f"Failed to test Windows Terminal: {str(e)}")
    
    def _test_wsl_powershell(self) -> Tuple[bool, str]:
        """Test WSL with PowerShell"""
        try:
            # Simple test to see if powershell.exe is available
            test_cmd = ['powershell.exe', '-Command', 'echo "test"']
            process = subprocess.Popen(
                test_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            stdout, stderr = process.communicate(timeout=2)
            if process.returncode == 0:
                return (True, "PowerShell is available in WSL")
            else:
                return (False, "PowerShell not accessible from WSL")
        except Exception as e:
            return (False, f"Failed to test PowerShell: {str(e)}")
    
    def _test_wsl_cmd(self) -> Tuple[bool, str]:
        """Test WSL with cmd.exe"""
        try:
            # Simple test to see if cmd.exe is available
            test_cmd = ['cmd.exe', '/c', 'echo test']
            process = subprocess.Popen(
                test_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            stdout, stderr = process.communicate(timeout=2)
            if process.returncode == 0:
                return (True, "cmd.exe is available in WSL")
            else:
                return (False, "cmd.exe not accessible from WSL")
        except Exception as e:
            return (False, f"Failed to test cmd.exe: {str(e)}")
    
    def _test_msys2_windows_terminal(self) -> Tuple[bool, str]:
        """Test MSYS2 with Windows Terminal"""
        msys2_path = self._find_msys2_installation()
        if not msys2_path:
            return (False, "MSYS2 not found")
        
        bash_exe = os.path.join(msys2_path, 'usr', 'bin', 'bash.exe')
        if not os.path.exists(bash_exe):
            return (False, "bash.exe not found")
        
        # Check if Windows Terminal is available
        try:
            # Test if wt.exe exists in PATH
            test_cmd = ['where', 'wt.exe']
            process = subprocess.Popen(
                test_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0
            )
            stdout, stderr = process.communicate(timeout=2)
            if process.returncode == 0:
                return (True, "Windows Terminal is available")
            else:
                return (False, "Windows Terminal (wt.exe) not found in PATH")
        except Exception as e:
            return (False, f"Failed to test Windows Terminal: {str(e)}")
    
    def _test_msys2_bash_direct(self) -> Tuple[bool, str]:
        """Test MSYS2 bash directly"""
        msys2_path = self._find_msys2_installation()
        if not msys2_path:
            return (False, "MSYS2 not found")
        
        bash_exe = os.path.join(msys2_path, 'usr', 'bin', 'bash.exe')
        if not os.path.exists(bash_exe):
            return (False, "bash.exe not found")
        
        # Use -l flag for login shell to ensure proper environment
        cmd = [bash_exe, '-l', '-c', 'TEST_SCRIPT']
        return self._test_command(cmd, expect_running=False)
    
    def _test_powershell_direct(self) -> Tuple[bool, str]:
        """Test PowerShell directly"""
        cmd = ['powershell.exe', '-Command', '& TEST_SCRIPT']
        return self._test_command(cmd, expect_running=False)
    
    def _test_cmd_direct(self) -> Tuple[bool, str]:
        """Test cmd.exe directly"""
        cmd = ['cmd.exe', '/c', 'TEST_SCRIPT']
        return self._test_command(cmd, expect_running=False)
    
    # macOS terminal test
    def _test_macos_terminal(self) -> Tuple[bool, str]:
        """Test macOS Terminal.app"""
        cmd = ['open', '-a', 'Terminal', 'TEST_SCRIPT']
        return self._test_command(cmd, expect_running=True)
    
    # Linux terminal tests
    def _test_gnome_terminal(self) -> Tuple[bool, str]:
        """Test GNOME Terminal"""
        cmd = ['gnome-terminal', '--', 'bash', 'TEST_SCRIPT']
        return self._test_command(cmd, expect_running=True)
    
    def _test_konsole(self) -> Tuple[bool, str]:
        """Test KDE Konsole"""
        cmd = ['konsole', '-e', 'bash', 'TEST_SCRIPT']
        return self._test_command(cmd, expect_running=True)
    
    def _test_xfce4_terminal(self) -> Tuple[bool, str]:
        """Test XFCE4 Terminal"""
        cmd = ['xfce4-terminal', '-e', 'bash TEST_SCRIPT']
        return self._test_command(cmd, expect_running=True)
    
    def _test_mate_terminal(self) -> Tuple[bool, str]:
        """Test MATE Terminal"""
        cmd = ['mate-terminal', '-e', 'bash TEST_SCRIPT']
        return self._test_command(cmd, expect_running=True)
    
    def _test_terminator(self) -> Tuple[bool, str]:
        """Test Terminator"""
        cmd = ['terminator', '-e', 'bash TEST_SCRIPT']
        return self._test_command(cmd, expect_running=True)
    
    def _test_xterm(self) -> Tuple[bool, str]:
        """Test XTerm"""
        cmd = ['xterm', '-e', 'bash', 'TEST_SCRIPT']
        return self._test_command(cmd, expect_running=True)
    
    def detect(self, force_refresh: bool = False) -> Optional[str]:
        """Detect the best working terminal method
        
        Args:
            force_refresh: Force re-detection even if cache is valid
            
        Returns:
            The name of the best working method, or None if none work
        """
        platform = sys.platform
        
        # Normalize platform
        if platform.startswith('linux'):
            platform = 'linux'
        
        # Check cache
        if not force_refresh and self._is_cache_valid(platform):
            cached_method = self.cache[platform].get('method')
            if cached_method:
                self.logger.debug(f"Using cached method: {cached_method}")
                return cached_method
        
        # Get methods for this platform
        platform_methods = self.methods.get(platform, [])
        if not platform_methods:
            self.logger.warning(f"No methods defined for platform: {platform}")
            return None
        
        self.logger.debug(f"Testing {len(platform_methods)} methods for {platform}...")
        
        # Test each method
        working_methods = []
        for method_name, test_func in platform_methods:
            success, description = test_func()
            if success:
                self.logger.debug(f"[OK] {method_name}: {description}")
                working_methods.append(method_name)
            else:
                self.logger.debug(f"[FAIL] {method_name}: {description}")
        
        # Select the best method (first working one)
        best_method = working_methods[0] if working_methods else None
        
        # Update cache
        self.cache[platform] = {
            'method': best_method,
            'working_methods': working_methods,
            'timestamp': datetime.now().isoformat(),
            'platform': platform
        }
        self._save_cache()
        
        if best_method:
            self.logger.info(f"Selected terminal method: {best_method}")
        else:
            self.logger.warning("No working terminal methods found!")
        
        return best_method
    
    def get_launch_function(self, method_name: str):
        """Get the launch function for a specific method
        
        Returns a function that takes (cli_dir, command, description) and launches a terminal
        """
        launch_functions = {
            # Windows methods
            'msys2_mintty': self._launch_msys2_mintty,
            'wsl_wt': self._launch_wsl_windows_terminal,
            'wsl_powershell': self._launch_wsl_powershell,
            'wsl_cmd': self._launch_wsl_cmd,
            'msys2_wt': self._launch_msys2_windows_terminal,
            'msys2_bash': self._launch_msys2_bash_direct,
            'powershell': self._launch_powershell_direct,
            'cmd': self._launch_cmd_direct,
            # macOS methods
            'terminal_app': self._launch_macos_terminal,
            # Linux methods
            'gnome_terminal': self._launch_gnome_terminal,
            'konsole': self._launch_konsole,
            'xfce4_terminal': self._launch_xfce4_terminal,
            'mate_terminal': self._launch_mate_terminal,
            'terminator': self._launch_terminator,
            'xterm': self._launch_xterm
        }
        
        return launch_functions.get(method_name)
    
    def _windows_to_msys2_path(self, windows_path: str) -> str:
        """Convert Windows path to MSYS2 format"""
        if len(windows_path) >= 2 and windows_path[1] == ':':
            drive = windows_path[0].lower()
            rest = windows_path[2:].replace('\\', '/')
            return f'/{drive}{rest}'
        return windows_path.replace('\\', '/')
    
    # Launch functions for each method
    def _launch_msys2_mintty(self, cli_dir: str, command: str, description: str):
        """Launch using MSYS2 mintty"""
        msys2_path = self._find_msys2_installation()
        mintty_exe = os.path.join(msys2_path, 'usr', 'bin', 'mintty.exe')
        bash_exe = os.path.join(msys2_path, 'usr', 'bin', 'bash.exe')
        msys2_cli_dir = self._windows_to_msys2_path(cli_dir)
        
        import shlex
        cmd_parts = shlex.split(command)
        if cmd_parts[0] == 'term':
            cli_script = f'{msys2_cli_dir}/src/cli/rediacc-cli-term.py'
            args = cmd_parts[1:]
        elif cmd_parts[0] == 'sync':
            cli_script = f'{msys2_cli_dir}/src/cli/rediacc-cli-sync.py'
            args = cmd_parts[1:]
        else:
            cli_script = f'{msys2_cli_dir}/src/cli/rediacc-cli.py'
            args = cmd_parts
        
        escaped_args = ' '.join(shlex.quote(arg) for arg in args)
        bash_cmd = f'cd "{msys2_cli_dir}" && python3 {cli_script} {escaped_args}'
        
        # Launch maximized with -w max option
        subprocess.Popen([mintty_exe, '-w', 'max', '-e', bash_exe, '-l', '-c', bash_cmd])
    
    def _launch_wsl_windows_terminal(self, cli_dir: str, command: str, description: str):
        """Launch using WSL with Windows Terminal"""
        # Parse command to determine which CLI script to use
        import shlex
        try:
            cmd_parts = shlex.split(command)
        except:
            # If shlex fails, do simple split
            cmd_parts = command.split()
        
        # Determine the correct CLI script based on command
        if cmd_parts and cmd_parts[0] == 'term':
            cli_script = './src/cli/rediacc-cli-term.py'
            args = ' '.join(shlex.quote(arg) for arg in cmd_parts[1:])
        elif cmd_parts and cmd_parts[0] == 'sync':
            cli_script = './src/cli/rediacc-cli-sync.py'
            args = ' '.join(shlex.quote(arg) for arg in cmd_parts[1:])
        else:
            cli_script = './rediacc'
            args = command
        
        # Build the WSL command
        wsl_command = f'cd {cli_dir} && {cli_script} {args}'
        
        # Launch Windows Terminal maximized with WSL command
        wt_cmd = ['wt.exe', '--maximized', 'new-tab', 'wsl.exe', '-e', 'bash', '-c', wsl_command]
        
        try:
            # Launch directly without cmd.exe to avoid UNC path warning
            subprocess.Popen(wt_cmd)
        except Exception as e:
            # Fallback to cmd.exe method if direct launch fails
            cmd_str = f'wt.exe --maximized new-tab wsl.exe -e bash -c "{wsl_command}"'
            subprocess.Popen(['cmd.exe', '/c', cmd_str], cwd=os.environ.get('WINDIR', 'C:\\Windows'))
    
    def _launch_wsl_powershell(self, cli_dir: str, command: str, description: str):
        """Launch using WSL with PowerShell"""
        # Parse command to determine which CLI script to use
        import shlex
        try:
            cmd_parts = shlex.split(command)
        except:
            cmd_parts = command.split()
        
        # Determine the correct CLI script
        if cmd_parts and cmd_parts[0] == 'term':
            cli_script = './src/cli/rediacc-cli-term.py'
            args = ' '.join(shlex.quote(arg) for arg in cmd_parts[1:])
        elif cmd_parts and cmd_parts[0] == 'sync':
            cli_script = './src/cli/rediacc-cli-sync.py'
            args = ' '.join(shlex.quote(arg) for arg in cmd_parts[1:])
        else:
            cli_script = './rediacc'
            args = command
        
        # Use PowerShell's Start-Process to avoid UNC path issues, launch maximized
        ps_cmd = f'Start-Process wsl -WindowStyle Maximized -ArgumentList "-e", "bash", "-c", "cd {cli_dir} && {cli_script} {args}"'
        # Set working directory to Windows directory to avoid UNC warning
        subprocess.Popen(['powershell.exe', '-Command', ps_cmd], 
                        cwd=os.environ.get('WINDIR', 'C:\\Windows'))
    
    def _launch_wsl_cmd(self, cli_dir: str, command: str, description: str):
        """Launch using WSL with cmd.exe"""
        # Parse command to determine which CLI script to use
        import shlex
        try:
            cmd_parts = shlex.split(command)
        except:
            cmd_parts = command.split()
        
        # Determine the correct CLI script
        if cmd_parts and cmd_parts[0] == 'term':
            cli_script = './src/cli/rediacc-cli-term.py'
            args = ' '.join(f'"{arg}"' if ' ' in arg else arg for arg in cmd_parts[1:])
        elif cmd_parts and cmd_parts[0] == 'sync':
            cli_script = './src/cli/rediacc-cli-sync.py'
            args = ' '.join(f'"{arg}"' if ' ' in arg else arg for arg in cmd_parts[1:])
        else:
            cli_script = './rediacc'
            args = command
        
        # Use start with /D to set working directory and /max to maximize
        cmd_cmd = f'start /max "WSL Terminal" /D "%WINDIR%" wsl bash -c "cd {cli_dir} && {cli_script} {args}"'
        subprocess.Popen(['cmd.exe', '/c', cmd_cmd])
    
    def _launch_msys2_windows_terminal(self, cli_dir: str, command: str, description: str):
        """Launch using MSYS2 with Windows Terminal"""
        msys2_path = self._find_msys2_installation()
        bash_exe = os.path.join(msys2_path, 'usr', 'bin', 'bash.exe')
        msys2_cli_dir = self._windows_to_msys2_path(cli_dir)
        
        import shlex
        cmd_parts = shlex.split(command)
        if cmd_parts[0] == 'term':
            cli_script = f'{msys2_cli_dir}/src/cli/rediacc-cli-term.py'
            args = cmd_parts[1:]
        elif cmd_parts[0] == 'sync':
            cli_script = f'{msys2_cli_dir}/src/cli/rediacc-cli-sync.py'
            args = cmd_parts[1:]
        else:
            cli_script = f'{msys2_cli_dir}/src/cli/rediacc-cli.py'
            args = cmd_parts
        
        escaped_args = ' '.join(shlex.quote(arg) for arg in args)
        bash_cmd = f'cd "{msys2_cli_dir}" && python3 {cli_script} {escaped_args}'
        wt_cmd = f'wt.exe --maximized new-tab "{bash_exe}" -l -c "{bash_cmd}"'
        
        subprocess.Popen(['cmd.exe', '/c', wt_cmd])
    
    def _launch_msys2_bash_direct(self, cli_dir: str, command: str, description: str):
        """Launch using MSYS2 bash directly (no new window)"""
        msys2_path = self._find_msys2_installation()
        bash_exe = os.path.join(msys2_path, 'usr', 'bin', 'bash.exe')
        msys2_cli_dir = self._windows_to_msys2_path(cli_dir)
        
        import shlex
        cmd_parts = shlex.split(command)
        if cmd_parts[0] == 'term':
            cli_script = f'{msys2_cli_dir}/src/cli/rediacc-cli-term.py'
            args = cmd_parts[1:]
        elif cmd_parts[0] == 'sync':
            cli_script = f'{msys2_cli_dir}/src/cli/rediacc-cli-sync.py'
            args = cmd_parts[1:]
        else:
            cli_script = f'{msys2_cli_dir}/src/cli/rediacc-cli.py'
            args = cmd_parts
        
        escaped_args = ' '.join(shlex.quote(arg) for arg in args)
        bash_cmd = f'cd "{msys2_cli_dir}" && python3 {cli_script} {escaped_args}'
        
        subprocess.Popen([bash_exe, '-l', '-c', bash_cmd])
    
    def _launch_powershell_direct(self, cli_dir: str, command: str, description: str):
        """Launch using PowerShell directly"""
        import shlex
        cmd_parts = shlex.split(command)
        if cmd_parts[0] == 'term':
            cli_script = f'{cli_dir}\\src\\cli\\rediacc-cli-term.py'
            args = cmd_parts[1:]
        elif cmd_parts[0] == 'sync':
            cli_script = f'{cli_dir}\\src\\cli\\rediacc-cli-sync.py'
            args = cmd_parts[1:]
        else:
            cli_script = f'{cli_dir}\\src\\cli\\rediacc-cli.py'
            args = cmd_parts
        
        escaped_args = ' '.join(f'"{arg}"' if ' ' in arg else arg for arg in args)
        ps_cmd = f'Start-Process powershell -WindowStyle Maximized -ArgumentList "-Command", "cd \\"{cli_dir}\\"; python3 {cli_script} {escaped_args}"'
        
        subprocess.Popen(['powershell.exe', '-Command', ps_cmd])
    
    def _launch_cmd_direct(self, cli_dir: str, command: str, description: str):
        """Launch using cmd.exe directly"""
        import shlex
        cmd_parts = shlex.split(command)
        if cmd_parts[0] == 'term':
            cli_script = f'{cli_dir}\\src\\cli\\rediacc-cli-term.py'
            args = cmd_parts[1:]
        elif cmd_parts[0] == 'sync':
            cli_script = f'{cli_dir}\\src\\cli\\rediacc-cli-sync.py'
            args = cmd_parts[1:]
        else:
            cli_script = f'{cli_dir}\\src\\cli\\rediacc-cli.py'
            args = cmd_parts
        
        escaped_args = ' '.join(f'"{arg}"' if ' ' in arg else arg for arg in args)
        cmd_str = f'cd /d "{cli_dir}" && python {cli_script} {escaped_args}'
        
        # Launch maximized
        subprocess.Popen(['cmd.exe', '/c', f'start /max cmd /c {cmd_str}'])
    
    def _launch_macos_terminal(self, cli_dir: str, command: str, description: str):
        """Launch using macOS Terminal.app"""
        cmd_str = f'cd {cli_dir} && ./rediacc {command}'
        # Launch Terminal.app (maximizing is handled by macOS Window Manager)
        # Note: Terminal.app doesn't have a direct maximize flag
        subprocess.Popen(['open', '-a', 'Terminal', '--', 'bash', '-c', cmd_str])
    
    def _launch_gnome_terminal(self, cli_dir: str, command: str, description: str):
        """Launch using GNOME Terminal"""
        cmd_str = f'cd {cli_dir} && ./rediacc {command}'
        # Launch maximized
        subprocess.Popen(['gnome-terminal', '--maximize', '--', 'bash', '-c', cmd_str])
    
    def _launch_konsole(self, cli_dir: str, command: str, description: str):
        """Launch using KDE Konsole"""
        cmd_str = f'cd {cli_dir} && ./rediacc {command}'
        # Launch maximized
        subprocess.Popen(['konsole', '--fullscreen', '-e', 'bash', '-c', cmd_str])
    
    def _launch_xfce4_terminal(self, cli_dir: str, command: str, description: str):
        """Launch using XFCE4 Terminal"""
        cmd_str = f'cd {cli_dir} && ./rediacc {command}'
        # Launch maximized
        subprocess.Popen(['xfce4-terminal', '--maximize', '-e', f'bash -c "{cmd_str}"'])
    
    def _launch_mate_terminal(self, cli_dir: str, command: str, description: str):
        """Launch using MATE Terminal"""
        cmd_str = f'cd {cli_dir} && ./rediacc {command}'
        # Launch maximized
        subprocess.Popen(['mate-terminal', '--maximize', '-e', f'bash -c "{cmd_str}"'])
    
    def _launch_terminator(self, cli_dir: str, command: str, description: str):
        """Launch using Terminator"""
        cmd_str = f'cd {cli_dir} && ./rediacc {command}'
        # Launch maximized
        subprocess.Popen(['terminator', '--maximise', '-e', f'bash -c "{cmd_str}"'])
    
    def _launch_xterm(self, cli_dir: str, command: str, description: str):
        """Launch using XTerm"""
        cmd_str = f'cd {cli_dir} && ./rediacc {command}'
        # Launch maximized with geometry
        subprocess.Popen(['xterm', '-maximized', '-e', 'bash', '-c', cmd_str])


# ============================================================================
# MODULE EXPORTS - All functions and classes available from this module
# ============================================================================

__all__ = [
    # Config path functions
    'get_cli_root',
    'get_config_dir',
    'get_config_file',
    'get_main_config_file',
    'get_language_config_file',
    'get_plugin_connections_file',
    'get_terminal_cache_file',
    'get_terminal_detector_cache_file',
    'get_api_lock_file',
    'get_token_lock_file',
    'get_ssh_control_dir',
    
    # Logging functions
    'setup_logging',
    'get_logger',
    'is_verbose_enabled',
    
    # Config loader
    'ConfigError',
    'Config',
    'get_config',
    'load_config',
    'get',
    'get_required',
    'get_int',
    'get_bool',
    'get_path',
    
    # API mutex
    'api_mutex',
    'APIMutex',
    
    # Token manager
    'TokenManager',
    'get_default_token_manager',
    'is_encrypted',
    'decrypt_string',
    
    # I18n
    'I18n',
    'i18n',
    
    # Subprocess runner
    'SubprocessRunner',
    
    # Terminal detector
    'TerminalDetector',
]