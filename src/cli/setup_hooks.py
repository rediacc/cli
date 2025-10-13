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

def check_passwordless_sudo() -> bool:
    """Check if sudo is available without password prompt.
    
    Returns:
        bool: True if passwordless sudo is available, False otherwise
    """
    try:
        # Use sudo -n (non-interactive) to test if sudo works without password
        result = subprocess.run(
            ["sudo", "-n", "true"],
            capture_output=True,
            timeout=5
        )
        return result.returncode == 0
    except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
        return False

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

def get_executable_directory_unix() -> Path:
    """
    Get the executable directory for the current Python installation on Unix systems.
    Works for various Python installations (system, user, homebrew, pyenv, conda, etc.).
    """
    python_exe = Path(sys.executable)
    python_dir = python_exe.parent
    
    # Try to find rediacc executable using similar logic to protocol handlers
    try:
        import shutil
        rediacc_path = shutil.which("rediacc")
        if rediacc_path:
            return Path(rediacc_path).parent
    except Exception:
        pass
    
    # Common Unix installation patterns
    possible_locations = [
        python_dir,  # Same directory as python
        python_dir.parent / "bin",  # Standard Unix layout
        Path.home() / ".local" / "bin",  # User installation
    ]
    
    # Add system locations
    if platform.system().lower() == "darwin":  # macOS
        possible_locations.extend([
            Path("/usr/local/bin"),  # Homebrew installation
            Path("/opt/homebrew/bin"),  # Homebrew on Apple Silicon
        ])
    else:  # Linux
        possible_locations.extend([
            Path("/usr/local/bin"),  # System-wide installation
            Path("/usr/bin"),  # System installation
        ])
    
    # Check for rediacc executable in these locations
    for location in possible_locations:
        rediacc_exe = location / "rediacc"
        if rediacc_exe.exists() and rediacc_exe.is_file():
            return location
    
    return None

def is_directory_in_path_unix(directory: Path) -> bool:
    """Check if a directory is in the current PATH on Unix systems"""
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
        directory_str = str(directory)
        for path_dir in path_dirs:
            if str(path_dir) == directory_str:
                return True
    
    return False

def add_to_shell_profile_unix(directory: Path) -> bool:
    """
    Add directory to PATH in shell profile files on Unix systems.
    Returns True if successful, False otherwise.
    """
    if not directory.exists():
        return False
    
    try:
        # Determine which shell profiles to update
        shell_profiles = []
        home = Path.home()
        
        # Common shell profile files
        possible_profiles = [
            home / ".bashrc",
            home / ".bash_profile", 
            home / ".zshrc",
            home / ".profile",
        ]
        
        # Find existing profiles or create default ones
        for profile in possible_profiles:
            if profile.exists():
                shell_profiles.append(profile)
        
        # If no profiles exist, create .bashrc and .zshrc for broad compatibility
        if not shell_profiles:
            shell_profiles = [home / ".bashrc", home / ".zshrc"]
        
        success = False
        for profile in shell_profiles:
            try:
                # Check if PATH export already exists in the file
                path_line = f'export PATH="{directory}:$PATH"'
                
                if profile.exists():
                    content = profile.read_text()
                    # Check if this directory is already in PATH in this file
                    if str(directory) in content and "PATH" in content:
                        continue  # Already added
                else:
                    content = ""
                
                # Add the PATH export
                if content and not content.endswith("\n"):
                    content += "\n"
                content += f"\n# Added by rediacc installation\n{path_line}\n"
                
                # Write the updated content
                profile.write_text(content)
                print(f"Added {directory} to PATH in {profile}")
                success = True
                
            except Exception as e:
                print(f"Failed to update {profile}: {e}")
                continue
        
        if success:
            print("Note: You may need to restart your terminal or run 'source ~/.bashrc' (or ~/.zshrc) to see the PATH changes")
            return True
        else:
            return False
            
    except Exception as e:
        print(f"Failed to modify shell profiles: {e}")
        return False

