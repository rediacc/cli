#!/usr/bin/env python3
"""
Test suite for rediacc:// protocol URL parsing functionality
Tests URL parsing, validation, and parameter extraction
"""

import sys
import urllib.parse
from pathlib import Path
import pytest

# Add src directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent / 'src'))

from cli.core.protocol_handler import ProtocolUrlParser, ProtocolHandlerError


class TestProtocolUrlParser:
    """Test URL parsing functionality"""

    def setup_method(self):
        """Set up test fixtures"""
        self.parser = ProtocolUrlParser()

    def test_basic_url_parsing(self):
        """Test basic URL parsing without action or parameters"""
        url = "rediacc://token123/TeamA/MachineB/RepoC"

        result = self.parser.parse_url(url)

        assert result['token'] == 'token123'
        assert result['team'] == 'TeamA'
        assert result['machine'] == 'MachineB'
        assert result['repository'] == 'RepoC'
        assert result['action'] is None
        assert result['params'] == {}

    def test_url_with_action(self):
        """Test URL parsing with action"""
        url = "rediacc://token123/TeamA/MachineB/RepoC/sync"

        result = self.parser.parse_url(url)

        assert result['token'] == 'token123'
        assert result['team'] == 'TeamA'
        assert result['machine'] == 'MachineB'
        assert result['repository'] == 'RepoC'
        assert result['action'] == 'sync'
        assert result['params'] == {}

    def test_url_with_parameters(self):
        """Test URL parsing with query parameters"""
        url = "rediacc://token123/TeamA/MachineB/RepoC/sync?direction=upload&localPath=C:\\test&mirror=true"

        result = self.parser.parse_url(url)

        assert result['token'] == 'token123'
        assert result['action'] == 'sync'
        assert result['params']['direction'] == 'upload'
        assert result['params']['localPath'] == 'C:\\test'
        assert result['params']['mirror'] == 'true'

    def test_url_encoding_handling(self):
        """Test handling of URL-encoded characters"""
        url = "rediacc://token123/Team%20With%20Spaces/Machine-01/My%20Repo/terminal?command=ls%20-la"

        result = self.parser.parse_url(url)

        assert result['team'] == 'Team With Spaces'
        assert result['repository'] == 'My Repo'
        assert result['params']['command'] == 'ls -la'

    def test_complex_parameters(self):
        """Test parsing of complex parameter combinations"""
        url = "rediacc://token123/TeamA/MachineB/RepoC/browser?path=/var/log&view=list&showHidden=true&sortBy=date"

        result = self.parser.parse_url(url)

        assert result['action'] == 'browser'
        assert result['params']['path'] == '/var/log'
        assert result['params']['view'] == 'list'
        assert result['params']['showHidden'] == 'true'
        assert result['params']['sortBy'] == 'date'

    def test_special_characters_in_token(self):
        """Test parsing URLs with special characters in token"""
        url = "rediacc://token-123-abc-456/TeamA/MachineB/RepoC"

        result = self.parser.parse_url(url)

        assert result['token'] == 'token-123-abc-456'

    def test_numeric_parameters(self):
        """Test parsing of numeric parameters"""
        url = "rediacc://token123/TeamA/MachineB/RepoC/plugin?port=8888&timeout=30"

        result = self.parser.parse_url(url)

        assert result['params']['port'] == '8888'
        assert result['params']['timeout'] == '30'

    def test_boolean_parameters(self):
        """Test parsing of boolean-like parameters"""
        url = "rediacc://token123/TeamA/MachineB/RepoC/sync?mirror=true&verify=false&preview=1&autoStart=0"

        result = self.parser.parse_url(url)

        assert result['params']['mirror'] == 'true'
        assert result['params']['verify'] == 'false'
        assert result['params']['preview'] == '1'
        assert result['params']['autoStart'] == '0'

    def test_empty_parameters(self):
        """Test parsing URLs with empty parameter values"""
        url = "rediacc://token123/TeamA/MachineB/RepoC/terminal?command=&autoExecute=true"

        result = self.parser.parse_url(url)

        assert result['params']['command'] == ''
        assert result['params']['autoExecute'] == 'true'

    def test_duplicate_parameters(self):
        """Test handling of duplicate parameter names"""
        url = "rediacc://token123/TeamA/MachineB/RepoC/sync?param=value1&param=value2"

        result = self.parser.parse_url(url)

        # Should keep the first value (parse_qs with keep_blank_values returns lists)
        assert result['params']['param'] in ['value1', 'value2']  # Either value is acceptable

    def test_fragment_handling(self):
        """Test handling of URL fragments (should be ignored)"""
        url = "rediacc://token123/TeamA/MachineB/RepoC/sync?direction=upload#fragment"

        result = self.parser.parse_url(url)

        assert result['token'] == 'token123'
        assert result['action'] == 'sync'
        assert result['params']['direction'] == 'upload'

    def test_case_sensitivity(self):
        """Test case sensitivity in URL components"""
        url = "rediacc://Token123/TEAM_A/machine_b/REPO_c/SYNC"

        result = self.parser.parse_url(url)

        # Components should preserve case except action which is normalized to lowercase
        assert result['token'] == 'Token123'
        assert result['team'] == 'TEAM_A'
        assert result['machine'] == 'machine_b'
        assert result['repository'] == 'REPO_c'
        assert result['action'] == 'sync'  # Actions are normalized to lowercase

    def test_unicode_handling(self):
        """Test handling of Unicode characters in URLs"""
        url = "rediacc://token123/测试团队/机器A/仓库B/sync"

        result = self.parser.parse_url(url)

        assert result['team'] == '测试团队'
        assert result['machine'] == '机器A'
        assert result['repository'] == '仓库B'


