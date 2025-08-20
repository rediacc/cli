#!/usr/bin/env python3
"""
SuperClient - Universal API Client for Rediacc CLI

This module provides a single, consolidated API client instance that can be used
across all CLI components (main CLI, GUI, tests, etc.) with intelligent
auto-detection of configuration options.
"""

import hashlib
import json
import os
import sys
import time
from typing import Dict, Any, Optional, Tuple

# Import from core module
from .config import TokenManager, get_required, api_mutex
# Import environment configuration
from .env_config import EnvironmentConfig


class InMemoryTokenStore:
    def __init__(self):
        self.tokens: Dict[str, str] = {}
        self.active_session: Optional[str] = None
        
    def set_token(self, key: str, token: str):
        self.tokens[key] = token
        self.active_session = key
        
    def get_token(self, key: Optional[str] = None) -> Optional[str]:
        key = key or self.active_session
        return self.tokens.get(key) if key else None
        
    def clear_token(self, key: Optional[str] = None):
        key = key or self.active_session
        if key and key in self.tokens:
            del self.tokens[key]
            if self.active_session == key:
                self.active_session = None
                
    def set_active_session(self, key: str):
        if key in self.tokens:
            self.active_session = key


class SuperClient:
    PASSWORD_SALT = 'Rd!@cc111$ecur3P@$w0rd$@lt#H@$h'
    USER_AGENT = "rediacc/1.0"
    MIDDLEWARE_ERROR_HELP = "\nPlease ensure the middleware is running.\nTry: ./go system up middleware"
    
    _instance = None
    _initialized = False
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if SuperClient._initialized:
            return
        
        SuperClient._initialized = True
        self.user_agent = SuperClient.USER_AGENT
        self.base_headers = {"Content-Type": "application/json", "User-Agent": self.user_agent}
        self.config_manager = None
        self._vault_warning_shown = False
        self.use_requests = self._should_use_requests()
        
        if self.use_requests:
            try:
                import requests
                self.requests = requests
                self.session = requests.Session()
            except ImportError:
                self.use_requests = False
        
        self.token_store = InMemoryTokenStore()
    
    def _should_use_requests(self):
        if any(test_indicator in sys.argv[0] for test_indicator in ['test', 'pytest']):
            return True
        try:
            import requests
            return any(indicator in self.base_url for indicator in ['localhost', '127.0.0.1', ':7322'])
        except ImportError:
            return False
    
    def _execute_http_request(self, url, method='POST', data=None, headers=None, timeout=None):
        timeout = timeout or self.request_timeout
        merged_headers = {**self.base_headers, **(headers or {})}
        
        if os.environ.get('REDIACC_DEBUG'):
            prefix = "[REQUESTS]" if self.use_requests else "[URLLIB]"
            print(f"DEBUG: {prefix} {method} {url}", file=sys.stderr)
            print(f"DEBUG: Headers: {merged_headers}", file=sys.stderr)
            if data:
                print(f"DEBUG: Payload: {json.dumps(data, indent=2)}", file=sys.stderr)
        
        return (self._execute_with_requests(url, method, data, merged_headers, timeout) 
               if self.use_requests else 
               self._execute_with_urllib(url, method, data, merged_headers, timeout))
    
    def _execute_with_requests(self, url, method, data, headers, timeout):
        try:
            response = getattr(self.session, method.lower())(url, json=data, headers=headers, timeout=timeout)
            return response.text, response.status_code, dict(response.headers)
        except self.requests.exceptions.RequestException as e:
            raise Exception(f"Request error: {str(e)}")
    
    def _execute_with_urllib(self, url, method, data, headers, timeout):
        import urllib.request, urllib.error
        
        try:
            req_data = json.dumps(data).encode('utf-8') if data else None
            req = urllib.request.Request(url, data=req_data, headers=headers, method=method.upper())
            
            with urllib.request.urlopen(req, timeout=timeout) as response:
                return response.read().decode('utf-8'), response.getcode(), dict(response.info())
                
        except urllib.error.HTTPError as e:
            raise Exception(f"HTTP {e.code}: {e.read().decode('utf-8') if e.fp else str(e)}")
        except urllib.error.URLError as e:
            raise Exception(f"Connection error: {str(e)}")
        except Exception as e:
            raise Exception(f"Request error: {str(e)}")
    
    def _prepare_request_for_api(self, endpoint, data=None, headers=None):
        url = f"{self.base_url}{self.api_prefix}/{endpoint}"
        prepared_data = data
        merged_headers = {**self.base_headers, **(headers or {})}
        
        if data and self.should_use_vault_encryption and (master_pwd := self.config_manager.get_master_password()):
            try:
                from .config import encrypt_vault_fields
                prepared_data = encrypt_vault_fields(data, master_pwd)
            except Exception as e:
                from .config import colorize
                print(colorize(f"Warning: Failed to encrypt vault fields: {e}", 'YELLOW'))
        
        return url, prepared_data, merged_headers
    
    def _process_api_response(self, response_text, status_code):
        try:
            result = json.loads(response_text) if isinstance(response_text, str) else response_text
        except json.JSONDecodeError:
            return {"error": f"Invalid JSON response: {response_text}", "status_code": 500}
        
        if result.get('failure') and result.get('failure') != 0:
            errors = result.get('errors', [])
            error_msg = f"API Error: {'; '.join(errors) if errors else result.get('message', 'Request failed')}"
            result.update({'error': error_msg, 'status_code': result.get('failure', 400)})
            return result
        
        if self.should_use_vault_encryption and (master_pwd := self.config_manager.get_master_password()):
            try:
                from .config import decrypt_vault_fields
                result = decrypt_vault_fields(result, master_pwd)
            except Exception as e:
                from .config import colorize
                print(colorize(f"Warning: Failed to decrypt vault fields: {e}", 'YELLOW'))
        
        return result
    
    def _handle_http_error(self, error_msg, status_code):
        try:
            error_json = json.loads(error_msg)
            error_text = ('; '.join(error_json.get('errors', [])) or 
                         error_json.get('message') or 
                         error_json.get('error') or 
                         f"API Error: {status_code}")
            error_json.update({'error': error_text, 'status_code': status_code})
            return error_json
        except json.JSONDecodeError:
            return {"error": f"API Error: {status_code} - {error_msg}", "status_code": status_code}
    
    @property
    def base_url(self):
        return get_required('SYSTEM_API_URL')
    
    @property
    def api_prefix(self):
        base_url = self.base_url
        if base_url.endswith('/api') or '/api/' in base_url:
            return '/StoredProcedure'
        return '/api/StoredProcedure' if self.use_requests or ':7322' in base_url else '/StoredProcedure'
    
    @property
    def request_timeout(self):
        return 30
    
    @property
    def should_use_vault_encryption(self):
        return (self.config_manager and self.config_manager.get_master_password() and
                getattr(self.config_manager, 'has_vault_encryption', lambda: True)())
    
    def set_config_manager(self, config_manager):
        self.config_manager = config_manager
        if config_manager and hasattr(config_manager, 'load_vault_info_from_config'):
            config_manager.load_vault_info_from_config()
    
    def ensure_config_manager(self):
        if self.config_manager is None:
            from .config import get_default_config_manager
            self.set_config_manager(get_default_config_manager())
    
    def request(self, endpoint, data=None, headers=None):
        url, prepared_data, merged_headers = self._prepare_request_for_api(endpoint, data, headers)
        
        try:
            response_text, status_code, response_headers = self._execute_http_request(
                url, 'POST', prepared_data, merged_headers)
            
            if status_code >= 500:
                print(f"DEBUG: Endpoint URL: {url}\nDEBUG: HTTP Error {status_code} occurred", file=sys.stderr)
            
            return (self._process_api_response(response_text, status_code) 
                   if status_code == 200 else 
                   self._handle_http_error(response_text, status_code))
                
        except Exception as e:
            error_msg = str(e)
            print(f"DEBUG: Request error for endpoint: {url}\nDEBUG: Error details: {error_msg}", file=sys.stderr)
            
            if "HTTP " in error_msg and ":" in error_msg:
                try:
                    status_code = int(error_msg.split("HTTP ")[1].split(":")[0])
                    error_body = error_msg.split(":", 1)[1].strip()
                    return self._handle_http_error(error_body, status_code)
                except (ValueError, IndexError):
                    pass
            
            return {"error": f"Request error: {error_msg}", "status_code": 500}
    
    def auth_request(self, endpoint, email, pwd_hash, data=None):
        """Make an authentication request with email and password hash"""
        return self.request(endpoint, data, {"Rediacc-UserEmail": email, "Rediacc-UserHash": pwd_hash})
    
    def token_request(self, endpoint, data=None, retry_count=0):
        """Make an authenticated request with token"""
        try:
            with api_mutex.acquire(timeout=30.0):
                return self._token_request_impl(endpoint, data, retry_count)
        except TimeoutError as e:
            return {"error": f"API call timeout: {str(e)}", "status_code": 408}
        except Exception as e:
            return {"error": f"API call error: {str(e)}", "status_code": 500}
    
    def _token_request_impl(self, endpoint, data=None, retry_count=0):
        """Internal implementation of token request with retry logic"""
        token = TokenManager.get_token()
        if not token:
            return {"error": "Not authenticated. Please login first.", "status_code": 401}
        
        # Ensure vault info is loaded (for CLI usage)
        if (endpoint != 'GetCompanyVault' and self.should_use_vault_encryption and 
            self.config_manager and hasattr(self.config_manager, '_ensure_vault_info')):
            self.config_manager._ensure_vault_info()
            self._show_vault_warning_if_needed()
        
        response = self.request(endpoint, data, {"Rediacc-RequestToken": token})
        
        # Handle token expiration with retry
        if response and response.get('status_code') == 401 and retry_count < 2:
            time.sleep(0.1 * (retry_count + 1))
            if TokenManager.get_token() != token:
                return self._token_request_impl(endpoint, data, retry_count + 1)
        
        self._update_token_if_needed(response, token)
        return response
    
    def _show_vault_warning_if_needed(self):
        """Show vault warning if encryption is required but no password is set"""
        if (self.config_manager and 
            hasattr(self.config_manager, 'has_vault_encryption') and 
            self.config_manager.has_vault_encryption() and 
            not self.config_manager.get_master_password() and 
            not self._vault_warning_shown):
            from .config import colorize
            print(colorize("Warning: Your company requires vault encryption but no master password is set.", 'YELLOW'))
            print(colorize("Vault fields will not be decrypted. Use 'rediacc vault set-password' to set it.", 'YELLOW'))
            self._vault_warning_shown = True
    
    def _extract_token_from_response(self, response):
        """Extract nextRequestToken from various response structures"""
        for result_set in response.get('resultSets', []):
            if result_set and result_set.get('data'):
                for data_row in result_set['data']:
                    if data_row and isinstance(data_row, dict):
                        if token := (data_row.get('nextRequestToken') or data_row.get('NextRequestToken')):
                            return token
        
        return response.get('nextRequestToken') or response.get('NextRequestToken')
    
    def _update_token_if_needed(self, response, current_token):
        """Update authentication token if a new one is provided in the response"""
        if not response: return
        
        if not self.config_manager:
            if os.environ.get('REDIACC_DEBUG'): print("DEBUG: No config manager, initializing default for token rotation", file=sys.stderr)
            self.ensure_config_manager()
        
        new_token = self._extract_token_from_response(response)
        
        if os.environ.get('REDIACC_DEBUG'):
            if new_token: print(f"DEBUG: Found new token in response (length: {len(new_token)})", file=sys.stderr)
            else:
                print("DEBUG: No new token found in response", file=sys.stderr)
                if response:
                    import json
                    print(f"DEBUG: Response structure: {json.dumps(response, indent=2)}", file=sys.stderr)
        
        if os.environ.get('REDIACC_DEBUG'):
            skip_reasons = {
                not new_token: "no new token found", 
                new_token == current_token: "new token same as current",
                bool(os.environ.get('REDIACC_TOKEN')): "REDIACC_TOKEN env var set",
                hasattr(self.config_manager, 'is_token_overridden') and self.config_manager.is_token_overridden(): "token was overridden"
            }
            for condition, reason in skip_reasons.items():
                if condition:
                    print(f"DEBUG: Token update skipped - {reason}", file=sys.stderr)
                    break
        
        if (not new_token or new_token == current_token or 
            os.environ.get('REDIACC_TOKEN') or 
            (hasattr(self.config_manager, 'is_token_overridden') and self.config_manager.is_token_overridden())):
            return
        
        stored_token = TokenManager.get_token()
        if os.environ.get('REDIACC_DEBUG'):
            print(f"DEBUG: Checking token update condition: stored={stored_token[:8] if stored_token else 'None'}... vs current={current_token[:8] if current_token else 'None'}...", file=sys.stderr)
        
        if stored_token == current_token:
            if os.environ.get('REDIACC_DEBUG'): print(f"DEBUG: Updating token from {current_token[:8]}... to {new_token[:8]}...", file=sys.stderr)
            
            if hasattr(self.config_manager, 'config') and self.config_manager.config:
                config = self.config_manager.config
                TokenManager.set_token(new_token, 
                                     email=config.get('email'),
                                     company=config.get('company'),
                                     vault_company=config.get('vault_company'))
                if os.environ.get('REDIACC_DEBUG'):
                    print("DEBUG: Token updated via CLI config manager", file=sys.stderr)
            else:
                auth_info = TokenManager.get_auth_info()
                TokenManager.set_token(new_token, 
                                     email=auth_info.get('email') if auth_info else None,
                                     company=auth_info.get('company') if auth_info else None,
                                     vault_company=auth_info.get('vault_company') if auth_info else None)
                if os.environ.get('REDIACC_DEBUG'):
                    print("DEBUG: Token updated via GUI auth info", file=sys.stderr)
        elif os.environ.get('REDIACC_DEBUG'):
            current_stored = TokenManager.get_token()
            print(f"DEBUG: Token not updated - stored token mismatch: {current_stored[:8] if current_stored else 'None'}... vs current: {current_token[:8] if current_token else 'None'}...", file=sys.stderr)
    
    def _ensure_vault_info(self):
        """Ensure vault info is loaded from API if needed (CLI-specific)"""
        if not (self.config_manager and self.config_manager.needs_vault_info_fetch()):
            return
        
        self.config_manager.mark_vault_info_fetched()
        company_info = self.get_company_vault()
        if not company_info:
            return
        
        email = self.config_manager.config.get('email')
        token = TokenManager.get_token()
        if email and token:
            self.config_manager.set_auth(
                email, token, company_info.get('companyName'), company_info.get('vaultCompany'))
    
    def get_company_vault(self):
        """Get company vault information from API (CLI-specific)"""
        response = self.token_request("GetCompanyVault", {})
        
        if response.get('error'):
            return None
        
        for table in response.get('resultSets', []):
            if not (data := table.get('data', [])):
                continue
            
            row = data[0]
            if 'nextRequestToken' in row:
                continue
            
            # Get vault content and company credential
            vault_content = row.get('vaultContent') or row.get('VaultContent', '{}')
            company_credential = row.get('companyCredential') or row.get('CompanyCredential')
            
            # Parse vault content and add COMPANY_ID
            try:
                vault_dict = json.loads(vault_content) if vault_content and vault_content != '-' else {}
                if company_credential:
                    vault_dict['COMPANY_ID'] = company_credential
                vault_json = json.dumps(vault_dict)
            except (json.JSONDecodeError, TypeError):
                vault_json = vault_content
            
            return {
                'companyName': row.get('companyName') or row.get('CompanyName', ''),
                'companyVault': vault_json,
                'vaultCompany': row.get('vaultCompany') or row.get('VaultCompany', ''),
                'companyCredential': company_credential
            }
        
        return None
    
    def _make_direct_request(self, url, data=None, method='GET'):
        """Make direct HTTP request (not through stored procedure endpoint) - refactored to use central function"""
        headers = {"User-Agent": self.user_agent}
        if data:
            headers["Content-Type"] = "application/json"
        
        timeout = 30 if data else 5
        
        try:
            response_text, status_code, response_headers = self._execute_http_request(
                url, method, data, headers, timeout)
            
            if status_code >= 400:
                raise Exception(f"HTTP {status_code}: {response_text}")
            
            return json.loads(response_text)
            
        except Exception as e:
            error_msg = str(e)
            
            # Handle specific error messages for license server operations
            if "HTTP " in error_msg and ":" in error_msg:
                # Extract status code and body for license server errors
                try:
                    status_part = error_msg.split("HTTP ")[1].split(":")[0]
                    error_body = error_msg.split(":", 1)[1].strip()
                    raise Exception(f"License server error {status_part}: {error_body}")
                except (ValueError, IndexError):
                    pass
            
            # Provide context-specific error messages
            if data:
                raise Exception(f"Failed to connect to license server: {error_msg}")
            else:
                error_msg = f"Failed to generate hardware ID: {error_msg}"
                error_msg += SuperClient.MIDDLEWARE_ERROR_HELP
                raise Exception(error_msg)
    
    def get_hardware_id(self):
        """Get hardware ID from middleware health endpoint"""
        base_url = self.base_url.removesuffix('/api/StoredProcedure').removesuffix('/api')
        hardware_id_url = f"{base_url}/api/health/hardware-id"
        data = self._make_direct_request(hardware_id_url, method='GET')
        return data['hardwareId']
    
    def request_license(self, hardware_id, base_url=None):
        """Request license from license server"""
        request_base_url = (base_url or self.base_url).removesuffix('/api/StoredProcedure').removesuffix('/api')
        license_url = f"{request_base_url}/api/license/request"
        return self._make_direct_request(license_url, {"HardwareId": hardware_id}, method='POST')
    
    def hash_password(self, password: str) -> str:
        """Hash password with static salt"""
        salted = password + SuperClient.PASSWORD_SALT
        return '0x' + hashlib.sha256(salted.encode()).hexdigest()
    
    def get_universal_user_info(self) -> Tuple[str, str, Optional[str]]:
        """Get universal user info from environment or config
        Returns: (universal_user_name, universal_user_id, company_id)
        """
        return EnvironmentConfig.get_universal_user_info()
    
    def get_company_vault_defaults(self) -> Dict[str, Any]:
        """Get company vault defaults from environment"""
        return EnvironmentConfig.get_company_vault_defaults()
    
    def get_universal_user_name(self) -> str:
        """Get universal user name with guaranteed fallback"""
        return EnvironmentConfig.get_universal_user_name()
    
    def get_universal_user_id(self) -> str:
        """Get universal user ID with guaranteed fallback"""
        return EnvironmentConfig.get_universal_user_id()
    
    def execute_command(self, command: str, args: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a command through the API (for test compatibility)"""
        endpoint = self._map_command_to_endpoint(command)
        data = self._prepare_request_data(endpoint, args)
        headers = self._get_special_headers(endpoint, args)
        
        # Unauthenticated endpoints that should NOT send a token
        unauthenticated_endpoints = ['CreateNewCompany', 'ActivateUserAccount', 
                                   'CreateAuthenticationRequest', 'IsRegistered']
        
        token = '' if endpoint in unauthenticated_endpoints else None
        result = self._make_test_request(endpoint, data, token=token, headers=headers)
        
        # Handle logout - clear token
        if endpoint == 'DeleteUserRequest' and result['success']:
            self.token_store.clear_token()
        
        return self._format_response(endpoint, result['data'], args) if result['success'] else result
    
    def _make_test_request(self, endpoint: str, data: Dict[str, Any], 
                          token: Optional[str] = None, 
                          headers: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        """Make API request with automatic token rotation (for testing)"""
        request_headers = {'Content-Type': 'application/json', 'Accept': 'application/json'}
        
        # Add authentication token
        token = token if token is not None else self.token_store.get_token()
        if token:  # Only add header if token is not empty string
            request_headers['Rediacc-RequestToken'] = token
            
        if headers:
            request_headers.update(headers)
        
        response = self.request(endpoint, data, request_headers)
        
        # Handle response for testing
        if 'error' not in response:
            # Handle token rotation from response body
            new_token = self._extract_token_from_response(response)
            if new_token and self.token_store.active_session:
                self.token_store.set_token(self.token_store.active_session, new_token)
            
            return {'success': True, 'data': response, 'status_code': 200}
        else:
            return {'success': False, 'error': response['error'], 
                   'status_code': response.get('status_code', 500)}
    
    def _format_response(self, endpoint: str, raw_response: Dict[str, Any], args: Dict[str, Any]) -> Dict[str, Any]:
        """Format API response to match test expectations"""
        data_rows = []
        if 'resultSets' in raw_response:
            for i, result_set in enumerate(raw_response['resultSets']):
                if i > 0 and 'data' in result_set:
                    data_rows.extend(result_set['data'])
        
        special_responses = {
            'CreateAuthenticationRequest': {
                'email': args.get('email'),
                'company': None,
                'vault_encryption_enabled': False,
                'master_password_set': False
            },
            'DeleteUserRequest': {}
        }
        
        return {'success': True, 'data': special_responses.get(endpoint, data_rows)}
    
    def _map_command_to_endpoint(self, command: str) -> str:
        """Map CLI command to API endpoint"""
        if isinstance(command, list):
            command = command[0]
        
        return {'login': 'CreateAuthenticationRequest', 'logout': 'DeleteUserRequest'}.get(command, command)
    
    def _prepare_request_data(self, endpoint: str, args: Dict[str, Any]) -> Dict[str, Any]:
        """Prepare request data based on endpoint requirements"""
        endpoint_data = {
            'CreateAuthenticationRequest': {'name': args.get('name', args.get('session_name', 'CLI Session'))},
            'PrivilegeAuthenticationRequest': {'TFACode': args.get('tfaCode', '')},
            'ActivateUserAccount': {'activationCode': args.get('activationCode', '')},
            'CreateNewCompany': {
                'companyName': args.get('companyName', ''),
                **({'subscriptionPlan': args['subscriptionPlan']} if 'subscriptionPlan' in args else {})
            }
        }
        
        return {} if endpoint in ['GetRequestAuthenticationStatus'] else endpoint_data.get(endpoint, args)
    
    def _get_special_headers(self, endpoint: str, args: Dict[str, Any]) -> Optional[Dict[str, str]]:
        """Get special headers for certain endpoints"""
        # Endpoints that need email and passwordHash in headers
        auth_endpoints = ['CreateNewCompany', 'ActivateUserAccount', 'CreateAuthenticationRequest']
        if endpoint in auth_endpoints:
            headers = {
                'Rediacc-UserEmail': args.get('email', ''),
                'Rediacc-UserHash': self.hash_password(args.get('password', ''))
            }
            
            # Special handling for CreateAuthenticationRequest
            if endpoint == 'CreateAuthenticationRequest':
                session_key = f"session_{args.get('email', '')}"
                self.token_store.active_session = session_key
                self.token_store.set_token(session_key, "")
            
            return headers
        
        # Other special cases
        special_headers = {
            'GetRequestAuthenticationStatus': {
                'Rediacc-UserEmail': args.get('email', '')
            },
            'PrivilegeAuthenticationRequest': {
                'Rediacc-UserEmail': args.get('email', ''),
                'totp': args.get('totp', '')
            }
        }
        
        return special_headers.get(endpoint)


class SimpleConfigManager:
    """Minimal config manager for SuperClient compatibility"""
    
    def __init__(self):
        self.config = {}
        self._master_password = None
    
    def get_master_password(self):
        return self._master_password
    
    def set_master_password(self, password):
        self._master_password = password
    
    def has_vault_encryption(self):
        auth_info = TokenManager.get_auth_info()
        return auth_info.get('vault_company') if auth_info else False
    
    def needs_vault_info_fetch(self):
        return False
    
    def is_token_overridden(self):
        return bool(os.environ.get('REDIACC_TOKEN'))
    
    def load_vault_info_from_config(self):
        pass


# Global singleton instance
client = SuperClient()

def get_client():
    """Get the global SuperClient instance"""
    return client

# Convenience functions for environment access
def get_universal_user_info() -> Tuple[str, str, Optional[str]]:
    """Get universal user info from environment or config"""
    return client.get_universal_user_info()

def get_company_vault_defaults() -> Dict[str, Any]:
    """Get company vault defaults from environment"""
    return client.get_company_vault_defaults()