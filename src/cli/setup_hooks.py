#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Setup hooks for automatic protocol registration during pip install/uninstall
"""

import os
import sys
import platform
from pathlib import Path

def post_install():
    """Post-install hook - attempt to register protocol on Windows"""
    if platform.system().lower() != 'windows':
        print("Protocol registration is only supported on Windows")
        return
    
    # Skip if we're in a virtual environment without admin privileges
    # or if this is a development install
    if hasattr(sys, 'real_prefix') or (hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix):
        print("Detected virtual environment - skipping automatic protocol registration")
        print("To register protocol manually, run: rediacc --register-protocol")
        return
    
    try:
        # Import the protocol handler
        from cli.core.protocol_handler import WindowsProtocolHandler, ProtocolHandlerError
        
        handler = WindowsProtocolHandler()
        
        # Check if we have admin privileges
        if not handler.check_admin_privileges():
            print("WARNING: Administrator privileges required for automatic protocol registration")
            print("To register protocol manually with admin privileges, run:")
            print("  rediacc --register-protocol")
            return
        
        # Check if already registered
        if handler.is_protocol_registered():
            print("rediacc:// protocol is already registered")
            return
        
        # Attempt registration
        success = handler.register_protocol(force=False)
        if success:
            print("Successfully registered rediacc:// protocol for browser integration")
            print("Restart your browser to enable rediacc:// URL support")
        else:
            print("Failed to register rediacc:// protocol")
            print("You can register it manually by running: rediacc --register-protocol")
    
    except ImportError:
        print("Protocol handler not available - this is normal for development installs")
    except ProtocolHandlerError as e:
        print(f"Protocol registration failed: {e}")
        print("You can register it manually by running: rediacc --register-protocol")
    except Exception as e:
        print(f"Unexpected error during protocol registration: {e}")
        print("You can register it manually by running: rediacc --register-protocol")

def pre_uninstall():
    """Pre-uninstall hook - attempt to unregister protocol on Windows"""
    if platform.system().lower() != 'windows':
        return
    
    try:
        # Import the protocol handler
        from cli.core.protocol_handler import WindowsProtocolHandler, ProtocolHandlerError
        
        handler = WindowsProtocolHandler()
        
        # Check if protocol is registered
        if not handler.is_protocol_registered():
            return  # Nothing to unregister
        
        # Check if we have admin privileges
        if not handler.check_admin_privileges():
            print("WARNING: Administrator privileges required for automatic protocol unregistration")
            print("To unregister protocol manually with admin privileges, run:")
            print("  rediacc --unregister-protocol")
            return
        
        # Attempt unregistration
        success = handler.unregister_protocol()
        if success:
            print("Successfully unregistered rediacc:// protocol")
        else:
            print("Failed to unregister rediacc:// protocol")
            print("You may need to unregister it manually")
    
    except ImportError:
        # This is expected during uninstall as modules may not be available
        pass
    except ProtocolHandlerError as e:
        print(f"Protocol unregistration failed: {e}")
    except Exception as e:
        # Don't fail uninstall due to protocol cleanup issues
        pass

if __name__ == "__main__":
    if len(sys.argv) > 1:
        if sys.argv[1] == "post_install":
            post_install()
        elif sys.argv[1] == "pre_uninstall":
            pre_uninstall()
        else:
            print(f"Unknown hook: {sys.argv[1]}")
            sys.exit(1)
    else:
        print("Usage: setup_hooks.py [post_install|pre_uninstall]")
        sys.exit(1)