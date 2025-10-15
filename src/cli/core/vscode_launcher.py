#!/usr/bin/env python3
"""Centralized VS Code launch utilities shared by GUI and protocol handler."""

from __future__ import annotations

import json
import os
import platform
import posixpath
import shlex
import shutil
import subprocess
import time
import re
from typing import Any, Dict, List, Optional

from .config import get_logger
from .shared import (
    RepositoryConnection,
    SSHConnection,
    _decode_ssh_key,
    _get_universal_user_info,
    get_machine_connection_info,
    get_machine_info_with_team,
    get_ssh_key_from_vault,
    is_windows,
)

logger = get_logger(__name__)


def find_vscode_executable() -> Optional[str]:
    """Find VS Code executable on the system."""
    # Check for explicitly set VS Code path
    vscode_path = os.environ.get("REDIACC_VSCODE_PATH")
    if vscode_path and shutil.which(vscode_path):
        return vscode_path

    # Detect WSL environment
    is_wsl = False
    try:
        with open("/proc/version", "r", encoding="utf-8") as version_file:
            is_wsl = "microsoft" in version_file.read().lower()
    except (FileNotFoundError, OSError):
        is_wsl = False

    # Platform-specific candidates
    system = platform.system().lower()
    if system == "linux":
        if is_wsl:
            # In WSL, prefer Windows VS Code for better integration
            candidates = ["code.exe", "code"]
        else:
            # Native Linux
            candidates = ["code"]
    elif system == "darwin":  # macOS
        candidates = ["code", "/Applications/Visual Studio Code.app/Contents/Resources/app/bin/code"]
    elif system == "windows":
        candidates = ["code.cmd", "code.exe"]
    else:
        candidates = ["code"]

    for candidate in candidates:
        if shutil.which(candidate):
            return candidate

    return None


def _sanitize_hostname(name: str) -> str:
    """Sanitize name for use as SSH hostname (VS Code compatible)."""
    # Replace spaces and other invalid characters with hyphens
    # Keep only alphanumeric characters, hyphens, and dots
    sanitized = re.sub(r"[^a-zA-Z0-9.-]", "-", name)
    # Remove multiple consecutive hyphens
    sanitized = re.sub(r"-+", "-", sanitized)
    # Remove leading/trailing hyphens
    sanitized = sanitized.strip("-")
    # Ensure it's not empty
    return sanitized if sanitized else "default"


