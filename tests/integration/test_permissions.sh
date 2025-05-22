#!/bin/bash

# Permissions Management Tests for Rediacc CLI
# Tests permission groups and permission assignment commands

source "$(dirname "$0")/cli_test_framework.sh"

# Test permissions help
test_permissions_help() {
    test_start "Permissions Help Command"
    
    if run_cli 0 permissions --help; then
        assert_exit_code 0 "permissions help command"
        assert_output_contains "Permission management commands" "permissions help content"
        assert_output_contains "groups" "shows groups command"
        assert_output_contains "add" "shows add command"
        assert_output_contains "remove" "shows remove command"
        assert_output_contains "assign" "shows assign command"
    else
        test_fail "Permissions Help Command" "Failed to run permissions help"
    fi
}

# Test permissions groups help
test_permissions_groups_help() {
    test_start "Permissions Groups Help Command"
    
    if run_cli 0 permissions groups --help; then
        assert_exit_code 0 "permissions groups help command"
        assert_output_contains "Permission group management" "groups help content"
        assert_output_contains "list" "shows list command"
        assert_output_contains "create" "shows create command"
        assert_output_contains "delete" "shows delete command"
        assert_output_contains "show" "shows show command"
    else
        test_fail "Permissions Groups Help Command" "Failed to run permissions groups help"
    fi
}

# Test permissions groups list command
test_permissions_groups_list() {
    test_start "Permissions Groups List Command"
    
    if run_cli 0 permissions groups list; then
        assert_exit_code 0 "permissions groups list command"
        # May show "No permission groups found" or actual data
    else
        test_fail "Permissions Groups List Command" "Failed to run permissions groups list"
    fi
}

# Test permissions groups create without name
test_permissions_groups_create_no_name() {
    test_start "Permissions Groups Create Without Name"
    
    if run_cli 1 permissions groups create; then
        assert_exit_code 1 "groups create without name"
        assert_error_contains "arg" "error mentions arguments"
    else
        test_fail "Permissions Groups Create Without Name" "Unexpected behavior"
    fi
}

# Test permissions groups delete without name
test_permissions_groups_delete_no_name() {
    test_start "Permissions Groups Delete Without Name"
    
    if run_cli 1 permissions groups delete; then
        assert_exit_code 1 "groups delete without name"
        assert_error_contains "arg" "error mentions arguments"
    else
        test_fail "Permissions Groups Delete Without Name" "Unexpected behavior"
    fi
}

# Test permissions groups show without name
test_permissions_groups_show_no_name() {
    test_start "Permissions Groups Show Without Name"
    
    if run_cli 1 permissions groups show; then
        assert_exit_code 1 "groups show without name"
        assert_error_contains "arg" "error mentions arguments"
    else
        test_fail "Permissions Groups Show Without Name" "Unexpected behavior"
    fi
}

# Test permissions add without arguments
test_permissions_add_no_args() {
    test_start "Permissions Add Without Arguments"
    
    if run_cli 1 permissions add; then
        assert_exit_code 1 "permissions add without args"
        assert_error_contains "arg" "error mentions arguments"
    else
        test_fail "Permissions Add Without Arguments" "Unexpected behavior"
    fi
}

# Test permissions add with only one argument
test_permissions_add_one_arg() {
    test_start "Permissions Add With One Argument"
    
    if run_cli 1 permissions add group1; then
        assert_exit_code 1 "permissions add with one arg"
        assert_error_contains "arg" "error mentions arguments"
    else
        test_fail "Permissions Add With One Argument" "Unexpected behavior"
    fi
}

# Test permissions remove without arguments
test_permissions_remove_no_args() {
    test_start "Permissions Remove Without Arguments"
    
    if run_cli 1 permissions remove; then
        assert_exit_code 1 "permissions remove without args"
        assert_error_contains "arg" "error mentions arguments"
    else
        test_fail "Permissions Remove Without Arguments" "Unexpected behavior"
    fi
}

# Test permissions assign without arguments
test_permissions_assign_no_args() {
    test_start "Permissions Assign Without Arguments"
    
    if run_cli 1 permissions assign; then
        assert_exit_code 1 "permissions assign without args"
        assert_error_contains "arg" "error mentions arguments"
    else
        test_fail "Permissions Assign Without Arguments" "Unexpected behavior"
    fi
}

# Test permissions assign with only one argument
test_permissions_assign_one_arg() {
    test_start "Permissions Assign With One Argument"
    
    if run_cli 1 permissions assign user@example.com; then
        assert_exit_code 1 "permissions assign with one arg"
        assert_error_contains "arg" "error mentions arguments"
    else
        test_fail "Permissions Assign With One Argument" "Unexpected behavior"
    fi
}

