# Rediacc CLI GUI - Terminal and File Sync Tools

The Rediacc CLI GUI provides a simple graphical interface for the most commonly used CLI tools:
- **Terminal Access** - SSH into machines and repositories
- **File Sync** - Upload and download files using rsync

## Features

### Terminal Access
- Connect to any machine in your teams
- Access specific repository environments
- Execute commands remotely
- Open interactive terminal sessions

### File Sync
- Upload local files to remote repositories
- Download repository files to local machine
- Mirror mode for exact replication
- Verification after transfer
- Progress tracking

## Requirements

- Python 3.6+
- tkinter (GUI toolkit)
  - **Ubuntu/Debian**: `sudo apt-get install python3-tk`
  - **Fedora/RHEL**: `sudo dnf install python3-tkinter`
  - **macOS**: Included with Python
  - **Windows**: Included with Python

## Launching the GUI

### Native Launch (Default)
```bash
# Linux/macOS
./rediacc gui
./rediacc --gui
./rediacc --gui native

# Windows
.\rediacc.ps1 gui
.\rediacc.ps1 --gui

# Direct Python
python3 src/cli/rediacc-cli --gui
python3 src/cli/rediacc-cli --gui native
```

### Docker Launch (with X11 support)
```bash
# Run GUI in Docker (auto-builds if needed)
./rediacc gui docker
./rediacc --gui docker

# Force rebuild of Docker image
./rediacc gui docker-build
./rediacc --gui docker-build

# Note: The Docker image will be automatically built or rebuilt when:
# - Running for the first time
# - Source files have been updated
# - Dockerfile has changed

# X11 Requirements:
# - Linux: Works out of the box
# - macOS: Install XQuartz from https://www.xquartz.org/
# - Windows: Use X server like VcXsrv or WSLg
```

### All GUI Options
- `--gui` or `--gui native` - Run GUI natively (default)
- `--gui docker` - Run GUI in Docker container
- `--gui docker-build` - Build Docker image for GUI

## Usage

### Login
1. Launch the GUI
2. Enter your email and password
3. Click "Login" or press Enter

### Terminal Access
1. Select your team from the dropdown
2. Select the target machine
3. (Optional) Select a repository for container access
4. Either:
   - Enter a command and click "Execute Command" for one-off commands
   - Click "Open Interactive Terminal" for a full terminal session

### File Sync
1. Choose sync direction (Upload or Download)
2. Select team, machine, and repository
3. Browse or enter the local directory path
4. Configure options:
   - **Mirror**: Delete files at destination that don't exist at source
   - **Verify**: Check file integrity after transfer
5. Click "Start Sync"

## Keyboard Shortcuts

- **Enter**: Submit login form
- **Escape**: Close the application
- **Ctrl+C**: Force quit from terminal

## Security

- Credentials are never stored in the GUI
- Uses the same secure token management as the CLI
- All communications are encrypted
- SSH keys are handled securely

## Troubleshooting

### GUI Won't Start
- Ensure tkinter is installed
- Check Python version (3.6+ required)
- Try running with `python3 -m tkinter` to test tkinter

### Terminal Connection Failed
- Verify machine is online
- Check team permissions
- Ensure SSH key is configured in team vault

### File Sync Issues
- Verify local path exists and is accessible
- Check repository exists on target machine
- Ensure sufficient disk space

## Limitations

- The GUI is designed for common tasks only
- For advanced operations, use the CLI directly
- Interactive terminal may not work on all platforms