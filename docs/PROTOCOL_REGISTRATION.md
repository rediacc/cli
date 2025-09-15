# rediacc:// Protocol Registration

This document describes the cross-platform browser integration functionality that allows `rediacc://` URLs to automatically launch the appropriate CLI tools on Windows, macOS, and Linux.

## Overview

The Rediacc CLI includes cross-platform protocol registration support that enables seamless browser integration. When registered, clicking on `rediacc://` URLs in web pages will automatically execute the corresponding CLI commands on Windows, macOS, and Linux systems.

## Features

- **Automatic Protocol Registration**: Registers during `pip install` (with admin privileges)
- **Browser Integration**: Click `rediacc://` URLs to launch CLI tools
- **Multiple Actions**: Support for sync, terminal, plugin, and browser actions
- **URL Parameter Parsing**: Extract tokens, teams, machines, repositories, and action parameters
- **Cross-Platform Support**: Works on Windows, macOS, and Linux with consistent command structure

## URL Format

The `rediacc://` URL format follows this structure:

```
rediacc://token/team/machine/repository[/action][?parameters]
```

### Components

- **token**: Authentication token (required)
- **team**: Team name (required)
- **machine**: Machine name (required) 
- **repository**: Repository name (required)
- **action**: Action to perform (optional: sync, terminal, plugin, browser)
- **parameters**: Query string parameters specific to the action (optional)

### Examples

#### Sync Operations
```
# Upload files with mirror mode
rediacc://abc123/Production/web-server/webapp/sync?direction=upload&localPath=C:\MyProject&mirror=true

# Download files with verification
rediacc://abc123/Production/web-server/webapp/sync?direction=download&localPath=C:\Backup&verify=true
```

#### Terminal Access
```
# Open repository terminal
rediacc://abc123/Production/web-server/webapp/terminal

# Execute specific command
rediacc://abc123/Production/web-server/webapp/terminal?command=ls%20-la

# Connect to machine directly
rediacc://abc123/Production/web-server/webapp/terminal?terminalType=machine
```

#### Plugin Access
```
# Start Jupyter plugin on specific port
rediacc://abc123/Production/web-server/webapp/plugin?name=jupyter&port=8888
```

#### File Browser
```
# Browse specific directory
rediacc://abc123/Production/web-server/webapp/browser?path=/var/log
```

## Installation and Registration

### Automatic Registration (Recommended)

The protocol is automatically registered during installation if:
1. Installing on Windows
2. Running with administrator privileges
3. Not in a virtual environment

```bash
pip install rediacc
```

### Manual Registration

If automatic registration didn't work, you can register manually:

#### Current Command Structure (All Platforms)
```bash
# Register protocol for current user
./rediacc protocol register

# Register protocol system-wide (requires admin/sudo)
./rediacc protocol register --system-wide

# Check registration status
./rediacc protocol status

# Unregister protocol
./rediacc protocol unregister

# Unregister system-wide
./rediacc protocol unregister --system-wide
```


### Prerequisites

**All Platforms:**
- **Python**: Python executable must be accessible
- **Rediacc CLI**: Properly installed and configured

**Platform-Specific:**
- **Windows**: Administrator privileges required for system-wide registration (registry modifications)
- **macOS**: System-wide registration requires `sudo` (LaunchAgent installation)
- **Linux**: System-wide registration requires `sudo` (system application entries)

## Registry Details

The protocol registration creates these Windows registry entries:

```
HKEY_CLASSES_ROOT\rediacc
├── (Default) = "URL:Rediacc Protocol"
├── URL Protocol = ""
└── shell\open\command
    └── (Default) = "python \"path\to\cli_main.py\" protocol-handler \"%1\""
```

## Command Mapping

When a `rediacc://` URL is clicked, the system:

1. **Parses the URL** to extract components and parameters
2. **Routes to appropriate tool** based on the action:
   - `sync` → `rediacc-sync` tool
   - `terminal` → `rediacc-term` tool
   - `plugin` → `rediacc` main CLI
   - `browser` → `rediacc` main CLI
3. **Executes the command** with the extracted parameters

## Error Handling

The protocol handler includes comprehensive error handling:

- **Invalid URLs**: Clear error messages for malformed URLs
- **Missing Components**: Validation of required URL components
- **Permission Issues**: Helpful messages for admin privilege requirements
- **Tool Errors**: Proper exit codes and error propagation

## Development and Testing

### Running Tests

```bash
# Run protocol handler tests
python -m pytest tests/test_protocol_handler.py -v

# Run with coverage
python -m pytest tests/test_protocol_handler.py --cov=cli.core.protocol_handler
```

### Example Script

```bash
# Run example demonstrations
python examples/protocol_examples.py
```

### Development Registration

For development installs:

```bash
# Install in development mode
pip install -e .

# Manually register for testing
rediacc --register-protocol
```

## Troubleshooting

### Common Issues

1. **Not Registered**: Run with administrator privileges
2. **Outdated Registration**: Re-register after CLI updates
3. **Path Issues**: Ensure Python and CLI are in system PATH
4. **Browser Cache**: Restart browser after registration

### Checking Status

Use the status command to diagnose issues:

```bash
rediacc --protocol-status
```

This shows:
- Platform compatibility
- Registration status
- Admin privileges
- Python executable path
- CLI script location
- Current vs. expected registry commands

### Manual Cleanup

If needed, manually remove registry entries:

```cmd
reg delete "HKEY_CLASSES_ROOT\rediacc" /f
```

## Security Considerations

- **Token Exposure**: URLs contain authentication tokens in plaintext
- **Command Injection**: URL parameters are validated before execution
- **Admin Privileges**: Required only for registration, not for URL handling
- **Local Execution**: Protocol URLs only execute local CLI tools

## Browser Compatibility

Tested and supported browsers:
- Microsoft Edge
- Google Chrome
- Mozilla Firefox
- Internet Explorer 11+

## Integration with Console

The frontend console application can generate `rediacc://` URLs using the `protocolUrlService.ts`:

```typescript
import { protocolUrlService } from './services/protocolUrlService';

// Generate sync URL
const syncUrl = protocolUrlService.generateSyncUrl({
  token: 'abc123',
  team: 'Production', 
  machine: 'web-server',
  repository: 'webapp'
}, {
  direction: 'upload',
  localPath: 'C:\\MyProject',
  mirror: true
});

// Open URL (triggers protocol handler)
protocolUrlService.openUrl(syncUrl);
```

## Future Enhancements

Planned improvements:
- **Cross-platform support**: macOS and Linux protocol registration
- **Enhanced security**: Token encryption in URLs
- **URL validation**: Server-side URL verification
- **Deep linking**: More granular action parameters
- **Offline mode**: Handle URLs when CLI is not available

## Related Files

- **Core Handler**: `src/cli/core/protocol_handler.py`
- **CLI Integration**: `src/cli/commands/cli_main.py`
- **Setup Hooks**: `src/cli/setup_hooks.py`
- **Cross-Platform Wrappers**: `rediacc.py`, `rediacc.sh`, `rediacc.bat`
- **Tests**: `tests/test_protocol_handler.py`
- **Examples**: `examples/protocol_examples.py`
- **Frontend Service**: `console/src/services/protocolUrlService.ts`