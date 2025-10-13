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
import platform
from setuptools import setup
from setuptools.command.install import install
from setuptools.command.develop import develop
try:
    from wheel.bdist_wheel import bdist_wheel
except ImportError:
    bdist_wheel = None

class PostInstallCommand(install):
    """Custom install command with post-install hook for protocol registration"""
    
    def run(self):
        # Run the normal install
        install.run(self)
        
        # Run post-install hook on Windows only
        if platform.system().lower() == 'windows':
            self.execute_hook('post_install')
    
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
                potential_path = os.path.join(current_dir, 'src', 'cli', 'setup_hooks.py')
                if os.path.exists(potential_path):
                    setup_hooks_path = potential_path
            
            if setup_hooks_path:
                result = subprocess.run([python_exe, setup_hooks_path, hook_name], 
                                      capture_output=True, text=True, timeout=30)
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
    """Custom develop command with post-install hook for protocol registration"""
    
    def run(self):
        # Run the normal develop install
        develop.run(self)
        
        # Run post-install hook on Windows only
        if platform.system().lower() == 'windows':
            try:
                # For development installs, run the hook directly
                current_dir = os.path.dirname(os.path.abspath(__file__))
                setup_hooks_path = os.path.join(current_dir, 'src', 'cli', 'setup_hooks.py')
                
                if os.path.exists(setup_hooks_path):
                    import subprocess
                    result = subprocess.run([sys.executable, setup_hooks_path, 'post_install'], 
                                          capture_output=True, text=True, timeout=30)
                    if result.stdout:
                        print(result.stdout.strip())
                    if result.stderr:
                        print(result.stderr.strip(), file=sys.stderr)
                else:
                    print("Development install: protocol registration skipped")
                    print("You can register the protocol manually by running: rediacc --register-protocol")
            except Exception as e:
                print(f"Development post-install hook failed: {e}")
                print("You can register the protocol manually by running: rediacc --register-protocol")

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
                potential_path = os.path.join(current_dir, 'src', 'cli', 'setup_hooks.py')
                if os.path.exists(potential_path):
                    setup_hooks_path = potential_path
            
            if setup_hooks_path:
                print("Running pre-uninstall cleanup...")
                result = subprocess.run([python_exe, setup_hooks_path, 'pre_uninstall'], 
                                      capture_output=True, text=True, timeout=30)
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

# Custom command classes
cmdclass = {
    'install': PostInstallCommand,
    'develop': PostDevelopCommand,
}

# All configuration is in pyproject.toml
# This adds custom install commands for protocol registration
setup(cmdclass=cmdclass)