package company

import (
	"fmt"

	"github.com/spf13/cobra"
	"github.com/rediacc/cli/internal/api"
	"github.com/rediacc/cli/internal/config"
	"github.com/rediacc/cli/internal/format"
)

// CompanyCmd represents the company command
var CompanyCmd = &cobra.Command{
	Use:   "company",
	Short: "Company management commands",
	Long: `Company management commands for Rediacc CLI.
	
This command group includes company creation, information retrieval,
user management, resource limits, vault operations, and subscription details.`,
}

// createCmd creates a new company
var createCmd = &cobra.Command{
	Use:   "create",
	Short: "Create a new company",
	Long:  "Create a new company with specified name and admin email",
	RunE:  runCreate,
}

// infoCmd shows company information
var infoCmd = &cobra.Command{
	Use:   "info",
	Short: "Show company information",
	Long:  "Display detailed information about the current company",
	RunE:  runInfo,
}

// usersCmd manages company users
var usersCmd = &cobra.Command{
	Use:   "users",
	Short: "Company users management",
	Long:  "Commands for managing company users",
}

// usersListCmd lists company users
var usersListCmd = &cobra.Command{
	Use:   "list",
	Short: "List company users",
	Long:  "List all users in the current company",
	RunE:  runUsersList,
}

// limitsCmd shows resource limits
var limitsCmd = &cobra.Command{
	Use:   "limits",
	Short: "Show resource limits",
	Long:  "Display the current company's resource limits",
	RunE:  runLimits,
}

// vaultCmd manages company vault
var vaultCmd = &cobra.Command{
	Use:   "vault",
	Short: "Company vault management",
	Long:  "Commands for managing company secure data vault",
}

// vaultGetCmd retrieves vault data
var vaultGetCmd = &cobra.Command{
	Use:   "get",
	Short: "Get vault data",
	Long:  "Retrieve company secure data from vault",
	RunE:  runVaultGet,
}

// vaultUpdateCmd updates vault data
var vaultUpdateCmd = &cobra.Command{
	Use:   "update",
	Short: "Update vault data",
	Long:  "Update company secure data in vault",
	RunE:  runVaultUpdate,
}

// subscriptionCmd shows subscription info
var subscriptionCmd = &cobra.Command{
	Use:   "subscription",
	Short: "Show subscription information",
	Long:  "Display the current company's subscription details",
	RunE:  runSubscription,
}

func runCreate(cmd *cobra.Command, args []string) error {
	name, _ := cmd.Flags().GetString("name")
	adminEmail, _ := cmd.Flags().GetString("admin-email")
	adminPassword, _ := cmd.Flags().GetString("admin-password")

	if name == "" || adminEmail == "" || adminPassword == "" {
		return fmt.Errorf("company name, admin email, and admin password are required")
	}

	cfg := config.Get()
	client := api.NewClient(cfg.Server.URL)

	// CreateNewCompany expects companyName parameter (from tutorial)
	params := map[string]interface{}{
		"companyName": name,
	}

	// Use auth procedure since it's protected and needs email/password
	response, err := client.ExecuteAuthProcedure("CreateNewCompany", params, adminEmail, adminPassword)
	if err != nil {
		return fmt.Errorf("failed to create company: %w", err)
	}

	if response.Success {
		format.PrintSuccess("✓ Company '%s' created successfully", name)
		format.PrintSuccess("✓ Admin user '%s' created", adminEmail)
		format.PrintInfo("Check email for activation code to activate the account")
		return nil
	}

	return fmt.Errorf("failed to create company: %s", response.Error)
}

func runInfo(cmd *cobra.Command, args []string) error {
	cfg := config.Get()
	client := api.NewClient(cfg.Server.URL)

	response, err := client.ExecuteStoredProcedure("GetUserCompanyDetails", map[string]interface{}{})
	if err != nil {
		return fmt.Errorf("failed to get company info: %w", err)
	}

	if response.Success {
		if len(response.Data) == 0 {
			fmt.Println("No company information found")
			return nil
		}
		return format.Print(response.Data[0])
	}

	return fmt.Errorf("failed to get company info: %s", response.Error)
}

