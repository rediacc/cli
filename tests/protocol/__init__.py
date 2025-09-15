#!/usr/bin/env python3
"""
Rediacc Protocol Testing Package

This package contains comprehensive tests for the rediacc:// protocol handler,
including URL parsing, security validation, cross-platform registration,
and browser integration testing.

Test categories:
- test_protocol_parser.py: URL parsing and validation
- test_protocol_registration.py: Protocol registration/unregistration
- test_protocol_security.py: Security and safety testing
- test_protocol_cross_platform.py: Cross-platform compatibility
- test_protocol_playwright.py: Browser automation and integration

Run tests with:
    python3 rediacc.py test protocol
    python3 -m pytest tests/protocol/ -v
"""