package auth

import (
	"errors"
	"fmt"

	"github.com/spf13/cobra"
	"github.com/rediacc/cli/internal/api"
	"github.com/rediacc/cli/internal/config"
)

// AuthCmd represents the auth command
var AuthCmd = &cobra.Command{
	Use:   "auth",
	Short: "Authentication and user management commands",
	Long: `Authentication and user management commands for Rediacc CLI.
	
This command group includes login, logout, user management, and 2FA operations.`,
}

// loginCmd represents the login command
var loginCmd = &cobra.Command{
	Use:   "login",
	Short: "Login to Rediacc",
	Long:  "Authenticate with Rediacc using email and password",
	RunE:  runLogin,
}

// logoutCmd represents the logout command
var logoutCmd = &cobra.Command{
	Use:   "logout",
	Short: "Logout from Rediacc",
	Long:  "Logout from the current Rediacc session",
	RunE:  runLogout,
}

// statusCmd represents the status command
var statusCmd = &cobra.Command{
	Use:   "status",
	Short: "Show authentication status",
	Long:  "Display current authentication status and user information",
	RunE:  runStatus,
}

func runLogin(cmd *cobra.Command, args []string) error {
	email, _ := cmd.Flags().GetString("email")
	password, _ := cmd.Flags().GetString("password")

	// Validate input
	if email == "" {
		return errors.New("email is required")
	}
	if password == "" {
		return errors.New("password is required")
	}

	// Create API client
	cfg := config.Get()
	client := api.NewClient(cfg.Server.URL)

	// Attempt login
	fmt.Printf("Logging in as %s...\n", email)
	response, err := client.Login(email, password)
	if err != nil {
		return fmt.Errorf("login failed: %w", err)
	}

	if response.Success {
		fmt.Printf("✓ Successfully logged in as %s\n", email)
		return nil
	}

	return fmt.Errorf("login failed: %s", response.Error)
}

func runLogout(cmd *cobra.Command, args []string) error {
	cfg := config.Get()
	if cfg.Auth.Email == "" {
		return fmt.Errorf("not logged in")
	}

	client := api.NewClient(cfg.Server.URL)
	
	fmt.Printf("Logging out %s...\n", cfg.Auth.Email)
	if err := client.Logout(); err != nil {
		return fmt.Errorf("logout failed: %w", err)
	}

	fmt.Println("✓ Successfully logged out")
	return nil
}

func runStatus(cmd *cobra.Command, args []string) error {
	cfg := config.Get()
	
	if cfg.Auth.Email == "" {
		fmt.Println("Status: Not logged in")
		return nil
	}

	fmt.Printf("Status: Logged in as %s\n", cfg.Auth.Email)
	fmt.Printf("Server: %s\n", cfg.Server.URL)
	
	if cfg.Auth.RequestCredential != "" {
		fmt.Println("Session: Active")
		fmt.Printf("Request Credential: %s\n", cfg.Auth.RequestCredential)
	} else {
		fmt.Println("Session: No token")
	}

	return nil
}

func init() {
	// Add login command flags
	loginCmd.Flags().StringP("email", "e", "", "Email address")
	loginCmd.Flags().StringP("password", "p", "", "Password")
	loginCmd.MarkFlagRequired("email")
	loginCmd.MarkFlagRequired("password")

	// Add subcommands
	AuthCmd.AddCommand(loginCmd)
	AuthCmd.AddCommand(logoutCmd)
	AuthCmd.AddCommand(statusCmd)
}
