#!/usr/bin/env python3
"""
Helper script to create and activate a test user for the Rediacc test framework.

Note: This script is deprecated. Use setup_test_company.py instead, which creates
both a company and user using the CreateNewCompany API.
"""

import os
import sys

print("=" * 60)
print("DEPRECATED: This script is deprecated!")
print("=" * 60)
print("\nPlease use setup_test_company.py instead.")
print("\nThe new script properly creates both a company and user")
print("using the CreateNewCompany API, which is the correct way")
print("to set up test environments.\n")
print("Run: python3 setup_test_company.py")
print("=" * 60)

sys.exit(1)