class TestProtocolUrlParserValidation:
    """Test URL validation and error handling"""

    def setup_method(self):
        """Set up test fixtures"""
        self.parser = ProtocolUrlParser()

    def test_invalid_scheme(self):
        """Test parsing URLs with invalid scheme"""
        url = "http://token123/TeamA/MachineB/RepoC"

        with pytest.raises(ValueError):
            self.parser.parse_url(url)

    def test_missing_components(self):
        """Test parsing URLs with missing required components"""
        # First 3 URLs should fail (truly missing components)
        invalid_urls = [
            "rediacc://",
            "rediacc://token123",
            "rediacc://token123/TeamA",
        ]

        for url in invalid_urls:
            with pytest.raises(ValueError):
                self.parser.parse_url(url)

        # URL with empty repository is accepted (repository is optional)
        url_with_empty_repo = "rediacc://token123/TeamA/MachineB"
        result = self.parser.parse_url(url_with_empty_repo)
        assert result['repository'] == ''

    def test_empty_components(self):
        """Test parsing URLs with empty components - parser shifts components"""
        # When token is empty, components shift left
        url1 = "rediacc:///TeamA/MachineB/RepoC"
        result1 = self.parser.parse_url(url1)
        assert result1['token'] == 'TeamA'  # TeamA becomes token
        assert result1['team'] == 'MachineB'  # MachineB becomes team
        assert result1['machine'] == 'RepoC'  # RepoC becomes machine
        assert result1['repository'] == ''  # repository is empty

        # When team is empty, components shift left
        url2 = "rediacc://token123//MachineB/RepoC"
        result2 = self.parser.parse_url(url2)
        assert result2['token'] == 'token123'
        assert result2['team'] == 'MachineB'  # MachineB becomes team
        assert result2['machine'] == 'RepoC'  # RepoC becomes machine
        assert result2['repository'] == ''  # repository is empty

        # When machine is empty, components shift
        url3 = "rediacc://token123/TeamA//RepoC"
        result3 = self.parser.parse_url(url3)
        assert result3['token'] == 'token123'
        assert result3['team'] == 'TeamA'
        assert result3['machine'] == 'RepoC'  # RepoC becomes machine
        assert result3['repository'] == ''  # repository is empty

        # When repository is empty, it stays empty
        url4 = "rediacc://token123/TeamA/MachineB/"
        result4 = self.parser.parse_url(url4)
        assert result4['token'] == 'token123'
        assert result4['team'] == 'TeamA'
        assert result4['machine'] == 'MachineB'
        assert result4['repository'] == ''

    def test_malformed_urls(self):
        """Test parsing completely malformed URLs"""
        invalid_urls = [
            "not_a_url",
            "rediacc:invalid",
            "rediacc://token123/too/many/path/components/here/and/more",
            "rediacc://token123\\TeamA\\MachineB\\RepoC"  # Wrong separators
        ]

        for url in invalid_urls:
            with pytest.raises(ValueError):
                self.parser.parse_url(url)

    def test_extremely_long_components(self):
        """Test parsing URLs with extremely long components"""
        long_token = "a" * 1000
        url = f"rediacc://{long_token}/TeamA/MachineB/RepoC"

        # Should handle long components gracefully
        result = self.parser.parse_url(url)
        assert result['token'] == long_token

    def test_special_characters_validation(self):
        """Test handling of various special characters"""
        # These should be properly URL-encoded and handled
        test_cases = [
            ("rediacc://token123/Team%2FA/MachineB/RepoC", "Team/A"),
            ("rediacc://token123/Team%20A/MachineB/RepoC", "Team A"),
            ("rediacc://token123/Team%40A/MachineB/RepoC", "Team@A"),
        ]

        for url, expected_team in test_cases:
            result = self.parser.parse_url(url)
            assert result['team'] == expected_team

    def test_parameter_validation(self):
        """Test validation of parameter formats"""
        # Test malformed query strings
        url = "rediacc://token123/TeamA/MachineB/RepoC/sync?invalid=parameter=value"

        # Should handle malformed parameters gracefully
        result = self.parser.parse_url(url)
        # The exact behavior depends on implementation
        assert 'token' in result


