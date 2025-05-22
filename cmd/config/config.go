package config

import (
	"fmt"
	"os"
	"path/filepath"

	"github.com/spf13/cobra"
	"github.com/spf13/viper"
	appConfig "github.com/rediacc/cli/internal/config"
)

// ConfigCmd represents the config command
var ConfigCmd = &cobra.Command{
	Use:   "config",
	Short: "CLI configuration commands",
	Long: `CLI configuration commands for Rediacc CLI.
	
This command group includes configuration initialization, setting values,
getting values, and listing current configuration.`,
}

// listCmd shows the current configuration
var listCmd = &cobra.Command{
	Use:   "list",
	Short: "List current configuration",
	Long:  "Display the current configuration settings",
	RunE:  runList,
}

// getCmd gets a specific configuration value
var getCmd = &cobra.Command{
	Use:   "get <key>",
	Short: "Get a configuration value",
	Long:  "Get the value of a specific configuration key",
	Args:  cobra.ExactArgs(1),
	RunE:  runGet,
}

// setCmd sets a configuration value
var setCmd = &cobra.Command{
	Use:   "set <key> <value>",
	Short: "Set a configuration value",
	Long:  "Set the value of a specific configuration key",
	Args:  cobra.ExactArgs(2),
	RunE:  runSet,
}

// pathCmd shows the configuration file path
var pathCmd = &cobra.Command{
	Use:   "path",
	Short: "Show configuration file path",
	Long:  "Display the path to the configuration file",
	RunE:  runPath,
}

func runList(cmd *cobra.Command, args []string) error {
	cfg := appConfig.Get()
	
	fmt.Println("Current configuration:")
	fmt.Printf("  Server URL: %s\n", cfg.Server.URL)
	fmt.Printf("  Server Timeout: %s\n", cfg.Server.Timeout)
	fmt.Printf("  Auth Email: %s\n", cfg.Auth.Email)
	fmt.Printf("  Default Output Format: %s\n", cfg.Format.Default)
	fmt.Printf("  Colors Enabled: %t\n", cfg.Format.Colors)
	fmt.Printf("  Timestamps Enabled: %t\n", cfg.Format.Timestamps)
	fmt.Printf("  SSH Timeout: %s\n", cfg.SSH.Timeout)
	fmt.Printf("  SSH Retry Attempts: %d\n", cfg.SSH.RetryAttempts)
	fmt.Printf("  SSH Retry Delay: %s\n", cfg.SSH.RetryDelay)
	fmt.Printf("  Default Datastore Size: %s\n", cfg.Jobs.DefaultDatastoreSize)
	fmt.Printf("  SSH Key Path: %s\n", cfg.Jobs.SSHKeyPath)
	fmt.Printf("  Number of Machines: %d\n", len(cfg.Jobs.Machines))
	
	return nil
}

func runGet(cmd *cobra.Command, args []string) error {
	key := args[0]
	value := viper.Get(key)
	
	if value == nil {
		return fmt.Errorf("configuration key '%s' not found", key)
	}
	
	fmt.Printf("%s: %v\n", key, value)
	return nil
}

func runSet(cmd *cobra.Command, args []string) error {
	key := args[0]
	value := args[1]
	
	viper.Set(key, value)
	
	if err := viper.WriteConfig(); err != nil {
		return fmt.Errorf("failed to save configuration: %w", err)
	}
	
	fmt.Printf("Set %s = %s\n", key, value)
	return nil
}

func runPath(cmd *cobra.Command, args []string) error {
	home, err := os.UserHomeDir()
	if err != nil {
		return fmt.Errorf("could not get home directory: %w", err)
	}
	
	configPath := filepath.Join(home, ".rediacc-cli.yaml")
	fmt.Println(configPath)
	
	// Check if file exists
	if _, err := os.Stat(configPath); os.IsNotExist(err) {
		fmt.Println("(file does not exist)")
	} else {
		fmt.Println("(file exists)")
	}
	
	return nil
}

func init() {
	// Add subcommands
	ConfigCmd.AddCommand(listCmd)
	ConfigCmd.AddCommand(getCmd)
	ConfigCmd.AddCommand(setCmd)
	ConfigCmd.AddCommand(pathCmd)
}
