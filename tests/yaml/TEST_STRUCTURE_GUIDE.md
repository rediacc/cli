# Rediacc Test Structure Guide

## Database Entity Hierarchy with Test Files and Stored Procedures

```
Company (Root Level)
├── 01000_company.yaml → [protected_CreateNewCompany]
│   ├── Required: CompanyName, ActivationCode (6 chars), CompanyVaultDefaults (JSON), SubscriptionPlan
│   ├── 01050_company_settings.yaml → [public_UpdateCompanyBlockUserRequests, public_UpdateCompanyVault, public_UpdateCompanyVaults]
│   ├── 01080_company_export.yaml → [public_ExportCompanyData, public_ImportCompanyData]
│   ├── 01100_company_vault_get.yaml → [public_GetCompanyVault, public_GetCompanyVaults]
│   ├── 01200_company_list_entities.yaml → [public_GetCompanyPermissionGroups, public_GetCompanyRegions, public_GetCompanyTeams, public_GetCompanyUsers]
│   └── 01300_company_dashboard.yaml → [public_GetCompanyDashboardJson, public_GetCompanyDataGraphJson]
│
├── 02000_permissions.yaml → [public_CreatePermissionGroup, public_CreatePermissionInGroup]
│   ├── Permission Groups (belongs to Company)
│   ├── 02100_permission_details.yaml → [public_GetPermissionGroupDetails]
│   └── 02200_permission_delete.yaml → [public_DeletePermissionFromGroup, public_DeletePermissionGroup]
│
├── 03000_users.yaml → [protected_CreateNewUser, protected_ActivateUserAccount]
│   ├── User (belongs to Company, requires PermissionsId)
│   ├── 03050_user_auth.yaml → [protected_UpdateUserPassword, public_UpdateUser2FA]
│   ├── 03080_user_sessions.yaml → [protected_CreateAuthenticationRequest, public_DeleteUserRequest, public_GetUserRequests]
│   ├── 03100_user_update.yaml → [public_UpdateUserEmail, public_UpdateUserToDeactivated, public_UpdateUserAssignedPermissions]
│   └── 03200_user_info.yaml → [public_GetUserCompany, public_GetRequestAuthenticationStatus]
│
├── 04000_teams.yaml → [public_CreateTeam, public_UpdateTeamName, public_UpdateTeamVault]
│   ├── Team (belongs to Company, requires TeamVault)
│   ├── 04100_participation.yaml → [public_CreateTeamMembership, public_DeleteUserFromTeam, public_GetTeamMembers]
│   ├── 04200_repositories.yaml → [public_CreateRepository, public_UpdateRepositoryName, public_UpdateRepositoryVault, public_DeleteRepository, public_GetTeamRepositories]
│   ├── 04300_storage.yaml → [public_CreateStorage, public_UpdateStorageName, public_UpdateStorageVault, public_DeleteStorage, public_GetTeamStorages]
│   ├── 04400_schedules.yaml → [public_CreateSchedule, public_UpdateScheduleName, public_UpdateScheduleVault, public_DeleteSchedule, public_GetTeamSchedules]
│   ├── 04500_distributed_storage.yaml → [public_CreateDistributedStorageCluster, public_ListDistributedStorageClusters, public_AddMachinesToDistributedStorage]
│   │   └── Additional: [public_RemoveMachinesFromDistributedStorage, public_UpdateDistributedStorageClusterVault, public_UpdateDistributedStorageClusterStatus, public_DeleteDistributedStorageCluster]
│   ├── 04600_team_machines.yaml → [public_GetTeamMachines]
│   ├── 04700_team_queue.yaml → [public_GetTeamQueueItems]
│   └── 04800_team_delete.yaml → [public_DeleteTeam]
│
├── 05000_regions.yaml → [public_CreateRegion, public_UpdateRegionName, public_UpdateRegionVault, public_DeleteRegion]
│   └── 05100_region_list.yaml → [public_GetCompanyRegions, public_GetRegionBridges]
│
├── 06000_bridges.yaml → [public_CreateBridge, public_UpdateBridgeName, public_UpdateBridgeVault, public_DeleteBridge]
│   ├── 06100_bridge_auth.yaml → [public_ResetBridgeAuthorization, internal_GetGlobalBridgeTokens]
│   └── 06200_bridge_list.yaml → [public_GetRegionBridges]
│
├── 07000_machines.yaml → [public_CreateMachine, public_UpdateMachineName, public_UpdateMachineVault, public_DeleteMachine]
│   ├── 07100_machine_status.yaml → [public_UpdateMachineStatus, public_UpdateMachineAssignedBridge]
│   └── 07200_machine_list.yaml → [public_GetTeamMachines]
│
├── 08000_queue.yaml → [public_CreateQueueItem, public_UpdateQueueItemResponse, public_UpdateQueueItemToCompleted]
│   ├── Requires: Bridge, Team, User; Optional: Machine; Priority: 1-5
│   ├── 08100_queue_operations.yaml → [public_CancelQueueItem, public_DeleteQueueItem, public_RetryFailedQueueItem]
│   ├── 08200_queue_bridge.yaml → [public_GetQueueItemsNext]
│   └── 08300_queue_trace.yaml → [public_GetQueueItemTrace]
│
├── 09000_audit.yaml → [public_GetAuditLogs, public_GetEntityAuditTrace, public_GetEntityHistory]
│   └── Audit trail for all entity operations
│
├── 09500_authentication.yaml → [public_GetRequestAuthenticationStatus, public_PrivilegeAuthenticationRequest]
│   └── Session management and 2FA privilege elevation
│
├── 10000_vault_management.yaml → [private_ManageEncryptedVault]
│   └── Core vault encryption/decryption operations
│
├── 11000_internal_operations.yaml → [internal_HealthCheck, internal_ExportCompanyDataByName, internal_ImportCompanyDataByName]
│   └── Internal system operations
│
└── 12000_lookup_data.yaml → [public_GetLookupData, public_GetSubscriptionList]
    └── Reference data and subscriptions

99999_cleanup.yaml → [public_DeleteUserRequest, Logout operations]
```

