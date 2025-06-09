# Queue Trace Command Update Summary

## Changes Made

### 1. **CLI Updates** (`cli/rediacc-cli`)

#### Added `queue trace` Command Configuration:
- **Endpoint**: `GetQueueItemTrace` 
- **Parameters**: Takes a `taskId` parameter
- **Command syntax**: `rediacc-cli queue trace <task-id>`

#### Implementation Details:
- Added command configuration in `CMD_CONFIG` (lines 581-586)
- Added argument definition in `ARG_DEFS` (lines 905-907)
- Updated command handler to support trace output formatting (line 1635)
- Added custom formatting logic for trace command (lines 1642-1643)
- Implemented `format_queue_trace` method (lines 1908-2058)

#### Trace Output Structure:
The trace command returns 4 result sets that are formatted as:

**Text Output**:
1. **QUEUE ITEM DETAILS** - Comprehensive queue item information including:
   - Task ID, Status, Health Status
   - Timestamps (Created, Assigned, Last Heartbeat)
   - Priority (if Premium/Elite subscription)
   - Time calculations (processing duration, total duration)
   - Resource hierarchy (Company → Team → Region → Bridge → Machine)
   - Stale item warnings

2. **REQUEST VAULT** - Shows the original request data (if present)

3. **RESPONSE VAULT** - Shows any response data (if present)

4. **PROCESSING TIMELINE** - Shows the history of status changes

**JSON Output**:
```json
{
  "queue_item": { /* all queue item details */ },
  "request_vault": { /* vault type, version, content */ },
  "response_vault": { /* vault type, version, content */ },
  "timeline": [ /* array of timeline events */ ]
}
```

### 2. **Test Script Updates** (`cli/test.sh`)

#### Added Comprehensive Queue Trace Tests:
1. **Basic trace functionality** - Tests tracing an existing queue item
2. **Vault information verification** - Checks if request/response vaults are displayed
3. **Timeline verification** - Ensures processing timeline is shown
4. **JSON output validation** - Verifies JSON structure and validity
5. **Trace after update-response** - Tests that response vault updates are reflected
6. **Trace after completion** - Verifies completed status is shown
7. **Error handling tests**:
   - Invalid task ID (non-existent UUID)
   - Malformed task ID (not a valid UUID format)
8. **State-specific testing** - Creates a specific queue item to test tracing in PENDING state
9. **Cleanup handling** - Ensures trace test items are cleaned up

## Usage Examples

### Basic Usage:
```bash
# Trace a queue item by its task ID
rediacc-cli queue trace 7f5040b0-a0c7-4a08-9176-bdc386bd9bd4

# Trace with JSON output
rediacc-cli --output json queue trace 7f5040b0-a0c7-4a08-9176-bdc386bd9bd4
```

### Typical Workflow:
```bash
# 1. Create a queue item
rediacc-cli create queue-item MyTeam MyMachine MyBridge --vault '{"function": "test"}'
# Output: Task ID: 7f5040b0-a0c7-4a08-9176-bdc386bd9bd4

# 2. Trace the queue item to see its details
rediacc-cli queue trace 7f5040b0-a0c7-4a08-9176-bdc386bd9bd4

# 3. Update the response
rediacc-cli queue update-response 7f5040b0-a0c7-4a08-9176-bdc386bd9bd4 --vault '{"status": "processing"}'

# 4. Trace again to see the updated response vault
rediacc-cli queue trace 7f5040b0-a0c7-4a08-9176-bdc386bd9bd4

# 5. Complete the queue item
rediacc-cli queue complete 7f5040b0-a0c7-4a08-9176-bdc386bd9bd4 --vault '{"result": "success"}'

# 6. Final trace to see completed status and timeline
rediacc-cli queue trace 7f5040b0-a0c7-4a08-9176-bdc386bd9bd4
```

## Benefits

1. **Complete Visibility** - Users can see all details about a queue item in one command
2. **Debugging Support** - Shows vault contents and timeline for troubleshooting
3. **Status Tracking** - Easy to track the lifecycle of a queue item
4. **Subscription-Aware** - Respects subscription tiers (e.g., priority only shown for Premium/Elite)
5. **Multiple Formats** - Supports both human-readable text and machine-readable JSON output

## Testing

The test script (`test.sh`) has been updated to thoroughly test the new functionality, including:
- Success cases for different queue item states
- Error handling for invalid inputs
- JSON output validation
- Integration with other queue commands (update-response, complete)