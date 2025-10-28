#!/usr/bin/env python3
"""
Rediacc CLI VSCode - Launch VSCode with SSH remote connection and environment setup
"""

import argparse
import subprocess
import sys
import os
import shutil
import stat
import textwrap

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from cli._version import __version__
from cli.core.shared import (
    colorize, add_common_arguments,
    error_exit, initialize_cli_command, RepositoryConnection,
    get_ssh_key_from_vault, SSHConnection, get_machine_info_with_team,
    get_machine_connection_info, _get_universal_user_info,
    _decode_ssh_key, is_windows
)

from cli.core.config import setup_logging, get_logger
from cli.core.telemetry import track_command, initialize_telemetry, shutdown_telemetry
from cli.core.repository_env import (
    get_repository_environment, get_machine_environment, format_ssh_setenv
)
from cli.core.env_bootstrap import compose_env_block


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


def ensure_persistent_identity_file(team: str, machine: str, repo: str, ssh_key: str) -> str:
    """Persist the SSH private key for VS Code connections and return config-safe path."""
    ssh_dir = os.path.expanduser('~/.ssh')
    os.makedirs(ssh_dir, exist_ok=True)
    try:
        os.chmod(ssh_dir, 0o700)
    except (PermissionError, NotImplementedError, OSError):
        # Ignore permission errors on platforms where chmod is limited
        pass

    parts = [sanitize_hostname(p) for p in (team, machine) if p]
    if repo:
        parts.append(sanitize_hostname(repo))
    key_filename = f"rediacc_{'_'.join(parts)}_key"
    key_path = os.path.join(ssh_dir, key_filename)

    decoded_key = _decode_ssh_key(ssh_key)

    existing_content = None
    try:
        with open(key_path, 'r', encoding='utf-8') as existing_file:
            existing_content = existing_file.read()
    except FileNotFoundError:
        existing_content = None

    if existing_content != decoded_key:
        with open(key_path, 'w', newline='\n', encoding='utf-8') as key_file:
            key_file.write(decoded_key)

    try:
        if is_windows():
            os.chmod(key_path, stat.S_IREAD | stat.S_IWRITE)
        else:
            os.chmod(key_path, 0o600)
    except (PermissionError, NotImplementedError, OSError):
        # Best-effort permissions; continue if unsupported
        pass

    return key_path.replace('\\', '/')

def ensure_persistent_known_hosts_file(team: str, machine: str, repo: str, host_entry: str) -> str:
    """Persist the host key for VS Code connections and return config-safe path."""
    from cli.core.shared import _decode_host_entry

    ssh_dir = os.path.expanduser('~/.ssh')
    os.makedirs(ssh_dir, exist_ok=True)
    try:
        os.chmod(ssh_dir, 0o700)
    except (PermissionError, NotImplementedError, OSError):
        pass

    parts = [sanitize_hostname(p) for p in (team, machine) if p]
    if repo:
        parts.append(sanitize_hostname(repo))
    known_hosts_filename = f"rediacc_{'_'.join(parts)}_known_hosts"
    known_hosts_path = os.path.join(ssh_dir, known_hosts_filename)

    decoded_host_entry = _decode_host_entry(host_entry)

    existing_content = None
    try:
        with open(known_hosts_path, 'r', encoding='utf-8') as existing_file:
            existing_content = existing_file.read().strip()
    except FileNotFoundError:
        existing_content = None

    if existing_content != decoded_host_entry:
        with open(known_hosts_path, 'w', newline='\n', encoding='utf-8') as kh_file:
            kh_file.write(decoded_host_entry + '\n')

    try:
        os.chmod(known_hosts_path, 0o644)
    except (PermissionError, NotImplementedError, OSError):
        pass

    return known_hosts_path.replace('\\', '/')

def build_vscode_terminal_command(target_user: str, env_vars: dict) -> str:
    """Build terminal command for VSCode using shared env bootstrap logic (DRY)."""
    from cli.core.env_bootstrap import compose_sudo_env_command
    # Generate the sudo command with environment setup (reuses term command logic)
    # This creates: sudo -H -u {user} bash -lc 'export VAR=val\nexec bash'
    return compose_sudo_env_command(
        target_user,
        env_vars,
        additional_lines=['exec bash'],  # exec bash to replace the shell
        login_shell=True,  # Use bash -l to source .bashrc and .bashrc-rediacc
        preserve_home=True  # Use -H to set HOME properly
    )

