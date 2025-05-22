package format

import (
	"fmt"
	"reflect"
	"strings"
)

// TextFormatter handles simple text output formatting
type TextFormatter struct{}

// NewTextFormatter creates a new text formatter
func NewTextFormatter() *TextFormatter {
	return &TextFormatter{}
}

// Format formats data as simple text
func (f *TextFormatter) Format(data interface{}) error {
	if data == nil {
		fmt.Println("No data")
		return nil
	}

	switch v := data.(type) {
	case []map[string]interface{}:
		return f.formatMapSlice(v)
	case map[string]interface{}:
		return f.formatSingleMap(v)
	case []interface{}:
		return f.formatInterfaceSlice(v)
	case string:
		fmt.Println(v)
		return nil
	default:
		return f.formatReflection(data)
	}
}

// formatMapSlice formats a slice of maps as text
func (f *TextFormatter) formatMapSlice(data []map[string]interface{}) error {
	if len(data) == 0 {
		fmt.Println("No data")
		return nil
	}

	for i, item := range data {
		if i > 0 {
			fmt.Println()
		}
		fmt.Printf("Item %d:\n", i+1)
		for key, value := range item {
			fmt.Printf("  %s: %v\n", f.formatKey(key), f.formatValue(value))
		}
	}

	return nil
}

// formatSingleMap formats a single map as text
func (f *TextFormatter) formatSingleMap(data map[string]interface{}) error {
	for key, value := range data {
		fmt.Printf("%s: %v\n", f.formatKey(key), f.formatValue(value))
	}
	return nil
}

// formatInterfaceSlice formats a slice of interfaces as text
func (f *TextFormatter) formatInterfaceSlice(data []interface{}) error {
	if len(data) == 0 {
		fmt.Println("No data")
		return nil
	}

	for i, item := range data {
		if m, ok := item.(map[string]interface{}); ok {
			if i > 0 {
				fmt.Println()
			}
			fmt.Printf("Item %d:\n", i+1)
			for key, value := range m {
				fmt.Printf("  %s: %v\n", f.formatKey(key), f.formatValue(value))
			}
		} else {
			fmt.Printf("%v\n", f.formatValue(item))
		}
	}

	return nil
}

// formatReflection uses reflection to format unknown types
func (f *TextFormatter) formatReflection(data interface{}) error {
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

// formatStruct formats a struct as text
func (f *TextFormatter) formatStruct(v reflect.Value, t reflect.Type) error {
	for i := 0; i < v.NumField(); i++ {
		field := t.Field(i)
		value := v.Field(i)

		if field.IsExported() {
			fmt.Printf("%s: %v\n", f.formatKey(field.Name), f.formatValue(value.Interface()))
		}
	}
	return nil
}

// formatSlice formats a slice using reflection
func (f *TextFormatter) formatSlice(v reflect.Value) error {
	if v.Len() == 0 {
		fmt.Println("No data")
		return nil
	}

	data := make([]interface{}, v.Len())
	for i := 0; i < v.Len(); i++ {
		data[i] = v.Index(i).Interface()
	}

	return f.formatInterfaceSlice(data)
}

// formatKey formats a key for display
func (f *TextFormatter) formatKey(key string) string {
	// Convert snake_case to Title Case
	words := strings.Split(key, "_")
	for i, word := range words {
		if len(word) > 0 {
			words[i] = strings.ToUpper(word[:1]) + strings.ToLower(word[1:])
		}
	}
	return strings.Join(words, " ")
}

// formatValue formats a value for display
func (f *TextFormatter) formatValue(value interface{}) interface{} {
	if value == nil {
		return "N/A"
	}
	return value
}
