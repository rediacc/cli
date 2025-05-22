package auth

import (
	"crypto/sha256"
	"fmt"

	"github.com/spf13/cobra"
	"github.com/rediacc/cli/internal/api"
	"github.com/rediacc/cli/internal/config"
	"github.com/rediacc/cli/internal/format"
)

// userCmd represents the user command
var userCmd = &cobra.Command{
	Use:   "user",
	Short: "User management commands",
	Long:  "User management commands for authentication and user operations",
}

// userCreateCmd creates a new user
var userCreateCmd = &cobra.Command{
	Use:   "create",
	Short: "Create a new user",
	Long:  "Create a new user in the system",
	RunE:  runUserCreate,
}

// userListCmd lists users
var userListCmd = &cobra.Command{
	Use:   "list",
	Short: "List users",
	Long:  "List all users in the system",
	RunE:  runUserList,
}

// userInfoCmd shows user information
var userInfoCmd = &cobra.Command{
	Use:   "info <email>",
	Short: "Show user information",
	Long:  "Display detailed information about a specific user",
	Args:  cobra.ExactArgs(1),
	RunE:  runUserInfo,
}

// userActivateCmd activates a user
var userActivateCmd = &cobra.Command{
	Use:   "activate <email>",
	Short: "Activate a user",
	Long:  "Activate a user account",
	Args:  cobra.ExactArgs(1),
	RunE:  runUserActivate,
}

// userDeactivateCmd deactivates a user
var userDeactivateCmd = &cobra.Command{
	Use:   "deactivate <email>",
	Short: "Deactivate a user",
	Long:  "Deactivate a user account",
	Args:  cobra.ExactArgs(1),
	RunE:  runUserDeactivate,
}

// userUpdatePasswordCmd updates user password
var userUpdatePasswordCmd = &cobra.Command{
	Use:   "update-password <email>",
	Short: "Update user password",
	Long:  "Update the password for a user",
	Args:  cobra.ExactArgs(1),
	RunE:  runUserUpdatePassword,
}

func runUserCreate(cmd *cobra.Command, args []string) error {
	email, _ := cmd.Flags().GetString("email")
	password, _ := cmd.Flags().GetString("password")

	if email == "" || password == "" {
		return fmt.Errorf("email and password are required")
	}

	cfg := config.Get()
	client := api.NewClient(cfg.Server.URL)

	// CreateNewUser expects NewUserEmail and NewUserHash parameters
	// Middleware adds "prm" prefix automatically: NewUserEmail -> @prmNewUserEmail
	// Hash the password and format as hex string for binary parameter
	hash := sha256.Sum256([]byte(password))
	hexHash := fmt.Sprintf("0x%x", hash[:])
	
	params := map[string]interface{}{
		"NewUserEmail": email,
		"NewUserHash":  hexHash,
	}

	// CreateNewUser is public but requires current user password for validation
	adminEmail := cfg.Auth.Email
	
	fmt.Printf("Enter password for %s to create user: ", adminEmail)
	var adminPassword string
	fmt.Scanln(&adminPassword)
	
	response, err := client.ExecuteAuthProcedure("CreateNewUser", params, adminEmail, adminPassword)
	if err != nil {
		return fmt.Errorf("failed to create user: %w", err)
	}

	if response.Success {
		format.PrintSuccess("✓ User %s created successfully", email)
		return nil
	}

	return fmt.Errorf("failed to create user: %s", response.Error)
}

func runUserList(cmd *cobra.Command, args []string) error {
	cfg := config.Get()
	client := api.NewClient(cfg.Server.URL)

	response, err := client.ExecuteStoredProcedure("GetAllCompanyUsers", map[string]interface{}{})
	if err != nil {
		return fmt.Errorf("failed to list users: %w", err)
	}

	if response.Success {
		if len(response.Data) == 0 {
			fmt.Println("No users found")
			return nil
		}
		return format.Print(response.Data)
	}

	return fmt.Errorf("failed to list users: %s", response.Error)
}

func runUserInfo(cmd *cobra.Command, args []string) error {
	email := args[0]

	cfg := config.Get()
	client := api.NewClient(cfg.Server.URL)

	params := map[string]interface{}{
		"email": email,
	}

	response, err := client.ExecuteStoredProcedure("GetAllCompanyUsers", params)
	if err != nil {
		return fmt.Errorf("failed to get user info: %w", err)
	}

	if response.Success {
		if len(response.Data) == 0 {
			return fmt.Errorf("user %s not found", email)
		}
		return format.Print(response.Data[0])
	}

	return fmt.Errorf("failed to get user info: %s", response.Error)
}

func runUserActivate(cmd *cobra.Command, args []string) error {
	email := args[0]

	cfg := config.Get()
	client := api.NewClient(cfg.Server.URL)

	// EnableUserAccount expects userEmail parameter
	params := map[string]interface{}{
		"userEmail": email,
	}

	response, err := client.ExecuteStoredProcedure("EnableUserAccount", params)
	if err != nil {
		return fmt.Errorf("failed to activate user: %w", err)
	}

	if response.Success {
		format.PrintSuccess("✓ User %s activated successfully", email)
		return nil
	}

	return fmt.Errorf("failed to activate user: %s", response.Error)
}

func runUserDeactivate(cmd *cobra.Command, args []string) error {
	email := args[0]

	cfg := config.Get()
	client := api.NewClient(cfg.Server.URL)

	// DisableUserAccount expects userEmail parameter
	params := map[string]interface{}{
		"userEmail": email,
	}

	response, err := client.ExecuteStoredProcedure("DisableUserAccount", params)
	if err != nil {
		return fmt.Errorf("failed to deactivate user: %w", err)
	}

	if response.Success {
		format.PrintSuccess("✓ User %s deactivated successfully", email)
		return nil
	}

	return fmt.Errorf("failed to deactivate user: %s", response.Error)
}

func runUserUpdatePassword(cmd *cobra.Command, args []string) error {
	email := args[0]
	newPassword, _ := cmd.Flags().GetString("password")

	if newPassword == "" {
		return fmt.Errorf("new password is required")
	}

	cfg := config.Get()
	client := api.NewClient(cfg.Server.URL)

	// UpdateUserPassword expects userNewPass parameter (from tutorial)
	params := map[string]interface{}{
		"userNewPass": newPassword,
	}

	response, err := client.ExecuteStoredProcedure("UpdateUserPassword", params)
	if err != nil {
		return fmt.Errorf("failed to update password: %w", err)
	}

	if response.Success {
		format.PrintSuccess("✓ Password updated successfully for user %s", email)
		return format.Print(response.Data)
	}

	return fmt.Errorf("failed to update password: %s", response.Error)
}

func init() {
	// User create command flags
	userCreateCmd.Flags().StringP("email", "e", "", "User email address")
	userCreateCmd.Flags().StringP("password", "p", "", "User password")
	userCreateCmd.MarkFlagRequired("email")
	userCreateCmd.MarkFlagRequired("password")

	// User update password command flags
	userUpdatePasswordCmd.Flags().StringP("password", "p", "", "New password")
	userUpdatePasswordCmd.MarkFlagRequired("password")

	// Add subcommands to user command
	userCmd.AddCommand(userCreateCmd)
	userCmd.AddCommand(userListCmd)
	userCmd.AddCommand(userInfoCmd)
	userCmd.AddCommand(userActivateCmd)
	userCmd.AddCommand(userDeactivateCmd)
	userCmd.AddCommand(userUpdatePasswordCmd)

	// Add user command to auth command
	AuthCmd.AddCommand(userCmd)
}