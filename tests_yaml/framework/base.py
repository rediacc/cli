"""
Base classes for the Rediacc CLI test framework.
"""

import json
import time
import uuid
import logging
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional, Set
from enum import Enum
from datetime import datetime
import os
import re


class TestStatus(Enum):
    """Test execution status"""
    PENDING = "pending"
    RUNNING = "running"
    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"
    ERROR = "error"


@dataclass
class TestMetrics:
    """Performance metrics for test execution"""
    start_time: float = 0
    end_time: float = 0
    duration: float = 0
    api_calls: int = 0
    retries: int = 0
    
    def start(self):
        self.start_time = time.time()
    
    def stop(self):
        self.end_time = time.time()
        self.duration = self.end_time - self.start_time


@dataclass
class TestResult:
    """Result of a test execution"""
    test_id: str
    name: str
    status: TestStatus
    message: str = ""
    error: Optional[Exception] = None
    metrics: TestMetrics = field(default_factory=TestMetrics)
    stdout: str = ""
    stderr: str = ""
    captured_data: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'test_id': self.test_id,
            'name': self.name,
            'status': self.status.value,
            'message': self.message,
            'error': str(self.error) if self.error else None,
            'duration': self.metrics.duration,
            'api_calls': self.metrics.api_calls,
            'captured_data': self.captured_data
        }


