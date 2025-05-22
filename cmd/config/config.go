package config

import (
	"github.com/spf13/cobra"
)

// ConfigCmd represents the config command
var ConfigCmd = &cobra.Command{
	Use:   "config",
	Short: "CLI configuration commands",
	Long: `CLI configuration commands for Rediacc CLI.
	
This command group includes configuration initialization, setting values,
getting values, and listing current configuration.`,
}

func init() {
	// TODO: Add subcommands
}
