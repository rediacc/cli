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
import json
import hashlib
import time
import logging
from pathlib import Path
from typing import Dict, Any

# Setup logging for debugging - output to stderr to avoid polluting stdout JSON
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    stream=sys.stderr
)
logger = logging.getLogger(__name__)


def get_setup_state_file() -> Path:
    """Get the path to the setup state file"""
    if platform.system().lower() == "windows":
        # Windows: use AppData/Local
        state_dir = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local")) / "rediacc"
    else:
        # Unix: use XDG_CONFIG_HOME or ~/.config
        config_home = os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")
        state_dir = Path(config_home) / "rediacc"

    state_dir.mkdir(parents=True, exist_ok=True)
    return state_dir / "setup_state.json"


def load_setup_state() -> Dict[str, Any]:
    """Load the current setup state"""
    state_file = get_setup_state_file()
    if not state_file.exists():
        return {
            "version": "1.0",
            "last_setup": None,
            "path_configured": False,
            "protocol_registered": False,
            "dependencies_checked": False,
            "setup_hash": None,
            "executable_path": None,
            "scripts_directory": None,
            "failures": [],
        }

    try:
        with open(state_file, "r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, dict):
                return data
            else:
                logger.warning("Setup state file contains invalid format, resetting...")
                return {
                    "version": "1.0",
                    "last_setup": None,
                    "path_configured": False,
                    "protocol_registered": False,
                    "dependencies_checked": False,
                    "setup_hash": None,
                    "executable_path": None,
                    "scripts_directory": None,
                    "failures": [],
                }
    except (json.JSONDecodeError, IOError):
        logger.warning("Invalid setup state file, resetting...")
        return {
            "version": "1.0",
            "last_setup": None,
            "path_configured": False,
            "protocol_registered": False,
            "dependencies_checked": False,
            "setup_hash": None,
            "executable_path": None,
            "scripts_directory": None,
            "failures": [],
        }


def save_setup_state(state: Dict[str, Any]):
    """Save the current setup state"""
    state["last_setup"] = time.time()
    state_file = get_setup_state_file()
    try:
        with open(state_file, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2)
    except IOError as e:
        logger.error(f"Failed to save setup state: {e}")


def get_current_setup_hash() -> str:
    """Generate a hash of current installation state for change detection"""
    python_exe = sys.executable
    package_location = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    # Include key installation details
    data = {
        "python_executable": python_exe,
        "package_location": package_location,
        "platform": platform.platform(),
        "python_version": sys.version,
    }

    # Add Scripts directory for Windows
    if platform.system().lower() == "windows":
        scripts_dir = get_scripts_directory()
        if scripts_dir:
            data["scripts_directory"] = str(scripts_dir)

    hash_str = json.dumps(data, sort_keys=True)
    return hashlib.sha256(hash_str.encode()).hexdigest()


def detect_windows_store_python() -> bool:
    """Detect if this is Windows Store Python installation"""
    python_exe = sys.executable
    return "Microsoft\\WindowsApps" in python_exe or "Packages\\PythonSoftwareFoundation" in python_exe


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
        result = subprocess.run(
            [sys.executable, "-m", "pip", "show", "-f", "rediacc"], capture_output=True, text=True, timeout=10
        )

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
        result = subprocess.run(["sudo", "-n", "true"], capture_output=True, timeout=5)
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


def add_to_user_path_windows(directory: Path, verbose: bool = True) -> bool:
    """
    Add directory to user PATH on Windows using registry.

    Args:
        directory: Directory to add to PATH
        verbose: Whether to show output messages

    Returns:
        True if successful, False otherwise.
    """
    if not directory.exists():
        return False

    try:
        # Query current user PATH
        result = subprocess.run(
            ["reg", "query", "HKEY_CURRENT_USER\\Environment", "/v", "PATH"], capture_output=True, text=True, timeout=10
        )

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
        result = subprocess.run(
            ["reg", "add", "HKEY_CURRENT_USER\\Environment", "/v", "PATH", "/t", "REG_EXPAND_SZ", "/d", new_path, "/f"],
            capture_output=True,
            text=True,
            timeout=30,
        )

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
                    ctypes.byref(wintypes.DWORD()),
                )

                if verbose:
                    print(f"Successfully added {directory} to user PATH", file=sys.stderr)
                    print("Note: Open a new terminal to use the 'rediacc' command.", file=sys.stderr)
                return True
            except Exception as e:
                if verbose:
                    print(f"Added to PATH but failed to broadcast change: {e}", file=sys.stderr)
                    print(f"Successfully added {directory} to user PATH", file=sys.stderr)
                    print("Note: Open a new terminal to use the 'rediacc' command.", file=sys.stderr)
                return True
        else:
            if verbose:
                print(f"Failed to add directory to PATH: {result.stderr}", file=sys.stderr)
            return False

    except (subprocess.TimeoutExpired, FileNotFoundError) as e:
        if verbose:
            print(f"Failed to modify PATH: {e}", file=sys.stderr)
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
        print("WARNING: Could not locate Python Scripts directory", file=sys.stderr)
        return

    # Check if rediacc.exe exists in scripts directory
    rediacc_exe = scripts_dir / "rediacc.exe"
    if not rediacc_exe.exists():
        print("WARNING: rediacc.exe not found in Scripts directory", file=sys.stderr)
        return

    # Check if already in PATH
    if is_directory_in_path(scripts_dir):
        print(f"Scripts directory is already in PATH: {scripts_dir}", file=sys.stderr)
        return

    # Check if rediacc is accessible via PATH (maybe through a different directory)
    rediacc_in_path = shutil.which("rediacc")
    if rediacc_in_path:
        print(f"rediacc is already accessible via PATH: {rediacc_in_path}", file=sys.stderr)
        return

    print(f"Adding Scripts directory to PATH: {scripts_dir}", file=sys.stderr)

    # Try to add to user PATH
    if add_to_user_path_windows(scripts_dir):
        print("Successfully configured PATH for rediacc access", file=sys.stderr)
    else:
        print("Failed to automatically add Scripts directory to PATH", file=sys.stderr)
        print(f"You can manually add this directory to your PATH: {scripts_dir}", file=sys.stderr)
        print("Or run rediacc using the full path:", file=sys.stderr)
        print(f'  "{rediacc_exe}" --help', file=sys.stderr)


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
        possible_locations.extend(
            [
                Path("/usr/local/bin"),  # Homebrew installation
                Path("/opt/homebrew/bin"),  # Homebrew on Apple Silicon
            ]
        )
    else:  # Linux
        possible_locations.extend(
            [
                Path("/usr/local/bin"),  # System-wide installation
                Path("/usr/bin"),  # System installation
            ]
        )

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