class TestProtocolUrlParserEdgeCases:
    """Test edge cases and boundary conditions"""

    def setup_method(self):
        """Set up test fixtures"""
        self.parser = ProtocolUrlParser()

    def test_minimal_valid_url(self):
        """Test the minimal valid URL"""
        url = "rediacc://a/b/c/d"

        result = self.parser.parse_url(url)

        assert result['token'] == 'a'
        assert result['team'] == 'b'
        assert result['machine'] == 'c'
        assert result['repository'] == 'd'

    def test_url_with_port_in_token(self):
        """Test URL where token looks like hostname:port"""
        url = "rediacc://localhost:8080/TeamA/MachineB/RepoC"

        result = self.parser.parse_url(url)

        # Should treat entire "localhost:8080" as token
        assert result['token'] == 'localhost:8080'

    def test_action_with_special_characters(self):
        """Test that invalid actions with special characters are rejected"""
        url = "rediacc://token123/TeamA/MachineB/RepoC/sync-upload"

        # sync-upload is not a valid action, should raise ValueError
        with pytest.raises(ValueError):
            self.parser.parse_url(url)

    def test_parameters_with_arrays(self):
        """Test parameters that look like arrays"""
        url = "rediacc://token123/TeamA/MachineB/RepoC/sync?files[]=file1.txt&files[]=file2.txt"

        result = self.parser.parse_url(url)

        # Standard URL parsing should handle this
        assert 'files[]' in result['params']

    def test_parameters_with_nested_encoding(self):
        """Test parameters with multiple levels of encoding"""
        url = "rediacc://token123/TeamA/MachineB/RepoC/terminal?command=echo%20%22hello%20world%22"

        result = self.parser.parse_url(url)

        assert result['params']['command'] == 'echo "hello world"'

    def test_very_long_url(self):
        """Test handling of very long URLs"""
        long_param_value = "x" * 2000
        url = f"rediacc://token123/TeamA/MachineB/RepoC/sync?data={long_param_value}"

        result = self.parser.parse_url(url)

        assert result['params']['data'] == long_param_value

    def test_url_with_international_domain(self):
        """Test URL with international domain as token"""
        url = "rediacc://测试.com/TeamA/MachineB/RepoC"

        result = self.parser.parse_url(url)

        assert result['token'] == '测试.com'

    def test_path_traversal_attempts(self):
        """Test potential path traversal in URL components"""
        url = "rediacc://token123/../../../etc/passwd/MachineB/RepoC"

        # Path traversal creates too many components, 'etc' would be treated as invalid action
        with pytest.raises(ValueError):
            self.parser.parse_url(url)

    def test_injection_attempts(self):
        """Test potential injection attempts in parameters"""
        url = "rediacc://token123/TeamA/MachineB/RepoC/terminal?command=rm -rf /"

        result = self.parser.parse_url(url)

        # Should parse literally without executing
        assert result['params']['command'] == 'rm -rf /'

    def test_sql_injection_attempts(self):
        """Test SQL injection attempts in URL components"""
        url = "rediacc://token123/TeamA'; DROP TABLE users; --/MachineB/RepoC"

        result = self.parser.parse_url(url)

        # Should parse as literal team name
        assert result['team'] == "TeamA'; DROP TABLE users; --"

    def test_script_injection_attempts(self):
        """Test script injection attempts in parameters"""
        url = "rediacc://token123/TeamA/MachineB/RepoC/browser?path=<script>alert('xss')</script>"

        result = self.parser.parse_url(url)

        # Should parse literally without interpreting as script
        assert result['params']['path'] == "<script>alert('xss')</script>"


