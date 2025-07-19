"""
Test fixtures for common test scenarios and shared resources.
"""

import json
import os
from pathlib import Path
from typing import Dict, Any, Optional, List
import logging

try:
    from .generators import DataGenerator
    from .cli_wrapper import CLIWrapper
except ImportError:
    from generators import DataGenerator
    from cli_wrapper import CLIWrapper


class TestFixtures:
    """
    Manages shared test fixtures and pre-created resources.
    """
    
    def __init__(self, cli: Optional[CLIWrapper] = None, 
                 fixture_file: Optional[Path] = None):
        self.cli = cli
        self.fixture_file = fixture_file or Path("test_fixtures.json")
        self.logger = logging.getLogger(self.__class__.__name__)
        self.generator = DataGenerator()
        
        self._fixtures: Dict[str, Any] = {}
        self._loaded = False
    
    def load_fixtures(self):
        """Load fixtures from file if exists"""
        if self.fixture_file.exists():
            try:
                with open(self.fixture_file, 'r') as f:
                    self._fixtures = json.load(f)
                self._loaded = True
                self.logger.info(f"Loaded fixtures from {self.fixture_file}")
            except Exception as e:
                self.logger.error(f"Failed to load fixtures: {e}")
                self._fixtures = {}
    
    def save_fixtures(self):
        """Save fixtures to file"""
        try:
            with open(self.fixture_file, 'w') as f:
                json.dump(self._fixtures, f, indent=2)
            self.logger.info(f"Saved fixtures to {self.fixture_file}")
        except Exception as e:
            self.logger.error(f"Failed to save fixtures: {e}")
    
    def get_or_create_company(self, name: str = "TestCompany") -> Dict[str, Any]:
        """Get existing or create new test company"""
        if not self._loaded:
            self.load_fixtures()
        
        if 'company' in self._fixtures:
            return self._fixtures['company']
        
        # Create new company
        if self.cli:
            data = self.generator.generate_company(name)
            result = self.cli.create('company', **data)
            
            if result.get('success'):
                self._fixtures['company'] = data
                self.save_fixtures()
                return data
            else:
                raise RuntimeError(f"Failed to create company: {result.get('error')}")
        else:
            # Mock mode
            data = self.generator.generate_company(name)
            self._fixtures['company'] = data
            return data
    
    def get_or_create_team(self, company: Optional[str] = None, 
                          name: str = "TestTeam") -> Dict[str, Any]:
        """Get existing or create new test team"""
        if not self._loaded:
            self.load_fixtures()
        
        team_key = f"team_{name}"
        if team_key in self._fixtures:
            return self._fixtures[team_key]
        
        # Ensure company exists
        if not company:
            company_data = self.get_or_create_company()
            company = company_data['name']
        
        # Create new team
        if self.cli:
            data = self.generator.generate_team(company, name)
            result = self.cli.create('team', **data)
            
            if result.get('success'):
                self._fixtures[team_key] = data
                self.save_fixtures()
                return data
            else:
                raise RuntimeError(f"Failed to create team: {result.get('error')}")
        else:
            # Mock mode
            data = self.generator.generate_team(company, name)
            self._fixtures[team_key] = data
            return data
    
    def get_or_create_region(self, company: Optional[str] = None,
                            name: str = "TestRegion") -> Dict[str, Any]:
        """Get existing or create new test region"""
        if not self._loaded:
            self.load_fixtures()
        
        region_key = f"region_{name}"
        if region_key in self._fixtures:
            return self._fixtures[region_key]
        
        # Ensure company exists
        if not company:
            company_data = self.get_or_create_company()
            company = company_data['name']
        
        # Create new region
        if self.cli:
            data = self.generator.generate_region(company, name)
            result = self.cli.create('region', **data)
            
            if result.get('success'):
                self._fixtures[region_key] = data
                self.save_fixtures()
                return data
            else:
                raise RuntimeError(f"Failed to create region: {result.get('error')}")
        else:
            # Mock mode
            data = self.generator.generate_region(company, name)
            self._fixtures[region_key] = data
            return data
    
    def get_or_create_bridge(self, region: Optional[str] = None,
                            name: str = "TestBridge") -> Dict[str, Any]:
        """Get existing or create new test bridge"""
        if not self._loaded:
            self.load_fixtures()
        
        bridge_key = f"bridge_{name}"
        if bridge_key in self._fixtures:
            return self._fixtures[bridge_key]
        
        # Ensure region exists
        if not region:
            region_data = self.get_or_create_region()
            region = region_data['name']
        
        # Create new bridge
        if self.cli:
            data = self.generator.generate_bridge(region, name)
            result = self.cli.create('bridge', **data)
            
            if result.get('success'):
                self._fixtures[bridge_key] = data
                self.save_fixtures()
                return data
            else:
                raise RuntimeError(f"Failed to create bridge: {result.get('error')}")
        else:
            # Mock mode
            data = self.generator.generate_bridge(region, name)
            self._fixtures[bridge_key] = data
            return data
    
    def get_test_infrastructure(self) -> Dict[str, Dict[str, Any]]:
        """
        Get or create a complete test infrastructure including:
        - Company
        - Team with vault
        - Region
        - Bridge
        - Machine
        
        Returns dict with all created entities.
        """
        infrastructure = {}
        
        # Create company
        infrastructure['company'] = self.get_or_create_company()
        
        # Create team and region in parallel (they don't depend on each other)
        infrastructure['team'] = self.get_or_create_team(
            company=infrastructure['company']['name']
        )
        infrastructure['region'] = self.get_or_create_region(
            company=infrastructure['company']['name']
        )
        
        # Create bridge (depends on region)
        infrastructure['bridge'] = self.get_or_create_bridge(
            region=infrastructure['region']['name']
        )
        
        # Create machine (depends on team and bridge)
        if self.cli:
            machine_data = self.generator.generate_machine(
                team=infrastructure['team']['name'],
                bridge=infrastructure['bridge']['name'],
                name="TestMachine"
            )
            result = self.cli.create('machine', **machine_data)
            
            if result.get('success'):
                infrastructure['machine'] = machine_data
            else:
                raise RuntimeError(f"Failed to create machine: {result.get('error')}")
        else:
            infrastructure['machine'] = self.generator.generate_machine(
                team=infrastructure['team']['name'],
                bridge=infrastructure['bridge']['name'],
                name="TestMachine"
            )
        
        return infrastructure
    
    def cleanup_fixtures(self):
        """Clean up all created fixtures"""
        if not self.cli:
            self.logger.warning("No CLI wrapper, cannot cleanup fixtures")
            return
        
        # Clean up in reverse dependency order
        cleanup_order = [
            ('machine', 'machines'),
            ('bridge', 'bridges'),
            ('region', 'regions'),
            ('team', 'teams'),
            ('company', 'companies')
        ]
        
        for entity_single, entity_plural in cleanup_order:
            # Find all fixtures of this type
            for key, data in list(self._fixtures.items()):
                if key.startswith(f"{entity_single}_") or key == entity_single:
                    try:
                        name = data.get('name')
                        if name:
                            self.cli.delete(entity_plural, name)
                            self.logger.info(f"Deleted {entity_single}: {name}")
                            del self._fixtures[key]
                    except Exception as e:
                        self.logger.error(f"Failed to delete {entity_single}: {e}")
        
        # Save updated fixtures
        self.save_fixtures()
    
    def get_mock_responses(self) -> List[Dict[str, Any]]:
        """Get mock API responses for unit testing"""
        return [
            # Login response
            {
                "success": True,
                "token": "test-token-123",
                "nextRequestCredential": "next-token-456"
            },
            # Create company response
            {
                "success": True,
                "id": "company-123",
                "name": "TestCompany"
            },
            # Create team response
            {
                "success": True,
                "id": "team-123",
                "name": "TestTeam",
                "company": "TestCompany"
            },
            # Create machine response
            {
                "success": True,
                "id": "machine-123",
                "name": "TestMachine",
                "team": "TestTeam",
                "bridge": "TestBridge"
            },
            # Create queue item response
            {
                "success": True,
                "taskId": "task-123",
                "status": "PENDING"
            },
            # Get queue status response
            {
                "success": True,
                "taskId": "task-123",
                "status": "COMPLETED",
                "result": "Success"
            }
        ]
    
    @staticmethod
    def get_test_config() -> Dict[str, Any]:
        """Get test configuration"""
        return {
            "api_url": os.environ.get("TEST_API_URL", "https://api.test.rediacc.com"),
            "timeout": 30,
            "retry_count": 3,
            "parallel_workers": 4,
            "cleanup_on_exit": True,
            "auth": {
                "username": os.environ.get("TEST_USERNAME", None),
                "password": os.environ.get("TEST_PASSWORD", None)
            },
            "defaults": {
                "company": "TestCompany",
                "region": "us-east-1"
            }
        }