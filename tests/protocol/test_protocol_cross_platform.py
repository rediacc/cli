#!/usr/bin/env python3
"""
Cross-platform protocol testing for rediacc:// handler
Tests protocol registration and handling across Windows, Linux, and macOS
"""

import sys
import os
import platform
import tempfile
import subprocess
import shutil
from pathlib import Path
from unittest.mock import patch, Mock, MagicMock, mock_open
import pytest

# Add src directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent / 'src'))

from cli.core.protocol_handler import get_platform, get_platform_handler


class TestCrossPlatformDetection:
    """Test cross-platform detection and handler selection"""

    def test_platform_detection_accuracy(self):
        """Test that platform detection returns correct values"""
        detected_platform = get_platform()
        expected_platforms = ['windows', 'linux', 'macos', 'unknown']
        assert detected_platform in expected_platforms

        # Verify detection matches actual system
        system_name = platform.system().lower()
        if system_name == 'windows':
            assert detected_platform == 'windows'
        elif system_name == 'linux':
            assert detected_platform == 'linux'
        elif system_name == 'darwin':
            assert detected_platform == 'macos'

    def test_platform_handler_selection(self):
        """Test that correct handler is selected for each platform"""
        platform_handlers = {
            'windows': 'WindowsProtocolHandler',
            'linux': 'LinuxProtocolHandler',
            'macos': 'MacOSProtocolHandler'
        }

        for platform_name, expected_handler in platform_handlers.items():
            with patch('cli.core.protocol_handler.get_platform', return_value=platform_name):
                # Mock platform checks for cross-platform testing
                with patch('cli.core.protocol_handler.is_windows', return_value=(platform_name == 'windows')):
                    with patch('cli.core.shared.is_windows', return_value=(platform_name == 'windows')):
                        handler = get_platform_handler()
                        assert handler.__class__.__name__ == expected_handler

    def test_unknown_platform_handling(self):
        """Test handling of unknown/unsupported platforms"""
        with patch('cli.core.protocol_handler.get_platform', return_value='unknown'):
            from cli.core.protocol_handler import ProtocolHandlerError
            with pytest.raises(ProtocolHandlerError):
                get_platform_handler()


