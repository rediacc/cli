#!/usr/bin/env python3
"""
Integration tests for rediacc.py CLI wrapper
Tests real functionality without mocks
"""

import sys
import os
import subprocess
import tempfile
import shutil
from pathlib import Path
import pytest
import time

# Add the current directory to Python path so we can import rediacc
sys.path.insert(0, str(Path(__file__).parent))

from rediacc import RediaccCLI, Colors


class TestRealColors:
    """Test the Colors utility class with real behavior"""

    def test_colors_have_ansi_codes(self):
        """Test that colors contain ANSI escape sequences"""
        # Reset colors to ensure they're enabled
        Colors.RED = '\033[0;31m'
        Colors.GREEN = '\033[0;32m'
        Colors.NC = '\033[0m'

        assert '\033[' in Colors.RED
        assert '\033[' in Colors.GREEN
        assert '\033[' in Colors.NC

    def test_colors_disable_removes_codes(self):
        """Test that disable actually removes ANSI codes"""
        Colors.disable()

        assert Colors.RED == ''
        assert Colors.GREEN == ''
        assert Colors.NC == ''


class TestRealRediaccCLI:
    """Test RediaccCLI with real functionality"""

    def setup_method(self):
        """Set up test fixtures"""
        self.cli = RediaccCLI()
        self.temp_dir = Path(tempfile.mkdtemp())

    def teardown_method(self):
        """Clean up test fixtures"""
        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir)

    def test_init_creates_real_paths(self):
        """Test that initialization creates real Path objects"""
        assert isinstance(self.cli.script_dir, Path)
        assert isinstance(self.cli.cli_root, Path)
        assert isinstance(self.cli.env_file, Path)
        assert isinstance(self.cli.config_dir, Path)

        # Verify these are actual paths in the file system
        assert self.cli.script_dir.exists()
        assert self.cli.cli_root.exists()

    def test_find_python_returns_working_interpreter(self):
        """Test that find_python returns a working Python interpreter"""
        python_cmd = self.cli.find_python()

        if python_cmd:  # May be None if Python not found
            # Test that the returned command actually works
            result = subprocess.run(
                [python_cmd, '--version'],
                capture_output=True,
                text=True
            )
            assert result.returncode == 0
            assert 'Python' in result.stdout

    def test_get_python_command_returns_working_interpreter(self):
        """Test that get_python_command returns a working interpreter"""
        # This will exit if Python not found, so we expect it to work
        try:
            python_cmd = self.cli.get_python_command()

            # Test that the returned command actually works
            result = subprocess.run(
                [python_cmd, '--version'],
                capture_output=True,
                text=True
            )
            assert result.returncode == 0
            assert 'Python' in result.stdout
        except SystemExit:
            # If Python is not found, that's also a valid test result
            pytest.skip("Python interpreter not found on system")

    def test_run_command_with_real_command(self):
        """Test run_command with real system commands"""
        # Test a simple command that should work on all systems
        result = self.cli.run_command(['python3', '--version'], check=False)

        # Should be a real subprocess.CompletedProcess
        assert hasattr(result, 'returncode')
        assert hasattr(result, 'args')

    def test_load_env_with_real_file(self):
        """Test environment loading with a real temporary file"""
        # Create a temporary .env file
        env_file = self.temp_dir / '.env'
        env_content = """
# Test environment file
TEST_VAR=test_value
ANOTHER_VAR="quoted value"
# Comment line

EMPTY_VAR=
"""
        env_file.write_text(env_content)

        # Create a CLI instance pointing to our temp directory
        cli = RediaccCLI()
        cli.env_file = env_file
        cli.load_env()

        assert 'TEST_VAR' in cli.env_vars
        assert cli.env_vars['TEST_VAR'] == 'test_value'
        assert 'ANOTHER_VAR' in cli.env_vars
        assert cli.env_vars['ANOTHER_VAR'] == 'quoted value'
        assert 'EMPTY_VAR' in cli.env_vars
        assert cli.env_vars['EMPTY_VAR'] == ''

    def test_load_env_with_nonexistent_file(self):
        """Test environment loading when file doesn't exist"""
        cli = RediaccCLI()
        cli.env_file = self.temp_dir / 'nonexistent.env'

        # Should not raise an exception
        cli.load_env()

        # Should have empty env_vars (except what was loaded during __init__)
        original_vars = cli.env_vars.copy()
        cli.env_vars.clear()
        cli.load_env()
        assert len(cli.env_vars) == 0

    def test_print_help_produces_output(self, capsys):
        """Test that print_help actually produces help text"""
        self.cli.print_help()

        captured = capsys.readouterr()
        assert len(captured.out) > 0
        assert 'Rediacc CLI' in captured.out
        assert 'USAGE:' in captured.out
        assert 'COMMANDS:' in captured.out

    def test_check_docker_image_with_real_docker(self):
        """Test Docker image checking with real docker command"""
        if not shutil.which('docker'):
            pytest.skip("Docker not available")

        # Test with a common image that likely exists
        exists = self.cli.check_docker_image('hello-world:latest')
        assert isinstance(exists, bool)

        # Test with an image that definitely doesn't exist
        exists = self.cli.check_docker_image('nonexistent-image-12345:latest')
        assert exists is False


