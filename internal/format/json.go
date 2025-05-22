package format

import (
	"encoding/json"
	"fmt"
)

// JSONFormatter handles JSON output formatting
type JSONFormatter struct {
	pretty bool
}

// NewJSONFormatter creates a new JSON formatter
func NewJSONFormatter(pretty bool) *JSONFormatter {
	return &JSONFormatter{
		pretty: pretty,
	}
}

// Format formats data as JSON
func (f *JSONFormatter) Format(data interface{}) error {
	var output []byte
	var err error

	if f.pretty {
		output, err = json.MarshalIndent(data, "", "  ")
	} else {
		output, err = json.Marshal(data)
	}

	if err != nil {
		return fmt.Errorf("failed to marshal JSON: %w", err)
	}

	fmt.Println(string(output))
	return nil
}