func runUsersList(cmd *cobra.Command, args []string) error {
	cfg := config.Get()
	client := api.NewClient(cfg.Server.URL)

	response, err := client.ExecuteStoredProcedure("GetAllCompanyUsers", map[string]interface{}{})
	if err != nil {
		return fmt.Errorf("failed to list company users: %w", err)
	}

	if response.Success {
		if len(response.Data) == 0 {
			fmt.Println("No users found")
			return nil
		}
		return format.Print(response.Data)
	}

	return fmt.Errorf("failed to list company users: %s", response.Error)
}

func runLimits(cmd *cobra.Command, args []string) error {
	cfg := config.Get()
	client := api.NewClient(cfg.Server.URL)

	response, err := client.ExecuteStoredProcedure("GetCompanyResourceLimits", map[string]interface{}{})
	if err != nil {
		return fmt.Errorf("failed to get resource limits: %w", err)
	}

	if response.Success {
		if len(response.Data) == 0 {
			fmt.Println("No resource limits found")
			return nil
		}
		return format.Print(response.Data[0])
	}

	return fmt.Errorf("failed to get resource limits: %s", response.Error)
}

func runVaultGet(cmd *cobra.Command, args []string) error {
	cfg := config.Get()
	client := api.NewClient(cfg.Server.URL)

	response, err := client.ExecuteStoredProcedure("GetCompanySecureData", map[string]interface{}{})
	if err != nil {
		return fmt.Errorf("failed to get vault data: %w", err)
	}

	if response.Success {
		if len(response.Data) == 0 {
			fmt.Println("No vault data found")
			return nil
		}
		return format.Print(response.Data[0])
	}

	return fmt.Errorf("failed to get vault data: %s", response.Error)
}

func runVaultUpdate(cmd *cobra.Command, args []string) error {
	data, _ := cmd.Flags().GetString("data")

	if data == "" {
		return fmt.Errorf("vault data is required")
	}

	cfg := config.Get()
	client := api.NewClient(cfg.Server.URL)

	params := map[string]interface{}{
		"data": data,
	}

	response, err := client.ExecuteStoredProcedure("UpdateCompanySecureData", params)
	if err != nil {
		return fmt.Errorf("failed to update vault data: %w", err)
	}

	if response.Success {
		format.PrintSuccess("✓ Company vault data updated successfully")
		return nil
	}

	return fmt.Errorf("failed to update vault data: %s", response.Error)
}

func runSubscription(cmd *cobra.Command, args []string) error {
	cfg := config.Get()
	client := api.NewClient(cfg.Server.URL)

	response, err := client.ExecuteStoredProcedure("GetSubscriptionDetails", map[string]interface{}{})
	if err != nil {
		return fmt.Errorf("failed to get subscription details: %w", err)
	}

	if response.Success {
		if len(response.Data) == 0 {
			fmt.Println("No subscription information found")
			return nil
		}
		return format.Print(response.Data[0])
	}

	return fmt.Errorf("failed to get subscription details: %s", response.Error)
}

func init() {
	// Create command flags
	createCmd.Flags().StringP("name", "n", "", "Company name")
	createCmd.Flags().StringP("admin-email", "e", "", "Admin email address")
	createCmd.Flags().StringP("admin-password", "p", "", "Admin password")
	createCmd.MarkFlagRequired("name")
	createCmd.MarkFlagRequired("admin-email")
	createCmd.MarkFlagRequired("admin-password")

	// Vault update command flags
	vaultUpdateCmd.Flags().StringP("data", "d", "", "Vault data (JSON format)")
	vaultUpdateCmd.MarkFlagRequired("data")

	// Add subcommands to users command
	usersCmd.AddCommand(usersListCmd)

	// Add subcommands to vault command
	vaultCmd.AddCommand(vaultGetCmd)
	vaultCmd.AddCommand(vaultUpdateCmd)

	// Add subcommands to company command
	CompanyCmd.AddCommand(createCmd)
	CompanyCmd.AddCommand(infoCmd)
	CompanyCmd.AddCommand(usersCmd)
	CompanyCmd.AddCommand(limitsCmd)
	CompanyCmd.AddCommand(vaultCmd)
	CompanyCmd.AddCommand(subscriptionCmd)
}
