#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Rediacc CLI Workflow Module - High-level workflow commands for common operations
"""

import json
import time
import os
import secrets
import string
from typing import Optional, Dict, Any

from core.shared import colorize
from core.api_client import client


def format_output(data, format_type, message=None, error=None):
    """Format output based on format type"""
    if format_type in ['json', 'json-full']:
        output = {'success': error is None, 'data': data}
        if message: output['message'] = message
        if error: output['error'] = error
        return json.dumps(output, indent=2)
    return colorize(f"Error: {error}", 'RED') if error else data if data else colorize(message, 'GREEN') if message else "No data available"


def minifyJSON(json_str):
    """Minify JSON string by removing unnecessary whitespace"""
    try:
        return json.dumps(json.loads(json_str), separators=(',', ':'))
    except:
        return json_str


class WorkflowHandler:
    """Handler for workflow commands that combine multiple operations"""
    
    def __init__(self, command_handler):
        """Initialize workflow handler with command handler reference"""
        self.command_handler = command_handler
        self.config = command_handler.config
        self.config_manager = command_handler.config_manager
        self.client = command_handler.client
        self.output_format = command_handler.output_format
    
    def handle_response(self, response, success_message=None, format_args=None):
        """Delegate to command handler's handle_response"""
        return self.command_handler.handle_response(response, success_message, format_args)
    
    def _get_machine_data(self, team_name, machine_name):
        """Helper to get machine data including bridge and vault"""
        # Get all machines for the team and find the specific one
        response = self.client.token_request("GetTeamMachines", {'teamName': team_name})
        
        if response.get('error'):
            print(format_output(None, self.output_format, None, f"Failed to get machine data: {response['error']}"))
            return None
        
        if len(response.get('resultSets', [])) > 1 and response['resultSets'][1].get('data'):
            machines = response['resultSets'][1]['data']
            machine_data = next((m for m in machines if m.get('machineName') == machine_name), None)
            
            if not machine_data:
                print(format_output(None, self.output_format, None, f"Machine '{machine_name}' not found in team '{team_name}'"))
                return None
                
            if not machine_data.get('bridgeName'):
                print(format_output(None, self.output_format, None, f"Machine '{machine_name}' does not have an assigned bridge"))
                return None
            return machine_data
        
        print(format_output(None, self.output_format, None, f"No machines found for team '{team_name}'"))
        return None
    
    def _get_team_vault(self, team_name):
        """Helper to get team vault data"""
        # Use GetCompanyTeams which returns teams with vaultContent
        response = self.client.token_request("GetCompanyTeams", {})
        if not response.get('error') and len(response.get('resultSets', [])) > 1:
            teams = response['resultSets'][1].get('data', [])
            for team in teams:
                if team.get('teamName') == team_name:
                    vault = team.get('vaultContent') or team.get('teamVault', '{}')
                    if os.environ.get('REDIACC_VERBOSE'):
                        print(f"DEBUG: _get_team_vault found team '{team_name}'")
                        print(f"DEBUG: Team vault length: {len(str(vault))}")
                        # Parse and check for SSH keys
                        try:
                            parsed = json.loads(vault) if isinstance(vault, str) else vault
                            print(f"DEBUG: Team vault has SSH_PRIVATE_KEY: {'SSH_PRIVATE_KEY' in parsed}")
                            print(f"DEBUG: Team vault has SSH_PUBLIC_KEY: {'SSH_PUBLIC_KEY' in parsed}")
                        except:
                            print("DEBUG: Failed to parse team vault")
                    return vault
        
        return '{}'
    
    def _get_storage_vault(self, team_name, storage_name):
        """Helper to get storage vault data"""
        response = self.client.token_request("GetTeamStorageSystems", {'teamName': team_name})
        if not response.get('error') and len(response.get('resultSets', [])) > 1:
            storages = response['resultSets'][1].get('data', [])
            storage = next((s for s in storages if s.get('storageName') == storage_name), None)
            if storage:
                return storage.get('vaultContent') or storage.get('storageVault', '{}')
        return None
    
    def _cleanup_repository(self, team_name, repo_name):
        """Helper to cleanup created repository on error"""
        try:
            self.client.token_request("DeleteRepository", {
                'teamName': team_name,
                'repoName': repo_name
            })
        except:
            pass
    
    def _extract_command_output(self, completion_result):
        """Extract command output from completion result"""
        # Don't check for completed status - we want output even for failed tasks
        if not completion_result.get('resultSets'):
            return None
            
        # Response vault is at table index 2 (resultSets array index 2)
        if len(completion_result['resultSets']) > 2:
            response_vault = completion_result['resultSets'][2]
            if response_vault and len(response_vault) > 0:
                vault_data = response_vault[0]
                if vault_data.get('vaultContent'):
                    try:
                        vault_content = json.loads(vault_data['vaultContent'])
                        if vault_content.get('result'):
                            result_data = json.loads(vault_content['result'])
                            return result_data.get('command_output', '')
                    except json.JSONDecodeError:
                        pass
        return None
    
    def _extract_bridge_result(self, completion_result):
        """Extract structured result data from bridge-only task completion"""
        if not completion_result.get('completed') or not completion_result.get('resultSets'):
            return None
            
        # Response vault is at table index 2 (resultSets array index 2)
        if len(completion_result['resultSets']) > 2:
            response_vault = completion_result['resultSets'][2]
            if response_vault and len(response_vault) > 0:
                vault_data = response_vault[0]
                if vault_data.get('vaultContent'):
                    try:
                        vault_content = json.loads(vault_data['vaultContent'])
                        if vault_content.get('result'):
                            return json.loads(vault_content['result'])
                    except json.JSONDecodeError:
                        pass
        return None
    
    def _format_completion_result(self, result, completion_result):
        """Format completion result based on output format"""
        if self.output_format == 'json-full':
            # Full output with all server resultSets
            result['completed'] = completion_result['completed']
            result['final_status'] = completion_result['status'].lower()
            result['server_tables'] = completion_result['resultSets']
            if completion_result.get('error'):
                result['error'] = completion_result['error']
        elif self.output_format == 'json':
            # Concise output with just essential info
            result['completed'] = completion_result['completed']
            result['final_status'] = completion_result['status'].lower()
            if completion_result.get('error'):
                result['error'] = completion_result['error']
            
            # Add command output or bridge result if available
            command_output = self._extract_command_output(completion_result)
            if command_output:
                result['command_output'] = command_output
            else:
                # Check for bridge result (structured data)
                bridge_result = self._extract_bridge_result(completion_result)
                if bridge_result:
                    result['result'] = bridge_result
        
        return result
    
    def _wait_for_task_completion(self, task_id, team_name, timeout=300, poll_interval=2):
        """Wait for a task to complete with timeout, returning full response data"""
        start_time = time.time()
        last_status = None
        
        while time.time() - start_time < timeout:
            # Use GetQueueItemTrace to get status of specific task
            response = self.client.token_request("GetQueueItemTrace", {
                'taskId': task_id
            })
            
            if response.get('error'):
                if os.environ.get('REDIACC_VERBOSE'):
                    print(f"DEBUG: Error getting queue trace: {response.get('error')}")
                # Continue polling even on error - task might still be running
                time.sleep(poll_interval)
                continue
            
            # GetQueueItemTrace returns multiple resultSets
            # We include all resultSets except table 0 (which contains nextRequestToken)
            resultSets = response.get('resultSets', [])
            if len(resultSets) > 1:
                # Get status from table 1 (queue details)
                task_data = resultSets[1].get('data', [{}])[0] if resultSets[1].get('data') else {}
                status = task_data.get('status', '').upper()
                
                if status != last_status:
                    last_status = status
                    if self.output_format not in ['json', 'json-full']:
                        print(f"  Status: {status}")
                
                # Check if task is done
                if status in ['COMPLETED', 'FAILED', 'CANCELLED', 'ERROR']:
                    # Return all resultSets except table 0
                    result = {
                        'completed': status == 'COMPLETED',
                        'status': status,
                        'resultSets': []
                    }
                    
                    # Include all resultSets except table 0 (credentials)
                    for i in range(1, len(resultSets)):
                        result['resultSets'].append(resultSets[i].get('data', []))
                    
                    return result
            
            time.sleep(poll_interval)  # Poll at specified interval
        
        if os.environ.get('REDIACC_VERBOSE'):
            print(f"DEBUG: Task timed out after {timeout} seconds")
        
        # Return timeout result
        return {
            'completed': False,
            'status': 'TIMEOUT',
            'resultSets': [],
            'error': f'Task timed out after {timeout} seconds'
        }
    
    def workflow_repo_create(self, args):
        """Create repository and initialize it on machine"""
        try:
            # Import VaultBuilder here to avoid circular import
            from rediacc_cli import VaultBuilder
            
            # Step 1: Create repository record in database
            # Handle vault data - if not provided or empty, create with random credential
            vault_data = getattr(args, 'vault', '{}')
            if vault_data == '{}' or not vault_data:
                # Generate a random credential
                alphabet = string.ascii_letters + string.digits + string.punctuation
                random_credential = ''.join(secrets.choice(alphabet) for i in range(32))
                vault_data = json.dumps({"credential": random_credential})
            
            create_params = {
                'teamName': args.team,
                'repoName': args.name,
                'repoVault': vault_data
            }
            # Only add parentRepoName if provided
            if hasattr(args, 'parent') and args.parent:
                create_params['parentRepoName'] = args.parent
                
            repo_response = self.client.token_request("CreateRepository", create_params)
            
            if repo_response.get('error'):
                print(format_output(None, self.output_format, None, f"Failed to create repository: {repo_response['error']}"))
                return 1
            
            # Step 2: Get repository GUID by fetching team repositories
            repos_response = self.client.token_request("GetTeamRepositories", {
                'teamName': args.team
            })
            
            if repos_response.get('error'):
                # Rollback repository creation
                self._cleanup_repository(args.team, args.name)
                print(format_output(None, self.output_format, None, f"Failed to get repository list: {repos_response['error']}"))
                return 1
            
            # Find our repository and extract GUID
            repo_guid = None
            if len(repos_response.get('resultSets', [])) > 1:
                repos = repos_response['resultSets'][1].get('data', [])
                for repo in repos:
                    if repo.get('repoName') == args.name or repo.get('repositoryName') == args.name:
                        repo_guid = repo.get('repoGuid') or repo.get('repositoryGuid')
                        break
            
            if not repo_guid:
                # Rollback repository creation
                self._cleanup_repository(args.team, args.name)
                print(format_output(None, self.output_format, None, "Failed to get repository GUID"))
                return 1
            
            # Get machine data using helper method
            machine_data = self._get_machine_data(args.team, args.machine)
            if not machine_data:
                # Rollback repository creation
                self._cleanup_repository(args.team, args.name)
                return 1
            
            bridge_name = machine_data.get('bridgeName')
            machine_vault = machine_data.get('vaultContent', '{}')
            
            if not bridge_name:
                # Rollback repository creation
                self.client.token_request("DeleteRepository", {
                    'teamName': args.team,
                    'repoName': args.name
                })
                print(format_output(None, self.output_format, None, "Machine does not have an assigned bridge"))
                return 1
            
            # Get team vault data with SSH keys
            team_vault = self._get_team_vault(args.team)
            
            # Step 2: Build queue vault for 'new' function
            vault_builder = VaultBuilder(self.client)
            queue_vault = vault_builder.build_for_repo_create(
                team_name=args.team,
                machine_name=args.machine,
                repo_name=args.name,
                repo_guid=repo_guid,
                size=args.size,
                team_vault=team_vault,
                machine_vault=machine_vault
            )
            
            # Step 3: Create queue item to initialize repository on machine
            queue_response = self.client.token_request("CreateQueueItem", {
                'teamName': args.team,
                'machineName': args.machine,
                'bridgeName': bridge_name,
                'queueVault': queue_vault
            })
            
            if queue_response.get('error'):
                # Rollback repository creation
                self.client.token_request("DeleteRepository", {
                    'teamName': args.team,
                    'repoName': args.name
                })
                print(format_output(None, self.output_format, None, f"Failed to create queue item: {queue_response['error']}"))
                return 1
            
            # Extract task ID
            task_id = None
            if len(queue_response.get('resultSets', [])) > 1 and queue_response['resultSets'][1].get('data'):
                task_id = queue_response['resultSets'][1]['data'][0].get('taskId') or queue_response['resultSets'][1]['data'][0].get('TaskId')
            
            # Prepare result data
            result = {
                'repository_name': args.name,
                'repository_guid': repo_guid,
                'task_id': task_id,
                'team': args.team,
                'machine': args.machine,
                'size': args.size
            }
            
            # Output results
            if self.output_format in ['json', 'json-full']:
                if not getattr(args, 'wait', False):
                    print(format_output(result, self.output_format, f"Repository '{args.name}' created and initialization queued"))
            else:
                print(colorize(f"Repository '{args.name}' created successfully", 'GREEN'))
                print(f"Repository GUID: {repo_guid}")
                if task_id:
                    print(f"Initialization Task ID: {task_id}")
                    if getattr(args, 'trace', False):
                        print(colorize("Use 'rediacc queue trace' command to track progress", 'BLUE'))
            
            # Wait for completion if requested
            if getattr(args, 'wait', False) and task_id:
                if self.output_format != 'json':
                    print(colorize("Waiting for repository initialization...", 'BLUE'))
                poll_interval = getattr(args, 'poll_interval', 2)
                wait_timeout = getattr(args, 'wait_timeout', 300)
                completion_result = self._wait_for_task_completion(task_id, args.team, timeout=wait_timeout, poll_interval=poll_interval)
                
                if self.output_format in ['json', 'json-full']:
                    result = self._format_completion_result(result, completion_result)
                    print(format_output(result, self.output_format))
                else:
                    if completion_result['completed']:
                        print(colorize("Repository initialization completed successfully", 'GREEN'))
                        # Display command output if available
                        command_output = self._extract_command_output(completion_result)
                        if command_output:
                            print(colorize("\nCommand Output:", 'BLUE'))
                            # Clean up the output (replace \n with actual newlines)
                            clean_output = command_output.replace('\\n', '\n')
                            print(clean_output)
                    else:
                        print(colorize(f"Repository initialization {completion_result['status'].lower()}", 'RED'))
                        if completion_result.get('error'):
                            print(f"Error: {completion_result['error']}")
                        # Try to show command output even for failed tasks
                        command_output = self._extract_command_output(completion_result)
                        if command_output:
                            print(colorize("\nCommand Output:", 'YELLOW'))
                            clean_output = command_output.replace('\\n', '\n')
                            print(clean_output)
                        return 1
            
            return 0
            
        except Exception as e:
            print(format_output(None, self.output_format, None, f"Workflow error: {str(e)}"))
            return 1
    
    def workflow_repo_push(self, args):
        """Push repository with automatic destination creation"""
        try:
            # Import VaultBuilder here to avoid circular import
            from rediacc_cli import VaultBuilder
            
            # Get source repository data
            source_repo_response = self.client.token_request("GetTeamRepositories", {'teamName': args.source_team})
            if source_repo_response.get('error'):
                print(format_output(None, self.output_format, None, f"Failed to get source repositories: {source_repo_response['error']}"))
                return 1
            
            source_repo = None
            if len(source_repo_response.get('resultSets', [])) > 1:
                repos = source_repo_response['resultSets'][1].get('data', [])
                source_repo = next((r for r in repos if r.get('repoName') == args.source_repo), None)
            
            if not source_repo:
                print(format_output(None, self.output_format, None, f"Source repository '{args.source_repo}' not found"))
                return 1
            
            source_guid = source_repo.get('repoGuid')
            grand_guid = source_repo.get('grandGuid', source_guid)
            
            # Check if destination is machine or storage
            dest_type = getattr(args, 'dest_type', 'machine')
            dest_guid = None
            created_repo_name = None
            
            if dest_type == 'machine':
                # Check if destination repository exists
                dest_repo_response = self.client.token_request("GetTeamRepositories", {'teamName': args.dest_team})
                dest_repo = None
                if not dest_repo_response.get('error') and len(dest_repo_response.get('resultSets', [])) > 1:
                    repos = dest_repo_response['resultSets'][1].get('data', [])
                    dest_repo = next((r for r in repos if r.get('repoName') == args.dest_repo), None)
                
                if not dest_repo:
                    # Create destination repository
                    create_response = self.client.token_request("CreateRepository", {
                        'teamName': args.dest_team,
                        'repoName': args.dest_repo,
                        'repoVault': '{}',
                        'parentRepoName': args.source_repo
                    })
                    
                    if create_response.get('error'):
                        print(format_output(None, self.output_format, None, f"Failed to create destination repository: {create_response['error']}"))
                        return 1
                    
                    created_repo_name = args.dest_repo
                    
                    # Refetch to get the new repository GUID
                    dest_repo_response = self.client.token_request("GetTeamRepositories", {'teamName': args.dest_team})
                    if not dest_repo_response.get('error') and len(dest_repo_response.get('resultSets', [])) > 1:
                        repos = dest_repo_response['resultSets'][1].get('data', [])
                        dest_repo = next((r for r in repos if r.get('repoName') == args.dest_repo), None)
                
                if dest_repo:
                    dest_guid = dest_repo.get('repoGuid')
            
            # Get machine and vault data
            source_machine_data = self._get_machine_data(args.source_team, args.source_machine)
            if not source_machine_data:
                if created_repo_name:
                    self._cleanup_repository(args.dest_team, created_repo_name)
                return 1
            
            # Build push parameters
            push_params = {
                'src': args.source_path or '/',
                'dest': dest_guid if dest_type == 'machine' else args.dest_repo,
                'repo': source_guid,
                'grand': grand_guid,
                'destinationType': dest_type,
                'to': args.dest_machine if dest_type == 'machine' else args.dest_storage
            }
            
            # Get additional vault data if needed
            team_vault = self._get_team_vault(args.source_team)
            dest_machine_vault = None
            dest_storage_vault = None
            
            if dest_type == 'machine':
                dest_machine_data = self._get_machine_data(args.dest_team, args.dest_machine)
                if dest_machine_data:
                    dest_machine_vault = dest_machine_data.get('vaultContent', '{}')
            else:
                # Get storage vault data
                dest_storage_vault = self._get_storage_vault(args.dest_team, args.dest_storage)
            
            # Build queue vault
            vault_builder = VaultBuilder(self.client)
            context = {
                'teamName': args.source_team,
                'machineName': args.source_machine,
                'params': push_params,
                'teamVault': team_vault,
                'machineVault': source_machine_data.get('vaultContent', '{}'),
                'repositoryGuid': source_guid,
                'repositoryVault': source_repo.get('vaultContent', '{}'),
                'destinationGuid': dest_guid,
                'grandGuid': grand_guid
            }
            
            if dest_machine_vault:
                context['destinationMachineVault'] = dest_machine_vault
            if dest_storage_vault:
                context['destinationStorageVault'] = dest_storage_vault
            
            queue_vault = vault_builder.build_for_repo_push(context)
            
            # Create queue item
            queue_response = self.client.token_request("CreateQueueItem", {
                'teamName': args.source_team,
                'machineName': args.source_machine,
                'bridgeName': source_machine_data['bridgeName'],
                'queueVault': queue_vault
            })
            
            if queue_response.get('error'):
                if created_repo_name:
                    self._cleanup_repository(args.dest_team, created_repo_name)
                print(format_output(None, self.output_format, None, f"Failed to create queue item: {queue_response['error']}"))
                return 1
            
            # Extract task ID
            task_id = None
            if len(queue_response.get('resultSets', [])) > 1 and queue_response['resultSets'][1].get('data'):
                task_id = queue_response['resultSets'][1]['data'][0].get('taskId') or queue_response['resultSets'][1]['data'][0].get('TaskId')
            
            # Prepare result data
            result = {
                'source': f"{args.source_team}/{args.source_machine}/{args.source_repo}",
                'destination': f"{args.dest_team}/{args.dest_machine if dest_type == 'machine' else args.dest_storage}/{args.dest_repo}",
                'task_id': task_id,
                'created_destination': bool(created_repo_name)
            }
            
            # Output results
            if self.output_format in ['json', 'json-full']:
                if not getattr(args, 'wait', False):
                    print(format_output(result, self.output_format, "Repository push queued successfully"))
            else:
                print(colorize("Repository push queued successfully", 'GREEN'))
                print(f"Source: {args.source_team}/{args.source_machine}/{args.source_repo}")
                print(f"Destination: {args.dest_team}/{args.dest_machine if dest_type == 'machine' else args.dest_storage}/{args.dest_repo}")
                if created_repo_name:
                    print(colorize(f"Created destination repository: {created_repo_name}", 'BLUE'))
                if task_id:
                    print(f"Push Task ID: {task_id}")
                    if getattr(args, 'trace', False):
                        print(colorize("Use 'rediacc queue trace' command to track progress", 'BLUE'))
            
            # Wait for completion if requested
            if getattr(args, 'wait', False) and task_id:
                if self.output_format != 'json':
                    print(colorize("Waiting for push operation...", 'BLUE'))
                poll_interval = getattr(args, 'poll_interval', 2)
                wait_timeout = getattr(args, 'wait_timeout', 300)
                completion_result = self._wait_for_task_completion(task_id, args.source_team, timeout=wait_timeout, poll_interval=poll_interval)
                
                if self.output_format in ['json', 'json-full']:
                    result = self._format_completion_result(result, completion_result)
                    print(format_output(result, self.output_format))
                else:
                    if completion_result['completed']:
                        print(colorize("Push operation completed successfully", 'GREEN'))
                        # Display command output if available
                        command_output = self._extract_command_output(completion_result)
                        if command_output:
                            print("\nCommand output:")
                            print("-" * 50)
                            # Clean up the output (replace \n with actual newlines)
                            clean_output = command_output.replace('\\n', '\n')
                            print(clean_output)
                    else:
                        print(colorize(f"Push operation {completion_result['status'].lower()}", 'RED'))
                        if completion_result.get('error'):
                            print(f"Error: {completion_result['error']}")
                        return 1
            
            return 0
            
        except Exception as e:
            print(format_output(None, self.output_format, None, f"Workflow error: {str(e)}"))
            return 1
    
    def workflow_connectivity_test(self, args):
        """Test connectivity for multiple machines"""
        try:
            # Import VaultBuilder here to avoid circular import
            from rediacc_cli import VaultBuilder, format_table
            
            # Get machines for the specified team(s)
            team_filter = getattr(args, 'team', None)
            if isinstance(team_filter, str):
                teams = [team_filter]
            else:
                teams = team_filter if team_filter else []
            
            all_machines = []
            for team in teams:
                machines_response = self.client.token_request("GetTeamMachines", {'teamName': team})
                if not machines_response.get('error') and len(machines_response.get('resultSets', [])) > 1:
                    machines = machines_response['resultSets'][1].get('data', [])
                    all_machines.extend(machines)
            
            if not all_machines:
                print(format_output(None, self.output_format, None, "No machines found for the specified team(s)"))
                return 1
            
            # Filter by specific machines if provided
            if hasattr(args, 'machines') and args.machines:
                machine_names = args.machines if isinstance(args.machines, list) else args.machines.split(',')
                all_machines = [m for m in all_machines if m.get('machineName') in machine_names]
            
            results = []
            total = len(all_machines)
            
            if self.output_format not in ['json', 'json-full']:
                print(colorize(f"Testing connectivity for {total} machine(s)...", 'BLUE'))
            
            # Test each machine sequentially
            for i, machine in enumerate(all_machines):
                machine_name = machine.get('machineName')
                team_name = machine.get('teamName')
                bridge_name = machine.get('bridgeName')
                
                if not bridge_name:
                    results.append({
                        'machineName': machine_name,
                        'teamName': team_name,
                        'status': 'failed',
                        'message': 'No bridge assigned',
                        'duration': 0
                    })
                    continue
                
                start_time = time.time()
                
                if self.output_format not in ['json', 'json-full']:
                    print(f"\n[{i+1}/{total}] Testing {machine_name}...")
                
                # Get machine vault data
                machine_vault = machine.get('vaultContent', '{}')
                team_vault = self._get_team_vault(team_name)
                
                # Build ping vault
                vault_builder = VaultBuilder(self.client)
                queue_vault = vault_builder.build_for_ping(
                    team_name=team_name,
                    machine_name=machine_name,
                    bridge_name=bridge_name,
                    team_vault=team_vault,
                    machine_vault=machine_vault
                )
                
                # Create queue item
                queue_response = self.client.token_request("CreateQueueItem", {
                    'teamName': team_name,
                    'machineName': machine_name,
                    'bridgeName': bridge_name,
                    'queueVault': queue_vault
                })
                
                if queue_response.get('error'):
                    results.append({
                        'machineName': machine_name,
                        'teamName': team_name,
                        'status': 'failed',
                        'message': queue_response['error'],
                        'duration': time.time() - start_time
                    })
                    continue
                
                # Get task ID
                task_id = None
                if len(queue_response.get('resultSets', [])) > 1 and queue_response['resultSets'][1].get('data'):
                    task_id = queue_response['resultSets'][1]['data'][0].get('taskId') or queue_response['resultSets'][1]['data'][0].get('TaskId')
                
                if not task_id:
                    results.append({
                        'machineName': machine_name,
                        'teamName': team_name,
                        'status': 'failed',
                        'message': 'No task ID returned',
                        'duration': time.time() - start_time
                    })
                    continue
                
                # Wait for completion
                if getattr(args, 'wait', True):  # Default to waiting
                    poll_interval = getattr(args, 'poll_interval', 1)  # Faster polling for connectivity tests
                    wait_timeout = getattr(args, 'wait_timeout', 30)  # Shorter timeout for ping
                    
                    completion_result = self._wait_for_task_completion(task_id, team_name, timeout=wait_timeout, poll_interval=poll_interval)
                    
                    results.append({
                        'machineName': machine_name,
                        'teamName': team_name,
                        'bridgeName': bridge_name,
                        'taskId': task_id,
                        'status': 'success' if completion_result['completed'] else 'failed',
                        'message': 'Connected' if completion_result['completed'] else completion_result.get('error', 'Connection failed'),
                        'duration': time.time() - start_time,
                        'server_tables': completion_result.get('resultSets', []) if getattr(args, 'wait', False) else None
                    })
                else:
                    results.append({
                        'machineName': machine_name,
                        'teamName': team_name,
                        'bridgeName': bridge_name,
                        'taskId': task_id,
                        'status': 'queued',
                        'message': 'Test queued',
                        'duration': time.time() - start_time
                    })
            
            # Output results
            if self.output_format in ['json', 'json-full']:
                successful = len([r for r in results if r['status'] == 'success'])
                failed = len([r for r in results if r['status'] == 'failed'])
                output = {
                    'total': total,
                    'successful': successful,
                    'failed': failed,
                    'results': results
                }
                # For concise JSON, remove server_tables from results
                if self.output_format == 'json':
                    for result in output['results']:
                        if 'server_tables' in result:
                            # Extract command output if available
                            if result.get('server_tables'):
                                # Try to extract command output
                                command_output = None
                                if len(result['server_tables']) > 2:
                                    response_vault = result['server_tables'][2]
                                    if response_vault and len(response_vault) > 0:
                                        vault_data = response_vault[0]
                                        if vault_data.get('vaultContent'):
                                            try:
                                                vault_content = json.loads(vault_data['vaultContent'])
                                                if vault_content.get('result'):
                                                    result_data = json.loads(vault_content['result'])
                                                    command_output = result_data.get('command_output', '')
                                            except json.JSONDecodeError:
                                                pass
                                if command_output:
                                    result['command_output'] = command_output
                            del result['server_tables']
                print(format_output(output, self.output_format))
            else:
                # Summary
                print(colorize("\nConnectivity Test Results", 'HEADER'))
                print("=" * 50)
                
                # Table format
                successful = 0
                failed = 0
                for result in results:
                    status_color = 'GREEN' if result['status'] == 'success' else 'RED'
                    status_text = '✓' if result['status'] == 'success' else '✗'
                    duration = f"{result['duration']:.1f}s" if result['duration'] < 10 else f"{result['duration']:.0f}s"
                    
                    print(f"{colorize(status_text, status_color)} {result['machineName']:<20} {result['teamName']:<15} {duration:<6} {result['message']}")
                    
                    if result['status'] == 'success':
                        successful += 1
                    elif result['status'] == 'failed':
                        failed += 1
                
                print("\n" + "-" * 50)
                print(f"Total: {total} | " + 
                      colorize(f"Success: {successful}", 'GREEN') + " | " +
                      colorize(f"Failed: {failed}", 'RED'))
                
                # Average response time for successful tests
                successful_results = [r for r in results if r['status'] == 'success']
                if successful_results:
                    avg_duration = sum(r['duration'] for r in successful_results) / len(successful_results)
                    print(f"Average response time: {avg_duration:.1f}s")
            
            return 0
            
        except Exception as e:
            print(format_output(None, self.output_format, None, f"Workflow error: {str(e)}"))
            return 1
    
    def workflow_hello_test(self, args):
        """Simple hello test for machine connectivity"""
        try:
            # Import VaultBuilder here to avoid circular import
            from rediacc_cli import VaultBuilder
            
            # Get machine data
            machine_data = self._get_machine_data(args.team, args.machine)
            if not machine_data:
                return 1
            
            # Get vault data
            team_vault = self._get_team_vault(args.team)
            machine_vault = machine_data.get('vaultContent', '{}')
            bridge_name = machine_data.get('bridgeName')
            
            # Build hello vault
            vault_builder = VaultBuilder(self.client)
            queue_vault = vault_builder.build_for_hello(
                team_name=args.team,
                machine_name=args.machine,
                bridge_name=bridge_name,
                team_vault=team_vault,
                machine_vault=machine_vault
            )
            
            # Create queue item
            queue_response = self.client.token_request("CreateQueueItem", {
                'teamName': args.team,
                'machineName': args.machine,
                'bridgeName': bridge_name,
                'queueVault': queue_vault
            })
            
            if queue_response.get('error'):
                print(format_output(None, self.output_format, None, f"Failed to create queue item: {queue_response['error']}"))
                return 1
            
            # Extract task ID
            task_id = None
            if len(queue_response.get('resultSets', [])) > 1 and queue_response['resultSets'][1].get('data'):
                task_id = queue_response['resultSets'][1]['data'][0].get('taskId') or queue_response['resultSets'][1]['data'][0].get('TaskId')
            
            # Prepare result data
            result = {
                'machine': args.machine,
                'team': args.team,
                'task_id': task_id
            }
            
            # Output results
            if self.output_format in ['json', 'json-full']:
                if not getattr(args, 'wait', False):
                    print(format_output(result, self.output_format, "Hello test queued successfully"))
            else:
                print(colorize(f"Hello test queued for machine '{args.machine}'", 'GREEN'))
                if task_id:
                    print(f"Task ID: {task_id}")
            
            # Wait for completion if requested
            if getattr(args, 'wait', False) and task_id:
                if self.output_format not in ['json', 'json-full']:
                    print(colorize("Waiting for hello response...", 'BLUE'))
                poll_interval = getattr(args, 'poll_interval', 2)
                wait_timeout = getattr(args, 'wait_timeout', 30)
                
                completion_result = self._wait_for_task_completion(task_id, args.team, timeout=wait_timeout, poll_interval=poll_interval)
                
                if self.output_format in ['json', 'json-full']:
                    result = self._format_completion_result(result, completion_result)
                    print(format_output(result, self.output_format))
                else:
                    if completion_result['completed']:
                        print(colorize("Hello test completed successfully", 'GREEN'))
                        # Display command output if available
                        command_output = self._extract_command_output(completion_result)
                        if command_output:
                            print("\nCommand output:")
                            print("-" * 50)
                            # Clean up the output (replace \n with actual newlines)
                            clean_output = command_output.replace('\\n', '\n')
                            print(clean_output)
                    else:
                        print(colorize(f"Hello test {completion_result['status'].lower()}", 'RED'))
                        if completion_result.get('error'):
                            print(f"Error: {completion_result['error']}")
                        return 1
            
            return 0
            
        except Exception as e:
            print(format_output(None, self.output_format, None, f"Workflow error: {str(e)}"))
            return 1
    
    def workflow_ssh_test(self, args):
        """Test SSH connectivity for bridge"""
        try:
            # Import VaultBuilder here to avoid circular import
            from rediacc_cli import VaultBuilder
            
            # For SSH test, we need bridge information and SSH credentials
            # This is a special case where we might not need a specific machine
            
            # Build machine vault with SSH credentials
            machine_vault = {
                'ip': args.host,
                'user': args.user,
                'datastore': getattr(args, 'datastore', '/mnt/datastore')
            }
            
            # Add SSH password if provided
            if hasattr(args, 'password') and args.password:
                machine_vault['ssh_password'] = args.password
            
            machine_vault_str = json.dumps(machine_vault)
            
            # Get team vault for SSH keys
            team_vault = self._get_team_vault(args.team) if hasattr(args, 'team') and args.team else '{}'
            
            # Build SSH test vault with team context for SSH keys
            vault_builder = VaultBuilder(self.client)
            queue_vault = vault_builder.build_for_ssh_test(
                bridge_name=args.bridge,
                machine_vault=machine_vault_str,
                team_name=args.team,
                team_vault=team_vault
            )
            
            # Debug: Print the generated vault length only
            if os.environ.get('REDIACC_VERBOSE') and self.output_format != 'json':
                print(f"DEBUG: Generated vault length: {len(queue_vault)} characters")
            
            # Create queue item (bridge-only, no machine specified)
            # Note: API still requires teamName even for bridge-only tasks
            if not hasattr(args, 'team') or not args.team:
                print(format_output(None, self.output_format, None, "Error: --team is required for ssh-test workflow"))
                return 1
            
            queue_response = self.client.token_request("CreateQueueItem", {
                'teamName': args.team,
                'bridgeName': args.bridge,
                'queueVault': queue_vault
            })
            
            if queue_response.get('error'):
                print(format_output(None, self.output_format, None, f"Failed to create queue item: {queue_response['error']}"))
                return 1
            
            # Extract task ID
            task_id = None
            if len(queue_response.get('resultSets', [])) > 1 and queue_response['resultSets'][1].get('data'):
                task_id = queue_response['resultSets'][1]['data'][0].get('taskId') or queue_response['resultSets'][1]['data'][0].get('TaskId')
            
            # Prepare result data
            result = {
                'bridge': args.bridge,
                'host': args.host,
                'user': args.user,
                'task_id': task_id
            }
            
            # Output results
            if self.output_format in ['json', 'json-full']:
                if not getattr(args, 'wait', False):
                    print(format_output(result, self.output_format, "SSH test queued successfully"))
            else:
                print(colorize(f"SSH test queued for {args.user}@{args.host} via bridge '{args.bridge}'", 'GREEN'))
                if task_id:
                    print(f"Task ID: {task_id}")
            
            # Wait for completion if requested
            if getattr(args, 'wait', False) and task_id:
                if self.output_format not in ['json', 'json-full']:
                    print(colorize("Waiting for SSH test...", 'BLUE'))
                poll_interval = getattr(args, 'poll_interval', 2)
                wait_timeout = getattr(args, 'wait_timeout', 30)
                
                # For bridge-only tasks, we might not have a team name
                team_name = getattr(args, 'team', '')
                
                completion_result = self._wait_for_task_completion(task_id, team_name, timeout=wait_timeout, poll_interval=poll_interval)
                
                if self.output_format in ['json', 'json-full']:
                    result = self._format_completion_result(result, completion_result)
                    print(format_output(result, self.output_format))
                else:
                    if completion_result['completed']:
                        print(colorize("SSH test completed successfully", 'GREEN'))
                        # For bridge-only tasks, display structured result data
                        bridge_result = self._extract_bridge_result(completion_result)
                        if bridge_result:
                            print("\nSSH Test Results:")
                            print("-" * 50)
                            print(f"Status: {bridge_result.get('status', 'unknown')}")
                            print(f"Message: {bridge_result.get('message', 'No message')}")
                            print(f"Auth Method: {bridge_result.get('auth_method', 'unknown')}")
                            if 'kernel_compatibility' in bridge_result:
                                kernel_info = bridge_result['kernel_compatibility']
                                if 'os_info' in kernel_info:
                                    print(f"OS: {kernel_info['os_info'].get('pretty_name', 'Unknown')}")
                                print(f"Kernel: {kernel_info.get('kernel_version', 'Unknown')}")
                                print(f"Compatibility: {kernel_info.get('compatibility_status', 'unknown')}")
                    else:
                        print(colorize(f"SSH test {completion_result['status'].lower()}", 'RED'))
                        if completion_result.get('error'):
                            print(f"Error: {completion_result['error']}")
                        return 1
            
            return 0
            
        except Exception as e:
            print(format_output(None, self.output_format, None, f"Workflow error: {str(e)}"))
            return 1
    
    def workflow_machine_setup(self, args):
        """Setup a new machine with datastore and dependencies"""
        try:
            # Import VaultBuilder here to avoid circular import
            from rediacc_cli import VaultBuilder
            
            # Get machine data
            machine_data = self._get_machine_data(args.team, args.machine)
            if not machine_data:
                return 1
            
            # Get vault data
            team_vault = self._get_team_vault(args.team)
            machine_vault = machine_data.get('vaultContent', '{}')
            bridge_name = machine_data.get('bridgeName')
            
            # Build setup parameters
            setup_params = {
                'datastore_size': getattr(args, 'datastore_size', '95%'),
                'source': getattr(args, 'source', 'apt-repo'),
                'rclone_source': getattr(args, 'rclone_source', 'install-script'),
                'docker_source': getattr(args, 'docker_source', 'docker-repo'),
                'install_amd_driver': getattr(args, 'install_amd_driver', 'auto'),
                'install_nvidia_driver': getattr(args, 'install_nvidia_driver', 'auto'),
                'kernel_module_mode': getattr(args, 'kernel_module_mode', 'auto')
            }
            
            # Build setup vault
            vault_builder = VaultBuilder(self.client)
            queue_vault = vault_builder.build_for_setup(
                team_name=args.team,
                machine_name=args.machine,
                bridge_name=bridge_name,
                params=setup_params,
                team_vault=team_vault,
                machine_vault=machine_vault
            )
            
            # Create queue item
            queue_response = self.client.token_request("CreateQueueItem", {
                'teamName': args.team,
                'machineName': args.machine,
                'bridgeName': bridge_name,
                'queueVault': queue_vault
            })
            
            if queue_response.get('error'):
                print(format_output(None, self.output_format, None, f"Failed to create queue item: {queue_response['error']}"))
                return 1
            
            # Extract task ID
            task_id = None
            if len(queue_response.get('resultSets', [])) > 1 and queue_response['resultSets'][1].get('data'):
                task_id = queue_response['resultSets'][1]['data'][0].get('taskId') or queue_response['resultSets'][1]['data'][0].get('TaskId')
            
            # Prepare result data
            result = {
                'machine': args.machine,
                'team': args.team,
                'task_id': task_id,
                'datastore_size': setup_params['datastore_size']
            }
            
            # Output results
            if self.output_format in ['json', 'json-full']:
                if not getattr(args, 'wait', False):
                    print(format_output(result, self.output_format, "Machine setup queued successfully"))
            else:
                print(colorize(f"Machine setup queued for '{args.machine}'", 'GREEN'))
                print(f"Datastore size: {setup_params['datastore_size']}")
                if task_id:
                    print(f"Task ID: {task_id}")
                    if getattr(args, 'trace', False):
                        print(colorize("Use 'rediacc queue trace' command to track progress", 'BLUE'))
            
            # Wait for completion if requested
            if getattr(args, 'wait', False) and task_id:
                if self.output_format != 'json':
                    print(colorize("Waiting for machine setup... (this may take several minutes)", 'BLUE'))
                poll_interval = getattr(args, 'poll_interval', 5)  # Slower polling for long operations
                wait_timeout = getattr(args, 'wait_timeout', 600)  # 10 minutes default for setup
                
                completion_result = self._wait_for_task_completion(task_id, args.team, timeout=wait_timeout, poll_interval=poll_interval)
                
                if self.output_format in ['json', 'json-full']:
                    result = self._format_completion_result(result, completion_result)
                    print(format_output(result, self.output_format))
                else:
                    if completion_result['completed']:
                        print(colorize("Machine setup completed successfully", 'GREEN'))
                        # Display command output if available
                        command_output = self._extract_command_output(completion_result)
                        if command_output:
                            print("\nCommand output:")
                            print("-" * 50)
                            # Clean up the output (replace \n with actual newlines)
                            clean_output = command_output.replace('\\n', '\n')
                            print(clean_output)
                    else:
                        print(colorize(f"Machine setup {completion_result['status'].lower()}", 'RED'))
                        if completion_result.get('error'):
                            print(f"Error: {completion_result['error']}")
                        return 1
            
            return 0
            
        except Exception as e:
            print(format_output(None, self.output_format, None, f"Workflow error: {str(e)}"))
            return 1
    
    def workflow_add_machine(self, args):
        """Create machine and test SSH connection"""
        try:
            # Import VaultBuilder here to avoid circular import
            from rediacc_cli import VaultBuilder
            
            # Step 1: Create machine record in database using existing create command infrastructure
            vault_data = getattr(args, 'vault', '{}')
            if vault_data == '{}' or not vault_data:
                # Create basic machine vault with common fields
                vault_data = json.dumps({
                    "ip": "",
                    "user": "",
                    "datastore": "/mnt/datastore"
                })
            
            # Create a fake args object for the create machine command
            class CreateArgs:
                def __init__(self, team, bridge, name, vault):
                    self.team = team
                    self.bridge = bridge
                    self.name = name
                    self.vault = vault
                    self.vault_file = None
            
            create_args = CreateArgs(args.team, args.bridge, args.name, vault_data)
            
            # Use the existing create machine command
            create_result = self.command_handler.generic_command('create', 'machine', create_args)
            
            if create_result != 0:
                print(format_output(None, self.output_format, None, f"Failed to create machine: {args.name}"))
                return 1
            
            # Log machine creation success
            if self.output_format not in ['json', 'json-full']:
                print(colorize(f"Machine '{args.name}' created in team '{args.team}'", 'GREEN'))
            
            # Step 2: Test connection if not skipped and SSH credentials are available
            test_connection_success = False
            ssh_test_task_id = None
            
            if not getattr(args, 'no_test', False):
                # Parse vault data to check for SSH credentials
                try:
                    vault_json = json.loads(vault_data)
                    has_ssh_creds = vault_json.get('ip') and vault_json.get('user')
                    
                    if has_ssh_creds:
                        # Get team vault for SSH keys
                        team_vault = self._get_team_vault(args.team)
                        
                        # Build SSH test vault
                        vault_builder = VaultBuilder(self.client)
                        ssh_queue_vault = vault_builder.build_for_ssh_test(
                            bridge_name=args.bridge,
                            machine_vault=vault_data,
                            team_name=args.team,
                            team_vault=team_vault
                        )
                        
                        # Create SSH test queue item
                        ssh_response = self.client.token_request("CreateQueueItem", {
                            'teamName': args.team,
                            'bridgeName': args.bridge,
                            'queueVault': ssh_queue_vault
                        })
                        
                        if ssh_response.get('error'):
                            if self.output_format not in ['json', 'json-full']:
                                print(colorize(f"Warning: SSH test failed to queue: {ssh_response['error']}", 'YELLOW'))
                        else:
                            # Extract SSH test task ID
                            if len(ssh_response.get('resultSets', [])) > 1 and ssh_response['resultSets'][1].get('data'):
                                ssh_test_task_id = ssh_response['resultSets'][1]['data'][0].get('taskId') or ssh_response['resultSets'][1]['data'][0].get('TaskId')
                            
                            if self.output_format not in ['json', 'json-full']:
                                print(colorize("SSH connectivity test queued", 'BLUE'))
                                if ssh_test_task_id:
                                    print(f"SSH Test Task ID: {ssh_test_task_id}")
                            
                            # Wait for SSH test if requested
                            if getattr(args, 'wait', False) and ssh_test_task_id:
                                if self.output_format not in ['json', 'json-full']:
                                    print(colorize("Waiting for SSH test...", 'BLUE'))
                                
                                ssh_completion = self._wait_for_task_completion(
                                    ssh_test_task_id, 
                                    args.team, 
                                    timeout=getattr(args, 'wait_timeout', 30),
                                    poll_interval=getattr(args, 'poll_interval', 2)
                                )
                                
                                if ssh_completion['completed']:
                                    test_connection_success = True
                                    if self.output_format not in ['json', 'json-full']:
                                        print(colorize("SSH test completed successfully", 'GREEN'))
                                        
                                        # Display SSH test results
                                        bridge_result = self._extract_bridge_result(ssh_completion)
                                        if bridge_result:
                                            print("\nSSH Test Results:")
                                            print("-" * 50)
                                            print(f"Status: {bridge_result.get('status', 'unknown')}")
                                            print(f"Auth Method: {bridge_result.get('auth_method', 'unknown')}")
                                            if 'kernel_compatibility' in bridge_result:
                                                kernel_info = bridge_result['kernel_compatibility']
                                                if 'os_info' in kernel_info:
                                                    print(f"OS: {kernel_info['os_info'].get('pretty_name', 'Unknown')}")
                                                print(f"Kernel: {kernel_info.get('kernel_version', 'Unknown')}")
                                                print(f"Compatibility: {kernel_info.get('compatibility_status', 'unknown')}")
                                else:
                                    if self.output_format not in ['json', 'json-full']:
                                        print(colorize(f"SSH test {ssh_completion['status'].lower()}", 'YELLOW'))
                                        if ssh_completion.get('error'):
                                            print(f"SSH Test Error: {ssh_completion['error']}")
                    else:
                        if self.output_format not in ['json', 'json-full']:
                            print(colorize("SSH test skipped: No SSH credentials in machine vault", 'YELLOW'))
                        
                except json.JSONDecodeError:
                    if self.output_format not in ['json', 'json-full']:
                        print(colorize("SSH test skipped: Invalid vault JSON", 'YELLOW'))
            else:
                if self.output_format not in ['json', 'json-full']:
                    print(colorize("SSH test skipped (--no-test specified)", 'YELLOW'))
            
            # Step 3: Run machine setup if connection test succeeded and auto-setup requested
            setup_task_id = None
            if test_connection_success and getattr(args, 'auto_setup', False):
                if self.output_format not in ['json', 'json-full']:
                    print(colorize("Starting automatic machine setup...", 'BLUE'))
                
                # Build setup parameters
                setup_params = {
                    'datastore_size': getattr(args, 'datastore_size', '95%'),
                    'source': 'apt-repo',
                    'rclone_source': 'install-script',
                    'docker_source': 'docker-repo',
                    'install_amd_driver': 'auto',
                    'install_nvidia_driver': 'auto',
                    'kernel_module_mode': 'auto'
                }
                
                # Get machine and team vault data  
                team_vault = self._get_team_vault(args.team)
                
                # Build setup vault
                vault_builder = VaultBuilder(self.client)
                setup_queue_vault = vault_builder.build_for_setup(
                    team_name=args.team,
                    machine_name=args.name,
                    bridge_name=args.bridge,
                    params=setup_params,
                    team_vault=team_vault,
                    machine_vault=vault_data
                )
                
                # Create setup queue item
                setup_response = self.client.token_request("CreateQueueItem", {
                    'teamName': args.team,
                    'machineName': args.name,
                    'bridgeName': args.bridge,
                    'queueVault': setup_queue_vault
                })
                
                if setup_response.get('error'):
                    if self.output_format not in ['json', 'json-full']:
                        print(colorize(f"Warning: Machine setup failed to queue: {setup_response['error']}", 'YELLOW'))
                else:
                    # Extract setup task ID
                    if len(setup_response.get('resultSets', [])) > 1 and setup_response['resultSets'][1].get('data'):
                        setup_task_id = setup_response['resultSets'][1]['data'][0].get('taskId') or setup_response['resultSets'][1]['data'][0].get('TaskId')
                    
                    if self.output_format not in ['json', 'json-full']:
                        print(colorize("Machine setup queued", 'GREEN'))
                        if setup_task_id:
                            print(f"Setup Task ID: {setup_task_id}")
            
            # Prepare result data
            result = {
                'machine': args.name,
                'team': args.team,
                'bridge': args.bridge,
                'ssh_test_success': test_connection_success,
                'ssh_test_task_id': ssh_test_task_id,
                'setup_task_id': setup_task_id
            }
            
            # Output final results
            if self.output_format in ['json', 'json-full']:
                print(format_output(result, self.output_format, "Machine creation workflow completed"))
            else:
                print(colorize("\nMachine Creation Workflow Summary:", 'HEADER'))
                print("=" * 50)
                print(f"Machine: {args.name}")
                print(f"Team: {args.team}")
                print(f"Bridge: {args.bridge}")
                print(f"SSH Test: {'Passed' if test_connection_success else 'Skipped/Failed'}")
                if ssh_test_task_id:
                    print(f"SSH Test Task ID: {ssh_test_task_id}")
                if setup_task_id:
                    print(f"Setup Task ID: {setup_task_id}")
                    print(colorize("Tip: Use 'rediacc queue trace' to monitor setup progress", 'BLUE'))
            
            return 0
            
        except Exception as e:
            print(format_output(None, self.output_format, None, f"Workflow error: {str(e)}"))
            return 1