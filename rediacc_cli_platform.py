#!/usr/bin/env python3
"""
Platform-specific abstractions for Rediacc CLI
Provides cross-platform compatibility for Windows and Linux/macOS
"""
import os
import platform
import subprocess
import sys
import shutil
from typing import Dict, List, Optional, Tuple
from pathlib import Path


def get_platform() -> str:
    """Get the current platform type"""
    system = platform.system().lower()
    if system == 'windows':
        return 'windows'
    elif system in ['linux', 'darwin']:
        return 'unix'
    else:
        return 'unknown'


def is_windows() -> bool:
    """Check if running on Windows"""
    return get_platform() == 'windows'


def is_unix() -> bool:
    """Check if running on Unix-like system (Linux/macOS)"""
    return get_platform() == 'unix'


def get_null_device() -> str:
    """Get the null device path for the current platform"""
    if is_windows():
        return 'NUL'
    else:
        return '/dev/null'


def get_temp_dir() -> str:
    """Get the temporary directory path for the current platform"""
    if is_windows():
        # Use Windows TEMP environment variable
        return os.environ.get('TEMP', os.environ.get('TMP', 'C:\\Windows\\Temp'))
    else:
        return '/tmp'


def get_home_dir() -> Path:
    """Get the user's home directory"""
    return Path.home()


def get_ssh_command(options: str) -> List[str]:
    """Get the SSH command for the current platform"""
    if is_windows():
        # Check if we have ssh in MSYS2
        msys2_ssh = find_msys2_executable('ssh')
        if msys2_ssh:
            return ['cmd.exe', '/c', msys2_ssh] + options.split()
        # Fallback to Windows OpenSSH if available
        elif shutil.which('ssh'):
            return ['ssh'] + options.split()
        else:
            raise RuntimeError("SSH not found. Please install MSYS2 or enable Windows OpenSSH.")
    else:
        return ['ssh'] + options.split()


def get_rsync_command() -> str:
    """Get the rsync command for the current platform"""
    if is_windows():
        # Look for rsync in MSYS2
        msys2_rsync = find_msys2_executable('rsync')
        if msys2_rsync:
            return msys2_rsync
        else:
            raise RuntimeError("rsync not found. Please install MSYS2 with rsync package.")
    else:
        # On Unix, use rsync directly
        if not shutil.which('rsync'):
            raise RuntimeError("rsync not found. Please install rsync.")
        return 'rsync'


def find_msys2_executable(exe_name: str) -> Optional[str]:
    """Find an executable in MSYS2 installation"""
    if not is_windows():
        return None
    
    # Common MSYS2 installation paths
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
    
    # Search for the executable
    for msys2_path in msys2_paths:
        if os.path.exists(msys2_path):
            # Check in various MSYS2 subdirectories
            for subdir in ['usr\\bin', 'mingw64\\bin', 'mingw32\\bin']:
                exe_path = os.path.join(msys2_path, subdir, f'{exe_name}.exe')
                if os.path.exists(exe_path):
                    return exe_path
    
    return None


def run_platform_command(cmd: List[str], **kwargs) -> subprocess.CompletedProcess:
    """Run a command with platform-specific handling"""
    if is_windows() and cmd[0] == 'rsync':
        # Replace rsync with the full path on Windows
        rsync_path = get_rsync_command()
        cmd[0] = rsync_path
        
        # Run rsync through cmd.exe for better compatibility
        cmd = ['cmd.exe', '/c'] + cmd
    
    # For Windows, ensure we handle paths correctly
    if is_windows():
        # Convert Unix-style paths to Windows paths in arguments
        cmd = [convert_path_for_platform(arg) if '/' in arg and ':' not in arg else arg for arg in cmd]
    
    return subprocess.run(cmd, **kwargs)


