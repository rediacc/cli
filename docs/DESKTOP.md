# Rediacc Desktop Application - Terminal and File Sync Tools

The Rediacc Desktop application provides a simple graphical interface for the most commonly used CLI tools:
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
- tkinter (Desktop application toolkit)
  - **Ubuntu/Debian**: `sudo apt-get install python3-tk`
  - **Fedora/RHEL**: `sudo dnf install python3-tkinter`
  - **macOS**: Included with Python
  - **Windows**: Included with Python

## Launching the Desktop Application

### Native Launch (Default)
```bash
# Linux/macOS
./rediacc desktop
./rediacc --desktop
./rediacc --desktop native

# Windows
rediacc.bat desktop
rediacc.bat --desktop

# Direct Python
python3 src/cli/gui/main.py
python3 src/cli/gui/main.py
```

### Docker Launch (with X11 support)
```bash
# Run desktop app in Docker (auto-builds if needed)
./rediacc desktop docker
./rediacc --desktop docker

# Force rebuild of Docker image
./rediacc desktop docker-build
./rediacc --desktop docker-build

# Note: The Docker image will be automatically built or rebuilt when:
# - Running for the first time
# - Source files have been updated
# - Dockerfile has changed

# X11 Requirements:
# - Linux: Works out of the box
# - macOS: Install XQuartz from https://www.xquartz.org/
# - Windows: Use X server like VcXsrv or WSLg
```

### All Desktop Application Options
- `--desktop` or `--desktop native` - Run desktop app natively (default)
- `--desktop docker` - Run desktop app in Docker container
- `--desktop docker-build` - Build Docker image for desktop app

## Usage

### Login
1. Launch the desktop application
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