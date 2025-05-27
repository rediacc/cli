#!/bin/bash

# Authentication Tests for Rediacc CLI
# Tests login, logout, status, and error handling

source "$(dirname "$0")/cli_test_framework.sh"

# Test basic CLI help
test_cli_help() {
    test_start "CLI Help Command"
    
    if run_cli 0 --help; then
        assert_exit_code 0 "help command"
        assert_output_contains "Rediacc CLI" "help output"
        assert_output_contains "Available Commands" "help shows commands"
    else
        test_fail "CLI Help Command" "Failed to run help command"
    fi
}

# Test version command
test_cli_version() {
    test_start "CLI Version Command"
    
    if run_cli 0 --version; then
        assert_exit_code 0 "version command"
        assert_output_contains "version" "version output"
    else
        test_fail "CLI Version Command" "Failed to run version command"
    fi
}

# Test auth help
test_auth_help() {
    test_start "Auth Help Command"
    
    if run_cli 0 auth --help; then
        assert_exit_code 0 "auth help command"
        assert_output_contains "Authentication" "auth help content"
        assert_output_contains "login" "shows login command"
        assert_output_contains "logout" "shows logout command" 
        assert_output_contains "status" "shows status command"
    else
        test_fail "Auth Help Command" "Failed to run auth help"
    fi
}

# Test initial auth status (should be not logged in)
test_initial_auth_status() {
    test_start "Initial Auth Status"
    
    if run_cli 0 auth status; then
        assert_exit_code 0 "status command"
        assert_output_contains "Not logged in" "initial status"
    else
        test_fail "Initial Auth Status" "Failed to run status command"
    fi
}

# Test login without parameters (should fail)
test_login_no_params() {
    test_start "Login Without Parameters"
    
    if run_cli 1 auth login; then
        assert_exit_code 1 "login without params"
        assert_error_contains "required" "error mentions required parameters"
    else
        test_fail "Login Without Parameters" "Unexpected behavior"
    fi
}

# Test login with missing email
test_login_missing_email() {
    test_start "Login Missing Email"
    
    if run_cli 1 auth login -p password123; then
        assert_exit_code 1 "login missing email"
        assert_error_contains "email" "error mentions email"
    else
        test_fail "Login Missing Email" "Unexpected behavior"
    fi
}

# Test login with missing password
test_login_missing_password() {
    test_start "Login Missing Password"
    
    if run_cli 1 auth login -e test@example.com; then
        assert_exit_code 1 "login missing password"
        assert_error_contains "password" "error mentions password"
    else
        test_fail "Login Missing Password" "Unexpected behavior"
    fi
}

# Test login with invalid credentials (requires middleware)
test_login_invalid_credentials() {
    test_start "Login Invalid Credentials"
    
    if run_cli 1 auth login -e invalid@example.com -p wrongpassword; then
        assert_exit_code 1 "invalid login"
        assert_error_contains "login failed" "shows login failure"
    else
        test_fail "Login Invalid Credentials" "Unexpected behavior"
    fi
}

# Test successful login (requires middleware and setup)
test_successful_login() {
    test_start "Successful Login"
    
    # First ensure company is created and user is enabled
    log_info "Setting up test user..."
    
    # Create company (this should work with any email/password for authorization)
    curl -s -X POST "$MIDDLEWARE_URL/api/StoredProcedure/CreateNewCompany" \
        -H "Content-Type: application/json" \
        -H "Rediacc-UserEmail: $TEST_EMAIL" \
        -H "Rediacc-UserHash: $(echo -n '$TEST_PASSWORD' | sha256sum | cut -d' ' -f1 | xxd -r -p | base64)" \
        -d '{"companyName": "Test Company"}' > /dev/null
    
    # Enable user account
    curl -s -X POST "$MIDDLEWARE_URL/api/StoredProcedure/ActivateUserAccount" \
        -H "Content-Type: application/json" \
        -d "{\"userEmail\": \"$TEST_EMAIL\"}" > /dev/null
    
    if run_cli 0 auth login -e "$TEST_EMAIL" -p "$TEST_PASSWORD"; then
        assert_exit_code 0 "successful login"
        assert_output_contains "Successfully logged in" "login success message"
        assert_output_contains "$TEST_EMAIL" "shows email"
    else
        test_fail "Successful Login" "Failed to login with valid credentials"
    fi
}

