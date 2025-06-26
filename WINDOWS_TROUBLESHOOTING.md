# Windows Troubleshooting Guide for Rediacc CLI

## Common Issues and Solutions

### 1. "rsync not found" Error

**Problem**: You get an error saying rsync is not found when running sync commands.

**Solution**:
1. Ensure MSYS2 is installed (default: `C:\msys64`)
2. Open MSYS2 terminal and run:
   ```bash
   pacman -Syu
   pacman -S rsync openssh
   ```
3. Set the MSYS2_ROOT environment variable:
   ```cmd
   setx MSYS2_ROOT "C:\msys64"
   ```
4. Restart your terminal/command prompt

### 2. SSH Key Issues

**Problem**: SSH authentication fails or key permissions errors.

**Solution**:
- Windows doesn't support Unix-style file permissions, but the CLI handles this automatically
- If you still have issues, ensure your `.ssh` folder has proper Windows permissions:
  ```powershell
  icacls "$env:USERPROFILE\.ssh" /inheritance:r /grant:r "$env:USERNAME:(OI)(CI)F"
  ```

### 3. Path Format Issues

**Problem**: Errors related to paths like "C:\Users\..." or "/mnt/c/..."

**Solution**:
- The CLI automatically converts paths between Windows and Unix formats
- Use Windows paths normally: `C:\Users\myname\files`
- The CLI will convert them for rsync compatibility

### 4. "python" Command Not Found

**Problem**: Windows says python is not recognized as a command.

**Solution**:
1. Install Python 3.x from https://www.python.org/
2. During installation, check "Add Python to PATH"
3. Or use `py` instead of `python`:
   ```cmd
   py rediacc-cli login
   ```

### 5. PowerShell Execution Policy

**Problem**: PowerShell script cannot run due to execution policy.

**Solution**:
Option 1: Run with bypass flag:
```powershell
powershell -ExecutionPolicy Bypass -File .\rediacc.ps1 setup
```

Option 2: Change execution policy (permanent):
```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

### 6. MSYS2 Terminal Closes During Update

**Problem**: MSYS2 terminal closes when running `pacman -Syu`

**Solution**:
This is normal behavior. The terminal closes after core updates.
1. Reopen MSYS2 terminal
2. Run: `pacman -Su`
3. Then install packages: `pacman -S rsync openssh`

### 7. Antivirus Blocking MSYS2

**Problem**: Antivirus software blocks MSYS2 installation or execution.

**Solution**:
1. Temporarily disable antivirus during installation
2. Add MSYS2 directory to antivirus exclusions:
   - Default path: `C:\msys64`
   - Add to Windows Defender exclusions:
     ```powershell
     Add-MpPreference -ExclusionPath "C:\msys64"
     ```

### 8. Network Proxy Issues

**Problem**: Cannot download packages through corporate proxy.

**Solution**:
In MSYS2 terminal, set proxy:
```bash
export http_proxy=http://proxy.company.com:8080
export https_proxy=http://proxy.company.com:8080
pacman -Syu
```

## Testing Your Installation

Run the test command to verify everything is working:
```powershell
.\rediacc.ps1 test
```

Expected output should show:
- Platform: windows
- MSYS2 rsync: Found
- MSYS2 ssh: Found
- System is ready for Rediacc CLI on Windows!

## Getting Help

If you continue to experience issues:
1. Run `.\rediacc.ps1 test` to check your setup
2. Run `.\rediacc.ps1 setup` to fix missing components
3. Check the PowerShell error messages
4. Ensure Python and MSYS2 are properly installed

## Quick Command Reference

### PowerShell Wrapper (Recommended)
```powershell
# Setup and testing
.\rediacc.ps1 setup
.\rediacc.ps1 test
.\rediacc.ps1 help

# Authentication
.\rediacc.ps1 login --email user@example.com
.\rediacc.ps1 login  # Interactive

# File sync
.\rediacc.ps1 sync upload --token GUID --local C:\data --machine server --repo myrepo
.\rediacc.ps1 sync download --token GUID --machine server --repo myrepo --local C:\backup
.\rediacc.ps1 sync upload --help

# Terminal access
.\rediacc.ps1 term --token GUID --machine server --repo myrepo
```

### Python Direct (Alternative)
```cmd
python rediacc-cli login --email user@example.com
python rediacc-cli-sync upload --token GUID --local C:\data --machine server --repo myrepo
python rediacc-cli-sync download --token GUID --machine server --repo myrepo --local C:\backup
```

### Common Path Examples
- Windows path: `C:\Users\John\Documents\data`
- Network path: `\\server\share\folder`
- Relative path: `.\mydata` or `mydata`
- All will be automatically converted for rsync compatibility