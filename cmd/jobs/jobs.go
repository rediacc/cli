package jobs

import (
	"github.com/spf13/cobra"
)

// JobsCmd represents the jobs command
var JobsCmd = &cobra.Command{
	Use:   "jobs",
	Short: "Machine job management commands",
	Long: `Machine job management commands for Rediacc CLI.
	
This command group includes machine operations, repository operations,
plugin management, terminal access, and file operations.`,
}

func init() {
	// TODO: Add subcommands for machine, repo, plugin operations
}
