#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Rediacc CLI modules package with automatic setup hooks
Provides multiple fallback mechanisms to ensure setup hooks execute
"""

import os
import sys
import threading
import time
import atexit

# Package metadata
__version__ = "0.1.69"  # This will be overridden by _version.py
__author__ = "Rediacc Team"
__email__ = "info@rediacc.com"
__license__ = "MIT"
__description__ = "Infrastructure protection platform with 100-second recovery"

# Global state for hook execution
_hook_state = {"executed": False, "lock": threading.Lock(), "import_time": time.time(), "execution_attempts": 0}


def _should_run_setup_hook() -> bool:
    """Determine if we should attempt to run setup hooks on import"""
    # Skip in build environments
    if any(
        env in os.environ
        for env in [
            "PIP_BUILD_ISOLATION",
            "PIP_NO_BUILD_ISOLATION",
            "SETUPTOOLS_SCM_PRETEND_VERSION",
        ]
    ):
        return False

    # Skip if explicitly disabled
    if os.environ.get("REDIACC_SKIP_IMPORT_HOOKS"):
        return False

    # Skip if we're in a build process
    if any(arg in sys.argv for arg in ["setup.py", "build", "bdist", "sdist", "egg_info"]):
        return False

    return True


def _run_setup_hook_async(delay: float = 2.0):
    """Run setup hook asynchronously with delay"""

    def delayed_hook():
        time.sleep(delay)
        _run_setup_hook_safe()

    thread = threading.Thread(target=delayed_hook, daemon=True)
    thread.start()


def _run_setup_hook_safe():
    """Safely attempt to run setup hooks with error handling"""
    with _hook_state["lock"]:
        if _hook_state["executed"]:
            return

        _hook_state["execution_attempts"] += 1

        # Limit execution attempts to avoid infinite loops
        if _hook_state["execution_attempts"] > 2:
            return

        if not _should_run_setup_hook():
            return

        try:
            # Try to import and run the setup hooks
            try:
                from .setup_hooks import run_post_install_hook

                success = run_post_install_hook()
                if success:
                    _hook_state["executed"] = True
                    return
            except ImportError:
                pass
            except Exception:
                # Hook exists but failed - don't spam on import
                pass

            # Try legacy setup hooks
            try:
                from .setup_hooks import post_install

                post_install()
                _hook_state["executed"] = True
                return
            except (ImportError, Exception):
                pass

        except Exception:
            # Don't let hook failures break package import
            pass


def _register_atexit_hook():
    """Register an atexit hook as final fallback"""

    def final_setup_attempt():
        if not _hook_state["executed"]:
            # Give other mechanisms a chance to run first
            time.sleep(0.5)
            if not _hook_state["executed"]:
                _run_setup_hook_safe()

    atexit.register(final_setup_attempt)


def setup_rediacc_manually() -> bool:
    """
    Manually trigger rediacc setup.
    This can be called by users if automatic setup fails.
    """
    _hook_state["executed"] = False  # Reset state to allow re-execution
    _run_setup_hook_safe()
    return bool(_hook_state["executed"])


def check_rediacc_status() -> dict:
    """
    Check the current rediacc installation status.
    Returns a dictionary with status information.
    """
    try:
        import shutil

        status = {
            "package_imported": True,
            "import_time": _hook_state.get("import_time"),
            "hook_executed": _hook_state.get("executed", False),
            "execution_attempts": _hook_state.get("execution_attempts", 0),
            "executable_in_path": bool(shutil.which("rediacc")),
            "setup_hooks_available": False,
            "version": __version__,
        }

        # Check if setup hooks module is available
        try:
            from . import setup_hooks

            status["setup_hooks_available"] = True
            status["setup_hooks_module"] = str(setup_hooks.__file__)
        except ImportError:
            pass

        return status
    except Exception as e:
        return {"error": str(e), "version": __version__}


# Module-level initialization
def _initialize_package():
    """Initialize the package with conditional setup hook execution"""
    try:
        # Get version from _version.py if available
        try:
            from ._version import __version__ as version

            globals()["__version__"] = version
        except ImportError:
            pass

        # Auto-setup on import has been disabled to avoid side effects during normal CLI usage.
        # Setup hooks will run during installation/update and can be invoked manually via 'rediacc doctor'.

    except Exception:
        # Don't let hook failures break package import
        pass


# Public API
def get_version() -> str:
    """Get the package version"""
    return __version__


def get_package_info() -> dict:
    """Get package information"""
    return {
        "name": "rediacc",
        "version": __version__,
        "author": __author__,
        "email": __email__,
        "license": __license__,
        "description": __description__,
        "status": check_rediacc_status(),
    }


# Initialize package on import
_initialize_package()

# Export public API
__all__ = [
    "__version__",
    "__author__",
    "__email__",
    "__license__",
    "__description__",
    "setup_rediacc_manually",
    "check_rediacc_status",
    "get_version",
    "get_package_info",
]
