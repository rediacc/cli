#!/usr/bin/env python3
"""
Rediacc CLI VSCode - Launch VSCode with SSH remote connection and environment setup
"""

import argparse
import subprocess
import sys
import os
import shutil
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from cli._version import __version__
from cli.core.shared import (
    colorize, add_common_arguments,
    error_exit, initialize_cli_command, RepositoryConnection,
    get_ssh_key_from_vault, SSHConnection, get_machine_info_with_team,
    get_machine_connection_info, _get_universal_user_info
)

from cli.core.config import setup_logging, get_logger
from cli.core.telemetry import track_command, initialize_telemetry, shutdown_telemetry
from cli.core.repository_env import (
    get_repository_environment, get_machine_environment, format_ssh_setenv
)


def find_vscode_executable():
    """Find VS Code executable on the system"""
    # Check environment variable first
    vscode_path = os.environ.get('REDIACC_VSCODE_PATH')
    if vscode_path and os.path.exists(vscode_path):
        return vscode_path

    # Try common VS Code command names
    vscode_commands = ['code', 'code-insiders', 'code-oss', 'codium']

    for cmd in vscode_commands:
        vscode_path = shutil.which(cmd)
        if vscode_path:
            return vscode_path

    return None


def sanitize_hostname(name: str) -> str:
    """Sanitize hostname for SSH config"""
    return name.replace(' ', '-').replace('/', '-').replace('\\', '-')


def launch_vscode_repo(args):
    """Launch VSCode with repository connection"""
    logger = get_logger(__name__)

    print(colorize(f"Connecting to repository '{args.repo}' on machine '{args.machine}'...", 'HEADER'))

    # Find VSCode executable
    vscode_cmd = find_vscode_executable()
    if not vscode_cmd:
        error_exit(
            "VS Code is not installed or not found in PATH.\n\n"
            "Please install VS Code from: https://code.visualstudio.com/\n\n"
            "You can also set REDIACC_VSCODE_PATH environment variable to specify the path."
        )

    # Connect to repository
    conn = RepositoryConnection(args.team, args.machine, args.repo)
    conn.connect()

    # Get universal user info
    universal_user_name, universal_user_id, company_id = _get_universal_user_info()

    # Get environment variables using shared module
    env_vars = get_repository_environment(args.team, args.machine, args.repo,
                                          connection_info=conn.connection_info,
                                          repo_paths=conn.repo_paths)

    # Get SSH key
    ssh_key = get_ssh_key_from_vault(args.team)
    if not ssh_key:
        error_exit(f"SSH private key not found in vault for team '{args.team}'")

    host_entry = None if args.dev else conn.connection_info.get('host_entry')

    with SSHConnection(ssh_key, host_entry, prefer_agent=True) as ssh_conn:
        # Create SSH config entry
        connection_name = f"rediacc-{sanitize_hostname(args.team)}-{sanitize_hostname(args.machine)}-{sanitize_hostname(args.repo)}"
        ssh_host = conn.connection_info['ip']
        ssh_user = conn.connection_info['user']
        remote_path = conn.repo_paths['mount_path']

        # Format environment variables as SetEnv directives
        setenv_directives = format_ssh_setenv(env_vars)

        # Build SSH config entry
        remote_command_line = ""
        if universal_user_id and universal_user_id != ssh_user:
            remote_command_line = f"    RemoteCommand sudo -H -u {universal_user_id} bash\n"

        # Parse SSH options
        ssh_opts_lines = []
        if ssh_conn.ssh_opts:
            opts = ssh_conn.ssh_opts.split()
            i = 0
            while i < len(opts):
                if opts[i] == '-o' and i + 1 < len(opts):
                    option = opts[i + 1]
                    if '=' in option:
                        key, value = option.split('=', 1)
                        if key not in ['IdentityFile', 'UserKnownHostsFile']:
                            ssh_opts_lines.append(f"    {key} {value}")
                    i += 2
                elif opts[i] == '-i':
                    i += 2
                else:
                    i += 1

        ssh_config_entry = f"""Host {connection_name}
    HostName {ssh_host}
    User {ssh_user}
{remote_command_line}{chr(10).join(ssh_opts_lines) if ssh_opts_lines else ''}
{setenv_directives}
    ServerAliveInterval 60
    ServerAliveCountMax 3
"""

        # Add SSH config to user's SSH config file
        ssh_config_path = os.path.expanduser('~/.ssh/config')
        ssh_dir = os.path.dirname(ssh_config_path)
        os.makedirs(ssh_dir, exist_ok=True)
        os.chmod(ssh_dir, 0o700)

        # Check if this host already exists in SSH config
        host_exists = False
        if os.path.exists(ssh_config_path):
            with open(ssh_config_path, 'r') as f:
                if f"Host {connection_name}" in f.read():
                    host_exists = True

        # Add or update SSH config entry
        if not host_exists:
            with open(ssh_config_path, 'a') as f:
                f.write(f"\n# Rediacc VS Code connection\n")
                f.write(ssh_config_entry)
                f.write("\n")
            logger.info(f"Added SSH config entry for {connection_name}")
        else:
            logger.info(f"SSH config entry already exists for {connection_name}")

        # Launch VS Code
        vscode_uri = f"vscode-remote://ssh-remote+{connection_name}{remote_path}"
        cmd = [vscode_cmd, '--folder-uri', vscode_uri]

        logger.info(f"Launching VS Code: {' '.join(cmd)}")
        print(colorize(f"Opening VS Code for repository '{args.repo}'...", 'GREEN'))

        result = subprocess.run(cmd)
        return result.returncode


