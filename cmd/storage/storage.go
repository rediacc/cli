package storage

import (
	"github.com/spf13/cobra"
)

// StorageCmd represents the storage command
var StorageCmd = &cobra.Command{
	Use:   "storage",
	Short: "Storage and repository management commands",
	Long: `Storage and repository management commands for Rediacc CLI.
	
This command group includes storage creation, deletion, updates,
and repository management operations.`,
}

func init() {
	// TODO: Add subcommands
}
