"""
Entity definitions and validators for the Rediacc CLI test framework.
Defines the data structures and relationships between entities.
"""

from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional, Set
from enum import Enum
import re


class EntityType(Enum):
    """All entity types in the system"""
    COMPANY = "company"
    USER = "user"
    TEAM = "team"
    REGION = "region"
    BRIDGE = "bridge"
    MACHINE = "machine"
    REPOSITORY = "repository"
    STORAGE = "storage"
    SCHEDULE = "schedule"
    QUEUE_ITEM = "queue_item"
    
    @classmethod
    def _missing_(cls, value):
        """Handle variations in entity naming"""
        # Handle both singular and plural forms
        value = value.lower().replace('-', '_')
        if value.endswith('s'):
            singular = value[:-1]
            for member in cls:
                if member.value == singular:
                    return member
        return None


class EntityDependencies:
    """
    Defines the dependency graph for entities.
    Maps each entity to its required dependencies.
    """
    DEPENDENCIES = {
        EntityType.COMPANY: [],
        EntityType.USER: [EntityType.COMPANY],
        EntityType.TEAM: [EntityType.COMPANY],
        EntityType.REGION: [EntityType.COMPANY],
        EntityType.BRIDGE: [EntityType.REGION],
        EntityType.MACHINE: [EntityType.TEAM, EntityType.BRIDGE],
        EntityType.REPOSITORY: [EntityType.TEAM, EntityType.MACHINE],
        EntityType.STORAGE: [EntityType.TEAM],
        EntityType.SCHEDULE: [EntityType.TEAM],
        EntityType.QUEUE_ITEM: [EntityType.TEAM, EntityType.MACHINE]
    }
    
    @classmethod
    def get_dependencies(cls, entity_type: EntityType) -> List[EntityType]:
        """Get direct dependencies for an entity type"""
        return cls.DEPENDENCIES.get(entity_type, [])
    
    @classmethod
    def get_all_dependencies(cls, entity_type: EntityType) -> Set[EntityType]:
        """Get all dependencies (including transitive) for an entity type"""
        visited = set()
        to_visit = [entity_type]
        
        while to_visit:
            current = to_visit.pop()
            if current in visited:
                continue
                
            visited.add(current)
            deps = cls.get_dependencies(current)
            to_visit.extend(deps)
        
        visited.remove(entity_type)  # Remove self
        return visited
    
    @classmethod
    def get_dependency_order(cls) -> List[EntityType]:
        """Get entities in dependency order (items with no deps first)"""
        order = []
        remaining = set(EntityType)
        
        while remaining:
            # Find entities with no remaining dependencies
            ready = []
            for entity in remaining:
                deps = cls.get_dependencies(entity)
                if all(dep not in remaining for dep in deps):
                    ready.append(entity)
            
            if not ready:
                raise ValueError("Circular dependency detected")
            
            # Add to order and remove from remaining
            order.extend(sorted(ready, key=lambda e: e.value))
            remaining -= set(ready)
        
        return order


