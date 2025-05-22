#!/bin/bash

# Rediacc CLI Integration Test Runner
# Orchestrates all CLI integration tests

set -e

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CLI_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

# Source framework
source "$SCRIPT_DIR/cli_test_framework.sh"

# Test configuration
export CLI_BINARY="${CLI_BINARY:-$CLI_ROOT/bin/rediacc}"
export MIDDLEWARE_URL="${MIDDLEWARE_URL:-http://localhost:8080}"

# Test categories
run_basic_tests() {
    log_info "=========================================="
    log_info "         BASIC CLI TESTS"
    log_info "=========================================="
    
    source "$SCRIPT_DIR/test_auth.sh"
    
    # Run basic tests that don't require middleware
    test_cli_help
    test_cli_version
    test_auth_help
    test_initial_auth_status
    test_login_no_params
    test_login_missing_email
    test_login_missing_password
}

run_config_tests() {
    log_info "=========================================="
    log_info "       CONFIGURATION TESTS"
    log_info "=========================================="
    
    source "$SCRIPT_DIR/test_config.sh"
    run_config_tests
}

run_auth_integration_tests() {
    log_info "=========================================="
    log_info "    AUTHENTICATION INTEGRATION TESTS"
    log_info "=========================================="
    
    if check_middleware; then
        source "$SCRIPT_DIR/test_auth.sh"
        
        # Run middleware-dependent auth tests
        test_login_invalid_credentials
        test_successful_login
        test_auth_status_after_login
        test_logout
        test_auth_status_after_logout
        test_logout_when_not_logged_in
    else
        log_warning "Skipping authentication integration tests (middleware not available)"
        log_info "To run these tests, start middleware: cd $CLI_ROOT/../middleware && ./go start"
    fi
}

run_error_handling_tests() {
    log_info "=========================================="
    log_info "       ERROR HANDLING TESTS"
    log_info "=========================================="
    
    source "$SCRIPT_DIR/test_error_handling.sh"
    run_error_handling_tests
}

run_all_tests() {
    log_info "Running complete CLI test suite..."
    
    run_basic_tests
    run_config_tests
    run_error_handling_tests
    run_auth_integration_tests
}

# Parse command line arguments
usage() {
    echo "Usage: $0 [OPTIONS] [TEST_CATEGORY]"
    echo ""
    echo "Test Categories:"
    echo "  basic        - Basic CLI functionality (help, version, etc.)"
    echo "  config       - Configuration management tests"  
    echo "  auth         - Authentication tests (requires middleware)"
    echo "  errors       - Error handling and edge cases"
    echo "  all          - Run all tests (default)"
    echo ""
    echo "Options:"
    echo "  -h, --help   - Show this help"
    echo "  -v, --verbose - Verbose output"
    echo "  --cli-binary PATH - Path to CLI binary (default: ./bin/rediacc)"
    echo "  --middleware-url URL - Middleware URL (default: http://localhost:8080)"
    echo ""
    echo "Environment Variables:"
    echo "  CLI_BINARY          - Path to CLI binary"
    echo "  MIDDLEWARE_URL      - Middleware server URL"
    echo ""
    echo "Examples:"
    echo "  $0                  # Run all tests"
    echo "  $0 basic            # Run only basic tests"
    echo "  $0 auth             # Run only auth tests"
    echo "  $0 --cli-binary ./my-cli all  # Use custom CLI binary"
}

# Main execution
main() {
    local test_category="all"
    local verbose=false
    
    # Parse arguments
    while [[ $# -gt 0 ]]; do
        case $1 in
            -h|--help)
                usage
                exit 0
                ;;
            -v|--verbose)
                verbose=true
                shift
                ;;
            --cli-binary)
                export CLI_BINARY="$2"
                shift 2
                ;;
            --middleware-url)
                export MIDDLEWARE_URL="$2"
                shift 2
                ;;
            basic|config|auth|errors|all)
                test_category="$1"
                shift
                ;;
            *)
                log_error "Unknown argument: $1"
                usage
                exit 1
                ;;
        esac
    done
    
    # Print test configuration
    log_info "=========================================="
    log_info "      REDIACC CLI TEST RUNNER"
    log_info "=========================================="
    log_info "CLI Binary: $CLI_BINARY"
    log_info "Middleware URL: $MIDDLEWARE_URL"
    log_info "Test Category: $test_category"
    log_info "Test Config: $TEST_CONFIG_FILE"
    log_info "=========================================="
    
    # Set up test environment
    setup_test_environment
    
    # Ensure CLI binary exists and is executable
    if [ ! -f "$CLI_BINARY" ]; then
        log_error "CLI binary not found: $CLI_BINARY"
        log_info "Please build the CLI first:"
        log_info "  cd $CLI_ROOT && go build -o bin/rediacc main.go"
        exit 1
    fi
    
    if [ ! -x "$CLI_BINARY" ]; then
        log_error "CLI binary is not executable: $CLI_BINARY"
        log_info "Please make it executable:"
        log_info "  chmod +x $CLI_BINARY"
        exit 1
    fi
    
    # Run selected tests
    case $test_category in
        basic)
            run_basic_tests
            ;;
        config)
            run_config_tests
            ;;
        auth)
            run_auth_integration_tests
            ;;
        errors)
            run_error_handling_tests
            ;;
        all)
            run_all_tests
            ;;
        *)
            log_error "Unknown test category: $test_category"
            usage
            exit 1
            ;;
    esac
    
    # Clean up and show results
    cleanup_test_environment
    print_test_summary
}

# Run main function
main "$@"