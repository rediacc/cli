"""
YAML test definition parser and loader.
Supports both YAML and Python test definitions.
"""

import yaml
import json
import importlib.util
import sys
from pathlib import Path
from typing import Dict, Any, List, Optional, Union
import logging

try:
    from .base import TestScenario, TestStep, BaseTest
    from .entities import EntityType
except ImportError:
    from base import TestScenario, TestStep, BaseTest
    from entities import EntityType


class TestLoader:
    """
    Loads test definitions from YAML files and Python modules.
    """
    
    def __init__(self, test_dirs: Optional[List[Path]] = None):
        self.test_dirs = test_dirs or [Path(__file__).parent.parent / "tests"]
        self.logger = logging.getLogger(self.__class__.__name__)
        self._loaded_tests: Dict[str, TestScenario] = {}
    
    def load_all_tests(self, tags: Optional[List[str]] = None) -> List[TestScenario]:
        """Load all tests from configured directories"""
        tests = []
        
        for test_dir in self.test_dirs:
            if not test_dir.exists():
                self.logger.warning(f"Test directory not found: {test_dir}")
                continue
            
            # Load YAML tests
            for yaml_file in test_dir.glob("**/*.yaml"):
                try:
                    yaml_tests = self.load_yaml_file(yaml_file)
                    tests.extend(yaml_tests)
                except Exception as e:
                    self.logger.error(f"Failed to load {yaml_file}: {e}")
            
            for yml_file in test_dir.glob("**/*.yml"):
                try:
                    yml_tests = self.load_yaml_file(yml_file)
                    tests.extend(yml_tests)
                except Exception as e:
                    self.logger.error(f"Failed to load {yml_file}: {e}")
            
            # Load Python tests
            for py_file in test_dir.glob("**/test_*.py"):
                try:
                    py_tests = self.load_python_file(py_file)
                    tests.extend(py_tests)
                except Exception as e:
                    self.logger.error(f"Failed to load {py_file}: {e}")
        
        # Filter by tags if specified
        if tags:
            tests = [t for t in tests if any(tag in t.tags for tag in tags)]
        
        self.logger.info(f"Loaded {len(tests)} tests")
        return tests
    
    def load_yaml_file(self, file_path: Path) -> List[TestScenario]:
        """Load tests from a YAML file"""
        self.logger.debug(f"Loading YAML file: {file_path}")
        
        with open(file_path, 'r') as f:
            data = yaml.safe_load(f)
        
        if not data:
            return []
        
        # Handle single test or list of tests
        if isinstance(data, list):
            tests = []
            for test_data in data:
                test = self._parse_yaml_test(test_data, file_path)
                if test:
                    tests.append(test)
            return tests
        else:
            test = self._parse_yaml_test(data, file_path)
            return [test] if test else []
    
    def _parse_yaml_test(self, data: Dict[str, Any], source_file: Path) -> Optional[TestScenario]:
        """Parse a single YAML test definition"""
        try:
            # Validate required fields
            if 'name' not in data:
                self.logger.error(f"Test missing 'name' field in {source_file}")
                return None
            
            # Generate ID if not provided
            if 'id' not in data:
                data['id'] = f"{source_file.stem}_{data['name'].lower().replace(' ', '_')}"
            
            # Parse the test scenario
            test = TestScenario.from_dict(data)
            
            # Add source file info
            test.tags.append(f"source:{source_file.stem}")
            
            # Validate entity types (skip for special actions)
            for step in test.steps + test.cleanup:
                if step.action in ['wait', 'sleep', 'log', 'set_var', 'execute_raw']:
                    continue  # These actions don't need entity types
                try:
                    EntityType(step.entity)
                except ValueError:
                    self.logger.warning(f"Unknown entity type '{step.entity}' in test '{test.name}'")
            
            return test
            
        except Exception as e:
            self.logger.error(f"Failed to parse test from {source_file}: {e}")
            return None
    
    def load_python_file(self, file_path: Path) -> List[TestScenario]:
        """Load tests from a Python file"""
        self.logger.debug(f"Loading Python file: {file_path}")
        
        # Load module dynamically
        spec = importlib.util.spec_from_file_location(file_path.stem, file_path)
        if not spec or not spec.loader:
            return []
        
        module = importlib.util.module_from_spec(spec)
        sys.modules[file_path.stem] = module
        spec.loader.exec_module(module)
        
        tests = []
        
        # Find all test classes
        for name in dir(module):
            obj = getattr(module, name)
            
            # Check if it's a test class
            if (isinstance(obj, type) and 
                issubclass(obj, BaseTest) and 
                obj is not BaseTest):
                
                # Convert to TestScenario
                test = self._convert_python_test(obj, file_path)
                if test:
                    tests.append(test)
        
        return tests
    
    def _convert_python_test(self, test_class: type, source_file: Path) -> Optional[TestScenario]:
        """Convert a Python test class to TestScenario"""
        try:
            # Create test scenario
            test = TestScenario(
                id=f"{source_file.stem}_{test_class.__name__}",
                name=test_class.__name__,
                description=test_class.__doc__ or "",
                tags=getattr(test_class, 'tags', []) + [f"source:{source_file.stem}", "python"],
                dependencies={},  # Python tests manage their own dependencies
                parallel=getattr(test_class, 'parallel', True)
            )
            
            # Note: Python tests execute their own logic, so we don't parse steps
            # The runner will detect Python tests and execute them differently
            
            return test
            
        except Exception as e:
            self.logger.error(f"Failed to convert Python test {test_class.__name__}: {e}")
            return None
    
    def load_test_file(self, file_path: Union[str, Path]) -> List[TestScenario]:
        """Load tests from a specific file"""
        path = Path(file_path)
        
        if not path.exists():
            raise FileNotFoundError(f"Test file not found: {path}")
        
        if path.suffix in ['.yaml', '.yml']:
            return self.load_yaml_file(path)
        elif path.suffix == '.py':
            return self.load_python_file(path)
        else:
            raise ValueError(f"Unsupported file type: {path.suffix}")
    
    def validate_test(self, test: TestScenario) -> List[str]:
        """Validate a test scenario and return list of errors"""
        errors = []
        
        # Check for required fields
        if not test.name:
            errors.append("Test must have a name")
        
        if not test.steps:
            errors.append("Test must have at least one step")
        
        # Validate steps
        for i, step in enumerate(test.steps):
            if not step.action:
                errors.append(f"Step {i+1} missing action")
            
            if not step.entity:
                errors.append(f"Step {i+1} missing entity")
            
            # Validate entity type
            try:
                EntityType(step.entity)
            except ValueError:
                errors.append(f"Step {i+1} has unknown entity type: {step.entity}")
            
            # Validate action
            valid_actions = ['create', 'update', 'delete', 'verify', 'wait', 'execute_raw']
            if step.action not in valid_actions:
                errors.append(f"Step {i+1} has invalid action: {step.action}")
        
        # Validate dependencies
        for dep_name, dep_value in test.dependencies.items():
            try:
                EntityType(dep_name)
            except ValueError:
                errors.append(f"Unknown dependency type: {dep_name}")
        
        return errors