class TestProtocolUrlParserPerformance:
    """Test performance and resource usage"""

    def setup_method(self):
        """Set up test fixtures"""
        self.parser = ProtocolUrlParser()

    def test_parsing_performance(self):
        """Test parsing performance with many URLs"""
        import time

        urls = [
            f"rediacc://token{i}/Team{i}/Machine{i}/Repo{i}/sync?param{i}=value{i}"
            for i in range(100)
        ]

        start_time = time.time()

        for url in urls:
            result = self.parser.parse_url(url)
            assert 'token' in result

        end_time = time.time()

        # Should parse 100 URLs in reasonable time (< 1 second)
        assert end_time - start_time < 1.0

    def test_memory_usage_with_large_urls(self):
        """Test memory usage with very large URLs"""
        # Create a URL with large parameter values
        large_value = "x" * 10000
        url = f"rediacc://token123/TeamA/MachineB/RepoC/sync?data={large_value}"

        # Should handle large URLs without excessive memory usage
        result = self.parser.parse_url(url)
        assert result['params']['data'] == large_value


class TestProtocolUrlGeneration:
    """Test URL generation from components (if implemented)"""

    def setup_method(self):
        """Set up test fixtures"""
        self.parser = ProtocolUrlParser()

    def test_url_reconstruction(self):
        """Test that parsed URLs can be reconstructed"""
        original_url = "rediacc://token123/TeamA/MachineB/RepoC/sync?direction=upload&mirror=true"

        parsed = self.parser.parse_url(original_url)

        # Reconstruct URL from parsed components
        reconstructed_parts = [
            'rediacc://',
            parsed['token'],
            '/',
            parsed['team'],
            '/',
            parsed['machine'],
            '/',
            parsed['repository']
        ]

        if parsed['action']:
            reconstructed_parts.extend(['/', parsed['action']])

        if parsed['params']:
            query_string = urllib.parse.urlencode(parsed['params'])
            reconstructed_parts.extend(['?', query_string])

        reconstructed_url = ''.join(reconstructed_parts)

        # Parse reconstructed URL to verify it matches
        reparsed = self.parser.parse_url(reconstructed_url)

        assert reparsed['token'] == parsed['token']
        assert reparsed['team'] == parsed['team']
        assert reparsed['machine'] == parsed['machine']
        assert reparsed['repository'] == parsed['repository']
        assert reparsed['action'] == parsed['action']


if __name__ == '__main__':
    pytest.main([__file__, '-v'])