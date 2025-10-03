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

The protocol is automatically registered during installation on **all supported platforms**:

**Via PyPI:**
```bash
pip install rediacc
```

**Via Installation Script:**
```bash
# Linux/macOS
./scripts/install.sh --auto

# Windows
# Run as Administrator
pip install rediacc
```

The installer automatically detects your platform and registers the protocol handler if:
1. Not in a virtual environment
2. Required dependencies are available (see prerequisites below)
3. On Windows: Running with administrator privileges

### Manual Registration

If automatic registration didn't work, you can register manually:

#### Command Structure (All Platforms)
```bash
# Register protocol for current user (recommended)
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
- **Python**: Python 3.8+ executable must be accessible
- **Rediacc CLI**: Properly installed and configured

**Platform-Specific:**

#### Windows
- **Administrator privileges**: Required for system-wide registration (registry modifications)
- **User-level registration**: Works without admin privileges
- **Tools**: `reg.exe` (included with Windows)

#### Linux
- **xdg-utils package**: Required for protocol registration
  ```bash
  # Ubuntu/Debian
  sudo apt install xdg-utils

  # Fedora/RHEL
  sudo dnf install xdg-utils

  # Arch Linux
  sudo pacman -S xdg-utils
  ```
- **Desktop Environment**: Works with GNOME, KDE, XFCE, and most XDG-compliant DEs
- **System-wide registration**: Requires `sudo` for system application directory access

#### macOS
- **Optional: duti**: Enhanced protocol support (recommended but not required)
  ```bash
  brew install duti
  ```
- **LaunchServices**: Built-in macOS service (fallback if duti not available)
- **System-wide registration**: Requires `sudo` for LaunchAgent installation

## Platform Implementation Details

### Windows Registry

The protocol registration creates these Windows registry entries:

**User-Level Registration:**
```
HKEY_CURRENT_USER\Software\Classes\rediacc
├── (Default) = "URL:Rediacc Desktop"
├── URL Protocol = ""
├── FriendlyTypeName = "Rediacc Desktop"
└── shell\open\command
    └── (Default) = "python \"path\to\rediacc.py\" protocol-handler \"%1\""
```

**System-Wide Registration:**
```
HKEY_CLASSES_ROOT\rediacc
├── (Default) = "URL:Rediacc Desktop"
├── URL Protocol = ""
├── FriendlyTypeName = "Rediacc Desktop"
└── shell\open\command
    └── (Default) = "python \"path\to\rediacc.py\" protocol-handler \"%1\""
```

### Linux XDG Desktop File

The protocol registration creates a desktop entry at:
- **User-Level**: `~/.local/share/applications/rediacc-protocol.desktop`
- **System-Wide**: `/usr/share/applications/rediacc-protocol.desktop`

**Desktop File Content:**
```desktop
[Desktop Entry]
Name=Rediacc Protocol Handler
Comment=Handle rediacc:// protocol URLs
Exec=python "/path/to/cli_main.py" protocol-handler %u
Icon=application-x-executable
StartupNotify=true
NoDisplay=true
MimeType=x-scheme-handler/rediacc;
Type=Application
Categories=Network;
```

The MIME type `x-scheme-handler/rediacc` is registered via `xdg-mime`:
```bash
xdg-mime default rediacc-protocol.desktop x-scheme-handler/rediacc
```

### macOS LaunchServices

The protocol registration uses one of two methods:

**Method 1: Using duti (Recommended)**
```bash
duti -s com.rediacc.cli rediacc all
```

**Method 2: LaunchServices with LaunchAgent**

Creates a LaunchAgent plist at:
- **User-Level**: `~/Library/LaunchAgents/com.rediacc.cli.plist`
- **System-Wide**: `/Library/LaunchAgents/com.rediacc.cli.plist`

**LaunchAgent Plist:**
```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.rediacc.cli</string>
    <key>CFBundleIdentifier</key>
    <string>com.rediacc.cli</string>
    <key>CFBundleURLTypes</key>
    <array>
        <dict>
            <key>CFBundleURLName</key>
            <string>Rediacc Protocol</string>
            <key>CFBundleURLSchemes</key>
            <array>
                <string>rediacc</string>
            </array>
        </dict>
    </array>
    <key>LSUIElement</key>
    <true/>
    <key>RunAtLoad</key>
    <false/>
</dict>
</plist>
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

### Common Issues (All Platforms)

1. **Not Registered**: Check registration status with `./rediacc protocol status`
2. **Outdated Registration**: Re-register after CLI updates: `./rediacc protocol register --force`
3. **Path Issues**: Ensure Python and CLI are in system PATH
4. **Browser Cache**: Restart browser after registration
5. **Virtual Environment**: Protocol registration is skipped in venvs - install system-wide or register manually

### Checking Status

Use the status command to diagnose issues:

```bash
./rediacc protocol status
```

**Output includes:**
- Platform compatibility
- Registration status (user-level and system-wide)
- Required dependencies availability
- Python executable path
- CLI script location
- Current vs. expected handler configuration

### Platform-Specific Troubleshooting

#### Windows

**Issue: "Administrator privileges required"**
```cmd
REM Run PowerShell as Administrator
REM Then register protocol
rediacc protocol register --system-wide
```