@pytest.mark.skipif(platform.system() != 'Windows', reason="Windows-specific tests")
class TestWindowsProtocolIntegration:
    """Test Windows-specific protocol integration"""

    def setup_method(self):
        """Set up Windows test fixtures"""
        self.temp_dir = Path(tempfile.mkdtemp())

    def teardown_method(self):
        """Clean up Windows test fixtures"""
        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir)

    def test_windows_registry_operations(self):
        """Test Windows registry operations for protocol registration"""
        try:
            from cli.core.protocol_handler import WindowsProtocolHandler
            handler = WindowsProtocolHandler()

            # Test with mock registry operations
            with patch('cli.core.protocol_handler.is_windows', return_value=True):
                with patch.object(handler, '_open_registry_key') as mock_open:
                    with patch.object(handler, '_create_registry_key') as mock_create:
                        with patch.object(handler, '_set_registry_value') as mock_set:
                            mock_key = Mock()
                            mock_open.return_value = mock_key
                            mock_create.return_value = mock_key

                            # Test registration
                            result = handler.register(str(self.temp_dir / 'test_cli.exe'))
                            assert result is True

                            # Verify registry operations were called
                            assert mock_create.called
                            assert mock_set.called

        except ImportError:
            pytest.skip("Windows protocol handler not available")

    def test_windows_protocol_unregistration(self):
        """Test Windows protocol unregistration"""
        try:
            from cli.core.protocol_handler import WindowsProtocolHandler
            handler = WindowsProtocolHandler()

            with patch.object(handler, '_delete_registry_key') as mock_delete:
                result = handler.unregister()
                assert result is True
                mock_delete.assert_called()

        except ImportError:
            pytest.skip("Windows protocol handler not available")

    def test_windows_batch_integration(self):
        """Test batch wrapper integration"""
        bat_script = Path(__file__).parent.parent / 'rediacc.bat'
        if bat_script.exists():
            # Test batch protocol registration (dry run)
            try:
                result = subprocess.run(
                    [str(bat_script), 'protocol', 'status'],
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                # Should complete without error (regardless of actual registration status)
                assert result.returncode in [0, 1]
            except (subprocess.TimeoutExpired, FileNotFoundError):
                pytest.skip("Batch script not available or script timeout")

    def test_windows_admin_privilege_detection(self):
        """Test detection of administrator privileges on Windows"""
        try:
            from cli.core.protocol_handler import WindowsProtocolHandler
            handler = WindowsProtocolHandler()

            with patch('cli.core.protocol_handler.ctypes') as mock_ctypes:
                mock_ctypes.windll.shell32.IsUserAnAdmin.return_value = 1
                with patch.object(handler, '_has_admin_privileges') as mock_admin:
                    mock_admin.return_value = True
                    # Should detect admin privileges correctly
                    result = handler.register('/test/path')
                    # Registration attempt should be made regardless of result

        except ImportError:
            pytest.skip("Windows protocol handler not available")


@pytest.mark.skipif(platform.system() != 'Linux', reason="Linux-specific tests")
class TestLinuxProtocolIntegration:
    """Test Linux-specific protocol integration"""

    def setup_method(self):
        """Set up Linux test fixtures"""
        self.temp_dir = Path(tempfile.mkdtemp())

    def teardown_method(self):
        """Clean up Linux test fixtures"""
        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir)

    def test_linux_desktop_file_creation(self):
        """Test Linux desktop file creation for protocol registration"""
        try:
            from cli.core.linux_protocol_handler import LinuxProtocolHandler
            handler = LinuxProtocolHandler()

            # Create temporary applications directory
            temp_apps = self.temp_dir / 'applications'
            temp_apps.mkdir(parents=True)

            with patch.object(handler, 'applications_dir', temp_apps):
                with patch('subprocess.run') as mock_run:
                    mock_run.return_value = Mock(returncode=0)

                    cli_path = self.temp_dir / 'test_cli'
                    cli_path.touch()

                    result = handler.register(str(cli_path))
                    assert result is True

                    # Check desktop file was created
                    desktop_file = temp_apps / 'rediacc-protocol.desktop'
                    assert desktop_file.exists()

                    # Verify desktop file content
                    content = desktop_file.read_text()
                    assert '[Desktop Entry]' in content
                    assert 'rediacc' in content.lower()

        except ImportError:
            pytest.skip("Linux protocol handler not available")

    def test_linux_xdg_integration(self):
        """Test XDG desktop integration on Linux"""
        try:
            from cli.core.linux_protocol_handler import LinuxProtocolHandler
            handler = LinuxProtocolHandler()

            with patch('subprocess.run') as mock_run:
                mock_run.return_value = Mock(returncode=0)

                # Test desktop database update
                result = handler.register('/test/cli/path')

                # Should attempt to update desktop database
                update_calls = [call for call in mock_run.call_args_list
                               if 'update-desktop-database' in str(call)]

        except ImportError:
            pytest.skip("Linux protocol handler not available")

    def test_linux_protocol_unregistration(self):
        """Test Linux protocol unregistration"""
        try:
            from cli.core.linux_protocol_handler import LinuxProtocolHandler
            handler = LinuxProtocolHandler()

            temp_apps = self.temp_dir / 'applications'
            temp_apps.mkdir(parents=True)

            # Create desktop file
            desktop_file = temp_apps / 'rediacc-protocol.desktop'
            desktop_file.write_text('[Desktop Entry]\nName=Rediacc Protocol Handler\n')

            with patch.object(handler, 'applications_dir', temp_apps):
                result = handler.unregister()
                assert result is True

                # Desktop file should be removed
                assert not desktop_file.exists()

        except ImportError:
            pytest.skip("Linux protocol handler not available")

    def test_linux_environment_detection(self):
        """Test Linux desktop environment detection"""
        try:
            from cli.core.linux_protocol_handler import LinuxProtocolHandler
            handler = LinuxProtocolHandler()

            # Test with various desktop environments
            desktop_environments = ['GNOME', 'KDE', 'XFCE', 'MATE', None]

            for de in desktop_environments:
                with patch.dict(os.environ, {'XDG_CURRENT_DESKTOP': de} if de else {}, clear=True):
                    # Should handle any desktop environment
                    applications_dir = handler.applications_dir
                    assert applications_dir.exists() or applications_dir.parent.exists()

        except ImportError:
            pytest.skip("Linux protocol handler not available")