## Critical Stored Procedure Requirements

### Company Creation
- **CompanyVaultDefaults**: REQUIRED JSON parameter (not optional!)
- **ActivationCode**: Must be exactly 6 characters
- **BlockUserRequests**: Can prevent new user self-registration
- **Data Export/Import**: Full company data portability

### Permission Groups  
- Must create group (`CreatePermissionGroup`) BEFORE adding permissions
- `CreatePermissionInGroup` executes with elevated 'dbo' privileges

### User & Authentication
- **2FA Setup**: `UpdateUser2FA` with secret generation and verification
- **Session Management**: `CreateAuthenticationRequest` with token expiration
- **Privilege Elevation**: `PrivilegeAuthenticationRequest` for sensitive operations

### Infrastructure Order
1. Region → Bridge → Machine (strict dependency chain)
2. Team required before Machine
3. Bridge links to Region AND creating User
4. Bridge tokens managed globally via `internal_GetGlobalBridgeTokens`

### Storage Systems
- **Basic Storage**: Team-level storage with vault
- **Schedules**: Automation schedules with encrypted configs
- **Distributed Storage**: Ceph cluster management
  - Requires: ClusterName, PoolName, PoolPgNum, PoolSize, OsdDevice
  - Machine assignment via `AddMachinesToDistributedStorage`

### Queue Items
- Can run without Machine (bridge-only mode)
- Priority: 1-5 (1 is highest, default 4)

### Audit System
- **Audit Logs**: `GetAuditLogs` with date range and entity filters
- **Entity Trace**: `GetEntityAuditTrace` for specific entity history
- All operations automatically logged

## Current Test Issues and Fixes

### Issue: Permission Test Failing
**Current**: `04000_permission.yaml` tries to add permission to non-existent group
**Fix**: Create group first:
```yaml
tests:
  - name: "create_permission_group"  # ADD THIS FIRST
    command: ["permission", "create-group", "${permission_group}"]
  - name: "add_permission_get_teams"
    command: ["permission", "add", "${permission_group}", "GetCompanyTeams"]
```

