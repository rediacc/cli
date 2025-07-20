"""
Test runner with dependency resolution and parallel execution support.
"""

import asyncio
import time
import logging
import json
from typing import Dict, List, Set, Optional, Any, Tuple
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
import threading
from pathlib import Path

from .base import TestContext, TestScenario, TestResult, TestStatus, BaseTest
from .entities import EntityType, EntityDependencies
from .cli_wrapper import CLIWrapper


# Entity verification configuration
ENTITY_VERIFICATION_CONFIG = {
    "team": {
        "method": "list",
        "list_command": "teams",
        "name_field": "teamName",
        "required_params": []
    },
    "region": {
        "method": "list",
        "list_command": "regions", 
        "name_field": "regionName",
        "required_params": []
    },
    "bridge": {
        "method": "list",
        "list_command": "bridges",
        "name_field": "bridgeName",
        "required_params": ["region"],
        "list_params": {"region": "region"}
    },
    "schedule": {
        "method": "list",
        "list_command": "team-schedules",
        "name_field": "scheduleName",
        "required_params": ["team"],
        "list_params": {"team": "team"}
    },
    "storage": {
        "method": "list",
        "list_command": "team-storages",
        "name_field": "storageName",
        "required_params": ["team"],
        "list_params": {"team": "team"}
    },
    "machine": {
        "method": "mixed",  # Can use both inspect and list
        "list_command": "team-machines",
        "name_field": "machineName",
        "alternate_name_fields": ["name"],
        "required_params": ["team"],
        "list_params": {"team": "team"}
    },
    "repository": {
        "method": "inspect",
        "required_params": ["team"]
    }
}


class DependencyGraph:
    """
    Manages test dependencies and determines execution order.
    """
    
    def __init__(self):
        self.nodes: Dict[str, TestScenario] = {}
        self.edges: Dict[str, Set[str]] = defaultdict(set)  # node -> dependencies
        self.reverse_edges: Dict[str, Set[str]] = defaultdict(set)  # node -> dependents
    
    def add_test(self, test: TestScenario):
        """Add a test to the dependency graph"""
        self.nodes[test.id] = test
        
        # Add edges based on entity dependencies
        for entity_type in test.get_required_entities():
            try:
                entity_enum = EntityType(entity_type)
                deps = EntityDependencies.get_dependencies(entity_enum)
                
                # Find tests that provide these dependencies
                for dep in deps:
                    for other_id, other_test in self.nodes.items():
                        if other_id != test.id and dep.value in other_test.get_required_entities():
                            self.edges[test.id].add(other_id)
                            self.reverse_edges[other_id].add(test.id)
            except ValueError:
                # Unknown entity type, skip
                pass
    
    def get_execution_order(self) -> List[List[str]]:
        """
        Get tests in execution order. Returns list of batches where
        each batch contains tests that can run in parallel.
        """
        # Kahn's algorithm for topological sort with levels
        in_degree = {node: len(self.edges[node]) for node in self.nodes}
        queue = [node for node in self.nodes if in_degree[node] == 0]
        
        batches = []
        
        while queue:
            # Current batch - all nodes with no dependencies
            current_batch = queue[:]
            batches.append(current_batch)
            
            # Process batch and update degrees
            next_queue = []
            for node in current_batch:
                for dependent in self.reverse_edges[node]:
                    in_degree[dependent] -= 1
                    if in_degree[dependent] == 0:
                        next_queue.append(dependent)
            
            queue = next_queue
        
        # Check for cycles
        if sum(len(batch) for batch in batches) != len(self.nodes):
            raise ValueError("Circular dependency detected in tests")
        
        return batches
    
    def get_cleanup_order(self) -> List[str]:
        """Get cleanup order (reverse of creation)"""
        batches = self.get_execution_order()
        cleanup_order = []
        
        # Reverse the batches and flatten
        for batch in reversed(batches):
            cleanup_order.extend(reversed(batch))
        
        return cleanup_order


