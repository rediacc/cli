#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Universal Rediacc CLI wrapper for Linux/macOS/Windows
Consolidated wrapper with all CLI, Desktop, and Docker functionality
"""

import sys
import os
import subprocess
import json
import shutil
import platform
import argparse
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict, Any

# Color codes for terminal output
class Colors:
    RED = '\033[0;31m'
    GREEN = '\033[0;32m'
    YELLOW = '\033[1;33m'
    CYAN = '\033[0;36m'
    NC = '\033[0m'  # No Color
    
    @staticmethod
    def disable():
        """Disable colors for non-terminal output"""
        Colors.RED = ''
        Colors.GREEN = ''
        Colors.YELLOW = ''
        Colors.CYAN = ''
        Colors.NC = ''

# Check if output is to terminal
if not sys.stdout.isatty():
    Colors.disable()

class RediaccCLI:
    """Main CLI wrapper class"""
    
    def __init__(self):
        self.script_dir = Path(__file__).parent.resolve()
        self.cli_root = self.script_dir
        self.env_file = self.script_dir.parent / '.env'
        self.config_dir = self.cli_root / '.config'
        self.python_cmd = None
        self.verbose = False
        self.env_vars = {}
        
        # Load environment variables
        self.load_env()
        
        # Set verbose mode from environment or arguments
        if os.environ.get('REDIACC_VERBOSE') or '--verbose' in sys.argv or '-v' in sys.argv:
            self.verbose = True
            os.environ['REDIACC_VERBOSE'] = '1'
    
    def load_env(self):
        """Load environment variables from .env file"""
        if self.env_file.exists():
            with open(self.env_file, 'r') as f:
                for line in f:
                    line = line.strip()
                    # Skip comments and empty lines
                    if line.startswith('#') or not line:
                        continue
                    
                    if '=' in line:
                        key, value = line.split('=', 1)
                        # Remove quotes
                        value = value.strip('"\'')
                        self.env_vars[key] = value
                        os.environ[key] = value
    
    def find_python(self) -> Optional[str]:
        """Find suitable Python interpreter"""
        # Check if we're in MSYS2 and should use MinGW64 Python
        if os.environ.get('MSYSTEM') and shutil.which('/mingw64/bin/python3'):
            return '/mingw64/bin/python3'
        
        # Try different Python commands
        for cmd in ['python3', 'python']:
            if shutil.which(cmd):
                try:
                    result = subprocess.run(
                        [cmd, '--version'],
                        capture_output=True,
                        text=True,
                        check=True
                    )
                    if 'Python' in result.stdout:
                        return cmd
                except:
                    continue
        return None
    
    def get_python_command(self) -> str:
        """Get Python command or exit with error"""
        if not self.python_cmd:
            self.python_cmd = self.find_python()
            if not self.python_cmd:
                print(f"{Colors.RED}Error: Python not found. Run: ./rediacc setup{Colors.NC}", file=sys.stderr)
                sys.exit(1)
        
        if self.verbose or os.environ.get('REDIACC_DEBUG'):
            print(f"{Colors.CYAN}[DEBUG] Using Python: {self.python_cmd}{Colors.NC}", file=sys.stderr)
        
        return self.python_cmd
    
    def run_command(self, cmd: List[str], check: bool = True, **kwargs) -> subprocess.CompletedProcess:
        """Run a command with proper error handling"""
        if self.verbose:
            print(f"{Colors.CYAN}[DEBUG] Running: {' '.join(cmd)}{Colors.NC}", file=sys.stderr)
        
        try:
            return subprocess.run(cmd, check=check, **kwargs)
        except subprocess.CalledProcessError as e:
            if check:
                print(f"{Colors.RED}Command failed with exit code {e.returncode}{Colors.NC}", file=sys.stderr)
                sys.exit(e.returncode)
            return e
        except FileNotFoundError:
            print(f"{Colors.RED}Command not found: {cmd[0]}{Colors.NC}", file=sys.stderr)
            sys.exit(1)
    
    def install_python_packages(self, python_cmd: str) -> bool:
        """Install Python packages from requirements.txt"""
        requirements_file = self.cli_root / 'requirements.txt'
        
        if not requirements_file.exists():
            print(f"{Colors.YELLOW}Warning: requirements.txt not found, skipping package installation{Colors.NC}")
            return True
        
        print(f"{Colors.CYAN}Installing Python packages from requirements.txt...{Colors.NC}")
        
        # Upgrade pip first
        result = self.run_command(
            [python_cmd, '-m', 'pip', 'install', '--upgrade', 'pip', '--quiet'],
            check=False,
            capture_output=True
        )
        if result.returncode != 0:
            print(f"{Colors.YELLOW}Warning: Failed to upgrade pip{Colors.NC}")
        
        # Install requirements
        result = self.run_command(
            [python_cmd, '-m', 'pip', 'install', '-r', str(requirements_file), '--quiet'],
            check=False,
            capture_output=True
        )
        
        if result.returncode == 0:
            print(f"{Colors.GREEN}✓ Python packages installed successfully{Colors.NC}")
            return True
        else:
            print(f"{Colors.YELLOW}Warning: Some Python packages may not have installed correctly{Colors.NC}")
            return False
    
    def cmd_setup(self, args: List[str]):
        """Setup command - install dependencies and check environment"""
        print(f"{Colors.CYAN}=== Rediacc CLI Setup ==={Colors.NC}")
        print()
        
        # Check Python
        python_cmd = self.find_python()
        if python_cmd:
            result = subprocess.run(
                [python_cmd, '-c', 'import sys; print(".".join(map(str, sys.version_info[:2])))'],
                capture_output=True,
                text=True
            )
            python_version = result.stdout.strip()
            print(f"{Colors.GREEN}✓ Python {python_version} found ({python_cmd}){Colors.NC}")
            
            # Install Python packages
            self.install_python_packages(python_cmd)
        else:
            print(f"{Colors.RED}Error: Python is not installed{Colors.NC}")
            print("Please install Python 3.7 or later")
            sys.exit(1)
        
        # Check rsync
        if not shutil.which('rsync'):
            print(f"{Colors.YELLOW}Warning: rsync not found{Colors.NC}")
            print("Install rsync for file synchronization support:")
            print("  Ubuntu/Debian: sudo apt-get install rsync")
            print("  macOS: brew install rsync")
        else:
            print(f"{Colors.GREEN}✓ rsync found{Colors.NC}")
        
        # Check SSH
        if not shutil.which('ssh'):
            print(f"{Colors.YELLOW}Warning: SSH not found{Colors.NC}")
            print("SSH is required for terminal access")
        else:
            print(f"{Colors.GREEN}✓ SSH found{Colors.NC}")
        
        # Check tkinter for desktop application
        try:
            result = subprocess.run(
                [python_cmd, '-c', 'import tkinter'],
                capture_output=True,
                check=False
            )
            if result.returncode == 0:
                print(f"{Colors.GREEN}✓ tkinter found (desktop app support available){Colors.NC}")
            else:
                raise ImportError()
        except:
            print(f"{Colors.YELLOW}Warning: tkinter not found{Colors.NC}")
            print("Install python3-tk for Rediacc Desktop application support:")
            print("  Ubuntu/Debian: sudo apt-get install python3-tk")
            print("  macOS: tkinter should be included with Python")
        
        # Check configuration
        if (self.cli_root / '.env').exists():
            print(f"{Colors.GREEN}✓ Configuration file found{Colors.NC}")
        else:
            print(f"{Colors.YELLOW}Warning: No .env file found{Colors.NC}")
            print("Copy .env.example to .env and configure:")
            print("  cp .env.example .env")
        
        print()
        print(f"{Colors.GREEN}Setup check complete!{Colors.NC}")
    
    def cmd_test(self, args: List[str]):
        """Run tests"""
        os.chdir(self.cli_root)
        
        if not args:
            print(f"{Colors.GREEN}Running all CLI tests...{Colors.NC}")
            self.run_command([self.get_python_command(), '-m', 'pytest', 'tests/', '-v'])
        else:
            test_type = args[0]
            remaining_args = args[1:]
            
            if test_type == 'desktop':
                print(f"{Colors.GREEN}Running desktop application tests...{Colors.NC}")
                self.run_command([self.get_python_command(), '-m', 'pytest', 'tests/gui/', '-v'] + remaining_args)
            elif test_type == 'gui':
                print(f"{Colors.YELLOW}Note: 'gui' test type is deprecated, use 'desktop' instead{Colors.NC}")
                print(f"{Colors.GREEN}Running desktop application tests...{Colors.NC}")
                self.run_command([self.get_python_command(), '-m', 'pytest', 'tests/gui/', '-v'] + remaining_args)
            elif test_type == 'workflow':
                print(f"{Colors.GREEN}Running workflow tests...{Colors.NC}")
                self.run_command([self.get_python_command(), '-m', 'pytest', 'tests/workflow/', '-v'] + remaining_args)
            elif test_type == 'yaml':
                print(f"{Colors.GREEN}Running YAML tests...{Colors.NC}")
                self.run_command([self.get_python_command(), 'tests/run_tests.py'] + remaining_args)
            elif test_type == 'protocol':
                print(f"{Colors.GREEN}Running protocol tests...{Colors.NC}")
                self.run_command([self.get_python_command(), '-m', 'pytest', 'tests/protocol/', '-v'] + remaining_args)
            else:
                print(f"{Colors.GREEN}Running CLI tests with options...{Colors.NC}")
                self.run_command([self.get_python_command(), '-m', 'pytest', 'tests/'] + args)
    
    def cmd_release(self, args: List[str]):
        """Create a release build"""
        print(f"{Colors.GREEN}Preparing CLI release...{Colors.NC}")
        
        # Create release directory
        release_dir = self.cli_root / 'release'
        if release_dir.exists():
            shutil.rmtree(release_dir)
        release_dir.mkdir(parents=True)
        
        # Copy essential files
        for item in ['src', 'rediacc', 'rediacc.ps1', 'rediacc.py', '.env.example']:
            source = self.cli_root / item
            if source.exists():
                if source.is_dir():
                    shutil.copytree(source, release_dir / item)
                else:
                    shutil.copy2(source, release_dir / item)
        
        # Copy requirements.txt if it exists
        req_file = self.cli_root / 'requirements.txt'
        if req_file.exists():
            shutil.copy2(req_file, release_dir / 'requirements.txt')
        
        # Create version info
        version = datetime.now().strftime('%Y.%m.%d.%H%M')
        version_info = {
            'version': version,
            'build_date': datetime.utcnow().isoformat() + 'Z'
        }
        with open(release_dir / 'version.json', 'w') as f:
            json.dump(version_info, f, indent=2)
        
        # Create tarball
        tarball_name = f"rediacc-{version}.tar.gz"
        self.run_command(['tar', '-czf', tarball_name, '-C', str(self.cli_root), 'release/'])
        
        print(f"{Colors.GREEN}Release created: {tarball_name}{Colors.NC}")
        print(f"Release directory: {release_dir}")
    
    def cmd_docker_build(self, args: List[str]):
        """Build Docker image"""
        print(f"{Colors.GREEN}Building CLI Docker image...{Colors.NC}")
        
        cmd = [
            'docker', 'build', '-t', 'rediacc:latest',
            '--build-arg', 'REDIACC_LINUX_USER=rediacc',
            '--build-arg', 'REDIACC_LINUX_GROUP=rediacc',
            '--build-arg', 'REDIACC_USER_UID=7111',
            '--build-arg', 'REDIACC_USER_GID=7111',
            '-f', str(self.cli_root / 'docker' / 'Dockerfile'),
            str(self.cli_root)
        ]
        
        result = self.run_command(cmd, check=False)
        if result.returncode == 0:
            print(f"{Colors.GREEN}Docker image built successfully: rediacc:latest{Colors.NC}")
        else:
            print(f"{Colors.RED}Docker build failed{Colors.NC}")
            sys.exit(1)
    
    def check_docker_image(self, image_name: str = 'rediacc:latest') -> bool:
        """Check if Docker image exists"""
        result = subprocess.run(
            ['docker', 'images', '-q', image_name],
            capture_output=True,
            text=True,
            check=False
        )
        return bool(result.stdout.strip())
    
    def cmd_docker_run(self, args: List[str]):
        """Run CLI in Docker container"""
        # Build if image doesn't exist
        if not self.check_docker_image():
            print(f"{Colors.YELLOW}Docker image not found. Building...{Colors.NC}")
            self.cmd_docker_build([])
        
        # Prepare docker run command
        cmd = [
            'docker', 'run', '-it', '--rm',
            f'--name', f'rediacc-run-{os.getpid()}'
        ]
        
        # Add environment file if it exists
        if self.env_file.exists():
            cmd.extend(['--env-file', str(self.env_file)])
        
        # Add volume mounts
        cmd.extend([
            '-v', f'{self.cli_root / ".config"}:/home/rediacc/.config',
            '-v', f'{Path.home() / ".ssh"}:/home/rediacc/.ssh:ro',
            '-v', f'{os.getcwd()}:/workspace',
            '-w', '/workspace',
            '--network', 'host',
            'rediacc:latest'
        ])
        
        # Add user arguments
        cmd.extend(args)
        
        self.run_command(cmd)
    
    def cmd_docker_shell(self, args: List[str]):
        """Start interactive shell in Docker"""
        print(f"{Colors.GREEN}Starting interactive shell in Docker...{Colors.NC}")
        
        # Build if image doesn't exist
        if not self.check_docker_image():
            print(f"{Colors.YELLOW}Docker image not found. Building...{Colors.NC}")
            self.cmd_docker_build([])
        
        # Prepare docker run command
        cmd = [
            'docker', 'run', '-it', '--rm',
            f'--name', f'rediacc-shell-{os.getpid()}'
        ]
        
        # Add environment file if it exists
        if self.env_file.exists():
            cmd.extend(['--env-file', str(self.env_file)])
        
        # Add volume mounts
        cmd.extend([
            '-v', f'{self.cli_root / ".config"}:/home/rediacc/.config',
            '-v', f'{Path.home() / ".ssh"}:/home/rediacc/.ssh:ro',
            '-v', f'{os.getcwd()}:/workspace',
            '-w', '/workspace',
            '--network', 'host',
            'rediacc:latest',
            '/bin/bash'
        ])
        
        self.run_command(cmd)
    
    def cmd_desktop(self, args: List[str]):
        """Launch desktop application"""
        # Check for Docker mode
        if args and args[0] == 'docker':
            self.cmd_desktop_docker(args[1:])
            return
        elif args and args[0] == 'docker-build':
            self.cmd_desktop_docker_build(args[1:])
            return
        
        print(f"{Colors.GREEN}Starting Rediacc Desktop application...{Colors.NC}")
        
        python_cmd = self.get_python_command()
        
        # Check tkinter
        result = subprocess.run(
            [python_cmd, '-c', 'import tkinter'],
            capture_output=True,
            check=False
        )
        if result.returncode != 0:
            print(f"{Colors.RED}Error: tkinter not found{Colors.NC}")
            print("Install python3-tk:")
            print("  Ubuntu/Debian: sudo apt-get install python3-tk")
            print("  Fedora/RHEL: sudo dnf install python3-tkinter")
            print("  macOS: tkinter should be included with Python")
            sys.exit(1)
        
        # Run Desktop GUI
        gui_main = self.cli_root / 'src' / 'cli' / 'gui' / 'main.py'
        self.run_command([python_cmd, str(gui_main)] + args)
    
    def cmd_desktop_docker_build(self, args: List[str]):
        """Build Desktop Docker image"""
        print(f"{Colors.GREEN}Building Rediacc Desktop Docker image...{Colors.NC}")
        
        # Build CLI image (includes GUI support)
        cmd = [
            'docker', 'build', '-t', 'rediacc/cli:latest',
            '--build-arg', 'REDIACC_LINUX_USER=rediacc',
            '--build-arg', 'REDIACC_LINUX_GROUP=rediacc',
            '--build-arg', 'REDIACC_USER_UID=7111',
            '--build-arg', 'REDIACC_USER_GID=7111',
            '-f', str(self.cli_root / 'docker' / 'Dockerfile'),
            str(self.cli_root)
        ]
        
        result = self.run_command(cmd, check=False)
        if result.returncode == 0:
            print(f"{Colors.GREEN}Docker image built successfully: rediacc/cli:latest{Colors.NC}")
        else:
            print(f"{Colors.RED}Docker build failed{Colors.NC}")
            sys.exit(1)
    
    def cmd_desktop_docker(self, args: List[str]):
        """Run Desktop in Docker"""
        print(f"{Colors.GREEN}Running Rediacc Desktop in Docker...{Colors.NC}")
        
        image_name = 'rediacc/cli:latest'
        
        # Check if rebuild is needed
        rebuild_needed = False
        if not self.check_docker_image(image_name):
            print(f"{Colors.YELLOW}Docker image not found. Building...{Colors.NC}")
            rebuild_needed = True
        else:
            # Check if source files are newer than build marker
            build_marker = self.cli_root / '.dockerbuild'
            if build_marker.exists():
                # Find newer source files
                for pattern in ['*.py', 'Dockerfile*']:
                    for path in self.cli_root.rglob(pattern):
                        if path.stat().st_mtime > build_marker.stat().st_mtime:
                            print(f"{Colors.YELLOW}Source files have been updated. Rebuilding...{Colors.NC}")
                            rebuild_needed = True
                            break
                    if rebuild_needed:
                        break
            else:
                print(f"{Colors.YELLOW}No build marker found. Rebuilding to ensure latest version...{Colors.NC}")
                rebuild_needed = True
        
        if rebuild_needed:
            self.cmd_desktop_docker_build([])
            # Update build marker
            (self.cli_root / '.dockerbuild').touch()
        
        # Platform-specific display setup
        system = platform.system()
        if system == 'Darwin':
            # macOS
            if not shutil.which('xhost'):
                print(f"{Colors.RED}XQuartz not found{Colors.NC}")
                print("Install XQuartz from: https://www.xquartz.org/")
                sys.exit(1)
            subprocess.run(['xhost', '+local:docker'], capture_output=True)
            display_env = 'host.docker.internal:0'
        else:
            # Linux
            subprocess.run(['xhost', '+local:docker'], capture_output=True)
            display_env = os.environ.get('DISPLAY', ':0')
        
        print(f"{Colors.CYAN}Starting desktop application container...{Colors.NC}")
        
        # Ensure directories exist
        self.config_dir.mkdir(exist_ok=True)
        rediacc_volume = Path.home() / '.config-docker'
        rediacc_volume.mkdir(exist_ok=True)
        
        # Copy existing config if it exists
        config_file = self.config_dir / 'config.json'
        if config_file.exists():
            shutil.copy2(config_file, rediacc_volume / 'config.json')
        
        # Set permissions
        rediacc_volume.chmod(0o777)
        
        # Build docker run command
        cmd = [
            'docker', 'run', '-it', '--rm',
            f'--name', f'rediacc-desktop-{os.getpid()}',
            '-e', f'DISPLAY={display_env}',
            '-v', '/tmp/.X11-unix:/tmp/.X11-unix:rw',
            '-v', f'{Path.home() / ".Xauthority"}:/home/rediacc/.Xauthority:ro',
            '-v', f'{rediacc_volume}:/home/rediacc/.config:rw',
            '-v', f'{self.env_file}:/app/.env:ro',
            '--network', 'host',
            image_name,
            'python3', '/app/src/cli/gui/main.py'
        ]
        
        self.run_command(cmd)
        
        # Copy config back if updated
        updated_config = rediacc_volume / 'config.json'
        if updated_config.exists():
            shutil.copy2(updated_config, self.config_dir / 'config.json')
    
    def cmd_cli_command(self, command: str, args: List[str], inject_token: bool = False):
        """Run a CLI command"""
        python_cmd = self.get_python_command()
        
        # Build command path
        if command == 'cli':
            script = self.cli_root / 'src' / 'cli' / 'commands' / 'cli_main.py'
            cmd_args = args
        else:
            script = self.cli_root / 'src' / 'cli' / 'commands' / f'{command}_main.py'
            cmd_args = args
        
        # Check if we need to inject token
        if inject_token and '--token' not in args:
            # Try to get token from config
            try:
                sys.path.insert(0, str(self.cli_root / 'src'))
                from cli.core.config import TokenManager
                token = TokenManager().get_token()
                if token:
                    cmd_args = ['--token', token] + cmd_args
            except:
                pass
        
        # Run command
        self.run_command([python_cmd, str(script)] + cmd_args)
    
    def print_help(self):
        """Print help message"""
        help_text = f"""{Colors.CYAN}Rediacc CLI and Desktop for Linux/macOS/Windows{Colors.NC}