def ensure_executable_in_path_unix():
    """
    Ensure that the rediacc executable is accessible via PATH on Unix systems.
    Only runs on Linux and macOS, and only if not already in PATH.
    """
    system = platform.system().lower()
    if system not in ["linux", "darwin"]:
        return  # Not Unix, PATH management not needed
    
    exec_dir = get_executable_directory_unix()
    if not exec_dir:
        print("WARNING: Could not locate rediacc executable directory")
        return
    
    # Check if rediacc.exe exists in executable directory
    rediacc_exe = exec_dir / "rediacc"
    if not rediacc_exe.exists():
        print("WARNING: rediacc executable not found")
        return
    
    # Check if already in PATH
    if is_directory_in_path_unix(exec_dir):
        print(f"Executable directory is already in PATH: {exec_dir}")
        return
    
    # Check if rediacc is accessible via PATH (maybe through a different directory)
    try:
        import shutil
        rediacc_in_path = shutil.which("rediacc")
        if rediacc_in_path:
            print(f"rediacc is already accessible via PATH: {rediacc_in_path}")
            return
    except Exception:
        pass
    
    print(f"Adding executable directory to PATH: {exec_dir}")
    
    # Try to add to shell profiles
    if add_to_shell_profile_unix(exec_dir):
        print("Successfully configured PATH for rediacc access")
    else:
        print("Failed to automatically add executable directory to PATH")
        print(f"You can manually add this directory to your PATH: {exec_dir}")
        print("Add this line to your ~/.bashrc or ~/.zshrc:")
        print(f'export PATH="{exec_dir}:$PATH"')
        print("Or run rediacc using the full path:")
        print(f"  {rediacc_exe} --help")

def ensure_dependencies_installed():
    """Ensure required dependencies are available for protocol registration"""
    system = platform.system().lower()
    
    if system == "linux":
        # Check for xdg-utils and offer to install if missing
        try:
            import subprocess
            result = subprocess.run(["which", "xdg-mime"], capture_output=True, timeout=5)
            if result.returncode != 0:
                print("INFO: xdg-utils not found")
                
                # Check if we can install automatically (has passwordless sudo access)
                can_install = check_passwordless_sudo()
                
                if can_install:
                    print("Attempting automatic installation of xdg-utils...")
                    
                    # Try different package managers
                    package_managers = [
                        (["sudo", "apt", "update"], ["sudo", "apt", "install", "-y", "xdg-utils"]),  # Debian/Ubuntu
                        (["sudo", "dnf", "install", "-y", "xdg-utils"],),  # Fedora/RHEL
                        (["sudo", "yum", "install", "-y", "xdg-utils"],),  # Older RHEL/CentOS
                        (["sudo", "pacman", "-S", "--noconfirm", "xdg-utils"],),  # Arch
                        (["sudo", "zypper", "install", "-y", "xdg-utils"],),  # openSUSE
                    ]
                    
                    for commands in package_managers:
                        try:
                            if len(commands) == 2:  # Has update command
                                subprocess.run(commands[0], check=True, timeout=60, capture_output=True)
                                subprocess.run(commands[1], check=True, timeout=60, capture_output=True)
                            else:
                                subprocess.run(commands[0], check=True, timeout=60, capture_output=True)
                            print("Successfully installed xdg-utils")
                            return True
                        except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
                            continue
                    
                    print("Could not automatically install xdg-utils.")
                else:
                    print("No sudo access for automatic installation.")
                
                print("Please install xdg-utils manually:")
                print("  Ubuntu/Debian: sudo apt install xdg-utils")
                print("  Fedora/RHEL: sudo dnf install xdg-utils")
                print("  Arch: sudo pacman -S xdg-utils")
                print("  openSUSE: sudo zypper install xdg-utils")
                print("\nAfter installation, run: rediacc protocol register")
                return False
        except Exception:
            pass
    
    elif system == "darwin":
        # Check for duti and offer installation guidance
        try:
            import subprocess
            result = subprocess.run(["which", "duti"], capture_output=True, timeout=5)
            if result.returncode != 0:
                print("INFO: duti not found. For enhanced protocol support, install it:")
                print("  brew install duti")
                print("\nProtocol registration will proceed using Launch Services...")
        except Exception:
            pass
    
    return True

