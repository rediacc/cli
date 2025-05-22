package cmd

import (
	"fmt"
	"os"

	"github.com/spf13/cobra"
	"github.com/spf13/viper"

	"github.com/rediacc/cli/cmd/auth"
	"github.com/rediacc/cli/cmd/company"
	"github.com/rediacc/cli/cmd/config"
	"github.com/rediacc/cli/cmd/infra"
	"github.com/rediacc/cli/cmd/jobs"
	"github.com/rediacc/cli/cmd/permissions"
	"github.com/rediacc/cli/cmd/queue"
	"github.com/rediacc/cli/cmd/raw"
	"github.com/rediacc/cli/cmd/schedules"
	"github.com/rediacc/cli/cmd/storage"
	"github.com/rediacc/cli/cmd/teams"
	appConfig "github.com/rediacc/cli/internal/config"
)

var (
	cfgFile string
	debug   bool
	output  string
)

// rootCmd represents the base command when called without any subcommands
var rootCmd = &cobra.Command{
	Use:   "rediacc",
	Short: "Rediacc CLI - Command-line interface for Rediacc platform",
	Long: `Rediacc CLI provides command-line access to all functionality 
available through the Rediacc middleware service.

The CLI communicates with the Rediacc middleware via HTTP/REST API,
which in turn interfaces with the SQL Server database through stored procedures.`,
	Version: "1.0.0",
	PersistentPreRunE: func(cmd *cobra.Command, args []string) error {
		// Initialize configuration
		if err := appConfig.Initialize(cfgFile); err != nil {
			return fmt.Errorf("failed to initialize configuration: %w", err)
		}

		// Set debug mode
		if debug {
			appConfig.SetDebug(true)
		}

		// Set output format
		if output != "" {
			appConfig.SetOutputFormat(output)
		}

		return nil
	},
}

// Execute adds all child commands to the root command and sets flags appropriately.
// This is called by main.main(). It only needs to happen once to the rootCmd.
func Execute() error {
	return rootCmd.Execute()
}

func init() {
	cobra.OnInitialize(initConfig)

	// Global flags
	rootCmd.PersistentFlags().StringVar(&cfgFile, "config", "", "config file (default is $HOME/.rediacc-cli.yaml)")
	rootCmd.PersistentFlags().BoolVar(&debug, "debug", false, "enable debug mode")
	rootCmd.PersistentFlags().StringVarP(&output, "output", "o", "table", "output format (table, json, yaml, text)")

	// Add subcommands
	rootCmd.AddCommand(auth.AuthCmd)
	rootCmd.AddCommand(company.CompanyCmd)
	rootCmd.AddCommand(permissions.PermissionsCmd)
	rootCmd.AddCommand(teams.TeamsCmd)
	rootCmd.AddCommand(infra.InfraCmd)
	rootCmd.AddCommand(storage.StorageCmd)
	rootCmd.AddCommand(schedules.SchedulesCmd)
	rootCmd.AddCommand(queue.QueueCmd)
	rootCmd.AddCommand(jobs.JobsCmd)
	rootCmd.AddCommand(config.ConfigCmd)
	rootCmd.AddCommand(raw.RawCmd)
}

// initConfig reads in config file and ENV variables if set.
func initConfig() {
	if cfgFile != "" {
		// Use config file from the flag.
		viper.SetConfigFile(cfgFile)
	} else {
		// Find home directory.
		home, err := os.UserHomeDir()
		cobra.CheckErr(err)

		// Search config in home directory with name ".rediacc-cli" (without extension).
		viper.AddConfigPath(home)
		viper.SetConfigType("yaml")
		viper.SetConfigName(".rediacc-cli")
	}

	// Environment variables
	viper.SetEnvPrefix("REDIACC")
	viper.AutomaticEnv()

	// If a config file is found, read it in.
	if err := viper.ReadInConfig(); err == nil && debug {
		fmt.Fprintln(os.Stderr, "Using config file:", viper.ConfigFileUsed())
	}
}
