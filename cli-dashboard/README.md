# Rediacc CLI Dashboard

A web-based graphical interface for the Rediacc CLI, providing visual command building, real-time execution, and command history management.

## Features

- **Visual Command Builder**: Build CLI commands using forms instead of memorizing syntax
- **Real-time Output**: See command output as it executes with WebSocket streaming
- **Command History**: Track all executed commands with search and filtering
- **Authentication**: Secure login using existing Rediacc credentials
- **Dark Mode**: Toggle between light and dark themes
- **Responsive Design**: Works on desktop and tablet devices
- **Multi-language Support**: Available in 8 languages with RTL support
  - English (en)
  - Spanish (es)
  - French (fr)
  - German (de)
  - Chinese (zh)
  - Japanese (ja)
  - Arabic (ar) - with RTL layout
  - Turkish (tr)

## Quick Start

### Prerequisites

- Node.js 18+ and npm
- Python 3.8+ with pip
- Rediacc CLI installed and configured

### Installation

```bash
# Install dashboard and WebSocket dependencies
./go cli dashboard_install
```

### Development

```bash
# Start dashboard in development mode (includes WebSocket server)
./go cli dashboard_dev
```

The dashboard will be available at http://localhost:5173

### Production Build

```bash
# Build for production
./go cli dashboard_build

# Serve production build
./go cli dashboard_serve
```

## Architecture

### Frontend (React + TypeScript)

- **Framework**: React 18 with TypeScript
- **UI Library**: Ant Design v5
- **Build Tool**: Vite
- **Key Features**:
  - Command builder with dynamic forms
  - Real-time WebSocket integration
  - Command history with local storage
  - Token-based authentication

### Backend (Python WebSocket Server)

- **File**: `rediacc_cli_websocket.py`
- **Port**: 8765 (WebSocket)
- **Features**:
  - JWT authentication
  - Command execution with streaming output
  - Process management
  - Error handling

## Usage

### Login

1. Navigate to http://localhost:5173
2. Enter your Rediacc email and password
3. Click "Sign In"

### Building Commands

1. Go to "Command Builder" page
2. Select a command from the dropdown
3. Fill in the required parameters
4. Click "Execute" to run the command
5. View real-time output below

### Viewing History

1. Go to "History" page
2. Search and filter previous commands
3. Re-run or copy commands
4. Mark commands as favorites

## Configuration

### WebSocket Server

Edit `rediacc_cli_websocket.py` to configure:
- Host and port (default: localhost:8765)
- JWT secret for authentication
- Command timeout settings

### Dashboard Settings

Edit `vite.config.ts` to configure:
- API proxy settings
- WebSocket endpoint
- Development server port

## Security

- All API calls require authentication
- WebSocket connections use JWT tokens
- Commands run with user's CLI permissions
- No credentials stored in browser

## Troubleshooting

### WebSocket Connection Failed

1. Ensure WebSocket server is running:
   ```bash
   ./go cli websocket_start
   ```

2. Check firewall settings for port 8765

### Authentication Issues

1. Verify API server is running on port 7322
2. Check token expiration
3. Try logging out and back in

### Command Execution Errors

1. Ensure CLI is properly installed
2. Check Python path in WebSocket server
3. Verify user has necessary permissions

## Development

### Project Structure

```
cli-dashboard/
├── src/
│   ├── components/     # Reusable UI components
│   ├── pages/         # Page components
│   ├── services/      # API services
│   ├── hooks/         # Custom React hooks
│   ├── utils/         # Utility functions
│   └── types/         # TypeScript types
├── index.html
├── package.json
└── vite.config.ts
```

### Adding New Commands

1. Update `src/utils/commandDefinitions.ts`
2. Add command configuration with parameters
3. Test in Command Builder page

### Contributing

1. Follow existing code style
2. Add TypeScript types for new features
3. Test with both light and dark themes
4. Ensure responsive design works

## License

Part of the Rediacc monorepo. See main LICENSE file.