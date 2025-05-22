package auth

import (
	"github.com/spf13/cobra"
)

// AuthCmd represents the auth command
var AuthCmd = &cobra.Command{
	Use:   "auth",
	Short: "Authentication and user management commands",
	Long: `Authentication and user management commands for Rediacc CLI.
	
This command group includes login, logout, user management, and 2FA operations.`,
}

func init() {
	// TODO: Add subcommands
	// AuthCmd.AddCommand(loginCmd)
	// AuthCmd.AddCommand(logoutCmd)
	// AuthCmd.AddCommand(userCmd)
	// AuthCmd.AddCommand(twofaCmd)
}
