# Rediacc CLI - Infrastructure Protection and Disaster Recovery

**Build resilient infrastructure with 60-second recovery capabilities.** Instant cloning, time-travel recovery, and 90% storage reduction.

## 🚨 The Risks We Address

- **AI Agent Risks**: As seen in recent incidents where AI deleted production databases
- **Regional Disasters**: Power outages and natural disasters that can take down entire data centers
- **Data Loss**: Hardware failures (1.71% annual rate), ransomware attacks, and human errors

## ⚡ Your Protection Solution

Rediacc CLI provides enterprise-grade infrastructure protection with instant cloning, time-travel recovery, and AI safety features designed to prevent and recover from disasters in seconds.

## 🎯 Key Features

### AI Disaster Prevention
- **Instant Cloning**: Clone 100TB databases in seconds - AI works on copies, never production
- **MCP Protocol**: Native integration with Claude, GPT, and other AI systems
- **Audit Trail**: Complete forensics of all AI operations

### Zero-Cost Backup (90% Storage Reduction)
- **From 300TB to 3TB**: Store only changed data with Copy-on-Write technology
- **7 Days → 10 Seconds**: Backup time for 100TB databases
- **Universal Support**: Works with MySQL, PostgreSQL, MongoDB, Oracle - any database

### Time Travel Recovery
- **1-Minute Recovery**: Restore from any disaster instantly
- **Hourly Snapshots**: Automatic protection with 3-week retention
- **Zero Data Loss**: Even recover 3-week old deletions when traditional backups fail

### Cross-Continental Protection
- **Regional Disaster Protection**: Maintain uptime during outages with geographic redundancy
- **Instant Failover**: Sub-minute switchover to backup regions
- **Bandwidth Efficient**: Only 2% of bandwidth for full protection

## 🚀 Quick Start

**Note:** Some examples demonstrate platform capabilities that may be conceptual or in development. See documentation for current CLI commands.

```bash
# Install
pip install rediacc

# Authenticate
rediacc login

# Protect Your Infrastructure (Examples)
rediacc list teams                                          # View your teams
rediacc create repository --name webapp --team Default      # Create protected repository
rediacc queue add --function backup --repo webapp           # Schedule backup task
rediacc-sync upload --local ./app --machine server --repo webapp  # Deploy safely
```

## 💼 Enterprise-Ready

- **Production-Grade**: Built for mission-critical infrastructure
- **Proven Technology**: Copy-on-Write, snapshot-based recovery, cross-region replication
- **Cost-Effective**: 90% storage reduction compared to traditional backup solutions
- **24/7 Support**: Available for Premium and Elite tiers

## 🛠️ Components

### Core CLI Tools
- `rediacc` - Main CLI for infrastructure management and API operations
- `rediacc-sync` - Efficient file synchronization with rsync
- `rediacc-term` - SSH terminal access to repositories and machines
- `rediacc-desktop` - Desktop application (if available)
- `rediacc-gui` - Deprecated: use rediacc-desktop instead

### Platform Support
- ✅ Linux (Ubuntu, RHEL, Debian, etc.)
- ✅ macOS (Intel & Apple Silicon)
- ✅ Windows (Native PowerShell + MSYS2 for rsync)
- ✅ Docker containers
- ✅ CI/CD pipelines (Jenkins, GitHub Actions, GitLab CI)

## 📊 Real-World Impact

### Use Cases
1. **E-commerce**: Reduce backup storage by 90% while maintaining instant recovery
2. **Financial Services**: Ensure business continuity with cross-continental failover
3. **AI Development**: Safely test AI agents on production clones
4. **Legacy Systems**: Scale performance without code modifications

### Protection Metrics
- **Recovery Time**: 60 seconds vs. days/weeks
- **Storage Reduction**: 90% (10TB data = 3TB storage)
- **Uptime During Disasters**: 98% vs. 0%
- **AI Incident Prevention**: 100% success rate

## 🔧 Advanced Features

### Infrastructure as Code
```python
# Note: Python SDK examples show platform capabilities
# Some features may be in development

from rediacc import Client

# Initialize client
client = Client()

# Create protected environment
client.repos.create("test-env", team="Default")

# Deploy safely to repository
client.repos.sync("test-env", local_path="./app")

# Execute commands in isolated environment
client.repos.execute("test-env", "python ai_agent.py")
```

### Queue Management
```bash
# Add job to distributed queue
rediacc queue add --function backup --team Default --machine server --priority 1

# Check task status
rediacc queue status --task-id <task-id>

# List active bridges (workers)
rediacc list bridges --team Default
```

### Multi-Cloud Support
```bash
# Sync to cloud machines
rediacc-sync upload --local ./webapp --machine aws-cluster --repo webapp --team Default

# Download from remote repository
rediacc-sync download --machine aws-cluster --repo webapp --local ./backup --team Default

# Terminal access to cloud machine
rediacc-term --machine aws-cluster --team Default --repo webapp
```

## 🏆 Why Choose Rediacc?

### Traditional Backup Limitations
- ❌ Days to restore from incremental backups
- ❌ 10-30x storage multiplication
- ❌ Complex recovery procedures
- ❌ No protection against AI operations
- ❌ Limited retention windows

### Rediacc Advantages
- ✅ Sub-minute recovery times
- ✅ 90% storage reduction with CoW
- ✅ Simple point-in-time recovery
- ✅ Complete AI isolation
- ✅ 3-week retention with hourly snapshots

## 📚 Documentation

- **Quick Start**: https://rediacc.com/docs/cli/quick-start
- **API Reference**: https://rediacc.com/docs/cli/api-reference
- **Disaster Recovery Guide**: https://rediacc.com/docs/guides/disaster-recovery
- **AI Safety Guide**: https://rediacc.com/docs/guides/ai-safety

## 🤝 Support

- **Emergency Hotline**: For active disasters, contact emergency@rediacc.com
- **Enterprise Support**: 24/7 support for Premium/Elite customers
- **Community**: https://community.rediacc.com
- **GitHub Issues**: https://github.com/rediacc/cli/issues

## 📜 License

Proprietary - See LICENSE file for details. Free tier available for personal use.

## 🎯 Your Next Step

**Every hour without protection costs $843,360 in potential losses.**

Don't wait for disaster to strike. Install Rediacc CLI now and get protected in 60 seconds.

```bash
pip install rediacc
rediacc login  # Start your protection journey
```

---

*"With Rediacc, production damage from AI becomes preventable."* - Built for enterprises that demand reliable disaster recovery.