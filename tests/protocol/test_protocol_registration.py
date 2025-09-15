#!/usr/bin/env python3
"""
Test suite for rediacc:// protocol registration and unregistration
Tests cross-platform protocol handler registration functionality
"""

import sys
import os
import platform
import tempfile
import shutil
import subprocess
from pathlib import Path
from unittest.mock import patch, Mock, MagicMock
import pytest

# Add src directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent / 'src'))

from cli.core.protocol_handler import (
    get_platform, get_platform_handler, ProtocolHandlerError,
    register_protocol, unregister_protocol, get_protocol_status
)


class TestProtocolRegistration:
    """Test protocol registration functionality across platforms"""

    def setup_method(self):
        """Set up test fixtures"""
        self.test_cli_path = Path(__file__).parent.parent / 'rediacc.py'
        self.temp_dir = Path(tempfile.mkdtemp())

    def teardown_method(self):
        """Clean up test fixtures"""
        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir)

    def test_get_platform_detection(self):
        """Test platform detection functionality"""
        current_platform = get_platform()
        expected_platforms = ['windows', 'linux', 'macos', 'unknown']
        assert current_platform in expected_platforms

        # Test platform detection works correctly for current system
        system_name = platform.system().lower()
        if system_name == 'darwin':
            assert current_platform == 'macos'
        elif system_name == 'linux':
            assert current_platform == 'linux'
        elif system_name == 'windows':
            assert current_platform == 'windows'

    def test_get_platform_handler_factory(self):
        """Test platform handler factory function"""
        # Test Windows handler
        with patch('cli.core.protocol_handler.get_platform', return_value='windows'):
            handler = get_platform_handler()
            assert handler.__class__.__name__ == 'WindowsProtocolHandler'

        # Test Linux handler
        with patch('cli.core.protocol_handler.get_platform', return_value='linux'):
            handler = get_platform_handler()
            assert handler.__class__.__name__ == 'LinuxProtocolHandler'

        # Test macOS handler
        with patch('cli.core.protocol_handler.get_platform', return_value='macos'):
            handler = get_platform_handler()
            assert handler.__class__.__name__ == 'MacOSProtocolHandler'

        # Test unknown platform
        with patch('cli.core.protocol_handler.get_platform', return_value='unknown'):
            with pytest.raises(ProtocolHandlerError):
                get_platform_handler()

    @pytest.mark.skipif(platform.system() != 'Windows', reason="Windows-specific test")
    def test_windows_protocol_registration(self):
        """Test Windows protocol registration"""
        try:
            from cli.core.protocol_handler import WindowsProtocolHandler
            handler = WindowsProtocolHandler()

            # Test registration with mock registry operations
            with patch('cli.core.protocol_handler.is_windows', return_value=True):
                with patch.object(handler, '_create_registry_key') as mock_create:
                    with patch.object(handler, '_set_registry_value') as mock_set:
                        mock_create.return_value = Mock()

                        result = handler.register(str(self.test_cli_path))
                        assert result is True

                        # Verify registry operations were called
                        assert mock_create.called
                        assert mock_set.called

        except ImportError:
            pytest.skip("Windows protocol handler not available")

    @pytest.mark.skipif(platform.system() != 'Linux', reason="Linux-specific test")
    def test_linux_protocol_registration(self):
        """Test Linux protocol registration"""
        try:
            from cli.core.linux_protocol_handler import LinuxProtocolHandler
            handler = LinuxProtocolHandler()

            # Create temporary directories for testing
            temp_applications = self.temp_dir / 'applications'
            temp_applications.mkdir(parents=True)

            with patch.object(handler, 'applications_dir', temp_applications):
                result = handler.register(str(self.test_cli_path))
                assert result is True

                # Check that desktop file was created
                desktop_file = temp_applications / 'rediacc-protocol-handler.desktop'
                assert desktop_file.exists()

                # Verify desktop file content
                content = desktop_file.read_text()
                assert 'rediacc' in content
                assert 'protocol' in content.lower()

        except ImportError:
            pytest.skip("Linux protocol handler not available")

    @pytest.mark.skipif(platform.system() != 'Darwin', reason="macOS-specific test")
    def test_macos_protocol_registration(self):
        """Test macOS protocol registration"""
        try:
            from cli.core.macos_protocol_handler import MacOSProtocolHandler
            handler = MacOSProtocolHandler()

            # Mock LSSetDefaultHandlerForURLScheme
            with patch('cli.core.macos_protocol_handler.objc') as mock_objc:
                with patch('cli.core.macos_protocol_handler.AppKit') as mock_appkit:
                    mock_bundle = Mock()
                    mock_bundle.bundleIdentifier.return_value = 'com.rediacc.cli'
                    mock_appkit.NSBundle.mainBundle.return_value = mock_bundle

                    result = handler.register(str(self.test_cli_path))
                    assert result is True

        except ImportError:
            pytest.skip("macOS protocol handler not available")

    def test_protocol_registration_integration(self):
        """Test protocol registration through main interface"""
        with patch('cli.core.protocol_handler.get_platform_handler') as mock_handler:
            mock_instance = Mock()
            mock_instance.register.return_value = True
            mock_handler.return_value = mock_instance

            result = register_protocol(str(self.test_cli_path))
            assert result is True

            mock_handler.assert_called_once()
            mock_instance.register.assert_called_once_with(str(self.test_cli_path))

    def test_protocol_unregistration_integration(self):
        """Test protocol unregistration through main interface"""
        with patch('cli.core.protocol_handler.get_platform_handler') as mock_handler:
            mock_instance = Mock()
            mock_instance.unregister.return_value = True
            mock_handler.return_value = mock_instance

            result = unregister_protocol()
            assert result is True

            mock_handler.assert_called_once()
            mock_instance.unregister.assert_called_once()

    def test_protocol_status_check(self):
        """Test protocol status checking"""
        with patch('cli.core.protocol_handler.get_platform_handler') as mock_handler:
            mock_instance = Mock()
            mock_instance.is_registered.return_value = True
            mock_handler.return_value = mock_instance

            status = get_protocol_status()
            assert status is True

            mock_handler.assert_called_once()
            mock_instance.is_registered.assert_called_once()

    def test_registration_error_handling(self):
        """Test error handling during registration"""
        with patch('cli.core.protocol_handler.get_platform_handler') as mock_handler:
            mock_instance = Mock()
            mock_instance.register.side_effect = Exception("Registration failed")
            mock_handler.return_value = mock_instance

            result = register_protocol(str(self.test_cli_path))
            assert result is False

    def test_registration_with_invalid_cli_path(self):
        """Test registration with invalid CLI path"""
        invalid_path = "/nonexistent/path/to/cli"

        with patch('cli.core.protocol_handler.get_platform_handler') as mock_handler:
            mock_instance = Mock()
            mock_instance.register.return_value = False
            mock_handler.return_value = mock_instance

            result = register_protocol(invalid_path)
            assert result is False

    def test_registration_permission_handling(self):
        """Test registration when permissions are insufficient"""
        with patch('cli.core.protocol_handler.get_platform_handler') as mock_handler:
            mock_instance = Mock()
            mock_instance.register.side_effect = PermissionError("Admin privileges required")
            mock_handler.return_value = mock_instance

            result = register_protocol(str(self.test_cli_path))
            assert result is False

    @pytest.mark.skipif(not shutil.which('python3'), reason="Python3 not available")
    def test_real_protocol_status_command(self):
        """Test real protocol status command execution"""
        cli_script = Path(__file__).parent.parent / 'rediacc.py'

        if cli_script.exists():
            try:
                result = subprocess.run(
                    ['python3', str(cli_script), '--protocol-status'],
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                # Command should complete without error (regardless of protocol status)
                assert result.returncode in [0, 1]
                # Should produce some output
                assert len(result.stdout) > 0 or len(result.stderr) > 0
            except subprocess.TimeoutExpired:
                pytest.fail("Protocol status command timed out")

    def test_protocol_registration_cli_integration(self):
        """Test protocol registration through CLI commands"""
        # Test with mocked platform handler
        with patch('cli.core.protocol_handler.get_platform_handler') as mock_handler:
            mock_instance = Mock()
            mock_instance.register.return_value = True
            mock_instance.unregister.return_value = True
            mock_instance.is_registered.return_value = False
            mock_handler.return_value = mock_instance

            # Test registration
            from cli.commands.cli_main import main

            # Mock sys.argv for registration
            with patch('sys.argv', ['cli_main.py', '--register-protocol']):
                with patch('sys.exit') as mock_exit:
                    main()
                    # Should not exit with error
                    if mock_exit.called:
                        assert mock_exit.call_args[0][0] == 0

            # Test status check
            with patch('sys.argv', ['cli_main.py', '--protocol-status']):
                with patch('sys.exit') as mock_exit:
                    main()
                    # Status command should complete

            # Test unregistration
            mock_instance.is_registered.return_value = True
            with patch('sys.argv', ['cli_main.py', '--unregister-protocol']):
                with patch('sys.exit') as mock_exit:
                    main()
                    # Should not exit with error
                    if mock_exit.called:
                        assert mock_exit.call_args[0][0] == 0


class TestProtocolRegistrationSafety:
    """Test safety and security aspects of protocol registration"""

    def test_cli_path_validation(self):
        """Test that CLI path validation works correctly"""
        with patch('cli.core.protocol_handler.get_platform_handler') as mock_handler:
            mock_instance = Mock()
            mock_handler.return_value = mock_instance

            # Test with relative path
            register_protocol("./relative/path")
            # Should call with absolute path
            called_path = mock_instance.register.call_args[0][0]
            assert os.path.isabs(called_path)

    def test_registration_cleanup_on_failure(self):
        """Test cleanup when registration fails partway through"""
        with patch('cli.core.protocol_handler.get_platform_handler') as mock_handler:
            mock_instance = Mock()
            # Simulate partial failure
            mock_instance.register.side_effect = [True, Exception("Cleanup test")]
            mock_handler.return_value = mock_instance

            # Should handle failure gracefully
            result = register_protocol("/test/path")
            assert result is False

    def test_concurrent_registration_handling(self):
        """Test handling of concurrent registration attempts"""
        # This test would be more relevant for actual file-based operations
        # but we can test the basic concurrent call handling
        with patch('cli.core.protocol_handler.get_platform_handler') as mock_handler:
            mock_instance = Mock()
            mock_instance.register.return_value = True
            mock_handler.return_value = mock_instance

            # Multiple rapid calls should all succeed
            results = []
            for _ in range(5):
                results.append(register_protocol("/test/path"))

            assert all(results)

    def test_protocol_validation(self):
        """Test that protocol scheme validation works"""
        # This would test URL scheme validation if implemented
        # For now, we test that the basic structure is maintained
        with patch('cli.core.protocol_handler.get_platform_handler') as mock_handler:
            mock_instance = Mock()
            mock_instance.register.return_value = True
            mock_handler.return_value = mock_instance

            result = register_protocol("/valid/path")
            assert result is True

            # Verify the handler was called correctly
            mock_instance.register.assert_called_with("/valid/path")


class TestProtocolRegistrationEdgeCases:
    """Test edge cases and error conditions"""

    def test_registration_with_spaces_in_path(self):
        """Test registration with paths containing spaces"""
        test_path = "/path with spaces/to/cli"

        with patch('cli.core.protocol_handler.get_platform_handler') as mock_handler:
            mock_instance = Mock()
            mock_instance.register.return_value = True
            mock_handler.return_value = mock_instance

            result = register_protocol(test_path)
            assert result is True

            # Verify path was passed correctly
            mock_instance.register.assert_called_with(test_path)

    def test_registration_with_unicode_path(self):
        """Test registration with Unicode characters in path"""
        test_path = "/path/with/unicode/测试/cli"

        with patch('cli.core.protocol_handler.get_platform_handler') as mock_handler:
            mock_instance = Mock()
            mock_instance.register.return_value = True
            mock_handler.return_value = mock_instance

            result = register_protocol(test_path)
            assert result is True

    def test_unregistration_when_not_registered(self):
        """Test unregistration when protocol is not registered"""
        with patch('cli.core.protocol_handler.get_platform_handler') as mock_handler:
            mock_instance = Mock()
            mock_instance.is_registered.return_value = False
            mock_instance.unregister.return_value = True
            mock_handler.return_value = mock_instance

            result = unregister_protocol()
            # Should succeed even if not registered
            assert result is True

    def test_status_check_error_handling(self):
        """Test status check when underlying system errors occur"""
        with patch('cli.core.protocol_handler.get_platform_handler') as mock_handler:
            mock_instance = Mock()
            mock_instance.is_registered.side_effect = Exception("System error")
            mock_handler.return_value = mock_instance

            # Should handle errors gracefully
            status = get_protocol_status()
            # Should return False on error
            assert status is False

    def test_platform_handler_import_failure(self):
        """Test handling when platform-specific handler can't be imported"""
        with patch('cli.core.protocol_handler.get_platform', return_value='unknown'):
            with pytest.raises(ProtocolHandlerError):
                get_platform_handler()


if __name__ == '__main__':
    pytest.main([__file__, '-v'])