def _configure_vscode_platform(
    connection_name: str,
    sudo_user: Optional[str] = None,
    requires_remote_command: bool = False,
    server_install_path: Optional[str] = None,
) -> None:
    """Configure VS Code SSH settings for the generated host."""
    try:
        # Detect WSL environment
        is_wsl = False
        try:
            with open("/proc/version", "r", encoding="utf-8") as version_file:
                is_wsl = "microsoft" in version_file.read().lower()
        except (FileNotFoundError, OSError):
            is_wsl = False

        if is_wsl:
            # In WSL, VS Code settings might be in Windows user profile
            vscode_settings_paths: List[str] = []

            # Try Windows user profile first
            userprofile = os.environ.get("USERPROFILE")
            if userprofile:
                try:
                    import subprocess as _subprocess

                    wsl_path = _subprocess.check_output(["wslpath", userprofile], text=True).strip()
                    vscode_settings_paths.append(
                        os.path.join(wsl_path, "AppData", "Roaming", "Code", "User", "settings.json")
                    )
                except Exception:
                    pass

            # Fallback to WSL paths
            home_dir = os.path.expanduser("~")
            vscode_settings_paths.extend(
                [
                    os.path.join(home_dir, ".vscode-server", "data", "Machine", "settings.json"),  # VS Code Server
                    os.path.join(home_dir, ".config", "Code", "User", "settings.json"),  # WSL Linux
                ]
            )
        else:
            # Non-WSL paths
            home_dir = os.path.expanduser("~")
            vscode_settings_paths = [
                os.path.join(home_dir, ".config", "Code", "User", "settings.json"),  # Linux
                os.path.join(home_dir, "Library", "Application Support", "Code", "User", "settings.json"),  # macOS
                os.path.join(home_dir, "AppData", "Roaming", "Code", "User", "settings.json"),  # Windows
            ]

        vscode_settings_file = None
        for path in vscode_settings_paths:
            if os.path.exists(os.path.dirname(path)):
                vscode_settings_file = path
                logger.debug("Found VS Code settings directory: %s", os.path.dirname(path))
                break

        if not vscode_settings_file:
            # Create default path (first in list)
            vscode_settings_file = vscode_settings_paths[0]
            os.makedirs(os.path.dirname(vscode_settings_file), exist_ok=True)
            logger.debug("Created VS Code settings directory: %s", os.path.dirname(vscode_settings_file))

        # Read existing settings
        settings: Dict[str, Any] = {}
        if os.path.exists(vscode_settings_file):
            try:
                with open(vscode_settings_file, "r", encoding="utf-8") as handle:
                    settings = json.load(handle)
            except (json.JSONDecodeError, FileNotFoundError):
                settings = {}

        if server_install_path:
            install_paths = settings.setdefault("remote.SSH.serverInstallPath", {})
            install_paths[connection_name] = server_install_path

        # Update platform settings
        if requires_remote_command:
            remote_platform = settings.setdefault("remote.SSH.remotePlatform", {})
            # RemoteCommand conflicts with remotePlatform; ensure entry is removed.
            remote_platform.pop(connection_name, None)
            if not remote_platform:
                settings.pop("remote.SSH.remotePlatform", None)
            settings["remote.SSH.useLocalServer"] = True
            settings["remote.SSH.enableRemoteCommand"] = True
            settings["remote.SSH.showLoginTerminal"] = True
            settings["remote.SSH.localServerDownload"] = "always"
        else:
            remote_platform = settings.setdefault("remote.SSH.remotePlatform", {})
            remote_platform[connection_name] = "linux"

        # Configure terminal to use universal user (if provided)
        if sudo_user:
            if "terminal.integrated.profiles.linux" not in settings:
                settings["terminal.integrated.profiles.linux"] = {}

            sudo_for_shell = f"\\#{sudo_user[1:]}" if sudo_user.startswith("#") else sudo_user
            profile_key_suffix = sudo_user.replace("#", "uid-") if sudo_user.startswith("#") else sudo_user
            settings["terminal.integrated.profiles.linux"][f"{connection_name}-{profile_key_suffix}"] = {
                "path": "/bin/bash",
                "args": ["-c", f"sudo -H -u {sudo_for_shell} bash -l"],
            }

        # Set it as default for this connection
        if "terminal.integrated.defaultProfile.linux" not in settings:
            settings["terminal.integrated.defaultProfile.linux"] = {}

        # Write back settings
        with open(vscode_settings_file, "w", encoding="utf-8") as handle:
            json.dump(settings, handle, indent=2)

        logger.debug("Updated VS Code settings: %s -> linux", connection_name)

    except Exception as exc:
        # Don't fail the connection if we can't configure the platform
        logger.warning("Could not configure VS Code platform: %s", exc)


def _ensure_known_hosts_entry(path: str, entry_value: str, aliases: List[str]) -> str:
    """Ensure the host key is written to a persistent known_hosts file."""
    if not entry_value:
        return path

    lines = [line.strip() for line in entry_value.splitlines() if line.strip()]

    if not lines:
        return path

    def augment_hostnames(raw_line: str) -> str:
        parts = raw_line.split()
        if len(parts) < 2:
            return raw_line
        hostnames = parts[0]
        remainder = " ".join(parts[1:])
        existing_aliases = {alias.strip() for alias in hostnames.split(",") if alias.strip()}
        for alias_entry in aliases or []:
            if alias_entry and alias_entry not in existing_aliases:
                hostnames = f"{alias_entry},{hostnames}"
                existing_aliases.add(alias_entry)
        return f"{hostnames} {remainder}"

    augmented_lines = [augment_hostnames(line) for line in lines]

    existing_entries = set()
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as existing_file:
            existing_entries = {line.strip() for line in existing_file if line.strip()}

    new_entries = [line for line in augmented_lines if line not in existing_entries]
    if new_entries:
        with open(path, "a", newline="\n", encoding="utf-8") as output:
            if existing_entries:
                output.write("\n")
            output.write("\n".join(new_entries))
            output.write("\n")

        if is_windows():
            import stat

            os.chmod(path, stat.S_IREAD | stat.S_IWRITE)
        else:
            os.chmod(path, 0o600)

    return path


