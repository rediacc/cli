# Rediacc CLI PowerShell Wrapper
# This script provides Windows integration for Rediacc CLI tools

[CmdletBinding()]
param(
    [Parameter(Position=0)]
    [ValidateSet('setup', 'login', 'sync', 'term', 'test', 'gui', 'help')]
    [string]$Command = 'help',
    
    [Parameter(Position=1, ValueFromRemainingArguments=$true)]
    [string[]]$Arguments = @(),
    
    [switch]$AutoInstall,
    [switch]$SkipMSYS2Check,
    [switch]$ForceReinstall,
    [switch]$SkipPython,
    [switch]$SkipMSYS2,
    [string]$InstallDir,
    [switch]$NoProgress
)

$ErrorActionPreference = "Stop"

# Helper functions
function Write-ColorOutput {
    param(
        [string]$Message,
        [ConsoleColor]$Color = 'White'
    )
    Write-Host $Message -ForegroundColor $Color
}

function Write-Progress-Custom {
    param(
        [string]$Activity,
        [string]$Status,
        [int]$PercentComplete = -1
    )
    if (-not $NoProgress) {
        if ($PercentComplete -ge 0) {
            Write-Progress -Activity $Activity -Status $Status -PercentComplete $PercentComplete
        } else {
            Write-Progress -Activity $Activity -Status $Status
        }
    }
}

function Get-SystemArchitecture {
    $arch = $env:PROCESSOR_ARCHITECTURE
    switch ($arch) {
        "AMD64" { return "x64" }
        "ARM64" { return "arm64" }
        "x86" { return "x86" }
        default { return "x64" }
    }
}

function Find-Python {
    # Try different Python commands in order of preference
    $pythonCommands = @("python", "py", "python3")
    
    foreach ($cmd in $pythonCommands) {
        try {
            $pythonPath = Get-Command $cmd -ErrorAction SilentlyContinue
            if ($pythonPath) {
                # Test if it actually works
                $version = & $pythonPath.Source --version 2>&1
                if ($version -match "Python \d+\.\d+") {
                    return @{
                        Command = $pythonPath.Source
                        Name = $cmd
                        Version = $version
                    }
                }
            }
        } catch {
            # Continue to next command
        }
    }
    
    return $null
}

function Install-PythonPackages {
    param(
        [string]$PythonCommand
    )
    
    $requirementsFile = Join-Path $PSScriptRoot "requirements.txt"
    
    if (-not (Test-Path $requirementsFile)) {
        Write-ColorOutput "[WARNING] requirements.txt not found, skipping package installation" -Color Yellow
        return $true
    }
    
    Write-ColorOutput "[INFO] Installing Python packages from requirements.txt..." -Color Yellow
    
    try {
        # Upgrade pip first
        Write-ColorOutput "[INFO] Upgrading pip..." -Color Yellow
        $pipResult = Start-Process -FilePath $PythonCommand -ArgumentList "-m", "pip", "install", "--upgrade", "pip" -Wait -PassThru -NoNewWindow -RedirectStandardOutput "pip_stdout.txt" -RedirectStandardError "pip_stderr.txt"
        
        if ($pipResult.ExitCode -ne 0) {
            Write-ColorOutput "[WARNING] pip upgrade failed, but continuing..." -Color Yellow
        }
        
        # Install requirements with verbose output
        Write-ColorOutput "[INFO] Installing packages: cryptography, requests..." -Color Yellow
        $installResult = Start-Process -FilePath $PythonCommand -ArgumentList "-m", "pip", "install", "-r", $requirementsFile, "--verbose" -Wait -PassThru -NoNewWindow -RedirectStandardOutput "install_stdout.txt" -RedirectStandardError "install_stderr.txt"
        
        # Read and display output
        if (Test-Path "install_stdout.txt") {
            $stdout = Get-Content "install_stdout.txt" -Raw
            if ($stdout) {
                Write-ColorOutput "[INFO] Install output:" -Color Cyan
                Write-Host $stdout
            }
        }
        
        if (Test-Path "install_stderr.txt") {
            $stderr = Get-Content "install_stderr.txt" -Raw
            if ($stderr) {
                Write-ColorOutput "[INFO] Install errors/warnings:" -Color Yellow
                Write-Host $stderr
            }
        }
        
        if ($installResult.ExitCode -eq 0) {
            Write-ColorOutput "[OK] Python packages installed successfully" -Color Green
            
            # Test cryptography import
            Write-ColorOutput "[INFO] Testing cryptography library..." -Color Yellow
            $testResult = Start-Process -FilePath $PythonCommand -ArgumentList "-c", "import cryptography; print('cryptography version:', cryptography.__version__)" -Wait -PassThru -NoNewWindow -RedirectStandardOutput "test_stdout.txt" -RedirectStandardError "test_stderr.txt"
            
            if ($testResult.ExitCode -eq 0) {
                $testOutput = Get-Content "test_stdout.txt" -Raw
                Write-ColorOutput "[OK] Cryptography test passed: $testOutput" -Color Green
            } else {
                Write-ColorOutput "[WARNING] Cryptography test failed - library may not be properly installed" -Color Yellow
                
                # Try alternative installation methods
                Write-ColorOutput "[INFO] Attempting alternative installation..." -Color Yellow
                
                # Try installing with --only-binary to avoid compilation issues
                $altResult = Start-Process -FilePath $PythonCommand -ArgumentList "-m", "pip", "install", "cryptography", "--only-binary=all", "--upgrade" -Wait -PassThru -NoNewWindow -RedirectStandardOutput "alt_stdout.txt" -RedirectStandardError "alt_stderr.txt"
                
                if ($altResult.ExitCode -eq 0) {
                    Write-ColorOutput "[OK] Alternative cryptography installation succeeded" -Color Green
                } else {
                    Write-ColorOutput "[WARNING] Alternative installation also failed" -Color Yellow
                    if (Test-Path "alt_stderr.txt") {
                        $altStderr = Get-Content "alt_stderr.txt" -Raw
                        Write-ColorOutput "[ERROR] Alternative install error: $altStderr" -Color Red
                    }
                }
            }
        } else {
            Write-ColorOutput "[WARNING] Package installation failed (exit code: $($installResult.ExitCode))" -Color Yellow
        }
        
        # Cleanup temp files
        @("pip_stdout.txt", "pip_stderr.txt", "install_stdout.txt", "install_stderr.txt", "test_stdout.txt", "test_stderr.txt", "alt_stdout.txt", "alt_stderr.txt") | ForEach-Object {
            if (Test-Path $_) {
                Remove-Item $_ -ErrorAction SilentlyContinue
            }
        }
        
        return $true  # Don't fail setup for this, but provide detailed feedback
    } catch {
        Write-ColorOutput "[WARNING] Failed to install Python packages: $($_.Exception.Message)" -Color Yellow
        return $true  # Don't fail setup for this
    }
}