def launch_vscode_machine(args):
    """Launch VSCode with machine-only connection"""
    logger = get_logger(__name__)

    print(colorize(f"Connecting to machine '{args.machine}'...", 'HEADER'))

    # Find VSCode executable
    vscode_cmd = find_vscode_executable()
    if not vscode_cmd:
        error_exit(
            "VS Code is not installed or not found in PATH.\n\n"
            "Please install VS Code from: https://code.visualstudio.com/\n\n"
            "You can also set REDIACC_VSCODE_PATH environment variable to specify the path."
        )

    # Get machine info
    machine_info = get_machine_info_with_team(args.team, args.machine)
    connection_info = get_machine_connection_info(machine_info)

    # Get universal user info
    universal_user_name, universal_user_id, company_id = _get_universal_user_info()

    # Get environment variables using shared module
    env_vars = get_machine_environment(args.team, args.machine,
                                       connection_info=connection_info)

    # Calculate remote path
    if universal_user_id:
        remote_path = f"{connection_info['datastore']}/{universal_user_id}"
    else:
        remote_path = connection_info['datastore']

    # Get SSH key
    ssh_key = get_ssh_key_from_vault(args.team)
    if not ssh_key:
        error_exit(f"SSH private key not found in vault for team '{args.team}'")

    host_entry = None if args.dev else connection_info.get('host_entry')

    with SSHConnection(ssh_key, host_entry, prefer_agent=True) as ssh_conn:
        # Create SSH config entry
        connection_name = f"rediacc-{sanitize_hostname(args.team)}-{sanitize_hostname(args.machine)}"
        ssh_host = connection_info['ip']
        ssh_user = connection_info['user']

        # Format environment variables as SetEnv directives
        setenv_directives = format_ssh_setenv(env_vars)

        # Build SSH config entry
        remote_command_line = ""
        if universal_user_id and universal_user_id != ssh_user:
            remote_command_line = f"    RemoteCommand sudo -H -u {universal_user_id} bash\n"

        # Parse SSH options
        ssh_opts_lines = []
        if ssh_conn.ssh_opts:
            opts = ssh_conn.ssh_opts.split()
            i = 0
            while i < len(opts):
                if opts[i] == '-o' and i + 1 < len(opts):
                    option = opts[i + 1]
                    if '=' in option:
                        key, value = option.split('=', 1)
                        if key not in ['IdentityFile', 'UserKnownHostsFile']:
                            ssh_opts_lines.append(f"    {key} {value}")
                    i += 2
                elif opts[i] == '-i':
                    i += 2
                else:
                    i += 1

        ssh_config_entry = f"""Host {connection_name}
    HostName {ssh_host}
    User {ssh_user}
{remote_command_line}{chr(10).join(ssh_opts_lines) if ssh_opts_lines else ''}
{setenv_directives}
    ServerAliveInterval 60
    ServerAliveCountMax 3
"""

        # Add SSH config to user's SSH config file
        ssh_config_path = os.path.expanduser('~/.ssh/config')
        ssh_dir = os.path.dirname(ssh_config_path)
        os.makedirs(ssh_dir, exist_ok=True)
        os.chmod(ssh_dir, 0o700)

        # Check if this host already exists in SSH config
        host_exists = False
        if os.path.exists(ssh_config_path):
            with open(ssh_config_path, 'r') as f:
                if f"Host {connection_name}" in f.read():
                    host_exists = True

        # Add or update SSH config entry
        if not host_exists:
            with open(ssh_config_path, 'a') as f:
                f.write(f"\n# Rediacc VS Code connection\n")
                f.write(ssh_config_entry)
                f.write("\n")
            logger.info(f"Added SSH config entry for {connection_name}")
        else:
            logger.info(f"SSH config entry already exists for {connection_name}")

        # Launch VS Code
        vscode_uri = f"vscode-remote://ssh-remote+{connection_name}{remote_path}"
        cmd = [vscode_cmd, '--folder-uri', vscode_uri]

        logger.info(f"Launching VS Code: {' '.join(cmd)}")
        print(colorize(f"Opening VS Code for machine '{args.machine}'...", 'GREEN'))

        result = subprocess.run(cmd)
        return result.returncode


