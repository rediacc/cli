#!/usr/bin/env python3
"""
TOTP and Password Helper for testing Two-Factor Authentication
"""

import time
import base64
import struct
import hashlib
import hmac

# Static salt used by the Rediacc system for password hashing
STATIC_SALT = r'Rd!@cc111$ecur3P@$$w0rd$@lt#H@$h'


def hash_password(password):
    """
    Hash a password using SHA256 with the Rediacc static salt
    
    Args:
        password: The plain text password
    
    Returns:
        Hex string with 0x prefix (e.g., "0x9b6d089752b744a85c4579699574499ec4e2a581b55fc5fbf316fbb7e90f9768")
    """
    # Concatenate password with static salt before hashing
    salted_password = password + STATIC_SALT
    # Calculate SHA256 hash
    hash_bytes = hashlib.sha256(salted_password.encode()).digest()
    # Convert to hex string with 0x prefix
    return '0x' + hash_bytes.hex()


def base32_decode(encoded):
    """Decode base32 string"""
    # Add padding if needed
    missing_padding = len(encoded) % 8
    if missing_padding != 0:
        encoded += '=' * (8 - missing_padding)
    return base64.b32decode(encoded, casefold=True)


def generate_totp_code(secret, time_step=30, digits=6):
    """
    Generate a TOTP code from a secret (RFC 6238 implementation)
    
    Args:
        secret: The TOTP secret (base32 encoded)
        time_step: Time step in seconds (default 30)
        digits: Number of digits in the code (default 6)
    
    Returns:
        6-digit TOTP code as string
    """
    # Get current time counter
    counter = int(time.time()) // time_step
    
    # Decode the secret
    try:
        key = base32_decode(secret)
    except Exception:
        # If decode fails, assume it's raw bytes
        key = secret.encode() if isinstance(secret, str) else secret
    
    # Create HMAC
    counter_bytes = struct.pack('>Q', counter)
    hmac_hash = hmac.new(key, counter_bytes, hashlib.sha1).digest()
    
    # Dynamic truncation
    offset = hmac_hash[-1] & 0x0f
    truncated = hmac_hash[offset:offset + 4]
    code = struct.unpack('>I', truncated)[0]
    code &= 0x7fffffff
    code %= 10 ** digits
    
    # Return with leading zeros
    return str(code).zfill(digits)


def generate_totp_code_at_time(secret, timestamp, time_step=30, digits=6):
    """
    Generate a TOTP code for a specific timestamp
    
    Args:
        secret: The TOTP secret (base32 encoded)
        timestamp: Unix timestamp
        time_step: Time step in seconds (default 30)
        digits: Number of digits in the code (default 6)
    
    Returns:
        6-digit TOTP code as string
    """
    # Save current time
    current_time = time.time
    
    # Mock time for this calculation
    time.time = lambda: timestamp
    
    try:
        code = generate_totp_code(secret, time_step, digits)
    finally:
        # Restore time
        time.time = current_time
    
    return code


def verify_totp_code(secret, code, window=1):
    """
    Verify a TOTP code with time window tolerance
    
    Args:
        secret: The TOTP secret (base32 encoded)
        code: The code to verify
        window: Time window tolerance (default 1 = 30 seconds before/after)
    
    Returns:
        True if valid, False otherwise
    """
    current_code = generate_totp_code(secret)
    if current_code == code:
        return True
    
    # Check previous/next windows
    current_time = int(time.time())
    for i in range(1, window + 1):
        # Check past windows
        past_code = generate_totp_code_at_time(secret, current_time - (i * 30))
        if past_code == code:
            return True
        
        # Check future windows
        future_code = generate_totp_code_at_time(secret, current_time + (i * 30))
        if future_code == code:
            return True
    
    return False


def get_time_remaining():
    """
    Get the number of seconds remaining in the current TOTP time window
    
    Returns:
        Seconds remaining (0-29)
    """
    return 30 - (int(time.time()) % 30)


if __name__ == "__main__":
    # Test the TOTP helper
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python totp_helper.py <secret> [command]")
        print("Commands: generate (default), verify <code>, remaining")
        sys.exit(1)
    
    secret = sys.argv[1]
    
    if len(sys.argv) == 2 or sys.argv[2] == "generate":
        code = generate_totp_code(secret)
        print(f"TOTP Code: {code}")
        print(f"Time remaining: {get_time_remaining()}s")
    
    elif sys.argv[2] == "verify" and len(sys.argv) > 3:
        code = sys.argv[3]
        valid = verify_totp_code(secret, code)
        print(f"Code {code} is {'valid' if valid else 'invalid'}")
    
    elif sys.argv[2] == "remaining":
        print(f"Time remaining: {get_time_remaining()}s")
    
    else:
        print("Invalid command")
        sys.exit(1)