def convert_path_for_platform(path: str) -> str:
    """Convert a path to the appropriate format for the current platform"""
    if is_windows() and path.startswith('/'):
        # Convert Unix absolute paths to Windows paths
        # Handle WSL paths like /mnt/c/... to C:/...
        if path.startswith('/mnt/'):
            parts = path.split('/')
            if len(parts) > 2:
                drive = parts[2].upper()
                rest = '/'.join(parts[3:])
                return f'{drive}:/{rest}'
        # For other Unix paths, assume they're relative to MSYS2 root
        elif path == '/dev/null':
            return 'NUL'
        elif path == '/tmp':
            return get_temp_dir()
    return path


def get_ssh_known_hosts_path() -> str:
    """Get the SSH known_hosts file path for the current platform"""
    ssh_dir = Path.home() / '.ssh'
    known_hosts = ssh_dir / 'known_hosts'
    
    if is_windows():
        # Windows might use different location
        if not ssh_dir.exists():
            # Try Windows OpenSSH location
            programdata_ssh = Path('C:/ProgramData/ssh')
            if programdata_ssh.exists():
                return str(programdata_ssh / 'known_hosts')
    
    return str(known_hosts)


def create_temp_file(suffix: str = '', prefix: str = 'tmp', delete: bool = True) -> str:
    """Create a temporary file in a platform-appropriate way"""
    import tempfile
    
    # On Windows, we need to handle temp files differently
    if is_windows():
        # Use Windows temp directory
        temp_dir = get_temp_dir()
        fd, path = tempfile.mkstemp(suffix=suffix, prefix=prefix, dir=temp_dir)
        os.close(fd)  # Close the file descriptor
        return path
    else:
        # On Unix, use standard tempfile
        f = tempfile.NamedTemporaryFile(mode='w', delete=False, suffix=suffix, prefix=prefix)
        f.close()
        return f.name


def set_file_permissions(path: str, mode: int):
    """Set file permissions in a platform-appropriate way"""
    if is_unix():
        os.chmod(path, mode)
    elif is_windows():
        # Windows doesn't support Unix-style permissions
        # We can try to set read-only attribute for 0o400 type permissions
        import stat
        try:
            if mode & 0o200 == 0:  # If write permission is not set
                os.chmod(path, stat.S_IREAD)
            else:
                os.chmod(path, stat.S_IWRITE | stat.S_IREAD)
        except:
            # Ignore permission errors on Windows
            pass


def get_rsync_ssh_command(ssh_opts: str) -> str:
    """Get the SSH command string for rsync -e option"""
    if is_windows():
        # For Windows, we need to properly escape the SSH command for rsync
        msys2_ssh = find_msys2_executable('ssh')
        if msys2_ssh:
            # Use forward slashes for MSYS2
            msys2_ssh = msys2_ssh.replace('\\', '/')
            return f'{msys2_ssh} {ssh_opts}'
        elif shutil.which('ssh'):
            return f'ssh {ssh_opts}'
        else:
            raise RuntimeError("SSH not found for rsync")
    else:
        return f'ssh {ssh_opts}'


def prepare_rsync_paths(source: str, dest: str) -> Tuple[str, str]:
    """Prepare source and destination paths for rsync on current platform"""
    if is_windows():
        # Convert local Windows paths to MSYS2/Cygwin format for rsync
        def convert_local_path(path: str) -> str:
            # If it's a remote path (contains :), leave it as is
            if '@' in path and ':' in path.split('@')[1]:
                return path
            
            # Convert Windows path to MSYS2 format
            path_obj = Path(path)
            if path_obj.is_absolute():
                # Convert C:\path\to\file to /c/path/to/file
                drive = path_obj.drive[0].lower()
                rest = str(path_obj).replace(path_obj.drive + '\\', '').replace('\\', '/')
                return f'/{drive}/{rest}'
            else:
                # Relative paths just need backslash conversion
                return path.replace('\\', '/')
        
        # Convert source path if it's local
        if '@' not in source:
            source = convert_local_path(source)
        
        # Convert dest path if it's local
        if '@' not in dest:
            dest = convert_local_path(dest)
    
    return source, dest