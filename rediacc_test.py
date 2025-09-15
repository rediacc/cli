#!/usr/bin/env python3
"""
Comprehensive test suite for rediacc.py CLI wrapper
Tests the main RediaccCLI class and its functionality
"""

import sys
import os
import unittest
from unittest.mock import Mock, patch, mock_open, call, MagicMock
from pathlib import Path
import subprocess
import pytest
import tempfile
import shutil

# Add the current directory to Python path so we can import rediacc
sys.path.insert(0, str(Path(__file__).parent))

# Import the module under test
from rediacc import RediaccCLI, Colors, main


class TestColors:
    """Test the Colors utility class"""

    def test_colors_enabled_by_default(self):
        """Test that colors are enabled by default when stdout is a tty"""
        # Reset colors first in case they were disabled by another test
        Colors.RED = '\033[0;31m'
        Colors.GREEN = '\033[0;32m'
        Colors.NC = '\033[0m'

        # Colors should have ANSI codes
        assert Colors.RED == '\033[0;31m'
        assert Colors.GREEN == '\033[0;32m'
        assert Colors.NC == '\033[0m'

    def test_colors_disable(self):
        """Test that colors can be disabled"""
        Colors.disable()
        assert Colors.RED == ''
        assert Colors.GREEN == ''
        assert Colors.NC == ''

        # Reset for other tests
        Colors.RED = '\033[0;31m'
        Colors.GREEN = '\033[0;32m'
        Colors.NC = '\033[0m'


