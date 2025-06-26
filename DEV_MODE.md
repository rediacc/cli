# Development Mode for Rediacc CLI Tools

## Problem

In development environments, SSH host fingerprints often change when:
- Machines are recreated or redeployed
- Network configurations change
- Development VMs are reset

This causes SSH connections to fail with errors like:
```
Load key "/tmp/tmpfgzm6xs7_rsa": error in libcrypto
Warning: Permanently added '192.168.111.11' (ED25519) to the list of known hosts.
```

## Solution: Development Mode (`--dev` flag)

Both `rediacc-cli-term` and `rediacc-cli-sync` now support a `--dev` flag that:
- Disables strict host key checking
- Uses `StrictHostKeyChecking=accept-new` instead of verifying against stored fingerprints
- Maintains security by still using SSH key authentication

## Usage

### Terminal Access
```bash
# Machine connection in dev mode
./rediacc-cli-term --token TOKEN --machine rediacc11 --dev

# Repository connection in dev mode
./rediacc-cli-term --token TOKEN --machine rediacc11 --repo A1 --dev

# Execute command in dev mode
./rediacc-cli-term --token TOKEN --machine rediacc11 --dev --command "docker ps -a"
```

### File Sync
```bash
# Upload in dev mode
./rediacc-cli-sync upload --token TOKEN --local ./files --machine rediacc11 --repo A1 --dev

# Download in dev mode
./rediacc-cli-sync download --token TOKEN --machine rediacc11 --repo A1 --local ./backup --dev
```

## How It Works

1. **Normal Mode**: Uses `HOST_ENTRY` from machine vault for strict host key verification
2. **Dev Mode**: Temporarily ignores `HOST_ENTRY` and accepts new host keys automatically

## Security Considerations

- **Use `--dev` flag ONLY in development environments**
- Production environments should always use strict host key checking
- SSH key authentication is still required (no password authentication)
- The flag only affects host key verification, not user authentication

## Alternative Solutions Considered

1. **Update HOST_ENTRY in vault**: Would require API changes and manual updates
2. **Disable all SSH security**: Too risky, even for development
3. **Use SSH config file**: Would affect all SSH connections, not just Rediacc
4. **Auto-detect development**: Could lead to accidental security relaxation

The `--dev` flag provides explicit control while maintaining security awareness.