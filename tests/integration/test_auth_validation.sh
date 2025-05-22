#!/bin/bash

# Auth Validation Tests for Rediacc CLI
# Tests validation logic for auth commands without requiring middleware

source "$(dirname "$0")/cli_test_framework.sh"

# Test auth user command validation tests that don't require middleware
run_auth_validation_tests() {
    log_info "Running Auth Validation Tests (No Middleware Required)..."
    
    # Test auth user help
    test_start "Auth User Help Command"
    if run_cli 0 auth user --help; then
        assert_exit_code 0 "auth user help command"
        assert_output_contains "User management commands" "user help content"
        assert_output_contains "create" "shows create command"
        assert_output_contains "list" "shows list command"
        assert_output_contains "info" "shows info command"
        assert_output_contains "activate" "shows activate command"
        assert_output_contains "deactivate" "shows deactivate command"
        assert_output_contains "update-password" "shows update-password command"
    else
        test_fail "Auth User Help Command" "Failed to run auth user help"
    fi

    # Test user create without parameters
    test_start "User Create Without Parameters"
    if run_cli 1 auth user create; then
        assert_exit_code 1 "user create without params"
        assert_error_contains "required" "error mentions required parameters"
    else
        test_fail "User Create Without Parameters" "Unexpected behavior"
    fi

    # Test user create with missing email
    test_start "User Create Missing Email"
    if run_cli 1 auth user create -p password123; then
        assert_exit_code 1 "user create missing email"
        assert_error_contains "email" "error mentions email"
    else
        test_fail "User Create Missing Email" "Unexpected behavior"
    fi

    # Test user create with missing password
    test_start "User Create Missing Password"
    if run_cli 1 auth user create -e test@example.com; then
        assert_exit_code 1 "user create missing password"
        assert_error_contains "password" "error mentions password"
    else
        test_fail "User Create Missing Password" "Unexpected behavior"
    fi

    # Test user info without email parameter
    test_start "User Info Without Email"
    if run_cli 1 auth user info; then
        assert_exit_code 1 "user info without email"
        assert_error_contains "arg" "error mentions arguments"
    else
        test_fail "User Info Without Email" "Unexpected behavior"
    fi

    # Test user activate without email parameter
    test_start "User Activate Without Email"
    if run_cli 1 auth user activate; then
        assert_exit_code 1 "user activate without email"
        assert_error_contains "arg" "error mentions arguments"
    else
        test_fail "User Activate Without Email" "Unexpected behavior"
    fi

    # Test user deactivate without email parameter
    test_start "User Deactivate Without Email"
    if run_cli 1 auth user deactivate; then
        assert_exit_code 1 "user deactivate without email"
        assert_error_contains "arg" "error mentions arguments"
    else
        test_fail "User Deactivate Without Email" "Unexpected behavior"
    fi

    # Test user update-password without email parameter
    test_start "User Update Password Without Email"
    if run_cli 1 auth user update-password; then
        assert_exit_code 1 "user update password without email"
        assert_error_contains "arg" "error mentions arguments"
    else
        test_fail "User Update Password Without Email" "Unexpected behavior"
    fi

    # Test user update-password without password flag
    test_start "User Update Password Without Password Flag"
    if run_cli 1 auth user update-password test@example.com; then
        assert_exit_code 1 "user update password without password flag"
        assert_error_contains "password" "error mentions password"
    else
        test_fail "User Update Password Without Password Flag" "Unexpected behavior"
    fi

    log_info "Auth validation tests completed"
}