### Issue: Wrong Execution Order  
**Current**: Permissions (04000) created after users (03000)
**Fix**: Rename files:
- `04000_permission.yaml` → `02000_permissions.yaml`
- `03000_user.yaml` → `03000_users.yaml` (keep as is)
- `03100_user_password.yaml` → `03050_user_auth.yaml`
- `02000_team.yaml` → `04000_teams.yaml`
- `01000_company.yaml` → `01000_company.yaml` (keep as is)

### Issue: Missing Core Entities and Operations
**Current**: Many core entities and operations have no test coverage
**Fix**: Add these required test files:

**Infrastructure:**
- `05000_regions.yaml` → Create, update, delete regions
- `06000_bridges.yaml` → Create, update, delete bridges
- `07000_machines.yaml` → Create, update, delete machines

**Team Resources:**
- `04200_repositories.yaml` → Repository management
- `04300_storage.yaml` → Storage management
- `04400_schedules.yaml` → Schedule automation
- `04500_distributed_storage.yaml` → Ceph cluster management

**Operations & Monitoring:**
- `08100_queue_operations.yaml` → Cancel, retry queue items
- `09000_audit.yaml` → Audit logs and entity history
- `10000_vault_management.yaml` → Vault operations
- `11000_internal_operations.yaml` → Health checks
- `12000_lookup_data.yaml` → Reference data

**List/Get Operations:**
- `01200_company_list_entities.yaml` → List all company entities
- `04600_team_machines.yaml` → Get team machines
- `04700_team_queue.yaml` → Get team queue items

## Quick Migration Commands

```bash
# Fix file order with thousand-based numbering
cd cli/tests/yaml/community
mv 01000_company.yaml 01000_company.yaml  # Keep as is
mv 04000_permission.yaml 02000_permissions.yaml
mv 03000_user.yaml 03000_users.yaml  # Keep as is
mv 03100_user_password.yaml 03050_user_auth.yaml
mv 02000_team.yaml 04000_teams.yaml
mv 09999_logout.yaml 99999_cleanup.yaml

# Fix permission test (add group creation)
sed -i '1a\  - name: "create_permission_group"\n    command: ["permission", "create-group", "${permission_group}"]\n    expect:\n      success: true\n' 02000_permissions.yaml
```

## Tier Structure

### Community (Basic)
- 01000-04999: Core entities in dependency order
  - 01000s: Company setup and configuration
  - 02000s: Permissions and access control
  - 03000s: Users and authentication
  - 04000s: Teams and team resources
- 05000-07999: Infrastructure
  - 05000s: Regions
  - 06000s: Bridges
  - 07000s: Machines
- 08000-09999: Operations and monitoring
  - 08000s: Queue operations
  - 09000s: Audit and authentication

### Advanced/Premium/Elite (Overrides only)
- Only override specific test parameters
- Example: `01000_company.yaml` with `plan: "ADVANCED"`

## Complete Database Table Coverage

### Core Tables
1. **Company** - Full CRUD + vault operations (01xxx series)
2. **User** - Full CRUD + auth/2FA (03xxx series)
3. **Permissions** - Groups and individual permissions (02xxx series)
4. **Team** - Full CRUD + vault operations (04xxx series)
5. **Participation** - Team membership (04100)
6. **Region** - Full CRUD + listing (05xxx series)
7. **Bridge** - Full CRUD + auth tokens (06xxx series)
8. **Machine** - Full CRUD + status updates (07xxx series)
9. **Queue** - Full lifecycle + bridge operations (08xxx series)
10. **Repository** - Full CRUD + hierarchy support (04200)
11. **Storage** - Full CRUD + vault updates (04300)
12. **Schedule** - Full CRUD + automation (04400)
13. **Request** - Authentication sessions (03xxx series)
14. **Audit** - Logs and entity traces (09000)
15. **Vault** - Encrypted storage (10000)

### Special Tables
- **[web].[udt_Request]** - User-defined table type for request auth
- **[license].[Plans]** - Subscription plans (referenced in company creation)
- **[license].[Subscriptions]** - Active subscriptions (12000)
- **[license].[Prices]** - Plan pricing
- **[license].[Resources]** - Plan resource limits

### Total Stored Procedures: 123
- **Protected (5)**: Company/User creation, authentication
- **Public (110)**: All entity operations
- **Internal (8)**: System operations, health checks