# Backend Configuration Notes

## Company Creation Issue

The `create company` command is currently failing with an SQL error:
```
Implicit conversion from data type sql_variant to nvarchar is not allowed
```

### Root Cause

The middleware expects the `SYSTEM_COMPANY_VAULT_DEFAULTS` environment variable to be set when creating a company. This variable should contain JSON configuration for the default company vault settings.

From `middleware/Service/StoredProcedureController.Protected.cs`:
```csharp
var companyVaultDefaults = Environment.GetEnvironmentVariable("SYSTEM_COMPANY_VAULT_DEFAULTS")
    ?? throw new InvalidOperationException("Company vault defaults not configured...");
```

### Solution

To fix this issue, the middleware needs to have the environment variable set:
```bash
export SYSTEM_COMPANY_VAULT_DEFAULTS='{"key": "value"}'  # Replace with actual defaults
```

### Workaround for Testing

Until the backend is properly configured, you can:

1. Use the `00000_existing_company_test.yaml` test with existing credentials:
   ```bash
   export REDIACC_TEST_EMAIL="your-email@company.com"
   export REDIACC_TEST_PASSWORD="your-password"
   ./run_tests.py basic/00000_existing_company_test.yaml
   ```

2. Or manually create a company using the console web interface, which handles the vault defaults properly.

### Test Flow

The correct flow for company creation is:
1. Create company (generates activation code)
2. Activate user account with activation code
3. Login

In development mode, the activation code is hardcoded to "111111".