#!/usr/bin/env python3
"""
Terminal Detector - Tests and caches working terminal launch methods
"""

import os
import sys
import json
import subprocess
import time
import tempfile
from pathlib import Path
from typing import Dict, Optional, List, Tuple
from datetime import datetime, timedelta
from config_path import get_config_dir, get_config_file

# Import logging configuration
from logging_config import get_logger


class TerminalDetector:
    """Detects and caches working terminal launch methods for the current system"""
    
    # Use centralized config directory
    CACHE_FILE = str(get_config_file("terminal_detector_cache.json"))
    CACHE_DURATION = timedelta(days=7)  # Re-test methods after a week
    
    def __init__(self):
        self.logger = get_logger(__name__)
        self.cache_dir = os.path.dirname(self.CACHE_FILE)
        if not os.path.exists(self.cache_dir):
            os.makedirs(self.cache_dir, exist_ok=True)
        
        # Check if running in WSL
        is_wsl = self._is_wsl()
        
        self.methods = {
            'win32': [
                ('msys2_mintty', self._test_msys2_mintty),
                ('wsl_wt', self._test_wsl_windows_terminal),
                ('wsl_powershell', self._test_wsl_powershell),
                ('msys2_wt', self._test_msys2_windows_terminal),
                ('msys2_bash', self._test_msys2_bash_direct),
                ('powershell', self._test_powershell_direct),
                ('cmd', self._test_cmd_direct)
            ],
            'darwin': [
                ('terminal_app', self._test_macos_terminal)
            ],
            'linux': [
                # If in WSL, prioritize Windows terminal methods
                ('wsl_wt', self._test_wsl_windows_terminal),
                ('wsl_powershell', self._test_wsl_powershell),
                ('wsl_cmd', self._test_wsl_cmd),
                ('gnome_terminal', self._test_gnome_terminal),
                ('konsole', self._test_konsole),
                ('xfce4_terminal', self._test_xfce4_terminal),
                ('mate_terminal', self._test_mate_terminal),
                ('terminator', self._test_terminator),
                ('xterm', self._test_xterm)
            ] if is_wsl else [
                # Regular Linux
                ('gnome_terminal', self._test_gnome_terminal),
                ('konsole', self._test_konsole),
                ('xfce4_terminal', self._test_xfce4_terminal),
                ('mate_terminal', self._test_mate_terminal),
                ('terminator', self._test_terminator),
                ('xterm', self._test_xterm)
            ]
        }
        
        # Load cache
        self.cache = self._load_cache()
    
    def _load_cache(self) -> Dict:
        """Load cached detection results"""
        try:
            if os.path.exists(self.CACHE_FILE):
                with open(self.CACHE_FILE, 'r') as f:
                    return json.load(f)
        except Exception as e:
            self.logger.debug(f"Failed to load cache: {e}")
        return {}
    
    def _save_cache(self):
        """Save detection results to cache"""
        try:
            with open(self.CACHE_FILE, 'w') as f:
                json.dump(self.cache, f, indent=2)
        except Exception as e:
            self.logger.error(f"Failed to save cache: {e}")
    
    def _is_cache_valid(self, platform: str) -> bool:
        """Check if cached results are still valid"""
        if platform not in self.cache:
            return False
        
        cached_time = self.cache[platform].get('timestamp')
        if not cached_time:
            return False
        
        try:
            cached_datetime = datetime.fromisoformat(cached_time)
            return datetime.now() - cached_datetime < self.CACHE_DURATION
        except:
            return False
    
    def _find_msys2_installation(self) -> Optional[str]:
        """Find MSYS2 installation path"""
        msys2_paths = [
            'C:\\msys64',
            'C:\\msys2',
            os.path.expanduser('~\\msys64'),
            os.path.expanduser('~\\msys2'),
        ]
        
        # Check MSYS2_ROOT environment variable
        msys2_root = os.environ.get('MSYS2_ROOT')
        if msys2_root:
            msys2_paths.insert(0, msys2_root)
        
        for path in msys2_paths:
            if os.path.exists(path):
                return path
        return None
    
    def _is_wsl(self) -> bool:
        """Check if running in WSL"""
        try:
            with open('/proc/version', 'r') as f:
                return 'microsoft' in f.read().lower()
        except:
            return False
    
    def _test_command(self, cmd: List[str], timeout: float = 3.0, 
                     expect_running: bool = True) -> Tuple[bool, str]:
        """Test if a command works
        
        Args:
            cmd: Command to test
            timeout: How long to wait for the command
            expect_running: If True, command should still be running after timeout
                          If False, command should complete successfully
        
        Returns:
            Tuple of (success, method_description)
        """
        try:
            # Create a test script that exits cleanly
            # Use .bat on Windows for methods that don't use bash
            is_bash_method = any(x in str(cmd) for x in ['bash', 'msys', 'wsl'])
            suffix = '.sh' if is_bash_method else ('.bat' if sys.platform == 'win32' else '.sh')
            
            with tempfile.NamedTemporaryFile(mode='w', suffix=suffix, delete=False) as f:
                if suffix == '.bat':
                    f.write('@echo off\necho Terminal detection test successful\nexit /b 0\n')
                else:
                    f.write('#!/bin/bash\necho "Terminal detection test successful"\nexit 0\n')
                test_script = f.name
            
            os.chmod(test_script, 0o755)
            
            # Replace placeholder in command with actual test script
            test_cmd = []
            for arg in cmd:
                if 'TEST_SCRIPT' in arg:
                    # Check if this is for MSYS2 and needs path conversion
                    if ('msys' in cmd[0].lower() or 
                        (len(cmd) > 2 and 'bash' in cmd[0] and '/msys' in cmd[0])):
                        # Convert to MSYS2 path format
                        msys2_path = self._windows_to_msys2_path(test_script)
                        test_cmd.append(arg.replace('TEST_SCRIPT', msys2_path))
                    else:
                        test_cmd.append(arg.replace('TEST_SCRIPT', test_script))
                else:
                    test_cmd.append(arg)
            
            self.logger.debug(f"Testing command: {' '.join(test_cmd[:3])}...")
            
            process = subprocess.Popen(
                test_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0
            )
            
            try:
                stdout, stderr = process.communicate(timeout=timeout)
                
                # Clean up test script
                try:
                    os.unlink(test_script)
                except:
                    pass
                
                if expect_running:
                    # Process should have timed out (still running)
                    return (False, "Process completed when it should be running")
                else:
                    # Process should have completed successfully
                    if process.returncode == 0:
                        return (True, "Command executed successfully")
                    else:
                        error_info = f"Command failed with code {process.returncode}"
                        if stderr:
                            error_info += f" - stderr: {stderr.decode()[:100]}"
                        return (False, error_info)
                        
            except subprocess.TimeoutExpired:
                # Kill the process
                process.kill()
                
                # Schedule cleanup for later (in case file is in use)
                self._schedule_cleanup(test_script)
                
                if expect_running:
                    # This is expected - terminal is running
                    return (True, "Terminal launched successfully")
                else:
                    # This is unexpected - command should have completed
                    return (False, "Command timed out unexpectedly")
                    
        except Exception as e:
            # Clean up test script if it exists
            if 'test_script' in locals():
                self._schedule_cleanup(test_script)
            return (False, f"Exception: {str(e)}")
    
    def _schedule_cleanup(self, filepath: str):
        """Schedule file cleanup after a delay"""
        def cleanup():
            time.sleep(5)
            try:
                if os.path.exists(filepath):
                    os.unlink(filepath)
            except:
                pass
        
        import threading
        cleanup_thread = threading.Thread(target=cleanup)
        cleanup_thread.daemon = True
        cleanup_thread.start()
    
    # Windows terminal tests
    def _test_msys2_mintty(self) -> Tuple[bool, str]:
        """Test MSYS2 mintty terminal"""
        msys2_path = self._find_msys2_installation()
        if not msys2_path:
            return (False, "MSYS2 not found")
        
        mintty_exe = os.path.join(msys2_path, 'usr', 'bin', 'mintty.exe')
        if not os.path.exists(mintty_exe):
            return (False, "mintty.exe not found")
        
        # Simple test: just check if mintty can be launched
        # We can't reliably test if it stays open, so just verify it starts
        try:
            # Test with a simple echo command
            bash_exe = os.path.join(msys2_path, 'usr', 'bin', 'bash.exe')
            test_cmd = [mintty_exe, '--version']
            process = subprocess.Popen(
                test_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0
            )
            stdout, stderr = process.communicate(timeout=2)
            if process.returncode == 0:
                return (True, "mintty is available")
            else:
                return (False, f"mintty test failed with code {process.returncode}")
        except Exception as e:
            return (False, f"Failed to test mintty: {str(e)}")
    
    def _test_wsl_windows_terminal(self) -> Tuple[bool, str]:
        """Test WSL with Windows Terminal"""
        # Check if Windows Terminal is available
        try:
            test_cmd = ['cmd.exe', '/c', 'where', 'wt.exe']
            process = subprocess.Popen(
                test_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            stdout, stderr = process.communicate(timeout=2)
            if process.returncode == 0:
                return (True, "Windows Terminal is available in WSL")
            else:
                return (False, "Windows Terminal not found in WSL")
        except Exception as e:
            return (False, f"Failed to test Windows Terminal: {str(e)}")
    
    def _test_wsl_powershell(self) -> Tuple[bool, str]:
        """Test WSL with PowerShell"""
        try:
            # Simple test to see if powershell.exe is available
            test_cmd = ['powershell.exe', '-Command', 'echo "test"']
            process = subprocess.Popen(
                test_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            stdout, stderr = process.communicate(timeout=2)
            if process.returncode == 0:
                return (True, "PowerShell is available in WSL")
            else:
                return (False, "PowerShell not accessible from WSL")
        except Exception as e:
            return (False, f"Failed to test PowerShell: {str(e)}")
    
    def _test_wsl_cmd(self) -> Tuple[bool, str]:
        """Test WSL with cmd.exe"""
        try:
            # Simple test to see if cmd.exe is available
            test_cmd = ['cmd.exe', '/c', 'echo test']
            process = subprocess.Popen(
                test_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            stdout, stderr = process.communicate(timeout=2)
            if process.returncode == 0:
                return (True, "cmd.exe is available in WSL")
            else:
                return (False, "cmd.exe not accessible from WSL")
        except Exception as e:
            return (False, f"Failed to test cmd.exe: {str(e)}")
    
    def _test_msys2_windows_terminal(self) -> Tuple[bool, str]:
        """Test MSYS2 with Windows Terminal"""
        msys2_path = self._find_msys2_installation()
        if not msys2_path:
            return (False, "MSYS2 not found")
        
        bash_exe = os.path.join(msys2_path, 'usr', 'bin', 'bash.exe')
        if not os.path.exists(bash_exe):
            return (False, "bash.exe not found")
        
        # Check if Windows Terminal is available
        try:
            # Test if wt.exe exists in PATH
            test_cmd = ['where', 'wt.exe']
            process = subprocess.Popen(
                test_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0
            )
            stdout, stderr = process.communicate(timeout=2)
            if process.returncode == 0:
                return (True, "Windows Terminal is available")
            else:
                return (False, "Windows Terminal (wt.exe) not found in PATH")
        except Exception as e:
            return (False, f"Failed to test Windows Terminal: {str(e)}")
    
    def _test_msys2_bash_direct(self) -> Tuple[bool, str]:
        """Test MSYS2 bash directly"""
        msys2_path = self._find_msys2_installation()
        if not msys2_path:
            return (False, "MSYS2 not found")
        
        bash_exe = os.path.join(msys2_path, 'usr', 'bin', 'bash.exe')
        if not os.path.exists(bash_exe):
            return (False, "bash.exe not found")
        
        # Use -l flag for login shell to ensure proper environment
        cmd = [bash_exe, '-l', '-c', 'TEST_SCRIPT']
        return self._test_command(cmd, expect_running=False)
    
    def _test_powershell_direct(self) -> Tuple[bool, str]:
        """Test PowerShell directly"""
        cmd = ['powershell.exe', '-Command', '& TEST_SCRIPT']
        return self._test_command(cmd, expect_running=False)
    
    def _test_cmd_direct(self) -> Tuple[bool, str]:
        """Test cmd.exe directly"""
        cmd = ['cmd.exe', '/c', 'TEST_SCRIPT']
        return self._test_command(cmd, expect_running=False)
    
    # macOS terminal test
    def _test_macos_terminal(self) -> Tuple[bool, str]:
        """Test macOS Terminal.app"""
        cmd = ['open', '-a', 'Terminal', 'TEST_SCRIPT']
        return self._test_command(cmd, expect_running=True)
    
    # Linux terminal tests
    def _test_gnome_terminal(self) -> Tuple[bool, str]:
        """Test GNOME Terminal"""
        cmd = ['gnome-terminal', '--', 'bash', 'TEST_SCRIPT']
        return self._test_command(cmd, expect_running=True)
    
    def _test_konsole(self) -> Tuple[bool, str]:
        """Test KDE Konsole"""
        cmd = ['konsole', '-e', 'bash', 'TEST_SCRIPT']
        return self._test_command(cmd, expect_running=True)
    
    def _test_xfce4_terminal(self) -> Tuple[bool, str]:
        """Test XFCE4 Terminal"""
        cmd = ['xfce4-terminal', '-e', 'bash TEST_SCRIPT']
        return self._test_command(cmd, expect_running=True)
    
    def _test_mate_terminal(self) -> Tuple[bool, str]:
        """Test MATE Terminal"""
        cmd = ['mate-terminal', '-e', 'bash TEST_SCRIPT']
        return self._test_command(cmd, expect_running=True)
    
    def _test_terminator(self) -> Tuple[bool, str]:
        """Test Terminator"""
        cmd = ['terminator', '-e', 'bash TEST_SCRIPT']
        return self._test_command(cmd, expect_running=True)
    
    def _test_xterm(self) -> Tuple[bool, str]:
        """Test XTerm"""
        cmd = ['xterm', '-e', 'bash', 'TEST_SCRIPT']
        return self._test_command(cmd, expect_running=True)
    
    def detect(self, force_refresh: bool = False) -> Optional[str]:
        """Detect the best working terminal method
        
        Args:
            force_refresh: Force re-detection even if cache is valid
            
        Returns:
            The name of the best working method, or None if none work
        """
        platform = sys.platform
        
        # Normalize platform
        if platform.startswith('linux'):
            platform = 'linux'
        
        # Check cache
        if not force_refresh and self._is_cache_valid(platform):
            cached_method = self.cache[platform].get('method')
            if cached_method:
                self.logger.debug(f"Using cached method: {cached_method}")
                return cached_method
        
        # Get methods for this platform
        platform_methods = self.methods.get(platform, [])
        if not platform_methods:
            self.logger.warning(f"No methods defined for platform: {platform}")
            return None
        
        self.logger.debug(f"Testing {len(platform_methods)} methods for {platform}...")
        
        # Test each method
        working_methods = []
        for method_name, test_func in platform_methods:
            success, description = test_func()
            if success:
                self.logger.debug(f"[OK] {method_name}: {description}")
                working_methods.append(method_name)
            else:
                self.logger.debug(f"[FAIL] {method_name}: {description}")
        
        # Select the best method (first working one)
        best_method = working_methods[0] if working_methods else None
        
        # Update cache
        self.cache[platform] = {
            'method': best_method,
            'working_methods': working_methods,
            'timestamp': datetime.now().isoformat(),
            'platform': platform
        }
        self._save_cache()
        
        if best_method:
            self.logger.info(f"Selected terminal method: {best_method}")
        else:
            self.logger.warning("No working terminal methods found!")
        
        return best_method
    
    def get_launch_function(self, method_name: str):
        """Get the launch function for a specific method
        
        Returns a function that takes (cli_dir, command, description) and launches a terminal
        """
        launch_functions = {
            # Windows methods
            'msys2_mintty': self._launch_msys2_mintty,
            'wsl_wt': self._launch_wsl_windows_terminal,
            'wsl_powershell': self._launch_wsl_powershell,
            'wsl_cmd': self._launch_wsl_cmd,
            'msys2_wt': self._launch_msys2_windows_terminal,
            'msys2_bash': self._launch_msys2_bash_direct,
            'powershell': self._launch_powershell_direct,
            'cmd': self._launch_cmd_direct,
            # macOS methods
            'terminal_app': self._launch_macos_terminal,
            # Linux methods
            'gnome_terminal': self._launch_gnome_terminal,
            'konsole': self._launch_konsole,
            'xfce4_terminal': self._launch_xfce4_terminal,
            'mate_terminal': self._launch_mate_terminal,
            'terminator': self._launch_terminator,
            'xterm': self._launch_xterm
        }
        
        return launch_functions.get(method_name)
    
    def _windows_to_msys2_path(self, windows_path: str) -> str:
        """Convert Windows path to MSYS2 format"""
        if len(windows_path) >= 2 and windows_path[1] == ':':
            drive = windows_path[0].lower()
            rest = windows_path[2:].replace('\\', '/')
            return f'/{drive}{rest}'
        return windows_path.replace('\\', '/')
    
    # Launch functions for each method
    def _launch_msys2_mintty(self, cli_dir: str, command: str, description: str):
        """Launch using MSYS2 mintty"""
        msys2_path = self._find_msys2_installation()
        mintty_exe = os.path.join(msys2_path, 'usr', 'bin', 'mintty.exe')
        bash_exe = os.path.join(msys2_path, 'usr', 'bin', 'bash.exe')
        msys2_cli_dir = self._windows_to_msys2_path(cli_dir)
        
        import shlex
        cmd_parts = shlex.split(command)
        if cmd_parts[0] == 'term':
            cli_script = f'{msys2_cli_dir}/src/cli/rediacc-cli-term.py'
            args = cmd_parts[1:]
        elif cmd_parts[0] == 'sync':
            cli_script = f'{msys2_cli_dir}/src/cli/rediacc-cli-sync.py'
            args = cmd_parts[1:]
        else:
            cli_script = f'{msys2_cli_dir}/src/cli/rediacc-cli.py'
            args = cmd_parts
        
        escaped_args = ' '.join(shlex.quote(arg) for arg in args)
        bash_cmd = f'cd "{msys2_cli_dir}" && python3 {cli_script} {escaped_args}'
        
        # Launch maximized with -w max option
        subprocess.Popen([mintty_exe, '-w', 'max', '-e', bash_exe, '-l', '-c', bash_cmd])
    
    def _launch_wsl_windows_terminal(self, cli_dir: str, command: str, description: str):
        """Launch using WSL with Windows Terminal"""
        # Parse command to determine which CLI script to use
        import shlex
        try:
            cmd_parts = shlex.split(command)
        except:
            # If shlex fails, do simple split
            cmd_parts = command.split()
        
        # Determine the correct CLI script based on command
        if cmd_parts and cmd_parts[0] == 'term':
            cli_script = './src/cli/rediacc-cli-term.py'
            args = ' '.join(shlex.quote(arg) for arg in cmd_parts[1:])
        elif cmd_parts and cmd_parts[0] == 'sync':
            cli_script = './src/cli/rediacc-cli-sync.py'
            args = ' '.join(shlex.quote(arg) for arg in cmd_parts[1:])
        else:
            cli_script = './rediacc'
            args = command
        
        # Build the WSL command
        wsl_command = f'cd {cli_dir} && {cli_script} {args}'
        
        # Launch Windows Terminal maximized with WSL command
        wt_cmd = ['wt.exe', '--maximized', 'new-tab', 'wsl.exe', '-e', 'bash', '-c', wsl_command]
        
        try:
            # Launch directly without cmd.exe to avoid UNC path warning
            subprocess.Popen(wt_cmd)
        except Exception as e:
            # Fallback to cmd.exe method if direct launch fails
            cmd_str = f'wt.exe --maximized new-tab wsl.exe -e bash -c "{wsl_command}"'
            subprocess.Popen(['cmd.exe', '/c', cmd_str], cwd=os.environ.get('WINDIR', 'C:\\Windows'))
    
    def _launch_wsl_powershell(self, cli_dir: str, command: str, description: str):
        """Launch using WSL with PowerShell"""
        # Parse command to determine which CLI script to use
        import shlex
        try:
            cmd_parts = shlex.split(command)
        except:
            cmd_parts = command.split()
        
        # Determine the correct CLI script
        if cmd_parts and cmd_parts[0] == 'term':
            cli_script = './src/cli/rediacc-cli-term.py'
            args = ' '.join(shlex.quote(arg) for arg in cmd_parts[1:])
        elif cmd_parts and cmd_parts[0] == 'sync':
            cli_script = './src/cli/rediacc-cli-sync.py'
            args = ' '.join(shlex.quote(arg) for arg in cmd_parts[1:])
        else:
            cli_script = './rediacc'
            args = command
        
        # Use PowerShell's Start-Process to avoid UNC path issues, launch maximized
        ps_cmd = f'Start-Process wsl -WindowStyle Maximized -ArgumentList "-e", "bash", "-c", "cd {cli_dir} && {cli_script} {args}"'
        # Set working directory to Windows directory to avoid UNC warning
        subprocess.Popen(['powershell.exe', '-Command', ps_cmd], 
                        cwd=os.environ.get('WINDIR', 'C:\\Windows'))
    
    def _launch_wsl_cmd(self, cli_dir: str, command: str, description: str):
        """Launch using WSL with cmd.exe"""
        # Parse command to determine which CLI script to use
        import shlex
        try:
            cmd_parts = shlex.split(command)
        except:
            cmd_parts = command.split()
        
        # Determine the correct CLI script
        if cmd_parts and cmd_parts[0] == 'term':
            cli_script = './src/cli/rediacc-cli-term.py'
            args = ' '.join(f'"{arg}"' if ' ' in arg else arg for arg in cmd_parts[1:])
        elif cmd_parts and cmd_parts[0] == 'sync':
            cli_script = './src/cli/rediacc-cli-sync.py'
            args = ' '.join(f'"{arg}"' if ' ' in arg else arg for arg in cmd_parts[1:])
        else:
            cli_script = './rediacc'
            args = command
        
        # Use start with /D to set working directory and /max to maximize
        cmd_cmd = f'start /max "WSL Terminal" /D "%WINDIR%" wsl bash -c "cd {cli_dir} && {cli_script} {args}"'
        subprocess.Popen(['cmd.exe', '/c', cmd_cmd])
    
    def _launch_msys2_windows_terminal(self, cli_dir: str, command: str, description: str):
        """Launch using MSYS2 with Windows Terminal"""
        msys2_path = self._find_msys2_installation()
        bash_exe = os.path.join(msys2_path, 'usr', 'bin', 'bash.exe')
        msys2_cli_dir = self._windows_to_msys2_path(cli_dir)
        
        import shlex
        cmd_parts = shlex.split(command)
        if cmd_parts[0] == 'term':
            cli_script = f'{msys2_cli_dir}/src/cli/rediacc-cli-term.py'
            args = cmd_parts[1:]
        elif cmd_parts[0] == 'sync':
            cli_script = f'{msys2_cli_dir}/src/cli/rediacc-cli-sync.py'
            args = cmd_parts[1:]
        else:
            cli_script = f'{msys2_cli_dir}/src/cli/rediacc-cli.py'
            args = cmd_parts
        
        escaped_args = ' '.join(shlex.quote(arg) for arg in args)
        bash_cmd = f'cd "{msys2_cli_dir}" && python3 {cli_script} {escaped_args}'
        wt_cmd = f'wt.exe --maximized new-tab "{bash_exe}" -l -c "{bash_cmd}"'
        
        subprocess.Popen(['cmd.exe', '/c', wt_cmd])
    
    def _launch_msys2_bash_direct(self, cli_dir: str, command: str, description: str):
        """Launch using MSYS2 bash directly (no new window)"""
        msys2_path = self._find_msys2_installation()
        bash_exe = os.path.join(msys2_path, 'usr', 'bin', 'bash.exe')
        msys2_cli_dir = self._windows_to_msys2_path(cli_dir)
        
        import shlex
        cmd_parts = shlex.split(command)
        if cmd_parts[0] == 'term':
            cli_script = f'{msys2_cli_dir}/src/cli/rediacc-cli-term.py'
            args = cmd_parts[1:]
        elif cmd_parts[0] == 'sync':
            cli_script = f'{msys2_cli_dir}/src/cli/rediacc-cli-sync.py'
            args = cmd_parts[1:]
        else:
            cli_script = f'{msys2_cli_dir}/src/cli/rediacc-cli.py'
            args = cmd_parts
        
        escaped_args = ' '.join(shlex.quote(arg) for arg in args)
        bash_cmd = f'cd "{msys2_cli_dir}" && python3 {cli_script} {escaped_args}'
        
        subprocess.Popen([bash_exe, '-l', '-c', bash_cmd])
    
    def _launch_powershell_direct(self, cli_dir: str, command: str, description: str):
        """Launch using PowerShell directly"""
        import shlex
        cmd_parts = shlex.split(command)
        if cmd_parts[0] == 'term':
            cli_script = f'{cli_dir}\\src\\cli\\rediacc-cli-term.py'
            args = cmd_parts[1:]
        elif cmd_parts[0] == 'sync':
            cli_script = f'{cli_dir}\\src\\cli\\rediacc-cli-sync.py'
            args = cmd_parts[1:]
        else:
            cli_script = f'{cli_dir}\\src\\cli\\rediacc-cli.py'
            args = cmd_parts
        
        escaped_args = ' '.join(f'"{arg}"' if ' ' in arg else arg for arg in args)
        ps_cmd = f'Start-Process powershell -WindowStyle Maximized -ArgumentList "-Command", "cd \\"{cli_dir}\\"; python3 {cli_script} {escaped_args}"'
        
        subprocess.Popen(['powershell.exe', '-Command', ps_cmd])
    
    def _launch_cmd_direct(self, cli_dir: str, command: str, description: str):
        """Launch using cmd.exe directly"""
        import shlex
        cmd_parts = shlex.split(command)
        if cmd_parts[0] == 'term':
            cli_script = f'{cli_dir}\\src\\cli\\rediacc-cli-term.py'
            args = cmd_parts[1:]
        elif cmd_parts[0] == 'sync':
            cli_script = f'{cli_dir}\\src\\cli\\rediacc-cli-sync.py'
            args = cmd_parts[1:]
        else:
            cli_script = f'{cli_dir}\\src\\cli\\rediacc-cli.py'
            args = cmd_parts
        
        escaped_args = ' '.join(f'"{arg}"' if ' ' in arg else arg for arg in args)
        cmd_str = f'cd /d "{cli_dir}" && python {cli_script} {escaped_args}'
        
        # Launch maximized
        subprocess.Popen(['cmd.exe', '/c', f'start /max cmd /c {cmd_str}'])
    
    def _launch_macos_terminal(self, cli_dir: str, command: str, description: str):
        """Launch using macOS Terminal.app"""
        cmd_str = f'cd {cli_dir} && ./rediacc {command}'
        # Launch Terminal.app (maximizing is handled by macOS Window Manager)
        # Note: Terminal.app doesn't have a direct maximize flag
        subprocess.Popen(['open', '-a', 'Terminal', '--', 'bash', '-c', cmd_str])
    
    def _launch_gnome_terminal(self, cli_dir: str, command: str, description: str):
        """Launch using GNOME Terminal"""
        cmd_str = f'cd {cli_dir} && ./rediacc {command}'
        # Launch maximized
        subprocess.Popen(['gnome-terminal', '--maximize', '--', 'bash', '-c', cmd_str])
    
    def _launch_konsole(self, cli_dir: str, command: str, description: str):
        """Launch using KDE Konsole"""
        cmd_str = f'cd {cli_dir} && ./rediacc {command}'
        # Launch maximized
        subprocess.Popen(['konsole', '--fullscreen', '-e', 'bash', '-c', cmd_str])
    
    def _launch_xfce4_terminal(self, cli_dir: str, command: str, description: str):
        """Launch using XFCE4 Terminal"""
        cmd_str = f'cd {cli_dir} && ./rediacc {command}'
        # Launch maximized
        subprocess.Popen(['xfce4-terminal', '--maximize', '-e', f'bash -c "{cmd_str}"'])
    
    def _launch_mate_terminal(self, cli_dir: str, command: str, description: str):
        """Launch using MATE Terminal"""
        cmd_str = f'cd {cli_dir} && ./rediacc {command}'
        # Launch maximized
        subprocess.Popen(['mate-terminal', '--maximize', '-e', f'bash -c "{cmd_str}"'])
    
    def _launch_terminator(self, cli_dir: str, command: str, description: str):
        """Launch using Terminator"""
        cmd_str = f'cd {cli_dir} && ./rediacc {command}'
        # Launch maximized
        subprocess.Popen(['terminator', '--maximise', '-e', f'bash -c "{cmd_str}"'])
    
    def _launch_xterm(self, cli_dir: str, command: str, description: str):
        """Launch using XTerm"""
        cmd_str = f'cd {cli_dir} && ./rediacc {command}'
        # Launch maximized with geometry
        subprocess.Popen(['xterm', '-maximized', '-e', 'bash', '-c', cmd_str])


if __name__ == "__main__":
    # Test the detector
    detector = TerminalDetector()
    
    # Force detection for testing
    method = detector.detect(force_refresh=True)
    
    if method:
        print(f"\nBest terminal method: {method}")
        
        # Show all working methods
        platform = sys.platform
        if platform.startswith('linux'):
            platform = 'linux'
        
        cache_data = detector.cache.get(platform, {})
        working_methods = cache_data.get('working_methods', [])
        if working_methods:
            print(f"All working methods: {', '.join(working_methods)}")
    else:
        print("\nNo working terminal methods found!")
    
    # Show cache contents
    print(f"\nCache file: {detector.CACHE_FILE}")
    print(f"Cache contents: {json.dumps(detector.cache, indent=2)}")