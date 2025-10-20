#!/usr/bin/env python3
"""
Test for PyPI installation detection fix
Tests the is_pypi_installation() function and initialize_cli_command() behavior
"""

import sys
import os
from pathlib import Path
import unittest
from unittest.mock import patch, MagicMock

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from cli.core.shared import is_pypi_installation, CLI_TOOL


class TestPyPIInstallationDetection(unittest.TestCase):
    """Test suite for PyPI installation detection"""

    def test_is_pypi_installation_from_source(self):
        """Test detection when running from source (development)"""
        # When running tests from source, should detect as NOT a PyPI installation
        # This depends on the current test environment
        result = is_pypi_installation()
        # Should be False when running from source
        self.assertFalse(result, "Should detect source installation correctly")

    @patch('cli.core.shared.CLI_TOOL', '/home/user/.local/lib/python3.13/site-packages/cli/commands/cli_main.py')
    def test_is_pypi_installation_site_packages(self):
        """Test detection for site-packages installation"""
        result = is_pypi_installation()
        self.assertTrue(result, "Should detect site-packages as PyPI installation")

    @patch('cli.core.shared.CLI_TOOL', '/usr/lib/python3/dist-packages/cli/commands/cli_main.py')
    def test_is_pypi_installation_dist_packages(self):
        """Test detection for dist-packages installation (Debian/Ubuntu)"""
        result = is_pypi_installation()
        self.assertTrue(result, "Should detect dist-packages as PyPI installation")

    @patch('cli.core.shared.CLI_TOOL', '/home/user/projects/cli/src/cli/commands/cli_main.py')
    def test_is_pypi_installation_project_dir(self):
        """Test detection for project directory (development)"""
        result = is_pypi_installation()
        self.assertFalse(result, "Should detect project directory as source installation")

    def test_cli_tool_path_exists(self):
        """Verify CLI_TOOL path is correctly constructed"""
        self.assertTrue(os.path.exists(CLI_TOOL), f"CLI_TOOL path should exist: {CLI_TOOL}")
        self.assertTrue(CLI_TOOL.endswith('cli_main.py'), "CLI_TOOL should point to cli_main.py")


class TestInitializeCliCommand(unittest.TestCase):
    """Test suite for initialize_cli_command() with PyPI installation fix"""

    def setUp(self):
        """Set up test fixtures"""
        self.mock_args = MagicMock()
        self.mock_args.token = None
        self.mock_parser = MagicMock()

    @patch('cli.core.shared.TokenManager.get_token')
    @patch('cli.core.shared.is_pypi_installation')
    @patch('cli.core.shared.os.path.exists')
    @patch('cli.core.shared.os.access')
    def test_initialize_cli_command_pypi_installation(self, mock_access, mock_exists, mock_is_pypi, mock_get_token):
        """Test that executable check is skipped for PyPI installations"""
        from cli.core.shared import initialize_cli_command

        # Simulate PyPI installation where file exists but is not executable
        mock_is_pypi.return_value = True
        mock_exists.return_value = True
        mock_access.return_value = False  # Not executable
        mock_get_token.return_value = "test-token-123"

        # This should NOT raise an error because PyPI installations skip the executable check
        try:
            initialize_cli_command(self.mock_args, self.mock_parser, requires_cli_tool=True)
            # If we get here, the test passed
            self.assertTrue(True)
        except SystemExit:
            self.fail("initialize_cli_command should not fail for PyPI installation even if not executable")

    @patch('cli.core.shared.TokenManager.get_token')
    @patch('cli.core.shared.is_pypi_installation')
    @patch('cli.core.shared.is_windows')
    @patch('cli.core.shared.os.path.exists')
    @patch('cli.core.shared.os.access')
    @patch('cli.core.shared.error_exit')
    def test_initialize_cli_command_source_not_executable(self, mock_error_exit, mock_access, mock_exists,
                                                           mock_is_windows, mock_is_pypi, mock_get_token):
        """Test that executable check is enforced for source installations"""
        from cli.core.shared import initialize_cli_command

        # Simulate source installation where file exists but is not executable
        mock_is_pypi.return_value = False  # Source installation
        mock_is_windows.return_value = False  # Linux
        mock_exists.return_value = True
        mock_access.return_value = False  # Not executable
        mock_get_token.return_value = "test-token-123"

        # This SHOULD call error_exit because it's a source installation
        initialize_cli_command(self.mock_args, self.mock_parser, requires_cli_tool=True)

        # Verify error_exit was called
        mock_error_exit.assert_called_once()
        error_message = mock_error_exit.call_args[0][0]
        self.assertIn("not executable", error_message)


if __name__ == '__main__':
    unittest.main()