# Test auth status after login
test_auth_status_after_login() {
    test_start "Auth Status After Login"
    
    if run_cli 0 auth status; then
        assert_exit_code 0 "status after login"
        assert_output_contains "Logged in as $TEST_EMAIL" "shows logged in status"
        assert_output_contains "Session: Active" "shows active session"
        assert_output_contains "Request Credential" "shows credential"
    else
        test_fail "Auth Status After Login" "Failed to get status"
    fi
}

# Test logout
test_logout() {
    test_start "Logout"
    
    if run_cli 0 auth logout; then
        assert_exit_code 0 "logout command"
        assert_output_contains "Successfully logged out" "logout success message"
    else
        test_fail "Logout" "Failed to logout"
    fi
}

# Test auth status after logout
test_auth_status_after_logout() {
    test_start "Auth Status After Logout"
    
    if run_cli 0 auth status; then
        assert_exit_code 0 "status after logout"
        assert_output_contains "Not logged in" "shows not logged in"
    else
        test_fail "Auth Status After Logout" "Failed to get status"
    fi
}

# Test logout when not logged in
test_logout_when_not_logged_in() {
    test_start "Logout When Not Logged In"
    
    if run_cli 1 auth logout; then
        assert_exit_code 1 "logout when not logged in"
        assert_error_contains "not logged in" "error message"
    else
        test_fail "Logout When Not Logged In" "Unexpected behavior"
    fi
}

# Test auth user help
test_auth_user_help() {
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
}

# Test user create without parameters
test_user_create_no_params() {
    test_start "User Create Without Parameters"
    
    if run_cli 1 auth user create; then
        assert_exit_code 1 "user create without params"
        assert_error_contains "required" "error mentions required parameters"
    else
        test_fail "User Create Without Parameters" "Unexpected behavior"
    fi
}

# Test user create with missing email
test_user_create_missing_email() {
    test_start "User Create Missing Email"
    
    if run_cli 1 auth user create -n "Test User" -p password123; then
        assert_exit_code 1 "user create missing email"
        assert_error_contains "email" "error mentions email"
    else
        test_fail "User Create Missing Email" "Unexpected behavior"
    fi
}

# Test user create with missing name
test_user_create_missing_name() {
    test_start "User Create Missing Name"
    
    if run_cli 1 auth user create -e test@example.com -p password123; then
        assert_exit_code 1 "user create missing name"
        assert_error_contains "name" "error mentions name"
    else
        test_fail "User Create Missing Name" "Unexpected behavior"
    fi
}

# Test user create with missing password
test_user_create_missing_password() {
    test_start "User Create Missing Password"
    
    if run_cli 1 auth user create -e test@example.com -n "Test User"; then
        assert_exit_code 1 "user create missing password"
        assert_error_contains "password" "error mentions password"
    else
        test_fail "User Create Missing Password" "Unexpected behavior"
    fi
}

# Test user list command
test_user_list() {
    test_start "User List Command"
    
    if run_cli 0 auth user list; then
        assert_exit_code 0 "user list command"
        # May show "No users found" or actual user data
        # Just verify it doesn't error
    else
        test_fail "User List Command" "Failed to run user list"
    fi
}

# Test user info without email parameter
test_user_info_no_email() {
    test_start "User Info Without Email"
    
    if run_cli 1 auth user info; then
        assert_exit_code 1 "user info without email"
        assert_error_contains "arg" "error mentions arguments"
    else
        test_fail "User Info Without Email" "Unexpected behavior"
    fi
}

# Test user info with invalid email
test_user_info_invalid_email() {
    test_start "User Info Invalid Email"
    
    if run_cli 1 auth user info nonexistent@example.com; then
        assert_exit_code 1 "user info invalid email"
        # Will fail due to middleware call, but command structure is correct
    else
        test_fail "User Info Invalid Email" "Command should fail with middleware error"
    fi
}

# Test user activate without email parameter
test_user_activate_no_email() {
    test_start "User Activate Without Email"
    
    if run_cli 1 auth user activate; then
        assert_exit_code 1 "user activate without email"
        assert_error_contains "arg" "error mentions arguments"
    else
        test_fail "User Activate Without Email" "Unexpected behavior"
    fi
}

# Test user deactivate without email parameter
test_user_deactivate_no_email() {
    test_start "User Deactivate Without Email"
    
    if run_cli 1 auth user deactivate; then
        assert_exit_code 1 "user deactivate without email"
        assert_error_contains "arg" "error mentions arguments"
    else
        test_fail "User Deactivate Without Email" "Unexpected behavior"
    fi
}