def _write_or_update_ssh_config(path: str, host: str, entry: str) -> None:
    """Add or update the SSH config entry for the VS Code connection."""
    entry_lines = ["# Rediacc VS Code connection\n"]
    entry_lines.extend(line if line.endswith("\n") else f"{line}\n" for line in entry.splitlines())
    entry_lines.append("\n")

    existing_lines: List[str] = []
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as handle:
            existing_lines = handle.readlines()

    # Remove any legacy Rediacc blocks that contain backslash paths
    sanitized_lines: List[str] = []
    index = 0
    while index < len(existing_lines):
        line = existing_lines[index]
        if line.strip().startswith("# Rediacc VS Code connection"):
            block = [line]
            index += 1
            while index < len(existing_lines) and not existing_lines[index].strip().lower().startswith("host "):
                block.append(existing_lines[index])
                index += 1
            if index < len(existing_lines):
                block.append(existing_lines[index])
                index += 1
                while index < len(existing_lines) and not existing_lines[index].strip().lower().startswith("host "):
                    block.append(existing_lines[index])
                    index += 1
            if any("\\.vscode-server" in blk_line for blk_line in block):
                continue
            sanitized_lines.extend(block)
        else:
            sanitized_lines.append(line)
            index += 1

    existing_lines = sanitized_lines

    while True:
        start_idx = None
        end_idx = None
        for idx, line in enumerate(existing_lines):
            stripped = line.strip()
            if stripped.lower().startswith("host "):
                current_host = stripped.split(None, 1)[1]
                if current_host == host:
                    start_idx = idx
                    j_index = idx - 1
                    while j_index >= 0 and existing_lines[j_index].strip().startswith("# Rediacc VS Code connection"):
                        start_idx = j_index
                        j_index -= 1
                    end_idx = idx + 1
                    while end_idx < len(existing_lines):
                        next_line = existing_lines[end_idx].strip()
                        if next_line.lower().startswith("host "):
                            break
                        end_idx += 1
                    break

        if start_idx is not None and end_idx is not None:
            del existing_lines[start_idx:end_idx]
        else:
            break

    if existing_lines and existing_lines[-1].strip():
        existing_lines.append("\n")

    existing_lines.extend(entry_lines)

    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.writelines(existing_lines)


