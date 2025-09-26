"""
CLI assets module containing icons and other static resources.
"""
import os
from pathlib import Path

# Get the directory containing this file
ASSETS_DIR = Path(__file__).parent

def get_favicon_path():
    """Return the path to the favicon.svg file."""
    return ASSETS_DIR / "favicon.svg"

def get_asset_path(filename):
    """Return the path to any asset file."""
    return ASSETS_DIR / filename