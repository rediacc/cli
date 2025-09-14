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

from .shared import get_logger

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
    
    def get_python_executable(self) -> str:
        """Get the current Python executable path"""
        return sys.executable
    
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
        python_exe = self.get_python_executable()
        cli_script = self.get_cli_script_path()
        
        return f"""[Desktop Entry]
Name=Rediacc Protocol Handler
Comment=Handle rediacc:// protocol URLs
Exec={python_exe} "{cli_script}" protocol-handler %u
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
                desktop_file = self.user_applications_dir / self.DESKTOP_ENTRY_ID
            
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
                applications_dir = self.user_applications_dir
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
                applications_dir = self.user_applications_dir
            
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
        
        status = {
            "registered": self.is_protocol_registered(system_wide),
            "system_wide": system_wide,
            "dependencies": deps,
            "dependencies_available": all(deps.values()),
            "python_executable": self.get_python_executable(),
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
            desktop_file = self.user_applications_dir / self.DESKTOP_ENTRY_ID
        
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