def add_to_shell_profile_unix(directory: Path, verbose: bool = True) -> bool:
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
                # Use conditional PATH export format for better compatibility
                path_lines = [
                    f"# Added by rediacc installation - Add {directory} to PATH for user-installed packages",
                    f'if [ -d "{directory}" ] ; then',
                    f'    PATH="{directory}:$PATH"',
                    "fi"
                ]
                path_block = "\n".join(path_lines)

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
                content += f"\n{path_block}\n"

                # Write the updated content
                profile.write_text(content)
                if verbose:
                    print(f"Added {directory} to PATH in {profile}", file=sys.stderr)
                success = True

            except Exception as e:
                if verbose:
                    print(f"Failed to update {profile}: {e}", file=sys.stderr)
                continue

        if success:
            if verbose:
                print(
                    "Note: You may need to restart your terminal or run 'source ~/.bashrc' "
                    "(or ~/.zshrc) to see the PATH changes",
                    file=sys.stderr
                )
            return True
        else:
            return False

    except Exception as e:
        if verbose:
            print(f"Failed to modify shell profiles: {e}", file=sys.stderr)
        return False


def ensure_executable_in_path_unix(verbose: bool = True):
    """
    Ensure that the rediacc executable is accessible via PATH on Unix systems.
    Only runs on Linux and macOS, and only if not already in PATH.
    """
    system = platform.system().lower()
    if system not in ["linux", "darwin"]:
        return  # Not Unix, PATH management not needed

    exec_dir = get_executable_directory_unix()
    if not exec_dir:
        if verbose:
            print("WARNING: Could not locate rediacc executable directory", file=sys.stderr)
        return

    # Check if rediacc.exe exists in executable directory
    rediacc_exe = exec_dir / "rediacc"
    if not rediacc_exe.exists():
        if verbose:
            print("WARNING: rediacc executable not found", file=sys.stderr)
        return

    # Check if already in PATH
    if is_directory_in_path_unix(exec_dir):
        if verbose:
            print(f"Executable directory is already in PATH: {exec_dir}", file=sys.stderr)
        return

    # Check if rediacc is accessible via PATH (maybe through a different directory)
    try:
        import shutil

        rediacc_in_path = shutil.which("rediacc")
        if rediacc_in_path:
            if verbose:
                print(f"rediacc is already accessible via PATH: {rediacc_in_path}", file=sys.stderr)
            return
    except Exception:
        pass

    if verbose:
        print(f"Adding executable directory to PATH: {exec_dir}", file=sys.stderr)

    # Try to add to shell profiles
    if add_to_shell_profile_unix(exec_dir, verbose):
        if verbose:
            print("Successfully configured PATH for rediacc access", file=sys.stderr)
    else:
        if verbose:
            print("Failed to automatically add executable directory to PATH", file=sys.stderr)
        if verbose:
            print(f"You can manually add this directory to your PATH: {exec_dir}", file=sys.stderr)
        if verbose:
            print("Add this line to your ~/.bashrc or ~/.zshrc:", file=sys.stderr)
        if verbose:
            print(f'export PATH="{exec_dir}:$PATH"', file=sys.stderr)
        if verbose:
            print("Or run rediacc using the full path:", file=sys.stderr)
        if verbose:
            print(f"  {rediacc_exe} --help", file=sys.stderr)