@dataclass
class BaseEntity:
    """Base class for all entities"""
    name: str
    id: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    vault_data: Dict[str, Any] = field(default_factory=dict)
    
    def validate_name(self):
        """Validate entity name"""
        if not self.name:
            raise ValueError("Name is required")
        
        # Check for valid characters (alphanumeric, dash, underscore)
        if not re.match(r'^[a-zA-Z0-9_-]+$', self.name):
            raise ValueError(f"Invalid name '{self.name}'. Use only alphanumeric, dash, and underscore.")
        
        # Check length
        if len(self.name) > 100:
            raise ValueError(f"Name '{self.name}' is too long (max 100 characters)")
    
    def validate(self):
        """Validate the entity"""
        self.validate_name()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API calls"""
        data = {
            'name': self.name
        }
        if self.id:
            data['id'] = self.id
        if self.vault_data:
            data['vault'] = self.vault_data
        return data


@dataclass
class Company(BaseEntity):
    """Company entity"""
    email: Optional[str] = None
    
    def validate(self):
        super().validate()
        if self.email and '@' not in self.email:
            raise ValueError(f"Invalid email '{self.email}'")


@dataclass
class User(BaseEntity):
    """User entity"""
    company: str = ""
    email: str = ""
    role: str = "User"
    
    def validate(self):
        super().validate()
        if not self.company:
            raise ValueError("Company is required for User")
        if not self.email or '@' not in self.email:
            raise ValueError(f"Valid email is required, got '{self.email}'")
        if self.role not in ['Admin', 'User', 'Viewer']:
            raise ValueError(f"Invalid role '{self.role}'")


@dataclass
class Team(BaseEntity):
    """Team entity"""
    company: str = ""
    
    def validate(self):
        super().validate()
        if not self.company:
            raise ValueError("Company is required for Team")


@dataclass
class Region(BaseEntity):
    """Region entity"""
    company: str = ""
    location: str = "us-east-1"
    
    def validate(self):
        super().validate()
        if not self.company:
            raise ValueError("Company is required for Region")


@dataclass
class Bridge(BaseEntity):
    """Bridge entity"""
    region: str = ""
    api_url: Optional[str] = None
    
    def validate(self):
        super().validate()
        if not self.region:
            raise ValueError("Region is required for Bridge")


@dataclass
class Machine(BaseEntity):
    """Machine entity"""
    team: str = ""
    bridge: str = ""
    ip_address: Optional[str] = None
    ssh_user: Optional[str] = None
    datastore_path: Optional[str] = None
    
    def validate(self):
        super().validate()
        if not self.team:
            raise ValueError("Team is required for Machine")
        if not self.bridge:
            raise ValueError("Bridge is required for Machine")
    
    def to_dict(self) -> Dict[str, Any]:
        data = super().to_dict()
        data['team'] = self.team
        data['bridge'] = self.bridge
        
        # Machine-specific vault data
        if self.ip_address or self.ssh_user or self.datastore_path:
            data['vault'] = data.get('vault', {})
            if self.ip_address:
                data['vault']['ip'] = self.ip_address
            if self.ssh_user:
                data['vault']['user'] = self.ssh_user
            if self.datastore_path:
                data['vault']['datastore'] = self.datastore_path
        
        return data


@dataclass
class Repository(BaseEntity):
    """Repository entity"""
    team: str = ""
    machine: str = ""
    repo_type: str = "git"
    url: Optional[str] = None
    
    def validate(self):
        super().validate()
        if not self.team:
            raise ValueError("Team is required for Repository")
        if not self.machine:
            raise ValueError("Machine is required for Repository")
        if self.repo_type not in ['git', 'svn', 'mercurial', 'directory']:
            raise ValueError(f"Invalid repository type '{self.repo_type}'")


@dataclass
class Storage(BaseEntity):
    """Storage entity"""
    team: str = ""
    storage_type: str = "s3"
    bucket: Optional[str] = None
    
    def validate(self):
        super().validate()
        if not self.team:
            raise ValueError("Team is required for Storage")
        if self.storage_type not in ['s3', 'azure', 'gcs', 'local']:
            raise ValueError(f"Invalid storage type '{self.storage_type}'")


@dataclass
class Schedule(BaseEntity):
    """Schedule entity"""
    team: str = ""
    cron: str = "0 0 * * *"
    enabled: bool = True
    function: str = ""
    
    def validate(self):
        super().validate()
        if not self.team:
            raise ValueError("Team is required for Schedule")
        if not self.function:
            raise ValueError("Function is required for Schedule")
        # TODO: Add cron validation


@dataclass
class QueueItem:
    """Queue item entity (different from others as it's transient)"""
    task_id: str
    team: str
    machine: str
    bridge: Optional[str] = None
    function: str = ""
    status: str = "PENDING"
    priority: int = 3
    vault_data: Dict[str, Any] = field(default_factory=dict)
    result: Optional[str] = None
    error: Optional[str] = None
    
    def validate(self):
        if not self.team:
            raise ValueError("Team is required for QueueItem")
        if not self.machine:
            raise ValueError("Machine is required for QueueItem")
        if not self.function:
            raise ValueError("Function is required for QueueItem")
        if self.priority not in range(1, 6):
            raise ValueError(f"Priority must be 1-5, got {self.priority}")
        if self.status not in ['PENDING', 'ASSIGNED', 'PROCESSING', 'COMPLETED', 'FAILED', 'CANCELLED']:
            raise ValueError(f"Invalid status '{self.status}'")


class EntityFactory:
    """Factory for creating entity instances"""
    
    ENTITY_CLASSES = {
        EntityType.COMPANY: Company,
        EntityType.USER: User,
        EntityType.TEAM: Team,
        EntityType.REGION: Region,
        EntityType.BRIDGE: Bridge,
        EntityType.MACHINE: Machine,
        EntityType.REPOSITORY: Repository,
        EntityType.STORAGE: Storage,
        EntityType.SCHEDULE: Schedule,
    }
    
    @classmethod
    def create(cls, entity_type: EntityType, **kwargs) -> BaseEntity:
        """Create an entity instance"""
        entity_class = cls.ENTITY_CLASSES.get(entity_type)
        if not entity_class:
            raise ValueError(f"Unknown entity type: {entity_type}")
        
        entity = entity_class(**kwargs)
        entity.validate()
        return entity
    
    @classmethod
    def from_dict(cls, entity_type: EntityType, data: Dict[str, Any]) -> BaseEntity:
        """Create an entity from a dictionary"""
        entity_class = cls.ENTITY_CLASSES.get(entity_type)
        if not entity_class:
            raise ValueError(f"Unknown entity type: {entity_type}")
        
        # Filter out None values and unknown fields
        valid_fields = entity_class.__dataclass_fields__.keys()
        filtered_data = {k: v for k, v in data.items() 
                        if k in valid_fields and v is not None}
        
        entity = entity_class(**filtered_data)
        entity.validate()
        return entity


class EntityValidator:
    """Validates entity relationships and constraints"""
    
    @staticmethod
    def validate_dependencies(entities: Dict[str, BaseEntity]) -> List[str]:
        """
        Validate that all entity dependencies are satisfied.
        Returns list of validation errors.
        """
        errors = []
        
        for entity_name, entity in entities.items():
            entity_type = EntityType(entity.__class__.__name__.lower())
            
            # Check each dependency
            deps = EntityDependencies.get_dependencies(entity_type)
            for dep_type in deps:
                # Find the dependency value in the entity
                dep_field = dep_type.value
                dep_value = getattr(entity, dep_field, None)
                
                if not dep_value:
                    errors.append(f"{entity_name}: Missing required {dep_field}")
                    continue
                
                # Check if dependency exists
                dep_exists = any(
                    e.__class__.__name__.lower() == dep_type.value and e.name == dep_value
                    for e in entities.values()
                )
                
                if not dep_exists:
                    errors.append(f"{entity_name}: {dep_field} '{dep_value}' not found")
        
        return errors