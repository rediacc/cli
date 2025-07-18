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
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import common functionality from core module
from rediacc_cli_core import (
    colorize,
    validate_cli_tool,
    RepositoryConnection,
    setup_ssh_for_connection,
    is_windows
)

# Import from consolidated core module
from core import (
    TokenManager,
    setup_logging, get_logger
)

import shutil
import platform
from typing import List, Tuple

# Platform-specific rsync utilities
def find_msys2_executable(exe_name: str) -> Optional[str]:
    """Find an executable in MSYS2 installation"""
    if not is_windows():
        return None
    
    msys2_paths = filter(None, [
        os.environ.get('MSYS2_ROOT'),
        'C:\\msys64',
        'C:\\msys2',
        os.path.expanduser('~\\msys64'),
        os.path.expanduser('~\\msys2'),
    ])
    
    for msys2_path in msys2_paths:
        if not os.path.exists(msys2_path):
            continue
        
        for subdir in ['usr\\bin', 'mingw64\\bin', 'mingw32\\bin']:
            exe_path = os.path.join(msys2_path, subdir, f'{exe_name}.exe')
            if os.path.exists(exe_path):
                return exe_path
    
    return None

def get_rsync_command() -> str:
    """Get the rsync command for the current platform"""
    if is_windows():
        if msys2_rsync := find_msys2_executable('rsync'):
            return msys2_rsync
        raise RuntimeError("rsync not found. Please install MSYS2 with rsync package.")
    
    if shutil.which('rsync'):
        return 'rsync'
    raise RuntimeError("rsync not found. Please install rsync.")

def get_rsync_ssh_command(ssh_opts: str) -> str:
    """Get the SSH command string for rsync -e option"""
    if not is_windows():
        return f'ssh {ssh_opts}'
    
    if msys2_ssh := find_msys2_executable('ssh'):
        return f'{msys2_ssh.replace("\\", "/")} {ssh_opts}'
    
    if shutil.which('ssh'):
        return f'ssh {ssh_opts}'
    
    raise RuntimeError("SSH not found for rsync")

def prepare_rsync_paths(source: str, dest: str) -> Tuple[str, str]:
    """Prepare source and destination paths for rsync on current platform"""
    if not is_windows():
        return source, dest
    
    def convert_local_path(path: str) -> str:
        if '@' in path and ':' in path.split('@')[1]:
            return path
        
        path_obj = Path(path)
        if not path_obj.is_absolute():
            return path.replace('\\', '/')
        
        drive = path_obj.drive[0].lower()
        rest = str(path_obj).replace(path_obj.drive + '\\', '').replace('\\', '/')
        return f'/{drive}/{rest}'
    
    return (
        source if '@' in source else convert_local_path(source),
        dest if '@' in dest else convert_local_path(dest)
    )

def run_platform_command(cmd: List[str], **kwargs) -> subprocess.CompletedProcess:
    """Run a command with platform-specific handling"""
    logger = get_logger(__name__)
    
    if is_windows() and cmd[0] == 'rsync':
        try:
            cmd[0] = get_rsync_command()
            logger.debug(f"Windows rsync path: {cmd[0]}")
            logger.debug(f"Full command: {cmd}")
        except RuntimeError as e:
            logger.error(f"Failed to find rsync: {e}")
            raise
    
    return subprocess.run(cmd, **kwargs)


def get_rsync_changes(source: str, dest: str, ssh_cmd: str, options: Dict[str, Any], universal_user: str = None) -> Optional[str]:
    """Get list of changes that rsync would make using --dry-run"""
    source, dest = prepare_rsync_paths(source, dest)
    
    rsync_cmd = [get_rsync_command(), '-av', '--dry-run', '--itemize-changes', '-e', ssh_cmd]
    
    if universal_user and ('@' in source or '@' in dest):
        rsync_cmd.extend(['--rsync-path', f'sudo -u {universal_user} rsync'])
    
    if options.get('mirror'):
        rsync_cmd.extend(['--delete', '--exclude', '*.sock'])
    
    rsync_cmd.extend(
        ['--checksum', '--ignore-times'] if options.get('verify')
        else ['--partial', '--append-verify']
    )
    
    rsync_cmd.extend([source, dest])
    
    result = run_platform_command(rsync_cmd, capture_output=True, text=True)
    
    if result.returncode != 0:
        print(colorize(f"Error during dry-run: {result.stderr}", 'RED'))
        return None
    
    return result.stdout

