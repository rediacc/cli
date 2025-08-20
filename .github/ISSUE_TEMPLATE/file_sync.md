---
name: File Sync Issue
about: Report problems with rediacc-sync file synchronization operations
title: '[SYNC] '
labels: 'sync, needs-triage'
assignees: ''
---

## Sync Issue Description
<!-- Describe the file synchronization problem -->

## Sync Operation Details

### Operation Type
- [ ] Upload (local → remote)
- [ ] Download (remote → local)
- [ ] Mirror mode
- [ ] Verify mode
- [ ] Dry run

### Command Used
```bash
# Exact sync command executed
./rediacc sync [upload|download] --machine <machine> --repo <repo> --local <path> [options]
```

## Environment
- **OS**: <!-- e.g., Ubuntu 22.04, macOS 14.0, Windows 11 -->
- **Rediacc CLI Version**: <!-- Run: ./rediacc --version -->
- **rsync Version**: <!-- Run: rsync --version -->

### Platform-Specific Details

<details>
<summary>Windows Users</summary>

- **MSYS2 Installed**: <!-- Yes/No -->
- **MSYS2 rsync Path**: <!-- Usually C:\msys64\usr\bin\rsync.exe -->
- **Using PowerShell/CMD/MSYS2 Terminal**: <!-- Which terminal? -->

```powershell
# Check rsync availability
C:\msys64\usr\bin\bash.exe -c "which rsync && rsync --version"
```

</details>

<details>
<summary>Linux/macOS Users</summary>

```bash
# Check rsync installation
which rsync
rsync --version
```

</details>

## Sync Configuration

### Source and Destination
- **Local Path**: <!-- Full path to local directory -->
- **Machine Name**: <!-- Target machine -->
- **Repository Name**: <!-- Target repository -->
- **Remote Path**: <!-- If known, the remote datastore path -->

### Path Information
```bash
# Local path details
ls -la <local-path>
du -sh <local-path>  # Size
find <local-path> -type f | wc -l  # File count

# Check permissions
stat <local-path>
```

## Connection Details

### SSH Connection Test
```bash
# Test SSH to machine (if you have direct access)
./rediacc term --machine <machine> --command "echo 'Connection successful'"

# Check machine details
./rediacc inspect machine <machine-name>
```

### Network Conditions
- **Connection Type**: <!-- LAN/WAN/VPN -->
- **Bandwidth**: <!-- If known -->
- **Latency to Server**: <!-- ping results if available -->
- **Large Files Involved**: <!-- Yes/No, sizes -->

## Error Information

### Primary Error Message
```
# Paste the main error message
```

### Verbose Sync Output
```bash
# Run with verbose flags
./rediacc sync upload --machine <machine> --repo <repo> --local <path> --verbose

# Or with rsync verbose
RSYNC_VERBOSE="-vvv" ./rediacc sync [command]

# Paste output here
```

### rsync Specific Errors
```
# Any rsync error codes or messages
# Common codes:
# 23 - Partial transfer
# 24 - Source files vanished
# 255 - SSH connection failed
```

## File System Issues

### Permissions
- **Local Directory Writable**: <!-- Yes/No -->
- **File Ownership Issues**: <!-- Yes/No -->
- **Special Characters in Filenames**: <!-- Yes/No -->

```bash
# Check for problematic filenames
find <local-path> -name "*[[:space:]]*" -o -name "*[\"']*"
```

### Space Availability
```bash
# Local space
df -h <local-path>

# Remote space (if accessible)
./rediacc term --machine <machine> --command "df -h /path/to/datastore"
```

## Sync Options Used
<!-- Check all options that were used -->
- [ ] `--mirror` (exact replication)
- [ ] `--verify` (checksum verification)
- [ ] `--exclude` (exclusion patterns)
- [ ] `--include` (inclusion patterns)
- [ ] `--compress` (compression enabled)
- [ ] `--partial` (resume partial transfers)
- [ ] `--confirm` (preview mode)
- [ ] `--dev` (development mode)

### Exclusion/Inclusion Patterns
```bash
# If using exclude/include patterns, list them
--exclude "*.log"
--include "*.txt"
```

## Transfer Statistics

### Transfer Progress
- **Total Files**: <!-- Number -->
- **Transferred Successfully**: <!-- Number -->
- **Failed Files**: <!-- Number -->
- **Transfer Size**: <!-- MB/GB -->
- **Time Elapsed**: <!-- Duration -->

### Specific File Failures
```
# List specific files that failed to sync
```

## Attempted Solutions
<!-- What have you tried? -->

- [ ] Verified SSH connectivity
- [ ] Checked file permissions
- [ ] Ensured sufficient disk space
- [ ] Tried smaller file sets
- [ ] Used `--partial` for resume
- [ ] Removed special characters from filenames
- [ ] Updated rsync version
- [ ] Tried without compression
- [ ] Other: <!-- Specify -->

## Workarounds
<!-- Any temporary solutions? -->

## Logs

### Sync Log
<details>
<summary>Click to expand full sync log</summary>

```
# Full sync operation log
```

</details>

### SSH Debug Log
<details>
<summary>Click to expand SSH debug output (if relevant)</summary>

```bash
# SSH verbose output
ssh -vv user@host
```

</details>

## Additional Context

### File Types
- **Types of Files**: <!-- Code, binaries, media, etc. -->
- **Average File Size**: <!-- KB/MB/GB -->
- **Total Dataset Size**: <!-- MB/GB/TB -->
- **Binary vs Text Files**: <!-- Ratio -->

### Performance Metrics
- **Expected Transfer Rate**: <!-- MB/s -->
- **Actual Transfer Rate**: <!-- MB/s -->
- **Network Interruptions**: <!-- Yes/No -->

### Related Documentation
- [ ] Reviewed [Sync Documentation](docs/SYNC.md)
- [ ] Checked [Troubleshooting Guide](docs/guides/TROUBLESHOOTING.md)

---
<!-- 
Before submitting:
1. Remove sensitive information (paths, IPs, credentials)
2. Try sync with a small test directory first
3. Verify rsync is properly installed and accessible
4. Test SSH connectivity independently
-->