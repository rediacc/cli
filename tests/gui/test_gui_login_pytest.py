#!/usr/bin/env python3
"""
Pytest wrapper for GUI login tests
This file provides pytest-compatible test functions that use the TestSuite
"""

import sys
import os
from pathlib import Path

# Add parent directories to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / 'src' / 'cli'))

# Import the test suite - need to add the directory to path
sys.path.insert(0, str(Path(__file__).parent))
from test_gui_login_basic import GUITestSuite

# Create a global test suite instance
suite = GUITestSuite()


def test_window_title():
    """Test that window has correct title"""
    suite.test_window_title()


def test_window_widgets():
    """Test that all required widgets are present"""
    suite.test_window_widgets()


def test_login_form():
    """Test the login form interaction without real auth"""
    suite.test_login_form()


def test_wrong_credentials():
    """Test that login fails with wrong credentials"""
    suite.test_wrong_credentials()


def test_real_login():
    """Test real login with credentials from .env"""
    suite.test_real_login()


def teardown_module():
    """Clean up after all tests"""
    if suite.shared_window:
        suite.close_shared_window()