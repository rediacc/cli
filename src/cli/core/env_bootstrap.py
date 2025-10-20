#!/usr/bin/env python3
"""
Helpers for composing repository environment bootstrap scripts.

These utilities centralize the logic for turning environment dictionaries
into shell-friendly command fragments. They are shared by terminal integrations
and other launchers (e.g., VS Code) to keep environment handling consistent.
"""

from typing import Dict, Iterable, List, Optional

from .repository_env import format_bash_exports


def _split_lines(value: str) -> List[str]:
    """Split a string into lines while preserving intentional blanks."""
    if value == "":
        return [""]
    return value.splitlines()


def compose_env_block(
    env_vars: Dict[str, str],
    additional_lines: Optional[Iterable[Optional[str]]] = None,
    separator: str = "\n",
) -> str:
    """
    Build a command block with exports followed by optional lines.

    Args:
        env_vars: Mapping of environment variables to export.
        additional_lines: Optional iterable of strings to append after the exports.
                          Items may contain newlines; they will be flattened.
                          Use empty string to force a blank line.
        separator: Separator used when joining the flattened lines.

    Returns:
        Combined command block as a single string.
    """
    lines: List[str] = []
    exports_block = format_bash_exports(env_vars)
    if exports_block:
        lines.extend(exports_block.splitlines())

    if additional_lines:
        for item in additional_lines:
            if item is None:
                continue
            if isinstance(item, str):
                lines.extend(_split_lines(item))
            else:
                # Fall back to string conversion for non-string items
                lines.extend(_split_lines(str(item)))

    return separator.join(lines)


def escape_single_quotes(command_block: str) -> str:
    """Escape a command block for safe embedding inside single quotes."""
    return command_block.replace("'", "'\"'\"'")


def build_sudo_bash_command(
    sudo_user: str,
    command_block: str,
    *,
    login_shell: bool = False,
    preserve_home: bool = True,
) -> str:
    """
    Wrap a command block so it executes through sudo as the target user.

    Args:
        sudo_user: Target user to run as.
        command_block: Script content to execute.
        login_shell: When True, use ``bash -lc`` for a login shell.
        preserve_home: When True, add ``-H`` to sudo to reset HOME.

    Returns:
        A single sudo command string ready to pass to SSH / RemoteCommand.
    """
    escaped = escape_single_quotes(command_block)
    shell_flag = "-lc" if login_shell else "-c"
    home_flag = " -H" if preserve_home else ""
    return f"sudo{home_flag} -u {sudo_user} bash {shell_flag} '{escaped}'"


def compose_sudo_env_command(
    sudo_user: str,
    env_vars: Dict[str, str],
    additional_lines: Optional[Iterable[Optional[str]]] = None,
    *,
    separator: str = "\n",
    login_shell: bool = False,
    preserve_home: bool = True,
) -> str:
    """
    Convenience wrapper to create a sudo command that exports env vars
    before running the provided command lines.
    """
    command_block = compose_env_block(env_vars, additional_lines, separator=separator)
    return build_sudo_bash_command(
        sudo_user,
        command_block,
        login_shell=login_shell,
        preserve_home=preserve_home,
    )
