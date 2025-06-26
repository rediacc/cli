# Rediacc CLI PowerShell Wrapper
# This script provides Windows integration for Rediacc CLI tools

[CmdletBinding()]
param(
    [Parameter(Position=0)]
    [ValidateSet('setup', 'login', 'sync', 'term', 'test', 'help')]
    [string]$Command = 'help',
    
    [Parameter(Position=1, ValueFromRemainingArguments=$true)]
    [string[]]$Arguments = @(),
    
    [switch]$AutoInstall,
    [switch]$SkipMSYS2Check
)

$ErrorActionPreference = "Stop"

# Script configuration
$script:MSYS2_PATHS = @(
    "C:\msys64",
    "C:\msys2",
    "$env:USERPROFILE\msys64",
    "$env:USERPROFILE\msys2"
)

if ($env:MSYS2_ROOT) {
    $script:MSYS2_PATHS = @($env:MSYS2_ROOT) + $script:MSYS2_PATHS
}

# Helper functions
function Write-ColorOutput {
    param(
        [string]$Message,
        [ConsoleColor]$Color = 'White'
    )
    Write-Host $Message -ForegroundColor $Color
}

function Find-MSYS2 {
    foreach ($path in $script:MSYS2_PATHS) {
        if (Test-Path $path) {
            return $path
        }
    }
    return $null
}

function Test-MSYS2Components {
    param([string]$MSYS2Path)
    
    $components = @{
        rsync = Test-Path "$MSYS2Path\usr\bin\rsync.exe"
        ssh = Test-Path "$MSYS2Path\usr\bin\ssh.exe"
    }
    return $components
}

function Install-MSYS2Packages {
    param([string]$MSYS2Path)
    
    Write-ColorOutput "`nInstalling required MSYS2 packages..." -Color Cyan
    
    $installScript = @'
#!/bin/bash
echo "Updating package database..."
pacman -Syu --noconfirm
echo
echo "Installing rsync and openssh..."
pacman -S --noconfirm rsync openssh
echo
echo "Installation complete!"
'@
    
    $tempScript = [System.IO.Path]::GetTempFileName()
    $installScript | Out-File -FilePath $tempScript -Encoding ASCII -NoNewline
    
    $msys2Exe = Join-Path $MSYS2Path "msys2.exe"
    $bashPath = ($tempScript -replace '\\','/') -replace '^([A-Z]):','/$1' -replace ':',''
    
    Start-Process -FilePath $msys2Exe -ArgumentList "-c", "bash $bashPath" -Wait
    Remove-Item $tempScript -ErrorAction SilentlyContinue
}

function Setup-Environment {
    param([switch]$Force)
    
    Write-ColorOutput "=== Rediacc CLI Windows Setup ===" -Color Cyan
    Write-ColorOutput ""
    
    # Check Python
    $pythonCmd = Get-Command python -ErrorAction SilentlyContinue
    if (-not $pythonCmd) {
        $pythonCmd = Get-Command py -ErrorAction SilentlyContinue
    }
    
    if ($pythonCmd) {
        $pythonVersion = & $pythonCmd.Source --version 2>&1
        Write-ColorOutput "[OK] Python found: $pythonVersion" -Color Green
    } else {
        Write-ColorOutput "[ERROR] Python not found. Please install Python 3.x from https://www.python.org/" -Color Red
        return $false
    }
    
    # Check MSYS2
    $msys2Path = Find-MSYS2
    if (-not $msys2Path) {
        Write-ColorOutput "[ERROR] MSYS2 not found" -Color Red
        Write-ColorOutput "`nMSYS2 is required for rsync functionality." -Color Yellow
        Write-ColorOutput "Please install from: https://www.msys2.org/" -Color Yellow
        Write-ColorOutput "`nAfter installation, run this command again." -Color Yellow
        
        if ($Force -or $AutoInstall) {
            $answer = 'y'
        } else {
            $answer = Read-Host "`nWould you like to open the MSYS2 download page? (y/n)"
        }
        
        if ($answer -eq 'y') {
            Start-Process "https://www.msys2.org/"
        }
        return $false
    }
    
    Write-ColorOutput "[OK] MSYS2 found: $msys2Path" -Color Green
    
    # Check components
    $components = Test-MSYS2Components -MSYS2Path $msys2Path
    $allInstalled = $components.rsync -and $components.ssh
    
    if (-not $components.rsync) {
        Write-ColorOutput "[MISSING] rsync not installed" -Color Yellow
    } else {
        Write-ColorOutput "[OK] rsync installed" -Color Green
    }
    
    if (-not $components.ssh) {
        Write-ColorOutput "[MISSING] SSH client not installed" -Color Yellow
    } else {
        Write-ColorOutput "[OK] SSH client installed" -Color Green
    }
    
    if (-not $allInstalled) {
        if ($Force -or $AutoInstall) {
            Install-MSYS2Packages -MSYS2Path $msys2Path
        } else {
            Write-ColorOutput "`nRequired packages are missing." -Color Yellow
            $answer = Read-Host "Would you like to install them now? (y/n)"
            if ($answer -eq 'y') {
                Install-MSYS2Packages -MSYS2Path $msys2Path
            } else {
                Write-ColorOutput "`nTo install manually, open MSYS2 and run:" -Color Yellow
                Write-ColorOutput "  pacman -Syu" -Color White
                Write-ColorOutput "  pacman -S rsync openssh" -Color White
                return $false
            }
        }
    }
    
    # Set environment variable
    if (-not $env:MSYS2_ROOT -or $env:MSYS2_ROOT -ne $msys2Path) {
        Write-ColorOutput "`nSetting MSYS2_ROOT environment variable..." -Color Cyan
        [Environment]::SetEnvironmentVariable("MSYS2_ROOT", $msys2Path, [EnvironmentVariableTarget]::User)
        $env:MSYS2_ROOT = $msys2Path
        Write-ColorOutput "[OK] MSYS2_ROOT set to: $msys2Path" -Color Green
    }
    
    Write-ColorOutput "`n=== Setup Complete ===" -Color Green
    return $true
}