function Test-WindowsVersion {
    $version = [System.Environment]::OSVersion.Version
    $isWindows10OrLater = ($version.Major -eq 10 -and $version.Build -ge 10240) -or ($version.Major -gt 10)
    return $isWindows10OrLater
}

function Test-PackageManager {
    $packageManagers = @()
    
    # Test for Winget
    try {
        $winget = Get-Command winget -ErrorAction SilentlyContinue
        if ($winget) {
            $packageManagers += @{Name = "winget"; Command = "winget"; Available = $true}
        }
    } catch {
        $packageManagers += @{Name = "winget"; Command = "winget"; Available = $false}
    }
    
    # Test for Chocolatey
    try {
        $choco = Get-Command choco -ErrorAction SilentlyContinue
        if ($choco) {
            $packageManagers += @{Name = "chocolatey"; Command = "choco"; Available = $true}
        }
    } catch {
        $packageManagers += @{Name = "chocolatey"; Command = "choco"; Available = $false}
    }
    
    # Test for Scoop
    try {
        $scoop = Get-Command scoop -ErrorAction SilentlyContinue
        if ($scoop) {
            $packageManagers += @{Name = "scoop"; Command = "scoop"; Available = $true}
        }
    } catch {
        $packageManagers += @{Name = "scoop"; Command = "scoop"; Available = $false}
    }
    
    return $packageManagers
}

function Download-File {
    param(
        [string]$Url,
        [string]$OutputPath,
        [string]$Description = "Downloading file"
    )
    
    try {
        Write-ColorOutput "$Description..." -Color Cyan
        Write-Progress-Custom -Activity $Description -Status "Starting download"
        
        # Create directory if it doesn't exist
        $dir = Split-Path $OutputPath -Parent
        if (-not (Test-Path $dir)) {
            New-Item -ItemType Directory -Path $dir -Force | Out-Null
        }
        
        # Use .NET WebClient for progress reporting
        $webClient = New-Object System.Net.WebClient
        
        # Register progress event if not disabled
        if (-not $NoProgress) {
            Register-ObjectEvent -InputObject $webClient -EventName DownloadProgressChanged -Action {
                $Global:DLProgress = $Event.SourceEventArgs.ProgressPercentage
                Write-Progress-Custom -Activity $Description -Status "$($Event.SourceEventArgs.ProgressPercentage)% Complete" -PercentComplete $Event.SourceEventArgs.ProgressPercentage
            } | Out-Null
        }
        
        # Download file
        $webClient.DownloadFile($Url, $OutputPath)
        
        # Cleanup
        $webClient.Dispose()
        Get-EventSubscriber | Unregister-Event -Force
        
        Write-Progress-Custom -Activity $Description -Status "Download completed" -PercentComplete 100
        Write-ColorOutput "[OK] Download completed: $OutputPath" -Color Green
        
        return $true
    } catch {
        Write-ColorOutput "[ERROR] Download failed: $($_.Exception.Message)" -Color Red
        return $false
    }
}

