#!/usr/bin/env python3
"""
Minimal setup.py for backward compatibility.

This file exists for compatibility with legacy tools that expect setup.py.
All package configuration is now in pyproject.toml.

Modern installations should use:
    pip install .
or
    python -m build

Instead of:
    python setup.py install  # deprecated
    python setup.py develop  # deprecated
"""

from setuptools import setup

# All configuration is in pyproject.toml
# This is just a shim for backward compatibility
setup()