def ensure_dependencies_installed(verbose: bool = True):
    """Ensure required dependencies are available for protocol registration"""
    system = platform.system().lower()

    if system == "linux":
        # On Linux we need xdg-utils (xdg-mime) and desktop-file-utils (update-desktop-database).
        # update-mime-database (shared-mime-info) is optional but recommended.
        try:
            import subprocess
            import shutil as _shutil

            def _has(cmd: str) -> bool:
                return _shutil.which(cmd) is not None

            missing_core = []
            if not _has("xdg-mime"):
                missing_core.append("xdg-utils")  # provides xdg-mime
            if not _has("update-desktop-database"):
                missing_core.append("desktop-file-utils")  # provides update-desktop-database

            missing_optional = []
            if not _has("update-mime-database"):
                # provided by shared-mime-info
                missing_optional.append("shared-mime-info")

            if missing_core:
                print("INFO: Missing required packages for protocol registration on Linux:")
                print(f"  - {' '.join(sorted(set(missing_core)))}")

                can_install = check_passwordless_sudo()
                if can_install:
                    print("Attempting automatic installation of required packages...")

                    # Determine available package manager and install
                    installed = False
                    pkg_mgr = None
                    if _shutil.which("apt"):
                        pkg_mgr = "apt"
                        try:
                            subprocess.run(["sudo", "-n", "apt", "update"], check=True, timeout=120, capture_output=True)
                            cmd = ["sudo", "-n", "apt", "install", "-y"] + sorted(set(missing_core + missing_optional))
                            subprocess.run(cmd, check=True, timeout=600)
                            installed = True
                        except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
                            installed = False
                    elif _shutil.which("dnf"):
                        pkg_mgr = "dnf"
                        try:
                            cmd = ["sudo", "-n", "dnf", "install", "-y"] + sorted(set(missing_core + missing_optional))
                            subprocess.run(cmd, check=True, timeout=600)
                            installed = True
                        except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
                            installed = False
                    elif _shutil.which("yum"):
                        pkg_mgr = "yum"
                        try:
                            cmd = ["sudo", "-n", "yum", "install", "-y"] + sorted(set(missing_core + missing_optional))
                            subprocess.run(cmd, check=True, timeout=600)
                            installed = True
                        except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
                            installed = False
                    elif _shutil.which("pacman"):
                        pkg_mgr = "pacman"
                        try:
                            cmd = ["sudo", "-n", "pacman", "-S", "--noconfirm"] + sorted(set(missing_core + missing_optional))
                            subprocess.run(cmd, check=True, timeout=600)
                            installed = True
                        except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
                            installed = False
                    elif _shutil.which("zypper"):
                        pkg_mgr = "zypper"
                        try:
                            cmd = ["sudo", "-n", "zypper", "install", "-y"] + sorted(set(missing_core + missing_optional))
                            subprocess.run(cmd, check=True, timeout=600)
                            installed = True
                        except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
                            installed = False

                    if installed:
                        # Re-check presence
                        if _has("xdg-mime") and _has("update-desktop-database"):
                            print("Successfully installed Linux protocol registration dependencies")
                            return True
                        else:
                            print("Automatic installation completed but required commands are still missing.")
                    else:
                        print("Could not automatically install required packages.")
                        if pkg_mgr is None:
                            print("No supported package manager found (apt/dnf/yum/pacman/zypper)")
                else:
                    print("No passwordless sudo access for automatic installation.")

                # Print manual instructions
                print("Please install the following packages manually:")
                print("  Ubuntu/Debian: sudo apt install xdg-utils desktop-file-utils shared-mime-info")
                print("  Fedora/RHEL:   sudo dnf install xdg-utils desktop-file-utils shared-mime-info")
                print("  Arch:          sudo pacman -S xdg-utils desktop-file-utils shared-mime-info")
                print("  openSUSE:      sudo zypper install xdg-utils desktop-file-utils shared-mime-info")
                print("\nAfter installation, reopen your terminal and the protocol setup will complete automatically, or run:")
                print("  rediacc protocol register")
                return False
        except Exception:
            # If detection fails, don't block setup; protocol step will report precise errors
            pass

    elif system == "darwin":
        # Check for duti and offer installation guidance
        try:
            import subprocess

            result = subprocess.run(["which", "duti"], capture_output=True, timeout=5)
            if result.returncode != 0:
                if verbose:
                    print("INFO: duti not found. For enhanced protocol support, install it:", file=sys.stderr)
                if verbose:
                    print("  brew install duti", file=sys.stderr)
                if verbose:
                    print("\nProtocol registration will proceed using Launch Services...", file=sys.stderr)
        except Exception:
            pass

    return True


