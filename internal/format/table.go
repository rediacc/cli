package format

import (
	"fmt"
	"os"
	"reflect"
	"strconv"
	"strings"

	"github.com/fatih/color"
	"github.com/olekukonko/tablewriter"
)

// TableFormatter handles table output formatting
type TableFormatter struct {
	useColors bool
}

// NewTableFormatter creates a new table formatter
func NewTableFormatter(useColors bool) *TableFormatter {
	return &TableFormatter{
		useColors: useColors,
	}
}

// Format formats data as a table
func (f *TableFormatter) Format(data interface{}) error {
	if data == nil {
		fmt.Println("No data to display")
		return nil
	}

	// Handle different data types
	switch v := data.(type) {
	case []map[string]interface{}:
		return f.formatMapSlice(v)
	case map[string]interface{}:
		return f.formatSingleMap(v)
	case []interface{}:
		return f.formatInterfaceSlice(v)
	default:
		return f.formatReflection(data)
	}
}

// formatMapSlice formats a slice of maps as a table
func (f *TableFormatter) formatMapSlice(data []map[string]interface{}) error {
	if len(data) == 0 {
		fmt.Println("No data to display")
		return nil
	}

	// Get headers from first row
	headers := make([]string, 0)
	for key := range data[0] {
		headers = append(headers, f.formatHeader(key))
	}

	// Create table
	table := tablewriter.NewWriter(os.Stdout)
	table.SetHeader(headers)

	// Configure table appearance
	f.configureTable(table)

	// Add rows
	for _, row := range data {
		values := make([]string, len(headers))
		for i, header := range headers {
			// Convert header back to original key
			key := f.headerToKey(header)
			if val, exists := row[key]; exists {
				values[i] = f.formatValue(val)
			} else {
				values[i] = ""
			}
		}
		table.Append(values)
	}

	table.Render()
	return nil
}

// formatSingleMap formats a single map as a vertical table
func (f *TableFormatter) formatSingleMap(data map[string]interface{}) error {
	table := tablewriter.NewWriter(os.Stdout)
	table.SetHeader([]string{"Property", "Value"})

	f.configureTable(table)

	for key, value := range data {
		table.Append([]string{
			f.formatHeader(key),
			f.formatValue(value),
		})
	}

	table.Render()
	return nil
}

// formatInterfaceSlice formats a slice of interfaces
func (f *TableFormatter) formatInterfaceSlice(data []interface{}) error {
	if len(data) == 0 {
		fmt.Println("No data to display")
		return nil
	}

	// Try to convert to maps if possible
	mapData := make([]map[string]interface{}, 0, len(data))
	for _, item := range data {
		if m, ok := item.(map[string]interface{}); ok {
			mapData = append(mapData, m)
		} else {
			// Fall back to simple list
			return f.formatSimpleList(data)
		}
	}

	return f.formatMapSlice(mapData)
}

// formatSimpleList formats a simple list of values
func (f *TableFormatter) formatSimpleList(data []interface{}) error {
	table := tablewriter.NewWriter(os.Stdout)
	table.SetHeader([]string{"Value"})

	f.configureTable(table)

	for _, item := range data {
		table.Append([]string{f.formatValue(item)})
	}

	table.Render()
	return nil
}

// formatReflection uses reflection to format unknown types
func (f *TableFormatter) formatReflection(data interface{}) error {
	v := reflect.ValueOf(data)
	t := reflect.TypeOf(data)

	if v.Kind() == reflect.Ptr {
		v = v.Elem()
		t = t.Elem()
	}

	switch v.Kind() {
	case reflect.Struct:
		return f.formatStruct(v, t)
	case reflect.Slice:
		return f.formatSlice(v)
	default:
		fmt.Printf("%v\n", data)
		return nil
	}
}

// formatStruct formats a struct as a vertical table
func (f *TableFormatter) formatStruct(v reflect.Value, t reflect.Type) error {
	table := tablewriter.NewWriter(os.Stdout)
	table.SetHeader([]string{"Field", "Value"})

	f.configureTable(table)

	for i := 0; i < v.NumField(); i++ {
		field := t.Field(i)
		value := v.Field(i)

		if field.IsExported() {
			table.Append([]string{
				f.formatHeader(field.Name),
				f.formatValue(value.Interface()),
			})
		}
	}

	table.Render()
	return nil
}

// formatSlice formats a slice using reflection
func (f *TableFormatter) formatSlice(v reflect.Value) error {
	if v.Len() == 0 {
		fmt.Println("No data to display")
		return nil
	}

	// Convert to interface slice
	data := make([]interface{}, v.Len())
	for i := 0; i < v.Len(); i++ {
		data[i] = v.Index(i).Interface()
	}

	return f.formatInterfaceSlice(data)
}

// configureTable sets up table appearance
func (f *TableFormatter) configureTable(table *tablewriter.Table) {
	table.SetAutoWrapText(false)
	table.SetAutoFormatHeaders(true)
	table.SetHeaderAlignment(tablewriter.ALIGN_LEFT)
	table.SetAlignment(tablewriter.ALIGN_LEFT)
	table.SetCenterSeparator("")
	table.SetColumnSeparator("")
	table.SetRowSeparator("")
	table.SetHeaderLine(false)
	table.SetBorder(false)
	table.SetTablePadding("\t")
	table.SetNoWhiteSpace(true)

	if f.useColors {
		table.SetHeaderColor(
			tablewriter.Colors{tablewriter.Bold, tablewriter.FgHiBlueColor},
		)
	}
}

// formatHeader formats a header string
func (f *TableFormatter) formatHeader(header string) string {
	// Convert snake_case to Title Case
	words := strings.Split(header, "_")
	for i, word := range words {
		if len(word) > 0 {
			words[i] = strings.ToUpper(word[:1]) + strings.ToLower(word[1:])
		}
	}
	return strings.Join(words, " ")
}

// headerToKey converts a formatted header back to original key
func (f *TableFormatter) headerToKey(header string) string {
	// Convert Title Case back to snake_case
	words := strings.Split(header, " ")
	for i, word := range words {
		words[i] = strings.ToLower(word)
	}
	return strings.Join(words, "_")
}

// formatValue formats a value for display
func (f *TableFormatter) formatValue(value interface{}) string {
	if value == nil {
		return ""
	}

	switch v := value.(type) {
	case string:
		return v
	case int, int8, int16, int32, int64:
		return fmt.Sprintf("%d", v)
	case uint, uint8, uint16, uint32, uint64:
		return fmt.Sprintf("%d", v)
	case float32, float64:
		return fmt.Sprintf("%.2f", v)
	case bool:
		if f.useColors {
			if v {
				return color.GreenString("true")
			}
			return color.RedString("false")
		}
		return strconv.FormatBool(v)
	default:
		return fmt.Sprintf("%v", v)
	}
}
