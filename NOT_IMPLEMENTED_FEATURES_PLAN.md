# Deep Investigation & Implementation Plan for "Not Implemented" Features

## Investigation Summary

After thorough analysis of the codebase, I've identified the infrastructure available and dependencies for each not implemented feature:

---

## **TIER 1: Ready to Implement (High Impact, Low Complexity)**

### 1. **Toggle Preview** - F3 ✅ **INFRASTRUCTURE EXISTS**
**Status**: File browser already has complete preview functionality!
- **Infrastructure**: Full preview system exists in `file_browser.py`
- **Components**: `show_preview()`, `hide_preview()`, `preview_visible` flag
- **Complexity**: **TRIVIAL** - Just connect main window to file browser
- **Impact**: **HIGH** - Users frequently need file preview
- **Implementation**: 2-3 lines of code

### 2. **View Mode Switching** - Ctrl+1, Ctrl+2, Ctrl+3 ✅ **INFRASTRUCTURE EXISTS**
**Status**: Dual-pane system supports all three modes!
- **Infrastructure**: `paned_window` with local/remote frames
- **Components**: `local_frame`, `remote_frame`, `transfer_frame` can be hidden/shown
- **Complexity**: **LOW** - Hide/show pane widgets
- **Impact**: **HIGH** - Essential for focused work
- **Implementation**: ~20 lines of code

---

## **TIER 2: Moderate Implementation (Medium Impact, Medium Complexity)**

### 3. **Connect/Disconnect** - Ctrl+Shift+C/D ⚠️ **PARTIALLY EXISTS**
**Status**: Connection logic exists but menu actions are stubs
- **Infrastructure**: `RepositoryConnection` class, `ssh_connection` management
- **Components**: `connect()`, `disconnect_remote()` methods exist in file browser
- **Complexity**: **MEDIUM** - Wire menu to existing functionality + validation
- **Impact**: **MEDIUM** - Alternative to automatic connection
- **Implementation**: ~30 lines + validation logic

### 4. **Rename Selected** 🔧 **NEEDS IMPLEMENTATION**
**Status**: No infrastructure, but straightforward
- **Infrastructure**: SSH command execution exists
- **Components**: Context menu entry exists, just needs implementation
- **Complexity**: **MEDIUM** - Dialog + SSH `mv` command + refresh
- **Impact**: **MEDIUM** - Useful file management feature
- **Implementation**: ~50 lines (dialog + command execution)

---

## **TIER 3: Complex Implementation (Variable Impact, High Complexity)**

### 5. **Paste Files** 🚧 **NEEDS CUT/COPY INFRASTRUCTURE**
**Status**: Cut/copy operations exist but incomplete
- **Infrastructure**: `clipboard_files` property exists
- **Components**: `cut_selected()`, `copy_selected()` partially implemented
- **Complexity**: **HIGH** - Cross-pane operations, file transfer logic
- **Impact**: **LOW-MEDIUM** - Nice-to-have workflow enhancement
- **Implementation**: ~100+ lines (complete clipboard system)

### 6. **Plugin Logs Viewing** 🔧 **NEEDS PLUGIN SYSTEM INTEGRATION**
**Status**: Plugin system exists but logs not exposed
- **Infrastructure**: Plugin management system exists
- **Components**: Docker container access needed
- **Complexity**: **HIGH** - Docker integration, log streaming
- **Impact**: **LOW** - Developer/debugging feature
- **Implementation**: ~150+ lines (Docker logs integration)

---

## **TIER 4: Intentionally Not Implemented (Security/Safety)**

### 7. **Delete Selected** 🚫 **INTENTIONALLY DISABLED**
**Status**: Disabled for safety reasons
- **Reasoning**: Prevents accidental data loss
- **Recommendation**: **KEEP DISABLED** or implement with extensive safeguards
- **Alternative**: Use terminal for delete operations

---

## **Recommended Implementation Priority**

### **Phase 1 - Quick Wins (1-2 hours)**
1. **Toggle Preview** - Connect `main.py` to `file_browser.toggle_preview()`
2. **View Mode Switching** - Hide/show panes based on mode

### **Phase 2 - UI Enhancements (2-4 hours)**
3. **Connect/Disconnect** - Wire menu to existing connection logic
4. **Rename Selected** - Add rename dialog + SSH command

### **Phase 3 - Pro Features (Future)**
5. **Paste Files** - Complete clipboard system
6. **Plugin Logs** - Docker logs integration

---

## **Code Impact Assessment**

- **Files to modify**: `main.py` (menu actions), `file_browser.py` (new features)
- **New dependencies**: None required
- **Backward compatibility**: 100% - all additions
- **Testing requirements**: Manual UI testing for each feature

---

## **Current Feature Status List**

### **Fixed:**
- ✅ **Quick Command** (`show_quick_command`) - Ctrl+K *(Recently implemented)*

### **Main Window Features:**
1. **Toggle Preview** (`toggle_preview`) - F3
   - Shows "Not Implemented" message
   - Function: File preview pane toggle

2. **View Mode Switching** (`set_view_mode`) - Ctrl+1, Ctrl+2, Ctrl+3
   - Local Files Only, Remote Files Only, Split View
   - Shows "View mode: {mode} - Not Implemented"

3. **Connect** (`connect`) - Ctrl+Shift+C
   - Connection menu action
   - Shows "Not Implemented"

4. **Disconnect** (`disconnect`) - Ctrl+Shift+D
   - Connection menu action
   - Shows "Not Implemented"

### **File Browser Features:**
5. **Delete Selected Files** (`delete_selected`)
   - Shows "Delete functionality is not implemented for safety reasons"
   - **Intentionally not implemented** for security

6. **Paste Files** (`paste_files`)
   - Shows "Paste functionality is not implemented yet"
   - Related to cut/copy operations

7. **Rename Selected** (`rename_selected`)
   - Shows "Rename functionality is not implemented yet"
   - File/folder renaming

### **Plugin Features:**
8. **Plugin Logs Viewing** (`view_plugin_logs`)
   - Shows "Plugin logs viewing is not yet implemented"
   - Container log viewing functionality

---

## **Summary**

The investigation reveals that **most infrastructure already exists** for the "Not Implemented" features! The main issues are:

1. **Preview & View Modes**: Complete infrastructure exists, just need to connect main window to file browser
2. **Connect/Disconnect**: Connection logic exists, just need to wire menu actions
3. **Rename**: Straightforward implementation using existing SSH execution
4. **Paste/Plugin Logs**: More complex but not critical

**Recommendation**: Start with **Phase 1** (Toggle Preview + View Modes) as these provide immediate user value with minimal effort, then proceed based on user feedback and priorities.

---

## **Implementation Notes**

### Files Involved:
- `/home/muhammed/monorepo/cli/src/cli/gui/main.py` - Main window menu actions
- `/home/muhammed/monorepo/cli/src/cli/gui/file_browser.py` - File browser functionality

### Key Infrastructure Components:
- Preview system: `show_preview()`, `hide_preview()`, `preview_visible`
- Paned window: `paned_window`, `local_frame`, `remote_frame`, `transfer_frame`
- SSH execution: `execute_remote_command()`, `RepositoryConnection`
- Connection management: `ssh_connection`, `connect()`, `disconnect_remote()`

### Testing Strategy:
- Manual UI testing for each implemented feature
- Verify keyboard shortcuts work correctly
- Test with different connection states
- Validate error handling and edge cases