class TestRediaccCLI:
    """Test the main RediaccCLI class"""

    def setup_method(self):
        """Set up test fixtures before each test"""
        self.test_dir = Path(__file__).parent
        self.cli = RediaccCLI()

    def test_init_basic(self):
        """Test basic initialization"""
        assert isinstance(self.cli.script_dir, Path)
        assert self.cli.cli_root == self.cli.script_dir
        assert self.cli.env_file == self.cli.script_dir.parent / '.env'
        assert self.cli.config_dir == self.cli.cli_root / '.config'
        assert self.cli.python_cmd is None
        assert isinstance(self.cli.verbose, bool)
        assert isinstance(self.cli.env_vars, dict)

    @patch.dict(os.environ, {'REDIACC_VERBOSE': '1'})
    def test_init_with_verbose_env(self):
        """Test initialization with verbose environment variable"""
        cli = RediaccCLI()
        assert cli.verbose is True

    @patch('sys.argv', ['rediacc.py', '--verbose'])
    def test_init_with_verbose_arg(self):
        """Test initialization with verbose command line argument"""
        cli = RediaccCLI()
        assert cli.verbose is True

    def test_load_env_success(self):
        """Test successful environment loading"""
        with patch('builtins.open', mock_open(read_data='TEST_VAR=test_value\nANOTHER_VAR="quoted value"\n# Comment line\n\n')):
            with patch.object(Path, 'exists', return_value=True):
                cli = RediaccCLI()
                cli.load_env()

                assert 'TEST_VAR' in cli.env_vars
                assert cli.env_vars['TEST_VAR'] == 'test_value'
                assert 'ANOTHER_VAR' in cli.env_vars
                assert cli.env_vars['ANOTHER_VAR'] == 'quoted value'

    def test_load_env_no_file(self):
        """Test environment loading when .env file doesn't exist"""
        with patch.object(Path, 'exists', return_value=False):
            cli = RediaccCLI()
            # Should not raise an exception
            cli.load_env()
            assert len(cli.env_vars) == 0

    @patch('shutil.which')
    @patch('subprocess.run')
    def test_find_python_python3_success(self, mock_run, mock_which):
        """Test finding Python 3 successfully"""
        mock_which.side_effect = lambda cmd: '/usr/bin/python3' if cmd == 'python3' else None
        mock_run.return_value = subprocess.CompletedProcess(
            args=['python3', '--version'],
            returncode=0,
            stdout='Python 3.9.0'
        )

        result = self.cli.find_python()
        assert result == 'python3'

    @patch('shutil.which')
    @patch('subprocess.run')
    def test_find_python_fallback_to_python(self, mock_run, mock_which):
        """Test falling back to 'python' command"""
        mock_which.side_effect = lambda cmd: '/usr/bin/python' if cmd == 'python' else None
        mock_run.return_value = subprocess.CompletedProcess(
            args=['python', '--version'],
            returncode=0,
            stdout='Python 3.8.0'
        )

        result = self.cli.find_python()
        assert result == 'python'

    @patch('shutil.which', return_value=None)
    def test_find_python_not_found(self, mock_which):
        """Test when Python is not found"""
        result = self.cli.find_python()
        assert result is None

    @patch.dict(os.environ, {'MSYSTEM': 'MINGW64'})
    @patch('shutil.which')
    def test_find_python_msys2(self, mock_which):
        """Test finding Python in MSYS2 environment"""
        mock_which.side_effect = lambda cmd: '/mingw64/bin/python3' if cmd == '/mingw64/bin/python3' else None

        result = self.cli.find_python()
        assert result == '/mingw64/bin/python3'

    @patch.object(RediaccCLI, 'find_python', return_value='python3')
    def test_get_python_command_success(self, mock_find):
        """Test getting Python command successfully"""
        result = self.cli.get_python_command()
        assert result == 'python3'
        assert self.cli.python_cmd == 'python3'

    @patch.object(RediaccCLI, 'find_python', return_value=None)
    def test_get_python_command_not_found(self, mock_find):
        """Test getting Python command when not found"""
        with pytest.raises(SystemExit) as exc_info:
            self.cli.get_python_command()
        assert exc_info.value.code == 1

    @patch('subprocess.run')
    def test_run_command_success(self, mock_run):
        """Test successful command execution"""
        mock_run.return_value = subprocess.CompletedProcess(
            args=['echo', 'test'],
            returncode=0
        )

        result = self.cli.run_command(['echo', 'test'])
        assert result.returncode == 0
        mock_run.assert_called_once_with(['echo', 'test'], check=True)

    @patch('subprocess.run')
    def test_run_command_failure_with_check(self, mock_run):
        """Test command execution failure with check=True"""
        mock_run.side_effect = subprocess.CalledProcessError(1, ['false'])

        with pytest.raises(SystemExit) as exc_info:
            self.cli.run_command(['false'])
        assert exc_info.value.code == 1

    @patch('subprocess.run')
    def test_run_command_failure_without_check(self, mock_run):
        """Test command execution failure with check=False"""
        error = subprocess.CalledProcessError(1, ['false'])
        mock_run.side_effect = error

        result = self.cli.run_command(['false'], check=False)
        assert result == error

    @patch('subprocess.run')
    def test_run_command_not_found(self, mock_run):
        """Test command not found error"""
        mock_run.side_effect = FileNotFoundError()

        with pytest.raises(SystemExit) as exc_info:
            self.cli.run_command(['nonexistent_command'])
        assert exc_info.value.code == 1

    @patch.object(RediaccCLI, 'run_command')
    @patch.object(Path, 'exists', return_value=True)
    def test_install_python_packages_success(self, mock_exists, mock_run_cmd):
        """Test successful Python package installation"""
        mock_run_cmd.return_value = subprocess.CompletedProcess([], 0)

        result = self.cli.install_python_packages('python3')
        assert result is True

        # Should call pip upgrade and requirements install
        assert mock_run_cmd.call_count == 2

    @patch.object(RediaccCLI, 'run_command')
    @patch.object(Path, 'exists', return_value=False)
    def test_install_python_packages_no_requirements(self, mock_exists, mock_run_cmd):
        """Test package installation when requirements.txt doesn't exist"""
        result = self.cli.install_python_packages('python3')
        assert result is True
        mock_run_cmd.assert_not_called()

    @patch.object(RediaccCLI, 'run_command')
    @patch.object(Path, 'exists', return_value=True)
    def test_install_python_packages_failure(self, mock_exists, mock_run_cmd):
        """Test Python package installation failure"""
        # pip upgrade succeeds, requirements install fails
        mock_run_cmd.side_effect = [
            subprocess.CompletedProcess([], 0),  # pip upgrade
            subprocess.CompletedProcess([], 1)   # requirements install
        ]

        result = self.cli.install_python_packages('python3')
        assert result is False

    @patch('builtins.print')
    @patch.object(RediaccCLI, 'install_python_packages', return_value=True)
    @patch.object(RediaccCLI, 'find_python', return_value='python3')
    @patch('subprocess.run')
    @patch('shutil.which')
    def test_cmd_setup_complete_success(self, mock_which, mock_subprocess, mock_find, mock_install, mock_print):
        """Test complete successful setup"""
        # Mock all dependencies as available
        mock_which.side_effect = lambda cmd: f'/usr/bin/{cmd}' if cmd in ['rsync', 'ssh'] else None
        mock_subprocess.side_effect = [
            subprocess.CompletedProcess([], 0, stdout='3.9'),  # Python version
            subprocess.CompletedProcess([], 0)  # tkinter check
        ]

        self.cli.cmd_setup([])

        # Verify setup checks were performed
        mock_find.assert_called_once()
        mock_install.assert_called_once_with('python3')

    @patch('builtins.print')
    @patch.object(RediaccCLI, 'find_python', return_value=None)
    def test_cmd_setup_python_not_found(self, mock_find, mock_print):
        """Test setup when Python is not found"""
        with pytest.raises(SystemExit) as exc_info:
            self.cli.cmd_setup([])
        assert exc_info.value.code == 1

    @patch('os.chdir')
    @patch.object(RediaccCLI, 'get_python_command', return_value='python3')
    @patch.object(RediaccCLI, 'run_command')
    def test_cmd_test_no_args(self, mock_run_cmd, mock_get_python, mock_chdir):
        """Test running all tests with no arguments"""
        self.cli.cmd_test([])

        mock_chdir.assert_called_once_with(self.cli.cli_root)
        mock_run_cmd.assert_called_once_with(['python3', '-m', 'pytest', 'tests/', '-v'])

    @patch('os.chdir')
    @patch.object(RediaccCLI, 'get_python_command', return_value='python3')
    @patch.object(RediaccCLI, 'run_command')
    def test_cmd_test_desktop(self, mock_run_cmd, mock_get_python, mock_chdir):
        """Test running desktop tests"""
        self.cli.cmd_test(['desktop'])

        mock_run_cmd.assert_called_once_with(['python3', '-m', 'pytest', 'tests/gui/', '-v'])

    @patch('os.chdir')
    @patch.object(RediaccCLI, 'get_python_command', return_value='python3')
    @patch.object(RediaccCLI, 'run_command')
    def test_cmd_test_yaml(self, mock_run_cmd, mock_get_python, mock_chdir):
        """Test running YAML tests"""
        self.cli.cmd_test(['yaml'])

        mock_run_cmd.assert_called_once_with(['python3', 'tests/run_tests.py'])

    def test_cmd_release(self):
        """Test release creation"""
        with patch('builtins.print'):
            with patch.object(RediaccCLI, 'run_command') as mock_run_cmd:
                with patch('shutil.rmtree'):
                    with patch('shutil.copytree'):
                        with patch('shutil.copy2'):
                            with patch.object(Path, 'exists', return_value=True):
                                with patch.object(Path, 'mkdir'):
                                    with patch('builtins.open', mock_open()):
                                        with patch('json.dump'):
                                            self.cli.cmd_release([])

                                            # Verify tar creation command was called
                                            mock_run_cmd.assert_called_once()
                                            called_args = mock_run_cmd.call_args[0][0]
                                            assert called_args[0] == 'tar'
                                            assert '-czf' in called_args

    @patch('builtins.print')
    @patch.object(RediaccCLI, 'run_command')
    def test_cmd_docker_build_success(self, mock_run_cmd, mock_print):
        """Test Docker build success"""
        mock_run_cmd.return_value = subprocess.CompletedProcess([], 0)

        self.cli.cmd_docker_build([])

        # Verify docker build command was called
        mock_run_cmd.assert_called_once()
        called_args = mock_run_cmd.call_args[0][0]
        assert called_args[0] == 'docker'
        assert called_args[1] == 'build'
        assert 'rediacc:latest' in called_args

    @patch('builtins.print')
    @patch.object(RediaccCLI, 'run_command')
    def test_cmd_docker_build_failure(self, mock_run_cmd, mock_print):
        """Test Docker build failure"""
        mock_run_cmd.return_value = subprocess.CompletedProcess([], 1)

        with pytest.raises(SystemExit) as exc_info:
            self.cli.cmd_docker_build([])
        assert exc_info.value.code == 1

    @patch('subprocess.run')
    def test_check_docker_image_exists(self, mock_run):
        """Test checking if Docker image exists"""
        mock_run.return_value = subprocess.CompletedProcess([], 0, stdout='abc123\n')

        result = self.cli.check_docker_image('test:latest')
        assert result is True

    @patch('subprocess.run')
    def test_check_docker_image_not_exists(self, mock_run):
        """Test checking if Docker image doesn't exist"""
        mock_run.return_value = subprocess.CompletedProcess([], 0, stdout='')

        result = self.cli.check_docker_image('test:latest')
        assert result is False

    @patch.object(RediaccCLI, 'check_docker_image', return_value=False)
    @patch.object(RediaccCLI, 'cmd_docker_build')
    @patch.object(RediaccCLI, 'run_command')
    @patch.object(Path, 'exists', return_value=True)
    @patch('os.getcwd', return_value='/test/dir')
    @patch('os.getpid', return_value=12345)
    def test_cmd_docker_run_build_if_needed(self, mock_getpid, mock_getcwd, mock_exists,
                                           mock_run_cmd, mock_docker_build, mock_check_image):
        """Test Docker run builds image if needed"""
        self.cli.cmd_docker_run([])

        # Should build image first
        mock_docker_build.assert_called_once_with([])

        # Should run docker command
        mock_run_cmd.assert_called_once()
        called_args = mock_run_cmd.call_args[0][0]
        assert called_args[0] == 'docker'
        assert called_args[1] == 'run'
        assert 'rediacc:latest' in called_args

    @patch('builtins.print')
    @patch.object(RediaccCLI, 'get_python_command', return_value='python3')
    @patch('subprocess.run')
    def test_cmd_desktop_tkinter_not_found(self, mock_subprocess, mock_get_python, mock_print):
        """Test desktop command when tkinter is not available"""
        mock_subprocess.return_value = subprocess.CompletedProcess([], 1)  # tkinter check fails

        with pytest.raises(SystemExit) as exc_info:
            self.cli.cmd_desktop([])
        assert exc_info.value.code == 1

    @patch('builtins.print')
    @patch.object(RediaccCLI, 'get_python_command', return_value='python3')
    @patch.object(RediaccCLI, 'run_command')
    @patch('subprocess.run')
    def test_cmd_desktop_success(self, mock_subprocess, mock_run_cmd, mock_get_python, mock_print):
        """Test successful desktop command"""
        mock_subprocess.return_value = subprocess.CompletedProcess([], 0)  # tkinter check succeeds

        self.cli.cmd_desktop([])

        mock_run_cmd.assert_called_once()
        called_args = mock_run_cmd.call_args[0][0]
        assert called_args[0] == 'python3'
        assert 'gui/main.py' in called_args[1]

    @patch.object(RediaccCLI, 'cmd_desktop_docker')
    def test_cmd_desktop_docker_mode(self, mock_desktop_docker):
        """Test desktop command with docker mode"""
        self.cli.cmd_desktop(['docker', 'arg1'])

        mock_desktop_docker.assert_called_once_with(['arg1'])

    @patch('builtins.print')
    @patch.object(RediaccCLI, 'check_docker_image', return_value=False)
    @patch.object(RediaccCLI, 'cmd_docker_build')
    @patch.object(RediaccCLI, 'run_command')
    @patch.object(Path, 'exists', return_value=True)
    @patch('os.getcwd', return_value='/test/dir')
    @patch('os.getpid', return_value=12345)
    def test_cmd_docker_shell(self, mock_getpid, mock_getcwd, mock_exists,
                             mock_run_cmd, mock_docker_build, mock_check_image, mock_print):
        """Test Docker shell command"""
        self.cli.cmd_docker_shell([])

        # Should build image first
        mock_docker_build.assert_called_once_with([])

        # Should run docker shell command
        mock_run_cmd.assert_called_once()
        called_args = mock_run_cmd.call_args[0][0]
        assert called_args[0] == 'docker'
        assert called_args[1] == 'run'
        assert '/bin/bash' in called_args

    @patch('builtins.print')
    @patch.object(RediaccCLI, 'run_command')
    def test_cmd_desktop_docker_build(self, mock_run_cmd, mock_print):
        """Test desktop Docker build command"""
        mock_run_cmd.return_value = subprocess.CompletedProcess([], 0)

        self.cli.cmd_desktop_docker_build([])

        # Verify docker build command was called
        mock_run_cmd.assert_called_once()
        called_args = mock_run_cmd.call_args[0][0]
        assert called_args[0] == 'docker'
        assert called_args[1] == 'build'
        assert 'rediacc/cli:latest' in called_args

    @patch('builtins.print')
    @patch.object(RediaccCLI, 'check_docker_image', return_value=True)
    @patch.object(RediaccCLI, 'cmd_desktop_docker_build')
    @patch.object(RediaccCLI, 'run_command')
    @patch.object(Path, 'mkdir')
    @patch.object(Path, 'chmod')
    @patch.object(Path, 'exists', return_value=True)  # Build marker exists
    @patch.object(Path, 'stat')
    @patch.object(Path, 'rglob', return_value=[])  # No source files newer
    @patch.object(Path, 'touch')
    @patch('shutil.copy2')
    @patch('platform.system', return_value='Linux')
    @patch('subprocess.run')
    @patch('os.getpid', return_value=12345)
    def test_cmd_desktop_docker(self, mock_getpid, mock_subprocess, mock_system, mock_copy2,
                               mock_touch, mock_rglob, mock_stat, mock_exists, mock_chmod, mock_mkdir, mock_run_cmd, mock_docker_build, mock_check_image, mock_print):
        """Test desktop Docker run command when image exists and no rebuild needed"""
        self.cli.cmd_desktop_docker([])

        # Should NOT build image since it exists and no rebuild needed
        mock_docker_build.assert_not_called()

        # Should run docker command
        mock_run_cmd.assert_called_once()
        called_args = mock_run_cmd.call_args[0][0]
        assert called_args[0] == 'docker'
        assert called_args[1] == 'run'
        assert 'rediacc/cli:latest' in called_args

    @patch.object(RediaccCLI, 'get_python_command', return_value='python3')
    @patch.object(RediaccCLI, 'run_command')
    def test_cmd_cli_command_basic(self, mock_run_cmd, mock_get_python):
        """Test basic CLI command delegation"""
        self.cli.cmd_cli_command('sync', ['upload', '--help'])

        mock_run_cmd.assert_called_once()
        called_args = mock_run_cmd.call_args[0][0]
        assert called_args[0] == 'python3'
        assert 'sync_main.py' in called_args[1]
        assert called_args[2:] == ['upload', '--help']

    @patch.object(RediaccCLI, 'get_python_command', return_value='python3')
    @patch.object(RediaccCLI, 'run_command')
    def test_cmd_cli_command_with_token_injection_failure(self, mock_run_cmd, mock_get_python):
        """Test CLI command with token injection when import fails"""
        # Test the case where token injection fails (import error)
        self.cli.cmd_cli_command('cli', ['list', 'teams'], inject_token=True)

        mock_run_cmd.assert_called_once()
        called_args = mock_run_cmd.call_args[0][0]
        assert called_args[0] == 'python3'
        # Should fallback to command without token when import fails
        assert 'cli_main.py' in called_args[1]

    def test_print_help(self, capsys):
        """Test help message printing"""
        self.cli.print_help()

        captured = capsys.readouterr()
        assert 'Rediacc CLI and Desktop' in captured.out
        assert 'USAGE:' in captured.out
        assert 'COMMANDS:' in captured.out
        assert 'login' in captured.out
        assert 'sync' in captured.out
        assert 'desktop' in captured.out

    @patch.object(RediaccCLI, 'print_help')
    def test_run_help_commands(self, mock_print_help):
        """Test various help command invocations"""
        test_cases = [[], ['help'], ['--help'], ['-h']]

        for args in test_cases:
            self.cli.run(args)
            mock_print_help.assert_called()
            mock_print_help.reset_mock()

    @patch.object(RediaccCLI, 'cmd_setup')
    def test_run_setup_command(self, mock_cmd_setup):
        """Test setup command routing"""
        self.cli.run(['setup', '--flag'])
        mock_cmd_setup.assert_called_once_with(['--flag'])

    @patch.object(RediaccCLI, 'cmd_test')
    def test_run_test_command(self, mock_cmd_test):
        """Test test command routing"""
        self.cli.run(['test', 'desktop'])
        mock_cmd_test.assert_called_once_with(['desktop'])

    @patch.object(RediaccCLI, 'cmd_cli_command')
    def test_run_login_command(self, mock_cmd_cli):
        """Test login command routing"""
        self.cli.run(['login', '--token', 'xyz'])
        mock_cmd_cli.assert_called_once_with('cli', ['login', '--token', 'xyz'])

    @patch.object(RediaccCLI, 'cmd_cli_command')
    def test_run_sync_command(self, mock_cmd_cli):
        """Test sync command routing"""
        self.cli.run(['sync', 'upload'])
        mock_cmd_cli.assert_called_once_with('sync', ['upload'])

    @patch.object(RediaccCLI, 'cmd_desktop')
    def test_run_deprecated_gui_command(self, mock_cmd_desktop):
        """Test deprecated gui command routing"""
        self.cli.run(['gui'])
        mock_cmd_desktop.assert_called_once_with([])

    @patch.object(RediaccCLI, 'cmd_cli_command')
    def test_run_license_command_with_injection(self, mock_cmd_cli):
        """Test license command routing with token injection"""
        self.cli.run(['license', 'generate-id'])
        mock_cmd_cli.assert_called_once_with('cli', ['license', 'generate-id'], inject_token=True)

    @patch.object(RediaccCLI, 'cmd_cli_command')
    def test_run_unknown_command_passthrough(self, mock_cmd_cli):
        """Test unknown command passthrough with token injection"""
        self.cli.run(['unknown', 'command'])
        mock_cmd_cli.assert_called_once_with('cli', ['unknown', 'command'], inject_token=True)


