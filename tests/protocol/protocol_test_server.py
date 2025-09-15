#!/usr/bin/env python3
"""
Protocol Test Web Service

A local web service that provides real Rediacc credentials and can trigger
CLI commands for protocol testing. This allows the HTML test page to use
actual system data instead of hardcoded values.

Endpoints:
- GET /api/credentials - Get current token and system info
- GET /api/teams - List available teams
- GET /api/machines/{team} - List machines for a team
- GET /api/repositories/{team} - List repositories for a team
- POST /api/protocol/test - Test a protocol URL by invoking CLI
- GET /health - Health check
"""

import sys
import os
import json
import subprocess
import tempfile
from pathlib import Path
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs, unquote
from typing import Dict, Any
import threading
import time

# Set full environment for local API before importing client
os.environ.setdefault('SYSTEM_API_URL', 'http://localhost:7322/api')
os.environ.setdefault('SYSTEM_HTTP_PORT', '7322')

# Add src directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent / 'src'))

# Import CLI internal modules for direct API access (avoiding subprocess token rotation issues)
from cli.core.api_client import client
from cli.core.config import TokenManager, get_config_dir, load_config

# Initialize config like the CLI does
try:
    load_config()
except Exception as e:
    print(f"Warning: Could not load CLI config: {e}")
    pass

