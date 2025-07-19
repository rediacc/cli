#!/bin/bash
# Example script showing how to run tests in parallel with different credentials

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}=== Parallel Test Runner Example ===${NC}"
echo "This script demonstrates running tests in parallel with unique credentials"
echo

# Function to create a test company and run tests
run_test_instance() {
    local instance_id=$1
    local test_suite=$2
    
    echo -e "${BLUE}[Instance $instance_id] Creating test company...${NC}"
    
    # Create company and capture credentials
    output=$(python3 setup_test_company.py 2>&1)
    
    # Extract JSON credentials from output
    json_creds=$(echo "$output" | grep -A1 "JSON format:" | tail -n1)
    
    if [ -z "$json_creds" ] || [[ ! "$json_creds" =~ ^\{ ]]; then
        echo -e "${RED}[Instance $instance_id] Failed to create test company${NC}"
        echo "$output"
        return 1
    fi
    
    # Extract email and password from JSON
    email=$(echo "$json_creds" | python3 -c "import sys, json; print(json.load(sys.stdin)['email'])")
    password=$(echo "$json_creds" | python3 -c "import sys, json; print(json.load(sys.stdin)['password'])")
    
    echo -e "${GREEN}[Instance $instance_id] Created company with user: $email${NC}"
    
    # Run tests with these credentials
    echo -e "${BLUE}[Instance $instance_id] Running $test_suite tests...${NC}"
    python3 -m tests_yaml.run --suite "$test_suite" --username "$email" --password "$password"
    
    echo -e "${GREEN}[Instance $instance_id] Completed${NC}"
}

# Example: Run 3 test instances in parallel
echo "Starting 3 parallel test instances..."
echo

# Run instances in background
run_test_instance 1 basic &
pid1=$!

run_test_instance 2 complex &
pid2=$!

run_test_instance 3 negative &
pid3=$!

# Wait for all instances to complete
echo "Waiting for all test instances to complete..."
wait $pid1 $pid2 $pid3

echo
echo -e "${GREEN}All test instances completed!${NC}"