# Test successful permissions groups create (requires middleware)
test_permissions_groups_create_success() {
    test_start "Permissions Groups Create Success"
    
    local group_name="test-group"
    
    if run_cli 0 permissions groups create "$group_name"; then
        assert_exit_code 0 "successful groups create"
        assert_output_contains "created successfully" "create success message"
        assert_output_contains "$group_name" "shows group name"
    else
        test_fail "Permissions Groups Create Success" "Failed to create permission group"
    fi
}

# Test permissions groups list with data (requires middleware)
test_permissions_groups_list_success() {
    test_start "Permissions Groups List Success"
    
    if run_cli 0 permissions groups list; then
        assert_exit_code 0 "successful groups list"
        assert_output_contains "test-group" "shows created group"
    else
        test_fail "Permissions Groups List Success" "Failed to list permission groups"
    fi
}

# Test permissions groups show (requires middleware)
test_permissions_groups_show_success() {
    test_start "Permissions Groups Show Success"
    
    local group_name="test-group"
    
    if run_cli 0 permissions groups show "$group_name"; then
        assert_exit_code 0 "successful groups show"
        assert_output_contains "$group_name" "shows group details"
    else
        test_fail "Permissions Groups Show Success" "Failed to show permission group"
    fi
}

# Test permissions add (requires middleware)
test_permissions_add_success() {
    test_start "Permissions Add Success"
    
    local group_name="test-group"
    local permission="read_users"
    
    if run_cli 0 permissions add "$group_name" "$permission"; then
        assert_exit_code 0 "successful permission add"
        assert_output_contains "added" "add success message"
        assert_output_contains "$permission" "shows permission name"
        assert_output_contains "$group_name" "shows group name"
    else
        test_fail "Permissions Add Success" "Failed to add permission"
    fi
}

# Test permissions assign (requires middleware)
test_permissions_assign_success() {
    test_start "Permissions Assign Success"
    
    local user_email="test@example.com"
    local group_name="test-group"
    
    if run_cli 0 permissions assign "$user_email" "$group_name"; then
        assert_exit_code 0 "successful permission assign"
        assert_output_contains "assigned" "assign success message"
        assert_output_contains "$user_email" "shows user email"
        assert_output_contains "$group_name" "shows group name"
    else
        test_fail "Permissions Assign Success" "Failed to assign user to group"
    fi
}

# Test permissions remove (requires middleware)
test_permissions_remove_success() {
    test_start "Permissions Remove Success"
    
    local group_name="test-group"
    local permission="read_users"
    
    if run_cli 0 permissions remove "$group_name" "$permission"; then
        assert_exit_code 0 "successful permission remove"
        assert_output_contains "removed" "remove success message"
        assert_output_contains "$permission" "shows permission name"
        assert_output_contains "$group_name" "shows group name"
    else
        test_fail "Permissions Remove Success" "Failed to remove permission"
    fi
}

# Test permissions groups delete (requires middleware)
test_permissions_groups_delete_success() {
    test_start "Permissions Groups Delete Success"
    
    local group_name="test-group"
    
    if run_cli 0 permissions groups delete "$group_name"; then
        assert_exit_code 0 "successful groups delete"
        assert_output_contains "deleted successfully" "delete success message"
        assert_output_contains "$group_name" "shows group name"
    else
        test_fail "Permissions Groups Delete Success" "Failed to delete permission group"
    fi
}

# Run all permissions tests
run_permissions_tests() {
    log_info "Running Permissions Management Tests..."
    
    # Basic permissions command tests
    test_permissions_help
    test_permissions_groups_help
    
    # Permissions groups validation tests
    test_permissions_groups_list
    test_permissions_groups_create_no_name
    test_permissions_groups_delete_no_name
    test_permissions_groups_show_no_name
    
    # Permissions add/remove/assign validation tests
    test_permissions_add_no_args
    test_permissions_add_one_arg
    test_permissions_remove_no_args
    test_permissions_assign_no_args
    test_permissions_assign_one_arg
    
    # Permissions tests with middleware
    if check_middleware; then
        test_permissions_groups_create_success
        test_permissions_groups_list_success
        test_permissions_groups_show_success
        test_permissions_add_success
        test_permissions_assign_success
        test_permissions_remove_success
        test_permissions_groups_delete_success
    else
        log_warning "Skipping middleware-dependent permissions tests"
    fi
}