def parse_rsync_changes(dry_run_output: str) -> Dict[str, list]:
    """Parse rsync dry-run output and categorize changes"""
    changes = {
        'new_files': [],
        'modified_files': [],
        'deleted_files': [],
        'new_dirs': [],
        'other': []
    }
    
    skip_prefixes = ('sending ', 'receiving ', 'sent ', 'total size')
    
    for line in dry_run_output.strip().split('\n'):
        if not line or any(line.startswith(prefix) for prefix in skip_prefixes):
            continue
        
        if line.startswith('deleting '):
            changes['deleted_files'].append(line[9:].strip())
            continue
        
        if len(line) > 11 and line[11] == ' ':
            flags, filename = line[:11], line[12:].strip()
            
            if '*deleting' in line:
                changes['deleted_files'].append(filename)
            elif flags[:2] == 'cd':
                changes['new_dirs'].append(filename)
            elif flags[0] in '><' and flags[1] == 'f':
                category = 'new_files' if flags[2] == '+' else 'modified_files'
                changes[category].append(filename)
            else:
                changes['other'].append(line)
        else:
            changes['other'].append(line)
    
    return changes

def display_changes_and_confirm(changes: Dict[str, list], operation: str) -> bool:
    """Display planned changes and ask for confirmation"""
    def show_changes_summary(limit: int = None):
        """Helper to display changes with optional limit"""
        categories = [
            ('new_files', 'New files to be transferred', 'GREEN', '+', ''),
            ('modified_files', 'Files to be updated', 'YELLOW', '~', ''),
            ('deleted_files', 'Files to be deleted', 'RED', '-', ''),
            ('new_dirs', 'New directories to be created', 'GREEN', '+', '/')
        ]
        
        for key, desc, color, prefix, suffix in categories:
            if not (items := changes[key]):
                continue
            
            print(colorize(f"\n{desc} ({len(items)}):", color))
            
            display_items = items[:limit] if limit else items
            for item in display_items:
                print(f"  {prefix} {item}{suffix}")
            
            if limit and len(items) > limit:
                print(f"  ... and {len(items) - limit} more")
    
    print(colorize(f"\n{operation} Preview:", 'HEADER'))
    print(colorize("=" * 60, 'BLUE'))
    
    show_changes_summary(limit=10)
    
    total_changes = sum(len(changes[k]) for k in ['new_files', 'modified_files', 'deleted_files', 'new_dirs'])
    
    print(colorize("\n" + "=" * 60, 'BLUE'))
    print(f"Total changes: {total_changes}")
    
    if total_changes == 0:
        print(colorize("\nNo changes needed - everything is in sync!", 'GREEN'))
        return False
    
    while True:
        response = input(colorize("\nProceed with these changes? [y/N/d(etails)]: ", 'BOLD')).lower().strip()
        
        if response == 'd':
            print(colorize("\nDetailed change list:", 'HEADER'))
            show_changes_summary()
        elif response == 'y':
            return True
        elif response in ('n', ''):
            print(colorize("Operation cancelled by user.", 'YELLOW'))
            return False

def perform_rsync(source: str, dest: str, ssh_cmd: str, options: Dict[str, Any], universal_user: str = None):
    """Perform rsync operation with given options"""
    source, dest = prepare_rsync_paths(source, dest)
    
    if options.get('confirm'):
        print(colorize("Analyzing changes...", 'BLUE'))
        if not (dry_run_output := get_rsync_changes(source, dest, ssh_cmd, options, universal_user)):
            print(colorize("Failed to analyze changes", 'RED'))
            return False
        
        changes = parse_rsync_changes(dry_run_output)
        operation = "Upload" if '@' in dest else "Download"
        
        if not display_changes_and_confirm(changes, operation):
            return False
    
    rsync_cmd = [
        get_rsync_command(), '-av', '--verbose', '--inplace', '--no-whole-file',
        '-e', ssh_cmd, '--progress'
    ]
    
    if universal_user and ('@' in source or '@' in dest):
        rsync_cmd.extend(['--rsync-path', f'sudo -u {universal_user} rsync'])
    
    if options.get('mirror'):
        rsync_cmd.extend(['--delete', '--exclude', '*.sock'])
    
    rsync_cmd.extend(
        ['--checksum', '--ignore-times'] if options.get('verify')
        else ['--partial', '--append-verify']
    )
    
    rsync_cmd.extend([source, dest])
    
    print(colorize(f"Executing: {' '.join(rsync_cmd)}", 'BLUE'))
    
    result = run_platform_command(rsync_cmd, capture_output=True, text=True)
    
    if result.returncode == 0:
        return True
    
    if result.returncode == 23 and any(x in result.stderr for x in ["lost+found", "Permission denied"]):
        print(colorize("Warning: Some files could not be accessed (usually system files like lost+found)", 'YELLOW'))
        return True
    
    if result.stderr:
        print(colorize(f"Error: {result.stderr}", 'RED'))
    return False

