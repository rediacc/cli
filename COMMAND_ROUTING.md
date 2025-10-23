# Command Routing Documentation

This document explains how commands flow through the Rediacc CLI architecture, from user input to execution.

## Overview

The Rediacc CLI uses a **dual entry point system**:

1. **PyPI package entry points** - Installed commands like `rediacc`, `rediacc-sync`, `rediacc-term`
2. **Direct Python execution** - For development: `python3 src/cli/commands/cli_main.py`

All commands follow a consistent routing pattern through the main CLI dispatcher or execute as standalone modules.

---

## Entry Points

Defined in `pyproject.toml`:

```toml
[project.scripts]
rediacc = "cli.commands.cli_main:main"
rediacc-sync = "cli.commands.sync_main:main"
rediacc-term = "cli.commands.term_main:main"
rediacc-vscode = "cli.commands.vscode_main:main"
rediacc-plugin = "cli.commands.plugin_main:main"
rediacc-workflow = "cli.commands.workflow_main:main"
rediacc-desktop = "cli.gui.main:main"
rediacc-gui = "cli.gui.main:main"
```

**Note**: All commands work via both routes:
- `rediacc sync` (via dispatcher)
- `rediacc-sync` (direct entry point)

---

## Command Types & Routing

### 1. Standalone Commands (Dispatcher-Routed)

**Commands**: `sync`, `term`, `plugin`, `vscode`, `compose`, `license`, `protocol`, `workflow`, `desktop`, `gui`

**Characteristics**:
- Self-contained modules with their own `main()` function
- Handle authentication, argparse, and execution independently
- Routed through the command dispatcher

**Flow**:
```
User executes: rediacc sync --help
         ↓
cli_main.py:main()
         ↓
handle_special_flags()
  - Checks if --help appears BEFORE command
  - If yes → show global help and exit
  - If no → continue
         ↓
Command dispatcher
  - Checks if 'sync' in command_modules dict
  - command_modules = {
      'sync': ('cli.commands.sync_main', 'Sync'),
      ...
    }
         ↓
Import module: cli.commands.sync_main
         ↓
Adjust sys.argv: ['rediacc-sync', '--help']
  - Removes 'sync' from argv[1]
         ↓
Call sync_main.main()
         ↓
Execute sync-specific argparse and logic
```

**Code Location**:
```python
# cli_main.py - Command dispatcher
command_modules = {
    'sync': ('cli.commands.sync_main', 'Sync'),
    'term': ('cli.commands.term_main', 'Term'),
    'plugin': ('cli.commands.plugin_main', 'Plugin'),
    'vscode': ('cli.commands.vscode_main', 'VSCode'),
    'compose': ('cli.commands.compose_main', 'Compose'),
    'license': ('cli.commands.license_main', 'License'),
    'protocol': ('cli.commands.protocol_main', 'Protocol'),
    'workflow': ('cli.commands.workflow_main', 'Workflow'),
    'desktop': ('cli.gui.main', 'Desktop'),
    'gui': ('cli.gui.main', 'GUI'),
}

if command in command_modules:
    module_path, cmd_name = command_modules[command]
    module = __import__(module_path, fromlist=['main'])
    sys.argv = [sys.argv[0]] + sys.argv[2:]  # Remove subcommand
    return module.main()
```

---

### 2. Management Commands (API Wrappers)

**Commands**: `create`, `list`, `update`, `rm`, `vault`, `permission`, `user`, `team-member`, `bridge`, `queue`, `company`, `audit`, `inspect`, `distributed-storage`, `auth`

**Characteristics**:
- Configuration-driven from `cli-config.json` API_ENDPOINTS
- Generic wrapper around API calls
- All follow the same pattern: `rediacc <command> <resource> [options]`

**Flow**:
```
User executes: rediacc list teams
         ↓
cli_main.py:main()
         ↓
setup_parser()
  - Reads cli-config.json
  - Dynamically builds argparse for each endpoint
  - Creates subparsers for each resource type
         ↓
Parse arguments:
  args.command = 'list'
  args.resource = 'teams'
         ↓
Authentication check
  - Verify token exists
  - Skip for specific commands like 'create company'
         ↓
CommandHandler.generic_command()
  - Maps command + resource to API endpoint
  - Calls client.token_request()
         ↓
API client sends request to backend
         ↓
Format and display response
```

**Config Example** (`cli-config.json`):
```json
{
  "API_ENDPOINTS": {
    "list": {
      "teams": {"endpoint": "GetCompanyTeams", "parameters": {}},
      "users": {"endpoint": "GetCompanyUsers", "parameters": {}},
      ...
    }
  }
}
```

