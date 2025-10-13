#!/usr/bin/env python3
"""
Setup script with protocol registration hooks for Windows.

This file exists for compatibility with legacy tools that expect setup.py.
All package configuration is now in pyproject.toml, but we add custom
install/uninstall commands for protocol registration.

Modern installations should use:
    pip install .
or
    python -m build

Instead of:
    python setup.py install  # deprecated
    python setup.py develop  # deprecated
"""

import os
import sys
import threading
import time
import atexit
from setuptools import setup
from setuptools.command.install import install
from setuptools.command.develop import develop
from setuptools.command.egg_info import egg_info

try:
    from wheel.bdist_wheel import bdist_wheel
except ImportError:
    bdist_wheel = None

# Global hook execution state
_hook_state = {"executed": False, "lock": threading.Lock(), "execution_attempts": 0}


class HookRunner:
    """Enhanced utility class to manage hook execution across different scenarios"""

    @staticmethod
    def should_run_hook():
        """Determine if we should run the setup hook"""
        # Skip in certain environments
        if os.environ.get("PIP_NO_BUILD_ISOLATION"):
            return False
        if os.environ.get("REDIACC_SKIP_SETUP_HOOKS"):
            return False
        if any(arg in sys.argv for arg in ["bdist_wheel", "sdist", "build"]):
            return False  # Building package, not installing
        return True

    @staticmethod
    def run_setup_hook_safe(hook_name="post_install", delay=0):
        """Safely run setup hook with error handling and idempotency"""
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

            # Strategy 1: Import and run directly
            hook_function = None
            try:
                # Try to import from installed package first
                from cli.setup_hooks import run_post_install_hook

                hook_function = run_post_install_hook
            except ImportError:
                try:
                    # Fallback to legacy function
                    from cli.setup_hooks import post_install

                    hook_function = post_install
                except ImportError:
                    pass

            if hook_function:
                try:
                    success = (
                        hook_function() if "run_post_install_hook" in str(hook_function) else (hook_function(), True)[1]
                    )
                    if success:
                        _hook_state["executed"] = True
                        print("Rediacc: Setup hook completed successfully")
                        return True
                except Exception as e:
                    print(f"Rediacc: Setup hook failed: {e}")

            # Strategy 2: Run as subprocess (most reliable)
            import subprocess

            script_paths = [
                os.path.join(os.path.dirname(__file__), "src", "cli", "setup_hooks.py"),
            ]

            for script_path in script_paths:
                if os.path.exists(script_path):
                    result = subprocess.run(
                        [sys.executable, script_path, hook_name], capture_output=True, text=True, timeout=60
                    )

                    if result.returncode == 0:
                        _hook_state["executed"] = True
                        print("Rediacc: Setup hook completed successfully")
                        if result.stdout:
                            print(result.stdout.strip())
                        return True
                    else:
                        print(f"Rediacc: Setup hook failed: {result.stderr}")

            print("Rediacc: Could not locate or run setup hooks")
            return False

        except Exception as e:
            print(f"Rediacc: Setup hook execution failed: {e}")
            return False


class PostInstallCommand(install):
    """Enhanced custom install command with comprehensive hook support"""

    def run(self):
        # Run the normal install
        install.run(self)

        # Run setup hook with enhanced error handling
        HookRunner.run_setup_hook_safe("post_install")

        # Also register an atexit handler as backup
        atexit.register(lambda: HookRunner.run_setup_hook_safe("post_install", delay=1))

    def execute_hook(self, hook_name):
        """Execute the specified setup hook"""
        try:
            # Import and execute the hook
            import subprocess

            python_exe = sys.executable

            # Find the setup_hooks.py file
            setup_hooks_path = None

            # Try to find it in the installed package
            try:
                import cli.setup_hooks

                setup_hooks_path = cli.setup_hooks.__file__
            except ImportError:
                # Fallback to relative path for development installs
                current_dir = os.path.dirname(os.path.abspath(__file__))
                potential_path = os.path.join(current_dir, "src", "cli", "setup_hooks.py")
                if os.path.exists(potential_path):
                    setup_hooks_path = potential_path

            if setup_hooks_path:
                result = subprocess.run(
                    [python_exe, setup_hooks_path, hook_name], capture_output=True, text=True, timeout=30
                )
                if result.stdout:
                    print(result.stdout.strip())
                if result.stderr:
                    print(result.stderr.strip(), file=sys.stderr)
            else:
                print("Setup hooks not found - skipping protocol registration")
                print("You can register the protocol manually by running: rediacc --register-protocol")

        except Exception as e:
            print(f"Post-install hook failed: {e}")
            print("You can register the protocol manually by running: rediacc --register-protocol")