def upload(args):
    """Handle upload command"""
    print(colorize(f"Uploading from {args.local} to {args.machine}:{args.repo}", 'HEADER'))
    
    source_path = Path(args.local)
    if not source_path.exists():
        print(colorize(f"Local path '{args.local}' does not exist", 'RED'))
        sys.exit(1)
    
    conn = RepositoryConnection(args.team, args.machine, args.repo)
    conn.connect()
    
    original_host_entry = conn.connection_info.get('host_entry') if args.dev else None
    if args.dev:
        conn.connection_info['host_entry'] = None
    
    ssh_opts, ssh_key_file, known_hosts_file = conn.setup_ssh()
    ssh_cmd = get_rsync_ssh_command(ssh_opts)
    
    if args.dev and original_host_entry is not None:
        conn.connection_info['host_entry'] = original_host_entry
    
    try:
        dest_path = f"{conn.ssh_destination}:{conn.repo_paths['mount_path']}/"
        source = str(source_path) + ('/' if source_path.is_dir() and not str(source_path).endswith('/') else '')
        
        print("Starting rsync transfer...")
        options = {
            'mirror': args.mirror,
            'verify': args.verify,
            'confirm': args.confirm
        }
        success = perform_rsync(source, dest_path, ssh_cmd, options, conn.connection_info.get('universal_user'))
        
        print(colorize("Upload completed successfully!" if success else "Upload failed!", 
                      'GREEN' if success else 'RED'))
        if not success:
            sys.exit(1)
            
    finally:
        conn.cleanup_ssh(ssh_key_file, known_hosts_file)

def download(args):
    """Handle download command"""
    print(colorize(f"Downloading from {args.machine}:{args.repo} to {args.local}", 'HEADER'))
    
    dest_path = Path(args.local)
    dest_path.mkdir(parents=True, exist_ok=True)
    
    conn = RepositoryConnection(args.team, args.machine, args.repo)
    conn.connect()
    
    original_host_entry = conn.connection_info.get('host_entry') if args.dev else None
    if args.dev:
        conn.connection_info['host_entry'] = None
    
    ssh_opts, ssh_key_file, known_hosts_file = conn.setup_ssh()
    ssh_cmd = get_rsync_ssh_command(ssh_opts)
    
    if args.dev and original_host_entry is not None:
        conn.connection_info['host_entry'] = original_host_entry
    
    try:
        source_path = f"{conn.ssh_destination}:{conn.repo_paths['mount_path']}/"
        dest = str(dest_path) + ('/' if not str(dest_path).endswith('/') else '')
        
        print("Starting rsync transfer...")
        options = {
            'mirror': args.mirror,
            'verify': args.verify,
            'confirm': args.confirm
        }
        success = perform_rsync(source_path, dest, ssh_cmd, options, conn.connection_info.get('universal_user'))
        
        print(colorize("Download completed successfully!" if success else "Download failed!", 
                      'GREEN' if success else 'RED'))
        if not success:
            sys.exit(1)
            
    finally:
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
    parser.add_argument('--verbose', '-v', action='store_true',
                       help='Enable verbose logging output')
    
    subparsers = parser.add_subparsers(dest='command', help='Commands')
    
    common_args = [
        ('--token', {'required': False, 'help': 'Authentication token (GUID) - uses saved token if not specified'}),
        ('--team', {'required': True, 'help': 'Team name'}),
        ('--machine', {'required': True, 'help': 'Machine name'}),
        ('--repo', {'required': True, 'help': 'Repository name'}),
        ('--mirror', {'action': 'store_true', 'help': 'Delete files not present in source'}),
        ('--verify', {'action': 'store_true', 'help': 'Verify all transfers with checksums'}),
        ('--confirm', {'action': 'store_true', 'help': 'Preview changes and ask for confirmation'}),
        ('--dev', {'action': 'store_true', 'help': 'Development mode - relaxes SSH host key checking'})
    ]
    
    for cmd_name, cmd_func, cmd_help in [
        ('upload', upload, 'Upload files to repository'),
        ('download', download, 'Download files from repository')
    ]:
        parser_cmd = subparsers.add_parser(cmd_name, help=cmd_help)
        parser_cmd.add_argument('--local', required=True, 
                               help=f'Local path to {cmd_name} {"from" if cmd_name == "upload" else "to"}')
        for arg, kwargs in common_args:
            parser_cmd.add_argument(arg, **kwargs)
        parser_cmd.set_defaults(func=cmd_func)
    
    args = parser.parse_args()
    
    setup_logging(verbose=args.verbose)
    logger = get_logger(__name__)
    
    if args.verbose:
        logger.debug("Rediacc CLI Sync starting up")
        logger.debug(f"Command: {args.command}")
        logger.debug(f"Arguments: {vars(args)}")
    
    if not args.command:
        parser.print_help()
        sys.exit(1)
    
    if hasattr(args, 'token') and args.token:
        os.environ['REDIACC_TOKEN'] = args.token
    elif not TokenManager.get_token():
        parser.error("No authentication token available. Please login first.")
    
    validate_cli_tool()
    args.func(args)

if __name__ == '__main__':
    main()