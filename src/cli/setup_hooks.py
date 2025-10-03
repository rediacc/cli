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
    """Post-install hook - attempt to register protocol on all platforms"""
    system = platform.system().lower()

    # Skip if we're in a virtual environment
    if hasattr(sys, 'real_prefix') or (hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix):
        print("Detected virtual environment - skipping automatic protocol registration")
        print("To register protocol manually, run: rediacc protocol register")
        return

    try:
        # Import the cross-platform protocol handler
        from cli.core.protocol_handler import (
            get_platform_handler,
            is_protocol_supported,
            ProtocolHandlerError
        )

        if not is_protocol_supported():
            print(f"Protocol registration is not supported on {system}")
            return

        handler = get_platform_handler()

        # Platform-specific privilege checks
        if system == 'windows':
            if not handler.check_admin_privileges():
                print("WARNING: Administrator privileges required for automatic protocol registration")
                print("To register protocol manually with admin privileges, run:")
                print("  rediacc protocol register")
                return
        elif system == 'linux':
            # Check for xdg-utils on Linux
            if not handler.check_xdg_utils_available():
                print("WARNING: xdg-utils package required for protocol registration")
                print("Install it with:")
                print("  Ubuntu/Debian: sudo apt install xdg-utils")
                print("  Fedora/RHEL: sudo dnf install xdg-utils")
                print("  Arch: sudo pacman -S xdg-utils")
                print("\nThen register manually: rediacc protocol register")
                return
        elif system == 'darwin':  # macOS
            # macOS registration can work without duti, but better with it
            if not handler.check_duti_available():
                print("INFO: For enhanced protocol support, install duti:")
                print("  brew install duti")
                print("\nProtocol registration will proceed using Launch Services...")

        # Check if already registered
        if handler.is_protocol_registered():
            print("rediacc:// protocol is already registered")
            return

        # Attempt registration (user-level)
        success = handler.register_protocol(force=False, system_wide=False)
        if success:
            print("Successfully registered rediacc:// protocol for browser integration")
            if system == 'linux':
                print("Note: You may need to restart your browser to enable rediacc:// URL support")
            elif system == 'darwin':
                print("Note: You may need to restart your browser to enable rediacc:// URL support")
            elif system == 'windows':
                print("Note: Restart your browser to enable rediacc:// URL support")
        else:
            print("Failed to register rediacc:// protocol")
            print("You can register it manually by running: rediacc protocol register")

    except ImportError as e:
        print(f"Protocol handler not available: {e}")
        print("This is normal for development installs")
    except ProtocolHandlerError as e:
        print(f"Protocol registration failed: {e}")
        print("You can register it manually by running: rediacc protocol register")
    except Exception as e:
        print(f"Unexpected error during protocol registration: {e}")
        print("You can register it manually by running: rediacc protocol register")

def pre_uninstall():
    """Pre-uninstall hook - attempt to unregister protocol on all platforms"""
    system = platform.system().lower()

    try:
        # Import the cross-platform protocol handler
        from cli.core.protocol_handler import (
            get_platform_handler,
            is_protocol_supported,
            ProtocolHandlerError
        )

        if not is_protocol_supported():
            return  # Platform not supported, nothing to do

        handler = get_platform_handler()

        # Check if protocol is registered
        if not handler.is_protocol_registered():
            return  # Nothing to unregister

        # Platform-specific privilege checks
        if system == 'windows':
            if not handler.check_admin_privileges():
                print("WARNING: Administrator privileges required for automatic protocol unregistration")
                print("To unregister protocol manually with admin privileges, run:")
                print("  rediacc protocol unregister")
                return

        # Attempt unregistration (user-level)
        success = handler.unregister_protocol(system_wide=False)
        if success:
            print("Successfully unregistered rediacc:// protocol")
        else:
            print("Failed to unregister rediacc:// protocol")
            print("You may need to unregister it manually: rediacc protocol unregister")

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