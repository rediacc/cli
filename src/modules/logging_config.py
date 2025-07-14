#!/usr/bin/env python3
"""
Logging configuration for Rediacc CLI.
"""

import logging
import sys
from typing import Optional


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