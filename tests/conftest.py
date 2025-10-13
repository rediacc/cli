#!/usr/bin/env python3
"""
Pytest configuration and fixtures for test suite
"""

import os
import pytest
import sys
from pathlib import Path
import platform

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

    # Optional targeted skip: Linux + Python >= 3.12 + CI env flag(s)
    SKIP_GUI_PY312 = (
        IN_CI
        and sys.version_info >= (3, 12)
        and platform.system().lower() == "linux"
        and os.environ.get("SKIP_GUI_FOR_PY312", "").lower() in ("1", "true", "yes")
    )
    SKIP_GUI_PY313 = (
        IN_CI
        and sys.version_info >= (3, 13)
        and platform.system().lower() == "linux"
        and os.environ.get("SKIP_GUI_FOR_PY313", "").lower() in ("1", "true", "yes")
    )
    skip_gui_py312 = pytest.mark.skip(reason="Skipping GUI tests on Python 3.12 Linux in CI (temporary workaround)")
    skip_gui_py313 = pytest.mark.skip(reason="Skipping GUI tests on Python 3.13 Linux in CI (temporary workaround)")

    for item in items:
        # Skip GUI tests when no display is available
        if "gui" in item.keywords and not DISPLAY_AVAILABLE:
            item.add_marker(skip_gui)

        # Targeted skip for known hang on Linux + Python 3.12/3.13 (enabled via env vars)
        if "gui" in item.keywords and (SKIP_GUI_PY312 or SKIP_GUI_PY313):
            if SKIP_GUI_PY312:
                item.add_marker(skip_gui_py312)
            if SKIP_GUI_PY313:
                item.add_marker(skip_gui_py313)

        # Skip GUI tests that are in gui directory
        if "/gui/" in str(item.fspath) and not DISPLAY_AVAILABLE:
            item.add_marker(skip_gui)

        # Skip Playwright tests when browsers aren't installed
        if "playwright" in item.keywords and not PLAYWRIGHT_BROWSERS_INSTALLED:
            item.add_marker(skip_playwright)

        # Skip Playwright tests based on file path
        if "test_protocol_playwright" in str(item.fspath) and not PLAYWRIGHT_BROWSERS_INSTALLED:
            item.add_marker(skip_playwright)