class PostDevelopCommand(develop):
    """Enhanced custom develop command for development installs"""

    def run(self):
        # Run the normal develop install
        develop.run(self)

        # Run setup hook with enhanced error handling
        HookRunner.run_setup_hook_safe("post_install")

        # Also register an atexit handler as backup
        atexit.register(lambda: HookRunner.run_setup_hook_safe("post_install", delay=1))


class PostEggInfoCommand(egg_info):
    """Enhanced custom egg_info command that can trigger hooks in some scenarios"""

    def run(self):
        egg_info.run(self)

        # Only run hook if this seems to be a final installation step
        if not any(cmd in sys.argv for cmd in ["bdist_wheel", "sdist", "build"]):
            # Delay execution to avoid interfering with egg_info
            def delayed_hook():
                time.sleep(2)
                HookRunner.run_setup_hook_safe("post_install")

            thread = threading.Thread(target=delayed_hook, daemon=True)
            thread.start()


class PreUninstallCommand:
    """Custom uninstall preparation - clean up protocol registration

    Note: This cannot be automatically called by pip uninstall, but provides
    a manual way to clean up before uninstalling.
    """

    @staticmethod
    def run():
        """Execute pre-uninstall cleanup"""
        try:
            # Import and execute the pre-uninstall hook
            import subprocess

            python_exe = sys.executable

            # Find the setup_hooks.py file
            setup_hooks_path = None

            # Try to find it in the installed package
            try:
                import cli.setup_hooks

                setup_hooks_path = cli.setup_hooks.__file__
            except ImportError:
                # Fallback to relative path for development installs
                current_dir = os.path.dirname(os.path.abspath(__file__))
                potential_path = os.path.join(current_dir, "src", "cli", "setup_hooks.py")
                if os.path.exists(potential_path):
                    setup_hooks_path = potential_path

            if setup_hooks_path:
                print("Running pre-uninstall cleanup...")
                result = subprocess.run(
                    [python_exe, setup_hooks_path, "pre_uninstall"], capture_output=True, text=True, timeout=30
                )
                if result.stdout:
                    print(result.stdout.strip())
                if result.stderr:
                    print(result.stderr.strip(), file=sys.stderr)
                print("Pre-uninstall cleanup completed.")
            else:
                print("Setup hooks not found - unable to run pre-uninstall cleanup")
                print("You may need to manually unregister protocols: rediacc protocol unregister")

        except Exception as e:
            print(f"Pre-uninstall cleanup failed: {e}")
            print("You may need to manually unregister protocols: rediacc protocol unregister")


# Entry point functions for alternative triggering mechanisms
def trigger_hook_via_entry_point():
    """Entry point that triggers setup hook - can be called by pip"""
    HookRunner.run_setup_hook_safe("post_install")


def setup_atexit_hook():
    """Register an atexit hook as final fallback"""

    def final_hook():
        if not _hook_state["executed"]:
            HookRunner.run_setup_hook_safe("post_install", delay=0.5)

    atexit.register(final_hook)


# Register the atexit hook immediately when setup.py is loaded
setup_atexit_hook()

# Additional hook triggers based on command line arguments
if "install" in sys.argv or "develop" in sys.argv:
    # Schedule hook to run after setup completes
    def post_setup_hook():
        time.sleep(3)  # Give setup time to complete
        HookRunner.run_setup_hook_safe("post_install")

    thread = threading.Thread(target=post_setup_hook, daemon=True)
    thread.start()

# Enhanced custom command classes
cmdclass = {
    "install": PostInstallCommand,
    "develop": PostDevelopCommand,
    "egg_info": PostEggInfoCommand,
}

# All configuration is in pyproject.toml
# This adds enhanced custom install commands with multiple hook triggers
setup(cmdclass=cmdclass)