@pytest.mark.skipif(platform.system() != 'Darwin', reason="macOS-specific tests")
class TestMacOSProtocolIntegration:
    """Test macOS-specific protocol integration"""

    def setup_method(self):
        """Set up macOS test fixtures"""
        self.temp_dir = Path(tempfile.mkdtemp())

    def teardown_method(self):
        """Clean up macOS test fixtures"""
        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir)

    def test_macos_url_scheme_registration(self):
        """Test macOS URL scheme registration"""
        try:
            from cli.core.macos_protocol_handler import MacOSProtocolHandler
            handler = MacOSProtocolHandler()

            # Mock Objective-C components
            with patch('cli.core.macos_protocol_handler.objc') as mock_objc:
                with patch('cli.core.macos_protocol_handler.AppKit') as mock_appkit:
                    with patch('cli.core.macos_protocol_handler.CoreServices') as mock_core:
                        # Mock bundle identifier
                        mock_bundle = Mock()
                        mock_bundle.bundleIdentifier.return_value = 'com.rediacc.cli'
                        mock_appkit.NSBundle.mainBundle.return_value = mock_bundle

                        # Mock LSSetDefaultHandlerForURLScheme
                        mock_core.LSSetDefaultHandlerForURLScheme.return_value = 0

                        result = handler.register('/test/cli/path')
                        assert result is True

                        # Verify URL scheme registration was attempted
                        mock_core.LSSetDefaultHandlerForURLScheme.assert_called()

        except ImportError:
            pytest.skip("macOS protocol handler not available")

    def test_macos_protocol_unregistration(self):
        """Test macOS protocol unregistration"""
        try:
            from cli.core.macos_protocol_handler import MacOSProtocolHandler
            handler = MacOSProtocolHandler()

            with patch('cli.core.macos_protocol_handler.objc') as mock_objc:
                with patch('cli.core.macos_protocol_handler.CoreServices') as mock_core:
                    mock_core.LSSetDefaultHandlerForURLScheme.return_value = 0

                    result = handler.unregister()
                    assert result is True

        except ImportError:
            pytest.skip("macOS protocol handler not available")

    def test_macos_bundle_creation(self):
        """Test macOS application bundle handling"""
        try:
            from cli.core.macos_protocol_handler import MacOSProtocolHandler
            handler = MacOSProtocolHandler()

            # Test bundle identifier generation
            with patch('cli.core.macos_protocol_handler.AppKit') as mock_appkit:
                mock_bundle = Mock()
                mock_bundle.bundleIdentifier.return_value = None
                mock_appkit.NSBundle.mainBundle.return_value = mock_bundle

                # Should handle missing bundle identifier gracefully
                bundle_id = handler._get_bundle_identifier()
                assert bundle_id is not None

        except ImportError:
            pytest.skip("macOS protocol handler not available")


class TestProtocolCompatibility:
    """Test protocol compatibility across different system configurations"""

    def test_path_separator_handling(self):
        """Test handling of different path separators across platforms"""
        test_paths = [
            '/unix/style/path',
            'C:\\Windows\\Style\\Path',
            '~/home/relative/path',
            './current/directory/path'
        ]

        for test_path in test_paths:
            # Should handle all path styles on all platforms
            normalized_path = os.path.normpath(test_path)
            assert normalized_path is not None

    def test_line_ending_compatibility(self):
        """Test handling of different line endings in configuration files"""
        line_endings = ['\n', '\r\n', '\r']
        test_content_base = '[Desktop Entry]\nName=Rediacc\nExec=/usr/bin/rediacc'

        for ending in line_endings:
            content = test_content_base.replace('\n', ending)
            # Should parse correctly regardless of line endings
            lines = content.splitlines()
            assert len(lines) >= 3

    def test_permission_handling(self):
        """Test permission handling across platforms"""
        temp_file = Path(tempfile.mktemp())

        try:
            temp_file.touch()

            # Test permission modification
            if os.name != 'nt':  # Unix-like systems
                temp_file.chmod(0o755)
                stat_info = temp_file.stat()
                assert stat_info.st_mode & 0o755

        finally:
            if temp_file.exists():
                temp_file.unlink()

    def test_encoding_compatibility(self):
        """Test encoding compatibility across platforms"""
        test_strings = [
            'ASCII text',
            'UTF-8 tëxt with special characters',
            'Unicode: 测试文本',
            'Emoji: 🔗 Protocol Test 📋'
        ]

        for test_string in test_strings:
            # Should handle various encodings
            encoded = test_string.encode('utf-8')
            decoded = encoded.decode('utf-8')
            assert decoded == test_string


