# -*- coding: utf-8 -*-
"""
Setuptools custom command classes for running rediacc setup hooks during install/develop.

Placed in an importable package module so that pyproject.toml can
reference python-qualified identifiers during isolated builds.
"""
from __future__ import annotations

import os
import sys
import threading
import time
import atexit
from typing import Optional

from setuptools.command.install import install
from setuptools.command.develop import develop
from setuptools.command.egg_info import egg_info


# Minimal shared state for idempotent hook execution
_hook_state = {"executed": False, "lock": threading.Lock(), "execution_attempts": 0}


class HookRunner:
    """Utility to run setup hooks safely and idempotently."""

    @staticmethod
    def should_run_hook() -> bool:
        # Skip when explicitly disabled or clearly a build-only context
        if os.environ.get("REDIACC_SKIP_SETUP_HOOKS"):
            return False
        # Avoid running during wheel/sdist build steps
        if any(arg in sys.argv for arg in ["bdist_wheel", "sdist", "build"]):
            return False
        return True

    @staticmethod
    def run_setup_hook_safe(hook_name: str = "post_install", delay: float = 0.0) -> bool:
        if delay > 0:
            time.sleep(delay)

        with _hook_state["lock"]:
            if _hook_state["executed"]:
                return True
            _hook_state["execution_attempts"] += 1
            if _hook_state["execution_attempts"] > 3:
                return False

        if not HookRunner.should_run_hook():
            print("Rediacc: Skipping setup hooks (build environment detected)")
            return True

        try:
            print(f"Rediacc: Running {hook_name} setup hook...")

            # Strategy 1: call modern hook if available
            hook_fn: Optional[object] = None
            try:
                from cli.setup_hooks import run_post_install_hook  # type: ignore

                hook_fn = run_post_install_hook
            except Exception:
                # Strategy 1b: legacy name
                try:
                    from cli.setup_hooks import post_install  # type: ignore

                    hook_fn = post_install
                except Exception:
                    hook_fn = None

            if hook_fn is not None:
                try:
                    # run_post_install_hook returns bool; legacy post_install returns None
                    if hook_fn.__name__ == "run_post_install_hook":  # type: ignore[attr-defined]
                        success = bool(hook_fn())  # type: ignore[misc]
                    else:
                        hook_fn()  # type: ignore[misc]
                        success = True

                    if success:
                        with _hook_state["lock"]:
                            _hook_state["executed"] = True
                        print("Rediacc: Setup hook completed successfully")
                        return True
                except Exception as e:  # noqa: BLE001 - broad to avoid setup breakage
                    print(f"Rediacc: Setup hook failed: {e}")

            # Strategy 2: subprocess fallback to script path in source tree
            try:
                import subprocess
                from pathlib import Path

                repo_root = Path(__file__).resolve().parents[2]
                script_path = repo_root / "src" / "cli" / "setup_hooks.py"
                if script_path.exists():
                    result = subprocess.run(
                        [sys.executable, str(script_path), hook_name], capture_output=True, text=True, timeout=60
                    )
                    if result.returncode == 0:
                        with _hook_state["lock"]:
                            _hook_state["executed"] = True
                        print("Rediacc: Setup hook completed successfully")
                        if result.stdout:
                            print(result.stdout.strip())
                        return True
                    else:
                        if result.stdout:
                            print(result.stdout.strip())
                        if result.stderr:
                            print(result.stderr.strip(), file=sys.stderr)
            except Exception as e:  # noqa: BLE001
                print(f"Rediacc: Subprocess setup hook failed: {e}")

            print("Rediacc: Could not locate or run setup hooks")
            return False
        except Exception as e:  # noqa: BLE001
            print(f"Rediacc: Setup hook execution failed: {e}")
            return False


class PostInstallCommand(install):
    """Custom install command that triggers rediacc post-install setup."""

    def run(self) -> None:  # type: ignore[override]
        super().run()
        HookRunner.run_setup_hook_safe("post_install")
        atexit.register(lambda: HookRunner.run_setup_hook_safe("post_install", delay=1.0))


class PostDevelopCommand(develop):
    """Custom develop command that triggers rediacc setup for editable installs."""

    def run(self) -> None:  # type: ignore[override]
        super().run()
        HookRunner.run_setup_hook_safe("post_install")
        atexit.register(lambda: HookRunner.run_setup_hook_safe("post_install", delay=1.0))


class PostEggInfoCommand(egg_info):
    """Custom egg_info that may trigger hooks in certain scenarios."""

    def run(self) -> None:  # type: ignore[override]
        super().run()
        # Avoid interfering with egg_info; delay slightly and only run outside build
        if not any(cmd in sys.argv for cmd in ["bdist_wheel", "sdist", "build"]):
            threading.Thread(
                target=lambda: HookRunner.run_setup_hook_safe("post_install", delay=2.0), daemon=True
            ).start()
