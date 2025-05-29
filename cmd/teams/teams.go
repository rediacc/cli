package teams

import (
	"fmt"

	"github.com/spf13/cobra"
	"github.com/rediacc/cli/internal/api"
	"github.com/rediacc/cli/internal/config"
	"github.com/rediacc/cli/internal/format"
)

// TeamsCmd represents the teams command
var TeamsCmd = &cobra.Command{
	Use:   "teams",
	Short: "Team management commands",
	Long: `Team management commands for Rediacc CLI.
	
This command group includes team creation, deletion, renaming,
vault operations, and member management.`,
}

// listCmd lists teams
var listCmd = &cobra.Command{
	Use:   "list",
	Short: "List teams",
	Long:  "List all teams in the company",
	RunE:  runList,
}

// createCmd creates a new team
var createCmd = &cobra.Command{
	Use:   "create <name>",
	Short: "Create a new team",
	Long:  "Create a new team with the specified name",
	Args:  cobra.ExactArgs(1),
	RunE:  runCreate,
}

// deleteCmd deletes a team
var deleteCmd = &cobra.Command{
	Use:   "delete <name>",
	Short: "Delete a team",
	Long:  "Delete an existing team",
	Args:  cobra.ExactArgs(1),
	RunE:  runDelete,
}

// renameCmd renames a team
var renameCmd = &cobra.Command{
	Use:   "rename <old-name> <new-name>",
	Short: "Rename a team",
	Long:  "Rename an existing team",
	Args:  cobra.ExactArgs(2),
	RunE:  runRename,
}

// membersCmd manages team members
var membersCmd = &cobra.Command{
	Use:   "members",
	Short: "Team member management",
	Long:  "Commands for managing team members",
}

// membersListCmd lists team members
var membersListCmd = &cobra.Command{
	Use:   "list <team-name>",
	Short: "List team members",
	Long:  "List all members of a specific team",
	Args:  cobra.ExactArgs(1),
	RunE:  runMembersList,
}

// membersAddCmd adds a member to a team
var membersAddCmd = &cobra.Command{
	Use:   "add <team-name> <user-email>",
	Short: "Add team member",
	Long:  "Add a user to a team",
	Args:  cobra.ExactArgs(2),
	RunE:  runMembersAdd,
}

// membersRemoveCmd removes a member from a team
var membersRemoveCmd = &cobra.Command{
	Use:   "remove <team-name> <user-email>",
	Short: "Remove team member",
	Long:  "Remove a user from a team",
	Args:  cobra.ExactArgs(2),
	RunE:  runMembersRemove,
}

func runList(cmd *cobra.Command, args []string) error {
	cfg := config.Get()
	client := api.NewClient(cfg.Server.URL)

	response, err := client.ExecuteStoredProcedure("GetCompanyTeams", map[string]interface{}{})
	if err != nil {
		return fmt.Errorf("failed to list teams: %w", err)
	}

	if response.Success {
		if len(response.Data) == 0 {
			fmt.Println("No teams found")
			return nil
		}
		return format.Print(response.Data)
	}

	return fmt.Errorf("failed to list teams: %s", response.Error)
}

func runCreate(cmd *cobra.Command, args []string) error {
	name := args[0]

	cfg := config.Get()
	client := api.NewClient(cfg.Server.URL)

	// CreateTeam expects teamName and teamVault parameters (from tutorial)
	params := map[string]interface{}{
		"teamName":  name,
		"teamVault": "{}", // Empty vault data
	}

	response, err := client.ExecuteStoredProcedure("CreateTeam", params)
	if err != nil {
		return fmt.Errorf("failed to create team: %w", err)
	}

	if response.Success {
		format.PrintSuccess("✓ Team '%s' created successfully", name)
		return format.Print(response.Data)
	}

	return fmt.Errorf("failed to create team: %s", response.Error)
}

func runDelete(cmd *cobra.Command, args []string) error {
	name := args[0]

	cfg := config.Get()
	client := api.NewClient(cfg.Server.URL)

	params := map[string]interface{}{
		"name": name,
	}

	response, err := client.ExecuteStoredProcedure("DeleteTeam", params)
	if err != nil {
		return fmt.Errorf("failed to delete team: %w", err)
	}

	if response.Success {
		format.PrintSuccess("✓ Team '%s' deleted successfully", name)
		return nil
	}

	return fmt.Errorf("failed to delete team: %s", response.Error)
}

func runRename(cmd *cobra.Command, args []string) error {
	oldName := args[0]
	newName := args[1]

	cfg := config.Get()
	client := api.NewClient(cfg.Server.URL)

	params := map[string]interface{}{
		"oldName": oldName,
		"newName": newName,
	}

	response, err := client.ExecuteStoredProcedure("UpdateTeamName", params)
	if err != nil {
		return fmt.Errorf("failed to rename team: %w", err)
	}

	if response.Success {
		format.PrintSuccess("✓ Team renamed from '%s' to '%s' successfully", oldName, newName)
		return nil
	}

	return fmt.Errorf("failed to rename team: %s", response.Error)
}

func runMembersList(cmd *cobra.Command, args []string) error {
	teamName := args[0]

	cfg := config.Get()
	client := api.NewClient(cfg.Server.URL)

	params := map[string]interface{}{
		"name": teamName,
	}

	response, err := client.ExecuteStoredProcedure("GetTeamMembers", params)
	if err != nil {
		return fmt.Errorf("failed to list team members: %w", err)
	}

	if response.Success {
		if len(response.Data) == 0 {
			fmt.Printf("No members found in team '%s'\n", teamName)
			return nil
		}
		return format.Print(response.Data)
	}

	return fmt.Errorf("failed to list team members: %s", response.Error)
}

func runMembersAdd(cmd *cobra.Command, args []string) error {
	teamName := args[0]
	userEmail := args[1]

	cfg := config.Get()
	client := api.NewClient(cfg.Server.URL)

	params := map[string]interface{}{
		"Team":         teamName,
		"NewUserEmail": userEmail,
	}

	response, err := client.ExecuteStoredProcedure("AddUserToTeam", params)
	if err != nil {
		return fmt.Errorf("failed to add user to team: %w", err)
	}

	if response.Success {
		format.PrintSuccess("✓ User '%s' added to team '%s' successfully", userEmail, teamName)
		return nil
	}

	return fmt.Errorf("failed to add user to team: %s", response.Error)
}

func runMembersRemove(cmd *cobra.Command, args []string) error {
	teamName := args[0]
	userEmail := args[1]

	cfg := config.Get()
	client := api.NewClient(cfg.Server.URL)

	params := map[string]interface{}{
		"teamName":  teamName,
		"userEmail": userEmail,
	}

	response, err := client.ExecuteStoredProcedure("DeleteUserFromTeam", params)
	if err != nil {
		return fmt.Errorf("failed to remove user from team: %w", err)
	}

	if response.Success {
		format.PrintSuccess("✓ User '%s' removed from team '%s' successfully", userEmail, teamName)
		return nil
	}

	return fmt.Errorf("failed to remove user from team: %s", response.Error)
}

func init() {
	// Add subcommands to members command
	membersCmd.AddCommand(membersListCmd)
	membersCmd.AddCommand(membersAddCmd)
	membersCmd.AddCommand(membersRemoveCmd)

	// Add subcommands to teams command
	TeamsCmd.AddCommand(listCmd)
	TeamsCmd.AddCommand(createCmd)
	TeamsCmd.AddCommand(deleteCmd)
	TeamsCmd.AddCommand(renameCmd)
	TeamsCmd.AddCommand(membersCmd)
}
