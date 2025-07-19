#!/usr/bin/env python3
"""
Helper script to create a test company and user for the Rediacc test framework.
This uses the CreateNewCompany API which creates both a company and admin user.
"""

import os
import sys
import json
import subprocess
import hashlib
import base64
import time
import random
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

def pwd_hash_base64(password):
    """Generate a base64 password hash for authentication"""
    return base64.b64encode(hashlib.sha256(password.encode()).digest()).decode()

def run_cli_command(args):
    """Run a CLI command and return the result"""
    cmd = [sys.executable, "../src/cli/rediacc-cli.py"] + args + ["--output", "json"]
    
    print(f"Running: {' '.join(args)}")
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.stdout:
            return json.loads(result.stdout)
        else:
            return {"success": False, "error": result.stderr}
    except Exception as e:
        return {"success": False, "error": str(e)}

def main():
    # Load environment variables
    from tests_yaml.run import load_env_file
    load_env_file()
    
    # Check if we already have system admin credentials
    system_admin_email = os.environ.get('SYSTEM_ADMIN_EMAIL')
    system_admin_password = os.environ.get('SYSTEM_ADMIN_PASSWORD')
    
    if system_admin_email and system_admin_password:
        print(f"\nSystem admin credentials found:")
        print(f"  Email: {system_admin_email}")
        print(f"  Using existing credentials to create test company\n")
        
        # Login as system admin first
        print("1. Logging in as system admin...")
        result = run_cli_command([
            "login",
            "--email", system_admin_email,
            "--password", system_admin_password
        ])
        
        if not result.get("success"):
            print(f"   ✗ System admin login failed: {result.get('error', 'Unknown error')}")
            print("\nFalling back to creating new company...\n")
        else:
            print("   ✓ System admin login successful")
            # For now, we'll proceed to create a new company anyway
            # In a real scenario, you might want to use the admin account to create test users
    
    # Get activation code from environment (required)
    activation_code = os.environ.get('REDIACC_TEST_ACTIVATION_CODE', '111111')
    
    # Generate unique test credentials for parallel testing
    import time
    import random
    timestamp = int(time.time())
    random_suffix = random.randint(1000, 9999)
    
    # Generate unique values
    unique_company_name = f"TestCompany_{timestamp}_{random_suffix}"
    unique_email = f"test_{timestamp}_{random_suffix}@example.com"
    test_password = f"TestPass{timestamp}!"  # Unique but predictable for debugging
    
    print(f"\nCreating new test company:")
    print(f"  Company: {unique_company_name}")
    print(f"  Admin Email: {unique_email}")
    print(f"  Activation Code: {activation_code}")
    
    # Step 1: Create company (which also creates the admin user)
    print("\n1. Creating company and admin user...")
    result = run_cli_command([
        "create", "company",
        unique_company_name,
        "--email", unique_email,
        "--password", test_password,
        "--activation-code", activation_code,
        "--plan", "ELITE"  # Use ELITE plan for all features
    ])
    
    if result.get("success"):
        print("   ✓ Company and admin user created successfully")
    else:
        error = result.get("error", "")
        # Check if it's a permissions error
        if "403" in error or "Access denied" in error:
            print("   ✗ Access denied - only system admins can create companies")
            print("\nTo create test companies, you need system admin credentials.")
            print("Add these to your .env file:")
            print("  SYSTEM_ADMIN_EMAIL=admin@rediacc.io")
            print("  SYSTEM_ADMIN_PASSWORD=<admin_password>")
            return 1
        else:
            print(f"   ✗ Failed to create company: {error}")
            return 1
    
    # Step 2: The user should already be activated with the code we provided
    print("\n2. User should be automatically activated...")
    print("   ✓ User activation handled during company creation")
    
    # Step 3: Test login with the new credentials
    print("\n3. Testing login with new credentials...")
    result = run_cli_command([
        "login",
        "--email", unique_email,
        "--password", test_password
    ])
    
    if result.get("success"):
        print("   ✓ Login successful!")
        print(f"   Token: {result.get('token', 'N/A')[:20]}...")
        
        print(f"\n✅ Test company setup complete!")
        
        # Output credentials in a format that can be used directly
        print(f"\nTo run tests with these credentials:")
        print(f"  python3 -m tests_yaml.run --suite basic --username '{unique_email}' --password '{test_password}'")
        print(f"\nOr export as environment variables:")
        print(f"  export REDIACC_TEST_USERNAME='{unique_email}'")
        print(f"  export REDIACC_TEST_PASSWORD='{test_password}'")
        print(f"  python3 -m tests_yaml.run --suite basic")
        
        # Also output in JSON format for scripts
        print(f"\nJSON format:")
        test_credentials = {
            "email": unique_email,
            "password": test_password,
            "company": unique_company_name,
            "activation_code": activation_code
        }
        print(json.dumps(test_credentials))
        print(f"\nTest credentials:")
        print(f"  Email: {unique_email}")
        print(f"  Password: {test_password}")
        print(f"  Company: {unique_company_name}")
        
    else:
        print(f"   ✗ Login failed: {result.get('error', 'Unknown error')}")
        print("\n❌ Test company setup failed.")
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main())