---

### 3. Simple Commands (Hardcoded)

**Commands**: `login`, `logout`, `setup`

**Characteristics**:
- Small, focused commands with minimal logic
- Hardcoded in `cli_main.py` main flow
- Direct method calls, no complex routing

**Flow**:
```
User executes: rediacc login
         ↓
cli_main.py:main()
         ↓
setup_parser() creates login subparser
         ↓
Parse arguments: args.command = 'login'
         ↓
Direct routing:
  if args.command == 'login':
      return handler.login(args)
         ↓
CommandHandler.login()
  - Prompt for credentials
  - Call authentication API
  - Save token to config
```

**Special Case - setup**:
```
User executes: rediacc setup
         ↓
cli_main.py:main()
         ↓
Direct handler
  - No API call needed
  - Just display setup instructions
```

---

## Special Flags Handling

Global flags are processed **BEFORE** command routing to ensure consistent behavior.

**Flags**: `--version`, `--help`, no arguments

**Flow**:
```
cli_main.py:main()
         ↓
handle_special_flags()
         ↓
Check 1: --version in sys.argv?
  → YES: show_version() → exit
         ↓
Check 2: --help or -h in sys.argv (without command)?
  → YES: show_help() → exit
  → Logic: Only show global help if no command before --help
         ↓
Check 3: len(sys.argv) == 1 (no arguments)?
  → YES: show_help() → exit
         ↓
Return False → continue to command routing
```

**Example Behaviors**:
```bash
rediacc --help              # Global help (no command)
rediacc sync --help         # Sync-specific help (has command)
rediacc --version           # Version info
rediacc                     # Global help (no args)
```

---

## Workflow Refactoring Example

### Before Refactoring (Hybrid Architecture)

**Problem**: Workflow was tightly coupled to `cli_main.py`

```
User: rediacc workflow repo-create --team=X --machine=Y
         ↓
cli_main.py:main()
         ↓
setup_parser() builds argparse IN cli_main.py
  - Reads workflow config from cli-config.json
  - Creates workflow subparsers
         ↓
Parse: args.command = 'workflow', args.workflow_type = 'repo-create'
         ↓
Special workflow handling
  - Massive if/elif chain for each workflow type
  - if args.workflow_type == 'repo-create':
         ↓
handler.workflow_repo_create(args)
  - CommandHandler delegate method
         ↓
WorkflowHandler(command_handler)
  - Requires CommandHandler instance
  - Tightly coupled dependencies
         ↓
workflow.workflow_repo_create(args)
```

**Issues**:
- ❌ Can't run workflow standalone
- ❌ Argparse setup in wrong place
- ❌ Tight coupling to CommandHandler
- ❌ Inconsistent with other commands

### After Refactoring (Standalone Architecture)

**Solution**: Workflow is now a standalone module

```
User: rediacc workflow repo-create --team=X --machine=Y
         ↓
cli_main.py:main()
         ↓
handle_special_flags()
         ↓
Command dispatcher
  'workflow': ('cli.commands.workflow_main', 'Workflow')
         ↓
Import: cli.commands.workflow_main
         ↓
Adjust sys.argv: ['rediacc-workflow', 'repo-create', '--team=X', ...]
         ↓
Call: workflow_main.main()
         ↓
setup_workflow_parser() IN workflow_main.py
  - Reads cli-config.json directly
  - Builds complete argparse
         ↓
Parse: args.workflow_type = 'repo-create'
         ↓
Initialize standalone WorkflowHandler:
  handler = WorkflowHandler(
      config_manager=config_manager,
      client_instance=api_client,
      output_format=args.output
  )
         ↓
Route to method:
  handler.workflow_repo_create(args)
```

**Benefits**:
- ✅ Consistent with sync, term, plugin
- ✅ Can run standalone: `rediacc-workflow` or `python3 workflow_main.py`
- ✅ Self-contained: handles own argparse, auth, API calls
- ✅ Cleaner cli_main.py (removed 50+ lines)

---

## Code Location Reference

| Component | File | Function/Section | Description |
|-----------|------|------------------|-------------|
| Main entry point | `cli_main.py` | `main()` | Main dispatcher logic |
| Special flags handler | `cli_main.py` | `handle_special_flags()` | --version, --help, no-args |
| Command dispatcher | `cli_main.py` | `command_modules` dict | Routes to standalone modules |
| Argparse setup | `cli_main.py` | `setup_parser()` | Management command parsers |
| Help generator | `core/help_generator.py` | `generate_help_data()` | Dynamic help system |
| Help formatter | `core/format_help.py` | `format_comprehensive_help()` | Docker-style help display |
| Workflow standalone | `workflow_main.py` | `main()` | Workflow entry point and parser |
| Sync standalone | `sync_main.py` | `main()` | Sync command implementation |
| Term standalone | `term_main.py` | `main()` | Terminal command implementation |

