# Terminal Access Guide

The `rediacc-cli-term` tool provides SSH access to remote machines and repository environments.

## Overview

Key features:
- Direct SSH access to machines
- Repository-specific Docker environments
- Single command execution
- Interactive shell sessions
- Pre-configured environment variables
- Helper functions for container management

## Access Modes

### 1. Repository Environment (Docker Container)

Access a specific repository's Docker environment:

```bash
# Interactive shell in repository container
rediacc-cli-term --machine server --repo webapp

# Execute command in repository
rediacc-cli-term --machine server --repo webapp --command "npm list"
```

When accessing a repository:
- Connects to the repository's Docker container
- Working directory set to repository root
- Environment variables pre-configured
- Helper functions available

### 2. Machine Direct Access

Access the machine directly as the universal user:

```bash
# Interactive shell on machine
rediacc-cli-term --machine server

# Execute command on machine
rediacc-cli-term --machine server --command "df -h"
```

When accessing a machine directly:
- Connects as the `universal` user
- Access to all repositories on the machine
- Can manage Docker containers
- System-level operations

## Common Use Cases

### 1. Application Management

```bash
# Check application status
rediacc-cli-term --machine prod --repo api --command "npm start status"

# View logs
rediacc-cli-term --machine prod --repo api --command "tail -f logs/app.log"

# Restart service
rediacc-cli-term --machine prod --repo api --command "npm restart"

# Interactive debugging
rediacc-cli-term --machine prod --repo api
# Then in the shell:
$ npm test
$ node debug.js
```

### 2. Docker Operations

```bash
# List all containers on machine
rediacc-cli-term --machine server --command "docker ps -a"

# Check container logs
rediacc-cli-term --machine server --command "docker logs webapp"

# Restart container
rediacc-cli-term --machine server --command "docker restart webapp"

# Interactive Docker management
rediacc-cli-term --machine server
$ docker ps
$ docker stats
$ docker-compose -f /repos/webapp/docker-compose.yml restart
```

### 3. System Monitoring

```bash
# Check disk usage
rediacc-cli-term --machine server --command "df -h"

# Monitor processes
rediacc-cli-term --machine server --command "htop"

# Check memory
rediacc-cli-term --machine server --command "free -h"

# View system logs
rediacc-cli-term --machine server --command "journalctl -n 100"
```

### 4. Database Operations

```bash
# Database backup
rediacc-cli-term --machine db-server --repo postgres \
  --command "pg_dump mydb > /backups/mydb_$(date +%Y%m%d).sql"

# Run SQL query
rediacc-cli-term --machine db-server --repo postgres \
  --command "psql -d mydb -c 'SELECT COUNT(*) FROM users;'"

# Interactive database session
rediacc-cli-term --machine db-server --repo postgres
$ psql -d mydb
```

## Environment Variables

When accessing a repository, these environment variables are available:

```bash
REPO_NAME          # Current repository name
REPO_PATH          # Repository root path
MACHINE_NAME       # Current machine name
TEAM_NAME          # Current team name
DOCKER_CONTAINER   # Container name (if applicable)
```

Example usage:
```bash
rediacc-cli-term --machine server --repo webapp
$ echo $REPO_NAME      # webapp
$ echo $REPO_PATH      # /app
$ cd $REPO_PATH
```

## Helper Functions

Repository environments include helper functions:

```bash
# Container management
rdocker ps          # List containers for this repo
rdocker logs        # View container logs
rdocker restart     # Restart container

# Log viewing
rlogs               # View application logs
rlogs -f            # Follow logs in real-time

# Quick navigation
repo-root           # cd to repository root
repo-logs           # cd to logs directory
```

## Advanced Usage

### 1. Script Execution

```bash
# Run local script on remote
cat script.sh | rediacc-cli-term --machine server --repo app \
  --command "bash -s"

# Execute remote script
rediacc-cli-term --machine server --repo app \
  --command "/scripts/deploy.sh production"
```

### 2. Pipe Commands