# Load configuration from .env file
function Load-EnvFile {
    $envPaths = @(
        ".\.env",
        "$PSScriptRoot\.env",
        "$PSScriptRoot\..\.env",
        "$env:USERPROFILE\.rediacc\.env"
    )
    
    $envFileFound = $false
    foreach ($envPath in $envPaths) {
        if (Test-Path $envPath) {
            Get-Content $envPath | ForEach-Object {
                if ($_ -match '^([^#][^=]+)=(.*)$') {
                    $key = $matches[1].Trim()
                    $value = $matches[2].Trim().Trim('"''')
                    if (-not [Environment]::GetEnvironmentVariable($key)) {
                        [Environment]::SetEnvironmentVariable($key, $value)
                    }
                }
            }
            $envFileFound = $true
            break
        }
    }
    
    # If no .env file found, automatically create one from example
    if (-not $envFileFound) {
        $examplePath = Join-Path $PSScriptRoot ".env.example"
        $targetPath = Join-Path $PSScriptRoot ".env"
        
        if (Test-Path $examplePath) {
            try {
                Copy-Item $examplePath $targetPath
                Write-ColorOutput "`n[INFO] Created .env configuration file from template" -Color Cyan
                Write-ColorOutput "[INFO] Edit .env to customize your configuration" -Color Yellow
                
                # Load the newly created file
                Get-Content $targetPath | ForEach-Object {
                    if ($_ -match '^([^#][^=]+)=(.*)$') {
                        $key = $matches[1].Trim()
                        $value = $matches[2].Trim().Trim('"''')
                        if (-not [Environment]::GetEnvironmentVariable($key)) {
                            [Environment]::SetEnvironmentVariable($key, $value)
                        }
                    }
                }
            } catch {
                Write-ColorOutput "[ERROR] Failed to create .env file: $($_.Exception.Message)" -Color Red
            }
        } else {
            Write-ColorOutput "`n[WARNING] No .env.example file found. Cannot create configuration template." -Color Yellow
        }
    }
}

function Test-RequiredConfiguration {
    param(
        [switch]$Silent
    )
    
    $requiredVars = @(
        @{Name = "SYSTEM_HTTP_PORT"; Description = "Port for the Rediacc API server"},
        @{Name = "REDIACC_API_URL"; Description = "Full URL to the Rediacc API endpoint"}
    )
    
    $missing = @()
    foreach ($var in $requiredVars) {
        if (-not [Environment]::GetEnvironmentVariable($var.Name)) {
            $missing += $var
        }
    }
    
    if ($missing.Count -gt 0 -and -not $Silent) {
        Write-ColorOutput "`n[ERROR] Missing required configuration:" -Color Red
        foreach ($var in $missing) {
            Write-ColorOutput "  $($var.Name): $($var.Description)" -Color Red
        }
        Write-ColorOutput "`nPlease set these environment variables or create a .env file." -Color Yellow
        Write-ColorOutput "See .env.example for a template." -Color Yellow
        
        # Auto-create .env if it doesn't exist
        $envPath = Join-Path $PSScriptRoot ".env"
        if (-not (Test-Path $envPath)) {
            Write-ColorOutput "`nAttempting to create .env from template..." -Color Cyan
            Load-EnvFile
        }
    }
    
    return $missing.Count -eq 0
}