def ensure_vscode_env_setup(
    ssh_conn,
    destination: str,
    env_vars,
    target_user: str,
    ssh_user: str,
    logger
) -> None:
    """
    Install/update the VS Code server environment bootstrap script and terminal settings.
    Configures VSCode terminal to run as target_user if different from ssh_user.
    """
    env_content = compose_env_block(env_vars)
    # Always end with a newline so Python write_text doesn't omit final line
    env_content_with_newline = env_content + '\n' if not env_content.endswith('\n') else env_content

    # Determine if we need to sudo to target user for terminals
    need_sudo = bool(target_user and target_user.strip() and target_user != ssh_user)

    # Build the terminal command using shared logic (DRY - same as term command)
    terminal_command = build_vscode_terminal_command(target_user, env_vars) if need_sudo else ""

    python_script = textwrap.dedent(f"""
        import os
        import pathlib
        import stat
        import json

        env_content = {env_content_with_newline!r}
        target_user = {target_user!r}
        need_sudo = {need_sudo}
        terminal_command = {terminal_command!r}

        # Setup environment file
        setup_dir = pathlib.Path.home() / ".vscode-server"
        setup_dir.mkdir(parents=True, exist_ok=True)

        env_file = setup_dir / "rediacc-env.sh"
        env_file.write_text(env_content, encoding="utf-8")
        try:
            env_file.chmod(stat.S_IRUSR | stat.S_IWUSR)
        except (PermissionError, NotImplementedError, OSError):
            pass

        setup_file = setup_dir / "server-env-setup"
        marker_start = "# >>> REDIACC ENV START\\n"
        marker_end = "# <<< REDIACC ENV END\\n"
        env_line = '. "' + str(env_file) + '"\\n'

        lines = []
        if setup_file.exists():
            existing = setup_file.read_text(encoding="utf-8").splitlines(keepends=True)
            skip = False
            for line in existing:
                if line == marker_start:
                    skip = True
                    continue
                if line == marker_end:
                    skip = False
                    continue
                if not skip:
                    lines.append(line)

        if lines and not lines[-1].endswith("\\n"):
            lines.append("\\n")

        lines.extend([marker_start, env_line, marker_end])
        setup_file.write_text("".join(lines), encoding="utf-8")
        try:
            setup_file.chmod(stat.S_IRUSR | stat.S_IWUSR)
        except (PermissionError, NotImplementedError, OSError):
            pass

        # Configure VSCode terminal to run as target user with environment
        if need_sudo and target_user and terminal_command:
            data_dir = setup_dir / "data"
            data_dir.mkdir(parents=True, exist_ok=True)

            machine_dir = data_dir / "Machine"
            machine_dir.mkdir(parents=True, exist_ok=True)

            settings_file = machine_dir / "settings.json"

            # Load existing settings or create new
            settings = {{}}
            if settings_file.exists():
                try:
                    settings = json.loads(settings_file.read_text(encoding="utf-8"))
                except:
                    settings = {{}}

            # Use the pre-built terminal command (reuses term command logic via compose_sudo_env_command)
            profile_name = f"{{target_user}}"
            settings["terminal.integrated.profiles.linux"] = {{
                profile_name: {{
                    "path": "/bin/bash",
                    "args": ["-c", terminal_command],
                    "icon": "terminal"
                }}
            }}
            settings["terminal.integrated.defaultProfile.linux"] = profile_name

            # Write settings
            settings_file.write_text(json.dumps(settings, indent=2), encoding="utf-8")
    """).strip()

    ssh_parts = ssh_conn.ssh_opts.split() if ssh_conn.ssh_opts else []
    command = ['ssh', *ssh_parts, destination, 'python3', '-']

    logger.debug(f"[ensure_vscode_env_setup] Installing VSCode terminal config via: {' '.join(command)}")

    try:
        subprocess.run(
            command,
            input=(python_script + '\n').encode('utf-8'),
            check=True
        )
    except FileNotFoundError as exc:
        logger.warning(f"Unable to launch SSH command for VSCode setup: {exc}")
    except subprocess.CalledProcessError as exc:
        logger.warning(
            "Failed to install VS Code terminal configuration (exit code %s). "
            "VS Code terminals may not switch to target user.",
            exc.returncode
        )