def attempt_protocol_registration_with_fallbacks(system: str, verbose: bool = True) -> bool:
    """Attempt protocol registration with various fallback strategies"""
    try:
        from cli.core.protocol_handler import get_platform_handler, is_protocol_supported

        if not is_protocol_supported():
            if verbose:
                print(f"Protocol registration is not supported on {system}", file=sys.stderr)
            return False

        handler = get_platform_handler()

        # Check if already registered
        if handler.is_protocol_registered():
            if verbose:
                print("rediacc:// protocol is already registered", file=sys.stderr)
            return True

        # Try user-level registration first (works without admin privileges)
        try:
            if verbose:
                print("Attempting user-level protocol registration...", file=sys.stderr)
            success = handler.register_protocol(force=False, system_wide=False)
            if success:
                if verbose:
                    print("Successfully registered rediacc:// protocol (user-level)", file=sys.stderr)
                    print_browser_restart_note(system, verbose)
                return True
        except Exception as e:
            if verbose:
                print(f"User-level registration failed: {e}", file=sys.stderr)

        # For Windows, try system-wide registration if user has admin privileges
        if system == "windows":
            try:
                if handler.check_admin_privileges():
                    if verbose:
                        print("Attempting system-wide protocol registration...", file=sys.stderr)
                    success = handler.register_protocol(force=False, system_wide=True)
                    if success:
                        if verbose:
                            print("Successfully registered rediacc:// protocol (system-wide)", file=sys.stderr)
                            print_browser_restart_note(system, verbose)
                        return True
                else:
                    if verbose:
                        print("User-level registration failed and no admin privileges for system-wide registration", file=sys.stderr)
                    if verbose:
                        print("To register manually with admin privileges, run:", file=sys.stderr)
                    if verbose:
                        print("  rediacc protocol register", file=sys.stderr)
                    return False
            except Exception as e:
                if verbose:
                    print(f"System-wide registration failed: {e}", file=sys.stderr)

        return False

    except ImportError as e:
        if verbose:
            print(f"Protocol handler not available: {e}", file=sys.stderr)
        return False
    except Exception as e:
        if verbose:
            print(f"Protocol registration error: {e}", file=sys.stderr)
        return False


