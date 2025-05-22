#!/bin/bash

# Configuration Tests for Rediacc CLI
# Tests config commands and configuration management

source "$(dirname "$0")/cli_test_framework.sh"

# Test config help
test_config_help() {
    test_start "Config Help Command"
    
    if run_cli 0 config --help; then
        assert_exit_code 0 "config help command"
        assert_output_contains "configuration" "config help content"
        assert_output_contains "list" "shows list command"
        assert_output_contains "get" "shows get command"
        assert_output_contains "set" "shows set command"
        assert_output_contains "path" "shows path command"
    else
        test_fail "Config Help Command" "Failed to run config help"
    fi
}

# Test config path command
test_config_path() {
    test_start "Config Path Command"
    
    if run_cli 0 config path; then
        assert_exit_code 0 "config path command"
        # The path command shows the default location, not the --config override
        assert_output_contains ".rediacc-cli.yaml" "shows config file name"
        assert_output_contains "(file exists)" "indicates file exists"
    else
        test_fail "Config Path Command" "Failed to get config path"
    fi
}

# Test config list command
test_config_list() {
    test_start "Config List Command"
    
    if run_cli 0 config list; then
        assert_exit_code 0 "config list command"
        assert_output_contains "Current configuration" "shows config header"
        assert_output_contains "Server URL" "shows server URL"
        assert_output_contains "$MIDDLEWARE_URL" "shows correct URL"
        assert_output_contains "Auth Email" "shows auth email"
        assert_output_contains "Default Output Format" "shows output format"
    else
        test_fail "Config List Command" "Failed to list config"
    fi
}

# Test config get with valid key
test_config_get_valid() {
    test_start "Config Get Valid Key"
    
    if run_cli 0 config get server.url; then
        assert_exit_code 0 "config get valid key"
        assert_output_contains "server.url:" "shows key name"
        assert_output_contains "$MIDDLEWARE_URL" "shows correct value"
    else
        test_fail "Config Get Valid Key" "Failed to get config value"
    fi
}

# Test config get with invalid key
test_config_get_invalid() {
    test_start "Config Get Invalid Key"
    
    if run_cli 1 config get invalid.key; then
        assert_exit_code 1 "config get invalid key"
        assert_error_contains "not found" "shows not found error"
    else
        test_fail "Config Get Invalid Key" "Unexpected behavior"
    fi
}

# Test config set command
test_config_set() {
    test_start "Config Set Command"
    
    local test_key="format.colors"
    local test_value="false"
    
    if run_cli 0 config set "$test_key" "$test_value"; then
        assert_exit_code 0 "config set command"
        assert_output_contains "Set $test_key = $test_value" "shows set confirmation"
    else
        test_fail "Config Set Command" "Failed to set config value"
        return
    fi
    
    # Verify the value was set
    if run_cli 0 config get "$test_key"; then
        assert_output_contains "$test_value" "config value was updated"
    else
        test_fail "Config Set Verification" "Failed to verify set value"
    fi
}

# Test config set with invalid format
test_config_set_invalid_format() {
    test_start "Config Set Invalid Format"
    
    # Test setting with too few arguments
    if run_cli 1 config set only_one_arg; then
        assert_exit_code 1 "config set insufficient args"
        assert_error_contains "accepts 2 arg" "shows argument error"
    else
        test_fail "Config Set Invalid Format" "Unexpected behavior"
    fi
}

# Test config persistence (set, restart, get)
test_config_persistence() {
    test_start "Config Persistence"
    
    local test_key="server.timeout"
    local test_value="45s"
    
    # Set a value
    if run_cli 0 config set "$test_key" "$test_value"; then
        assert_exit_code 0 "config set for persistence test"
    else
        test_fail "Config Persistence Setup" "Failed to set config"
        return
    fi
    
    # Get the value (this simulates a new CLI invocation)
    if run_cli 0 config get "$test_key"; then
        assert_exit_code 0 "config get after set"
        assert_output_contains "$test_value" "persisted value is correct"
    else
        test_fail "Config Persistence" "Failed to persist config value"
    fi
}

# Test output format configuration
test_output_format_config() {
    test_start "Output Format Configuration"
    
    # Test setting different output formats
    local formats=("table" "json" "yaml" "text")
    
    for format in "${formats[@]}"; do
        if run_cli 0 config set format.default "$format"; then
            assert_exit_code 0 "set format to $format"
            
            # Verify it was set
            if run_cli 0 config get format.default; then
                assert_output_contains "$format" "format $format was set"
            else
                test_fail "Output Format Config" "Failed to verify $format setting"
            fi
        else
            test_fail "Output Format Config" "Failed to set format to $format"
        fi
    done
}

# Test config validation (attempt to set invalid values)
test_config_validation() {
    test_start "Config Validation"
    
    # Try to set an invalid server URL format (this should still work as it's just a string)
    if run_cli 0 config set server.url "invalid-url"; then
        assert_exit_code 0 "config allows invalid URL format"
    else
        test_fail "Config Validation" "Unexpected validation behavior"
    fi
    
    # Reset to valid URL
    run_cli 0 config set server.url "$MIDDLEWARE_URL"
}

# Test special characters in config values
test_config_special_characters() {
    test_start "Config Special Characters"
    
    local test_key="auth.email"
    local test_value="test+special.chars@example-domain.com"
    
    if run_cli 0 config set "$test_key" "$test_value"; then
        assert_exit_code 0 "config set with special characters"
        
        # Verify special characters are preserved
        if run_cli 0 config get "$test_key"; then
            assert_output_contains "$test_value" "special characters preserved"
        else
            test_fail "Config Special Characters Verification" "Failed to verify special characters"
        fi
    else
        test_fail "Config Special Characters" "Failed to set value with special characters"
    fi
}

# Run all config tests
run_config_tests() {
    log_info "Running Configuration Tests..."
    
    # Basic config tests
    test_config_help
    test_config_path
    test_config_list
    
    # Config get/set tests
    test_config_get_valid
    test_config_get_invalid
    test_config_set
    test_config_set_invalid_format
    
    # Advanced config tests
    test_config_persistence
    test_output_format_config
    test_config_validation
    test_config_special_characters
}