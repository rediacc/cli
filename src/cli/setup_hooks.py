#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Setup hooks for automatic protocol registration during pip install/uninstall
Enhanced with PATH detection and Windows Store Python support
"""

import os
import sys
import platform
import subprocess
import shutil
from pathlib import Path

def detect_windows_store_python() -> bool:
    """Detect if this is Windows Store Python installation"""
    python_exe = sys.executable
    return ("Microsoft\\WindowsApps" in python_exe or 
            "Packages\\PythonSoftwareFoundation" in python_exe)

def get_scripts_directory() -> Path:
    """
    Get the Scripts directory for the current Python installation.
    Works for both traditional and Windows Store Python.
    """
    python_exe = Path(sys.executable)
    python_dir = python_exe.parent
    
    # For traditional Python installations
    scripts_dir = python_dir / "Scripts"
    if scripts_dir.exists():
        return scripts_dir
    
    # For Windows Store Python installations
    if detect_windows_store_python():
        # Path structure: ...\PythonSoftwareFoundation.Python.X.Y_...\LocalCache\local-packages\PythonXYZ\Scripts
        current_path = python_dir
        while current_path.parent != current_path:  # Stop at root
            local_cache = current_path / "LocalCache" / "local-packages"
            if local_cache.exists():
                # Find PythonXYZ directory
                for python_ver_dir in local_cache.glob("Python*"):
                    scripts_dir = python_ver_dir / "Scripts"
                    if scripts_dir.exists():
                        return scripts_dir
            current_path = current_path.parent
    
    # Fallback: try to use pip to locate
    try:
        result = subprocess.run([
            sys.executable, "-m", "pip", "show", "-f", "rediacc"
        ], capture_output=True, text=True, timeout=10)
        
        if result.returncode == 0:
            for line in result.stdout.splitlines():
                if line.strip().startswith("Location:"):
                    location = line.split(":", 1)[1].strip()
                    site_packages = Path(location)
                    scripts_dir = site_packages.parent / "Scripts"
                    if scripts_dir.exists():
                        return scripts_dir
    except (subprocess.TimeoutExpired, FileNotFoundError, Exception):
        pass
    
    return None

def is_directory_in_path(directory: Path) -> bool:
    """Check if a directory is in the current PATH"""
    if not directory or not directory.exists():
        return False
    
    path_env = os.environ.get("PATH", "")
    path_dirs = [Path(p) for p in path_env.split(os.pathsep) if p.strip()]
    
    try:
        # Resolve to handle symlinks and relative paths
        resolved_dir = directory.resolve()
        for path_dir in path_dirs:
            try:
                if path_dir.resolve() == resolved_dir:
                    return True
            except (OSError, RuntimeError):
                # Handle cases where path resolution fails
                if str(path_dir).lower() == str(directory).lower():
                    return True
    except (OSError, RuntimeError):
        # Fallback to string comparison if resolve() fails
        directory_str = str(directory).lower()
        for path_dir in path_dirs:
            if str(path_dir).lower() == directory_str:
                return True
    
    return False

def add_to_user_path_windows(directory: Path) -> bool:
    """
    Add directory to user PATH on Windows using registry.
    Returns True if successful, False otherwise.
    """
    if not directory.exists():
        return False
    
    try:
        # Query current user PATH
        result = subprocess.run([
            "reg", "query", "HKEY_CURRENT_USER\\Environment",
            "/v", "PATH"
        ], capture_output=True, text=True, timeout=10)
        
        current_path = ""
        if result.returncode == 0:
            # Parse the output to extract current PATH
            for line in result.stdout.splitlines():
                if "PATH" in line and "REG_" in line:
                    parts = line.split("REG_SZ", 1)
                    if len(parts) > 1:
                        current_path = parts[1].strip()
                    elif "REG_EXPAND_SZ" in line:
                        parts = line.split("REG_EXPAND_SZ", 1)
                        if len(parts) > 1:
                            current_path = parts[1].strip()
                    break
        
        # Check if directory is already in PATH
        if current_path:
            path_parts = [p.strip() for p in current_path.split(";") if p.strip()]
            directory_str = str(directory)
            if any(p.lower() == directory_str.lower() for p in path_parts):
                return True  # Already in PATH
        
        # Add to PATH
        new_path = f"{current_path};{directory}" if current_path else str(directory)
        
        # Update user PATH in registry
        result = subprocess.run([
            "reg", "add", "HKEY_CURRENT_USER\\Environment",
            "/v", "PATH",
            "/t", "REG_EXPAND_SZ",
            "/d", new_path,
            "/f"
        ], capture_output=True, text=True, timeout=30)
        
        if result.returncode == 0:
            # Notify system of environment change
            try:
                import ctypes
                from ctypes import wintypes
                
                # Broadcast WM_SETTINGCHANGE to notify system
                HWND_BROADCAST = 0xFFFF
                WM_SETTINGCHANGE = 0x1A
                SMTO_ABORTIFHUNG = 0x0002
                
                result = ctypes.windll.user32.SendMessageTimeoutW(
                    HWND_BROADCAST,
                    WM_SETTINGCHANGE,
                    0,
                    "Environment",
                    SMTO_ABORTIFHUNG,
                    5000,  # 5 second timeout
                    ctypes.byref(wintypes.DWORD())
                )
                
                print(f"Successfully added {directory} to user PATH")
                print("Note: You may need to restart your terminal or applications to see the PATH changes")
                return True
            except Exception as e:
                print(f"Added to PATH but failed to broadcast change: {e}")
                print(f"Successfully added {directory} to user PATH")
                print("Note: Please restart your terminal to see the PATH changes")
                return True
        else:
            print(f"Failed to add directory to PATH: {result.stderr}")
            return False
            
    except (subprocess.TimeoutExpired, FileNotFoundError) as e:
        print(f"Failed to modify PATH: {e}")
        return False

def ensure_scripts_in_path():
    """
    Ensure that the Scripts directory is in PATH.
    Only applies to Windows and only if not already in PATH.
    """
    if platform.system().lower() != "windows":
        return  # Not Windows, PATH management not needed
    
    scripts_dir = get_scripts_directory()
    if not scripts_dir:
        print("WARNING: Could not locate Python Scripts directory")
        return
    
    # Check if rediacc.exe exists in scripts directory
    rediacc_exe = scripts_dir / "rediacc.exe"
    if not rediacc_exe.exists():
        print("WARNING: rediacc.exe not found in Scripts directory")
        return
    
    # Check if already in PATH
    if is_directory_in_path(scripts_dir):
        print(f"Scripts directory is already in PATH: {scripts_dir}")
        return
    
    # Check if rediacc is accessible via PATH (maybe through a different directory)
    rediacc_in_path = shutil.which("rediacc")
    if rediacc_in_path:
        print(f"rediacc is already accessible via PATH: {rediacc_in_path}")
        return
    
    print(f"Adding Scripts directory to PATH: {scripts_dir}")
    
    # Try to add to user PATH
    if add_to_user_path_windows(scripts_dir):
        print("Successfully configured PATH for rediacc access")
    else:
        print("Failed to automatically add Scripts directory to PATH")
        print(f"You can manually add this directory to your PATH: {scripts_dir}")
        print("Or run rediacc using the full path:")
        print(f"  \"{rediacc_exe}\" --help")

def post_install():
    """Post-install hook - attempt to register protocol on all platforms"""
    system = platform.system().lower()

    # Skip if we're in a virtual environment
    if hasattr(sys, 'real_prefix') or (hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix):
        print("Detected virtual environment - skipping automatic protocol registration and PATH setup")
        print("To register protocol manually, run: rediacc protocol register")
        return

    # Ensure Scripts directory is in PATH (Windows only)
    try:
        ensure_scripts_in_path()
    except Exception as e:
        print(f"Warning: Failed to setup PATH: {e}")

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