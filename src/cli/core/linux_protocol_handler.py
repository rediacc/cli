#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Linux Protocol Handler for rediacc:// URLs
Provides XDG desktop entry and MIME type management for Linux protocol registration
"""

import os
import sys
import subprocess
import shutil
from pathlib import Path
from typing import Dict, Any, Optional

from .config import get_logger

logger = get_logger(__name__)

class LinuxProtocolHandler:
    """Handles Linux XDG protocol registration for rediacc:// URLs"""
    
    PROTOCOL_SCHEME = "rediacc"
    DESKTOP_ENTRY_ID = "rediacc-protocol.desktop"
    MIME_TYPE = f"x-scheme-handler/{PROTOCOL_SCHEME}"
    
    def __init__(self):
        self.user_applications_dir = Path.home() / ".local" / "share" / "applications"
        self.user_mime_dir = Path.home() / ".local" / "share" / "mime"
        self.system_applications_dir = Path("/usr/share/applications")
        self.system_mime_dir = Path("/usr/share/mime")

    @property
    def applications_dir(self) -> Path:
        """Compatibility property for tests - returns user_applications_dir"""
        return self.user_applications_dir

    @applications_dir.setter
    def applications_dir(self, value: Path):
        """Setter for applications_dir - updates user_applications_dir"""
        self.user_applications_dir = value

    @applications_dir.deleter
    def applications_dir(self):
        """Deleter for applications_dir - allows mock to clean up"""
        pass

    def register(self, cli_path: str = None, system_wide: bool = False, force: bool = False) -> bool:
        """Compatibility method for tests - calls register_protocol()"""
        return self.register_protocol(system_wide=system_wide, force=force)

    def unregister(self, system_wide: bool = False) -> bool:
        """Compatibility method for tests - calls unregister_protocol()"""
        return self.unregister_protocol(system_wide=system_wide)

    def get_python_executable(self) -> str:
        """Get the current Python executable path"""
        return sys.executable
    
    def get_rediacc_executable_path(self) -> Optional[str]:
        """
        Get the path to the rediacc executable.
        Works for various Linux Python installations (system, user, virtualenv, conda, etc.).
        """
        try:
            # Method 1: Try using shutil.which to find rediacc in PATH
            rediacc_in_path = shutil.which("rediacc")
            if rediacc_in_path:
                return rediacc_in_path
            
            # Method 2: Try common installation locations
            python_exe = sys.executable
            python_dir = Path(python_exe).parent
            
            # For system Python installations
            possible_locations = [
                python_dir / "rediacc",  # Same directory as python
                python_dir.parent / "bin" / "rediacc",  # Standard Unix layout
                Path.home() / ".local" / "bin" / "rediacc",  # User installation
                Path("/usr/local/bin/rediacc"),  # System-wide installation
                Path("/usr/bin/rediacc"),  # System installation
            ]
            
            for location in possible_locations:
                if location.exists() and location.is_file():
                    return str(location)
            
            # Method 3: Try to use pip to locate the installed scripts
            try:
                import subprocess
                result = subprocess.run([
                    python_exe, "-m", "pip", "show", "-f", "rediacc"
                ], capture_output=True, text=True, timeout=10)
                
                if result.returncode == 0:
                    # Parse the output to find the installation location
                    for line in result.stdout.splitlines():
                        if line.strip().startswith("Location:"):
                            location = line.split(":", 1)[1].strip()
                            site_packages = Path(location)
                            
                            # Try different possible bin locations
                            bin_locations = [
                                site_packages.parent / "bin" / "rediacc",
                                site_packages.parent.parent / "bin" / "rediacc",
                                site_packages.parent / "Scripts" / "rediacc",  # Windows-style on some systems
                            ]
                            
                            for bin_loc in bin_locations:
                                if bin_loc.exists() and bin_loc.is_file():
                                    return str(bin_loc)
            except (subprocess.TimeoutExpired, FileNotFoundError, Exception) as e:
                logger.debug(f"Failed to use pip show to locate rediacc: {e}")
            
            # Method 4: Try to find based on this module's location
            try:
                this_file = Path(__file__)
                # Navigate up to find potential bin directories
                current = this_file.parent
                for _ in range(5):  # Search up to 5 levels
                    for bin_name in ["bin", "Scripts"]:
                        bin_dir = current / bin_name
                        rediacc_exe = bin_dir / "rediacc"
                        if rediacc_exe.exists() and rediacc_exe.is_file():
                            return str(rediacc_exe)
                    current = current.parent
                    if current.parent == current:  # Reached root
                        break
            except Exception as e:
                logger.debug(f"Failed to locate rediacc via module path: {e}")
            
            logger.warning("Could not locate rediacc executable")
            return None
            
        except Exception as e:
            logger.error(f"Error finding rediacc executable: {e}")
            return None
    
    def get_cli_script_path(self) -> str:
        """Get the path to the CLI main script"""
        # Try to find the CLI script in the package
        cli_module = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        cli_script = os.path.join(cli_module, "commands", "cli_main.py")
        
        if os.path.exists(cli_script):
            return cli_script
        
        # Fallback: try to use the module import path
        try:
            import cli.commands.cli_main
            return cli.commands.cli_main.__file__
        except ImportError:
            pass
        
        # Last resort: use the current file's relative path
        current_dir = Path(__file__).parent.parent
        return str(current_dir / "commands" / "cli_main.py")
    
    def get_desktop_entry_content(self) -> str:
        """Generate the desktop entry content for the protocol handler"""
        # Try to get the rediacc executable path first (preferred method)
        rediacc_exe = self.get_rediacc_executable_path()
        
        if rediacc_exe:
            # Use the rediacc executable directly
            exec_command = f"{rediacc_exe} protocol-handler %u"
        else:
            # Fallback to Python + script method (original behavior)
            logger.warning("Could not locate rediacc executable, falling back to Python script method")
            python_exe = self.get_python_executable()
            cli_script = self.get_cli_script_path()
            exec_command = f'{python_exe} "{cli_script}" protocol-handler %u'
        
        return f"""[Desktop Entry]
Name=Rediacc Protocol Handler
Comment=Handle rediacc:// protocol URLs
Exec={exec_command}
Icon=application-x-executable
StartupNotify=true
NoDisplay=true
MimeType={self.MIME_TYPE};
Type=Application
Categories=Network;
"""
    
    def check_xdg_utils_available(self) -> bool:
        """Check if xdg-utils package is available"""
        required_commands = ["xdg-mime", "update-desktop-database"]
        for cmd in required_commands:
            if not shutil.which(cmd):
                return False
        return True
    
    def check_dependencies(self) -> Dict[str, bool]:
        """Check for required dependencies"""
        deps = {
            "xdg-mime": shutil.which("xdg-mime") is not None,
            "update-desktop-database": shutil.which("update-desktop-database") is not None,
            "desktop-file-validate": shutil.which("desktop-file-validate") is not None,
        }
        return deps
    
    def is_protocol_registered(self, system_wide: bool = False) -> bool:
        """Check if the rediacc protocol is registered"""
        try:
            # Check using xdg-mime
            result = subprocess.run([
                "xdg-mime", "query", "default", self.MIME_TYPE
            ], capture_output=True, text=True, timeout=10)
            
            if result.returncode == 0 and result.stdout.strip():
                default_app = result.stdout.strip()
                return default_app == self.DESKTOP_ENTRY_ID
            
            return False
        except (subprocess.TimeoutExpired, FileNotFoundError):
            # Fallback: check if desktop file exists
            if system_wide:
                desktop_file = self.system_applications_dir / self.DESKTOP_ENTRY_ID
            else:
                desktop_file = self.applications_dir / self.DESKTOP_ENTRY_ID

            return desktop_file.exists()
    
    def register_protocol(self, system_wide: bool = False, force: bool = False) -> bool:
        """Register the rediacc:// protocol in Linux"""
        if not force and self.is_protocol_registered(system_wide):
            logger.info("Protocol already registered")
            return True
        
        if not self.check_xdg_utils_available():
            raise RuntimeError(
                "xdg-utils package required for protocol registration. "
                "Install with: sudo apt install xdg-utils (Ubuntu/Debian) or "
                "sudo dnf install xdg-utils (Fedora/RHEL) or "
                "sudo pacman -S xdg-utils (Arch)"
            )
        
        try:
            # Determine installation directories
            if system_wide:
                if os.geteuid() != 0:
                    raise PermissionError("System-wide installation requires root privileges")
                applications_dir = self.system_applications_dir
                mime_dir = self.system_mime_dir
            else:
                applications_dir = self.applications_dir
                mime_dir = self.user_mime_dir
            
            # Create directories if they don't exist
            applications_dir.mkdir(parents=True, exist_ok=True)
            
            # Create desktop entry file
            desktop_file = applications_dir / self.DESKTOP_ENTRY_ID
            desktop_content = self.get_desktop_entry_content()
            
            with open(desktop_file, 'w') as f:
                f.write(desktop_content)
            
            # Set permissions
            desktop_file.chmod(0o644)
            
            # Validate desktop file if validator is available
            if shutil.which("desktop-file-validate"):
                result = subprocess.run([
                    "desktop-file-validate", str(desktop_file)
                ], capture_output=True, text=True, timeout=10)
                
                if result.returncode != 0:
                    logger.warning(f"Desktop file validation warnings: {result.stderr}")
            
            # Register MIME type
            subprocess.run([
                "xdg-mime", "default", self.DESKTOP_ENTRY_ID, self.MIME_TYPE
            ], check=True, timeout=30)
            
            # Update desktop database
            if system_wide:
                subprocess.run([
                    "update-desktop-database", str(applications_dir)
                ], check=True, timeout=30)
            else:
                subprocess.run([
                    "update-desktop-database", str(applications_dir)
                ], check=True, timeout=30)
            
            # Update MIME database (if needed)
            try:
                subprocess.run([
                    "update-mime-database", str(mime_dir / "packages")
                ], check=True, timeout=30)
            except (subprocess.CalledProcessError, FileNotFoundError):
                # Not critical if this fails
                pass
            
            logger.info(f"Successfully registered {self.PROTOCOL_SCHEME}:// protocol")
            return True
        
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"Failed to register protocol: {e}")
        except subprocess.TimeoutExpired:
            raise RuntimeError("Protocol registration timed out")
        except PermissionError as e:
            raise RuntimeError(f"Permission denied: {e}")
    
    def unregister_protocol(self, system_wide: bool = False) -> bool:
        """Unregister the rediacc:// protocol from Linux"""
        if not self.is_protocol_registered(system_wide):
            logger.info("Protocol not registered")
            return True
        
        if not self.check_xdg_utils_available():
            raise RuntimeError("xdg-utils package required for protocol unregistration")
        
        try:
            # Determine installation directories
            if system_wide:
                if os.geteuid() != 0:
                    raise PermissionError("System-wide uninstallation requires root privileges")
                applications_dir = self.system_applications_dir
            else:
                applications_dir = self.applications_dir
            
            desktop_file = applications_dir / self.DESKTOP_ENTRY_ID
            
            # Remove desktop entry file
            if desktop_file.exists():
                desktop_file.unlink()
            
            # Unregister MIME type (set to no default)
            try:
                subprocess.run([
                    "xdg-mime", "default", "", self.MIME_TYPE
                ], timeout=30)
            except subprocess.CalledProcessError:
                # This might fail if no default was set, which is okay
                pass
            
            # Update desktop database
            subprocess.run([
                "update-desktop-database", str(applications_dir)
            ], check=True, timeout=30)
            
            logger.info(f"Successfully unregistered {self.PROTOCOL_SCHEME}:// protocol")
            return True
        
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"Failed to unregister protocol: {e}")
        except subprocess.TimeoutExpired:
            raise RuntimeError("Protocol unregistration timed out")
        except PermissionError as e:
            raise RuntimeError(f"Permission denied: {e}")
    
    def get_protocol_status(self, system_wide: bool = False) -> Dict[str, Any]:
        """Get detailed status of protocol registration"""
        deps = self.check_dependencies()
        rediacc_exe_path = self.get_rediacc_executable_path()
        
        status = {
            "registered": self.is_protocol_registered(system_wide),
            "system_wide": system_wide,
            "dependencies": deps,
            "dependencies_available": all(deps.values()),
            "python_executable": self.get_python_executable(),
            "rediacc_executable": rediacc_exe_path,
            "cli_script": self.get_cli_script_path(),
            "desktop_entry_id": self.DESKTOP_ENTRY_ID,
            "mime_type": self.MIME_TYPE,
        }
        
        # Check current MIME type handler
        try:
            result = subprocess.run([
                "xdg-mime", "query", "default", self.MIME_TYPE
            ], capture_output=True, text=True, timeout=10)
            
            if result.returncode == 0:
                status["current_handler"] = result.stdout.strip()
            else:
                status["current_handler"] = None
        except (subprocess.TimeoutExpired, FileNotFoundError):
            status["current_handler"] = None
        
        # Check if desktop file exists
        if system_wide:
            desktop_file = self.system_applications_dir / self.DESKTOP_ENTRY_ID
        else:
            desktop_file = self.applications_dir / self.DESKTOP_ENTRY_ID

        status["desktop_file_exists"] = desktop_file.exists()
        status["desktop_file_path"] = str(desktop_file)
        
        return status
    
    def get_install_instructions(self) -> list:
        """Get installation instructions for missing dependencies"""
        deps = self.check_dependencies()
        instructions = []
        
        if not deps["xdg-mime"] or not deps["update-desktop-database"]:
            instructions.extend([
                "Install xdg-utils package:",
                "  Ubuntu/Debian: sudo apt install xdg-utils",
                "  Fedora/RHEL: sudo dnf install xdg-utils", 
                "  Arch Linux: sudo pacman -S xdg-utils",
                "  openSUSE: sudo zypper install xdg-utils"
            ])
        
        if not self.is_protocol_registered():
            instructions.extend([
                "",
                "Register the protocol:",
                "  ./rediacc --register-protocol",
                "",
                "For system-wide registration (requires sudo):",
                "  sudo ./rediacc --register-protocol --system-wide"
            ])
        
        return instructions