function Install-Python {
    param(
        [string]$InstallPath,
        [switch]$Force
    )
    
    # Check if Python is already installed (unless Force)
    if (-not $Force) {
        $pythonCmd = Get-Command python -ErrorAction SilentlyContinue
        if (-not $pythonCmd) {
            $pythonCmd = Get-Command py -ErrorAction SilentlyContinue
        }
        
        if ($pythonCmd) {
            Write-ColorOutput "[INFO] Python is already installed. Use -ForceReinstall to reinstall." -Color Yellow
            return $true
        }
    }
    
    Write-ColorOutput "Installing Python..." -Color Cyan
    
    # Get system architecture
    $arch = Get-SystemArchitecture
    
    # Python 3.13.5 URLs
    $pythonUrls = @{
        "x64" = "https://www.python.org/ftp/python/3.13.5/python-3.13.5-amd64.exe"
        "x86" = "https://www.python.org/ftp/python/3.13.5/python-3.13.5.exe"
        "arm64" = "https://www.python.org/ftp/python/3.13.5/python-3.13.5-arm64.exe"
    }
    
    $pythonUrl = $pythonUrls[$arch]
    if (-not $pythonUrl) {
        Write-ColorOutput "[ERROR] Unsupported architecture: $arch" -Color Red
        return $false
    }
    
    # Try package managers first
    $packageManagers = Test-PackageManager
    $installedViaPackageManager = $false
    
    foreach ($pm in $packageManagers) {
        if ($pm.Available) {
            Write-ColorOutput "[INFO] Attempting installation via $($pm.Name)..." -Color Yellow
            
            try {
                switch ($pm.Name) {
                    "winget" {
                        $result = Start-Process -FilePath "winget" -ArgumentList "install", "Python.Python.3.13", "--silent", "--accept-source-agreements", "--accept-package-agreements" -Wait -PassThru
                        if ($result.ExitCode -eq 0) {
                            $installedViaPackageManager = $true
                            Write-ColorOutput "[OK] Python installed via Winget" -Color Green
                            break
                        }
                    }
                    "chocolatey" {
                        $result = Start-Process -FilePath "choco" -ArgumentList "install", "python", "--version=3.13.5", "-y" -Wait -PassThru
                        if ($result.ExitCode -eq 0) {
                            $installedViaPackageManager = $true
                            Write-ColorOutput "[OK] Python installed via Chocolatey" -Color Green
                            break
                        }
                    }
                    "scoop" {
                        $result = Start-Process -FilePath "scoop" -ArgumentList "install", "python" -Wait -PassThru
                        if ($result.ExitCode -eq 0) {
                            $installedViaPackageManager = $true
                            Write-ColorOutput "[OK] Python installed via Scoop" -Color Green
                            break
                        }
                    }
                }
            } catch {
                Write-ColorOutput "[WARNING] Failed to install via $($pm.Name): $($_.Exception.Message)" -Color Yellow
            }
            
            if ($installedViaPackageManager) {
                break
            }
        }
    }
    
    # If package manager installation failed, try direct download
    if (-not $installedViaPackageManager) {
        Write-ColorOutput "[INFO] Package manager installation failed or unavailable. Trying direct download..." -Color Yellow
        
        # Create temp directory
        $tempDir = Join-Path $env:TEMP "rediacc-setup"
        $installerPath = Join-Path $tempDir "python-installer.exe"
        
        # Download installer
        $downloadSuccess = Download-File -Url $pythonUrl -OutputPath $installerPath -Description "Downloading Python 3.13.5"
        
        if (-not $downloadSuccess) {
            Write-ColorOutput "[ERROR] Failed to download Python installer" -Color Red
            return $false
        }
        
        # Try silent installation
        try {
            Write-ColorOutput "[INFO] Installing Python silently..." -Color Yellow
            $installArgs = @("/quiet", "InstallAllUsers=1", "PrependPath=1", "Include_test=0")
            
            if ($InstallPath) {
                $installArgs += "TargetDir=$InstallPath"
            }
            
            $result = Start-Process -FilePath $installerPath -ArgumentList $installArgs -Wait -PassThru
            
            if ($result.ExitCode -eq 0) {
                Write-ColorOutput "[OK] Python installed successfully" -Color Green
                $installedViaPackageManager = $true
            } else {
                Write-ColorOutput "[WARNING] Silent installation failed (exit code: $($result.ExitCode))" -Color Yellow
            }
        } catch {
            Write-ColorOutput "[WARNING] Silent installation failed: $($_.Exception.Message)" -Color Yellow
        }
        
        # If silent installation failed, prompt for manual installation
        if (-not $installedViaPackageManager) {
            Write-ColorOutput "[INFO] Automatic installation failed. Opening installer for manual installation..." -Color Yellow
            
            if ($AutoInstall) {
                Write-ColorOutput "[ERROR] Cannot proceed with manual installation in AutoInstall mode" -Color Red
                return $false
            }
            
            $answer = Read-Host "Would you like to run the installer manually? (y/n)"
            if ($answer -eq 'y') {
                Start-Process -FilePath $installerPath -Wait
                Write-ColorOutput "[INFO] Please restart your command prompt after installation" -Color Yellow
            } else {
                Write-ColorOutput "[INFO] Python installer saved to: $installerPath" -Color Cyan
                Write-ColorOutput "[INFO] Please run it manually when ready" -Color Cyan
            }
        }
        
        # Cleanup
        try {
            Remove-Item $installerPath -ErrorAction SilentlyContinue
        } catch {
            # Ignore cleanup errors
        }
    }
    
    # Refresh PATH and verify installation
    if ($installedViaPackageManager) {
        Write-ColorOutput "[INFO] Refreshing environment variables..." -Color Yellow
        $env:Path = [System.Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path", "User")
        
        # Verify installation
        Start-Sleep 2
        $pythonCmd = Get-Command python -ErrorAction SilentlyContinue
        if (-not $pythonCmd) {
            $pythonCmd = Get-Command py -ErrorAction SilentlyContinue
        }
        
        if ($pythonCmd) {
            $pythonVersion = & $pythonCmd.Source --version 2>&1
            Write-ColorOutput "[OK] Python verification successful: $pythonVersion" -Color Green
            return $true
        } else {
            Write-ColorOutput "[WARNING] Python installation completed but not detected in PATH" -Color Yellow
            Write-ColorOutput "[INFO] Please restart your command prompt" -Color Yellow
            return $true
        }
    }
    
    return $false
}

function Install-MSYS2-Auto {
    param(
        [string]$InstallPath,
        [switch]$Force
    )
    
    # Check if MSYS2 is already installed (unless Force)
    if (-not $Force) {
        $msys2Path = Find-MSYS2
        if ($msys2Path) {
            Write-ColorOutput "[INFO] MSYS2 is already installed at: $msys2Path. Use -ForceReinstall to reinstall." -Color Yellow
            return $true
        }
    }
    
    Write-ColorOutput "Installing MSYS2..." -Color Cyan
    
    # MSYS2 installer URL
    $msys2Url = "https://github.com/msys2/msys2-installer/releases/download/2025-06-22/msys2-x86_64-20250622.exe"
    $defaultInstallPath = if ($InstallPath) { $InstallPath } else { "C:\msys64" }
    
    # Try package managers first
    $packageManagers = Test-PackageManager
    $installedViaPackageManager = $false
    
    foreach ($pm in $packageManagers) {
        if ($pm.Available) {
            Write-ColorOutput "[INFO] Attempting installation via $($pm.Name)..." -Color Yellow
            
            try {
                switch ($pm.Name) {
                    "winget" {
                        $result = Start-Process -FilePath "winget" -ArgumentList "install", "MSYS2.MSYS2", "--silent", "--accept-source-agreements", "--accept-package-agreements" -Wait -PassThru
                        if ($result.ExitCode -eq 0) {
                            $installedViaPackageManager = $true
                            Write-ColorOutput "[OK] MSYS2 installed via Winget" -Color Green
                            break
                        }
                    }
                    "chocolatey" {
                        $chocoArgs = @("install", "msys2", "-y")
                        if ($InstallPath) {
                            $chocoArgs += "--params", "/InstallDir:$InstallPath"
                        }
                        $result = Start-Process -FilePath "choco" -ArgumentList $chocoArgs -Wait -PassThru
                        if ($result.ExitCode -eq 0) {
                            $installedViaPackageManager = $true
                            Write-ColorOutput "[OK] MSYS2 installed via Chocolatey" -Color Green
                            break
                        }
                    }
                    "scoop" {
                        # Note: Scoop doesn't have MSYS2 in main bucket, skip
                        Write-ColorOutput "[INFO] Scoop doesn't support MSYS2 installation, skipping..." -Color Yellow
                    }
                }
            } catch {
                Write-ColorOutput "[WARNING] Failed to install via $($pm.Name): $($_.Exception.Message)" -Color Yellow
            }
            
            if ($installedViaPackageManager) {
                break
            }
        }
    }
    
    # If package manager installation failed, try direct download
    if (-not $installedViaPackageManager) {
        Write-ColorOutput "[INFO] Package manager installation failed or unavailable. Trying direct download..." -Color Yellow
        
        # Create temp directory
        $tempDir = Join-Path $env:TEMP "rediacc-setup"
        $installerPath = Join-Path $tempDir "msys2-installer.exe"
        
        # Download installer
        $downloadSuccess = Download-File -Url $msys2Url -OutputPath $installerPath -Description "Downloading MSYS2 installer"
        
        if (-not $downloadSuccess) {
            Write-ColorOutput "[ERROR] Failed to download MSYS2 installer" -Color Red
            return $false
        }
        
        # Try silent installation
        try {
            Write-ColorOutput "[INFO] Installing MSYS2 silently..." -Color Yellow
            $installArgs = @("install", "--root", $defaultInstallPath, "--confirm-command")
            
            $result = Start-Process -FilePath $installerPath -ArgumentList $installArgs -Wait -PassThru
            
            if ($result.ExitCode -eq 0) {
                Write-ColorOutput "[OK] MSYS2 installed successfully" -Color Green
                $installedViaPackageManager = $true
            } else {
                Write-ColorOutput "[WARNING] Silent installation failed (exit code: $($result.ExitCode))" -Color Yellow
            }
        } catch {
            Write-ColorOutput "[WARNING] Silent installation failed: $($_.Exception.Message)" -Color Yellow
        }
        
        # If silent installation failed, prompt for manual installation
        if (-not $installedViaPackageManager) {
            Write-ColorOutput "[INFO] Automatic installation failed. Opening installer for manual installation..." -Color Yellow
            
            if ($AutoInstall) {
                Write-ColorOutput "[ERROR] Cannot proceed with manual installation in AutoInstall mode" -Color Red
                return $false
            }
            
            $answer = Read-Host "Would you like to run the installer manually? (y/n)"
            if ($answer -eq 'y') {
                Start-Process -FilePath $installerPath -Wait
                Write-ColorOutput "[INFO] Please restart your command prompt after installation" -Color Yellow
            } else {
                Write-ColorOutput "[INFO] MSYS2 installer saved to: $installerPath" -Color Cyan
                Write-ColorOutput "[INFO] Please run it manually when ready" -Color Cyan
            }
        }
        
        # Cleanup
        try {
            Remove-Item $installerPath -ErrorAction SilentlyContinue
        } catch {
            # Ignore cleanup errors
        }
    }
    
    # Verify installation and install required packages
    if ($installedViaPackageManager) {
        Write-ColorOutput "[INFO] Locating MSYS2 installation..." -Color Yellow
        
        # Update MSYS2 paths and find installation
        $script:MSYS2_PATHS = @(
            $defaultInstallPath,
            "C:\msys64",
            "C:\msys2",
            "$env:USERPROFILE\msys64",
            "$env:USERPROFILE\msys2"
        )
        
        $msys2Path = Find-MSYS2
        if ($msys2Path) {
            Write-ColorOutput "[OK] MSYS2 found at: $msys2Path" -Color Green
            
            # Set environment variable
            [Environment]::SetEnvironmentVariable("MSYS2_ROOT", $msys2Path, [EnvironmentVariableTarget]::User)
            $env:MSYS2_ROOT = $msys2Path
            
            # Install required packages
            Write-ColorOutput "[INFO] Installing required packages (rsync, openssh)..." -Color Yellow
            try {
                Install-MSYS2Packages -MSYS2Path $msys2Path
                Write-ColorOutput "[OK] MSYS2 setup completed successfully" -Color Green
                return $true
            } catch {
                Write-ColorOutput "[WARNING] MSYS2 installed but package installation failed: $($_.Exception.Message)" -Color Yellow
                return $true
            }
        } else {
            Write-ColorOutput "[WARNING] MSYS2 installation completed but not detected" -Color Yellow
            Write-ColorOutput "[INFO] Please restart your command prompt" -Color Yellow
            return $true
        }
    }
    
    return $false
}

# Load environment if needed
if (-not $env:REDIACC_MSYS2_ROOT) {
    Load-EnvFile
}

# Script configuration
if ($env:REDIACC_MSYS2_ROOT) {
    $script:MSYS2_PATHS = @($env:REDIACC_MSYS2_ROOT)
} else {
    Write-ColorOutput "Warning: REDIACC_MSYS2_ROOT not set. Please configure your .env file." "Yellow"
    # Still try common paths as last resort
    $script:MSYS2_PATHS = @(
        "C:\msys64",
        "C:\msys2",
        "$env:USERPROFILE\msys64",
        "$env:USERPROFILE\msys2"
    )
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
        python = Test-Path "$MSYS2Path\usr\bin\python.exe"
        python3 = Test-Path "$MSYS2Path\usr\bin\python3.exe"
    }
    return $components
}

