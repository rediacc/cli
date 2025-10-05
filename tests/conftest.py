#!/usr/bin/env python3
"""
Pytest configuration and fixtures for test suite
"""

import os
import pytest
import sys
from pathlib import Path

# Check if we're in CI environment
IN_CI = os.environ.get('CI', 'false').lower() == 'true'
# Display is available if DISPLAY env var exists and is not empty
DISPLAY_AVAILABLE = bool(os.environ.get('DISPLAY'))

# Check for playwright browsers
PLAYWRIGHT_BROWSERS_INSTALLED = False
try:
    from playwright.sync_api import sync_playwright
    # Try to check if browsers are installed
    home = Path.home()
    ms_playwright = home / '.cache' / 'ms-playwright'
    if ms_playwright.exists():
        # Check for chromium
        chromium_folders = list(ms_playwright.glob('chromium-*'))
        if chromium_folders:
            PLAYWRIGHT_BROWSERS_INSTALLED = True
except ImportError:
    pass


def pytest_configure(config):
    """Configure pytest with custom markers"""
    config.addinivalue_line(
        "markers", "gui: marks tests that require a graphical display"
    )
    config.addinivalue_line(
        "markers", "playwright: marks tests that require Playwright browsers"
    )


def pytest_collection_modifyitems(config, items):
    """Modify test collection to skip tests based on environment"""
    skip_gui = pytest.mark.skip(reason="No display available (running in headless environment)")
    skip_playwright = pytest.mark.skip(reason="Playwright browsers not installed. Run: playwright install")

    for item in items:
        # Skip GUI tests when no display is available
        if "gui" in item.keywords and not DISPLAY_AVAILABLE:
            item.add_marker(skip_gui)

        # Skip GUI tests that are in gui directory
        if "/gui/" in str(item.fspath) and not DISPLAY_AVAILABLE:
            item.add_marker(skip_gui)

        # Skip Playwright tests when browsers aren't installed
        if "playwright" in item.keywords and not PLAYWRIGHT_BROWSERS_INSTALLED:
            item.add_marker(skip_playwright)

        # Skip Playwright tests based on file path
        if "test_protocol_playwright" in str(item.fspath) and not PLAYWRIGHT_BROWSERS_INSTALLED:
            item.add_marker(skip_playwright)