---

## Developer Guide

### Adding a New Standalone Command

**Steps**:

1. **Create module**: `src/cli/commands/<command>_main.py`
   ```python
   #!/usr/bin/env python3
   import argparse
   import sys
   from cli.core.config import TokenManager, setup_logging, get_logger

   def main():
       parser = argparse.ArgumentParser(
           prog='rediacc <command>',
           description='Your command description'
       )
       parser.add_argument('--token', '-t', help='Authentication token')
       parser.add_argument('--verbose', '-v', action='store_true')

       args = parser.parse_args()

       # Your logic here
       return 0

   if __name__ == '__main__':
       sys.exit(main())
   ```

2. **Add to dispatcher** in `cli_main.py`:
   ```python
   # Look for command_modules dict in main()
   command_modules = {
       ...
       '<command>': ('cli.commands.<command>_main', '<Command>'),
   }
   ```

3. **Add entry point** in `pyproject.toml`:
   ```toml
   [project.scripts]
   rediacc-<command> = "cli.commands.<command>_main:main"
   ```

4. **Add to help generator** in `core/help_generator.py`:
   ```python
   def get_dedicated_commands():
       modules = {
           ...
           '<command>': 'Description of command',
       }
   ```

5. **Reinstall package**:
   ```bash
   ./dev.sh
   ```

### Adding a New Management Command

**Steps**:

1. **Add to cli-config.json**:
   ```json
   {
     "API_ENDPOINTS": {
       "<command>": {
         "<resource>": {
           "endpoint": "APIEndpointName",
           "parameters": {
             "param1": {"type": "str", "help": "Description"}
           }
         }
       }
     }
   }
   ```

2. **No code changes needed** - argparse is auto-generated!

3. **Help is automatic** - added to `help_generator.py` generically

---

## Troubleshooting

### Command not found

**Symptom**: `Error: Not authenticated. Please login first.` for a command that should exist

**Cause**: Command not in dispatcher dict

**Solution**: Add to `command_modules` dict in `cli_main.py`

---

### Help not working for subcommand

**Symptom**: `rediacc sync --help` shows global help instead of sync help

**Cause**: `handle_special_flags()` catching --help too early

**Solution**: This is fixed - `handle_special_flags()` now checks if a command exists before --help

---

### Command shows in help but doesn't work

**Symptom**: Command appears in `rediacc --help` but fails when executed

**Cause**: Command in help generator but not properly routed

**Solution**:
- For standalone: Add to dispatcher
- For management: Add to cli-config.json
- Check `help_generator.py` matches actual implementation

---

### Workflow (or other command) executed twice

**Symptom**: Command logic runs twice

**Cause**: Command in both dispatcher AND special handling in main()

**Solution**: Remove from special handling, keep only in dispatcher

---

## Architecture Decisions

### Why Dispatcher Pattern?

**Benefits**:
- ✅ Consistent Docker-style UX (`docker run`, `git commit`)
- ✅ Both `rediacc sync` and `rediacc-sync` work
- ✅ Clean separation of concerns
- ✅ Easy to add new commands
- ✅ Testable in isolation

**Alternative considered**: Argparse subparsers only
- ❌ Can't have standalone entry points
- ❌ cli_main.py becomes massive
- ❌ Harder to test individual commands

### Why Config-Driven Management Commands?

**Benefits**:
- ✅ No code duplication
- ✅ Easy to add new API endpoints
- ✅ Consistent parameter handling
- ✅ Automatic help generation

**Trade-off**: Less flexibility for special cases

### Why Special Flags Handler?

**Benefits**:
- ✅ Consistent --version/--help across all entry points
- ✅ Works before command routing
- ✅ Single source of truth (DRY principle)

---

## Summary

**Command Flow**:
```
User Input
    ↓
cli_main.py:main()
    ↓
Special Flags? → show_version/show_help → EXIT
    ↓
Standalone Command? → Dispatcher → <command>_main.py:main()
    ↓
Management Command? → setup_parser() → CommandHandler.generic_command()
    ↓
Simple Command? → CommandHandler.<method>()
    ↓
Execute & Return
```

**Three Architectures**:
1. **Standalone**: Self-contained modules (sync, term, workflow, etc.)
2. **Management**: Config-driven API wrappers (create, list, update, etc.)
3. **Simple**: Hardcoded helpers (login, logout, setup)

All work together seamlessly through the unified `cli_main.py` entry point.