def print_browser_restart_note(system: str, verbose: bool = True):
    """Print platform-specific browser restart instructions

    Args:
        system: Operating system name
        verbose: Whether to show output messages
    """
    if not verbose:
        return

    if system == "linux":
        print("Note: You may need to restart your browser to enable rediacc:// URL support", file=sys.stderr)
    elif system == "darwin":
        print("Note: You may need to restart your browser to enable rediacc:// URL support", file=sys.stderr)
    elif system == "windows":
        print("Note: Restart your browser to enable rediacc:// URL support", file=sys.stderr)


def run_post_install_hook(force: bool = False) -> bool:
    """
    Enhanced post-install hook that coordinates all setup tasks.
    Fully idempotent and handles updates/changes gracefully.

    Output is shown only when setup is actually needed (first install,
    updates, failures, or force flag). Silent during regular CLI usage.
    """
    system = platform.system().lower()

    # Skip virtual environments unless forced
    is_venv = hasattr(sys, "real_prefix") or (hasattr(sys, "base_prefix") and sys.base_prefix != sys.prefix)
    if is_venv and not force:
        logger.info("Detected virtual environment - skipping automatic setup")
        logger.info(
            'To setup manually, run: python -c "from cli.setup_hooks import run_post_install_hook; '
            'run_post_install_hook(force=True)"'
        )
        return True

    # Load current state
    state = load_setup_state()
    current_hash = get_current_setup_hash()

    # Check if we need to run setup
    needs_setup = (
        force
        or not state.get("last_setup")
        or state.get("setup_hash") != current_hash
        or state.get("failures")  # Retry if there were previous failures
    )

    # Determine if we should show output (verbose mode)
    # Only show messages during actual setup/installation, not regular CLI usage
    verbose = force or needs_setup or bool(state.get("failures"))

    if verbose:
        logger.info(f"Setting up rediacc for {system.capitalize()}...")

    if not needs_setup and state.get("path_configured") and state.get("protocol_registered"):
        if verbose:
            logger.info("Setup is current, no changes needed")
        return True

    # Clear previous failures for this run
    state["failures"] = []
    state["setup_hash"] = current_hash

    # Run setup tasks with enhanced logic (pass verbose flag)
    results = {
        "path_setup": _ensure_path_setup_enhanced(state, system, verbose),
        "dependencies": _check_dependencies_enhanced(state, system, verbose),
        "protocol": _ensure_protocol_registration_enhanced(state, system, verbose),
    }

    # Save state
    save_setup_state(state)

    # Only print summary if verbose (actual setup occurred)
    if verbose:
        print("\n" + "=" * 50, file=sys.stderr)
        print("REDIACC SETUP SUMMARY", file=sys.stderr)
        print("=" * 50, file=sys.stderr)

        for task, success in results.items():
            status = "✅ Success" if success else "❌ Failed"
            print(f"{task.replace('_', ' ').title()}: {status}", file=sys.stderr)

        if state.get("failures"):
            print("\nFailures:", file=sys.stderr)
            for failure in state["failures"]:
                print(f"  - {failure}", file=sys.stderr)

        # Check final status
        rediacc_accessible = shutil.which("rediacc")
        if rediacc_accessible:
            print("\n🎉 rediacc is ready to use!", file=sys.stderr)
            print(f"Executable: {rediacc_accessible}", file=sys.stderr)
            print("Try: rediacc --help", file=sys.stderr)
        else:
            print("\n⚠️  Setup completed with issues", file=sys.stderr)
            print("Open a new terminal to start using the 'rediacc' command.", file=sys.stderr)

    return all(results.values())


