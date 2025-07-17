#!/usr/bin/env python3
"""
Centralized configuration path management for Rediacc CLI
Provides a single source of truth for locating configuration directories and files
"""
import os
from pathlib import Path
from typing import Optional


def get_cli_root() -> Path:
    """
    Get the CLI root directory (where src, scripts, tests, etc. are located)
    
    Returns:
        Path: The absolute path to the CLI root directory
    """
    # This module is in cli/src/modules, so go up 2 levels
    current_file = Path(__file__).resolve()
    cli_root = current_file.parent.parent.parent  # modules -> src -> cli
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