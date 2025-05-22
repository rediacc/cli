package schedules

import (
	"github.com/spf13/cobra"
)

// SchedulesCmd represents the schedules command
var SchedulesCmd = &cobra.Command{
	Use:   "schedules",
	Short: "Schedule management commands",
	Long: `Schedule management commands for Rediacc CLI.
	
This command group includes schedule creation, deletion, listing, and updates.`,
}

func init() {
	// TODO: Add subcommands
}
