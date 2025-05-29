package permissions

import (
	"fmt"

	"github.com/spf13/cobra"
	"github.com/rediacc/cli/internal/api"
	"github.com/rediacc/cli/internal/config"
	"github.com/rediacc/cli/internal/format"
)

// PermissionsCmd represents the permissions command
var PermissionsCmd = &cobra.Command{
	Use:   "permissions",
	Short: "Permission management commands",
	Long: `Permission management commands for Rediacc CLI.
	
This command group includes permission group management, adding/removing permissions,
and assigning users to permission groups.`,
}

// groupsCmd manages permission groups
var groupsCmd = &cobra.Command{
	Use:   "groups",
	Short: "Permission group management",
	Long:  "Commands for managing permission groups",
}

// groupsListCmd lists permission groups
var groupsListCmd = &cobra.Command{
	Use:   "list",
	Short: "List permission groups",
	Long:  "List all permission groups in the company",
	RunE:  runGroupsList,
}

// groupsCreateCmd creates a permission group
var groupsCreateCmd = &cobra.Command{
	Use:   "create <name>",
	Short: "Create permission group",
	Long:  "Create a new permission group",
	Args:  cobra.ExactArgs(1),
	RunE:  runGroupsCreate,
}

// groupsDeleteCmd deletes a permission group
var groupsDeleteCmd = &cobra.Command{
	Use:   "delete <name>",
	Short: "Delete permission group",
	Long:  "Delete an existing permission group",
	Args:  cobra.ExactArgs(1),
	RunE:  runGroupsDelete,
}

// groupsShowCmd shows permission group details
var groupsShowCmd = &cobra.Command{
	Use:   "show <name>",
	Short: "Show permission group details",
	Long:  "Display detailed information about a permission group",
	Args:  cobra.ExactArgs(1),
	RunE:  runGroupsShow,
}

// addCmd adds a permission to a group
var addCmd = &cobra.Command{
	Use:   "add <group> <permission>",
	Short: "Add permission to group",
	Long:  "Add a permission to a permission group",
	Args:  cobra.ExactArgs(2),
	RunE:  runAdd,
}

// removeCmd removes a permission from a group
var removeCmd = &cobra.Command{
	Use:   "remove <group> <permission>",
	Short: "Remove permission from group",
	Long:  "Remove a permission from a permission group",
	Args:  cobra.ExactArgs(2),
	RunE:  runRemove,
}

// assignCmd assigns a user to a permission group
var assignCmd = &cobra.Command{
	Use:   "assign <user-email> <group>",
	Short: "Assign user to permission group",
	Long:  "Assign a user to a permission group",
	Args:  cobra.ExactArgs(2),
	RunE:  runAssign,
}

func runGroupsList(cmd *cobra.Command, args []string) error {
	cfg := config.Get()
	client := api.NewClient(cfg.Server.URL)

	response, err := client.ExecuteStoredProcedure("GetCompanyPermissionGroups", map[string]interface{}{})
	if err != nil {
		return fmt.Errorf("failed to list permission groups: %w", err)
	}

	if response.Success {
		if len(response.Data) == 0 {
			fmt.Println("No permission groups found")
			return nil
		}
		return format.Print(response.Data)
	}

	return fmt.Errorf("failed to list permission groups: %s", response.Error)
}

func runGroupsCreate(cmd *cobra.Command, args []string) error {
	name := args[0]

	cfg := config.Get()
	client := api.NewClient(cfg.Server.URL)

	params := map[string]interface{}{
		"name": name,
	}

	response, err := client.ExecuteStoredProcedure("CreatePermissionGroup", params)
	if err != nil {
		return fmt.Errorf("failed to create permission group: %w", err)
	}

	if response.Success {
		format.PrintSuccess("✓ Permission group '%s' created successfully", name)
		return nil
	}

	return fmt.Errorf("failed to create permission group: %s", response.Error)
}

func runGroupsDelete(cmd *cobra.Command, args []string) error {
	name := args[0]

	cfg := config.Get()
	client := api.NewClient(cfg.Server.URL)

	params := map[string]interface{}{
		"name": name,
	}

	response, err := client.ExecuteStoredProcedure("DeletePermissionGroup", params)
	if err != nil {
		return fmt.Errorf("failed to delete permission group: %w", err)
	}

	if response.Success {
		format.PrintSuccess("✓ Permission group '%s' deleted successfully", name)
		return nil
	}

	return fmt.Errorf("failed to delete permission group: %s", response.Error)
}

func runGroupsShow(cmd *cobra.Command, args []string) error {
	name := args[0]

	cfg := config.Get()
	client := api.NewClient(cfg.Server.URL)

	params := map[string]interface{}{
		"name": name,
	}

	response, err := client.ExecuteStoredProcedure("GetPermissionGroupDetails", params)
	if err != nil {
		return fmt.Errorf("failed to get permission group details: %w", err)
	}

	if response.Success {
		if len(response.Data) == 0 {
			return fmt.Errorf("permission group '%s' not found", name)
		}
		return format.Print(response.Data[0])
	}

	return fmt.Errorf("failed to get permission group details: %s", response.Error)
}

func runAdd(cmd *cobra.Command, args []string) error {
	group := args[0]
	permission := args[1]

	cfg := config.Get()
	client := api.NewClient(cfg.Server.URL)

	params := map[string]interface{}{
		"group":      group,
		"permission": permission,
	}

	response, err := client.ExecuteStoredProcedure("CreatePermissionInGroup", params)
	if err != nil {
		return fmt.Errorf("failed to add permission: %w", err)
	}

	if response.Success {
		format.PrintSuccess("✓ Permission '%s' added to group '%s' successfully", permission, group)
		return nil
	}

	return fmt.Errorf("failed to add permission: %s", response.Error)
}

func runRemove(cmd *cobra.Command, args []string) error {
	group := args[0]
	permission := args[1]

	cfg := config.Get()
	client := api.NewClient(cfg.Server.URL)

	params := map[string]interface{}{
		"group":      group,
		"permission": permission,
	}

	response, err := client.ExecuteStoredProcedure("DeletePermissionFromGroup", params)
	if err != nil {
		return fmt.Errorf("failed to remove permission: %w", err)
	}

	if response.Success {
		format.PrintSuccess("✓ Permission '%s' removed from group '%s' successfully", permission, group)
		return nil
	}

	return fmt.Errorf("failed to remove permission: %s", response.Error)
}

func runAssign(cmd *cobra.Command, args []string) error {
	userEmail := args[0]
	group := args[1]

	cfg := config.Get()
	client := api.NewClient(cfg.Server.URL)

	params := map[string]interface{}{
		"userEmail": userEmail,
		"group":     group,
	}

	response, err := client.ExecuteStoredProcedure("UpdateUserPermissionGroup", params)
	if err != nil {
		return fmt.Errorf("failed to assign user to group: %w", err)
	}

	if response.Success {
		format.PrintSuccess("✓ User '%s' assigned to group '%s' successfully", userEmail, group)
		return nil
	}

	return fmt.Errorf("failed to assign user to group: %s", response.Error)
}

func init() {
	// Add subcommands to groups command
	groupsCmd.AddCommand(groupsListCmd)
	groupsCmd.AddCommand(groupsCreateCmd)
	groupsCmd.AddCommand(groupsDeleteCmd)
	groupsCmd.AddCommand(groupsShowCmd)

	// Add subcommands to permissions command
	PermissionsCmd.AddCommand(groupsCmd)
	PermissionsCmd.AddCommand(addCmd)
	PermissionsCmd.AddCommand(removeCmd)
	PermissionsCmd.AddCommand(assignCmd)
}