function Install-MSYS2Packages {
    param([string]$MSYS2Path)
    
    Write-ColorOutput "`nInstalling required MSYS2 packages..." -Color Cyan
    
    $installScript = @'
#!/bin/bash
set -e  # Exit on any error

echo "=== MSYS2 Package Installation ==="
echo "Starting package installation process..."

echo "Step 1: Updating package database..."
pacman -Sy --noconfirm
echo "[OK] Package database updated"

echo "Step 2: Installing core packages..."
pacman -S --noconfirm rsync openssh python python-pip
echo "[OK] Core packages installed"

echo "Step 3: Creating python3 symlink..."
ln -sf /usr/bin/python /usr/bin/python3
echo "[OK] python3 symlink created"

echo "Step 4: Checking Python installation..."
echo "Python version: $(python --version)"
echo "Python3 version: $(python3 --version)"

echo "Step 5: Installing Python packages..."
echo "Upgrading pip..."
python -m pip install --upgrade pip --break-system-packages

echo "Installing requests (simple package)..."
python -m pip install --break-system-packages requests

echo "Attempting cryptography installation..."
if python -m pip install --break-system-packages cryptography; then
    echo "[OK] Cryptography installed via pip"
else
    echo "[WARNING] Cryptography pip installation failed, trying alternative..."
    # Try using pacman if available
    if pacman -S --noconfirm python-cryptography 2>/dev/null; then
        echo "[OK] Cryptography installed via pacman"
    else
        echo "[WARNING] Cryptography installation failed - may need manual setup"
        echo "You can try: pacman -S python-cryptography"
    fi
fi

echo "=== Installation Summary ==="
echo "Installed packages:"
echo "- rsync: $(rsync --version 2>/dev/null | head -n1 || echo 'not found')"
echo "- ssh: $(ssh -V 2>&1 || echo 'not found')"
echo "- python: $(python --version 2>/dev/null || echo 'not found')"
echo "- python3: $(python3 --version 2>/dev/null || echo 'not found')"

echo "Testing Python imports..."
python -c "import requests; print('✓ requests:', requests.__version__)" 2>/dev/null || echo "✗ requests: failed"
python -c "import cryptography; print('✓ cryptography:', cryptography.__version__)" 2>/dev/null || echo "✗ cryptography: failed"

echo "=== Installation Complete ==="
'@
    
    try {
        $tempScript = [System.IO.Path]::GetTempFileName()
        $installScript | Out-File -FilePath $tempScript -Encoding UTF8 -NoNewline
        
        # Use bash.exe directly for better output handling
        $bashExe = Join-Path $MSYS2Path "usr\bin\bash.exe"
        $bashPath = ($tempScript -replace '\\','/') -replace '^([A-Z]):','/$1' -replace ':',''
        
        Write-ColorOutput "[INFO] Executing installation script..." -Color Yellow
        Write-ColorOutput "[INFO] Script path: $tempScript" -Color Gray
        
        if (Test-Path $bashExe) {
            # Use bash.exe directly with login shell for proper environment
            $result = Start-Process -FilePath $bashExe -ArgumentList "-l", $bashPath -Wait -PassThru -NoNewWindow
            
            if ($result.ExitCode -eq 0) {
                Write-ColorOutput "[OK] MSYS2 packages installed successfully" -Color Green
            } else {
                Write-ColorOutput "[WARNING] Installation completed with exit code: $($result.ExitCode)" -Color Yellow
            }
        } else {
            # Fallback to msys2.exe
            $msys2Exe = Join-Path $MSYS2Path "msys2.exe"
            Write-ColorOutput "[INFO] Using fallback msys2.exe: $msys2Exe" -Color Yellow
            
            $result = Start-Process -FilePath $msys2Exe -ArgumentList "-c", "bash $bashPath" -Wait -PassThru -NoNewWindow
            
            if ($result.ExitCode -eq 0) {
                Write-ColorOutput "[OK] MSYS2 packages installed successfully" -Color Green
            } else {
                Write-ColorOutput "[WARNING] Installation completed with exit code: $($result.ExitCode)" -Color Yellow
            }
        }
        
        # Give user time to see output
        Start-Sleep -Seconds 2
        
    } catch {
        Write-ColorOutput "[ERROR] Failed to install MSYS2 packages: $($_.Exception.Message)" -Color Red
    } finally {
        # Cleanup
        if (Test-Path $tempScript) {
            Remove-Item $tempScript -ErrorAction SilentlyContinue
        }
    }
}

