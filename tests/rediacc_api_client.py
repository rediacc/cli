"""
In-memory API client for Rediacc CLI tests
Provides direct API access without subprocess overhead
"""
import hashlib
import json
import requests
from typing import Dict, Any, Optional, List
import time


class InMemoryTokenStore:
    """In-memory token storage for test sessions"""
    def __init__(self):
        self.tokens: Dict[str, str] = {}
        self.active_session: Optional[str] = None
        
    def set_token(self, key: str, token: str):
        """Store token in memory"""
        self.tokens[key] = token
        self.active_session = key
        
    def get_token(self, key: Optional[str] = None) -> Optional[str]:
        """Retrieve token from memory"""
        if key is None:
            key = self.active_session
        return self.tokens.get(key) if key else None
        
    def clear_token(self, key: Optional[str] = None):
        """Remove token from memory"""
        if key is None:
            key = self.active_session
        if key and key in self.tokens:
            del self.tokens[key]
            if self.active_session == key:
                self.active_session = None
                
    def set_active_session(self, key: str):
        """Set the active session"""
        if key in self.tokens:
            self.active_session = key


class RediaccAPIClient:
    """Direct API client for Rediacc with token rotation support"""
    
    # Static salt from the system
    PASSWORD_SALT = 'Rd!@cc111$ecur3P@$w0rd$@lt#H@$h'
    
    def __init__(self, base_url: str = "http://localhost:7322"):
        self.base_url = base_url.rstrip('/')
        self.token_store = InMemoryTokenStore()
        self.session = requests.Session()
        
    def hash_password(self, password: str) -> str:
        """Hash password with static salt"""
        salted = password + self.PASSWORD_SALT
        hash_bytes = hashlib.sha256(salted.encode()).digest()
        # Return hex string with 0x prefix (expected by backend)
        return '0x' + hash_bytes.hex()
        
    def _make_request(self, endpoint: str, data: Dict[str, Any], 
                      token: Optional[str] = None, 
                      headers: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        """Make API request with automatic token rotation"""
        url = f"{self.base_url}/api/StoredProcedure/{endpoint}"
        
        # Build headers
        request_headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }
        
        # Add authentication token
        if token is None:
            token = self.token_store.get_token()
        if token:  # Only add header if token is not empty string
            request_headers['Rediacc-RequestToken'] = token
            
        # Merge additional headers
        if headers:
            request_headers.update(headers)
            
        try:
            response = self.session.post(
                url,
                json=data,
                headers=request_headers,
                timeout=30
            )
            
            # Parse response
            if response.status_code == 200:
                result = response.json()
                
                # Handle token rotation from response body
                if 'resultSets' in result and len(result['resultSets']) > 0:
                    first_table = result['resultSets'][0]
                    if 'data' in first_table and len(first_table['data']) > 0:
                        first_row = first_table['data'][0]
                        if 'nextRequestCredential' in first_row:
                            new_token = first_row['nextRequestCredential']
                            if self.token_store.active_session:
                                self.token_store.set_token(self.token_store.active_session, new_token)
                
                return {
                    'success': True,
                    'data': result,
                    'status_code': response.status_code
                }
            else:
                # Try to parse error response
                try:
                    error_data = response.json()
                    # Check for errors array first (from stored procedures)
                    if 'errors' in error_data and error_data['errors']:
                        error_msg = error_data['errors'][0] if isinstance(error_data['errors'], list) else str(error_data['errors'])
                    else:
                        error_msg = error_data.get('error', f'HTTP {response.status_code}')
                except:
                    error_msg = f'HTTP {response.status_code}'
                    
                return {
                    'success': False,
                    'error': f'API Error: {response.status_code} - {error_msg}',
                    'status_code': response.status_code
                }
                
        except requests.exceptions.Timeout:
            return {
                'success': False,
                'error': 'Request timed out',
                'timeout': True
            }
        except Exception as e:
            return {
                'success': False,
                'error': f'Request failed: {str(e)}'
            }
            
    def execute_command(self, command: str, args: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a command through the API"""
        # Map command to endpoint
        endpoint = self._map_command_to_endpoint(command)
        
        # Prepare data based on endpoint requirements
        data = self._prepare_request_data(endpoint, args)
        
        # Some endpoints need special header handling
        headers = self._get_special_headers(endpoint, args)
        
        # Determine if this endpoint should use token
        # Unauthenticated endpoints that should NOT send a token
        unauthenticated_endpoints = [
            'CreateNewCompany',
            'ActivateUserAccount',
            'CreateAuthenticationRequest',
            'IsRegistered'
        ]
        
        # For unauthenticated endpoints, explicitly pass empty token
        if endpoint in unauthenticated_endpoints:
            result = self._make_request(endpoint, data, token='', headers=headers)
        else:
            result = self._make_request(endpoint, data, headers=headers)
        
        # Handle logout - clear token
        if endpoint == 'DeleteUserRequest' and result['success']:
            self.token_store.clear_token()
        
        # Format response for compatibility with tests
        if result['success']:
            return self._format_response(endpoint, result['data'], args)
        else:
            return result
            
    def _format_response(self, endpoint: str, raw_response: Dict[str, Any], args: Dict[str, Any]) -> Dict[str, Any]:
        """Format API response to match test expectations"""
        # Extract data from resultSets format
        data_rows = []
        if 'resultSets' in raw_response:
            # Skip the first resultSet (contains nextRequestCredential)
            # Use subsequent resultSets for actual data
            for i, result_set in enumerate(raw_response['resultSets']):
                if i > 0 and 'data' in result_set:
                    data_rows.extend(result_set['data'])
        
        # Special formatting for specific endpoints
        if endpoint == 'CreateAuthenticationRequest':
            # Login response
            return {
                'success': True,
                'data': {
                    'email': args.get('email'),
                    'company': None,
                    'vault_encryption_enabled': False,
                    'master_password_set': False
                }
            }
        elif endpoint == 'DeleteUserRequest':
            # Logout response
            return {
                'success': True,
                'data': {}
            }
        else:
            # Standard response format
            return {
                'success': True,
                'data': data_rows
            }
        
    def _map_command_to_endpoint(self, command: str) -> str:
        """Map CLI command to API endpoint"""
        # Handle array format commands
        if isinstance(command, list):
            command = command[0]
            
        # Special command mappings
        if command == 'login':
            return 'CreateAuthenticationRequest'
        elif command == 'logout':
            return 'DeleteUserRequest'
            
        # All other commands map directly to endpoints
        return command
        
    def _prepare_request_data(self, endpoint: str, args: Dict[str, Any]) -> Dict[str, Any]:
        """Prepare request data based on endpoint requirements"""
        # CreateAuthenticationRequest expects name parameter in body
        if endpoint == 'CreateAuthenticationRequest':
            return {
                'name': args.get('name', args.get('session_name', 'CLI Session'))
            }
            
        # These endpoints expect empty body (auth in headers only)
        headers_only_endpoints = [
            'GetRequestAuthenticationStatus'
        ]
        
        if endpoint in headers_only_endpoints:
            return {}
            
        # PrivilegeAuthenticationRequest expects TFACode parameter
        if endpoint == 'PrivilegeAuthenticationRequest':
            return {
                'TFACode': args.get('tfaCode', '')
            }
            
        # CreateNewCompany expects companyName and optionally subscriptionPlan in body
        if endpoint == 'CreateNewCompany':
            data = {
                'companyName': args.get('companyName', '')
            }
            if 'subscriptionPlan' in args:
                data['subscriptionPlan'] = args['subscriptionPlan']
            return data
        
        # ActivateUserAccount only needs activationCode in body
        if endpoint == 'ActivateUserAccount':
            return {
                'activationCode': args.get('activationCode', '')
            }
            
        # Most endpoints accept all parameters in body
        return args
        
    def _get_special_headers(self, endpoint: str, args: Dict[str, Any]) -> Optional[Dict[str, str]]:
        """Get special headers for certain endpoints"""
        # CreateNewCompany needs email and passwordHash in headers with Rediacc- prefix
        if endpoint == 'CreateNewCompany':
            password_hash = self.hash_password(args.get('password', ''))
            return {
                'Rediacc-UserEmail': args.get('email', ''),
                'Rediacc-UserHash': password_hash
            }
            
        # ActivateUserAccount needs email and passwordHash in headers with Rediacc- prefix
        if endpoint == 'ActivateUserAccount':
            password_hash = self.hash_password(args.get('password', ''))
            return {
                'Rediacc-UserEmail': args.get('email', ''),
                'Rediacc-UserHash': password_hash
            }
            
        # CreateAuthenticationRequest needs email and passwordHash in headers with Rediacc- prefix
        if endpoint == 'CreateAuthenticationRequest':
            email = args.get('email', '')
            password_hash = self.hash_password(args.get('password', ''))
            # Create session key for token storage
            session_key = f"session_{email}"
            self.token_store.active_session = session_key
            # Initialize with empty token - will be updated after response
            self.token_store.set_token(session_key, "")
            return {
                'Rediacc-UserEmail': email,
                'Rediacc-UserHash': password_hash
            }
            
        # GetRequestAuthenticationStatus needs email in header
        if endpoint == 'GetRequestAuthenticationStatus':
            return {
                'Rediacc-UserEmail': args.get('email', '')
            }
            
        # PrivilegeAuthenticationRequest needs email and totp in headers
        if endpoint == 'PrivilegeAuthenticationRequest':
            return {
                'Rediacc-UserEmail': args.get('email', ''),
                'totp': args.get('totp', '')
            }
            
        return None