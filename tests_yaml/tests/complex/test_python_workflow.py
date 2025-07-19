"""
Python-based test for complex workflows that require more control.
"""

import asyncio
from typing import Dict, Any
import time

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from framework.base import BaseTest


class TestAdvancedWorkflow(BaseTest):
    """
    Tests advanced workflow with conditional logic and complex verifications.
    This demonstrates capabilities beyond YAML tests.
    """
    
    dependencies = ['company']
    tags = ['python', 'advanced', 'workflow']
    timeout = 600  # 10 minutes
    
    async def test_conditional_deployment(self):
        """Test deployment with conditional logic based on environment"""
        
        # Create base infrastructure
        team = await self.create_entity('team', 
            name=self.random_name('adv_team'),
            company=self.context.get_var('company'),
            vault={
                'environment': 'staging',
                'deploy_key': 'test-key-123'
            }
        )
        
        region = await self.create_entity('region',
            name=self.random_name('adv_region'),
            company=self.context.get_var('company'),
            location='us-west-2'
        )
        
        # Create multiple bridges for redundancy
        bridges = []
        for i in range(3):
            bridge = await self.create_entity('bridge',
                name=self.random_name(f'adv_bridge_{i}'),
                region=region['name']
            )
            bridges.append(bridge)
        
        # Select primary bridge based on some logic
        primary_bridge = bridges[0]  # In real test, could ping bridges
        
        # Create machines in different zones
        machines = []
        for i, bridge in enumerate(bridges[:2]):  # Use only 2 bridges
            machine = await self.create_entity('machine',
                name=self.random_name(f'adv_machine_{i}'),
                team=team['name'],
                bridge=bridge['name'],
                vault={
                    'ip': f'10.0.{i}.100',
                    'user': 'deploy',
                    'datastore': f'/mnt/zone{i}/repos',
                    'zone': f'zone-{i}'
                }
            )
            machines.append(machine)
        
        # Create repository on primary machine
        repo = await self.create_entity('repository',
            name=self.random_name('adv_repo'),
            team=team['name'],
            machine=machines[0]['name'],
            repo_type='git',
            url='git@github.com:example/app.git'
        )
        
        # Submit deployment job
        job = await self.cli.create_queue_item(
            team=team['name'],
            machine=machines[0]['name'],
            bridge=primary_bridge['name'],
            function='deploy_application',
            priority=2,
            vault={
                'repository': repo['name'],
                'version': '1.2.3',
                'environment': 'staging',
                'pre_deploy_checks': True,
                'post_deploy_verification': True
            }
        )
        
        self.assert_response_success(job)
        task_id = job['taskId']
        
        # Monitor deployment progress
        start_time = time.time()
        last_status = None
        
        while time.time() - start_time < 300:  # 5 minute timeout
            status_response = await self.cli.get_queue_status(task_id)
            
            if status_response.get('success'):
                status = status_response.get('status')
                
                # Log status changes
                if status != last_status:
                    self.logger.info(f"Deployment status: {status}")
                    last_status = status
                
                if status == 'COMPLETED':
                    # Verify deployment success
                    result = status_response.get('result', {})
                    self.assert_equal(result.get('deployment_status'), 'success')
                    self.assert_in('version', result)
                    self.assert_equal(result['version'], '1.2.3')
                    break
                    
                elif status == 'FAILED':
                    error = status_response.get('error', 'Unknown error')
                    raise AssertionError(f"Deployment failed: {error}")
            
            await self._sleep(5)
        else:
            raise TimeoutError("Deployment timed out")
        
        # If staging deployment successful, deploy to production
        if last_status == 'COMPLETED':
            # Create production machine
            prod_machine = await self.create_entity('machine',
                name=self.random_name('prod_machine'),
                team=team['name'],
                bridge=bridges[1]['name'],  # Use different bridge
                vault={
                    'ip': '10.1.0.100',
                    'user': 'deploy',
                    'datastore': '/mnt/production/repos',
                    'environment': 'production'
                }
            )
            
            # Submit production deployment
            prod_job = await self.cli.create_queue_item(
                team=team['name'],
                machine=prod_machine['name'],
                bridge=bridges[1]['name'],
                function='deploy_application',
                priority=1,  # Higher priority for production
                vault={
                    'repository': repo['name'],
                    'version': '1.2.3',
                    'environment': 'production',
                    'canary_deployment': True,
                    'canary_percentage': 10
                }
            )
            
            # Wait for production deployment
            await self.wait_for_condition(
                lambda: self._check_deployment_status(prod_job['taskId'], 'COMPLETED'),
                timeout=300
            )
    
    async def _check_deployment_status(self, task_id: str, expected_status: str) -> bool:
        """Helper to check deployment status"""
        response = await self.cli.get_queue_status(task_id)
        if response.get('success'):
            return response.get('status') == expected_status
        return False
    
    async def test_bulk_operations(self):
        """Test bulk creation and management of resources"""
        
        # Create team for bulk operations
        team = await self.create_entity('team',
            name=self.random_name('bulk_team'),
            company=self.context.get_var('company')
        )
        
        # Create region and bridge
        region = await self.create_entity('region',
            name=self.random_name('bulk_region'),
            company=self.context.get_var('company')
        )
        
        bridge = await self.create_entity('bridge',
            name=self.random_name('bulk_bridge'),
            region=region['name']
        )
        
        # Create multiple machines in parallel
        machine_count = 10
        machine_tasks = []
        
        for i in range(machine_count):
            task = self.create_entity('machine',
                name=self.random_name(f'bulk_machine_{i:03d}'),
                team=team['name'],
                bridge=bridge['name'],
                vault={
                    'ip': f'10.0.1.{100 + i}',
                    'user': 'deploy',
                    'datastore': f'/mnt/node{i:03d}'
                }
            )
            machine_tasks.append(task)
        
        # Wait for all machines to be created
        machines = await asyncio.gather(*machine_tasks)
        
        # Verify all machines were created
        self.assert_equal(len(machines), machine_count)
        for machine in machines:
            self.assert_response_success(machine)
        
        # Create repositories on each machine
        repo_tasks = []
        for i, machine in enumerate(machines):
            task = self.create_entity('repository',
                name=self.random_name(f'bulk_repo_{i:03d}'),
                team=team['name'],
                machine=machine['name'],
                repo_type='git'
            )
            repo_tasks.append(task)
        
        repos = await asyncio.gather(*repo_tasks)
        
        # Submit queue jobs for all repositories
        job_tasks = []
        for repo, machine in zip(repos, machines):
            task = self.cli.create_queue_item(
                team=team['name'],
                machine=machine['name'],
                bridge=bridge['name'],
                function='initialize_repository',
                priority=3,
                vault={
                    'repository': repo['name']
                }
            )
            job_tasks.append(task)
        
        jobs = await asyncio.gather(*job_tasks)
        
        # Track job completion
        completed = 0
        failed = 0
        
        for job in jobs:
            if job.get('success'):
                # In a real test, we would monitor these jobs
                completed += 1
            else:
                failed += 1
        
        self.logger.info(f"Bulk operations: {completed} succeeded, {failed} failed")
        self.assert_equal(failed, 0, "All bulk operations should succeed")