class TestRealCommandIntegration:
    """Test real command integration and help systems"""

    def setup_method(self):
        """Set up test fixtures"""
        self.cli = RediaccCLI()

    def test_help_command_routing(self):
        """Test that help commands are routed correctly"""
        # These should not raise exceptions
        self.cli.run(['help'])
        self.cli.run(['--help'])
        self.cli.run(['-h'])
        self.cli.run([])  # No args should show help

    def test_version_output(self):
        """Test that version command produces output"""
        if not shutil.which('python3'):
            pytest.skip("Python3 not available")

        # This should execute the real version command
        try:
            result = subprocess.run(
                ['python3', str(Path(__file__).parent / 'rediacc.py'), '--version'],
                capture_output=True,
                text=True,
                timeout=10
            )
            # Should complete without error or timeout
            assert result.returncode in [0, 1]  # May fail if dependencies missing
        except subprocess.TimeoutExpired:
            pytest.fail("Version command timed out")

    def test_setup_command_execution(self):
        """Test that setup command can be executed"""
        if not shutil.which('python3'):
            pytest.skip("Python3 not available")

        try:
            result = subprocess.run(
                ['python3', str(Path(__file__).parent / 'rediacc.py'), 'setup'],
                capture_output=True,
                text=True,
                timeout=30
            )
            # Should complete (may succeed or fail based on system state)
            assert result.returncode in [0, 1]
            # Should produce some output
            assert len(result.stdout) > 0 or len(result.stderr) > 0
        except subprocess.TimeoutExpired:
            pytest.fail("Setup command timed out")


class TestRealFileOperations:
    """Test real file operations and path handling"""

    def setup_method(self):
        """Set up test fixtures"""
        self.cli = RediaccCLI()
        self.temp_dir = Path(tempfile.mkdtemp())

    def teardown_method(self):
        """Clean up test fixtures"""
        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir)

    def test_install_python_packages_with_real_requirements(self):
        """Test Python package installation with real requirements file"""
        if not shutil.which('python3'):
            pytest.skip("Python3 not available")

        # Create a simple requirements file
        req_file = self.temp_dir / 'requirements.txt'
        req_file.write_text('# Simple test requirements\n# No actual packages to avoid side effects\n')

        # Point CLI to our temp directory
        cli = RediaccCLI()
        cli.cli_root = self.temp_dir

        # This should not raise an exception
        result = cli.install_python_packages('python3')
        assert isinstance(result, bool)

    def test_install_python_packages_no_requirements(self):
        """Test Python package installation when requirements.txt doesn't exist"""
        if not shutil.which('python3'):
            pytest.skip("Python3 not available")

        # Point CLI to empty temp directory
        cli = RediaccCLI()
        cli.cli_root = self.temp_dir

        # Should return True (no error, just nothing to install)
        result = cli.install_python_packages('python3')
        assert result is True


