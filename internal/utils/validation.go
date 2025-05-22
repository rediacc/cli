package utils

import (
	"fmt"
	"net/mail"
	"regexp"
	"strings"
)

// ValidateEmail validates an email address
func ValidateEmail(email string) error {
	if email == "" {
		return fmt.Errorf("email is required")
	}

	_, err := mail.ParseAddress(email)
	if err != nil {
		return fmt.Errorf("invalid email format")
	}

	return nil
}

// ValidatePassword validates a password
func ValidatePassword(password string) error {
	if password == "" {
		return fmt.Errorf("password is required")
	}

	if len(password) < 8 {
		return fmt.Errorf("password must be at least 8 characters long")
	}

	return nil
}

// ValidateRequired validates that a string is not empty
func ValidateRequired(value, fieldName string) error {
	if strings.TrimSpace(value) == "" {
		return fmt.Errorf("%s is required", fieldName)
	}
	return nil
}

// ValidateName validates a name field
func ValidateName(name, fieldName string) error {
	if err := ValidateRequired(name, fieldName); err != nil {
		return err
	}

	if len(name) > 255 {
		return fmt.Errorf("%s must be less than 255 characters", fieldName)
	}

	// Check for valid characters (letters, numbers, spaces, hyphens, underscores)
	validName := regexp.MustCompile(`^[a-zA-Z0-9\s\-_]+$`)
	if !validName.MatchString(name) {
		return fmt.Errorf("%s contains invalid characters", fieldName)
	}

	return nil
}

// ValidateAlias validates an alias field (no spaces)
func ValidateAlias(alias, fieldName string) error {
	if err := ValidateRequired(alias, fieldName); err != nil {
		return err
	}

	if len(alias) > 100 {
		return fmt.Errorf("%s must be less than 100 characters", fieldName)
	}

	// Check for valid characters (letters, numbers, hyphens, underscores only)
	validAlias := regexp.MustCompile(`^[a-zA-Z0-9\-_]+$`)
	if !validAlias.MatchString(alias) {
		return fmt.Errorf("%s can only contain letters, numbers, hyphens, and underscores", fieldName)
	}

	return nil
}

// ValidateIP validates an IP address
func ValidateIP(ip string) error {
	if err := ValidateRequired(ip, "IP address"); err != nil {
		return err
	}

	// Simple IPv4 validation
	ipv4Pattern := regexp.MustCompile(`^(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)$`)
	if !ipv4Pattern.MatchString(ip) {
		return fmt.Errorf("invalid IP address format")
	}

	return nil
}

// ValidateURL validates a URL
func ValidateURL(url string) error {
	if err := ValidateRequired(url, "URL"); err != nil {
		return err
	}

	urlPattern := regexp.MustCompile(`^https?://[a-zA-Z0-9\-\.]+\.[a-zA-Z]{2,}(?:/.*)?$`)
	if !urlPattern.MatchString(url) {
		return fmt.Errorf("invalid URL format")
	}

	return nil
}

// ValidateSize validates a size string (e.g., "100G", "1T")
func ValidateSize(size string) error {
	if err := ValidateRequired(size, "size"); err != nil {
		return err
	}

	sizePattern := regexp.MustCompile(`^[0-9]+[KMGTPE]?[B]?$`)
	if !sizePattern.MatchString(strings.ToUpper(size)) {
		return fmt.Errorf("invalid size format (use format like 100G, 1T)")
	}

	return nil
}