class YAMLTestBuilder:
    """
    Helper class to build YAML test definitions programmatically.
    """
    
    def __init__(self, name: str):
        self.test = {
            'name': name,
            'steps': [],
            'cleanup': []
        }
    
    def description(self, desc: str) -> 'YAMLTestBuilder':
        self.test['description'] = desc
        return self
    
    def tags(self, *tags: str) -> 'YAMLTestBuilder':
        self.test['tags'] = list(tags)
        return self
    
    def depends_on(self, **dependencies) -> 'YAMLTestBuilder':
        self.test['dependencies'] = dependencies
        return self
    
    def setup_var(self, var_name: str, value: Any) -> 'YAMLTestBuilder':
        if 'setup' not in self.test:
            self.test['setup'] = []
        self.test['setup'].append({f'set_var': var_name, 'value': value})
        return self
    
    def setup_random(self, var_name: str, prefix: str = "test") -> 'YAMLTestBuilder':
        if 'setup' not in self.test:
            self.test['setup'] = []
        self.test['setup'].append({f'create_random_{prefix}_name': var_name})
        return self
    
    def create(self, entity: str, **params) -> 'YAMLTestBuilder':
        step = {
            'action': 'create',
            'entity': entity,
            'params': params
        }
        self.test['steps'].append(step)
        return self
    
    def verify(self, entity: str, name: str, **expect) -> 'YAMLTestBuilder':
        step = {
            'action': 'verify',
            'entity': entity,
            'params': {'name': name},
            'expect': expect
        }
        self.test['steps'].append(step)
        return self
    
    def update(self, entity: str, name: str, **params) -> 'YAMLTestBuilder':
        step = {
            'action': 'update',
            'entity': entity,
            'params': {'name': name, **params}
        }
        self.test['steps'].append(step)
        return self
    
    def delete(self, entity: str, name: str) -> 'YAMLTestBuilder':
        step = {
            'action': 'delete',
            'entity': entity,
            'params': {'name': name}
        }
        self.test['steps'].append(step)
        return self
    
    def cleanup_delete(self, entity: str, name: str) -> 'YAMLTestBuilder':
        step = {
            'action': 'delete',
            'entity': entity,
            'params': {'name': name}
        }
        self.test['cleanup'].append(step)
        return self
    
    def capture(self, var_name: str, json_path: str) -> 'YAMLTestBuilder':
        if self.test['steps']:
            last_step = self.test['steps'][-1]
            if 'capture' not in last_step:
                last_step['capture'] = {}
            last_step['capture'][var_name] = json_path
        return self
    
    def expect(self, **expectations) -> 'YAMLTestBuilder':
        if self.test['steps']:
            last_step = self.test['steps'][-1]
            if 'expect' not in last_step:
                last_step['expect'] = {}
            last_step['expect'].update(expectations)
        return self
    
    def to_yaml(self) -> str:
        """Convert to YAML string"""
        return yaml.dump(self.test, default_flow_style=False, sort_keys=False)
    
    def to_dict(self) -> Dict[str, Any]:
        """Get the test dictionary"""
        return self.test.copy()