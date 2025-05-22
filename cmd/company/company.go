package company

import (
	"github.com/spf13/cobra"
)

// CompanyCmd represents the company command
var CompanyCmd = &cobra.Command{
	Use:   "company",
	Short: "Company management commands",
	Long: `Company management commands for Rediacc CLI.
	
This command group includes company creation, information retrieval,
user management, resource limits, vault operations, and subscription details.`,
}

func init() {
	// TODO: Add subcommands
}