def launch_vscode_connection(
    team: str,
    machine: str,
    repo: Optional[str] = None,
    token: Optional[str] = None,
    api_url: Optional[str] = None,
) -> Dict[str, Any]:
    """Launch VS Code with SSH remote connection for GUI or protocol handler.

    Returns:
        Dict with success flag, VS Code URI, connection_name, and optional error.
    """
    result: Dict[str, Any] = {
        "success": False,
        "vscode_uri": "",
        "connection_name": "",
        "error": None,
    }

    try:
        if not team or not machine:
            raise ValueError("Both team and machine must be provided to launch VS Code")

        if api_url:
            os.environ["SYSTEM_API_URL"] = api_url

        if token:
            try:
                from .config import TokenManager

                if TokenManager.validate_token(token):
                    TokenManager.set_token(token)
                else:
                    raise ValueError("Invalid token format provided for VS Code launch")
            except Exception as token_error:
                raise ValueError(f"Failed to initialize token: {token_error}") from token_error

        vscode_cmd = find_vscode_executable()
        if not vscode_cmd:
            raise FileNotFoundError(
                "VS Code is not installed or not found in PATH. "
                "Please install VS Code or set REDIACC_VSCODE_PATH."
            )

        # Get universal user info for both repo and machine connections
        universal_user_name, universal_user_id, _ = _get_universal_user_info()

        remote_sudo_user: Optional[str] = None

        def _update_remote_user(name: Optional[str], uid: Optional[str]) -> None:
            nonlocal remote_sudo_user
            if name:
                remote_sudo_user = name
            elif uid:
                remote_sudo_user = f"#{uid}"

        _update_remote_user(universal_user_name, universal_user_id)

        ssh_context: SSHConnection
        ssh_host: str
        ssh_user: str
        host_entry: Optional[str]
        remote_path: str

        if repo:
            # Repository connection - use RepositoryConnection
            connection = RepositoryConnection(team, machine, repo)
            connection.connect()

            remote_path = connection.repo_paths["mount_path"].replace("\\", "/")
            connection_name = (
                f"rediacc-{_sanitize_hostname(team)}-"
                f"{_sanitize_hostname(machine)}-{_sanitize_hostname(repo)}"
            )

            # Use RepositoryConnection's SSH context
            ssh_context = connection.ssh_context(prefer_agent=True)
            ssh_host = connection.connection_info["ip"]
            ssh_user = connection.connection_info["user"]
            host_entry = connection.connection_info.get("host_entry")
            if not host_entry:
                raise RuntimeError(
                    "Missing SSH host key (HOST_ENTRY) in machine vault. Please set HOST_ENTRY to enforce secure SSH."
                )
            _update_remote_user(
                connection.connection_info.get("universal_user"),
                connection.connection_info.get("universal_user_id"),
            )
            ssh_key = connection._ssh_key  # pylint: disable=protected-access
        else:
            # Machine-only connection - follow terminal's connect_to_machine pattern
            machine_info = get_machine_info_with_team(team, machine)
            connection_info = get_machine_connection_info(machine_info)

            ssh_key = get_ssh_key_from_vault(team)
            if not ssh_key:
                raise RuntimeError(f"SSH private key not found in vault for team '{team}'")

            if universal_user_id:
                remote_path = f"{connection_info['datastore']}/{universal_user_id}"
            else:
                remote_path = connection_info["datastore"]
            remote_path = remote_path.replace("\\", "/")

            connection_name = f"rediacc-{_sanitize_hostname(team)}-{_sanitize_hostname(machine)}"

            host_entry = connection_info.get("host_entry")
            if not host_entry:
                raise RuntimeError(
                    "Missing SSH host key (HOST_ENTRY) in machine vault. Please set HOST_ENTRY to enforce secure SSH."
                )
            ssh_context = SSHConnection(ssh_key, host_entry, prefer_agent=True)
            ssh_host = connection_info["ip"]
            ssh_user = connection_info["user"]
            _update_remote_user(
                connection_info.get("universal_user"),
                connection_info.get("universal_user_id"),
            )

        if not remote_sudo_user:
            if universal_user_name:
                remote_sudo_user = universal_user_name
            elif universal_user_id:
                remote_sudo_user = f"#{universal_user_id}"
            else:
                remote_sudo_user = "rediacc"

        normalized_remote_path = remote_path.rstrip("/") or "/"
        server_install_path = posixpath.join(normalized_remote_path, ".vscode-server")

        env_exports: List[str] = []
        if team:
            env_exports.append(f"export REDIACC_TEAM={shlex.quote(team)}")
        if machine:
            env_exports.append(f"export REDIACC_MACHINE={shlex.quote(machine)}")
        if repo:
            env_exports.append(f"export REDIACC_REPO={shlex.quote(repo)}")

        ps1_segments: List[str] = []
        if team:
            ps1_segments.append(f"[{team}]")
        if machine:
            ps1_segments.append(f"[{machine}]")
        if repo:
            ps1_segments.append(f"[{repo}]")

        ps1_prompt = "\\u@\\h"
        if ps1_segments:
            ps1_prompt += ":" + "".join(ps1_segments)
        else:
            ps1_prompt += ":[$PWD]"
        ps1_prompt += "$ "
        env_exports.append(f"export PS1={shlex.quote(ps1_prompt)}")

        env_exports_str = "".join(f"{cmd}; " for cmd in env_exports)

        # Create persistent SSH key file for VS Code
        ssh_dir = os.path.expanduser("~/.ssh")
        os.makedirs(ssh_dir, exist_ok=True)
        os.chmod(ssh_dir, 0o700)

        # Create persistent key file with unique name for this connection
        key_filename = f"rediacc_{_sanitize_hostname(team)}_{_sanitize_hostname(machine)}"
        if repo:
            key_filename += f"_{_sanitize_hostname(repo)}"
        key_filename += "_key"

        persistent_key_path = os.path.join(ssh_dir, key_filename)
        known_hosts_path = os.path.join(ssh_dir, "known_hosts")

        # Decode and write the SSH key
        decoded_key = _decode_ssh_key(ssh_key)

        with open(persistent_key_path, "w", newline="\n", encoding="utf-8") as handle:
            handle.write(decoded_key)

        if is_windows():
            import stat

            os.chmod(persistent_key_path, stat.S_IREAD | stat.S_IWRITE)
        else:
            os.chmod(persistent_key_path, 0o600)

        logger.debug("Created persistent SSH key at: %s", persistent_key_path)

        with ssh_context as ssh_conn:
            if not ssh_host or not ssh_user:
                raise RuntimeError("Missing SSH connection details")

            ssh_opts_lines: List[str] = []

            # Add the persistent identity file (convert Windows paths to forward slashes)
            key_path_for_config = persistent_key_path.replace("\\", "/")
            ssh_opts_lines.append(f"    IdentityFile {key_path_for_config}")
            ssh_opts_lines.append("    IdentitiesOnly yes")

            # Parse other SSH options from ssh_conn.ssh_opts
            if ssh_conn.ssh_opts:
                opts = ssh_conn.ssh_opts.split()
                index = 0
                while index < len(opts):
                    if opts[index] == "-o" and index + 1 < len(opts):
                        option = opts[index + 1]
                        if "=" in option:
                            key, value = option.split("=", 1)
                            if key not in ["IdentityFile", "UserKnownHostsFile"]:
                                ssh_opts_lines.append(f"    {key} {value}")
                        index += 2
                    elif opts[index] == "-i":
                        # Skip -i keyfile since we're using persistent key
                        index += 2
                    else:
                        index += 1

            remote_command_line = ""
            remote_command_needed = False

            if remote_sudo_user:
                comparison_user = (
                    remote_sudo_user.lstrip("#") if remote_sudo_user.startswith("#") else remote_sudo_user
                )
                remote_command_needed = comparison_user != ssh_user

            if remote_command_needed and remote_sudo_user:
                sudo_target = (
                    f"\\#{remote_sudo_user[1:]}" if remote_sudo_user.startswith("#") else remote_sudo_user
                )
                install_path_arg = shlex.quote(server_install_path)
                remote_command_script = (
                    f"export VSCODE_AGENT_FOLDER={install_path_arg}; "
                    f"mkdir -p {install_path_arg} >/dev/null 2>&1 || true; "
                    "if [ -n \"$SSH_ORIGINAL_COMMAND\" ]; then "
                    "exec bash -lc \"$SSH_ORIGINAL_COMMAND\"; "
                    "else exec bash -l; "
                    "fi"
                )
                remote_command_line = (
                    f"    RemoteCommand sudo -n -H -u {sudo_target} "
                    f"bash -lc {shlex.quote(env_exports_str + remote_command_script)}\n"
                )

            if host_entry:
                host_aliases = [connection_name, ssh_host]
                if ssh_host and ":" not in ssh_host and not ssh_host.startswith("["):
                    host_aliases.append(f"[{ssh_host}]")

                _ensure_known_hosts_entry(known_hosts_path, host_entry, host_aliases)
                ssh_opts_lines.append(f"    HostKeyAlias {connection_name}")
                ssh_opts_lines.append("    StrictHostKeyChecking yes")
                ssh_opts_lines.append("    CheckHostIP no")

            options_block = "\n".join(ssh_opts_lines)
            if options_block:
                options_block += "\n"

            ssh_config_entry = (
                f"Host {connection_name}\n"
                f"    HostName {ssh_host}\n"
                f"    User {ssh_user}\n"
                f"{remote_command_line}{options_block}"
                f"    ServerAliveInterval 60\n"
                f"    ServerAliveCountMax 3\n"
            )

            logger.debug("SSH Config Generation:")
            logger.debug("  Connection name: %s", connection_name)
            logger.debug("  SSH host: %s", ssh_host)
            logger.debug("  SSH user: %s", ssh_user)
            logger.debug("  Universal user target: %s", remote_sudo_user)
            logger.debug("  Remote path: %s", remote_path)
            logger.debug("  SSH opts lines: %s", ssh_opts_lines)
            logger.debug("  Generated SSH config entry:\n%s", ssh_config_entry)

            ssh_config_path = os.path.expanduser("~/.ssh/config")

            ssh_dirname = os.path.dirname(ssh_config_path)
            os.makedirs(ssh_dirname, exist_ok=True)
            os.chmod(ssh_dirname, 0o700)

            _write_or_update_ssh_config(ssh_config_path, connection_name, ssh_config_entry)

        _configure_vscode_platform(
            connection_name,
            remote_sudo_user,
            requires_remote_command=remote_command_needed,
            server_install_path=server_install_path,
        )

        vscode_uri = f"vscode-remote://ssh-remote+{connection_name}{remote_path}"
        command = [vscode_cmd, "--folder-uri", vscode_uri]

        result["connection_name"] = connection_name
        result["vscode_uri"] = vscode_uri

        logger.debug("Launching VS Code: %s", " ".join(command))
        logger.debug("Platform config: %s -> linux", connection_name)

        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=os.environ.copy(),
        )

        time.sleep(2)  # Give VS Code time to start
        if process.poll() is None:
            result["success"] = True
            return result

        stdout, stderr = process.communicate()
        if process.returncode != 0:
            error_msg = stderr.decode() if stderr else "Unknown error"
            raise RuntimeError(f"VS Code failed to start: {error_msg}")

        logger.debug("VS Code process exited quickly with return code 0")
        result["success"] = True
        return result

    except Exception as exc:
        logger.error("Failed to launch VS Code: %s", exc)
        result["error"] = str(exc)
        return result

