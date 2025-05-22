package infra

import (
	"fmt"

	"github.com/spf13/cobra"
	"github.com/rediacc/cli/internal/api"
	"github.com/rediacc/cli/internal/config"
	"github.com/rediacc/cli/internal/format"
)

// InfraCmd represents the infra command
var InfraCmd = &cobra.Command{
	Use:   "infra",
	Short: "Infrastructure management commands",
	Long: `Infrastructure management commands for Rediacc CLI.
	
This command group includes region, bridge, and machine management operations.`,
}

// regionsCmd manages regions
var regionsCmd = &cobra.Command{
	Use:   "regions",
	Short: "Region management commands",
	Long:  "Commands for managing infrastructure regions",
}

// regionsListCmd lists regions
var regionsListCmd = &cobra.Command{
	Use:   "list",
	Short: "List regions",
	Long:  "List all regions in the company",
	RunE:  runRegionsList,
}

// regionsCreateCmd creates a region
var regionsCreateCmd = &cobra.Command{
	Use:   "create <name>",
	Short: "Create a region",
	Long:  "Create a new infrastructure region",
	Args:  cobra.ExactArgs(1),
	RunE:  runRegionsCreate,
}

// machinesCmd manages machines
var machinesCmd = &cobra.Command{
	Use:   "machines",
	Short: "Machine management commands",
	Long:  "Commands for managing infrastructure machines",
}

// machinesListCmd lists machines
var machinesListCmd = &cobra.Command{
	Use:   "list <team>",
	Short: "List machines",
	Long:  "List all machines for a specific team",
	Args:  cobra.ExactArgs(1),
	RunE:  runMachinesList,
}

func runRegionsList(cmd *cobra.Command, args []string) error {
	cfg := config.Get()
	client := api.NewClient(cfg.Server.URL)

	response, err := client.ExecuteStoredProcedure("GetAllCompanyRegions", map[string]interface{}{})
	if err != nil {
		return fmt.Errorf("failed to list regions: %w", err)
	}

	if response.Success {
		if len(response.Data) == 0 {
			fmt.Println("No regions found")
			return nil
		}
		return format.Print(response.Data)
	}

	return fmt.Errorf("failed to list regions: %s", response.Error)
}

func runRegionsCreate(cmd *cobra.Command, args []string) error {
	name := args[0]

	cfg := config.Get()
	client := api.NewClient(cfg.Server.URL)

	params := map[string]interface{}{
		"name": name,
	}

	response, err := client.ExecuteStoredProcedure("CreateRegion", params)
	if err != nil {
		return fmt.Errorf("failed to create region: %w", err)
	}

	if response.Success {
		format.PrintSuccess("✓ Region '%s' created successfully", name)
		return nil
	}

	return fmt.Errorf("failed to create region: %s", response.Error)
}

func runMachinesList(cmd *cobra.Command, args []string) error {
	team := args[0]

	cfg := config.Get()
	client := api.NewClient(cfg.Server.URL)

	params := map[string]interface{}{
		"team": team,
	}

	response, err := client.ExecuteStoredProcedure("GetTeamMachines", params)
	if err != nil {
		return fmt.Errorf("failed to list machines: %w", err)
	}

	if response.Success {
		if len(response.Data) == 0 {
			fmt.Printf("No machines found for team '%s'\n", team)
			return nil
		}
		return format.Print(response.Data)
	}

	return fmt.Errorf("failed to list machines: %s", response.Error)
}

func init() {
	// Add subcommands to regions command
	regionsCmd.AddCommand(regionsListCmd)
	regionsCmd.AddCommand(regionsCreateCmd)

	// Add subcommands to machines command
	machinesCmd.AddCommand(machinesListCmd)

	// Add subcommands to infra command
	InfraCmd.AddCommand(regionsCmd)
	InfraCmd.AddCommand(machinesCmd)
}