class TestMainFunction:
    """Test the main entry point function"""

    @patch.object(RediaccCLI, 'run')
    @patch('sys.argv', ['rediacc.py', 'login'])
    def test_main_success(self, mock_run):
        """Test successful main execution"""
        main()
        mock_run.assert_called_once_with(['login'])

    @patch.object(RediaccCLI, 'run')
    @patch('sys.argv', ['rediacc.py'])
    def test_main_keyboard_interrupt(self, mock_run):
        """Test main with keyboard interrupt"""
        mock_run.side_effect = KeyboardInterrupt()

        with pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code == 130

    @patch.object(RediaccCLI, 'run')
    @patch('sys.argv', ['rediacc.py'])
    @patch.dict(os.environ, {}, clear=True)  # Clear REDIACC_DEBUG
    def test_main_exception_no_debug(self, mock_run):
        """Test main with exception when debug is disabled"""
        mock_run.side_effect = Exception("Test error")

        with pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code == 1

    @patch.object(RediaccCLI, 'run')
    @patch('sys.argv', ['rediacc.py'])
    @patch.dict(os.environ, {'REDIACC_DEBUG': '1'})
    @patch('traceback.print_exc')
    def test_main_exception_with_debug(self, mock_traceback, mock_run):
        """Test main with exception when debug is enabled"""
        mock_run.side_effect = Exception("Test error")

        with pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code == 1
        mock_traceback.assert_called_once()


if __name__ == '__main__':
    # Run the tests
    pytest.main([__file__, '-v'])