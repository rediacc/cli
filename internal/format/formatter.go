package format

import (
	"fmt"

	"github.com/fatih/color"
	"github.com/rediacc/cli/internal/config"
)

// Formatter interface for different output formats
type Formatter interface {
	Format(data interface{}) error
}

// GetFormatter returns a formatter based on the specified format
func GetFormatter(format string) (Formatter, error) {
	cfg := config.Get()
	useColors := cfg.Format.Colors

	switch format {
	case "table":
		return NewTableFormatter(useColors), nil
	case "json":
		return NewJSONFormatter(true), nil
	case "json-compact":
		return NewJSONFormatter(false), nil
	case "yaml":
		return NewYAMLFormatter(), nil
	case "text":
		return NewTextFormatter(), nil
	default:
		return nil, fmt.Errorf("unsupported format: %s", format)
	}
}

// Print formats and prints data using the configured output format
func Print(data interface{}) error {
	format := config.GetOutputFormat()
	formatter, err := GetFormatter(format)
	if err != nil {
		return err
	}
	return formatter.Format(data)
}

// PrintSuccess prints a success message
func PrintSuccess(message string, args ...interface{}) {
	cfg := config.Get()
	if cfg.Format.Colors {
		color.Green(message, args...)
	} else {
		fmt.Printf(message+"\n", args...)
	}
}

// PrintError prints an error message
func PrintError(message string, args ...interface{}) {
	cfg := config.Get()
	if cfg.Format.Colors {
		color.Red(message, args...)
	} else {
		fmt.Printf("Error: "+message+"\n", args...)
	}
}

// PrintWarning prints a warning message
func PrintWarning(message string, args ...interface{}) {
	cfg := config.Get()
	if cfg.Format.Colors {
		color.Yellow(message, args...)
	} else {
		fmt.Printf("Warning: "+message+"\n", args...)
	}
}

// PrintInfo prints an info message
func PrintInfo(message string, args ...interface{}) {
	cfg := config.Get()
	if cfg.Format.Colors {
		color.Blue(message, args...)
	} else {
		fmt.Printf("Info: "+message+"\n", args...)
	}
}

// PrintDebug prints a debug message if debug mode is enabled
func PrintDebug(message string, args ...interface{}) {
	if config.IsDebug() {
		cfg := config.Get()
		if cfg.Format.Colors {
			color.Cyan("[DEBUG] "+message, args...)
		} else {
			fmt.Printf("[DEBUG] "+message+"\n", args...)
		}
	}
}