# Test user update-password without email parameter
test_user_update_password_no_email() {
    test_start "User Update Password Without Email"
    
    if run_cli 1 auth user update-password; then
        assert_exit_code 1 "user update password without email"
        assert_error_contains "arg" "error mentions arguments"
    else
        test_fail "User Update Password Without Email" "Unexpected behavior"
    fi
}

# Test user update-password without password flag
test_user_update_password_no_password() {
    test_start "User Update Password Without Password Flag"
    
    if run_cli 1 auth user update-password test@example.com; then
        assert_exit_code 1 "user update password without password flag"
        assert_error_contains "password" "error mentions password"
    else
        test_fail "User Update Password Without Password Flag" "Unexpected behavior"
    fi
}

# Test successful user create (requires middleware)
test_user_create_success() {
    test_start "User Create Success"
    
    local test_user_email="newuser@example.com"
    local test_user_name="New Test User"
    local test_user_password="newpassword123"
    
    if run_cli 0 auth user create -e "$test_user_email" -n "$test_user_name" -p "$test_user_password"; then
        assert_exit_code 0 "successful user create"
        assert_output_contains "created successfully" "create success message"
        assert_output_contains "$test_user_email" "shows email"
    else
        test_fail "User Create Success" "Failed to create user"
    fi
}

# Test user info after creation (requires middleware)
test_user_info_success() {
    test_start "User Info Success"
    
    local test_user_email="newuser@example.com"
    
    if run_cli 0 auth user info "$test_user_email"; then
        assert_exit_code 0 "successful user info"
        assert_output_contains "$test_user_email" "shows user email"
    else
        test_fail "User Info Success" "Failed to get user info"
    fi
}

# Test user activate (requires middleware)
test_user_activate_success() {
    test_start "User Activate Success"
    
    local test_user_email="newuser@example.com"
    
    if run_cli 0 auth user activate "$test_user_email"; then
        assert_exit_code 0 "successful user activate"
        assert_output_contains "activated successfully" "activate success message"
        assert_output_contains "$test_user_email" "shows email"
    else
        test_fail "User Activate Success" "Failed to activate user"
    fi
}

# Test user update password (requires middleware)
test_user_update_password_success() {
    test_start "User Update Password Success"
    
    local test_user_email="newuser@example.com"
    local new_password="updatedpassword123"
    
    if run_cli 0 auth user update-password "$test_user_email" -p "$new_password"; then
        assert_exit_code 0 "successful password update"
        assert_output_contains "updated successfully" "password update success message"
        assert_output_contains "$test_user_email" "shows email"
    else
        test_fail "User Update Password Success" "Failed to update password"
    fi
}

# Test user deactivate (requires middleware)
test_user_deactivate_success() {
    test_start "User Deactivate Success"
    
    local test_user_email="newuser@example.com"
    
    if run_cli 0 auth user deactivate "$test_user_email"; then
        assert_exit_code 0 "successful user deactivate"
        assert_output_contains "deactivated successfully" "deactivate success message"
        assert_output_contains "$test_user_email" "shows email"
    else
        test_fail "User Deactivate Success" "Failed to deactivate user"
    fi
}

# Run all auth tests
run_auth_tests() {
    log_info "Running Authentication Tests..."
    
    # Basic CLI tests
    test_cli_help
    test_cli_version
    test_auth_help
    
    # Auth status tests
    test_initial_auth_status
    
    # Login validation tests
    test_login_no_params
    test_login_missing_email
    test_login_missing_password
    
    # User command help tests
    test_auth_user_help
    
    # User command validation tests
    test_user_create_no_params
    test_user_create_missing_email
    test_user_create_missing_name
    test_user_create_missing_password
    test_user_list
    test_user_info_no_email
    test_user_info_invalid_email
    test_user_activate_no_email
    test_user_deactivate_no_email
    test_user_update_password_no_email
    test_user_update_password_no_password
    
    # Auth flow tests (require middleware)
    if check_middleware; then
        test_login_invalid_credentials
        test_successful_login
        test_auth_status_after_login
        
        # User management tests with middleware
        test_user_create_success
        test_user_info_success
        test_user_activate_success
        test_user_update_password_success
        test_user_deactivate_success
        
        test_logout
        test_auth_status_after_logout
        test_logout_when_not_logged_in
    else
        log_warning "Skipping middleware-dependent tests"
    fi
}