class TestContext:
    """
    Manages test execution context including variables, authentication, and state.
    """
    
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self.variables: Dict[str, Any] = {}
        self.created_resources: List[Dict[str, Any]] = []
        self.auth_token: Optional[str] = None
        self.master_password: Optional[str] = None
        self.logger = logging.getLogger(self.__class__.__name__)
        
        # Load environment variables
        self._load_env_vars()
        
        # Initialize with defaults
        self.variables.update(self.config.get('defaults', {}))
    
    def _load_env_vars(self):
        """Load environment variables with TEST_ prefix"""
        for key, value in os.environ.items():
            if key.startswith('TEST_'):
                var_name = key[5:].lower()
                self.variables[var_name] = value
    
    def set_var(self, name: str, value: Any):
        """Set a variable in the context"""
        self.variables[name] = value
        self.logger.debug(f"Set variable {name} = {value}")
    
    def get_var(self, name: str, default: Any = None) -> Any:
        """Get a variable from the context"""
        return self.variables.get(name, default)
    
    def interpolate(self, text: str) -> str:
        """Interpolate variables in text using {{ variable }} syntax"""
        if not isinstance(text, str):
            return text
            
        pattern = r'\{\{\s*(\w+)\s*\}\}'
        
        def replacer(match):
            var_name = match.group(1)
            value = self.get_var(var_name)
            if value is None:
                raise ValueError(f"Variable '{var_name}' not found in context")
            return str(value)
        
        return re.sub(pattern, replacer, text)
    
    def interpolate_dict(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Recursively interpolate variables in a dictionary"""
        if not isinstance(data, dict):
            return data
            
        result = {}
        for key, value in data.items():
            if isinstance(value, str):
                result[key] = self.interpolate(value)
            elif isinstance(value, dict):
                result[key] = self.interpolate_dict(value)
            elif isinstance(value, list):
                result[key] = [self.interpolate_dict(item) if isinstance(item, dict) 
                              else self.interpolate(item) if isinstance(item, str)
                              else item for item in value]
            else:
                result[key] = value
        return result
    
    def track_resource(self, entity_type: str, entity_id: str, data: Dict[str, Any] = None):
        """Track a created resource for cleanup"""
        resource = {
            'type': entity_type,
            'id': entity_id,
            'data': data or {},
            'created_at': datetime.utcnow().isoformat()
        }
        self.created_resources.append(resource)
        self.logger.info(f"Tracked resource: {entity_type}/{entity_id}")
    
    def get_cleanup_order(self) -> List[Dict[str, Any]]:
        """Get resources in reverse creation order for cleanup"""
        return list(reversed(self.created_resources))


@dataclass
class TestStep:
    """Individual test operation"""
    action: str  # create, update, delete, verify, wait, etc.
    entity: str = ""  # team, machine, repository, etc. (optional for some actions)
    params: Dict[str, Any] = field(default_factory=dict)
    expect: Dict[str, Any] = field(default_factory=dict)
    capture: Dict[str, str] = field(default_factory=dict)  # {var_name: json_path}
    retry: int = 0
    timeout: int = 30
    parallel: bool = False  # Whether this step can run in parallel with others
    continue_on_error: bool = False  # Whether to continue if this step fails
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'action': self.action,
            'entity': self.entity,
            'params': self.params,
            'expect': self.expect,
            'capture': self.capture,
            'retry': self.retry,
            'timeout': self.timeout
        }


@dataclass
class TestScenario:
    """Collection of test steps forming a complete test"""
    id: str
    name: str
    description: str = ""
    tags: List[str] = field(default_factory=list)
    dependencies: Dict[str, str] = field(default_factory=dict)
    setup: List[Dict[str, Any]] = field(default_factory=list)
    steps: List[TestStep] = field(default_factory=list)
    cleanup: List[TestStep] = field(default_factory=list)
    skip_cleanup: bool = False
    parallel: bool = False
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'TestScenario':
        """Create TestScenario from dictionary"""
        scenario = cls(
            id=data.get('id', str(uuid.uuid4())),
            name=data['name'],
            description=data.get('description', ''),
            tags=data.get('tags', []),
            dependencies=data.get('dependencies', {}),
            skip_cleanup=data.get('skip_cleanup', False),
            parallel=data.get('parallel', False)
        )
        
        # Parse setup
        scenario.setup = data.get('setup', [])
        
        # Parse steps
        for step_data in data.get('steps', []):
            step = TestStep(**step_data)
            scenario.steps.append(step)
        
        # Parse cleanup
        for cleanup_data in data.get('cleanup', []):
            step = TestStep(**cleanup_data)
            scenario.cleanup.append(step)
        
        return scenario
    
    def get_required_entities(self) -> Set[str]:
        """Get all entity types required by this scenario"""
        entities = set()
        
        # From dependencies
        entities.update(self.dependencies.keys())
        
        # From steps
        for step in self.steps + self.cleanup:
            entities.add(step.entity)
            
        return entities


class BaseTest:
    """
    Base class for Python-based tests. Provides common functionality
    for test execution, resource management, and assertions.
    """
    
    # Class-level configuration
    dependencies: List[str] = []
    tags: List[str] = []
    timeout: int = 300
    parallel: bool = True
    
    def __init__(self, context: TestContext, cli_wrapper=None):
        self.context = context
        self.cli = cli_wrapper
        self.logger = logging.getLogger(self.__class__.__name__)
        self.test_id = str(uuid.uuid4())
        self._cleanup_actions = []
    
    async def setup(self):
        """Setup method called before test execution"""
        pass
    
    async def teardown(self):
        """Teardown method called after test execution"""
        for action in reversed(self._cleanup_actions):
            try:
                await action()
            except Exception as e:
                self.logger.error(f"Cleanup error: {e}")
    
    def random_name(self, prefix: str = "test") -> str:
        """Generate a random name with prefix"""
        suffix = str(uuid.uuid4())[:8]
        return f"{prefix}_{suffix}"
    
    async def create_entity(self, entity_type: str, **params) -> Dict[str, Any]:
        """Create an entity and track it for cleanup"""
        result = await self.cli.create(entity_type, **params)
        
        # Track for cleanup
        entity_id = params.get('name', result.get('id', 'unknown'))
        self.context.track_resource(entity_type, entity_id, result)
        
        # Add cleanup action
        self._cleanup_actions.append(
            lambda: self.cli.delete(entity_type, name=entity_id)
        )
        
        return result
    
    async def wait_for_condition(self, check_func, timeout: int = 60, interval: int = 2):
        """Wait for a condition to become true"""
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            if await check_func():
                return True
            await self._sleep(interval)
        
        raise TimeoutError(f"Condition not met within {timeout} seconds")
    
    async def _sleep(self, seconds: float):
        """Async sleep"""
        import asyncio
        await asyncio.sleep(seconds)
    
    def assert_equal(self, actual, expected, message: str = ""):
        """Assert equality with descriptive message"""
        if actual != expected:
            msg = f"Expected {expected}, got {actual}"
            if message:
                msg = f"{message}: {msg}"
            raise AssertionError(msg)
    
    def assert_in(self, item, container, message: str = ""):
        """Assert item in container"""
        if item not in container:
            msg = f"{item} not found in {container}"
            if message:
                msg = f"{message}: {msg}"
            raise AssertionError(msg)
    
    def assert_response_success(self, response: Dict[str, Any]):
        """Assert API response indicates success"""
        if not response.get('success', False):
            error = response.get('error', 'Unknown error')
            raise AssertionError(f"API call failed: {error}")