function Setup-Environment {
    param([switch]$Force)
    
    Write-ColorOutput "=== Rediacc CLI Windows Setup ===" -Color Cyan
    Write-ColorOutput ""
    
    # Check Windows version compatibility
    $windowsCompatible = Test-WindowsVersion
    if (-not $windowsCompatible) {
        Write-ColorOutput "[WARNING] This version of Windows may not be fully supported" -Color Yellow
    }
    
    # Check Python
    $pythonCmd = Get-Command python -ErrorAction SilentlyContinue
    if (-not $pythonCmd) {
        $pythonCmd = Get-Command py -ErrorAction SilentlyContinue
    }
    
    if ($pythonCmd) {
        $pythonVersion = & $pythonCmd.Source --version 2>&1
        Write-ColorOutput "[OK] Python found: $pythonVersion" -Color Green
    } else {
        Write-ColorOutput "[MISSING] Python not found" -Color Red
        
        if (-not $SkipPython) {
            if ($Force -or $AutoInstall) {
                Write-ColorOutput "[INFO] Attempting automatic Python installation..." -Color Yellow
                $pythonInstalled = Install-Python -InstallPath $InstallDir -Force:$ForceReinstall
                if (-not $pythonInstalled) {
                    Write-ColorOutput "[ERROR] Python installation failed" -Color Red
                    return $false
                }
            } else {
                Write-ColorOutput "[INFO] Python is required for CLI functionality" -Color Yellow
                $answer = Read-Host "Would you like to install Python automatically? (y/n)"
                if ($answer -eq 'y') {
                    $pythonInstalled = Install-Python -InstallPath $InstallDir -Force:$ForceReinstall
                    if (-not $pythonInstalled) {
                        Write-ColorOutput "[ERROR] Python installation failed" -Color Red
                        return $false
                    }
                } else {
                    Write-ColorOutput "[INFO] Please install Python manually from: https://www.python.org/" -Color Yellow
                    return $false
                }
            }
        } else {
            Write-ColorOutput "[INFO] Python installation skipped (-SkipPython)" -Color Yellow
        }
    }
    
    # Install Python packages if Python is available
    $python = Find-Python
    if ($python) {
        Write-ColorOutput "[INFO] Found Python: $($python.Version)" -Color Green
        Install-PythonPackages -PythonCommand $python.Command
    }
    
    # Check MSYS2
    $msys2Path = Find-MSYS2
    if (-not $msys2Path) {
        Write-ColorOutput "[MISSING] MSYS2 not found" -Color Red
        
        if (-not $SkipMSYS2) {
            if ($Force -or $AutoInstall) {
                Write-ColorOutput "[INFO] Attempting automatic MSYS2 installation..." -Color Yellow
                $msys2Installed = Install-MSYS2-Auto -InstallPath $InstallDir -Force:$ForceReinstall
                if (-not $msys2Installed) {
                    Write-ColorOutput "[ERROR] MSYS2 installation failed" -Color Red
                    return $false
                }
            } else {
                Write-ColorOutput "[INFO] MSYS2 is required for rsync functionality" -Color Yellow
                $answer = Read-Host "Would you like to install MSYS2 automatically? (y/n)"
                if ($answer -eq 'y') {
                    $msys2Installed = Install-MSYS2-Auto -InstallPath $InstallDir -Force:$ForceReinstall
                    if (-not $msys2Installed) {
                        Write-ColorOutput "[ERROR] MSYS2 installation failed" -Color Red
                        return $false
                    }
                } else {
                    Write-ColorOutput "[INFO] Please install MSYS2 manually from: https://www.msys2.org/" -Color Yellow
                    return $false
                }
            }
        } else {
            Write-ColorOutput "[INFO] MSYS2 installation skipped (-SkipMSYS2)" -Color Yellow
        }
    } else {
        Write-ColorOutput "[OK] MSYS2 found: $msys2Path" -Color Green
        
        # Check components
        $components = Test-MSYS2Components -MSYS2Path $msys2Path
        $allInstalled = $components.rsync -and $components.ssh -and $components.python
        
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
        
        if (-not $components.python) {
            Write-ColorOutput "[MISSING] Python not installed in MSYS2" -Color Yellow
        } else {
            Write-ColorOutput "[OK] Python installed in MSYS2" -Color Green
            
            # Check if python3 symlink exists
            if ($components.python3) {
                Write-ColorOutput "[OK] python3 symlink available" -Color Green
            } else {
                Write-ColorOutput "[WARNING] python3 symlink missing (will be created)" -Color Yellow
            }
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
                    Write-ColorOutput "  pacman -S rsync openssh python python-pip" -Color White
                    Write-ColorOutput "  ln -sf /usr/bin/python /usr/bin/python3" -Color White
                    Write-ColorOutput "  python -m pip install cryptography requests" -Color White
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
    
    # Find Python using our enhanced detection
    $python = Find-Python
    if (-not $python) {
        Write-ColorOutput "ERROR: Python not found. Run: .\rediacc.ps1 setup" -Color Red
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
    $scriptPath = Join-Path (Join-Path $PSScriptRoot "src\cli") $Tool
    
    # Execute
    & $python.Command $scriptPath $Arguments
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
    gui         Launch graphical user interface
    help        Show this help message

SETUP:
    .\rediacc-cli.ps1 setup
    .\rediacc-cli.ps1 setup -AutoInstall
    .\rediacc-cli.ps1 setup -ForceReinstall
    .\rediacc-cli.ps1 setup -SkipPython -SkipMSYS2
    .\rediacc-cli.ps1 setup -InstallDir C:\custom\path

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

GRAPHICAL USER INTERFACE:
    .\rediacc-cli.ps1 gui

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
    -ForceReinstall     Force reinstallation of components even if they exist
    -SkipPython         Skip Python installation during setup
    -SkipMSYS2          Skip MSYS2 installation during setup
    -InstallDir         Custom installation directory for components
    -NoProgress         Disable progress indicators during downloads

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
        $testScript = Join-Path (Join-Path $PSScriptRoot "scripts") "test_windows_compat.py"
        $python = Find-Python
        
        if ($python) {
            & $python.Command $testScript
        } else {
            Write-ColorOutput "ERROR: Python not found. Run: .\rediacc.ps1 setup" -Color Red
        }
    }
    
    'gui' {
        Invoke-RediaccCLI -Tool "rediacc-cli" -Arguments @('--gui')
    }
    
    'help' {
        Show-Help
    }
    
    default {
        Show-Help
    }
}