class TestRunner:
    """
    Main test runner that executes tests with proper dependency resolution
    and parallel execution support.
    """
    
    def __init__(self, 
                 context: TestContext,
                 cli_wrapper: Optional[CLIWrapper] = None,
                 parallel_workers: int = 4,
                 continue_on_failure: bool = False,
                 cleanup_on_failure: bool = True,
                 verbose_on_error: bool = False):
        
        self.context = context
        self.cli = cli_wrapper or CLIWrapper()
        self.parallel_workers = parallel_workers
        self.continue_on_failure = continue_on_failure
        self.cleanup_on_failure = cleanup_on_failure
        self.verbose_on_error = verbose_on_error
        
        self.logger = logging.getLogger(self.__class__.__name__)
        self.results: Dict[str, TestResult] = {}
        self.lock = threading.Lock()
        
        # Track resources for cleanup
        self.created_resources: List[Tuple[str, str, Dict[str, Any]]] = []
        
        # Track failed tests for verbose re-run
        self.failed_tests_for_rerun: List[TestScenario] = []
    
    async def run_tests(self, tests: List[TestScenario]) -> Dict[str, TestResult]:
        """Run a collection of tests with dependency resolution"""
        
        # Build dependency graph
        graph = DependencyGraph()
        for test in tests:
            graph.add_test(test)
        
        # Get execution order
        try:
            batches = graph.get_execution_order()
        except ValueError as e:
            self.logger.error(f"Dependency resolution failed: {e}")
            return {}
        
        self.logger.info(f"Executing {len(tests)} tests in {len(batches)} batches")
        
        # Execute batches
        for i, batch in enumerate(batches):
            self.logger.info(f"Executing batch {i+1}/{len(batches)}: {batch}")
            
            # Check if we should continue based on previous failures
            if not self.continue_on_failure and any(
                r.status == TestStatus.FAILED for r in self.results.values()
            ):
                self.logger.warning("Stopping execution due to previous failures")
                break
            
            # Run batch in parallel
            await self._run_batch(batch, graph.nodes)
        
        # Cleanup if enabled
        if self.cleanup_on_failure or all(
            r.status == TestStatus.PASSED for r in self.results.values()
        ):
            await self._cleanup_resources(graph.get_cleanup_order(), graph.nodes)
        
        # If verbose-on-error is enabled and we have failed tests, re-run them with verbose output
        if self.verbose_on_error and self.failed_tests_for_rerun:
            await self._rerun_failed_tests_verbose()
        
        return self.results
    
    async def _run_batch(self, batch: List[str], all_tests: Dict[str, TestScenario]):
        """Run a batch of tests in parallel"""
        tasks = []
        
        for test_id in batch:
            test = all_tests[test_id]
            
            # Check if dependencies passed
            deps_failed = any(
                self.results.get(dep_id, TestResult(dep_id, "", TestStatus.PENDING)).status == TestStatus.FAILED
                for dep_id in test.dependencies.values()
            )
            
            if deps_failed:
                # Skip test if dependencies failed
                result = TestResult(
                    test_id=test_id,
                    name=test.name,
                    status=TestStatus.SKIPPED,
                    message="Skipped due to dependency failure"
                )
                self.results[test_id] = result
                continue
            
            # Run test
            if test.parallel and self.parallel_workers > 1:
                task = asyncio.create_task(self._run_single_test(test))
                tasks.append(task)
            else:
                # Run sequentially
                await self._run_single_test(test)
        
        # Wait for parallel tasks
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
    
    async def _run_single_test(self, test: TestScenario) -> TestResult:
        """Run a single test scenario"""
        result = TestResult(
            test_id=test.id,
            name=test.name,
            status=TestStatus.RUNNING
        )
        
        result.metrics.start()
        
        try:
            self.logger.info(f"Starting test: {test.name}")
            
            # Setup phase
            for setup_action in test.setup:
                await self._execute_setup_action(setup_action)
            
            # Execute test steps
            for step in test.steps:
                step_result = await self._execute_step(step, test)
                
                # Capture variables
                if step.capture and isinstance(step_result, dict):
                    for var_name, json_path in step.capture.items():
                        value = self._extract_json_path(step_result, json_path)
                        self.context.set_var(var_name, value)
                
                # Track created resources
                if step.action == "create" and step_result.get("success"):
                    # Get the interpolated params
                    interpolated_params = self.context.interpolate_dict(step.params)
                    resource_id = interpolated_params.get("name", step_result.get("id"))
                    self._track_resource(step.entity, resource_id, step_result)
            
            result.status = TestStatus.PASSED
            result.message = "Test completed successfully"
            
        except Exception as e:
            result.status = TestStatus.FAILED
            result.error = e
            result.message = str(e)
            self.logger.error(f"Test {test.name} failed: {e}")
            
            # Track failed test for potential verbose re-run
            if self.verbose_on_error and not self.cli.verbose:
                with self.lock:
                    self.failed_tests_for_rerun.append(test)
        
        finally:
            result.metrics.stop()
            
            # Store result
            with self.lock:
                self.results[test.id] = result
        
        return result
    
    async def _execute_setup_action(self, action: Dict[str, Any]):
        """Execute a setup action"""
        action_type = list(action.keys())[0]
        
        if action_type.startswith("create_random_"):
            # Generate name using shared test_run_id and counter
            var_name = action[action_type]
            prefix = action_type.replace("create_random_", "").replace("_name", "")
            
            # Get and increment the counter for this entity type
            counter_name = f"{prefix}_counter"
            counter = self.context.get_var(counter_name, 0) + 1
            self.context.set_var(counter_name, counter)
            
            # Create name with format: prefix_counter_testrunid
            test_run_id = self.context.get_var('test_run_id')
            value = f"{prefix}_{counter}_{test_run_id}"
            
            self.context.set_var(var_name, value)
            self.logger.debug(f"Generated {var_name} = {value}")
        
        elif action_type == "set_var":
            # Set variable
            for key, value in action.items():
                if key != "set_var":
                    self.context.set_var(key, value)
    
    async def _execute_step(self, step, test: TestScenario) -> Dict[str, Any]:
        """Execute a single test step"""
        # Interpolate parameters
        params = self.context.interpolate_dict(step.params)
        
        # Execute based on action
        if step.action == "create":
            return await self._execute_create(step.entity, params)
        
        elif step.action == "verify":
            return await self._execute_verify(step.entity, params, step.expect)
        
        elif step.action == "update":
            return await self._execute_update(step.entity, params)
        
        elif step.action == "delete":
            return await self._execute_delete(step.entity, params)
        
        elif step.action == "wait":
            await asyncio.sleep(params.get("seconds", 1))
            return {"success": True}
        
        elif step.action == "execute_raw":
            return await self._execute_raw(params)
        
        else:
            raise ValueError(f"Unknown action: {step.action}")
    
    async def _execute_create(self, entity_type: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute create action"""
        # Use thread pool for sync CLI calls
        loop = asyncio.get_event_loop()
        # Create a lambda to handle kwargs
        create_func = lambda: self.cli.create(entity_type, **params)
        result = await loop.run_in_executor(None, create_func)
        
        # Log the result for debugging
        if not result.get("success"):
            self.logger.error(f"Create {entity_type} failed: {result.get('error', 'Unknown error')}")
        else:
            self.logger.debug(f"Create {entity_type} succeeded: {params.get('name', 'unnamed')}")
        
        return result
    
    async def _verify_via_list(self, entity_type: str, name: str, params: Dict[str, Any], 
                              config: Dict[str, Any]) -> Dict[str, Any]:
        """Verify entity existence using list operation"""
        loop = asyncio.get_event_loop()
        
        # Build list parameters
        list_kwargs = {}
        if "list_params" in config:
            for param_key, param_name in config["list_params"].items():
                if param_key in params:
                    list_kwargs[param_name] = params[param_key]
        
        # Execute list command
        list_func = lambda: self.cli.list(config["list_command"], **list_kwargs)
        result = await loop.run_in_executor(None, list_func)
        
        if not result.get("success"):
            raise AssertionError(f"Failed to list {config['list_command']}")
        
        # Find the specific entity in the list
        items = result.get("data", [])
        found_item = None
        name_field = config.get("name_field")
        alternate_fields = config.get("alternate_name_fields", [])
        
        for item in items:
            # Check primary name field
            if name_field and item.get(name_field) == name:
                found_item = item
                break
            # Check alternate name fields
            for alt_field in alternate_fields:
                if item.get(alt_field) == name:
                    found_item = item
                    break
            if found_item:
                break
        
        if not found_item:
            # Build helpful error message
            existing_names = []
            if name_field:
                existing_names = [item.get(name_field) for item in items if item.get(name_field)]
            raise AssertionError(f"{entity_type.capitalize()} {name} not found. Available: {existing_names}")
        
        return {"success": True, **found_item}
    
    async def _verify_via_inspect(self, entity_type: str, name: str, params: Dict[str, Any], 
                                 config: Dict[str, Any]) -> Dict[str, Any]:
        """Verify entity existence using inspect/get operation"""
        loop = asyncio.get_event_loop()
        
        # Build get parameters
        get_kwargs = {}
        for param in config.get("required_params", []):
            if param in params:
                get_kwargs[param] = params[param]
        
        # Execute get command
        get_func = lambda: self.cli.get(entity_type, name, **get_kwargs)
        result = await loop.run_in_executor(None, get_func)
        
        if not result.get("success"):
            raise AssertionError(f"Failed to get {entity_type} {name}")
        
        # Handle cases where data is returned as an array
        if isinstance(result.get("data"), list) and len(result["data"]) > 0:
            result.update(result["data"][0])
        
        return result
    
    async def _execute_verify(self, entity_type: str, params: Dict[str, Any], 
                             expect: Dict[str, Any]) -> Dict[str, Any]:
        """Execute verify action using configuration-based approach"""
        # Get entity name
        name = params.get("name")
        if not name:
            raise ValueError("Name required for verify action")
        
        # Get entity configuration
        config = ENTITY_VERIFICATION_CONFIG.get(entity_type)
        if not config:
            raise ValueError(f"Unknown entity type for verification: {entity_type}")
        
        # Validate required parameters
        for param in config.get("required_params", []):
            if param not in params:
                raise ValueError(f"{param} required for {entity_type} verification")
        
        # Determine verification method
        method = config.get("method", "inspect")
        
        # Use list method for certain entities or when explicitly requested
        if method == "list" or (method == "mixed" and params.get("use_list", False)):
            result = await self._verify_via_list(entity_type, name, params, config)
        else:
            result = await self._verify_via_inspect(entity_type, name, params, config)
        
        # Verify expectations (interpolate expected values)
        interpolated_expect = self.context.interpolate_dict(expect)
        for key, expected in interpolated_expect.items():
            # Skip checking 'success' as it's not a team property
            if key == "success":
                continue
            actual = result.get(key)
            if actual != expected:
                raise AssertionError(f"Expected {key}={expected}, got {actual}")
        
        return result
    
    async def _execute_update(self, entity_type: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute update action"""
        loop = asyncio.get_event_loop()
        name = params.pop("name", None)
        if not name:
            raise ValueError("Name required for update action")
        
        update_func = lambda: self.cli.update(entity_type, name, **params)
        return await loop.run_in_executor(None, update_func)
    
    async def _execute_delete(self, entity_type: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute delete action"""
        loop = asyncio.get_event_loop()
        name = params.get("name")
        if not name:
            raise ValueError("Name required for delete action")
        
        delete_func = lambda: self.cli.delete(entity_type, name)
        return await loop.run_in_executor(None, delete_func)
    
    async def _execute_raw(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute raw CLI command"""
        args = params.get('args', [])
        stdin = params.get('stdin')
        output_json = params.get('output_json', True)
        
        loop = asyncio.get_event_loop()
        raw_func = lambda: self.cli.execute_raw(args, output_json=output_json, stdin=stdin)
        result = await loop.run_in_executor(None, raw_func)
        
        if result.get('success'):
            self.logger.info(f"Executed raw command: {' '.join(args)}")
        else:
            self.logger.error(f"Raw command failed: {' '.join(args)}")
        
        return result
    
    def _extract_json_path(self, data: Dict[str, Any], path: str) -> Any:
        """Extract value from JSON using simple path (e.g., $.id or $.data.name)"""
        if path.startswith("$"):
            path = path[1:]
        
        if path.startswith("."):
            path = path[1:]
        
        parts = path.split(".")
        current = data
        
        for part in parts:
            if isinstance(current, dict) and part in current:
                current = current[part]
            else:
                return None
        
        return current
    
    def _track_resource(self, entity_type: str, resource_id: str, data: Dict[str, Any]):
        """Track created resource for cleanup"""
        with self.lock:
            self.created_resources.append((entity_type, resource_id, data))
            self.context.track_resource(entity_type, resource_id, data)
    
    async def _cleanup_resources(self, cleanup_order: List[str], all_tests: Dict[str, TestScenario]):
        """Clean up resources in proper order"""
        self.logger.info("Starting cleanup phase")
        
        # Group resources by test
        test_resources = defaultdict(list)
        for entity_type, resource_id, data in self.created_resources:
            # Find which test created this resource
            for test_id, test in all_tests.items():
                for step in test.steps:
                    if (step.action == "create" and 
                        step.entity == entity_type and
                        step.params.get("name") == resource_id):
                        test_resources[test_id].append((entity_type, resource_id))
                        break
        
        # Clean up in order
        for test_id in cleanup_order:
            test = all_tests.get(test_id)
            if not test or test.skip_cleanup:
                continue
            
            # Run test's cleanup steps
            for cleanup_step in test.cleanup:
                try:
                    # Check if the step can be executed (all variables exist)
                    # Try to interpolate params to see if variables exist
                    try:
                        self.context.interpolate_dict(cleanup_step.params)
                        # If interpolation succeeded, execute the step
                        await self._execute_step(cleanup_step, test)
                    except ValueError as ve:
                        # Variable not found - skip this cleanup step
                        self.logger.debug(f"Skipping cleanup step for {test.name}: {ve}")
                except Exception as e:
                    self.logger.error(f"Cleanup failed for {test.name}: {e}")
            
            # Clean up tracked resources
            for entity_type, resource_id in test_resources.get(test_id, []):
                try:
                    await self._execute_delete(entity_type, {"name": resource_id})
                    self.logger.info(f"Cleaned up {entity_type}/{resource_id}")
                except Exception as e:
                    self.logger.error(f"Failed to cleanup {entity_type}/{resource_id}: {e}")
    
    async def _rerun_failed_tests_verbose(self):
        """Re-run failed tests with verbose output for debugging"""
        self.logger.info("\n" + "=" * 60)
        self.logger.info("RE-RUNNING FAILED TESTS WITH VERBOSE OUTPUT")
        self.logger.info("=" * 60)
        
        # Save original verbose state
        original_verbose = self.cli.verbose
        
        try:
            # Enable verbose mode
            self.cli.verbose = True
            
            for test in self.failed_tests_for_rerun:
                self.logger.info(f"\nRe-running test with verbose output: {test.name}")
                self.logger.info("-" * 60)
                
                # Create a new result for the verbose re-run (don't overwrite the original)
                verbose_result = TestResult(
                    test_id=f"{test.id}_verbose",
                    name=f"{test.name} (verbose re-run)",
                    status=TestStatus.RUNNING
                )
                
                verbose_result.metrics.start()
                
                try:
                    # Re-run the test with verbose output
                    # Note: We don't update self.results here to preserve the original failure
                    
                    # Setup phase
                    for setup_action in test.setup:
                        await self._execute_setup_action(setup_action)
                    
                    # Execute test steps
                    for step in test.steps:
                        step_result = await self._execute_step(step, test)
                        
                        # Capture variables
                        if step.capture and isinstance(step_result, dict):
                            for var_name, json_path in step.capture.items():
                                value = self._extract_json_path(step_result, json_path)
                                self.context.set_var(var_name, value)
                    
                    self.logger.info(f"Verbose re-run of {test.name} completed successfully")
                    
                except Exception as e:
                    self.logger.error(f"Verbose re-run of {test.name} failed with: {e}")
                
                finally:
                    verbose_result.metrics.stop()
                    self.logger.info(f"Verbose re-run duration: {verbose_result.metrics.duration:.2f}s")
                    self.logger.info("-" * 60)
            
        finally:
            # Restore original verbose state
            self.cli.verbose = original_verbose
            
        self.logger.info("\n" + "=" * 60)
        self.logger.info("VERBOSE RE-RUN COMPLETE")
        self.logger.info("=" * 60 + "\n")