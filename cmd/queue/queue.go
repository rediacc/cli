package queue

import (
	"github.com/spf13/cobra"
)

// QueueCmd represents the queue command
var QueueCmd = &cobra.Command{
	Use:   "queue",
	Short: "Queue management commands",
	Long: `Queue management commands for Rediacc CLI.
	
This command group includes queue item management, responses, and getting next items.`,
}

func init() {
	// TODO: Add subcommands
}
