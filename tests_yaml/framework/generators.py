"""
Test data generators for creating valid and invalid test data.
"""

import random
import string
import uuid
import json
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
import ipaddress


class DataGenerator:
    """
    Generate test data for various entity types and fields.
    """
    
    def __init__(self, seed: Optional[int] = None):
        if seed:
            random.seed(seed)
        
        self.used_names: Dict[str, set] = {}
    
    def unique_name(self, prefix: str = "test", suffix_length: int = 8) -> str:
        """Generate a unique name with prefix"""
        if prefix not in self.used_names:
            self.used_names[prefix] = set()
        
        while True:
            suffix = ''.join(random.choices(string.ascii_lowercase + string.digits, k=suffix_length))
            name = f"{prefix}_{suffix}"
            
            if name not in self.used_names[prefix]:
                self.used_names[prefix].add(name)
                return name
    
    def random_string(self, min_length: int = 5, max_length: int = 20, 
                     charset: str = None) -> str:
        """Generate random string"""
        if charset is None:
            charset = string.ascii_letters + string.digits
        
        length = random.randint(min_length, max_length)
        return ''.join(random.choices(charset, k=length))
    
    def random_email(self, domain: str = "test.com") -> str:
        """Generate random email address"""
        username = self.random_string(5, 10, string.ascii_lowercase + string.digits)
        return f"{username}@{domain}"
    
    def random_ip(self, private: bool = True) -> str:
        """Generate random IP address"""
        if private:
            # Generate private IP ranges
            networks = [
                ipaddress.IPv4Network('10.0.0.0/8'),
                ipaddress.IPv4Network('172.16.0.0/12'),
                ipaddress.IPv4Network('192.168.0.0/16')
            ]
            network = random.choice(networks)
            return str(ipaddress.IPv4Address(
                random.randint(int(network.network_address), int(network.broadcast_address))
            ))
        else:
            # Generate public IP
            return f"{random.randint(1, 223)}.{random.randint(0, 255)}.{random.randint(0, 255)}.{random.randint(1, 254)}"
    
    def random_port(self, min_port: int = 1024, max_port: int = 65535) -> int:
        """Generate random port number"""
        return random.randint(min_port, max_port)
    
    def random_path(self, depth: int = 3, prefix: str = "/data") -> str:
        """Generate random file path"""
        parts = [prefix]
        for _ in range(depth):
            parts.append(self.random_string(3, 10, string.ascii_lowercase))
        return '/'.join(parts)
    
    def random_url(self, protocol: str = "https") -> str:
        """Generate random URL"""
        domain = f"{self.random_string(5, 10, string.ascii_lowercase)}.com"
        path = self.random_path(2, "")
        return f"{protocol}://{domain}/{path}"
    
    def random_cron(self) -> str:
        """Generate random cron expression"""
        minute = random.randint(0, 59)
        hour = random.randint(0, 23)
        day = random.randint(1, 28)
        month = random.randint(1, 12)
        dow = random.randint(0, 6)
        
        # Generate different patterns
        patterns = [
            f"{minute} {hour} * * *",  # Daily
            f"{minute} {hour} * * {dow}",  # Weekly
            f"{minute} {hour} {day} * *",  # Monthly
            f"0 */4 * * *",  # Every 4 hours
            f"*/30 * * * *",  # Every 30 minutes
        ]
        
        return random.choice(patterns)
    
    def random_json(self, depth: int = 2, max_items: int = 5) -> Dict[str, Any]:
        """Generate random JSON object"""
        if depth <= 0:
            return self.random_string()
        
        obj = {}
        num_items = random.randint(1, max_items)
        
        for _ in range(num_items):
            key = self.random_string(3, 10, string.ascii_lowercase)
            
            # Random value type
            value_type = random.choice(['string', 'number', 'boolean', 'object', 'array'])
            
            if value_type == 'string':
                obj[key] = self.random_string()
            elif value_type == 'number':
                obj[key] = random.randint(0, 1000)
            elif value_type == 'boolean':
                obj[key] = random.choice([True, False])
            elif value_type == 'object':
                obj[key] = self.random_json(depth - 1, max_items)
            elif value_type == 'array':
                obj[key] = [self.random_string() for _ in range(random.randint(1, 3))]
        
        return obj
    
    def generate_company(self, name: Optional[str] = None) -> Dict[str, Any]:
        """Generate company data"""
        return {
            'name': name or self.unique_name('company'),
            'email': self.random_email()
        }
    
    def generate_user(self, company: str, email: Optional[str] = None) -> Dict[str, Any]:
        """Generate user data"""
        return {
            'name': self.unique_name('user'),
            'company': company,
            'email': email or self.random_email(),
            'role': random.choice(['Admin', 'User', 'Viewer'])
        }
    
    def generate_team(self, company: str, name: Optional[str] = None) -> Dict[str, Any]:
        """Generate team data"""
        data = {
            'name': name or self.unique_name('team'),
            'company': company
        }
        
        # Add vault data
        if random.choice([True, False]):
            data['vault'] = {
                'SSH_PRIVATE_KEY': self.generate_ssh_key(),
                'custom_field': self.random_string()
            }
        
        return data
    
    def generate_region(self, company: str, name: Optional[str] = None) -> Dict[str, Any]:
        """Generate region data"""
        locations = ['us-east-1', 'us-west-2', 'eu-west-1', 'ap-southeast-1']
        
        return {
            'name': name or self.unique_name('region'),
            'company': company,
            'location': random.choice(locations)
        }
    
    def generate_bridge(self, region: str, name: Optional[str] = None) -> Dict[str, Any]:
        """Generate bridge data"""
        data = {
            'name': name or self.unique_name('bridge'),
            'region': region
        }
        
        if random.choice([True, False]):
            data['api_url'] = self.random_url()
        
        return data
    
    def generate_machine(self, team: str, bridge: str, name: Optional[str] = None) -> Dict[str, Any]:
        """Generate machine data"""
        data = {
            'name': name or self.unique_name('machine'),
            'team': team,
            'bridge': bridge
        }
        
        # Add vault data
        data['vault'] = {
            'ip': self.random_ip(),
            'user': random.choice(['ubuntu', 'ec2-user', 'admin', 'deploy']),
            'datastore': self.random_path(2, '/mnt/datastore')
        }
        
        if random.choice([True, False]):
            data['vault']['port'] = self.random_port(22, 22222)
        
        return data
    
    def generate_repository(self, team: str, machine: str, name: Optional[str] = None) -> Dict[str, Any]:
        """Generate repository data"""
        repo_types = ['git', 'svn', 'mercurial', 'directory']
        repo_type = random.choice(repo_types)
        
        data = {
            'name': name or self.unique_name('repo'),
            'team': team,
            'machine': machine,
            'repo_type': repo_type
        }
        
        if repo_type == 'git':
            data['url'] = f"git@github.com:test/{data['name']}.git"
        elif repo_type == 'svn':
            data['url'] = f"svn://svn.test.com/{data['name']}"
        
        return data
    
    def generate_storage(self, team: str, name: Optional[str] = None) -> Dict[str, Any]:
        """Generate storage data"""
        storage_types = ['s3', 'azure', 'gcs', 'local']
        storage_type = random.choice(storage_types)
        
        data = {
            'name': name or self.unique_name('storage'),
            'team': team,
            'storage_type': storage_type
        }
        
        if storage_type == 's3':
            data['bucket'] = f"s3://test-bucket-{self.random_string(5, 10)}"
        elif storage_type == 'azure':
            data['bucket'] = f"azure://test-container-{self.random_string(5, 10)}"
        
        return data
    
    def generate_schedule(self, team: str, name: Optional[str] = None) -> Dict[str, Any]:
        """Generate schedule data"""
        functions = ['backup', 'sync', 'cleanup', 'healthcheck', 'deploy']
        
        return {
            'name': name or self.unique_name('schedule'),
            'team': team,
            'cron': self.random_cron(),
            'enabled': random.choice([True, False]),
            'function': random.choice(functions)
        }
    
    def generate_queue_item(self, team: str, machine: str, 
                           bridge: Optional[str] = None) -> Dict[str, Any]:
        """Generate queue item data"""
        functions = ['create_repository', 'backup', 'restore', 'sync', 'execute_script']
        
        data = {
            'team': team,
            'machine': machine,
            'function': random.choice(functions),
            'priority': random.randint(1, 5)
        }
        
        if bridge:
            data['bridge'] = bridge
        
        # Add vault data based on function
        function = data['function']
        if function == 'create_repository':
            data['vault'] = {
                'repository': self.unique_name('repo'),
                'type': 'git'
            }
        elif function == 'backup':
            data['vault'] = {
                'source': self.random_path(),
                'destination': f"s3://backup/{self.random_string()}"
            }
        elif function == 'execute_script':
            data['vault'] = {
                'script': 'echo "Hello from test"',
                'timeout': 300
            }
        
        return data
    
    def generate_ssh_key(self) -> str:
        """Generate fake SSH private key for testing"""
        return f"""-----BEGIN RSA PRIVATE KEY-----
{self.random_string(64, 64)}
{self.random_string(64, 64)}
{self.random_string(64, 64)}
-----END RSA PRIVATE KEY-----"""
    
    def generate_invalid_data(self, entity_type: str) -> List[Dict[str, Any]]:
        """Generate invalid test data for negative testing"""
        invalid_data = []
        
        if entity_type == 'company':
            invalid_data.extend([
                {'name': ''},  # Empty name
                {'name': 'test company with spaces'},  # Invalid characters
                {'name': 'a' * 101},  # Too long
                {'email': 'invalid-email'},  # Invalid email
            ])
        
        elif entity_type == 'team':
            invalid_data.extend([
                {'name': 'test', 'company': ''},  # Missing company
                {'name': '', 'company': 'test'},  # Empty name
                {'name': 'test@team', 'company': 'test'},  # Invalid characters
            ])
        
        elif entity_type == 'machine':
            invalid_data.extend([
                {'name': 'test', 'team': 'test'},  # Missing bridge
                {'name': 'test', 'bridge': 'test'},  # Missing team
                {'name': 'test', 'team': 'test', 'bridge': 'test', 'vault': {}},  # Empty vault
            ])
        
        elif entity_type == 'queue_item':
            invalid_data.extend([
                {'team': 'test', 'machine': 'test'},  # Missing function
                {'team': 'test', 'function': 'test'},  # Missing machine
                {'team': 'test', 'machine': 'test', 'function': 'test', 'priority': 0},  # Invalid priority
                {'team': 'test', 'machine': 'test', 'function': 'test', 'priority': 6},  # Invalid priority
            ])
        
        return invalid_data
    
    def generate_bulk_data(self, entity_type: str, count: int, **params) -> List[Dict[str, Any]]:
        """Generate bulk test data"""
        data = []
        
        generator_map = {
            'company': self.generate_company,
            'user': self.generate_user,
            'team': self.generate_team,
            'region': self.generate_region,
            'bridge': self.generate_bridge,
            'machine': self.generate_machine,
            'repository': self.generate_repository,
            'storage': self.generate_storage,
            'schedule': self.generate_schedule,
            'queue_item': self.generate_queue_item
        }
        
        generator = generator_map.get(entity_type)
        if not generator:
            raise ValueError(f"Unknown entity type: {entity_type}")
        
        for i in range(count):
            item_params = params.copy()
            # Add index-based naming if name not provided
            if 'name' not in item_params and entity_type != 'queue_item':
                item_params['name'] = f"{entity_type}_{i:04d}"
            
            data.append(generator(**item_params))
        
        return data