def _ensure_path_setup_enhanced(state: Dict[str, Any], system: str, verbose: bool = True) -> bool:
    """Enhanced PATH setup with state tracking

    Args:
        state: Setup state dictionary
        system: Operating system name
        verbose: Whether to show output messages
    """
    current_hash = get_current_setup_hash()
    needs_update = not state.get("path_configured") or state.get("setup_hash") != current_hash

    if system == "windows":
        scripts_dir = get_scripts_directory()
        if not scripts_dir:
            state["failures"].append("Could not locate Scripts directory")
            return False

        state["scripts_directory"] = str(scripts_dir)

        # Check if rediacc.exe exists
        rediacc_exe = scripts_dir / "rediacc.exe"
        if not rediacc_exe.exists():
            state["failures"].append("rediacc.exe not found in Scripts directory")
            return False

        # Check if already accessible
        if shutil.which("rediacc") and not needs_update:
            state["path_configured"] = True
            state["executable_path"] = shutil.which("rediacc")
            return True

        # Add to PATH if needed
        if needs_update or not is_directory_in_path(scripts_dir):
            success = add_to_user_path_windows(scripts_dir, verbose)
            state["path_configured"] = success
            if not success:
                state["failures"].append("Failed to add Scripts directory to PATH")
            return success
        return True
    else:
        # Unix systems - use existing logic with state tracking
        try:
            ensure_executable_in_path_unix(verbose)
            state["path_configured"] = bool(shutil.which("rediacc"))
            if state["path_configured"]:
                state["executable_path"] = shutil.which("rediacc")
            return bool(state["path_configured"])
        except Exception as e:
            state["failures"].append(f"Unix PATH setup failed: {e}")
            return False


def _check_dependencies_enhanced(state: Dict[str, Any], system: str, verbose: bool = True) -> bool:
    """Enhanced dependency checking with state tracking

    Args:
        state: Setup state dictionary
        system: Operating system name
        verbose: Whether to show output messages
    """
    current_hash = get_current_setup_hash()
    if state.get("dependencies_checked") and state.get("setup_hash") == current_hash:
        return True

    try:
        dependencies_ok = ensure_dependencies_installed(verbose)
        state["dependencies_checked"] = dependencies_ok
        return bool(dependencies_ok)
    except Exception as e:
        state["failures"].append(f"Dependency check failed: {e}")
        return False


def _ensure_protocol_registration_enhanced(state: Dict[str, Any], system: str, verbose: bool = True) -> bool:
    """Enhanced protocol registration with state tracking

    Args:
        state: Setup state dictionary
        system: Operating system name
        verbose: Whether to show output messages
    """
    try:
        protocol_success = attempt_protocol_registration_with_fallbacks(system, verbose)
        state["protocol_registered"] = protocol_success
        if not protocol_success:
            state["failures"].append("Protocol registration failed")
        return protocol_success
    except Exception as e:
        state["failures"].append(f"Protocol registration error: {e}")
        return False


# Legacy function for compatibility
def post_install():
    """Legacy function for compatibility"""
    return run_post_install_hook()


def post_update():
    """Post-update hook - re-register protocol with updated executable paths"""
    system = platform.system().lower()

    print(f"Updating rediacc configuration for {system.capitalize()}...", file=sys.stderr)

    # Skip if we're in a virtual environment
    if hasattr(sys, "real_prefix") or (hasattr(sys, "base_prefix") and sys.base_prefix != sys.prefix):
        print("Detected virtual environment - skipping automatic protocol update", file=sys.stderr)
        print("To update protocol manually, run: rediacc protocol register --force", file=sys.stderr)
        return

    # Re-register protocol with force flag to update executable paths
    try:
        from cli.core.protocol_handler import get_platform_handler, is_protocol_supported, ProtocolHandlerError

        if not is_protocol_supported():
            print(f"Protocol registration is not supported on {system}", file=sys.stderr)
            return

        handler = get_platform_handler()

        # Force re-registration to update executable paths
        print("Updating rediacc:// protocol registration...", file=sys.stderr)
        success = handler.register_protocol(force=True, system_wide=False)
        if success:
            print("Successfully updated rediacc:// protocol registration", file=sys.stderr)
            print_browser_restart_note(system)
        else:
            print("Failed to update rediacc:// protocol registration", file=sys.stderr)
            print("You can update it manually by running: rediacc protocol register --force", file=sys.stderr)

    except ImportError as e:
        print(f"Protocol handler not available: {e}", file=sys.stderr)
    except ProtocolHandlerError as e:
        print(f"Protocol update failed: {e}", file=sys.stderr)
        print("You can update it manually by running: rediacc protocol register --force", file=sys.stderr)
    except Exception as e:
        print(f"Unexpected error during protocol update: {e}", file=sys.stderr)
        print("You can update it manually by running: rediacc protocol register --force", file=sys.stderr)