class ProtocolTestHandler(BaseHTTPRequestHandler):
    """HTTP request handler for protocol testing endpoints"""

    def __init__(self, *args, **kwargs):
        self.cli_root = Path(__file__).parent.parent.parent
        self._api_client = None
        self._super_client = None
        self._token_manager = None
        super().__init__(*args, **kwargs)

    def do_GET(self):
        """Handle GET requests"""
        parsed_path = urlparse(self.path)
        path = parsed_path.path
        query_params = parse_qs(parsed_path.query)

        try:
            if path == '/health':
                self._respond_json({'status': 'healthy', 'service': 'protocol-test-server'})
            elif path == '/api/credentials':
                self._handle_get_credentials()
            elif path == '/api/teams':
                self._handle_get_teams()
            elif path.startswith('/api/machines/'):
                team_name = unquote(path.split('/')[-1])
                self._handle_get_machines(team_name)
            elif path.startswith('/api/repositories/'):
                team_name = unquote(path.split('/')[-1])
                machine_name = query_params.get('machine', [None])[0]
                self._handle_get_repositories(team_name, machine_name)
            elif path == '/':
                self._serve_test_page()
            else:
                self._respond_error(404, 'Endpoint not found')
        except Exception as e:
            self._respond_error(500, f'Server error: {str(e)}')

    def do_POST(self):
        """Handle POST requests"""
        parsed_path = urlparse(self.path)
        path = parsed_path.path

        try:
            if path == '/api/protocol/test':
                self._handle_protocol_test()
            else:
                self._respond_error(404, 'Endpoint not found')
        except Exception as e:
            self._respond_error(500, f'Server error: {str(e)}')

    def do_OPTIONS(self):
        """Handle CORS preflight requests"""
        self._set_cors_headers()
        self.send_response(200)
        self.end_headers()

    def _set_cors_headers(self):
        """Set CORS headers for browser compatibility"""
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')

    def _respond_json(self, data, status_code=200):
        """Send JSON response"""
        self.send_response(status_code)
        self.send_header('Content-Type', 'application/json')
        self._set_cors_headers()
        self.end_headers()

        response = json.dumps(data, indent=2)
        self.wfile.write(response.encode('utf-8'))

    def _respond_error(self, status_code, message):
        """Send error response"""
        self._respond_json({'error': message, 'status': status_code}, status_code)

    def _serve_test_page(self):
        """Serve the HTML test page"""
        html_file = Path(__file__).parent / 'test_protocol_page_dynamic.html'
        if html_file.exists():
            self.send_response(200)
            self.send_header('Content-Type', 'text/html')
            self._set_cors_headers()
            self.end_headers()

            with open(html_file, 'r', encoding='utf-8') as f:
                self.wfile.write(f.read().encode('utf-8'))
        else:
            self._respond_error(404, 'Test page not found')

    def _call_api_directly(self, endpoint: str, data: Dict[str, Any] = None) -> Dict[str, Any]:
        """Call the Rediacc API directly using internal client (handles token rotation automatically)"""
        try:
            # Use the global client - it handles token rotation internally
            response = client.token_request(endpoint, data or {})

            # Check for API errors in response
            if response and 'error' in response:
                return {
                    'success': False,
                    'data': None,
                    'stderr': response.get('error', 'Unknown API error'),
                    'exit_code': response.get('status_code', 1)
                }

            return {
                'success': True,
                'data': response,
                'stderr': '',
                'exit_code': 0
            }
        except Exception as e:
            return {
                'success': False,
                'data': None,
                'stderr': str(e),
                'exit_code': 1
            }

    def _run_cli_command(self, args, env_vars=None):
        """Run CLI command and return result (handles token rotation)"""
        # IMPORTANT: Don't cache credentials! Each CLI call rotates the token,
        # so we must always use the fresh token from the config file.

        # Set up environment for CLI subprocess
        env = os.environ.copy()
        if env_vars:
            env.update(env_vars)

        # Ensure CLI uses local API (read from parent process or default to localhost)
        if 'SYSTEM_API_URL' not in env:
            env['SYSTEM_API_URL'] = 'http://localhost:7322/api'

        cmd = ['python3', str(self.cli_root / 'rediacc.py')] + args

        try:
            # Get token before CLI call (for logging)
            old_config = self._get_fresh_credentials()
            old_token = old_config.get('token', '')[:12] + '...' if old_config.get('token') else 'none'

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                cwd=self.cli_root,
                env=env,
                timeout=30
            )

            # Check if token was rotated after CLI call
            new_config = self._get_fresh_credentials()
            new_token = new_config.get('token', '')[:12] + '...' if new_config.get('token') else 'none'

            if old_token != new_token:
                print(f"🔄 Token rotated: {old_token} → {new_token}")

            return {
                'success': result.returncode == 0,
                'stdout': result.stdout,
                'stderr': result.stderr,
                'exit_code': result.returncode
            }
        except subprocess.TimeoutExpired:
            return {
                'success': False,
                'stdout': '',
                'stderr': 'Command timed out',
                'exit_code': -1
            }
        except Exception as e:
            return {
                'success': False,
                'stdout': '',
                'stderr': str(e),
                'exit_code': -1
            }

    def _get_fresh_credentials(self):
        """Get fresh credentials from config file (handles token rotation)"""
        try:
            config_file = self.cli_root / 'src' / '.config' / 'config.json'
            if config_file.exists():
                with open(config_file, 'r') as f:
                    config = json.load(f)
                return config
            return {}
        except Exception:
            return {}


    def _extract_repositories_from_machines(self, team_name, machine_name=None):
        """Extract repository information from machine status data, optionally filtered by machine"""
        result = self._call_api_directly('GetTeamMachines', {'teamName': team_name})
        repositories = []

        if not result['success']:
            return repositories

        try:
            data = result['data']
            if not (data.get('success') and 'resultSets' in data):
                return repositories

            # Get machines from resultSets
            result_sets = data.get('resultSets', [])
            machines_data = []
            for i, result_set in enumerate(result_sets):
                # Skip token result sets
                if (i == 0 or
                    'TOKEN' in result_set.get('resultSetName', '').upper() or
                    'CREDENTIAL' in result_set.get('resultSetName', '').upper()):
                    continue

                if result_set and result_set.get('data'):
                    machines_data.extend(result_set['data'])

            # Extract repositories from machine vaultStatus
            repo_guids_found = set()
            for machine in machines_data:
                current_machine_name = machine.get('machineName', '')

                # Filter by machine if specified
                if machine_name and current_machine_name != machine_name:
                    continue

                print(f"DEBUG: Processing repositories for machine: {current_machine_name}")
                print(f"DEBUG: Machine data keys for {current_machine_name}: {list(machine.keys())}")
                vault_status = machine.get('vaultStatus', '')
                print(f"DEBUG: VaultStatus length for {current_machine_name}: {len(vault_status) if vault_status else 0}")

                # Also check alternative field names
                for field in ['vaultStatus', 'vault_status', 'status', 'machineStatus']:
                    if field in machine:
                        print(f"DEBUG: Found field '{field}' for {current_machine_name}: {len(str(machine[field])) if machine[field] else 0} chars")
                if vault_status:
                    try:
                        status_data = json.loads(vault_status)
                        print(f"DEBUG: VaultStatus keys for {current_machine_name}: {list(status_data.keys())}")
                        result_str = status_data.get('result', '{}')
                        print(f"DEBUG: Result string length for {current_machine_name}: {len(result_str) if result_str else 0}")
                        if result_str:
                            result_data = json.loads(result_str)
                            print(f"DEBUG: Result data keys for {current_machine_name}: {list(result_data.keys())}")
                            machine_repos = result_data.get('repositories', [])
                            print(f"DEBUG: Found {len(machine_repos)} repositories on machine {current_machine_name}")
                            if machine_repos:
                                print(f"DEBUG: First repository data: {machine_repos[0] if machine_repos else 'None'}")
                            for repo in machine_repos:
                                repo_guid = repo.get('name', '')  # This is actually the GUID
                                if repo_guid:
                                    # Use a key that includes machine name to allow same repo on different machines
                                    repo_key = f"{repo_guid}_{current_machine_name}"
                                    if repo_key not in repo_guids_found:
                                        repo_guids_found.add(repo_key)
                                        repositories.append({
                                            'guid': repo_guid,
                                            'name': repo_guid,  # Will be mapped to human name later
                                            'machine': current_machine_name,
                                            'size': repo.get('size_human', 'Unknown'),
                                            'mounted': repo.get('mounted', False)
                                        })
                                        print(f"DEBUG: Added repository {repo_guid} from machine {current_machine_name}")
                    except (json.JSONDecodeError, KeyError) as e:
                        print(f"DEBUG: Error parsing vaultStatus for machine {current_machine_name}: {e}")
                        continue

        except Exception as e:
            print(f"DEBUG: Error extracting repositories from machines: {e}")

        return repositories

    def _get_repository_name_mapping(self, team_name):
        """Get mapping from repository GUID to human-readable name"""
        try:
            result = self._call_api_directly('GetTeamRepositories', {'teamName': team_name})
            if result['success']:
                data = result['data']
                if 'resultSets' in data and data.get('success'):
                    result_sets = data.get('resultSets', [])
                    for i, result_set in enumerate(result_sets):
                        # Skip token result sets
                        if (i == 0 or
                            'TOKEN' in result_set.get('resultSetName', '').upper() or
                            'CREDENTIAL' in result_set.get('resultSetName', '').upper()):
                            continue

                        if result_set and result_set.get('data'):
                            mapping = {}
                            for repo in result_set['data']:
                                repo_guid = repo.get('repoGuid', '')
                                repo_name = repo.get('repoName', '')
                                if repo_guid and repo_name:
                                    mapping[repo_guid] = repo_name
                            return mapping
        except Exception as e:
            print(f"DEBUG: Error getting repository name mapping: {e}")

        return {}

    def _handle_get_credentials(self):
        """Get current CLI credentials and token"""
        try:
            # Always read fresh config to get latest rotated token
            config = self._get_fresh_credentials()

            # Extract token and basic info
            credentials = {
                'token': config.get('token', ''),
                'email': config.get('email', ''),
                'has_credentials': bool(config.get('token')),
                'token_updated_at': config.get('token_updated_at', ''),
                'api_url': os.environ.get('SYSTEM_API_URL', 'https://www.rediacc.com/api')
            }

            self._respond_json(credentials)

        except Exception as e:
            self._respond_error(500, f'Failed to get credentials: {str(e)}')

    def _handle_get_teams(self):
        """Get list of available teams"""
        result = self._call_api_directly('GetCompanyTeams')

        if result['success']:
            try:
                data = result['data']

                # Check if this is a resultSets format (API response) or simplified format
                if 'resultSets' in data and data.get('success'):
                    # API format: token in [0], data in [1] or later
                    result_sets = data.get('resultSets', [])
                    teams_data = []
                    for i, result_set in enumerate(result_sets):
                        if i == 0:  # Skip token result set
                            continue
                        if result_set and result_set.get('data'):
                            teams_data.extend(result_set['data'])

                    teams = [{'name': team['teamName'], 'machineCount': team['machineCount'], 'repoCount': team['repoCount']}
                            for team in teams_data if team.get('teamName')]

                elif data.get('success') and 'data' in data:
                    # Simplified format
                    teams = [{'name': team['teamName'], 'machineCount': team['machineCount'], 'repoCount': team['repoCount']}
                            for team in data['data']]
                else:
                    self._respond_error(400, data.get('error', 'Failed to get teams'))
                    return

                self._respond_json({'teams': teams})
            except Exception as e:
                self._respond_error(500, f'Error processing teams data: {str(e)}')
        else:
            self._respond_error(500, f'API call failed: {result["stderr"]}')

    def _handle_get_machines(self, team_name):
        """Get list of machines for a team"""
        print(f"DEBUG: Getting machines for team: '{team_name}'")
        result = self._call_api_directly('GetTeamMachines', {'teamName': team_name})

        if result['success']:
            try:
                data = result['data']
                print(f"DEBUG: API response keys: {list(data.keys())}")
                print(f"DEBUG: Success: {data.get('success')}, has resultSets: {'resultSets' in data}, has data: {'data' in data}")
                if 'data' in data:
                    print(f"DEBUG: Data count: {len(data['data']) if data['data'] else 0}")

                # Check if this is a resultSets format (API response) or simplified format
                if 'resultSets' in data and data.get('success'):
                    # API format: token in [0], data in [1]
                    result_sets = data.get('resultSets', [])
                    print(f"DEBUG: Found {len(result_sets)} result sets")

                    machines_data = []
                    for i, result_set in enumerate(result_sets):
                        print(f"DEBUG: ResultSet {i}: {result_set.get('resultSetName', 'unnamed')}, data count: {len(result_set.get('data', []))}")
                        # Skip token result set (index 0, or resultSetName containing TOKEN/CREDENTIAL)
                        if (i == 0 or
                            'TOKEN' in result_set.get('resultSetName', '').upper() or
                            'CREDENTIAL' in result_set.get('resultSetName', '').upper()):
                            continue

                        if result_set and result_set.get('data'):
                            machines_data.extend(result_set['data'])

                    print(f"DEBUG: Total machines data items: {len(machines_data)}")
                    machines = [{'name': machine['machineName'], 'ip': self._extract_machine_ip(machine)}
                               for machine in machines_data if machine.get('machineName')]
                    print(f"DEBUG: Processed machines: {[m['name'] for m in machines]}")

                elif data.get('success') and 'data' in data:
                    # Simplified format
                    print(f"DEBUG: Using simplified format. Data count: {len(data['data'])}")
                    machines = [{'name': machine['machineName'], 'ip': self._extract_machine_ip(machine)}
                               for machine in data['data'] if machine.get('machineName')]
                    print(f"DEBUG: Processed machines from simplified format: {[m['name'] for m in machines]}")
                else:
                    print(f"DEBUG: Unexpected response format: success={data.get('success')}, has_data={'data' in data}")
                    self._respond_error(400, data.get('error', 'Failed to get machines'))
                    return

                self._respond_json({'machines': machines})
            except Exception as e:
                self._respond_error(500, f'Error processing machines data: {str(e)}')
        else:
            print(f"DEBUG: API call failed. Endpoint: GetTeamMachines, Team: {team_name}")
            print(f"DEBUG: Error: {result.get('stderr', '')}")
            self._respond_error(500, f'API call failed: {result["stderr"]}')

    def _handle_get_repositories(self, team_name, machine_name=None):
        """Get list of repositories for a team, optionally filtered by machine"""
        if machine_name:
            print(f"DEBUG: Getting repositories for team: '{team_name}', machine: '{machine_name}' (using cached machine data)")
        else:
            print(f"DEBUG: Getting repositories for team: '{team_name}' (all machines, using cached machine data)")

        try:
            # Extract repositories from cached machine status data
            repositories_from_machines = self._extract_repositories_from_machines(team_name, machine_name)
            print(f"DEBUG: Found {len(repositories_from_machines)} repositories from machine status")

            # Get GUID-to-name mapping from GetTeamRepositories (still needed for human-readable names)
            name_mapping = self._get_repository_name_mapping(team_name)
            print(f"DEBUG: Got name mapping for {len(name_mapping)} repositories")

            # Map GUIDs to human-readable names
            repositories = []
            for repo in repositories_from_machines:
                repo_guid = repo['guid']
                human_name = name_mapping.get(repo_guid, repo_guid)  # Fallback to GUID if no mapping
                repositories.append({
                    'name': human_name,
                    'guid': repo_guid,
                    'machine': repo['machine'],
                    'size': repo['size'],
                    'mounted': repo['mounted']
                })

            print(f"DEBUG: Processed repositories: {[r['name'] for r in repositories]}")

            # Return only repositories found on the specified machine (or all machines if no machine specified)
            if machine_name and not repositories:
                print(f"DEBUG: No repositories found on machine '{machine_name}'")
            elif not repositories:
                print("DEBUG: No repositories found in any machine status")

            self._respond_json({'repositories': repositories})

        except Exception as e:
            print(f"DEBUG: Error in _handle_get_repositories: {e}")
            self._respond_error(500, f'Error processing repositories data: {str(e)}')

    def _extract_machine_ip(self, machine_data):
        """Extract IP address from machine vault content"""
        machine_name = machine_data.get('machineName', 'Unknown')
        try:
            vault_content = machine_data.get('vaultContent', '')
            print(f"DEBUG: Extracting IP for machine {machine_name}")
            print(f"DEBUG: VaultContent length: {len(vault_content) if vault_content else 0}")

            if vault_content and vault_content.strip():
                # Parse the JSON vault content
                print(f"DEBUG: VaultContent for {machine_name}: {vault_content[:200]}...")  # First 200 chars
                parsed_content = json.loads(vault_content)
                ip = parsed_content.get('ip', '').strip()
                print(f"DEBUG: Extracted IP '{ip}' for machine {machine_name}")
                if ip:
                    return ip

            # Fallback: check if IP is in other fields
            if 'ip' in machine_data and machine_data['ip']:
                print(f"DEBUG: Using fallback IP for {machine_name}: {machine_data['ip']}")
                return machine_data['ip']

            # If no IP found, return a descriptive placeholder
            print(f"DEBUG: No IP found for machine {machine_name}")
            return 'No IP Configured'
        except json.JSONDecodeError as e:
            print(f"DEBUG: Failed to parse vaultContent JSON for machine {machine_name}: {e}")
            print(f"DEBUG: Raw vaultContent: {vault_content}")
            return 'Invalid Vault Data'
        except Exception as e:
            print(f"DEBUG: Error extracting IP for machine {machine_name}: {e}")
            return 'Error Reading Vault'

    def _handle_protocol_test(self):
        """Test a protocol URL by simulating CLI invocation"""
        # Read request body
        content_length = int(self.headers.get('Content-Length', 0))
        if content_length > 0:
            body = self.rfile.read(content_length).decode('utf-8')
            try:
                data = json.loads(body)
                protocol_url = data.get('url', '')

                if not protocol_url.startswith('rediacc://'):
                    self._respond_error(400, 'Invalid protocol URL')
                    return

                # Parse the protocol URL
                from cli.core.protocol_handler import ProtocolUrlParser
                parser = ProtocolUrlParser()

                try:
                    parsed_url = parser.parse_url(protocol_url)

                    # Simulate what would happen when the protocol handler is invoked
                    test_result = {
                        'url': protocol_url,
                        'parsed': parsed_url,
                        'simulation': {
                            'action': 'protocol_handler_invoked',
                            'would_execute': self._get_cli_command_for_protocol(parsed_url),
                            'timestamp': time.time()
                        }
                    }

                    # Try to actually execute the command (in dry-run mode if possible)
                    if parsed_url.get('action') == 'sync':
                        # For sync, we can do a dry run
                        cli_args = ['sync', '--help']  # Just show help instead of actual sync
                        result = self._run_cli_command(cli_args)
                        test_result['cli_test'] = {
                            'command': ' '.join(cli_args),
                            'success': result['success'],
                            'output': result['stdout'][:500]  # Truncate output
                        }

                    self._respond_json(test_result)

                except Exception as e:
                    self._respond_error(400, f'Failed to parse protocol URL: {str(e)}')

            except json.JSONDecodeError:
                self._respond_error(400, 'Invalid JSON in request body')
        else:
            self._respond_error(400, 'Missing request body')

    def _get_cli_command_for_protocol(self, parsed_url):
        """Generate the CLI command that would be executed for a protocol URL"""
        action = parsed_url.get('action')
        params = parsed_url.get('params', {})

        if action == 'sync':
            direction = params.get('direction', 'download')
            local_path = params.get('localPath', './download')
            cmd = f"rediacc sync {direction} --machine {parsed_url['machine']} --repo {parsed_url['repository']} --local {local_path}"
        elif action == 'terminal':
            cmd = f"rediacc term --machine {parsed_url['machine']} --repo {parsed_url['repository']}"
        elif action == 'plugin':
            plugin_type = params.get('type', 'terminal')
            cmd = f"rediacc plugin {plugin_type} --machine {parsed_url['machine']} --repo {parsed_url['repository']}"
        elif action == 'browser':
            path = params.get('path', '/')
            cmd = f"rediacc plugin browser --machine {parsed_url['machine']} --repo {parsed_url['repository']} --path {path}"
        else:
            cmd = f"rediacc # Unknown action: {action}"

        return cmd

    def log_message(self, format, *args):
        """Override to customize logging"""
        print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {format % args}")


def start_server(port=8765, host='localhost'):
    """Start the protocol test server"""
    server_address = (host, port)
    httpd = HTTPServer(server_address, ProtocolTestHandler)

    print(f"🚀 Protocol Test Server starting on http://{host}:{port}")
    print(f"📄 Test page: http://{host}:{port}")
    print(f"🔧 API endpoints:")
    print(f"   GET  /api/credentials")
    print(f"   GET  /api/teams")
    print(f"   GET  /api/machines/{{team}}")
    print(f"   GET  /api/repositories/{{team}}")
    print(f"   POST /api/protocol/test")
    print(f"   GET  /health")
    print(f"\n✅ Server ready! Press Ctrl+C to stop.")

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print(f"\n🛑 Shutting down server...")
        httpd.shutdown()


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='Protocol Test Web Service')
    parser.add_argument('--port', type=int, default=8765, help='Server port (default: 8765)')
    parser.add_argument('--host', default='localhost', help='Server host (default: localhost)')

    args = parser.parse_args()
    start_server(args.port, args.host)