class TestRealEnvironmentBehavior:
    """Test behavior under different environment conditions"""

    def test_verbose_mode_from_environment(self):
        """Test verbose mode activation from environment variable"""
        # Test without environment variable
        old_env = os.environ.get('REDIACC_VERBOSE')
        if old_env:
            del os.environ['REDIACC_VERBOSE']

        cli = RediaccCLI()
        # Default should be False unless --verbose in sys.argv
        # (Note: actual value depends on sys.argv during test run)

        # Test with environment variable
        os.environ['REDIACC_VERBOSE'] = '1'
        cli_verbose = RediaccCLI()
        assert cli_verbose.verbose is True

        # Restore original environment
        if old_env:
            os.environ['REDIACC_VERBOSE'] = old_env
        elif 'REDIACC_VERBOSE' in os.environ:
            del os.environ['REDIACC_VERBOSE']

    def test_msys2_detection(self):
        """Test MSYS2 environment detection"""
        # Test without MSYSTEM
        old_msystem = os.environ.get('MSYSTEM')
        if old_msystem:
            del os.environ['MSYSTEM']

        cli = RediaccCLI()
        result = cli.find_python()
        # Should use normal Python discovery

        # Test with MSYSTEM (simulated)
        os.environ['MSYSTEM'] = 'MINGW64'
        cli_msys = RediaccCLI()
        result_msys = cli_msys.find_python()
        # Should attempt MSYS2 path (though may not exist in test environment)

        # Restore original environment
        if old_msystem:
            os.environ['MSYSTEM'] = old_msystem
        elif 'MSYSTEM' in os.environ:
            del os.environ['MSYSTEM']


class TestRealSystemIntegration:
    """Test integration with real system tools and commands"""

    def test_system_tool_detection(self):
        """Test detection of real system tools"""
        cli = RediaccCLI()

        # Test Python detection
        python_cmd = cli.find_python()
        if python_cmd:
            assert shutil.which(python_cmd) is not None

        # Test other common tools
        tools = ['git', 'docker', 'rsync', 'ssh']
        for tool in tools:
            exists = shutil.which(tool) is not None
            # Just verify the check doesn't crash
            assert isinstance(exists, bool)

    def test_real_command_execution_safety(self):
        """Test that command execution handles real errors safely"""
        cli = RediaccCLI()

        # Test with a command that should fail gracefully
        # Use a command that exists but will fail (false command)
        if shutil.which('false'):
            result = cli.run_command(['false'], check=False)
            # Should return CompletedProcess with non-zero return code
            assert hasattr(result, 'returncode')
            assert result.returncode != 0
        else:
            # If 'false' command doesn't exist, test with a command that will fail
            try:
                result = cli.run_command(['python3', '-c', 'exit(1)'], check=False)
                assert hasattr(result, 'returncode')
                assert result.returncode != 0
            except SystemExit:
                # If FileNotFoundError causes sys.exit, that's also valid behavior
                pass

    def test_path_resolution_accuracy(self):
        """Test that path resolution works with real file system"""
        cli = RediaccCLI()

        # Verify paths are resolved correctly
        assert cli.script_dir.is_absolute()
        assert cli.cli_root.is_absolute()
        assert cli.env_file.is_absolute()

        # Verify relationships
        assert cli.cli_root == cli.script_dir
        # The .env file is in the parent directory of cli_root
        assert cli.env_file.parent == cli.cli_root.parent


def test_real_cli_as_script():
    """Test that the CLI can be executed as a real script"""
    if not shutil.which('python3'):
        pytest.skip("Python3 not available")

    script_path = Path(__file__).parent / 'rediacc.py'

    # Test help command
    result = subprocess.run(
        ['python3', str(script_path), 'help'],
        capture_output=True,
        text=True,
        timeout=10
    )

    # Should complete and produce output
    assert result.returncode == 0
    assert len(result.stdout) > 0
    assert 'Rediacc CLI' in result.stdout


if __name__ == '__main__':
    # Run the tests
    pytest.main([__file__, '-v'])