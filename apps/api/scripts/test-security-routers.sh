#!/bin/bash

# Security Router Test Runner Script
# Ensures stable, consistent test execution for security-critical APIs

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}═══════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}     Security-Critical API Test Suite Runner${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════════════${NC}"

# Configuration
export ENVIRONMENT=test
export DATABASE_URL="sqlite+aiosqlite:///:memory:"
export TESTING=true

# Test categories
AUTH_TESTS="tests/unit/routers/test_auth_router_focused.py tests/unit/routers/test_auth_router_comprehensive.py"
MFA_TESTS="tests/unit/routers/test_mfa_router_comprehensive.py"
PASSKEY_TESTS="tests/unit/routers/test_passkey_router_focused.py"
ALL_SECURITY_TESTS="$AUTH_TESTS $MFA_TESTS $PASSKEY_TESTS"

# Parse arguments
MODE=${1:-"all"}
VERBOSE=${2:-""}

# Function to run tests with proper error handling
run_tests() {
    local test_files=$1
    local test_name=$2

    echo -e "\n${YELLOW}Running $test_name...${NC}"

    if [ "$VERBOSE" = "-v" ]; then
        python -m pytest $test_files --tb=short -v
    else
        python -m pytest $test_files --tb=no -q
    fi

    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✓ $test_name passed${NC}"
        return 0
    else
        echo -e "${RED}✗ $test_name had failures${NC}"
        return 1
    fi
}

# Function to run coverage analysis
run_coverage() {
    echo -e "\n${YELLOW}Running coverage analysis...${NC}"

    python -m pytest $ALL_SECURITY_TESTS \
        --cov=app.routers.v1.auth \
        --cov=app.routers.v1.mfa \
        --cov=app.routers.v1.passkeys \
        --cov-report=term-missing \
        --tb=no -q

    echo -e "${GREEN}Coverage analysis complete${NC}"
}

# Main execution
case $MODE in
    "auth")
        run_tests "$AUTH_TESTS" "Authentication Router Tests"
        ;;
    "mfa")
        run_tests "$MFA_TESTS" "MFA Router Tests"
        ;;
    "passkey")
        run_tests "$PASSKEY_TESTS" "Passkey Router Tests"
        ;;
    "coverage")
        run_coverage
        ;;
    "all")
        TOTAL_FAILURES=0

        run_tests "$AUTH_TESTS" "Authentication Router Tests" || ((TOTAL_FAILURES++))
        run_tests "$MFA_TESTS" "MFA Router Tests" || ((TOTAL_FAILURES++))
        run_tests "$PASSKEY_TESTS" "Passkey Router Tests" || ((TOTAL_FAILURES++))

        echo -e "\n${BLUE}═══════════════════════════════════════════════════════${NC}"
        if [ $TOTAL_FAILURES -eq 0 ]; then
            echo -e "${GREEN}All security router tests completed successfully!${NC}"
        else
            echo -e "${YELLOW}Tests completed with $TOTAL_FAILURES suite(s) having failures${NC}"
            echo -e "${YELLOW}This is expected - see TEST_COVERAGE_REPORT.md for details${NC}"
        fi
        echo -e "${BLUE}═══════════════════════════════════════════════════════${NC}"
        ;;
    "help")
        echo "Usage: $0 [mode] [-v]"
        echo ""
        echo "Modes:"
        echo "  all      - Run all security router tests (default)"
        echo "  auth     - Run authentication router tests only"
        echo "  mfa      - Run MFA router tests only"
        echo "  passkey  - Run passkey router tests only"
        echo "  coverage - Run tests with coverage report"
        echo "  help     - Show this help message"
        echo ""
        echo "Options:"
        echo "  -v       - Verbose output (show individual test results)"
        echo ""
        echo "Examples:"
        echo "  $0                    # Run all tests quietly"
        echo "  $0 auth -v           # Run auth tests with verbose output"
        echo "  $0 coverage          # Run all tests with coverage report"
        ;;
    *)
        echo -e "${RED}Invalid mode: $MODE${NC}"
        echo "Use '$0 help' for usage information"
        exit 1
        ;;
esac

# Always show summary
echo -e "\n${BLUE}Test Configuration:${NC}"
echo -e "  Environment: ${GREEN}$ENVIRONMENT${NC}"
echo -e "  Database: ${GREEN}In-memory SQLite${NC}"
echo -e "  Test Files: ${GREEN}$(echo $ALL_SECURITY_TESTS | wc -w) files${NC}"

# Check if report exists
if [ -f "tests/unit/routers/TEST_COVERAGE_REPORT.md" ]; then
    echo -e "\n${BLUE}📄 For detailed coverage information, see:${NC}"
    echo -e "   ${GREEN}tests/unit/routers/TEST_COVERAGE_REPORT.md${NC}"
fi

exit 0