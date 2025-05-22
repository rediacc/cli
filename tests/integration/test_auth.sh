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
    curl -s -X POST "$MIDDLEWARE_URL/api/StoredProcedure/EnableUserAccount" \
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
    
    # Auth flow tests (require middleware)
    if check_middleware; then
        test_login_invalid_credentials
        test_successful_login
        test_auth_status_after_login
        test_logout
        test_auth_status_after_logout
        test_logout_when_not_logged_in
    else
        log_warning "Skipping middleware-dependent tests"
    fi
}