def pre_uninstall():
    """Pre-uninstall hook - attempt to unregister protocol on all platforms"""
    system = platform.system().lower()

    print(f"Starting rediacc uninstall cleanup on {system.capitalize()}...", file=sys.stderr)

    try:
        # Import the cross-platform protocol handler
        from cli.core.protocol_handler import get_platform_handler, is_protocol_supported, ProtocolHandlerError

        if not is_protocol_supported():
            print(f"Protocol registration not supported on {system} - skipping cleanup", file=sys.stderr)
            return  # Platform not supported, nothing to do

        handler = get_platform_handler()

        # Check if protocol is registered
        if not handler.is_protocol_registered():
            print("No rediacc:// protocol registration found - nothing to clean up", file=sys.stderr)
            return  # Nothing to unregister

        print("Found rediacc:// protocol registration - cleaning up...", file=sys.stderr)

        # Attempt unregistration (try both user and system level)
        user_success = False
        system_success = False

        try:
            user_success = handler.unregister_protocol(system_wide=False)
        except Exception as e:
            print(f"User-level unregistration failed: {e}", file=sys.stderr)

        # Try system-wide unregistration if we have admin privileges
        if system == "windows" and handler.check_admin_privileges():
            try:
                system_success = handler.unregister_protocol(system_wide=True)
            except Exception as e:
                print(f"System-wide unregistration failed: {e}", file=sys.stderr)

        if user_success or system_success:
            print("Successfully unregistered rediacc:// protocol", file=sys.stderr)
        else:
            print("Protocol unregistration may have failed", file=sys.stderr)
            print("You may need to unregister manually: rediacc protocol unregister", file=sys.stderr)

    except ImportError:
        # This is expected during uninstall as modules may not be available
        pass
    except ProtocolHandlerError as e:
        print(f"Protocol unregistration failed: {e}", file=sys.stderr)
    except Exception:
        # Don't fail uninstall due to protocol cleanup issues
        pass


if __name__ == "__main__":
    if len(sys.argv) > 1:
        hook = sys.argv[1]
        force_flag = "--force" in sys.argv
        if hook == "post_install":
            success = run_post_install_hook(force=force_flag)
            sys.exit(0 if success else 1)
        elif hook == "post_update":
            success = run_post_install_hook(force=True)  # Updates always forced
            sys.exit(0 if success else 1)
        elif hook == "pre_uninstall":
            pre_uninstall()
            sys.exit(0)
        elif hook == "status":
            state = load_setup_state()
            print("Rediacc Setup Status:", file=sys.stderr)
            print(f"  Last setup: {time.ctime(state['last_setup']) if state['last_setup'] else 'Never'}", file=sys.stderr)
            print(f"  PATH configured: {state.get('path_configured', False)}", file=sys.stderr)
            print(f"  Protocol registered: {state.get('protocol_registered', False)}", file=sys.stderr)
            print(f"  Dependencies checked: {state.get('dependencies_checked', False)}", file=sys.stderr)
            print(f"  Executable accessible: {bool(shutil.which('rediacc'))}", file=sys.stderr)
            if state.get("failures"):
                print(f"  Previous failures: {len(state['failures'])}", file=sys.stderr)
                for failure in state["failures"]:
                    print(f"    - {failure}", file=sys.stderr)
            sys.exit(0)
        else:
            print(f"Unknown hook: {hook}", file=sys.stderr)
            print("Available hooks: post_install, post_update, pre_uninstall, status", file=sys.stderr)
            sys.exit(1)
    else:
        print("Usage: setup_hooks.py [post_install|post_update|pre_uninstall|status] [--force]", file=sys.stderr)
        print("\nHooks:", file=sys.stderr)
        print("  post_install  - Run after initial package installation", file=sys.stderr)
        print("  post_update   - Run after package updates to refresh protocol registration", file=sys.stderr)
        print("  pre_uninstall - Run before package uninstallation to clean up", file=sys.stderr)
        print("  status        - Show current setup status and state", file=sys.stderr)
        print("\nOptions:", file=sys.stderr)
        print("  --force       - Force setup even in virtual environments", file=sys.stderr)
        sys.exit(1)