USAGE:
    python3 rediacc.py <command> [arguments]

COMMANDS:
  Core:
    login       Authenticate with Rediacc API
    sync        File synchronization operations
    term        Terminal access to repositories
    plugin      Manage plugin connections (SSH tunnels)
    cli         Direct access to CLI (bypass wrapper)
    desktop [mode]  Launch Rediacc Desktop application
                    native: Run natively (default)
                    docker: Run in Docker (auto-builds)
                    docker-build: Force rebuild Docker image
    gui         Deprecated: Use 'desktop' command instead

  License Management:
    license generate-id   Generate hardware ID for offline licensing
    license request       Request license using hardware ID
    license install       Install license file

  Development:
    test        Test installation and run test suite
    release     Create a release build

  Docker:
    docker-build          Build CLI Docker image
    docker-run            Run CLI in Docker container
    docker-shell          Interactive shell in Docker

  Setup:
    setup       Install dependencies and set up environment
    help        Show this help message

EXAMPLES:
    python3 rediacc.py setup         # Check/install dependencies
    python3 rediacc.py login         # Interactive login
    python3 rediacc.py desktop       # Launch desktop app natively
    python3 rediacc.py desktop docker # Launch desktop app in Docker
    python3 rediacc.py sync --help   # Sync help
    python3 rediacc.py term --help   # Terminal help
    python3 rediacc.py plugin --help # Plugin help

  Testing:
    python3 rediacc.py test          # Run all tests
    python3 rediacc.py test protocol # Run protocol tests
    python3 rediacc.py test desktop  # Run desktop tests
    python3 rediacc.py test yaml     # Run YAML tests

  License Management:
    python3 rediacc.py license generate-id           # Generate hardware ID
    python3 rediacc.py license request -i hw-id.txt  # Request license
    python3 rediacc.py license install -f license.lic # Install license