**Issue: Registry key not working**
```cmd
REM Check current registration
rediacc protocol status

REM Manually clean up (as Administrator)
reg delete "HKEY_CLASSES_ROOT\rediacc" /f
reg delete "HKEY_CURRENT_USER\Software\Classes\rediacc" /f

REM Re-register
rediacc protocol register
```

#### Linux

**Issue: "xdg-utils package required"**
```bash
# Ubuntu/Debian
sudo apt install xdg-utils

# Fedora/RHEL
sudo dnf install xdg-utils

# Arch Linux
sudo pacman -S xdg-utils

# Then register
./rediacc protocol register
```

**Issue: Protocol not working in browser**
```bash
# Check default handler
xdg-mime query default x-scheme-handler/rediacc

# Should output: rediacc-protocol.desktop
# If not, re-register:
./rediacc protocol register --force

# Update desktop database
update-desktop-database ~/.local/share/applications/
```

**Issue: Permission denied**
```bash
# For user-level registration (recommended):
./rediacc protocol register

# For system-wide (requires sudo):
sudo ./rediacc protocol register --system-wide
```

#### macOS

**Issue: "duti not found"**
```bash
# Install duti (optional but recommended)
brew install duti

# Or proceed without it - CLI will use LaunchServices fallback
./rediacc protocol register
```

**Issue: Protocol not responding**
```bash
# Check current handler
duti -x rediacc

# Re-register with force
./rediacc protocol register --force

# Rebuild Launch Services database
/System/Library/Frameworks/CoreServices.framework/Frameworks/LaunchServices.framework/Support/lsregister -kill -r -domain local -domain system -domain user
```

**Issue: LaunchAgent not loading**
```bash
# Check if plist exists
ls -la ~/Library/LaunchAgents/com.rediacc.cli.plist

# Manually load LaunchAgent
launchctl load ~/Library/LaunchAgents/com.rediacc.cli.plist

# Check status
launchctl list | grep rediacc
```

### Manual Cleanup

#### Windows
```cmd
REM As Administrator
reg delete "HKEY_CLASSES_ROOT\rediacc" /f
reg delete "HKEY_CURRENT_USER\Software\Classes\rediacc" /f
```

#### Linux
```bash
# Remove desktop file
rm ~/.local/share/applications/rediacc-protocol.desktop

# Unregister MIME type
xdg-mime default '' x-scheme-handler/rediacc

# Update database
update-desktop-database ~/.local/share/applications/
```

#### macOS
```bash
# Unload LaunchAgent
launchctl unload ~/Library/LaunchAgents/com.rediacc.cli.plist

# Remove plist
rm ~/Library/LaunchAgents/com.rediacc.cli.plist

# Rebuild Launch Services
/System/Library/Frameworks/CoreServices.framework/Frameworks/LaunchServices.framework/Support/lsregister -kill -r -domain local -domain system -domain user
```

## Security Considerations

- **Token Exposure**: URLs contain authentication tokens in plaintext
- **Command Injection**: URL parameters are validated before execution
- **Admin Privileges**: Required only for registration, not for URL handling
- **Local Execution**: Protocol URLs only execute local CLI tools

## Browser Compatibility

### Windows
- ✅ Microsoft Edge
- ✅ Google Chrome
- ✅ Mozilla Firefox
- ✅ Internet Explorer 11+
- ✅ Brave
- ✅ Opera

### Linux
- ✅ Google Chrome / Chromium
- ✅ Mozilla Firefox
- ✅ Brave
- ✅ Opera
- ⚠️ Safari (not available on Linux)
- Requires xdg-utils for proper protocol handling

### macOS
- ✅ Safari
- ✅ Google Chrome
- ✅ Mozilla Firefox
- ✅ Brave
- ✅ Opera
- ✅ Microsoft Edge

**Note**: After registration, restart your browser for the protocol handler to take effect.

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
- **Enhanced security**: Token encryption in URLs
- **URL validation**: Server-side URL verification
- **Deep linking**: More granular action parameters
- **Offline mode**: Handle URLs when CLI is not available
- **Auto-update**: Automatic protocol re-registration after CLI updates
- **Custom actions**: Support for user-defined protocol actions

## Related Files

**Core Protocol System:**
- **Cross-Platform Handler**: `src/cli/core/protocol_handler.py`
- **Windows Handler**: `src/cli/core/protocol_handler.py` (WindowsProtocolHandler class)
- **Linux Handler**: `src/cli/core/linux_protocol_handler.py`
- **macOS Handler**: `src/cli/core/macos_protocol_handler.py`

**Integration:**
- **CLI Integration**: `src/cli/commands/cli_main.py`
- **Setup Hooks**: `src/cli/setup_hooks.py`
- **Installation Script**: `scripts/install.sh`

**Platform Wrappers:**
- **Python**: `rediacc.py`
- **Bash (Linux/macOS)**: `rediacc`
- **Windows Batch**: `rediacc.bat`

**Testing & Examples:**
- **Tests**: `tests/test_protocol_handler.py`
- **Examples**: `examples/protocol_examples.py`

**Frontend:**
- **Protocol URL Service**: `console/src/services/protocolUrlService.ts`

**Documentation:**
- **This Document**: `docs/PROTOCOL_REGISTRATION.md`
- **Installation Guide**: `docs/INSTALLATION.md`
- **Main README**: `README.md`