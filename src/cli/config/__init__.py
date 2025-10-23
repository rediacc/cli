"""
Configuration files for Rediacc CLI

This package contains all JSON configuration files used by the CLI.
"""

from pathlib import Path

# Configuration directory
CONFIG_DIR = Path(__file__).parent

# Main CLI configuration file
CLI_CONFIG_FILE = CONFIG_DIR / "cli-config.json"

# GUI configuration files
GUI_CONFIG_FILE = CONFIG_DIR / "rediacc-gui-config.json"
GUI_TRANSLATIONS_FILE = CONFIG_DIR / "rediacc-gui-translations.json"

# Terminal configuration
TERM_CONFIG_FILE = CONFIG_DIR / "rediacc-term-config.json"

__all__ = [
    'CONFIG_DIR',
    'CLI_CONFIG_FILE',
    'GUI_CONFIG_FILE',
    'GUI_TRANSLATIONS_FILE',
    'TERM_CONFIG_FILE',
]