@track_command('vscode')
def main():
    """Main entry point for vscode command"""
    initialize_telemetry()

    parser = argparse.ArgumentParser(
        prog='rediacc vscode',
        description='Rediacc CLI VSCode - Launch VSCode with SSH remote connection and repository environment',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  Connect to repository:
    %(prog)s --token=<GUID> --team=MyTeam --machine=server1 --repo=myrepo

  Connect to machine only:
    %(prog)s --token=<GUID> --team=MyTeam --machine=server1

Environment Variables:
  When connected to a repository, the following variables are automatically set:
    REPO_PATH        - Repository filesystem path
    DOCKER_HOST      - Docker daemon connection
    DOCKER_SOCKET    - Docker runtime socket path
    DOCKER_FOLDER    - Docker configuration folder
    DOCKER_DATA      - Docker data directory
    DOCKER_EXEC      - Docker exec directory
    REDIACC_REPO     - Repository name
    REDIACC_TEAM     - Team name
    REDIACC_MACHINE  - Machine name
"""
    )

    # Note: --version is only available at root level (rediacc --version)

    # Add common arguments (standard order: token, team, machine, verbose)
    add_common_arguments(parser, include_args=['token', 'team', 'machine', 'verbose'])

    # Add repo separately since it's optional
    parser.add_argument('--repo', help='Target repository name (optional - if not specified, connects to machine only)')
    parser.add_argument('--dev', action='store_true', help='Development mode - relaxes SSH host key checking')

    args = parser.parse_args()

    setup_logging(verbose=args.verbose)
    logger = get_logger(__name__)

    if args.verbose:
        logger.debug("Rediacc CLI VSCode starting up")
        logger.debug(f"Arguments: {vars(args)}")

    if not (args.team and args.machine):
        parser.error("--team and --machine are required")

    initialize_cli_command(args, parser)

    try:
        if args.repo:
            return launch_vscode_repo(args)
        else:
            return launch_vscode_machine(args)
    except Exception as e:
        logger.error(f"VSCode launch failed: {e}")
        return 1
    finally:
        shutdown_telemetry()


if __name__ == '__main__':
    sys.exit(main())
