package permissions

import (
	"github.com/spf13/cobra"
)

// PermissionsCmd represents the permissions command
var PermissionsCmd = &cobra.Command{
	Use:   "permissions",
	Short: "Permission management commands",
	Long: `Permission management commands for Rediacc CLI.
	
This command group includes permission group management, adding/removing permissions,
and assigning users to permission groups.`,
}

func init() {
	// TODO: Add subcommands
}
