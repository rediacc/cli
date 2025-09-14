#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
macOS Protocol Handler for rediacc:// URLs
Provides URL scheme registration for macOS using duti and LaunchServices
"""

import os
import sys
import subprocess
import shutil
import plistlib
import tempfile
from pathlib import Path
from typing import Dict, Any, Optional

from .shared import get_logger

logger = get_logger(__name__)

class MacOSProtocolHandler:
    """Handles macOS URL scheme registration for rediacc:// URLs"""
    
    PROTOCOL_SCHEME = "rediacc"
    BUNDLE_ID = "com.rediacc.cli"
    
    def __init__(self):
        self.user_launch_agents_dir = Path.home() / "Library" / "LaunchAgents"
        self.system_launch_agents_dir = Path("/Library/LaunchAgents")
    
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
    
    def check_duti_available(self) -> bool:
        """Check if duti command is available"""
        return shutil.which("duti") is not None
    
    def check_dependencies(self) -> Dict[str, bool]:
        """Check for required/optional dependencies"""
        deps = {
            "duti": self.check_duti_available(),
            "plutil": shutil.which("plutil") is not None,
            "launchctl": shutil.which("launchctl") is not None,
        }
        return deps
    
    def is_protocol_registered(self) -> bool:
        """Check if the rediacc protocol is registered"""
        try:
            if self.check_duti_available():
                # Use duti to check current handler
                result = subprocess.run([
                    "duti", "-x", self.PROTOCOL_SCHEME
                ], capture_output=True, text=True, timeout=10)
                
                if result.returncode == 0:
                    # Parse duti output to see if our bundle ID is registered
                    output = result.stdout.strip()
                    return self.BUNDLE_ID in output
            
            # Fallback: check using lsappinfo (if available)
            try:
                result = subprocess.run([
                    "lsappinfo", "info", "-only", "bundleid", self.BUNDLE_ID
                ], capture_output=True, text=True, timeout=10)
                return result.returncode == 0
            except FileNotFoundError:
                pass
            
            # Last resort: check if our launch agent exists
            user_plist = self.user_launch_agents_dir / f"{self.BUNDLE_ID}.plist"
            system_plist = self.system_launch_agents_dir / f"{self.BUNDLE_ID}.plist"
            
            return user_plist.exists() or system_plist.exists()
        
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return False
    
    def create_launch_agent_plist(self, system_wide: bool = False) -> str:
        """Create a LaunchAgent plist for the protocol handler"""
        python_exe = self.get_python_executable()
        cli_script = self.get_cli_script_path()
        
        plist_data = {
            "Label": self.BUNDLE_ID,
            "ProgramArguments": [
                python_exe,
                cli_script,
                "protocol-handler"
            ],
            "CFBundleIdentifier": self.BUNDLE_ID,
            "CFBundleURLTypes": [
                {
                    "CFBundleURLName": "Rediacc Protocol",
                    "CFBundleURLSchemes": [self.PROTOCOL_SCHEME]
                }
            ],
            "LSUIElement": True,  # Hide from Dock
            "RunAtLoad": False,   # Don't run at startup
        }
        
        # Determine plist location
        if system_wide:
            plist_dir = self.system_launch_agents_dir
        else:
            plist_dir = self.user_launch_agents_dir
        
        plist_dir.mkdir(parents=True, exist_ok=True)
        plist_path = plist_dir / f"{self.BUNDLE_ID}.plist"
        
        # Write plist file
        with open(plist_path, 'wb') as f:
            plistlib.dump(plist_data, f)
        
        return str(plist_path)
    
    def register_protocol_with_duti(self) -> bool:
        """Register protocol using duti command"""
        if not self.check_duti_available():
            return False
        
        try:
            # Register the protocol scheme with our bundle ID
            subprocess.run([
                "duti", "-s", self.BUNDLE_ID, self.PROTOCOL_SCHEME, "all"
            ], check=True, timeout=30)
            
            logger.info(f"Registered {self.PROTOCOL_SCHEME} protocol with duti")
            return True
        
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to register with duti: {e}")
            return False
    
    def register_protocol_with_launch_services(self, system_wide: bool = False) -> bool:
        """Register protocol using LaunchServices and LaunchAgent"""
        try:
            # Create LaunchAgent plist
            plist_path = self.create_launch_agent_plist(system_wide)
            
            # Load the LaunchAgent
            if system_wide:
                # System-wide requires sudo
                subprocess.run([
                    "sudo", "launchctl", "load", plist_path
                ], check=True, timeout=30)
            else:
                subprocess.run([
                    "launchctl", "load", plist_path
                ], check=True, timeout=30)
            
            # Register with Launch Services using LSRegisterURL
            # Create a temporary app bundle structure
            with tempfile.TemporaryDirectory() as temp_dir:
                app_bundle = Path(temp_dir) / "RediaccProtocol.app"
                contents_dir = app_bundle / "Contents"
                macos_dir = contents_dir / "MacOS"
                
                # Create directories
                macos_dir.mkdir(parents=True)
                
                # Create Info.plist
                info_plist = {
                    "CFBundleIdentifier": self.BUNDLE_ID,
                    "CFBundleName": "Rediacc Protocol Handler",
                    "CFBundleVersion": "1.0",
                    "CFBundleURLTypes": [
                        {
                            "CFBundleURLName": "Rediacc Protocol",
                            "CFBundleURLSchemes": [self.PROTOCOL_SCHEME]
                        }
                    ],
                    "LSUIElement": True
                }
                
                with open(contents_dir / "Info.plist", 'wb') as f:
                    plistlib.dump(info_plist, f)
                
                # Create executable script
                executable = macos_dir / "RediaccProtocol"
                executable_content = f"""#!/bin/bash
{self.get_python_executable()} "{self.get_cli_script_path()}" protocol-handler "$@"
"""
                executable.write_text(executable_content)
                executable.chmod(0o755)
                
                # Register with Launch Services
                subprocess.run([
                    "/System/Library/Frameworks/CoreServices.framework/Frameworks/LaunchServices.framework/Support/lsregister",
                    "-f", str(app_bundle)
                ], check=True, timeout=30)
            
            logger.info(f"Registered {self.PROTOCOL_SCHEME} protocol with Launch Services")
            return True
        
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to register with Launch Services: {e}")
            return False
        except PermissionError as e:
            logger.error(f"Permission denied: {e}")
            return False
    
    def register_protocol(self, system_wide: bool = False, force: bool = False) -> bool:
        """Register the rediacc:// protocol on macOS"""
        if not force and self.is_protocol_registered():
            logger.info("Protocol already registered")
            return True
        
        # Try duti first (simpler and more reliable)
        if self.register_protocol_with_duti():
            return True
        
        # Fallback to Launch Services registration
        logger.info("duti not available, trying Launch Services registration")
        return self.register_protocol_with_launch_services(system_wide)
    
    def unregister_protocol(self, system_wide: bool = False) -> bool:
        """Unregister the rediacc:// protocol from macOS"""
        if not self.is_protocol_registered():
            logger.info("Protocol not registered")
            return True
        
        try:
            success = True
            
            # Remove LaunchAgent if it exists
            if system_wide:
                plist_path = self.system_launch_agents_dir / f"{self.BUNDLE_ID}.plist"
            else:
                plist_path = self.user_launch_agents_dir / f"{self.BUNDLE_ID}.plist"
            
            if plist_path.exists():
                try:
                    # Unload LaunchAgent first
                    if system_wide:
                        subprocess.run([
                            "sudo", "launchctl", "unload", str(plist_path)
                        ], timeout=30)
                    else:
                        subprocess.run([
                            "launchctl", "unload", str(plist_path)
                        ], timeout=30)
                except subprocess.CalledProcessError:
                    # Unload might fail if not loaded, continue anyway
                    pass
                
                # Remove plist file
                plist_path.unlink()
            
            # Try to unregister with duti if available
            if self.check_duti_available():
                try:
                    # duti doesn't have a direct unregister, but we can register a different default
                    # For now, we'll just rely on the plist removal
                    pass
                except subprocess.CalledProcessError:
                    success = False
            
            if success:
                logger.info(f"Successfully unregistered {self.PROTOCOL_SCHEME}:// protocol")
            
            return success
        
        except Exception as e:
            logger.error(f"Failed to unregister protocol: {e}")
            return False
    
    def get_protocol_status(self, system_wide: bool = False) -> Dict[str, Any]:
        """Get detailed status of protocol registration"""
        deps = self.check_dependencies()
        
        status = {
            "registered": self.is_protocol_registered(),
            "system_wide": system_wide,
            "dependencies": deps,
            "python_executable": self.get_python_executable(),
            "cli_script": self.get_cli_script_path(),
            "bundle_id": self.BUNDLE_ID,
            "protocol_scheme": self.PROTOCOL_SCHEME,
        }
        
        # Check current protocol handler
        if self.check_duti_available():
            try:
                result = subprocess.run([
                    "duti", "-x", self.PROTOCOL_SCHEME
                ], capture_output=True, text=True, timeout=10)
                
                if result.returncode == 0:
                    status["current_handler_info"] = result.stdout.strip()
                else:
                    status["current_handler_info"] = None
            except (subprocess.TimeoutExpired, FileNotFoundError):
                status["current_handler_info"] = None
        else:
            status["current_handler_info"] = "duti not available"
        
        # Check if LaunchAgent exists
        if system_wide:
            plist_path = self.system_launch_agents_dir / f"{self.BUNDLE_ID}.plist"
        else:
            plist_path = self.user_launch_agents_dir / f"{self.BUNDLE_ID}.plist"
        
        status["launch_agent_exists"] = plist_path.exists()
        status["launch_agent_path"] = str(plist_path)
        
        return status
    
    def get_install_instructions(self) -> list:
        """Get installation instructions for missing dependencies"""
        deps = self.check_dependencies()
        instructions = []
        
        if not deps["duti"]:
            instructions.extend([
                "For enhanced protocol registration, install duti:",
                "  brew install duti",
                "",
                "Alternatively, the CLI can register protocols without duti",
                "using the built-in Launch Services integration."
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