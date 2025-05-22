#!/bin/bash

# Error Handling Tests for Rediacc CLI
# Tests various error scenarios and edge cases

source "$(dirname "$0")/cli_test_framework.sh"

# Test invalid command
test_invalid_command() {
    test_start "Invalid Command"
    
    if run_cli 1 invalid-command; then
        assert_exit_code 1 "invalid command"
        assert_error_contains "unknown command" "shows unknown command error"
    else
        test_fail "Invalid Command" "Unexpected behavior"
    fi
}

# Test invalid subcommand
test_invalid_subcommand() {
    test_start "Invalid Subcommand"
    
    # Cobra shows help for invalid subcommands with exit code 0
    if run_cli 0 auth invalid-subcommand; then
        assert_exit_code 0 "invalid subcommand shows help"
        assert_output_contains "Available Commands" "shows help for invalid subcommand"
    else
        test_fail "Invalid Subcommand" "Unexpected behavior"
    fi
}

# Test invalid flag
test_invalid_flag() {
    test_start "Invalid Flag"
    
    if run_cli 1 auth login --invalid-flag; then
        assert_exit_code 1 "invalid flag"
        assert_error_contains "unknown flag" "shows unknown flag error"
    else
        test_fail "Invalid Flag" "Unexpected behavior"
    fi
}

# Test malformed config file (backup and restore original)
test_malformed_config() {
    test_start "Malformed Config File"
    
    # Backup original config
    local backup_file="${TEST_CONFIG_FILE}.backup"
    cp "$TEST_CONFIG_FILE" "$backup_file"
    
    # Create malformed config
    echo "invalid: yaml: content: [unclosed" > "$TEST_CONFIG_FILE"
    
    # Try to run a command with malformed config
    if run_cli 1 auth status; then
        assert_exit_code 1 "malformed config"
        assert_error_contains "config" "mentions config error"
    else
        test_fail "Malformed Config" "Unexpected behavior with malformed config"
    fi
    
    # Restore original config
    mv "$backup_file" "$TEST_CONFIG_FILE"
}

# Test missing config file
test_missing_config() {
    test_start "Missing Config File"
    
    # Test with non-existent config file
    local missing_config="/tmp/non-existent-config.yaml"
    
    if run_cli 1 --config "$missing_config" auth status; then
        assert_exit_code 1 "missing config returns error"
        assert_error_contains "no such file or directory" "mentions missing config file"
    else
        test_fail "Missing Config" "Failed to handle missing config"
    fi
}

# Test network connectivity issues (when middleware is down)
test_network_connectivity() {
    test_start "Network Connectivity Issues"
    
    # Temporarily change config to point to non-existent server
    local original_url=$(run_cli 0 config get server.url && echo "$CLI_OUTPUT" | cut -d' ' -f2)
    
    # Set invalid server URL
    run_cli 0 config set server.url "http://non-existent-server:9999"
    
    # Try to login (should fail with network error)
    if run_cli 1 auth login -e test@example.com -p password123; then
        assert_exit_code 1 "network connectivity error"
        assert_error_contains "failed" "shows connection failure"
    else
        test_fail "Network Connectivity" "Unexpected network error behavior"
    fi
    
    # Restore original URL
    run_cli 0 config set server.url "$original_url"
}

# Test very long input values
test_long_input_values() {
    test_start "Long Input Values"
    
    # Create very long email (over typical limits)
    local long_email=$(printf 'a%.0s' {1..300})"@example.com"
    
    if run_cli 1 auth login -e "$long_email" -p password123; then
        assert_exit_code 1 "long email input"
        # Should handle gracefully (either validation error or server error)
    else
        test_fail "Long Input Values" "Unexpected behavior with long input"
    fi
}

# Test special characters in input
test_special_characters_input() {
    test_start "Special Characters Input"
    
    # Test with various special characters
    local special_chars_email="test+special@example.com"
    local special_chars_password="p@ssw0rd!#$%"
    
    if run_cli 1 auth login -e "$special_chars_email" -p "$special_chars_password"; then
        # Should handle special characters properly (might fail due to invalid creds, not parsing)
        if echo "$CLI_ERROR" | grep -q "login failed"; then
            test_pass "Special Characters Input - handled login failure correctly"
        else
            test_fail "Special Characters Input" "Unexpected error with special characters"
        fi
    else
        test_fail "Special Characters Input" "Failed to handle special characters"
    fi
}

# Test empty input values
test_empty_input_values() {
    test_start "Empty Input Values"
    
    # Test with empty password
    if run_cli 1 auth login -e test@example.com -p ""; then
        assert_exit_code 1 "empty password"
        assert_error_contains "password" "mentions password error"
    else
        test_fail "Empty Input Values" "Unexpected behavior with empty password"
    fi
    
    # Test with empty email
    if run_cli 1 auth login -e "" -p password123; then
        assert_exit_code 1 "empty email"
        assert_error_contains "email" "mentions email error"
    else
        test_fail "Empty Input Values" "Unexpected behavior with empty email"
    fi
}

# Test concurrent access (multiple CLI instances)
test_concurrent_access() {
    test_start "Concurrent Access"
    
    # This test is more complex and might require different approach
    # For now, just test that multiple quick sequential calls don't break anything
    
    local success_count=0
    local total_attempts=3
    
    for i in $(seq 1 $total_attempts); do
        if run_cli 0 config get server.url > /dev/null 2>&1; then
            success_count=$((success_count + 1))
        fi
    done
    
    if [ $success_count -eq $total_attempts ]; then
        test_pass "Concurrent Access - all sequential calls succeeded"
    else
        test_fail "Concurrent Access" "Only $success_count/$total_attempts calls succeeded"
    fi
}

# Test file permission issues
test_file_permissions() {
    test_start "File Permissions"
    
    # Make config file read-only temporarily
    chmod 444 "$TEST_CONFIG_FILE"
    
    # Try to set config (should fail)
    if run_cli 1 config set test.key test.value; then
        assert_exit_code 1 "readonly config file"
        assert_error_contains "permission\|denied\|readonly" "mentions permission error"
    else
        test_fail "File Permissions" "Unexpected behavior with readonly config"
    fi
    
    # Restore write permissions
    chmod 644 "$TEST_CONFIG_FILE"
}

# Test graceful handling of interrupted operations
test_interrupted_operations() {
    test_start "Interrupted Operations"
    
    # This is difficult to test programmatically, but we can test
    # that the CLI doesn't leave partial/corrupted config files
    
    # Run a config operation and verify config integrity
    run_cli 0 config set test.interrupt.key "test_value"
    
    # Verify config file is still valid YAML
    if python3 -c "import yaml; yaml.safe_load(open('$TEST_CONFIG_FILE'))" 2>/dev/null; then
        test_pass "Interrupted Operations - config file remains valid"
    else
        test_fail "Interrupted Operations" "Config file corrupted"
    fi
    
    # Clean up test key
    run_cli 0 config set test.interrupt.key ""
}

# Run all error handling tests
run_error_handling_tests() {
    log_info "Running Error Handling Tests..."
    
    # Command validation tests
    test_invalid_command
    test_invalid_subcommand
    test_invalid_flag
    
    # Config file error tests
    test_malformed_config
    test_missing_config
    test_file_permissions
    
    # Input validation tests
    test_long_input_values
    test_special_characters_input
    test_empty_input_values
    
    # System-level error tests
    test_network_connectivity
    test_concurrent_access
    test_interrupted_operations
}