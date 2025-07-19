# Rediacc CLI Help System Completion Plan

## Overview
This document outlines the remaining work needed to complete the help documentation for all endpoints in the rediacc-cli.json configuration file.

## Completed Work
✅ Implemented dynamic help generation system in rediacc-cli.py
✅ Added help structure to configuration file
✅ Documented key endpoints with comprehensive help text

## Remaining Endpoints to Document

### 1. List Commands (High Priority)
- [ ] **lookup-data** - API endpoint: GetLookupData
  - Purpose: Provides dropdown/selection data for UI components
  - Parameters: context (optional)
  - Use case: Getting valid values for creating resources

- [ ] **user-company** - API endpoint: GetUserCompany
  - Purpose: Shows which company the current user belongs to
  - No parameters
  - Use case: Verifying logged-in user's company context

- [ ] **entity-history** - API endpoint: GetEntityHistory
  - Purpose: Shows change history for a specific entity
  - Parameters: entity_type, credential, max_records
  - Use case: Auditing changes to specific resources

- [ ] **team-repositories** - API endpoint: GetTeamRepositories
  - Purpose: Lists all repositories owned by a team
  - Parameters: team (required)
  - Use case: Managing team's code repositories

- [ ] **team-schedules** - API endpoint: GetTeamSchedules
  - Purpose: Lists scheduled tasks for a team
  - Parameters: team (required)
  - Use case: Managing cron jobs and scheduled tasks

- [ ] **team-storages** - API endpoint: GetTeamStorages
  - Purpose: Lists storage resources for a team
  - Parameters: team (required)
  - Use case: Managing external storage connections

### 2. Update Commands (Medium Priority)
- [ ] **region** - API endpoint: UpdateRegionName
  - Purpose: Rename a region
  - Parameters: name, new_name

- [ ] **bridge** - API endpoint: UpdateBridgeName
  - Purpose: Rename a bridge
  - Parameters: region, name, new_name

- [ ] **repository** - API endpoint: UpdateRepositoryName
  - Purpose: Rename a repository
  - Parameters: team, name, new_name

- [ ] **repository-vault** - API endpoint: UpdateRepositoryVault
  - Purpose: Update repository configuration
  - Parameters: team, name, vault data

- [ ] **storage** - API endpoint: UpdateStorageName
  - Purpose: Rename a storage resource
  - Parameters: team, name, new_name

- [ ] **storage-vault** - API endpoint: UpdateStorageVault
  - Purpose: Update storage configuration
  - Parameters: team, name, vault data

- [ ] **schedule** - API endpoint: UpdateScheduleName
  - Purpose: Rename a scheduled task
  - Parameters: team, name, new_name

- [ ] **schedule-vault** - API endpoint: UpdateScheduleVault
  - Purpose: Update schedule configuration
  - Parameters: team, name, vault data

### 3. Vault Commands (Medium Priority)
- [ ] **set** - Special handler for setting vault data
  - Purpose: Update vault for any resource type
  - Parameters: resource_type, name, file/data

- [ ] **set-password** - Set master password
  - Purpose: Configure encryption password
  - No parameters (prompts interactively)

- [ ] **clear-password** - Clear master password
  - Purpose: Remove stored encryption password
  - No parameters

- [ ] **status** - Show vault encryption status
  - Purpose: Check if master password is configured
  - No parameters

### 4. Permission Commands (Low Priority)
- [ ] **create-group** - API endpoint: CreatePermissionGroup
  - Purpose: Create a new permission group
  - Parameters: name

- [ ] **delete-group** - API endpoint: DeletePermissionGroup
  - Purpose: Remove a permission group
  - Parameters: name, --force

- [ ] **add** - API endpoint: CreatePermissionInGroup
  - Purpose: Add permission to a group
  - Parameters: group, name

- [ ] **remove** - API endpoint: DeletePermissionFromGroup
  - Purpose: Remove permission from a group
  - Parameters: group, name, --force

- [ ] **assign** - API endpoint: UpdateUserAssignedPermissions
  - Purpose: Assign permission group to user
  - Parameters: email, group

