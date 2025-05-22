package teams

import (
	"github.com/spf13/cobra"
)

// TeamsCmd represents the teams command
var TeamsCmd = &cobra.Command{
	Use:   "teams",
	Short: "Team management commands",
	Long: `Team management commands for Rediacc CLI.
	
This command group includes team creation, deletion, renaming,
vault operations, and member management.`,
}

func init() {
	// TODO: Add subcommands
}
