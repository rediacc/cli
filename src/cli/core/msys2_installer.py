#!/usr/bin/env python3
"""
Windows MSYS2 Installer Module

This module provides automatic MSYS2 installation with rsync support
for Windows systems, resolving the "rsync not found" issue.
"""
import os
import sys
import subprocess
import tempfile
import urllib.request
import urllib.error
from pathlib import Path
import time
from typing import Optional, Tuple
import shutil

from .config import get_logger
from .shared import is_windows

logger = get_logger(__name__)

class MSYS2Installer:
    """Automatic MSYS2 installer with rsync support"""
    
    # MSYS2 installer configuration
    INSTALLER_URL = "https://github.com/msys2/msys2-installer/releases/download/nightly-x86_64/msys2-x86_64-latest.exe"
    DEFAULT_INSTALL_DIR = "C:/msys64"
    INSTALLER_TIMEOUT = 600  # 10 minutes for installation
    PACKAGE_TIMEOUT = 300    # 5 minutes for package installation
    
    def __init__(self, install_dir: str = None, verbose: bool = False):
        """
        Initialize MSYS2 installer
        
        Args:
            install_dir: Custom installation directory (default: C:/msys64)
            verbose: Enable verbose logging
        """
        if not is_windows():
            raise RuntimeError("MSYS2 installer is only available on Windows")
            
        self.install_dir = install_dir or self.DEFAULT_INSTALL_DIR
        self.verbose = verbose
        self.install_path = Path(self.install_dir)
        self.bash_path = self.install_path / "usr" / "bin" / "bash.exe"
        self.rsync_path = self.install_path / "usr" / "bin" / "rsync.exe"
        
        if self.verbose:
            logger.setLevel(10)  # DEBUG level
    
    def is_msys2_installed(self) -> bool:
        """Check if MSYS2 is already installed"""
        return self.install_path.exists() and self.bash_path.exists()
    
    def is_rsync_available(self) -> bool:
        """Check if rsync is available in MSYS2"""
        if not self.is_msys2_installed():
            return False
        return self.rsync_path.exists()
    
    def get_rsync_path(self) -> Optional[str]:
        """Get the full path to rsync.exe if available"""
        if self.is_rsync_available():
            return str(self.rsync_path)
        return None
    
    def download_installer(self, temp_dir: Path) -> Path:
        """Download the MSYS2 installer"""
        installer_path = temp_dir / "msys2-x86_64-latest.exe"
        
        logger.info(f"Downloading MSYS2 installer...")
        logger.debug(f"URL: {self.INSTALLER_URL}")
        logger.debug(f"Target: {installer_path}")
        
        try:
            # Download with progress indication for verbose mode
            if self.verbose:
                def progress_hook(block_num, block_size, total_size):
                    if total_size > 0:
                        percent = min(100, (block_num * block_size * 100) // total_size)
                        print(f"\rDownloading: {percent}%", end="", flush=True)
                
                urllib.request.urlretrieve(self.INSTALLER_URL, installer_path, progress_hook)
                print()  # New line after progress
            else:
                urllib.request.urlretrieve(self.INSTALLER_URL, installer_path)
            
            size_mb = installer_path.stat().st_size / (1024 * 1024)
            logger.info(f"✓ Downloaded installer ({size_mb:.1f} MB)")
            return installer_path
            
        except urllib.error.URLError as e:
            logger.error(f"Failed to download MSYS2 installer: {e}")
            raise
        except Exception as e:
            logger.error(f"Download error: {e}")
            raise
    
    def install_msys2_silent(self, installer_path: Path) -> bool:
        """Install MSYS2 silently"""
        logger.info(f"Installing MSYS2 to: {self.install_dir}")
        
        # Silent installation command
        cmd = [
            str(installer_path),
            "in",  # install mode
            "--confirm-command",  # auto-confirm commands
            "--accept-messages",  # accept all messages
            "--root", self.install_dir  # installation directory
        ]
        
        logger.debug(f"Installation command: {' '.join(cmd)}")
        
        try:
            # Run the installer with timeout
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self.INSTALLER_TIMEOUT
            )
            
            logger.debug(f"Installer exit code: {result.returncode}")
            if self.verbose and result.stdout:
                logger.debug(f"Installer output: {result.stdout[-1000:]}")  # Last 1000 chars
            
            # Check if installation succeeded
            if result.returncode == 0:
                if self.install_path.exists():
                    logger.info("✓ MSYS2 installed successfully")
                    return True
                else:
                    logger.error(f"Installation reported success but directory {self.install_path} not found")
                    return False
            else:
                logger.error(f"Installation failed with exit code {result.returncode}")
                if result.stderr:
                    logger.error(f"Error output: {result.stderr}")
                return False
                
        except subprocess.TimeoutExpired:
            logger.error(f"Installation timed out after {self.INSTALLER_TIMEOUT} seconds")
            return False
        except Exception as e:
            logger.error(f"Installation failed: {e}")
            return False
    
    def update_packages_and_install_rsync(self) -> bool:
        """Update MSYS2 packages and install rsync"""
        if not self.bash_path.exists():
            logger.error(f"MSYS2 bash not found at {self.bash_path}")
            return False
        
        logger.info("Updating MSYS2 packages and installing rsync...")
        
        try:
            # Step 1: Update packages
            logger.info("Updating package database...")
            update_cmd = [
                str(self.bash_path), "-lc",
                "pacman -Syu --noconfirm"
            ]
            
            result = subprocess.run(update_cmd, capture_output=True, text=True, timeout=self.PACKAGE_TIMEOUT)
            logger.debug(f"Package update exit code: {result.returncode}")
            if self.verbose and result.stdout:
                logger.debug(f"Update output: {result.stdout[-500:]}")
            
            # Step 2: Install rsync
            logger.info("Installing rsync package...")
            install_cmd = [
                str(self.bash_path), "-lc",
                "pacman -S --noconfirm rsync"
            ]
            
            result = subprocess.run(install_cmd, capture_output=True, text=True, timeout=self.PACKAGE_TIMEOUT)
            logger.debug(f"Rsync install exit code: {result.returncode}")
            if self.verbose and result.stdout:
                logger.debug(f"Install output: {result.stdout[-500:]}")
            
            # Step 3: Verify installation
            if self.rsync_path.exists():
                logger.info("✓ rsync installed successfully")
                return True
            else:
                logger.error(f"rsync not found after installation at {self.rsync_path}")
                return False
                
        except subprocess.TimeoutExpired:
            logger.error("Package installation timed out")
            return False
        except Exception as e:
            logger.error(f"Package installation failed: {e}")
            return False
    
    def test_rsync_functionality(self) -> bool:
        """Test that rsync works correctly"""
        if not self.is_rsync_available():
            return False
        
        logger.info("Testing rsync functionality...")
        
        try:
            rsync_cmd = [
                str(self.bash_path), "-lc",
                "rsync --version"
            ]
            
            result = subprocess.run(rsync_cmd, capture_output=True, text=True, timeout=30)
            
            if result.returncode == 0:
                version_line = result.stdout.split('\n')[0]
                logger.info(f"✓ rsync is working: {version_line}")
                return True
            else:
                logger.error(f"rsync test failed: {result.stderr}")
                return False
                
        except Exception as e:
            logger.error(f"rsync test failed: {e}")
            return False
    
    def add_to_path(self) -> bool:
        """Add MSYS2 bin directories to system PATH (optional)"""
        if not self.is_msys2_installed():
            return False
        
        try:
            # Add MSYS2 paths to current session
            msys2_paths = [
                str(self.install_path / "usr" / "bin"),
                str(self.install_path / "mingw64" / "bin")
            ]
            
            current_path = os.environ.get('PATH', '')
            
            # Check if paths are already in PATH
            path_parts = current_path.split(os.pathsep)
            paths_to_add = [p for p in msys2_paths if p not in path_parts]
            
            if paths_to_add:
                new_path = os.pathsep.join(paths_to_add + [current_path])
                os.environ['PATH'] = new_path
                logger.debug(f"Added MSYS2 paths to session PATH: {paths_to_add}")
            
            return True
            
        except Exception as e:
            logger.warning(f"Failed to add MSYS2 to PATH: {e}")
            return False
    
    def install_full(self, add_to_path: bool = True) -> Tuple[bool, str]:
        """
        Complete MSYS2 installation with rsync
        
        Args:
            add_to_path: Whether to add MSYS2 to PATH for current session
            
        Returns:
            Tuple of (success: bool, message: str)
        """
        try:
            # Check if already installed and working
            if self.is_rsync_available():
                if self.test_rsync_functionality():
                    logger.info("✓ MSYS2 with rsync already installed and working")
                    if add_to_path:
                        self.add_to_path()
                    return True, "MSYS2 with rsync is already installed and working"
            
            # Check if MSYS2 is installed but rsync is missing
            if self.is_msys2_installed() and not self.is_rsync_available():
                logger.info("MSYS2 found but rsync missing, installing rsync...")
                if self.update_packages_and_install_rsync() and self.test_rsync_functionality():
                    if add_to_path:
                        self.add_to_path()
                    return True, "rsync installed successfully in existing MSYS2"
                else:
                    return False, "Failed to install rsync in existing MSYS2"
            
            # Full installation required
            logger.info("Starting MSYS2 installation...")
            
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_path = Path(temp_dir)
                
                # Step 1: Download installer
                installer_path = self.download_installer(temp_path)
                
                # Step 2: Install MSYS2
                if not self.install_msys2_silent(installer_path):
                    return False, "MSYS2 installation failed"
                
                # Step 3: Install packages
                if not self.update_packages_and_install_rsync():
                    return False, "Failed to install rsync packages"
                
                # Step 4: Test functionality
                if not self.test_rsync_functionality():
                    return False, "rsync installation verification failed"
                
                # Step 5: Add to PATH if requested
                if add_to_path:
                    self.add_to_path()
                
                return True, "MSYS2 with rsync installed successfully"
                
        except Exception as e:
            logger.error(f"Installation failed: {e}")
            return False, f"Installation error: {str(e)}"


def install_msys2_if_needed(verbose: bool = False) -> Tuple[bool, str]:
    """
    Convenience function to install MSYS2 if rsync is not available
    
    Args:
        verbose: Enable verbose logging
        
    Returns:
        Tuple of (success: bool, message: str)
    """
    if not is_windows():
        return True, "Not on Windows, MSYS2 not needed"
    
    # Check if rsync is already available in PATH
    if shutil.which('rsync'):
        return True, "rsync already available in PATH"
    
    # Try MSYS2 installation
    installer = MSYS2Installer(verbose=verbose)
    return installer.install_full()


def get_msys2_rsync_path() -> Optional[str]:
    """
    Get the path to rsync.exe in MSYS2 installation
    
    Returns:
        Path to rsync.exe or None if not found
    """
    if not is_windows():
        return None
    
    installer = MSYS2Installer()
    return installer.get_rsync_path()