def attempt_protocol_registration_with_fallbacks(system: str) -> bool:
    """Attempt protocol registration with various fallback strategies"""
    try:
        from cli.core.protocol_handler import (
            get_platform_handler,
            is_protocol_supported,
            ProtocolHandlerError
        )

        if not is_protocol_supported():
            print(f"Protocol registration is not supported on {system}")
            return False

        handler = get_platform_handler()

        # Check if already registered
        if handler.is_protocol_registered():
            print("rediacc:// protocol is already registered")
            return True

        # Try user-level registration first (works without admin privileges)
        try:
            print("Attempting user-level protocol registration...")
            success = handler.register_protocol(force=False, system_wide=False)
            if success:
                print("Successfully registered rediacc:// protocol (user-level)")
                print_browser_restart_note(system)
                return True
        except Exception as e:
            print(f"User-level registration failed: {e}")

        # For Windows, try system-wide registration if user has admin privileges
        if system == 'windows':
            try:
                if handler.check_admin_privileges():
                    print("Attempting system-wide protocol registration...")
                    success = handler.register_protocol(force=False, system_wide=True)
                    if success:
                        print("Successfully registered rediacc:// protocol (system-wide)")
                        print_browser_restart_note(system)
                        return True
                else:
                    print("User-level registration failed and no admin privileges for system-wide registration")
                    print("To register manually with admin privileges, run:")
                    print("  rediacc protocol register")
                    return False
            except Exception as e:
                print(f"System-wide registration failed: {e}")

        return False

    except ImportError as e:
        print(f"Protocol handler not available: {e}")
        return False
    except Exception as e:
        print(f"Protocol registration error: {e}")
        return False

def print_browser_restart_note(system: str):
    """Print platform-specific browser restart instructions"""
    if system == 'linux':
        print("Note: You may need to restart your browser to enable rediacc:// URL support")
    elif system == 'darwin':
        print("Note: You may need to restart your browser to enable rediacc:// URL support")
    elif system == 'windows':
        print("Note: Restart your browser to enable rediacc:// URL support")

def post_install():
    """Post-install hook - attempt to register protocol on all platforms"""
    system = platform.system().lower()

    # Skip if we're in a virtual environment
    if hasattr(sys, 'real_prefix') or (hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix):
        print("Detected virtual environment - skipping automatic protocol registration and PATH setup")
        print("To register protocol manually, run: rediacc protocol register")
        return

    print(f"Setting up rediacc for {system.capitalize()}...")

    # Step 1: Ensure executable is in PATH for all platforms
    path_setup_success = False
    try:
        if system == "windows":
            ensure_scripts_in_path()
        else:
            ensure_executable_in_path_unix()
        path_setup_success = True
    except Exception as e:
        print(f"Warning: Failed to setup PATH: {e}")

    # Step 2: Ensure dependencies are available
    dependencies_ok = ensure_dependencies_installed()

    # Step 3: Attempt protocol registration with enhanced logic
    if dependencies_ok:
        protocol_success = attempt_protocol_registration_with_fallbacks(system)
        
        if not protocol_success:
            print("\nAutomatic protocol registration failed, but you can register manually:")
            print("  rediacc protocol register")
    else:
        print("\nSkipping automatic protocol registration due to missing dependencies.")
        print("After installing dependencies, register manually:")
        print("  rediacc protocol register")

    # Step 4: Summary
    print("\n" + "="*50)
    print("INSTALLATION SUMMARY")
    print("="*50)
    print(f"✅ PATH setup: {'Success' if path_setup_success else 'Failed (manual setup required)'}")
    print(f"✅ Dependencies: {'Available' if dependencies_ok else 'Missing (install required)'}")
    
    # Check final protocol status
    try:
        from cli.core.protocol_handler import get_platform_handler, is_protocol_supported
        if is_protocol_supported():
            handler = get_platform_handler()
            is_registered = handler.is_protocol_registered()
            print(f"✅ Protocol registration: {'Active' if is_registered else 'Manual setup required'}")
    except Exception:
        print("✅ Protocol registration: Status unknown")
    
    print("\nrediacc is ready to use!")
    if path_setup_success:
        print("Try: rediacc --help")
    else:
        print("Try: python -m cli.commands.cli_main --help")


