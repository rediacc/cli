#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Rediacc CLI Sync - Rsync-based synchronization utility for Rediacc
Handles secure file synchronization between local system and Rediacc repositories using rsync over SSH
"""
import argparse
import os
import subprocess
import sys
from pathlib import Path
from typing import Dict, Any, Optional

# Add parent directory to path for module imports
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'modules'))

# Import common functionality from core module
from rediacc_cli_core import (
    colorize,
    validate_cli_tool,
    RepositoryConnection,
    setup_ssh_for_connection,
    is_windows
)

# Import token manager
from token_manager import TokenManager

# Import logging configuration
from logging_config import setup_logging, get_logger

import shutil
import platform
from typing import List, Tuple

# Platform-specific rsync utilities
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

def run_platform_command(cmd: List[str], **kwargs) -> subprocess.CompletedProcess:
    """Run a command with platform-specific handling"""
    logger = get_logger(__name__)
    
    if is_windows() and cmd[0] == 'rsync':
        # Replace rsync with the full path on Windows
        try:
            rsync_path = get_rsync_command()
            cmd[0] = rsync_path
            logger.debug(f"Windows rsync path: {rsync_path}")
            logger.debug(f"Full command: {cmd}")
        except RuntimeError as e:
            logger.error(f"Failed to find rsync: {e}")
            raise
        
        # On Windows, execute directly without cmd.exe for better compatibility
        # The MSYS2 rsync executable should work directly
    
    return subprocess.run(cmd, **kwargs)


def get_rsync_changes(source: str, dest: str, ssh_cmd: str, options: Dict[str, Any], universal_user: str = None) -> Optional[str]:
    """Get list of changes that rsync would make using --dry-run"""
    # Convert paths for platform
    source, dest = prepare_rsync_paths(source, dest)
    
    # Base rsync options for dry run
    rsync_cmd = [get_rsync_command(), '-av', '--dry-run', '--itemize-changes']
    
    # Add SSH command
    rsync_cmd.extend(['-e', ssh_cmd])
    
    # If universal_user is provided and we're checking remote (source or dest has @), use sudo
    if universal_user and ('@' in source or '@' in dest):
        rsync_cmd.extend(['--rsync-path', f'sudo -u {universal_user} rsync'])
    
    # Add mirror option (--delete) with socket exclusion
    if options.get('mirror'):
        rsync_cmd.append('--delete')
        # Exclude socket files to prevent deletion of plugin sockets
        rsync_cmd.extend(['--exclude', '*.sock'])
    
    # Add verify mode options
    if options.get('verify'):
        rsync_cmd.extend(['--checksum', '--ignore-times'])
    else:
        rsync_cmd.extend(['--partial', '--append-verify'])
    
    # Add source and destination
    rsync_cmd.extend([source, dest])
    
    # Run rsync in dry-run mode
    result = run_platform_command(rsync_cmd, capture_output=True, text=True)
    
    if result.returncode == 0:
        return result.stdout
    else:
        print(colorize(f"Error during dry-run: {result.stderr}", 'RED'))
        return None

def parse_rsync_changes(dry_run_output: str) -> Dict[str, list]:
    """Parse rsync dry-run output and categorize changes"""
    changes = {
        'new_files': [],
        'modified_files': [],
        'deleted_files': [],
        'new_dirs': [],
        'other': []
    }
    
    for line in dry_run_output.strip().split('\n'):
        if not line or line.startswith('sending ') or line.startswith('receiving ') or line.startswith('sent ') or line.startswith('total size'):
            continue
            
        # Parse itemize-changes format
        # Format: YXcstpoguax path/to/file
        # where Y = type, X = action
        if len(line) > 11 and line[11] == ' ':
            flags = line[:11]
            filename = line[12:].strip()
            
            # Check for deletions
            if '*deleting' in line:
                changes['deleted_files'].append(filename)
            # Check for new directories
            elif flags[0] == 'c' and flags[1] == 'd':
                changes['new_dirs'].append(filename)
            # Check for new files
            elif flags[0] in ['>', '<'] and flags[1] == 'f' and flags[2] == '+':
                changes['new_files'].append(filename)
            # Check for modified files
            elif flags[0] in ['>', '<'] and flags[1] == 'f':
                changes['modified_files'].append(filename)
            else:
                changes['other'].append(line)
        else:
            # Handle deletion lines
            if line.startswith('deleting '):
                filename = line[9:].strip()
                changes['deleted_files'].append(filename)
            else:
                changes['other'].append(line)
    
    return changes

def display_changes_and_confirm(changes: Dict[str, list], operation: str) -> bool:
    """Display planned changes and ask for confirmation"""
    print(colorize(f"\n{operation} Preview:", 'HEADER'))
    print(colorize("=" * 60, 'BLUE'))
    
    total_changes = 0
    
    if changes['new_files']:
        print(colorize(f"\nNew files to be transferred ({len(changes['new_files'])}):", 'GREEN'))
        for f in changes['new_files'][:10]:  # Show first 10
            print(f"  + {f}")
        if len(changes['new_files']) > 10:
            print(f"  ... and {len(changes['new_files']) - 10} more")
        total_changes += len(changes['new_files'])
    
    if changes['modified_files']:
        print(colorize(f"\nFiles to be updated ({len(changes['modified_files'])}):", 'YELLOW'))
        for f in changes['modified_files'][:10]:  # Show first 10
            print(f"  ~ {f}")
        if len(changes['modified_files']) > 10:
            print(f"  ... and {len(changes['modified_files']) - 10} more")
        total_changes += len(changes['modified_files'])
    
    if changes['deleted_files']:
        print(colorize(f"\nFiles to be deleted ({len(changes['deleted_files'])}):", 'RED'))
        for f in changes['deleted_files'][:10]:  # Show first 10
            print(f"  - {f}")
        if len(changes['deleted_files']) > 10:
            print(f"  ... and {len(changes['deleted_files']) - 10} more")
        total_changes += len(changes['deleted_files'])
    
    if changes['new_dirs']:
        print(colorize(f"\nNew directories to be created ({len(changes['new_dirs'])}):", 'GREEN'))
        for d in changes['new_dirs'][:5]:  # Show first 5
            print(f"  + {d}/")
        if len(changes['new_dirs']) > 5:
            print(f"  ... and {len(changes['new_dirs']) - 5} more")
        total_changes += len(changes['new_dirs'])
    
    print(colorize("\n" + "=" * 60, 'BLUE'))
    print(f"Total changes: {total_changes}")
    
    if total_changes == 0:
        print(colorize("\nNo changes needed - everything is in sync!", 'GREEN'))
        return False
    
    # Ask for confirmation
    while True:
        response = input(colorize("\nProceed with these changes? [y/N/d(etails)]: ", 'BOLD')).lower().strip()
        
        if response == 'd':
            # Show all changes
            print(colorize("\nDetailed change list:", 'HEADER'))
            if changes['new_files']:
                print(colorize(f"\nAll new files ({len(changes['new_files'])}):", 'GREEN'))
                for f in changes['new_files']:
                    print(f"  + {f}")
            if changes['modified_files']:
                print(colorize(f"\nAll modified files ({len(changes['modified_files'])}):", 'YELLOW'))
                for f in changes['modified_files']:
                    print(f"  ~ {f}")
            if changes['deleted_files']:
                print(colorize(f"\nAll deleted files ({len(changes['deleted_files'])}):", 'RED'))
                for f in changes['deleted_files']:
                    print(f"  - {f}")
            if changes['new_dirs']:
                print(colorize(f"\nAll new directories ({len(changes['new_dirs'])}):", 'GREEN'))
                for d in changes['new_dirs']:
                    print(f"  + {d}/")
            continue
        elif response == 'y':
            return True
        else:
            print(colorize("Operation cancelled by user.", 'YELLOW'))
            return False

def perform_rsync(source: str, dest: str, ssh_cmd: str, options: Dict[str, Any], universal_user: str = None):
    """Perform rsync operation with given options"""
    # Convert paths for platform
    source, dest = prepare_rsync_paths(source, dest)
    
    # If confirm mode is enabled, do a dry run first
    if options.get('confirm'):
        print(colorize("Analyzing changes...", 'BLUE'))
        dry_run_output = get_rsync_changes(source, dest, ssh_cmd, options, universal_user)
        
        if dry_run_output is None:
            print(colorize("Failed to analyze changes", 'RED'))
            return False
        
        # Parse and display changes
        changes = parse_rsync_changes(dry_run_output)
        operation = "Upload" if '@' in dest else "Download"
        
        if not display_changes_and_confirm(changes, operation):
            return False
    
    # Base rsync options
    rsync_cmd = [get_rsync_command(), '-av', '--verbose', '--inplace', '--no-whole-file']
    
    # Add SSH command
    rsync_cmd.extend(['-e', ssh_cmd])
    
    # If universal_user is provided and we're accessing remote (source or dest has @), use sudo
    if universal_user and ('@' in source or '@' in dest):
        rsync_cmd.extend(['--rsync-path', f'sudo -u {universal_user} rsync'])
    
    # Add mirror option (--delete) with socket exclusion
    if options.get('mirror'):
        rsync_cmd.append('--delete')
        # Exclude socket files to prevent deletion of plugin sockets
        rsync_cmd.extend(['--exclude', '*.sock'])
    
    # Add verify mode options (checksum verification)
    if options.get('verify'):
        # In verify mode, use checksums and don't skip files
        rsync_cmd.extend(['--checksum', '--ignore-times'])
    else:
        # Normal mode - accept files being modified during transfer
        rsync_cmd.extend(['--partial', '--append-verify'])
    
    # Add progress
    rsync_cmd.append('--progress')
    
    # Add source and destination
    rsync_cmd.extend([source, dest])
    
    # Show the command being executed
    print(colorize(f"Executing: {' '.join(rsync_cmd)}", 'BLUE'))
    
    # Run rsync
    result = run_platform_command(rsync_cmd, capture_output=True, text=True)
    
    # Check for success or acceptable errors
    if result.returncode == 0:
        return True
    elif result.returncode == 23:
        # Code 23 is "some files/attrs were not transferred"
        # This can happen with permission issues on files like lost+found
        if "lost+found" in result.stderr or "Permission denied" in result.stderr:
            print(colorize("Warning: Some files could not be accessed (usually system files like lost+found)", 'YELLOW'))
            return True
    
    # For other errors, print stderr and fail
    if result.stderr:
        print(colorize(f"Error: {result.stderr}", 'RED'))
    return False

def upload(args):
    """Handle upload command"""
    print(colorize(f"Uploading from {args.local} to {args.machine}:{args.repo}", 'HEADER'))
    
    # Validate source
    source_path = Path(args.local)
    if not source_path.exists():
        print(colorize(f"Local path '{args.local}' does not exist", 'RED'))
        sys.exit(1)
    
    # Token is already managed by TokenManager, no need to set it again
    
    # Create repository connection
    conn = RepositoryConnection(args.team, args.machine, args.repo)
    conn.connect()
    
    # Set up SSH
    # In dev mode, temporarily disable host key checking
    if args.dev:
        original_host_entry = conn.connection_info.get('host_entry')
        conn.connection_info['host_entry'] = None
    
    ssh_opts, ssh_key_file, known_hosts_file = conn.setup_ssh()
    ssh_cmd = get_rsync_ssh_command(ssh_opts)
    
    # Restore original host entry
    if args.dev and 'original_host_entry' in locals():
        conn.connection_info['host_entry'] = original_host_entry
    
    try:
        # Build destination path using repository paths
        dest_path = f"{conn.ssh_destination}:{conn.repo_paths['mount_path']}/"
        
        # Ensure source has trailing slash for directory contents
        source = str(source_path)
        if source_path.is_dir() and not source.endswith('/'):
            source += '/'
        
        # Perform rsync
        print(f"Starting rsync transfer...")
        universal_user = conn.connection_info.get('universal_user')
        success = perform_rsync(source, dest_path, ssh_cmd, {
            'mirror': args.mirror,
            'verify': args.verify,
            'confirm': args.confirm
        }, universal_user)
        
        if success:
            print(colorize("Upload completed successfully!", 'GREEN'))
        else:
            print(colorize("Upload failed!", 'RED'))
            sys.exit(1)
            
    finally:
        # Clean up SSH key and known_hosts files
        conn.cleanup_ssh(ssh_key_file, known_hosts_file)

def download(args):
    """Handle download command"""
    print(colorize(f"Downloading from {args.machine}:{args.repo} to {args.local}", 'HEADER'))
    
    # Create destination if it doesn't exist
    dest_path = Path(args.local)
    dest_path.mkdir(parents=True, exist_ok=True)
    
    # Token is already managed by TokenManager, no need to set it again
    
    # Create repository connection
    conn = RepositoryConnection(args.team, args.machine, args.repo)
    conn.connect()
    
    # Set up SSH
    # In dev mode, temporarily disable host key checking
    if args.dev:
        original_host_entry = conn.connection_info.get('host_entry')
        conn.connection_info['host_entry'] = None
    
    ssh_opts, ssh_key_file, known_hosts_file = conn.setup_ssh()
    ssh_cmd = get_rsync_ssh_command(ssh_opts)
    
    # Restore original host entry
    if args.dev and 'original_host_entry' in locals():
        conn.connection_info['host_entry'] = original_host_entry
    
    try:
        # Build source path using repository paths
        source_path = f"{conn.ssh_destination}:{conn.repo_paths['mount_path']}/"
        
        # Ensure destination has trailing slash
        dest = str(dest_path)
        if not dest.endswith('/'):
            dest += '/'
        
        # Perform rsync
        print(f"Starting rsync transfer...")
        universal_user = conn.connection_info.get('universal_user')
        success = perform_rsync(source_path, dest, ssh_cmd, {
            'mirror': args.mirror,
            'verify': args.verify,
            'confirm': args.confirm
        }, universal_user)
        
        if success:
            print(colorize("Download completed successfully!", 'GREEN'))
        else:
            print(colorize("Download failed!", 'RED'))
            sys.exit(1)
            
    finally:
        # Clean up SSH key and known_hosts files
        conn.cleanup_ssh(ssh_key_file, known_hosts_file)

def main():
    parser = argparse.ArgumentParser(
        description='Rediacc CLI Sync - Rsync-based synchronization utility',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  Upload a folder to repository:
    %(prog)s upload --token=<GUID> --local=/my/files --machine=server1 --repo=data
    
  Download repository to local folder:
    %(prog)s download --token=<GUID> --machine=server1 --repo=data --local=/backup
    
  Upload with mirror (delete remote files not in local):
    %(prog)s upload --token=<GUID> --local=/my/files --machine=server1 --repo=data --mirror
    
  Download with checksum verification:
    %(prog)s download --token=<GUID> --machine=server1 --repo=data --local=/backup --verify
    
  Upload with preview and confirmation:
    %(prog)s upload --token=<GUID> --local=/my/files --machine=server1 --repo=data --confirm
    
  Download with all options:
    %(prog)s download --token=<GUID> --machine=server1 --repo=data --local=/backup --mirror --verify --confirm
"""
    )
    
    # Add GUI option as top-level argument
    parser.add_argument('--gui', action='store_true',
                       help='Launch graphical user interface')
    # Add verbose logging option
    parser.add_argument('--verbose', '-v', action='store_true',
                       help='Enable verbose logging output')
    
    subparsers = parser.add_subparsers(dest='command', help='Commands')
    
    # Upload command
    upload_parser = subparsers.add_parser('upload', help='Upload files to repository')
    upload_parser.add_argument('--token', required=False, help='Authentication token (GUID) - uses saved token if not specified')
    upload_parser.add_argument('--team', required=True, help='Team name')
    upload_parser.add_argument('--local', required=True, help='Local path to upload from')
    upload_parser.add_argument('--machine', required=True, help='Target machine name')
    upload_parser.add_argument('--repo', required=True, help='Target repository name')
    upload_parser.add_argument('--mirror', action='store_true', help='Delete remote files not present locally')
    upload_parser.add_argument('--verify', action='store_true', help='Verify all transfers with checksums')
    upload_parser.add_argument('--confirm', action='store_true', help='Preview changes and ask for confirmation')
    upload_parser.add_argument('--dev', action='store_true', help='Development mode - relaxes SSH host key checking')
    upload_parser.set_defaults(func=upload)
    
    # Download command
    download_parser = subparsers.add_parser('download', help='Download files from repository')
    download_parser.add_argument('--token', required=False, help='Authentication token (GUID) - uses saved token if not specified')
    download_parser.add_argument('--team', required=True, help='Team name')
    download_parser.add_argument('--machine', required=True, help='Source machine name')
    download_parser.add_argument('--repo', required=True, help='Source repository name')
    download_parser.add_argument('--local', required=True, help='Local path to download to')
    download_parser.add_argument('--mirror', action='store_true', help='Delete local files not present remotely')
    download_parser.add_argument('--verify', action='store_true', help='Verify all transfers with checksums')
    download_parser.add_argument('--confirm', action='store_true', help='Preview changes and ask for confirmation')
    download_parser.add_argument('--dev', action='store_true', help='Development mode - relaxes SSH host key checking')
    download_parser.set_defaults(func=download)
    
    args = parser.parse_args()
    
    # Setup logging based on verbose flag
    setup_logging(verbose=args.verbose)
    logger = get_logger(__name__)
    
    # Log startup information in verbose mode
    if args.verbose:
        logger.debug("Rediacc CLI Sync starting up")
        logger.debug(f"Command: {args.command}")
        logger.debug(f"Arguments: {vars(args)}")
    
    # Check if GUI mode is requested
    if args.gui:
        try:
            from rediacc_cli_gui import launch_gui
            launch_gui()
            sys.exit(0)
        except ImportError as e:
            print(colorize("Error: Failed to launch GUI. Make sure tkinter is installed.", 'RED'))
            print(colorize(f"Details: {str(e)}", 'RED'))
            sys.exit(1)
        except Exception as e:
            print(colorize(f"Error launching GUI: {str(e)}", 'RED'))
            sys.exit(1)
    
    if not args.command:
        parser.print_help()
        sys.exit(1)
    
    # Handle token authentication
    if hasattr(args, 'token'):
        if args.token:
            # If token provided via command line, set it as environment variable
            os.environ['REDIACC_TOKEN'] = args.token
        else:
            # Verify token exists in TokenManager
            token = TokenManager.get_token()
            if not token:
                parser.error("No authentication token available. Please login first.")
    
    # Validate CLI tool exists
    validate_cli_tool()
    
    # Execute the command
    args.func(args)

if __name__ == '__main__':
    main()