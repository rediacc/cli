#!/bin/bash

# Teams Management Tests for Rediacc CLI
# Tests team creation, deletion, listing, renaming, and member management commands

source "$(dirname "$0")/cli_test_framework.sh"

# Test teams help
test_teams_help() {
    test_start "Teams Help Command"
    
    if run_cli 0 teams --help; then
        assert_exit_code 0 "teams help command"
        assert_output_contains "Team management commands" "teams help content"
        assert_output_contains "create" "shows create command"
        assert_output_contains "delete" "shows delete command"
        assert_output_contains "list" "shows list command"
        assert_output_contains "rename" "shows rename command"
        assert_output_contains "members" "shows members command"
    else
        test_fail "Teams Help Command" "Failed to run teams help"
    fi
}

# Test teams list command
test_teams_list() {
    test_start "Teams List Command"
    
    if run_cli 0 teams list; then
        assert_exit_code 0 "teams list command"
        # May show "No teams found" or actual data
    else
        test_fail "Teams List Command" "Failed to run teams list"
    fi
}

# Test teams create without name
test_teams_create_no_name() {
    test_start "Teams Create Without Name"
    
    if run_cli 1 teams create; then
        assert_exit_code 1 "teams create without name"
        assert_error_contains "arg" "error mentions arguments"
    else
        test_fail "Teams Create Without Name" "Unexpected behavior"
    fi
}

# Test teams delete without name
test_teams_delete_no_name() {
    test_start "Teams Delete Without Name"
    
    if run_cli 1 teams delete; then
        assert_exit_code 1 "teams delete without name"
        assert_error_contains "arg" "error mentions arguments"
    else
        test_fail "Teams Delete Without Name" "Unexpected behavior"
    fi
}

# Test teams rename without arguments
test_teams_rename_no_args() {
    test_start "Teams Rename Without Arguments"
    
    if run_cli 1 teams rename; then
        assert_exit_code 1 "teams rename without args"
        assert_error_contains "arg" "error mentions arguments"
    else
        test_fail "Teams Rename Without Arguments" "Unexpected behavior"
    fi
}

# Test teams rename with one argument
test_teams_rename_one_arg() {
    test_start "Teams Rename With One Argument"
    
    if run_cli 1 teams rename "old-team"; then
        assert_exit_code 1 "teams rename with one arg"
        assert_error_contains "arg" "error mentions arguments"
    else
        test_fail "Teams Rename With One Argument" "Unexpected behavior"
    fi
}

# Test teams members help
test_teams_members_help() {
    test_start "Teams Members Help Command"
    
    if run_cli 0 teams members --help; then
        assert_exit_code 0 "teams members help command"
        assert_output_contains "Team member management" "members help content"
        assert_output_contains "list" "shows list command"
        assert_output_contains "add" "shows add command"
        assert_output_contains "remove" "shows remove command"
    else
        test_fail "Teams Members Help Command" "Failed to run teams members help"
    fi
}

# Test teams members list without team name
test_teams_members_list_no_team() {
    test_start "Teams Members List Without Team"
    
    if run_cli 1 teams members list; then
        assert_exit_code 1 "teams members list without team"
        assert_error_contains "arg" "error mentions arguments"
    else
        test_fail "Teams Members List Without Team" "Unexpected behavior"
    fi
}

# Test teams members add without arguments
test_teams_members_add_no_args() {
    test_start "Teams Members Add Without Arguments"
    
    if run_cli 1 teams members add; then
        assert_exit_code 1 "teams members add without args"
        assert_error_contains "arg" "error mentions arguments"
    else
        test_fail "Teams Members Add Without Arguments" "Unexpected behavior"
    fi
}

# Test teams members add with one argument
test_teams_members_add_one_arg() {
    test_start "Teams Members Add With One Argument"
    
    if run_cli 1 teams members add "team-name"; then
        assert_exit_code 1 "teams members add with one arg"
        assert_error_contains "arg" "error mentions arguments"
    else
        test_fail "Teams Members Add With One Argument" "Unexpected behavior"
    fi
}

# Test teams members remove without arguments
test_teams_members_remove_no_args() {
    test_start "Teams Members Remove Without Arguments"
    
    if run_cli 1 teams members remove; then
        assert_exit_code 1 "teams members remove without args"
        assert_error_contains "arg" "error mentions arguments"
    else
        test_fail "Teams Members Remove Without Arguments" "Unexpected behavior"
    fi
}