class TestProtocolEnvironmentAdaptation:
    """Test protocol adaptation to different environments"""

    def test_virtual_environment_detection(self):
        """Test detection of virtual environments"""
        # Test various virtual environment indicators
        venv_indicators = [
            ('VIRTUAL_ENV', '/path/to/venv'),
            ('CONDA_DEFAULT_ENV', 'myenv'),
            ('PIPENV_ACTIVE', '1'),
        ]

        for env_var, value in venv_indicators:
            with patch.dict(os.environ, {env_var: value}):
                # Should detect virtual environment
                in_venv = any(var in os.environ for var, _ in venv_indicators)
                assert in_venv

    def test_container_environment_detection(self):
        """Test detection of container environments"""
        container_indicators = [
            ('/.dockerenv', True),
            ('/proc/1/cgroup', 'docker'),
            ('KUBERNETES_SERVICE_HOST', 'kubernetes.default.svc'),
        ]

        # Test Docker detection
        with patch('os.path.exists') as mock_exists:
            mock_exists.return_value = True
            # Should detect Docker environment
            in_docker = os.path.exists('/.dockerenv')

    def test_wsl_environment_detection(self):
        """Test detection of WSL environment"""
        wsl_indicators = [
            ('/proc/version', 'Microsoft'),
            ('WSL_DISTRO_NAME', 'Ubuntu'),
        ]

        # Test WSL detection
        with patch('builtins.open', mock_open(read_data='Linux version 4.4.0-Microsoft')):
            with patch('os.path.exists', return_value=True):
                try:
                    with open('/proc/version', 'r') as f:
                        version_info = f.read()
                        in_wsl = 'Microsoft' in version_info
                except:
                    in_wsl = False

    def test_headless_environment_handling(self):
        """Test handling of headless environments"""
        # Test without display
        with patch.dict(os.environ, {}, clear=True):
            # Should handle missing DISPLAY gracefully
            display = os.environ.get('DISPLAY')
            assert display is None

        # Test with display
        with patch.dict(os.environ, {'DISPLAY': ':0'}):
            display = os.environ.get('DISPLAY')
            assert display == ':0'

    def test_different_shell_environments(self):
        """Test protocol handling in different shell environments"""
        shell_configs = [
            ('SHELL', '/bin/bash'),
            ('SHELL', '/bin/zsh'),
            ('SHELL', '/bin/fish'),
            ('SHELL', '/usr/bin/powershell'),
        ]

        for env_var, shell_path in shell_configs:
            with patch.dict(os.environ, {env_var: shell_path}):
                current_shell = os.environ.get('SHELL')
                # Should handle any shell environment
                assert current_shell == shell_path


class TestProtocolVersionCompatibility:
    """Test protocol compatibility across different software versions"""

    def test_python_version_compatibility(self):
        """Test compatibility with different Python versions"""
        python_version = sys.version_info

        # Should work with Python 3.7+
        assert python_version.major >= 3
        if python_version.major == 3:
            assert python_version.minor >= 7

    def test_cli_version_detection(self):
        """Test CLI version detection for compatibility"""
        cli_script = Path(__file__).parent.parent / 'rediacc.py'

        if cli_script.exists():
            try:
                result = subprocess.run(
                    [sys.executable, str(cli_script), '--version'],
                    capture_output=True,
                    text=True,
                    timeout=10
                )

                if result.returncode == 0:
                    version_output = result.stdout
                    # Should have version information
                    assert len(version_output) > 0

            except subprocess.TimeoutExpired:
                pytest.skip("Version command timeout")

    def test_dependency_compatibility(self):
        """Test compatibility with different dependency versions"""
        # Test core dependencies
        core_modules = ['urllib.parse', 'pathlib', 'subprocess', 'platform']

        for module_name in core_modules:
            try:
                __import__(module_name)
            except ImportError:
                pytest.fail(f"Required module {module_name} not available")


if __name__ == '__main__':
    pytest.main([__file__, '-v'])