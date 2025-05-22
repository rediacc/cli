package infra

import (
	"github.com/spf13/cobra"
)

// InfraCmd represents the infra command
var InfraCmd = &cobra.Command{
	Use:   "infra",
	Short: "Infrastructure management commands",
	Long: `Infrastructure management commands for Rediacc CLI.
	
This command group includes region, bridge, and machine management operations.`,
}

func init() {
	// TODO: Add subcommands for regions, bridges, machines
}