def post_update():
    """Post-update hook - re-register protocol with updated executable paths"""
    system = platform.system().lower()
    
    print(f"Updating rediacc configuration for {system.capitalize()}...")
    
    # Skip if we're in a virtual environment
    if hasattr(sys, 'real_prefix') or (hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix):
        print("Detected virtual environment - skipping automatic protocol update")
        print("To update protocol manually, run: rediacc protocol register --force")
        return
    
    # Re-register protocol with force flag to update executable paths
    try:
        from cli.core.protocol_handler import (
            get_platform_handler,
            is_protocol_supported,
            ProtocolHandlerError
        )

        if not is_protocol_supported():
            print(f"Protocol registration is not supported on {system}")
            return

        handler = get_platform_handler()
        
        # Force re-registration to update executable paths
        print("Updating rediacc:// protocol registration...")
        success = handler.register_protocol(force=True, system_wide=False)
        if success:
            print("Successfully updated rediacc:// protocol registration")
            print_browser_restart_note(system)
        else:
            print("Failed to update rediacc:// protocol registration")
            print("You can update it manually by running: rediacc protocol register --force")

    except ImportError as e:
        print(f"Protocol handler not available: {e}")
    except ProtocolHandlerError as e:
        print(f"Protocol update failed: {e}")
        print("You can update it manually by running: rediacc protocol register --force")
    except Exception as e:
        print(f"Unexpected error during protocol update: {e}")
        print("You can update it manually by running: rediacc protocol register --force")

def pre_uninstall():
    """Pre-uninstall hook - attempt to unregister protocol on all platforms"""
    system = platform.system().lower()

    print(f"Starting rediacc uninstall cleanup on {system.capitalize()}...")

    try:
        # Import the cross-platform protocol handler
        from cli.core.protocol_handler import (
            get_platform_handler,
            is_protocol_supported,
            ProtocolHandlerError
        )

        if not is_protocol_supported():
            print(f"Protocol registration not supported on {system} - skipping cleanup")
            return  # Platform not supported, nothing to do

        handler = get_platform_handler()

        # Check if protocol is registered
        if not handler.is_protocol_registered():
            print("No rediacc:// protocol registration found - nothing to clean up")
            return  # Nothing to unregister

        print("Found rediacc:// protocol registration - cleaning up...")
        
        # Attempt unregistration (try both user and system level)
        user_success = False
        system_success = False
        
        try:
            user_success = handler.unregister_protocol(system_wide=False)
        except Exception as e:
            print(f"User-level unregistration failed: {e}")
        
        # Try system-wide unregistration if we have admin privileges
        if system == 'windows' and handler.check_admin_privileges():
            try:
                system_success = handler.unregister_protocol(system_wide=True)
            except Exception as e:
                print(f"System-wide unregistration failed: {e}")
        
        if user_success or system_success:
            print("Successfully unregistered rediacc:// protocol")
        else:
            print("Protocol unregistration may have failed")
            print("You may need to unregister manually: rediacc protocol unregister")

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
        hook = sys.argv[1]
        if hook == "post_install":
            post_install()
        elif hook == "post_update":
            post_update()
        elif hook == "pre_uninstall":
            pre_uninstall()
        else:
            print(f"Unknown hook: {hook}")
            print("Available hooks: post_install, post_update, pre_uninstall")
            sys.exit(1)
    else:
        print("Usage: setup_hooks.py [post_install|post_update|pre_uninstall]")
        print("\nHooks:")
        print("  post_install  - Run after initial package installation")
        print("  post_update   - Run after package updates to refresh protocol registration")
        print("  pre_uninstall - Run before package uninstallation to clean up")
        sys.exit(1)