```bash
# Pipe local data to remote
echo "SELECT * FROM users;" | rediacc-cli-term --machine db --repo postgres \
  --command "psql -d mydb"

# Pipe remote output locally
rediacc-cli-term --machine server --repo logs \
  --command "cat access.log" | grep ERROR > local-errors.log
```

### 3. Development Mode

Use `--dev` flag for relaxed SSH host checking (development only):

```bash
# Useful for dynamic/temporary environments
rediacc-cli-term --machine dev-temp --repo test --dev
```

## Security Considerations

### 1. SSH Key Management
- Private keys stored encrypted in team vault
- Temporary key files created with mode 600
- Keys deleted after session ends

### 2. Access Control
- Requires valid Rediacc token
- Respects team and machine permissions
- All sessions logged for audit

### 3. Command Restrictions
- Repository access limited to container
- Machine access limited to universal user
- No sudo/root access

## Troubleshooting

### Connection Issues

#### Host Key Verification Failed
```
Error: Host key verification failed
```
**Solution**: 
- Contact admin to verify host key change
- Use `--dev` flag for development environments only

#### Connection Refused
```
Error: ssh: connect to host X.X.X.X port 22: Connection refused
```
**Solution**:
- Verify machine is online
- Check SSH service is running
- Verify firewall rules

#### Permission Denied
```
Error: Permission denied (publickey)
```
**Solution**:
- Ensure team vault has correct SSH key
- Verify machine access permissions

### Repository Issues

#### Container Not Found
```
Error: Container 'webapp' not found
```
**Solution**:
- Verify repository exists on machine
- Check if container is running
- Try machine-level access to investigate

#### Working Directory Error
```
Error: Cannot cd to /app
```
**Solution**:
- Repository may not be properly initialized
- Container may be in error state
- Check container logs

### Debug Mode

Enable verbose SSH output:

```bash
# Set verbose mode
export REDIACC_VERBOSE=1

# Run command with debug output
rediacc-cli-term --machine server --repo app
```

## Best Practices

### 1. Use Commands for Automation

```bash
# Good: Automated, repeatable
rediacc-cli-term --machine prod --repo api \
  --command "npm run health-check"

# Avoid: Interactive for automation
rediacc-cli-term --machine prod --repo api
# Then manually running commands
```

### 2. Log Important Operations

```bash
# Create audit trail
LOGFILE="operations-$(date +%Y%m%d).log"
echo "$(date): Restarting production API" >> $LOGFILE
rediacc-cli-term --machine prod --repo api \
  --command "docker restart api" | tee -a $LOGFILE
```

### 3. Use Repository Access When Possible

```bash
# Good: Repository-scoped access
rediacc-cli-term --machine server --repo webapp \
  --command "npm install"

# Avoid: Machine-level for repo operations
rediacc-cli-term --machine server \
  --command "cd /repos/webapp && npm install"
```

### 4. Handle Errors Gracefully

```bash
# Check command success
if rediacc-cli-term --machine prod --repo api \
     --command "npm test" > test-results.log 2>&1; then
  echo "Tests passed"
else
  echo "Tests failed, see test-results.log"
  exit 1
fi
```

## Integration Examples

### CI/CD Pipeline

```yaml
# GitHub Actions example
- name: Deploy and Verify
  run: |
    # Run deployment
    ./rediacc-cli-term --machine prod --repo api \
      --command "/scripts/deploy.sh"
    
    # Verify deployment
    ./rediacc-cli-term --machine prod --repo api \
      --command "curl -f http://localhost:3000/health" || exit 1
```

### Monitoring Script

```bash
#!/bin/bash
# Monitor multiple services

SERVICES=("api" "webapp" "worker")
for service in "${SERVICES[@]}"; do
  echo "Checking $service..."
  if rediacc-cli-term --machine prod --repo $service \
       --command "curl -s http://localhost/health" | grep -q "ok"; then
    echo "✓ $service is healthy"
  else
    echo "✗ $service is down!"
    # Send alert
  fi
done
```