# Test successful teams create (requires middleware)
test_teams_create_success() {
    test_start "Teams Create Success"
    
    local team_name="test-team"
    
    if run_cli 0 teams create "$team_name"; then
        assert_exit_code 0 "successful teams create"
        assert_output_contains "created successfully" "create success message"
        assert_output_contains "$team_name" "shows team name"
    else
        test_fail "Teams Create Success" "Failed to create team"
    fi
}

# Test teams list with data (requires middleware)
test_teams_list_success() {
    test_start "Teams List Success"
    
    if run_cli 0 teams list; then
        assert_exit_code 0 "successful teams list"
        assert_output_contains "test-team" "shows created team"
    else
        test_fail "Teams List Success" "Failed to list teams"
    fi
}

# Test teams members list (requires middleware)
test_teams_members_list_success() {
    test_start "Teams Members List Success"
    
    local team_name="test-team"
    
    if run_cli 0 teams members list "$team_name"; then
        assert_exit_code 0 "successful members list"
        # May show "No members found" or actual member data
    else
        test_fail "Teams Members List Success" "Failed to list team members"
    fi
}

# Test teams members add (requires middleware)
test_teams_members_add_success() {
    test_start "Teams Members Add Success"
    
    local team_name="test-team"
    local user_email="testuser@example.com"
    
    if run_cli 0 teams members add "$team_name" "$user_email"; then
        assert_exit_code 0 "successful member add"
        assert_output_contains "added" "add success message"
        assert_output_contains "$user_email" "shows user email"
        assert_output_contains "$team_name" "shows team name"
    else
        test_fail "Teams Members Add Success" "Failed to add team member"
    fi
}

# Test teams rename (requires middleware)
test_teams_rename_success() {
    test_start "Teams Rename Success"
    
    local old_name="test-team"
    local new_name="renamed-test-team"
    
    if run_cli 0 teams rename "$old_name" "$new_name"; then
        assert_exit_code 0 "successful teams rename"
        assert_output_contains "renamed" "rename success message"
        assert_output_contains "$old_name" "shows old name"
        assert_output_contains "$new_name" "shows new name"
    else
        test_fail "Teams Rename Success" "Failed to rename team"
    fi
}

# Test teams members remove (requires middleware)
test_teams_members_remove_success() {
    test_start "Teams Members Remove Success"
    
    local team_name="renamed-test-team"
    local user_email="testuser@example.com"
    
    if run_cli 0 teams members remove "$team_name" "$user_email"; then
        assert_exit_code 0 "successful member remove"
        assert_output_contains "removed" "remove success message"
        assert_output_contains "$user_email" "shows user email"
        assert_output_contains "$team_name" "shows team name"
    else
        test_fail "Teams Members Remove Success" "Failed to remove team member"
    fi
}

# Test teams delete (requires middleware)
test_teams_delete_success() {
    test_start "Teams Delete Success"
    
    local team_name="renamed-test-team"
    
    if run_cli 0 teams delete "$team_name"; then
        assert_exit_code 0 "successful teams delete"
        assert_output_contains "deleted successfully" "delete success message"
        assert_output_contains "$team_name" "shows team name"
    else
        test_fail "Teams Delete Success" "Failed to delete team"
    fi
}

# Run all teams tests
run_teams_tests() {
    log_info "Running Teams Management Tests..."
    
    # Basic teams command tests
    test_teams_help
    test_teams_list
    
    # Teams validation tests
    test_teams_create_no_name
    test_teams_delete_no_name
    test_teams_rename_no_args
    test_teams_rename_one_arg
    
    # Teams members validation tests
    test_teams_members_help
    test_teams_members_list_no_team
    test_teams_members_add_no_args
    test_teams_members_add_one_arg
    test_teams_members_remove_no_args
    
    # Teams tests with middleware
    if check_middleware; then
        test_teams_create_success
        test_teams_list_success
        test_teams_members_list_success
        test_teams_members_add_success
        test_teams_rename_success
        test_teams_members_remove_success
        test_teams_delete_success
    else
        log_warning "Skipping middleware-dependent teams tests"
    fi
}