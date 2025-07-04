export interface User {
  email: string;
  permissions?: string;
  company?: string;
}

export interface AuthState {
  user: User | null;
  token: string | null;
  isAuthenticated: boolean;
}

export interface Command {
  id: string;
  command: string;
  args: string[];
  timestamp: Date;
  status: 'pending' | 'running' | 'completed' | 'failed';
  output?: string;
  error?: string;
  duration?: number;
}

export interface CommandHistory {
  commands: Command[];
  favorites: string[];
}

export interface WebSocketMessage {
  type: 'output' | 'error' | 'status' | 'complete';
  data: any;
  commandId?: string;
}

export interface CommandDefinition {
  name: string;
  description: string;
  category: string;
  subcommands?: {
    [key: string]: {
      description: string;
      params: ParamDefinition[];
    };
  };
  params?: ParamDefinition[];
}

export interface ParamDefinition {
  name: string;
  type: 'string' | 'number' | 'boolean' | 'file' | 'select';
  required?: boolean;
  default?: any;
  help?: string;
  choices?: string[];
  multiple?: boolean;
}