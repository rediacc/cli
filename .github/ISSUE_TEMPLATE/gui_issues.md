---
name: GUI Issue
about: Report problems with the Rediacc CLI graphical user interface
title: '[GUI] '
labels: 'gui, needs-triage'
assignees: ''
---

## GUI Issue Description
<!-- Describe the GUI problem you're experiencing -->

## Issue Type
<!-- Check all that apply -->
- [ ] GUI won't launch
- [ ] Display/rendering issues  
- [ ] Interactive elements not working
- [ ] Window management problems
- [ ] Docker GUI issues
- [ ] X11 forwarding problems
- [ ] Font/text display issues
- [ ] Theme/appearance issues
- [ ] Performance problems
- [ ] Other: <!-- Specify -->

## Environment

### System Information
- **OS**: <!-- e.g., Ubuntu 22.04, macOS 14.0, Windows 11 with WSL2 -->
- **Desktop Environment**: <!-- GNOME, KDE, XFCE, macOS, Windows -->
- **Display Server**: <!-- X11, Wayland, XQuartz (macOS), VcXsrv (Windows) -->
- **Python Version**: <!-- Run: python3 --version -->
- **Rediacc CLI Version**: <!-- Run: ./rediacc --version -->

### GUI Launch Method
- [ ] Native Python tkinter (`./rediacc gui`)
- [ ] Docker container (`./rediacc gui --docker`)
- [ ] Direct Python script (`python3 src/cli/gui/main.py`)
- [ ] Other: <!-- Specify -->

## Pre-Launch Checks

### tkinter Availability
```bash
# Check if tkinter is installed
python3 -c "import tkinter; print('tkinter version:', tkinter.TkVersion)"

# If error, install tkinter:
# Ubuntu/Debian: sudo apt-get install python3-tk
# Fedora: sudo dnf install python3-tkinter
# macOS: Usually included with Python
```

### Display Configuration
```bash
# Check display variable
echo $DISPLAY

# Check X11 availability (Linux)
xdpyinfo | head -5

# List running display managers
ps aux | grep -E "(Xorg|wayland|Xquartz)"
```

## GUI Launch Attempt

### Command Used
```bash
# Exact command to launch GUI
./rediacc gui [options]
```

### Launch Output
```
# Paste complete output when trying to launch GUI
```

### Error Messages
```python
# Paste any Python exceptions or error messages
```

## Docker GUI Issues
<!-- If using Docker for GUI -->

### Docker Configuration
```bash
# Docker version
docker --version

# Check X11 socket mounting
docker run --rm -it \
  -e DISPLAY=$DISPLAY \
  -v /tmp/.X11-unix:/tmp/.X11-unix \
  rediacc-gui echo $DISPLAY
```

### X11 Forwarding Setup
- **xhost Configured**: <!-- Yes/No -->
- **Socket Mounted**: <!-- Yes/No -->
- **DISPLAY Variable Set**: <!-- Value -->

```bash
# X11 permissions
xhost +local:docker  # or xhost +

# Docker run command used
docker run -it \
  -e DISPLAY=$DISPLAY \
  -v /tmp/.X11-unix:/tmp/.X11-unix \
  -v ~/.rediacc:/root/.rediacc \
  rediacc-gui
```

## Platform-Specific Issues

<details>
<summary>macOS Specific</summary>

### XQuartz Configuration
- **XQuartz Installed**: <!-- Yes/No, version -->
- **XQuartz Running**: <!-- Yes/No -->
- **Allow Network Clients**: <!-- Enabled/Disabled -->

```bash
# Check XQuartz
ls -la /Applications/Utilities/XQuartz.app
defaults read org.xquartz.X11

# Set DISPLAY
export DISPLAY=:0
```

</details>

<details>
<summary>Windows (WSL2) Specific</summary>

### X Server Configuration
- **X Server Software**: <!-- VcXsrv, Xming, X410, etc. -->
- **X Server Running**: <!-- Yes/No -->
- **Firewall Rules**: <!-- Configured/Not configured -->

```bash
# In WSL2
export DISPLAY=$(cat /etc/resolv.conf | grep nameserver | awk '{print $2}'):0
echo $DISPLAY

# Test X11
xclock  # or xeyes
```

</details>

<details>
<summary>Linux Specific</summary>

### Wayland vs X11
- **Session Type**: <!-- X11/Wayland -->
- **XWayland Available**: <!-- Yes/No -->

```bash
# Check session type
echo $XDG_SESSION_TYPE

# For Wayland users
echo $WAYLAND_DISPLAY
```

</details>

## GUI Behavior

### Visual Issues
<!-- If GUI launches but has problems -->
- **Window Size**: <!-- Too small/large, not resizable -->
- **Font Rendering**: <!-- Blurry, too small, missing -->
- **Colors/Theme**: <!-- Wrong colors, theme not applied -->
- **Layout Problems**: <!-- Overlapping, cut off, misaligned -->

### Screenshots
<!-- Attach screenshots if possible -->
<details>
<summary>Click to view screenshots</summary>

<!-- Drag and drop images here -->

</details>

### Interactive Issues
- **Buttons/Clicks**: <!-- Not responding, wrong action -->
- **Text Input**: <!-- Can't type, wrong characters -->
- **Scrolling**: <!-- Not working, jumpy -->
- **Keyboard Shortcuts**: <!-- Not working -->

## Performance

### Resource Usage
```bash
# While GUI is running
top -p $(pgrep -f "rediacc.*gui")

# Memory usage
ps aux | grep -E "rediacc.*gui"
```

### Responsiveness
- **Launch Time**: <!-- Seconds to appear -->
- **Input Lag**: <!-- Immediate/Delayed -->
- **Rendering Speed**: <!-- Smooth/Choppy -->

## Attempted Solutions
<!-- What have you tried? -->

- [ ] Installed/reinstalled tkinter
- [ ] Set DISPLAY variable correctly
- [ ] Configured X11 forwarding
- [ ] Tried Docker GUI option
- [ ] Updated graphics drivers
- [ ] Disabled compositor/effects
- [ ] Changed display server (X11/Wayland)
- [ ] Ran with different Python version
- [ ] Other: <!-- Specify -->

## Workarounds
<!-- Any temporary solutions that work? -->

## Logs and Debugging

### GUI Debug Output
```bash
# Run with debug mode
REDIACC_GUI_DEBUG=1 ./rediacc gui

# Or verbose Python
python3 -v src/cli/gui/main.py
```

### X11 Debug
<details>
<summary>Click to expand X11 debug info</summary>

```bash
# X11 errors
xev  # X event viewer
glxinfo | head  # OpenGL info
```

</details>

### System Logs
<details>
<summary>Click to expand system logs</summary>

```bash
# Check system logs for GUI-related errors
journalctl -xe | grep -E "(tk|gui|X11)"
dmesg | grep -E "(display|gpu)"
```

</details>

## Additional Context

### Recent Changes
- [ ] System updates
- [ ] Display driver updates
- [ ] Python upgrade
- [ ] Desktop environment change
- [ ] Display configuration change
- [ ] Other: <!-- Specify -->

### Alternative Access
<!-- Can you use the CLI without GUI? -->
- **CLI Works**: <!-- Yes/No -->
- **Web Console Available**: <!-- Yes/No -->

### Related Issues
- #<!-- issue number -->

---
<!-- 
Before submitting:
1. Try both native and Docker GUI options
2. Verify tkinter is properly installed
3. Check display configuration thoroughly
4. Test with a simple tkinter script to isolate issues
5. Review GUI documentation in docs/GUI.md
-->