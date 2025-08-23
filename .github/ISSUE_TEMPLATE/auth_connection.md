---
name: Authentication/Connection Issue
about: Report problems with authentication, API connections, or SSH access
title: '[AUTH] '
labels: 'authentication, connectivity, needs-triage'
assignees: ''
---

## Issue Description
<!-- Describe the authentication or connection problem -->

## Issue Type
<!-- Check all that apply -->
- [ ] Login/Authentication failure
- [ ] Token rotation issues
- [ ] API connection problems
- [ ] SSH connection failures
- [ ] Network/proxy issues
- [ ] Certificate/SSL problems
- [ ] Host key verification
- [ ] Other: <!-- Specify -->

## Environment
- **OS**: <!-- e.g., Ubuntu 22.04, macOS 14.0, Windows 11 -->
- **Rediacc CLI Version**: <!-- Run: ./rediacc --version -->
- **Network Environment**: <!-- Corporate/Home/Cloud -->

## Authentication Details

### Current Authentication Status
```bash
# Check authentication status
./rediacc status

# Check token configuration
cat ~/.rediacc/config.json | grep -E "(token|api_url)" | head -5
# (Remove sensitive token values before sharing)
```

### API Configuration
- **API URL**: <!-- e.g., https://www.rediacc.com or custom -->
- **Using Custom Endpoint**: <!-- Yes/No -->
- **Environment Variables Set**: <!-- List any SYSTEM_API_URL, etc. -->

## Connection Tests

### API Connectivity
```bash
# Test API endpoint accessibility
curl -I <your-api-url>/health  # Replace with actual endpoint

# Test with CLI
./rediacc list teams --verbose

# Check DNS resolution
nslookup <api-hostname>
```

### Network Configuration
- **Behind Proxy**: <!-- Yes/No -->
- **Proxy URL**: <!-- If applicable, sanitize credentials -->
- **VPN Active**: <!-- Yes/No -->
- **Firewall Restrictions**: <!-- Yes/No/Unknown -->

```bash
# Check proxy settings
echo $HTTP_PROXY
echo $HTTPS_PROXY
echo $NO_PROXY
```

## SSH Connection Issues
<!-- If the issue involves SSH connections -->

### SSH Configuration
```bash
# SSH version
ssh -V

# Check SSH config
cat ~/.ssh/config | grep -A5 "rediacc"  # If relevant

# Test SSH connectivity (if applicable)
ssh -vv user@host  # Verbose output (sanitize before sharing)
```

### Known Hosts Issues
- **StrictHostKeyChecking**: <!-- Yes/No/Ask -->
- **Host Key Changed**: <!-- Yes/No -->
- **First Connection**: <!-- Yes/No -->

```bash
# Check known_hosts
grep <hostname> ~/.ssh/known_hosts
```

## Error Messages

### Primary Error
```
# Paste the main error message here
```

### Verbose/Debug Output
```bash
# Run with debug flags
REDIACC_DEBUG=1 ./rediacc [command]
# Or
./rediacc --verbose [command]

# Paste output here (remove sensitive data)
```

### API Response
```json
# If you can see the API response, paste it here
{
  "error": "",
  "status": "",
  "message": ""
}
```

## Token Information
<!-- DO NOT share actual token values -->

### Token Format Check
- **Token Length**: <!-- Approximate length -->
- **Token Prefix**: <!-- First few characters only -->
- **Contains Special Characters**: <!-- Yes/No -->
- **Rotates Properly**: <!-- Yes/No/Unknown -->

### Token Lifecycle
1. Initial authentication method: <!-- Email/Password, SSO, etc. -->
2. Token storage location: <!-- ~/.rediacc/config.json -->
3. Last successful authentication: <!-- Date/Time if known -->
4. Token expiration behavior: <!-- What happens when it expires -->

## SSL/TLS Issues
<!-- If experiencing certificate problems -->

```bash
# Test SSL connection
openssl s_client -connect <api-host>:443 -servername <api-host>

# Check certificate
curl -vI https://<api-url> 2>&1 | grep -E "(SSL|certificate)"
```

## Attempted Solutions
<!-- What have you tried? -->

- [ ] Logged out and back in (`./rediacc logout && ./rediacc login`)
- [ ] Deleted config and re-authenticated
- [ ] Checked network connectivity
- [ ] Disabled proxy/VPN
- [ ] Updated CLI to latest version
- [ ] Cleared SSH known_hosts
- [ ] Used --dev flag for SSH
- [ ] Other: <!-- Specify -->

## Workarounds
<!-- Any temporary solutions that work? -->

## Logs and Diagnostics

### Authentication Log
<details>
<summary>Click to expand authentication attempts</summary>

```
# Paste relevant log entries
```

</details>

### Network Trace
<details>
<summary>Click to expand network trace (if applicable)</summary>

```
# tcpdump, wireshark summary, etc. (sanitized)
```

</details>

## Additional Context

### Recent Changes
<!-- Any recent changes that might be related? -->
- [ ] Network configuration changed
- [ ] Proxy/firewall rules updated
- [ ] CLI version upgraded
- [ ] API endpoint changed
- [ ] Credentials rotated
- [ ] Other: <!-- Specify -->

### Related Issues
- #<!-- issue number -->

---
<!-- 
Before submitting:
1. Remove ALL sensitive information (tokens, passwords, internal IPs)
2. Try basic troubleshooting from docs/guides/TROUBLESHOOTING.md
3. Test with latest CLI version
4. Check if issue is network-specific (try different network)
-->