def build_ssh_config_options(ssh_conn, identity_file_path: str, known_hosts_file_path: str) -> list:
    """Build SSH config options list (DRY helper)."""
    ssh_opts_lines = [
        f"    IdentityFile {identity_file_path}",
        "    IdentitiesOnly yes",
        f"    UserKnownHostsFile {known_hosts_file_path}"
    ]
    if ssh_conn.ssh_opts:
        opts = ssh_conn.ssh_opts.split()
        i = 0
        while i < len(opts):
            if opts[i] == '-o' and i + 1 < len(opts):
                option = opts[i + 1]
                if '=' in option:
                    key, value = option.split('=', 1)
                    if key not in ['IdentityFile', 'UserKnownHostsFile']:
                        line = f"    {key} {value}"
                        if line not in ssh_opts_lines:
                            ssh_opts_lines.append(line)
                i += 2
            elif opts[i] == '-i':
                i += 2
            else:
                i += 1
    return ssh_opts_lines

def upsert_ssh_config_entry(ssh_config_path: str, connection_name: str, ssh_config_entry: str):
    """Add or replace the SSH config block for a given connection."""
    os.makedirs(os.path.dirname(ssh_config_path), exist_ok=True)

    block = "# Rediacc VS Code connection\n" + ssh_config_entry.rstrip() + "\n\n"
    block_lines = block.splitlines(keepends=True)

    lines = []
    if os.path.exists(ssh_config_path):
        with open(ssh_config_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()

    start = end = None
    for idx, line in enumerate(lines):
        if line.strip() == f"Host {connection_name}":
            start = idx
            if idx > 0 and lines[idx - 1].strip() == "# Rediacc VS Code connection":
                start = idx - 1
            end = len(lines)
            for j in range(idx + 1, len(lines)):
                if lines[j].startswith("Host "):
                    end = j
                    break
            break

    if start is not None:
        lines[start:end] = block_lines
        action = "updated"
    else:
        if lines:
            if not lines[-1].endswith('\n'):
                lines[-1] += '\n'
            if lines[-1].strip():
                lines.append('\n')
        lines.extend(block_lines)
        action = "added"

    with open(ssh_config_path, 'w', encoding='utf-8') as f:
        f.writelines(lines)

    return action


def resolve_universal_user(connection_value: str, universal_user_name: str) -> str:
    """Choose the sudo target user, preferring explicit connection metadata."""
    candidates = [connection_value, universal_user_name, 'rediacc']
    for value in candidates:
        if value:
            return value
    return 'rediacc'


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
    universal_user = resolve_universal_user(
        conn.connection_info.get('universal_user'),
        universal_user_name
    )

    # Get environment variables using shared module
    env_vars = get_repository_environment(args.team, args.machine, args.repo,
                                          connection_info=conn.connection_info,
                                          repo_paths=conn.repo_paths)

    # Get SSH key
    ssh_key = get_ssh_key_from_vault(args.team)
    if not ssh_key:
        error_exit(f"SSH private key not found in vault for team '{args.team}'")

    identity_file_path = ensure_persistent_identity_file(args.team, args.machine, args.repo, ssh_key)

    host_entry = conn.connection_info.get('host_entry')
    if not host_entry:
        error_exit("Security Error: No host key found in machine vault. Contact your administrator to add the host key.")

    known_hosts_file_path = ensure_persistent_known_hosts_file(args.team, args.machine, args.repo, host_entry)

    port = conn.connection_info.get('port', 22)

    with SSHConnection(ssh_key, host_entry, port, prefer_agent=True) as ssh_conn:
        # Create SSH config entry
        connection_name = f"rediacc-{sanitize_hostname(args.team)}-{sanitize_hostname(args.machine)}-{sanitize_hostname(args.repo)}"
        ssh_host = conn.connection_info['ip']
        ssh_user = conn.connection_info['user']
        ssh_port = port
        remote_path = conn.repo_paths['mount_path']

        ensure_vscode_env_setup(
            ssh_conn,
            conn.ssh_destination,
            env_vars,
            universal_user,
            ssh_user,
            logger
        )

        # Format environment variables as SetEnv directives
        setenv_directives = format_ssh_setenv(env_vars)

        # Parse SSH options using DRY helper
        ssh_opts_lines = build_ssh_config_options(ssh_conn, identity_file_path, known_hosts_file_path)

        # NOTE: We don't use RemoteCommand for VSCode because it interferes with VSCode server installation
        # Instead, we configure VSCode's terminal settings to sudo to the target user
        ssh_config_entry = f"""Host {connection_name}
    HostName {ssh_host}
    User {ssh_user}
    Port {ssh_port}
{chr(10).join(ssh_opts_lines) if ssh_opts_lines else ''}
{setenv_directives}
    ServerAliveInterval 60
    ServerAliveCountMax 3
"""

        # Add SSH config to user's SSH config file
        ssh_config_path = os.path.expanduser('~/.ssh/config')
        ssh_dir = os.path.dirname(ssh_config_path)
        os.makedirs(ssh_dir, exist_ok=True)
        try:
            os.chmod(ssh_dir, 0o700)
        except (PermissionError, NotImplementedError, OSError):
            pass

        action = upsert_ssh_config_entry(ssh_config_path, connection_name, ssh_config_entry)
        logger.info(f"{action.capitalize()} SSH config entry for {connection_name}")

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
    universal_user = resolve_universal_user(
        connection_info.get('universal_user'),
        universal_user_name
    )

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

    identity_file_path = ensure_persistent_identity_file(args.team, args.machine, None, ssh_key)

    host_entry = connection_info.get('host_entry')
    if not host_entry:
        error_exit("Security Error: No host key found in machine vault. Contact your administrator to add the host key.")

    known_hosts_file_path = ensure_persistent_known_hosts_file(args.team, args.machine, None, host_entry)

    port = connection_info.get('port', 22)

    with SSHConnection(ssh_key, host_entry, port, prefer_agent=True) as ssh_conn:
        # Create SSH config entry
        connection_name = f"rediacc-{sanitize_hostname(args.team)}-{sanitize_hostname(args.machine)}"
        ssh_host = connection_info['ip']
        ssh_user = connection_info['user']
        ssh_port = port

        ensure_vscode_env_setup(
            ssh_conn,
            f"{ssh_user}@{ssh_host}",
            env_vars,
            universal_user,
            ssh_user,
            logger
        )

        # Format environment variables as SetEnv directives
        setenv_directives = format_ssh_setenv(env_vars)

        # Parse SSH options using DRY helper
        ssh_opts_lines = build_ssh_config_options(ssh_conn, identity_file_path, known_hosts_file_path)

        # NOTE: We don't use RemoteCommand for VSCode because it interferes with VSCode server installation
        # Instead, we configure VSCode's terminal settings to sudo to the target user
        ssh_config_entry = f"""Host {connection_name}
    HostName {ssh_host}
    User {ssh_user}
    Port {ssh_port}
{chr(10).join(ssh_opts_lines) if ssh_opts_lines else ''}
{setenv_directives}
    ServerAliveInterval 60
    ServerAliveCountMax 3
"""

        # Add SSH config to user's SSH config file
        ssh_config_path = os.path.expanduser('~/.ssh/config')
        ssh_dir = os.path.dirname(ssh_config_path)
        os.makedirs(ssh_dir, exist_ok=True)
        try:
            os.chmod(ssh_dir, 0o700)
        except (PermissionError, NotImplementedError, OSError):
            pass

        action = upsert_ssh_config_entry(ssh_config_path, connection_name, ssh_config_entry)
        logger.info(f"{action.capitalize()} SSH config entry for {connection_name}")

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
