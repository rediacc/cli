#!/usr/bin/env python3
"""
Rediacc CLI Doctor - System diagnostics and troubleshooting
"""

import argparse
import os
import sys
import subprocess
import platform
import shutil
import tempfile
from pathlib import Path
from typing import List, Dict, Any, Tuple

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from cli._version import __version__
from cli.core.shared import colorize, add_common_arguments, initialize_cli_command
from cli.core.config import setup_logging, get_logger, get_config_dir
from cli.core.telemetry import track_command, initialize_telemetry, shutdown_telemetry

logger = get_logger(__name__)

class SystemCheck:
    """Represents a system check with its result"""
    def __init__(self, name: str, description: str):
        self.name = name
        self.description = description
        self.passed = False
        self.message = ""
        self.fix_command = None
        self.details = []

class DoctorSession:
    """Manages a complete doctor/troubleshooting session"""
    
    def __init__(self, auto_fix: bool = False, verbose: bool = False):
        self.auto_fix = auto_fix
        self.verbose = verbose
        self.checks = []
        self.fixes_applied = []
        self.platform = platform.system().lower()
    
    def add_check(self, check: SystemCheck):
        """Add a system check to the session"""
        self.checks.append(check)
    
    def run_all_checks(self) -> bool:
        """Run all system checks and return True if all passed"""
        print(colorize("🔍 REDIACC SYSTEM DOCTOR", 'HEADER'))
        print(colorize("=" * 50, 'BLUE'))
        print(f"Platform: {platform.system()} {platform.release()}")
        print(f"Python: {sys.version.split()[0]}")
        print()
        
        all_passed = True
        
        for i, check in enumerate(self.checks, 1):
            print(f"{i}. {colorize(check.description, 'BLUE')}")
            
            try:
                self._run_single_check(check)
                
                if check.passed:
                    print(f"   {colorize('✅ PASS', 'GREEN')}: {check.message}")
                else:
                    print(f"   {colorize('❌ FAIL', 'RED')}: {check.message}")
                    all_passed = False
                    
                    if check.fix_command and (self.auto_fix or self._ask_to_fix(check)):
                        self._apply_fix(check)
                
                if self.verbose and check.details:
                    for detail in check.details:
                        print(f"      {colorize('ℹ️', 'CYAN')} {detail}")
                        
            except Exception as e:
                check.passed = False
                check.message = f"Check failed with error: {e}"
                print(f"   {colorize('⚠️ ERROR', 'YELLOW')}: {check.message}")
                all_passed = False
                
                if self.verbose:
                    import traceback
                    print(f"      {colorize('Debug:', 'CYAN')} {traceback.format_exc()}")
            
            print()
        
        self._print_summary(all_passed)
        return all_passed
    
    def _run_single_check(self, check: SystemCheck):
        """Run a single system check"""
        if check.name == "ssh_client":
            self._check_ssh_client(check)
        elif check.name == "ssh_agent":
            self._check_ssh_agent(check)
        elif check.name == "known_hosts_dir":
            self._check_known_hosts_dir(check)
        elif check.name == "temp_directory":
            self._check_temp_directory(check)
        elif check.name == "network_connectivity":
            self._check_network_connectivity(check)
        elif check.name == "ssh_config":
            self._check_ssh_config(check)
        elif check.name == "system_packages":
            self._check_system_packages(check)
        else:
            raise ValueError(f"Unknown check: {check.name}")
    
    def _check_ssh_client(self, check: SystemCheck):
        """Check SSH client availability and version"""
        ssh_path = shutil.which('ssh')
        if not ssh_path:
            check.message = "SSH client not found"
            check.fix_command = self._get_ssh_install_command()
            return
            
        try:
            result = subprocess.run(['ssh', '-V'], capture_output=True, text=True, timeout=5)
            version_info = result.stderr.split('\n')[0]  # SSH version is in stderr
            check.passed = True
            check.message = f"SSH client available: {version_info}"
            check.details.append(f"SSH binary: {ssh_path}")
            
            # Check for common SSH tools
            tools = ['ssh-keygen', 'ssh-agent', 'ssh-add']
            for tool in tools:
                tool_path = shutil.which(tool)
                if tool_path:
                    check.details.append(f"{tool}: {tool_path}")
                else:
                    check.details.append(f"{tool}: NOT FOUND")
                    
        except subprocess.TimeoutExpired:
            check.message = "SSH client found but not responding"
        except Exception as e:
            check.message = f"SSH client check failed: {e}"
    
    def _check_ssh_agent(self, check: SystemCheck):
        """Check SSH agent functionality"""
        try:
            # Test if we can start ssh-agent
            result = subprocess.run(['ssh-agent', '-s'], capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                check.passed = True
                check.message = "SSH agent can be started successfully"
                
                # Extract agent info
                for line in result.stdout.strip().split('\n'):
                    if '=' in line and ';' in line:
                        var_assignment = line.split(';')[0]
                        if '=' in var_assignment:
                            key, value = var_assignment.split('=', 1)
                            if key == 'SSH_AGENT_PID':
                                check.details.append(f"Test agent PID: {value}")
                                # Clean up test agent
                                try:
                                    subprocess.run(['kill', value], capture_output=True, timeout=5)
                                except:
                                    pass
            else:
                check.message = f"SSH agent failed to start: {result.stderr}"
                
        except subprocess.TimeoutExpired:
            check.message = "SSH agent test timed out"
        except FileNotFoundError:
            check.message = "ssh-agent command not found"
            check.fix_command = self._get_ssh_install_command()
        except Exception as e:
            check.message = f"SSH agent test failed: {e}"
    
    def _check_known_hosts_dir(self, check: SystemCheck):
        """Check SSH directory and known_hosts setup"""
        ssh_dir = Path.home() / '.ssh'
        
        if not ssh_dir.exists():
            check.message = "SSH directory (~/.ssh) does not exist"
            check.fix_command = f"mkdir -p {ssh_dir} && chmod 700 {ssh_dir}"
        elif not ssh_dir.is_dir():
            check.message = "~/.ssh exists but is not a directory"
        else:
            # Check permissions
            permissions = oct(ssh_dir.stat().st_mode)[-3:]
            if permissions != '700':
                check.message = f"SSH directory has incorrect permissions ({permissions}), should be 700"
                check.fix_command = f"chmod 700 {ssh_dir}"
            else:
                check.passed = True
                check.message = "SSH directory exists with correct permissions"
                
                # Check known_hosts file
                known_hosts = ssh_dir / 'known_hosts'
                if known_hosts.exists():
                    check.details.append(f"known_hosts file exists ({known_hosts.stat().st_size} bytes)")
                else:
                    check.details.append("known_hosts file does not exist (will be created as needed)")
    
    def _check_temp_directory(self, check: SystemCheck):
        """Check temporary directory access"""
        try:
            with tempfile.NamedTemporaryFile(mode='w', delete=True, prefix='rediacc_test_') as f:
                f.write("test")
                f.flush()
                check.passed = True
                check.message = f"Temporary directory accessible: {os.path.dirname(f.name)}"
        except Exception as e:
            check.message = f"Cannot write to temporary directory: {e}"
            check.fix_command = "Check TMPDIR environment variable and /tmp permissions"
    
    def _check_network_connectivity(self, check: SystemCheck):
        """Check basic network connectivity"""
        # Test DNS resolution
        try:
            import socket
            socket.gethostbyname('google.com')
            check.passed = True
            check.message = "Network connectivity and DNS resolution working"
            check.details.append("DNS test: google.com resolved successfully")
        except socket.gaierror:
            check.message = "DNS resolution failed"
            check.details.append("Cannot resolve google.com")
        except Exception as e:
            check.message = f"Network connectivity test failed: {e}"
    
    def _check_ssh_config(self, check: SystemCheck):
        """Check SSH configuration"""
        ssh_config_locations = [
            Path.home() / '.ssh' / 'config',
            Path('/etc/ssh/ssh_config')
        ]
        
        config_found = False
        for config_path in ssh_config_locations:
            if config_path.exists():
                config_found = True
                check.details.append(f"SSH config found: {config_path}")
                
                try:
                    with open(config_path, 'r') as f:
                        content = f.read()
                        if 'StrictHostKeyChecking' in content:
                            check.details.append("Custom StrictHostKeyChecking settings detected")
                        if 'UserKnownHostsFile' in content:
                            check.details.append("Custom UserKnownHostsFile settings detected")
                except Exception as e:
                    check.details.append(f"Could not read {config_path}: {e}")
        
        if config_found:
            check.passed = True
            check.message = "SSH configuration files found"
        else:
            check.passed = True  # Not having SSH config is fine
            check.message = "No custom SSH configuration (using defaults)"
    
    def _check_system_packages(self, check: SystemCheck):
        """Check system packages that might be needed"""
        if self.platform == 'linux':
            # Check for rsync (used by sync command)
            rsync_path = shutil.which('rsync')
            if rsync_path:
                check.details.append(f"rsync: {rsync_path}")
            else:
                check.details.append("rsync: NOT FOUND (needed for file sync)")
            
            # Check for curl/wget (might be used for downloads)
            for tool in ['curl', 'wget']:
                tool_path = shutil.which(tool)
                if tool_path:
                    check.details.append(f"{tool}: {tool_path}")
                    break
            else:
                check.details.append("curl/wget: NOT FOUND (might be needed for downloads)")
        
        check.passed = True
        check.message = "System package check completed"
    
    def _get_ssh_install_command(self) -> str:
        """Get the appropriate SSH installation command for the platform"""
        if self.platform == 'linux':
            # Try to detect the package manager
            if shutil.which('apt-get'):
                return "sudo apt-get update && sudo apt-get install -y openssh-client"
            elif shutil.which('yum'):
                return "sudo yum install -y openssh-clients"
            elif shutil.which('dnf'):
                return "sudo dnf install -y openssh-clients"
            elif shutil.which('pacman'):
                return "sudo pacman -S openssh"
            else:
                return "Install openssh-client using your system's package manager"
        elif self.platform == 'darwin':
            return "SSH should be pre-installed on macOS. If missing, install Xcode Command Line Tools: xcode-select --install"
        else:
            return "Install OpenSSH client for your operating system"
    
    def _ask_to_fix(self, check: SystemCheck) -> bool:
        """Ask user if they want to apply a fix"""
        if not check.fix_command:
            return False
            
        print(f"   {colorize('🔧 Suggested fix:', 'YELLOW')} {check.fix_command}")
        response = input(f"   Apply this fix? [y/N]: ").strip().lower()
        return response in ['y', 'yes']
    
    def _apply_fix(self, check: SystemCheck):
        """Apply a fix for a failed check"""
        if not check.fix_command:
            return
            
        print(f"   {colorize('🔧 Applying fix...', 'CYAN')}")
        
        try:
            if check.fix_command.startswith('mkdir') or check.fix_command.startswith('chmod'):
                # Safe filesystem operations
                result = subprocess.run(check.fix_command, shell=True, capture_output=True, text=True, timeout=30)
                if result.returncode == 0:
                    print(f"   {colorize('✅ Fix applied successfully', 'GREEN')}")
                    self.fixes_applied.append(check.name)
                    # Re-run the check
                    self._run_single_check(check)
                else:
                    print(f"   {colorize('❌ Fix failed:', 'RED')} {result.stderr}")
            else:
                # For package installations and other complex fixes, just show the command
                print(f"   {colorize('ℹ️ Manual fix required:', 'CYAN')} Run this command:")
                print(f"   {colorize(check.fix_command, 'YELLOW')}")
                
        except Exception as e:
            print(f"   {colorize('❌ Fix failed:', 'RED')} {e}")
    
    def _print_summary(self, all_passed: bool):
        """Print final summary"""
        print(colorize("=" * 50, 'BLUE'))
        
        if all_passed:
            print(colorize("🎉 ALL CHECKS PASSED!", 'GREEN'))
            print("Your system appears to be properly configured for Rediacc CLI.")
        else:
            failed_checks = [check for check in self.checks if not check.passed]
            print(colorize(f"⚠️  {len(failed_checks)} CHECKS FAILED", 'YELLOW'))
            print("Some issues were found that may affect Rediacc CLI functionality.")
            
        if self.fixes_applied:
            print(f"\n{colorize('🔧 Fixes applied:', 'CYAN')} {', '.join(self.fixes_applied)}")
            
        print(f"\n{colorize('📋 Summary:', 'BLUE')}")
        print(f"   Total checks: {len(self.checks)}")
        print(f"   Passed: {colorize(str(sum(1 for c in self.checks if c.passed)), 'GREEN')}")
        print(f"   Failed: {colorize(str(sum(1 for c in self.checks if not c.passed)), 'RED' if not all_passed else 'GREEN')}")

def create_standard_checks() -> List[SystemCheck]:
    """Create the standard set of system checks"""
    return [
        SystemCheck("ssh_client", "SSH Client Installation"),
        SystemCheck("ssh_agent", "SSH Agent Functionality"),
        SystemCheck("known_hosts_dir", "SSH Directory Setup"),
        SystemCheck("temp_directory", "Temporary Directory Access"),
        SystemCheck("network_connectivity", "Network Connectivity"),
        SystemCheck("ssh_config", "SSH Configuration"),
        SystemCheck("system_packages", "System Packages"),
    ]

@track_command('doctor')
def main():
    initialize_telemetry()
    
    parser = argparse.ArgumentParser(
        description='Rediacc System Doctor - Diagnose and fix system issues',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  ./rediacc doctor                    # Run all diagnostic checks
  ./rediacc doctor --auto-fix         # Automatically apply safe fixes
  ./rediacc doctor --verbose          # Show detailed information
  ./rediacc troubleshoot              # Alias for doctor command

This command helps diagnose and resolve common system issues that
might prevent Rediacc CLI from working properly, including:
  • SSH client and agent setup
  • File permissions
  • Network connectivity
  • Required system packages
        """
    )
    
    parser.add_argument('--version', action='version', 
                       version=f'Rediacc CLI Doctor v{__version__}')
    
    add_common_arguments(parser, include_args=['verbose'])
    
    parser.add_argument('--auto-fix', action='store_true',
                       help='Automatically apply safe fixes without prompting')
    
    args = parser.parse_args()
    
    setup_logging(verbose=args.verbose)
    logger = get_logger(__name__)
    
    if args.verbose:
        logger.debug("Starting Rediacc System Doctor")
        logger.debug(f"Arguments: {vars(args)}")
    
    try:
        # Create and run all checks
        checks = create_standard_checks()
        doctor = DoctorSession(auto_fix=args.auto_fix, verbose=args.verbose)
        
        for check in checks:
            doctor.add_check(check)
        
        success = doctor.run_all_checks()
        
        return 0 if success else 1
        
    except KeyboardInterrupt:
        print(f"\n{colorize('🛑 Interrupted by user', 'YELLOW')}")
        return 1
    except Exception as e:
        logger.error(f"Doctor command failed: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        print(f"{colorize('❌ Error:', 'RED')} {e}")
        return 1
    finally:
        shutdown_telemetry()

if __name__ == '__main__':
    sys.exit(main())