function Get-SavedToken {
    $configPath = Join-Path $env:USERPROFILE ".rediacc\config.json"
    if (Test-Path $configPath) {
        try {
            $config = Get-Content $configPath | ConvertFrom-Json
            return $config.token
        } catch {
            return $null
        }
    }
    return $null
}

function Invoke-RediaccCLI {
    param(
        [string]$Tool,
        [string[]]$Arguments
    )
    
    # Find Python
    $pythonCmd = Get-Command python -ErrorAction SilentlyContinue
    if (-not $pythonCmd) {
        $pythonCmd = Get-Command py -ErrorAction SilentlyContinue
    }
    
    if (-not $pythonCmd) {
        Write-ColorOutput "ERROR: Python not found. Please install Python 3.x" -Color Red
        exit 1
    }
    
    # Check MSYS2 for sync operations
    if ($Tool -eq "rediacc-cli-sync" -and -not $SkipMSYS2Check) {
        $msys2Path = Find-MSYS2
        if (-not $msys2Path) {
            Write-ColorOutput "ERROR: MSYS2 not found. Run: .\rediacc-cli.ps1 setup" -Color Red
            exit 1
        }
        
        $components = Test-MSYS2Components -MSYS2Path $msys2Path
        if (-not $components.rsync -or -not $components.ssh) {
            Write-ColorOutput "ERROR: Required MSYS2 packages missing. Run: .\rediacc-cli.ps1 setup" -Color Red
            exit 1
        }
    }
    
    # Auto-inject token if not provided and tool needs it
    $needsToken = $Tool -in @("rediacc-cli-sync", "rediacc-cli-term")
    if ($needsToken -and -not ($Arguments -contains "--token")) {
        $token = Get-SavedToken
        if ($token) {
            $Arguments = @("--token", $token) + $Arguments
        } else {
            Write-ColorOutput "ERROR: No token provided and no saved token found" -Color Red
            Write-ColorOutput "Please login first: .\rediacc.ps1 login" -Color Yellow
            exit 1
        }
    }
    
    # Build script path
    $scriptPath = Join-Path $PSScriptRoot $Tool
    
    # Execute
    & $pythonCmd.Source $scriptPath $Arguments
}

function Show-Help {
    Write-ColorOutput @"
Rediacc CLI for Windows

USAGE:
    .\rediacc-cli.ps1 <command> [arguments]

COMMANDS:
    setup       Set up Windows environment for Rediacc CLI
    login       Authenticate with Rediacc API
    sync        File synchronization operations
    term        Terminal access to repositories
    test        Test Windows compatibility
    help        Show this help message

SETUP:
    .\rediacc-cli.ps1 setup
    .\rediacc-cli.ps1 setup -AutoInstall

AUTHENTICATION:
    .\rediacc-cli.ps1 login --email user@example.com --password yourpass
    .\rediacc-cli.ps1 login  # Interactive login

SYNC OPERATIONS:
    .\rediacc-cli.ps1 sync upload --token GUID --local C:\data --machine server --repo myrepo
    .\rediacc-cli.ps1 sync download --token GUID --machine server --repo myrepo --local C:\backup
    .\rediacc-cli.ps1 sync upload --help

TERMINAL ACCESS:
    .\rediacc-cli.ps1 term --token GUID --machine server --repo myrepo

TEST INSTALLATION:
    .\rediacc-cli.ps1 test

EXAMPLES:
    # First time setup
    .\rediacc-cli.ps1 setup -AutoInstall
    
    # Login
    .\rediacc-cli.ps1 login
    
    # Upload files
    .\rediacc-cli.ps1 sync upload --token YOUR_TOKEN --local "C:\MyProject" --machine myserver --repo myrepo
    
    # Download with confirmation
    .\rediacc-cli.ps1 sync download --token YOUR_TOKEN --machine myserver --repo myrepo --local "C:\Backup" --confirm

OPTIONS:
    -AutoInstall        Automatically install missing components without prompting
    -SkipMSYS2Check     Skip MSYS2 validation (for non-sync operations)

For more information, see README.md and WINDOWS_TROUBLESHOOTING.md
"@ -Color Cyan
}

# Main execution
switch ($Command) {
    'setup' {
        Setup-Environment -Force:$AutoInstall
    }
    
    'login' {
        Invoke-RediaccCLI -Tool "rediacc-cli" -Arguments (@('login') + $Arguments)
    }
    
    'sync' {
        Invoke-RediaccCLI -Tool "rediacc-cli-sync" -Arguments $Arguments
    }
    
    'term' {
        Invoke-RediaccCLI -Tool "rediacc-cli-term" -Arguments $Arguments
    }
    
    'test' {
        $testScript = Join-Path $PSScriptRoot "test_windows_compat.py"
        $pythonCmd = Get-Command python -ErrorAction SilentlyContinue
        if (-not $pythonCmd) {
            $pythonCmd = Get-Command py -ErrorAction SilentlyContinue
        }
        
        if ($pythonCmd) {
            & $pythonCmd.Source $testScript
        } else {
            Write-ColorOutput "ERROR: Python not found" -Color Red
        }
    }
    
    'help' {
        Show-Help
    }
    
    default {
        Show-Help
    }
}