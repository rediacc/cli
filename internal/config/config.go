package config

import (
	"fmt"
	"os"
	"path/filepath"

	"github.com/spf13/viper"
	"gopkg.in/yaml.v3"
)

// Config represents the application configuration
type Config struct {
	Server ServerConfig `yaml:"server"`
	Auth   AuthConfig   `yaml:"auth"`
	Jobs   JobsConfig   `yaml:"jobs"`
	Format FormatConfig `yaml:"format"`
	SSH    SSHConfig    `yaml:"ssh"`
}

// ServerConfig contains server connection settings
type ServerConfig struct {
	URL     string `yaml:"url"`
	Timeout string `yaml:"timeout"`
}

// AuthConfig contains authentication settings
type AuthConfig struct {
	Email             string `yaml:"email"`
	SessionToken      string `yaml:"session_token"`
	RequestCredential string `yaml:"request_credential"`
}

// JobsConfig contains job execution settings
type JobsConfig struct {
	DefaultDatastoreSize string    `yaml:"default_datastore_size"`
	SSHTimeout           string    `yaml:"ssh_timeout"`
	SSHKeyPath           string    `yaml:"ssh_key_path"`
	Machines             []Machine `yaml:"machines"`
}

// Machine represents a machine configuration
type Machine struct {
	Alias     string `yaml:"alias"`
	IP        string `yaml:"ip"`
	User      string `yaml:"user"`
	Datastore string `yaml:"datastore"`
}

// FormatConfig contains output formatting settings
type FormatConfig struct {
	Default    string `yaml:"default"`
	Colors     bool   `yaml:"colors"`
	Timestamps bool   `yaml:"timestamps"`
}

// SSHConfig contains SSH connection settings
type SSHConfig struct {
	Timeout       string `yaml:"timeout"`
	RetryAttempts int    `yaml:"retry_attempts"`
	RetryDelay    string `yaml:"retry_delay"`
}

var (
	globalConfig *Config
	debug        bool
	outputFormat string
)

// Initialize loads the configuration from file
func Initialize(configFile string) error {
	if configFile != "" {
		viper.SetConfigFile(configFile)
	} else {
		home, err := os.UserHomeDir()
		if err != nil {
			return fmt.Errorf("could not get home directory: %w", err)
		}

		viper.AddConfigPath(home)
		viper.SetConfigType("yaml")
		viper.SetConfigName(".rediacc-cli")
	}

	// Set defaults
	setDefaults()

	// Read config file
	if err := viper.ReadInConfig(); err != nil {
		if _, ok := err.(viper.ConfigFileNotFoundError); ok {
			// Config file not found; create default config
			if err := createDefaultConfig(); err != nil {
				return fmt.Errorf("could not create default config: %w", err)
			}
		} else {
			return fmt.Errorf("could not read config file: %w", err)
		}
	}

	// Unmarshal config
	globalConfig = &Config{}
	if err := viper.Unmarshal(globalConfig); err != nil {
		return fmt.Errorf("could not unmarshal config: %w", err)
	}

	// Workaround: manually sync auth fields from viper
	globalConfig.Auth.Email = viper.GetString("auth.email")
	globalConfig.Auth.SessionToken = viper.GetString("auth.session_token")
	globalConfig.Auth.RequestCredential = viper.GetString("auth.request_credential")

	return nil
}

// setDefaults sets default configuration values
func setDefaults() {
	viper.SetDefault("server.url", "http://localhost:8080")
	viper.SetDefault("server.timeout", "30s")
	viper.SetDefault("auth.email", "")
	viper.SetDefault("auth.session_token", "")
	viper.SetDefault("auth.request_credential", "")
	viper.SetDefault("jobs.default_datastore_size", "100G")
	viper.SetDefault("jobs.ssh_timeout", "30s")
	viper.SetDefault("jobs.ssh_key_path", "~/.ssh/id_rsa")
	viper.SetDefault("format.default", "table")
	viper.SetDefault("format.colors", true)
	viper.SetDefault("format.timestamps", true)
	viper.SetDefault("ssh.timeout", "30s")
	viper.SetDefault("ssh.retry_attempts", 3)
	viper.SetDefault("ssh.retry_delay", "5s")
}

// createDefaultConfig creates a default configuration file
func createDefaultConfig() error {
	home, err := os.UserHomeDir()
	if err != nil {
		return err
	}

	configPath := filepath.Join(home, ".rediacc-cli.yaml")

	defaultConfig := Config{
		Server: ServerConfig{
			URL:     "http://localhost:8080",
			Timeout: "30s",
		},
		Auth: AuthConfig{},
		Jobs: JobsConfig{
			DefaultDatastoreSize: "100G",
			SSHTimeout:           "30s",
			SSHKeyPath:           "~/.ssh/id_rsa",
			Machines:             []Machine{},
		},
		Format: FormatConfig{
			Default:    "table",
			Colors:     true,
			Timestamps: true,
		},
		SSH: SSHConfig{
			Timeout:       "30s",
			RetryAttempts: 3,
			RetryDelay:    "5s",
		},
	}

	data, err := yaml.Marshal(defaultConfig)
	if err != nil {
		return err
	}

	return os.WriteFile(configPath, data, 0600)
}

// Get returns the global configuration
func Get() *Config {
	if globalConfig == nil {
		globalConfig = &Config{}
	}
	return globalConfig
}

// Save saves the current configuration to file
func Save() error {
	if globalConfig == nil {
		return fmt.Errorf("no configuration to save")
	}

	home, err := os.UserHomeDir()
	if err != nil {
		return err
	}

	configPath := filepath.Join(home, ".rediacc-cli.yaml")

	data, err := yaml.Marshal(globalConfig)
	if err != nil {
		return err
	}

	return os.WriteFile(configPath, data, 0600)
}

// SetDebug sets the debug mode
func SetDebug(enabled bool) {
	debug = enabled
}

// IsDebug returns whether debug mode is enabled
func IsDebug() bool {
	return debug
}

// SetOutputFormat sets the output format
func SetOutputFormat(format string) {
	outputFormat = format
}

// GetOutputFormat returns the current output format
func GetOutputFormat() string {
	if outputFormat != "" {
		return outputFormat
	}
	if globalConfig != nil {
		return globalConfig.Format.Default
	}
	return "table"
}

// UpdateAuth updates the authentication configuration
func UpdateAuth(email, sessionToken, requestCredential string) error {
	if globalConfig == nil {
		return fmt.Errorf("configuration not initialized")
	}

	// Update both viper and globalConfig
	viper.Set("auth.email", email)
	viper.Set("auth.session_token", sessionToken)  
	viper.Set("auth.request_credential", requestCredential)
	
	globalConfig.Auth.Email = email
	globalConfig.Auth.SessionToken = sessionToken
	globalConfig.Auth.RequestCredential = requestCredential

	// Save using viper to ensure consistency
	return viper.WriteConfig()
}

// ClearAuth clears the authentication configuration
func ClearAuth() error {
	if globalConfig == nil {
		return fmt.Errorf("configuration not initialized")
	}

	// Clear both viper and globalConfig
	viper.Set("auth.email", "")
	viper.Set("auth.session_token", "")
	viper.Set("auth.request_credential", "")

	globalConfig.Auth.Email = ""
	globalConfig.Auth.SessionToken = ""
	globalConfig.Auth.RequestCredential = ""

	return viper.WriteConfig()
}