For detailed documentation, see docs/README.md"""
        print(help_text)
    
    def run(self, argv: List[str]):
        """Main entry point"""
        if not argv or argv[0] in ['help', '--help', '-h']:
            self.print_help()
            return
        
        command = argv[0]
        args = argv[1:]
        
        # Command routing
        if command == 'setup':
            self.cmd_setup(args)
        elif command == 'test':
            self.cmd_test(args)
        elif command == 'release':
            self.cmd_release(args)
        elif command == 'docker-build':
            self.cmd_docker_build(args)
        elif command == 'docker-run':
            self.cmd_docker_run(args)
        elif command == 'docker-shell':
            self.cmd_docker_shell(args)
        elif command in ['desktop', 'gui', '--gui']:
            if command == 'gui':
                print(f"{Colors.YELLOW}Note: 'gui' command is deprecated, use 'desktop' instead{Colors.NC}")
            self.cmd_desktop(args)
        elif command == 'desktop-docker':
            self.cmd_desktop_docker(args)
        elif command == 'desktop-docker-build':
            self.cmd_desktop_docker_build(args)
        elif command == 'login':
            self.cmd_cli_command('cli', ['login'] + args)
        elif command == 'sync':
            self.cmd_cli_command('sync', args)
        elif command in ['term', 'terminal']:
            self.cmd_cli_command('term', args)
        elif command == 'plugin':
            self.cmd_cli_command('plugin', args)
        elif command == 'cli':
            self.cmd_cli_command('cli', args)
        elif command in ['version', '--version']:
            self.cmd_cli_command('cli', ['--version'])
        elif command == 'license':
            # License management - pass through to CLI
            self.cmd_cli_command('cli', ['license'] + args, inject_token=True)
        else:
            # Default: pass through to main CLI with possible token injection
            self.cmd_cli_command('cli', argv, inject_token=True)


def main():
    """Main entry point"""
    cli = RediaccCLI()
    try:
        cli.run(sys.argv[1:])
    except KeyboardInterrupt:
        print(f"\n{Colors.YELLOW}Interrupted by user{Colors.NC}")
        sys.exit(130)
    except Exception as e:
        if os.environ.get('REDIACC_DEBUG'):
            import traceback
            traceback.print_exc()
        else:
            print(f"{Colors.RED}Error: {e}{Colors.NC}", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()