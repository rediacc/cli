package raw

import (
	"github.com/spf13/cobra"
)

// RawCmd represents the raw command
var RawCmd = &cobra.Command{
	Use:   "raw",
	Short: "Raw stored procedure execution commands",
	Long: `Raw stored procedure execution commands for Rediacc CLI.
	
This command group allows direct execution of stored procedures
and listing available procedures.`,
}

func init() {
	// TODO: Add subcommands
}
