import { CommandDefinition } from '@/types';

export const commandDefinitions: Record<string, CommandDefinition> = {
  login: {
    name: 'login',
    description: 'Authenticate with Rediacc',
    category: 'auth',
    params: [
      { name: '--email', type: 'string', required: true, help: 'User email address' },
      { name: '--password', type: 'string', required: true, help: 'User password' },
      { name: '--session-name', type: 'string', help: 'Name for this session' },
      { name: '--tfa-code', type: 'string', help: 'Two-factor authentication code' },
      { name: '--permissions', type: 'string', help: 'Requested permission group' },
      { name: '--expiration', type: 'number', default: 24, help: 'Token expiration in hours' },
    ],
  },
  logout: {
    name: 'logout',
    description: 'Logout from Rediacc',
    category: 'auth',
    params: [],
  },
  list: {
    name: 'list',
    description: 'List various resources',
    category: 'read',
    subcommands: {
      teams: {
        description: 'List all teams',
        params: [],
      },
      regions: {
        description: 'List all regions',
        params: [],
      },
      bridges: {
        description: 'List bridges in a region',
        params: [
          { name: 'region', type: 'string', required: true, help: 'Region name' },
        ],
      },
      users: {
        description: 'List company users',
        params: [],
      },
      'team-machines': {
        description: 'List machines in a team',
        params: [
          { name: 'team', type: 'string', required: true, help: 'Team name' },
        ],
      },
      'team-repositories': {
        description: 'List repositories in a team',
        params: [
          { name: 'team', type: 'string', required: true, help: 'Team name' },
        ],
      },
      'team-storages': {
        description: 'List storages in a team',
        params: [
          { name: 'team', type: 'string', required: true, help: 'Team name' },
        ],
      },
      'team-schedules': {
        description: 'List schedules in a team',
        params: [
          { name: 'team', type: 'string', required: true, help: 'Team name' },
        ],
      },
      sessions: {
        description: 'List user sessions',
        params: [],
      },
    },
  },
  create: {
    name: 'create',
    description: 'Create new resources',
    category: 'write',
    subcommands: {
      team: {
        description: 'Create a new team',
        params: [
          { name: 'name', type: 'string', required: true, help: 'Team name' },
          { name: '--vault', type: 'string', help: 'JSON vault data' },
          { name: '--vault-file', type: 'file', help: 'File containing JSON vault data' },
        ],
      },
      region: {
        description: 'Create a new region',
        params: [
          { name: 'name', type: 'string', required: true, help: 'Region name' },
          { name: '--vault', type: 'string', help: 'JSON vault data' },
          { name: '--vault-file', type: 'file', help: 'File containing JSON vault data' },
        ],
      },
      bridge: {
        description: 'Create a new bridge',
        params: [
          { name: 'region', type: 'string', required: true, help: 'Region name' },
          { name: 'name', type: 'string', required: true, help: 'Bridge name' },
          { name: '--vault', type: 'string', help: 'JSON vault data' },
          { name: '--vault-file', type: 'file', help: 'File containing JSON vault data' },
        ],
      },
      machine: {
        description: 'Create a new machine',
        params: [
          { name: 'team', type: 'string', required: true, help: 'Team name' },
          { name: 'bridge', type: 'string', required: true, help: 'Bridge name' },
          { name: 'name', type: 'string', required: true, help: 'Machine name' },
          { name: '--vault', type: 'string', help: 'JSON vault data' },
          { name: '--vault-file', type: 'file', help: 'File containing JSON vault data' },
        ],
      },
      repository: {
        description: 'Create a new repository',
        params: [
          { name: 'team', type: 'string', required: true, help: 'Team name' },
          { name: 'name', type: 'string', required: true, help: 'Repository name' },
          { name: '--vault', type: 'string', help: 'JSON vault data' },
          { name: '--vault-file', type: 'file', help: 'File containing JSON vault data' },
        ],
      },
      storage: {
        description: 'Create a new storage',
        params: [
          { name: 'team', type: 'string', required: true, help: 'Team name' },
          { name: 'name', type: 'string', required: true, help: 'Storage name' },
          { name: '--vault', type: 'string', help: 'JSON vault data' },
          { name: '--vault-file', type: 'file', help: 'File containing JSON vault data' },
        ],
      },
      schedule: {
        description: 'Create a new schedule',
        params: [
          { name: 'team', type: 'string', required: true, help: 'Team name' },
          { name: 'name', type: 'string', required: true, help: 'Schedule name' },
          { name: '--vault', type: 'string', help: 'JSON vault data' },
          { name: '--vault-file', type: 'file', help: 'File containing JSON vault data' },
        ],
      },
      'queue-item': {
        description: 'Create a new queue item',
        params: [
          { name: 'team', type: 'string', required: true, help: 'Team name' },
          { name: 'machine', type: 'string', required: true, help: 'Machine name' },
          { name: 'bridge', type: 'string', required: true, help: 'Bridge name' },
          { 
            name: '--priority', 
            type: 'select', 
            default: 3, 
            choices: ['1', '2', '3', '4', '5'], 
            help: 'Priority level (1=highest, 5=lowest)' 
          },
          { name: '--vault', type: 'string', help: 'JSON vault data' },
          { name: '--vault-file', type: 'file', help: 'File containing JSON vault data' },
        ],
      },
    },
  },
  update: {
    name: 'update',
    description: 'Update existing resources',
    category: 'write',
    subcommands: {
      team: {
        description: 'Update team name',
        params: [
          { name: 'name', type: 'string', required: true, help: 'Current team name' },
          { name: 'new_name', type: 'string', required: true, help: 'New team name' },
        ],
      },
      region: {
        description: 'Update region name',
        params: [
          { name: 'name', type: 'string', required: true, help: 'Current region name' },
          { name: 'new_name', type: 'string', required: true, help: 'New region name' },
        ],
      },
      bridge: {
        description: 'Update bridge name',
        params: [
          { name: 'region', type: 'string', required: true, help: 'Region name' },
          { name: 'name', type: 'string', required: true, help: 'Current bridge name' },
          { name: 'new_name', type: 'string', required: true, help: 'New bridge name' },
        ],
      },
      machine: {
        description: 'Update machine name',
        params: [
          { name: 'team', type: 'string', required: true, help: 'Team name' },
          { name: 'name', type: 'string', required: true, help: 'Current machine name' },
          { name: 'new_name', type: 'string', required: true, help: 'New machine name' },
        ],
      },
      'machine-bridge': {
        description: 'Update machine bridge assignment',
        params: [
          { name: 'team', type: 'string', required: true, help: 'Team name' },
          { name: 'name', type: 'string', required: true, help: 'Machine name' },
          { name: 'new_bridge', type: 'string', required: true, help: 'New bridge name' },
        ],
      },
    },
  },
  rm: {
    name: 'rm',
    description: 'Remove resources',
    category: 'write',
    subcommands: {
      team: {
        description: 'Delete a team',
        params: [
          { name: 'name', type: 'string', required: true, help: 'Team name' },
          { name: '--force', type: 'boolean', help: 'Skip confirmation' },
        ],
      },
      machine: {
        description: 'Delete a machine',
        params: [
          { name: 'team', type: 'string', required: true, help: 'Team name' },
          { name: 'name', type: 'string', required: true, help: 'Machine name' },
          { name: '--force', type: 'boolean', help: 'Skip confirmation' },
        ],
      },
      bridge: {
        description: 'Delete a bridge',
        params: [
          { name: 'region', type: 'string', required: true, help: 'Region name' },
          { name: 'name', type: 'string', required: true, help: 'Bridge name' },
          { name: '--force', type: 'boolean', help: 'Skip confirmation' },
        ],
      },
      region: {
        description: 'Delete a region',
        params: [
          { name: 'name', type: 'string', required: true, help: 'Region name' },
          { name: '--force', type: 'boolean', help: 'Skip confirmation' },
        ],
      },
      repository: {
        description: 'Delete a repository',
        params: [
          { name: 'team', type: 'string', required: true, help: 'Team name' },
          { name: 'name', type: 'string', required: true, help: 'Repository name' },
          { name: '--force', type: 'boolean', help: 'Skip confirmation' },
        ],
      },
      storage: {
        description: 'Delete a storage',
        params: [
          { name: 'team', type: 'string', required: true, help: 'Team name' },
          { name: 'name', type: 'string', required: true, help: 'Storage name' },
          { name: '--force', type: 'boolean', help: 'Skip confirmation' },
        ],
      },
      schedule: {
        description: 'Delete a schedule',
        params: [
          { name: 'team', type: 'string', required: true, help: 'Team name' },
          { name: 'name', type: 'string', required: true, help: 'Schedule name' },
          { name: '--force', type: 'boolean', help: 'Skip confirmation' },
        ],
      },
    },
  },
  queue: {
    name: 'queue',
    description: 'Manage queue items',
    category: 'queue',
    subcommands: {
      list: {
        description: 'List queue items',
        params: [
          { name: '--team', type: 'string', help: 'Filter by team name' },
          { name: '--machine', type: 'string', help: 'Filter by machine name' },
          { name: '--bridge', type: 'string', help: 'Filter by bridge name' },
          { 
            name: '--status', 
            type: 'select', 
            choices: ['PENDING', 'PROCESSING', 'COMPLETED', 'FAILED'],
            help: 'Filter by status' 
          },
          { name: '--priority', type: 'number', help: 'Filter by priority' },
          { name: '--max-records', type: 'number', help: 'Maximum records to retrieve' },
        ],
      },
      'get-next': {
        description: 'Get next queue items',
        params: [
          { name: '--count', type: 'number', default: 3, help: 'Number of items to retrieve' },
        ],
      },
      complete: {
        description: 'Mark queue item as completed',
        params: [
          { name: 'task_id', type: 'string', required: true, help: 'Task ID' },
          { name: '--vault', type: 'string', help: 'Final vault data' },
          { name: '--vault-file', type: 'file', help: 'File containing final vault data' },
        ],
      },
      cancel: {
        description: 'Cancel a queue item',
        params: [
          { name: 'task_id', type: 'string', required: true, help: 'Task ID' },
          { name: '--force', type: 'boolean', help: 'Skip confirmation' },
        ],
      },
      retry: {
        description: 'Retry a failed queue item',
        params: [
          { name: 'task_id', type: 'string', required: true, help: 'Task ID' },
        ],
      },
    },
  },
};