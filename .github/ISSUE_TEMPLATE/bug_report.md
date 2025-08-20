---
name: Bug Report
about: Report a bug or unexpected behavior in Rediacc CLI
title: '[BUG] '
labels: 'bug, needs-triage'
assignees: ''
---

## Bug Description
<!-- A clear and concise description of what the bug is -->

## Environment Information

### System Details
- **OS**: <!-- e.g., Ubuntu 22.04, macOS 14.0, Windows 11 -->
- **Python Version**: <!-- Run: python --version -->
- **Rediacc CLI Version**: <!-- Run: ./rediacc --version or check _version.py -->
- **Installation Method**: <!-- pip, manual, Docker, etc. -->

### Platform-Specific
<!-- Check the relevant section for your platform -->

<details>
<summary>Windows Users</summary>

- **MSYS2 Installed**: <!-- Yes/No -->
- **PowerShell Version**: <!-- Run: $PSVersionTable.PSVersion -->
- **rsync Available**: <!-- Run in MSYS2: rsync --version -->

</details>

<details>
<summary>Linux/macOS Users</summary>

- **Shell**: <!-- bash, zsh, etc. -->
- **rsync Version**: <!-- Run: rsync --version -->
- **SSH Version**: <!-- Run: ssh -V -->

</details>

## Steps to Reproduce
<!-- Provide detailed steps to reproduce the issue -->

1. <!-- First step -->
2. <!-- Second step -->
3. <!-- Third step -->
4. <!-- See error -->

### Command Executed
```bash
# Exact command that triggered the issue
```

## Expected Behavior
<!-- What you expected to happen -->

## Actual Behavior
<!-- What actually happened -->

### Error Output
```
# Paste the complete error message/stack trace here
```

### Debug Output
<!-- If applicable, run with verbose/debug flags -->
```bash
# For verbose output, try:
# REDIACC_DEBUG=1 ./rediacc [your command]
# or
# ./rediacc --verbose [your command]
```

## Additional Context

### Configuration
<!-- If relevant, share your configuration (remove sensitive data) -->
```json
# Contents of ~/.rediacc/config.json (sanitized)
```

### Network/Connectivity
- **Behind Proxy**: <!-- Yes/No -->
- **VPN Active**: <!-- Yes/No -->
- **API Endpoint**: <!-- If using custom endpoint -->

### Related Components
- [ ] Authentication/Token issues
- [ ] SSH connection problems
- [ ] API communication errors
- [ ] File sync operations
- [ ] GUI-related
- [ ] Terminal access
- [ ] Other: <!-- Specify -->

## Logs
<!-- Attach any relevant log files -->

<details>
<summary>Click to expand logs</summary>

```
# Paste logs here
```

</details>

## Possible Solution
<!-- If you have suggestions on how to fix the issue -->

## Related Issues
<!-- Link any related issues or discussions -->
- #<!-- issue number -->

---
<!-- 
Before submitting:
1. Check existing issues for duplicates
2. Try the troubleshooting guide: docs/guides/TROUBLESHOOTING.md
3. Ensure you're using the latest version
4. Remove any sensitive information (tokens, passwords, IPs)
-->