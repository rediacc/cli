"""
Simplified mock response handler using JSON configuration.
"""

import json
import re
import uuid
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
import logging


class MockHandler:
    """Handles mock responses based on JSON configuration."""
    
    def __init__(self, config_path: Optional[Path] = None):
        self.logger = logging.getLogger(self.__class__.__name__)
        
        # Load configuration
        if config_path is None:
            config_path = Path(__file__).parent / "mock_config.json"
        
        with open(config_path, 'r') as f:
            self.config = json.load(f)
        
        # Track created entities
        self.entities: Dict[str, Dict[str, Any]] = {}
        
        # ID counters for each entity type
        self.id_counters: Dict[str, int] = {}
    
    def parse_command(self, cmd: List[str]) -> Dict[str, Any]:
        """Parse command line into structured format."""
        cmd_str = ' '.join(cmd)
        
        # Extract command type
        command_type = None
        entity_type = None
        entity_name = None
        params = {}
        
        # Parse positional arguments
        i = 0
        while i < len(cmd):
            part = cmd[i]
            
            # Skip python and script path
            if part.endswith('python') or part.endswith('python3') or part.endswith('.py'):
                i += 1
                continue
            
            # Command actions
            if part in ['create', 'inspect', 'get', 'list', 'update', 'rm', 'delete']:
                command_type = part
                if i + 1 < len(cmd) and not cmd[i + 1].startswith('--'):
                    entity_type = cmd[i + 1]
                    i += 1
                    # Get entity name for inspect/get/update/delete
                    if command_type in ['inspect', 'get', 'update', 'rm', 'delete']:
                        if i + 1 < len(cmd) and not cmd[i + 1].startswith('--'):
                            entity_name = cmd[i + 1]
                            i += 1
            
            # Parse parameters
            elif part.startswith('--'):
                param_name = part[2:].replace('-', '_')
                if i + 1 < len(cmd):
                    param_value = cmd[i + 1]
                    # Try to parse JSON values
                    if param_value.startswith('{') or param_value.startswith('['):
                        try:
                            params[param_name] = json.loads(param_value)
                        except:
                            params[param_name] = param_value
                    else:
                        params[param_name] = param_value
                    i += 1
            
            i += 1
        
        return {
            'command': command_type,
            'entity': entity_type,
            'name': entity_name or params.get('name'),
            'params': params
        }
    
    def generate_response(self, parsed_cmd: Dict[str, Any]) -> Dict[str, Any]:
        """Generate mock response based on parsed command."""
        command = parsed_cmd['command']
        entity_type = parsed_cmd['entity']
        entity_name = parsed_cmd['name']
        params = parsed_cmd['params']
        
        # Handle special commands
        if entity_type == 'queue':
            return self._handle_queue_command(command, params)
        
        if command == 'login':
            return self._handle_login(params)
        
        # Normalize entity type (remove plural)
        if entity_type and entity_type.endswith('s'):
            entity_singular = entity_type[:-1]
        else:
            entity_singular = entity_type
        
        # Get entity config
        entity_config = self.config['entities'].get(entity_singular, {})
        if not entity_config:
            return {"success": False, "error": f"Unknown entity type: {entity_type}"}
        
        # Handle different command types
        if command == 'create':
            return self._handle_create(entity_singular, entity_name, params, entity_config)
        elif command in ['inspect', 'get']:
            return self._handle_get(entity_singular, entity_name, entity_config)
        elif command == 'list':
            return self._handle_list(entity_singular, params)
        elif command == 'update':
            return self._handle_update(entity_singular, entity_name, params)
        elif command in ['rm', 'delete']:
            return self._handle_delete(entity_singular, entity_name)
        
        return {"success": False, "error": f"Unknown command: {command}"}
    
    def _handle_create(self, entity_type: str, entity_name: str, 
                      params: Dict[str, Any], entity_config: Dict[str, Any]) -> Dict[str, Any]:
        """Handle entity creation."""
        # Validate entity name
        if not entity_name and not params.get('name'):
            return self._error_response('missing_required', entity=entity_type, field='name')
        
        name = entity_name or params.get('name', '')
        
        # Check for invalid characters in name
        if name and not re.match(r'^[a-zA-Z0-9_-]+$', name):
            return self._error_response('invalid_name', name=name)
        
        # Check for missing required fields
        for field in entity_config.get('required_params', []):
            if field not in params and field != 'name':
                # Check if it's a dependency that doesn't exist
                if field in ['team', 'bridge', 'region', 'company']:
                    value = params.get(field)
                    if value and not self._entity_exists(field, value):
                        return {"success": False, "error": f"{field} '{value}' not found"}
        
        # Generate ID
        counter = self.id_counters.get(entity_type, 0)
        entity_id = f"{entity_config['id_prefix']}-{counter}"
        self.id_counters[entity_type] = counter + 1
        
        # Build entity data
        entity_data = {
            "id": entity_id,
            "name": name
        }
        
        # Add fields from params and defaults
        for field in entity_config.get('response_fields', []):
            if field in params:
                entity_data[field] = params[field]
            elif field in entity_config.get('default_values', {}):
                entity_data[field] = entity_config['default_values'][field]
        
        # Store entity
        entity_key = f"{entity_type}:{name}"
        self.entities[entity_key] = entity_data
        
        # Return response
        response = {"success": True}
        response.update(entity_data)
        return response
    
    def _handle_get(self, entity_type: str, entity_name: str, 
                   entity_config: Dict[str, Any]) -> Dict[str, Any]:
        """Handle entity retrieval."""
        entity_key = f"{entity_type}:{entity_name}"
        
        # Check if entity exists
        if entity_key in self.entities:
            response = {"success": True}
            response.update(self.entities[entity_key])
            
            # Add verify fields
            for field in entity_config.get('verify_fields', []):
                if field == 'vault_encrypted':
                    response[field] = True
                elif field not in response and field in entity_config.get('default_values', {}):
                    response[field] = entity_config['default_values'][field]
            
            return response
        
        # Generate default response if not found
        response = {
            "success": True,
            "id": f"{entity_config['id_prefix']}-default",
            "name": entity_name
        }
        
        # Add default values
        for field in entity_config.get('verify_fields', []):
            if field == 'vault_encrypted':
                response[field] = True
            elif field in entity_config.get('default_values', {}):
                response[field] = entity_config['default_values'][field]
        
        return response
    
    def _handle_list(self, entity_type: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle entity listing."""
        items = []
        
        # Find all entities of this type
        for key, data in self.entities.items():
            if key.startswith(f"{entity_type}:"):
                items.append(data)
        
        return {
            "success": True,
            "items": items,
            "count": len(items)
        }
    
    def _handle_update(self, entity_type: str, entity_name: str, 
                      params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle entity update."""
        entity_key = f"{entity_type}:{entity_name}"
        
        if entity_key in self.entities:
            # Update entity data
            self.entities[entity_key].update(params)
            return {"success": True, "message": "Updated"}
        
        return {"success": False, "error": f"{entity_type} '{entity_name}' not found"}
    
    def _handle_delete(self, entity_type: str, entity_name: str) -> Dict[str, Any]:
        """Handle entity deletion."""
        entity_key = f"{entity_type}:{entity_name}"
        
        if entity_key in self.entities:
            del self.entities[entity_key]
            return {"success": True, "message": "Deleted"}
        
        # Return success even if not found (idempotent delete)
        return {"success": True, "message": "Already deleted"}
    
    def _handle_queue_command(self, command: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle queue-specific commands."""
        if command == 'create' or 'create' in params.get('command', ''):
            task_id = f"task-{uuid.uuid4().hex[:8]}"
            return {
                "success": True,
                "taskId": task_id,
                "status": "PENDING"
            }
        
        elif command == 'status' or 'status' in params.get('command', ''):
            return {
                "success": True,
                "taskId": params.get('task_id', 'task-123'),
                "status": "COMPLETED",
                "result": "Success"
            }
        
        return {"success": False, "error": "Unknown queue command"}
    
    def _handle_login(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle login command."""
        return {
            "success": True,
            "token": f"test-token-{uuid.uuid4().hex[:8]}",
            "nextRequestCredential": f"next-token-{uuid.uuid4().hex[:8]}"
        }
    
    def _entity_exists(self, entity_type: str, name: str) -> bool:
        """Check if an entity exists."""
        entity_key = f"{entity_type}:{name}"
        return entity_key in self.entities
    
    def _error_response(self, error_type: str, **kwargs) -> Dict[str, Any]:
        """Generate error response from template."""
        template = self.config['error_responses'].get(error_type, {})
        response = {}
        
        for key, value in template.items():
            if isinstance(value, str):
                # Replace placeholders
                for param_key, param_value in kwargs.items():
                    value = value.replace(f"{{{param_key}}}", str(param_value))
                response[key] = value
            else:
                response[key] = value
        
        return response
    
    def reset(self):
        """Reset mock state."""
        self.entities.clear()
        self.id_counters.clear()