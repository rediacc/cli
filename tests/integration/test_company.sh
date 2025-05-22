#!/bin/bash

# Company Management Tests for Rediacc CLI
# Tests company creation, info, users, limits, vault, and subscription commands

source "$(dirname "$0")/cli_test_framework.sh"

# Test company help
test_company_help() {
    test_start "Company Help Command"
    
    if run_cli 0 company --help; then
        assert_exit_code 0 "company help command"
        assert_output_contains "Company management commands" "company help content"
        assert_output_contains "create" "shows create command"
        assert_output_contains "info" "shows info command"
        assert_output_contains "users" "shows users command"
        assert_output_contains "limits" "shows limits command"
        assert_output_contains "vault" "shows vault command"
        assert_output_contains "subscription" "shows subscription command"
    else
        test_fail "Company Help Command" "Failed to run company help"
    fi
}

# Test company create without parameters
test_company_create_no_params() {
    test_start "Company Create Without Parameters"
    
    if run_cli 1 company create; then
        assert_exit_code 1 "company create without params"
        assert_error_contains "required" "error mentions required parameters"
    else
        test_fail "Company Create Without Parameters" "Unexpected behavior"
    fi
}

# Test company create with missing name
test_company_create_missing_name() {
    test_start "Company Create Missing Name"
    
    if run_cli 1 company create -e admin@example.com; then
        assert_exit_code 1 "company create missing name"
        assert_error_contains "name" "error mentions name"
    else
        test_fail "Company Create Missing Name" "Unexpected behavior"
    fi
}

# Test company create with missing admin email
test_company_create_missing_email() {
    test_start "Company Create Missing Email"
    
    if run_cli 1 company create -n "Test Company"; then
        assert_exit_code 1 "company create missing email"
        assert_error_contains "admin-email" "error mentions admin email"
    else
        test_fail "Company Create Missing Email" "Unexpected behavior"
    fi
}

# Test company info command
test_company_info() {
    test_start "Company Info Command"
    
    if run_cli 0 company info; then
        assert_exit_code 0 "company info command"
        # May show "No company information found" or actual data
    else
        test_fail "Company Info Command" "Failed to run company info"
    fi
}

# Test company users help
test_company_users_help() {
    test_start "Company Users Help Command"
    
    if run_cli 0 company users --help; then
        assert_exit_code 0 "company users help command"
        assert_output_contains "Company users management" "users help content"
        assert_output_contains "list" "shows list command"
    else
        test_fail "Company Users Help Command" "Failed to run company users help"
    fi
}

# Test company users list command
test_company_users_list() {
    test_start "Company Users List Command"
    
    if run_cli 0 company users list; then
        assert_exit_code 0 "company users list command"
        # May show "No users found" or actual user data
    else
        test_fail "Company Users List Command" "Failed to run company users list"
    fi
}

# Test company limits command
test_company_limits() {
    test_start "Company Limits Command"
    
    if run_cli 0 company limits; then
        assert_exit_code 0 "company limits command"
        # May show "No resource limits found" or actual data
    else
        test_fail "Company Limits Command" "Failed to run company limits"
    fi
}

# Test company vault help
test_company_vault_help() {
    test_start "Company Vault Help Command"
    
    if run_cli 0 company vault --help; then
        assert_exit_code 0 "company vault help command"
        assert_output_contains "Company vault management" "vault help content"
        assert_output_contains "get" "shows get command"
        assert_output_contains "update" "shows update command"
    else
        test_fail "Company Vault Help Command" "Failed to run company vault help"
    fi
}

# Test company vault get command
test_company_vault_get() {
    test_start "Company Vault Get Command"
    
    if run_cli 0 company vault get; then
        assert_exit_code 0 "company vault get command"
        # May show "No vault data found" or actual data
    else
        test_fail "Company Vault Get Command" "Failed to run company vault get"
    fi
}

# Test company vault update without data
test_company_vault_update_no_data() {
    test_start "Company Vault Update Without Data"
    
    if run_cli 1 company vault update; then
        assert_exit_code 1 "company vault update without data"
        assert_error_contains "data" "error mentions data"
    else
        test_fail "Company Vault Update Without Data" "Unexpected behavior"
    fi
}

# Test company subscription command
test_company_subscription() {
    test_start "Company Subscription Command"
    
    if run_cli 0 company subscription; then
        assert_exit_code 0 "company subscription command"
        # May show "No subscription information found" or actual data
    else
        test_fail "Company Subscription Command" "Failed to run company subscription"
    fi
}

# Test successful company create (requires middleware)
test_company_create_success() {
    test_start "Company Create Success"
    
    local company_name="Test Company CLI"
    local admin_email="admin@testcompany.com"
    
    if run_cli 0 company create -n "$company_name" -e "$admin_email"; then
        assert_exit_code 0 "successful company create"
        assert_output_contains "created successfully" "create success message"
        assert_output_contains "$company_name" "shows company name"
    else
        test_fail "Company Create Success" "Failed to create company"
    fi
}

# Test company info after creation (requires middleware)
test_company_info_success() {
    test_start "Company Info Success"
    
    if run_cli 0 company info; then
        assert_exit_code 0 "successful company info"
        # Should show actual company data now
    else
        test_fail "Company Info Success" "Failed to get company info"
    fi
}

# Test company users list with data (requires middleware)
test_company_users_list_success() {
    test_start "Company Users List Success"
    
    if run_cli 0 company users list; then
        assert_exit_code 0 "successful company users list"
        # Should show at least the admin user
    else
        test_fail "Company Users List Success" "Failed to list company users"
    fi
}

# Test company vault update (requires middleware)
test_company_vault_update_success() {
    test_start "Company Vault Update Success"
    
    local vault_data='{"testKey": "testValue", "environment": "test"}'
    
    if run_cli 0 company vault update -d "$vault_data"; then
        assert_exit_code 0 "successful vault update"
        assert_output_contains "updated successfully" "vault update success message"
    else
        test_fail "Company Vault Update Success" "Failed to update vault"
    fi
}

# Test company vault get after update (requires middleware)
test_company_vault_get_success() {
    test_start "Company Vault Get Success"
    
    if run_cli 0 company vault get; then
        assert_exit_code 0 "successful vault get"
        assert_output_contains "testKey" "shows updated vault data"
    else
        test_fail "Company Vault Get Success" "Failed to get vault data"
    fi
}

# Run all company tests
run_company_tests() {
    log_info "Running Company Management Tests..."
    
    # Basic company command tests
    test_company_help
    
    # Company create validation tests
    test_company_create_no_params
    test_company_create_missing_name
    test_company_create_missing_email
    
    # Company info tests
    test_company_info
    
    # Company users tests
    test_company_users_help
    test_company_users_list
    
    # Company limits tests
    test_company_limits
    
    # Company vault tests
    test_company_vault_help
    test_company_vault_get
    test_company_vault_update_no_data
    
    # Company subscription tests
    test_company_subscription
    
    # Company tests with middleware
    if check_middleware; then
        test_company_create_success
        test_company_info_success
        test_company_users_list_success
        test_company_vault_update_success
        test_company_vault_get_success
    else
        log_warning "Skipping middleware-dependent company tests"
    fi
}