- [ ] **list-groups** - API endpoint: GetCompanyPermissionGroups
  - Purpose: List all permission groups
  - No parameters

- [ ] **list-group** - API endpoint: GetPermissionGroupDetails
  - Purpose: Show permissions in a group
  - Parameters: name

### 5. Company Commands (Low Priority)
- [ ] **block-user-requests** - API endpoint: UpdateCompanyBlockUserRequests
  - Purpose: Enable/disable new user registrations
  - Parameters: block (true/false)

- [ ] **update-vault** - API endpoint: UpdateCompanyVault
  - Purpose: Update company-wide vault
  - Parameters: vault data

- [ ] **get-vaults** - API endpoint: GetCompanyVaults
  - Purpose: Retrieve all company vaults
  - No parameters

- [ ] **update-vaults** - API endpoint: UpdateCompanyVaults
  - Purpose: Bulk update company vaults
  - Parameters: vaults data

### 6. Distributed Storage Commands (Low Priority)
All distributed storage commands need help text:
- [ ] create-cluster
- [ ] delete-cluster
- [ ] get-cluster
- [ ] list-clusters
- [ ] add-machines
- [ ] remove-machines
- [ ] update-status
- [ ] update-vault

### 7. Other Commands (Low Priority)
- [ ] **bridge reset-auth** - API endpoint: ResetBridgeAuthorization
  - Purpose: Generate new bridge credentials
  - Parameters: name, --force

- [ ] **team-member add** - API endpoint: CreateTeamMembership
  - Purpose: Add user to team
  - Parameters: team, email

- [ ] **team-member remove** - API endpoint: DeleteUserFromTeam
  - Purpose: Remove user from team
  - Parameters: team, email, --force

- [ ] **auth status** - API endpoint: GetRequestAuthenticationStatus
  - Purpose: Check authentication request status
  - Parameters: request_hash

- [ ] **auth privilege** - API endpoint: PrivilegeAuthenticationRequest
  - Purpose: Grant special privileges to auth request
  - Parameters: request_hash, privilege

- [ ] **audit trace** - API endpoint: GetEntityAuditTrace
  - Purpose: Get detailed audit trail for entity
  - Parameters: entity_type, credential, max_records

- [ ] **inspect repository** - API endpoint: GetTeamRepositories
  - Purpose: Get detailed info about a repository
  - Parameters: team, name

## Help Text Template

For each endpoint, use this template:

```json
"help": {
  "description": "Brief one-line description",
  "details": "Detailed explanation of what this command does and when to use it",
  "parameters": {
    "param_name": {
      "description": "What this parameter does",
      "required": true/false,
      "default": "default_value",
      "example": "example_value"
    }
  },
  "examples": [
    {
      "command": "rediacc-cli command resource param1 param2",
      "description": "What this example does"
    }
  ],
  "notes": "Important considerations, warnings, or permission requirements"
}
```

## Implementation Steps

1. **Phase 1**: Complete high-priority list commands
   - These are frequently used for viewing resources
   - Focus on clear parameter documentation

2. **Phase 2**: Complete update commands
   - Important for resource management
   - Include warnings about impacts

3. **Phase 3**: Complete vault and permission commands
   - Critical for security configuration
   - Include detailed examples

4. **Phase 4**: Complete remaining commands
   - Distributed storage (advanced feature)
   - Company management
   - Authentication helpers

## Testing Checklist

For each completed endpoint:
- [ ] Test with `rediacc-cli <command>` (shows available resources)
- [ ] Test with `rediacc-cli <command> <resource> --help` (shows detailed help)
- [ ] Verify parameter descriptions are accurate
- [ ] Ensure examples actually work
- [ ] Check that notes include important warnings

## Notes

- All help text should be user-focused, not implementation-focused
- Include practical examples that demonstrate real use cases
- Mention subscription tier requirements where applicable
- Note which commands require special permissions
- Keep descriptions concise but informative
- Use consistent formatting and terminology

## Priority Justification

- **High Priority**: Commands used daily for viewing resources
- **Medium Priority**: Commands for resource management and configuration
- **Low Priority**: Advanced features and administrative commands