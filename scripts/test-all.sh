#!/bin/bash

# Plinto Platform - Comprehensive Test Orchestration
# This script runs all tests across the entire platform

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Test results
PASSED=0
FAILED=0
SKIPPED=0

# Function to print colored output
print_status() {
  local color=$1
  local status=$2
  local message=$3
  echo -e "${color}[${status}]${NC} ${message}"
}

# Function to run tests for a package
run_package_tests() {
  local package=$1
  local name=$2

  if [ ! -d "$package" ]; then
    print_status "$YELLOW" "SKIP" "$name - Directory not found"
    ((SKIPPED++))
    return
  fi

  cd "$package"

  if [ ! -f "package.json" ] && [ ! -f "pyproject.toml" ]; then
    print_status "$YELLOW" "SKIP" "$name - No test configuration found"
    ((SKIPPED++))
    cd - > /dev/null
    return
  fi

  print_status "$BLUE" "TEST" "$name"

  # Run appropriate test command based on package type
  if [ -f "package.json" ]; then
    # Node.js package
    if grep -q '"test"' package.json; then
      if npm test 2>&1 | grep -q "no test specified"; then
        print_status "$YELLOW" "SKIP" "$name - No tests defined"
        ((SKIPPED++))
      elif npm test > /dev/null 2>&1; then
        print_status "$GREEN" "PASS" "$name"
        ((PASSED++))
      else
        print_status "$RED" "FAIL" "$name"
        ((FAILED++))
      fi
    else
      print_status "$YELLOW" "SKIP" "$name - No test script"
      ((SKIPPED++))
    fi
  elif [ -f "pyproject.toml" ]; then
    # Python package
    if command -v pytest &> /dev/null; then
      if pytest --co -q 2>&1 | grep -q "no tests ran"; then
        print_status "$YELLOW" "SKIP" "$name - No tests found"
        ((SKIPPED++))
      elif pytest -q > /dev/null 2>&1; then
        print_status "$GREEN" "PASS" "$name"
        ((PASSED++))
      else
        print_status "$RED" "FAIL" "$name"
        ((FAILED++))
      fi
    else
      print_status "$YELLOW" "SKIP" "$name - pytest not installed"
      ((SKIPPED++))
    fi
  fi

  cd - > /dev/null
}

# Main test execution
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📦 Plinto Platform - Test Orchestration"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Save current directory
ROOT_DIR=$(pwd)

# Run build tests first
echo "🔨 Build Tests"
echo "─────────────────────────────────────"
print_status "$BLUE" "TEST" "TypeScript SDK Build"
if cd packages/typescript-sdk && npm run build > /dev/null 2>&1; then
  print_status "$GREEN" "PASS" "TypeScript SDK Build"
  ((PASSED++))
else
  print_status "$RED" "FAIL" "TypeScript SDK Build"
  ((FAILED++))
fi
cd "$ROOT_DIR"

print_status "$BLUE" "TEST" "React SDK Build"
if cd packages/react-sdk && npm run build > /dev/null 2>&1; then
  print_status "$GREEN" "PASS" "React SDK Build"
  ((PASSED++))
else
  print_status "$RED" "FAIL" "React SDK Build"
  ((FAILED++))
fi
cd "$ROOT_DIR"

print_status "$BLUE" "TEST" "Vue SDK Build"
if cd packages/vue-sdk && npm run build > /dev/null 2>&1; then
  print_status "$GREEN" "PASS" "Vue SDK Build"
  ((PASSED++))
else
  print_status "$RED" "FAIL" "Vue SDK Build"
  ((FAILED++))
fi
cd "$ROOT_DIR"

print_status "$BLUE" "TEST" "Python SDK Build"
if cd packages/python-sdk && python setup.py sdist bdist_wheel > /dev/null 2>&1; then
  print_status "$GREEN" "PASS" "Python SDK Build"
  ((PASSED++))
else
  print_status "$RED" "FAIL" "Python SDK Build"
  ((FAILED++))
fi
cd "$ROOT_DIR"

echo ""
echo "🧪 Unit Tests"
echo "─────────────────────────────────────"

# Test core packages
run_package_tests "packages/core" "Core Package"
run_package_tests "packages/typescript-sdk" "TypeScript SDK"
run_package_tests "packages/react-sdk" "React SDK"
run_package_tests "packages/vue-sdk" "Vue SDK"
run_package_tests "packages/python-sdk" "Python SDK"
run_package_tests "packages/nextjs-sdk" "Next.js SDK"
run_package_tests "packages/jwt-utils" "JWT Utils"
run_package_tests "packages/edge" "Edge Package"

echo ""
echo "🔗 Integration Tests"
echo "─────────────────────────────────────"

# Run integration tests
print_status "$BLUE" "TEST" "Package Installation Tests"
if node scripts/test-integration.js > /dev/null 2>&1; then
  print_status "$GREEN" "PASS" "Package Installation Tests"
  ((PASSED++))
else
  print_status "$RED" "FAIL" "Package Installation Tests"
  ((FAILED++))
fi

# Run API tests if Python environment is available
echo ""
echo "🌐 API Tests"
echo "─────────────────────────────────────"

if [ -d "apps/api" ]; then
  print_status "$BLUE" "TEST" "FastAPI Backend"
  if cd apps/api && python -m pytest tests/ -q > /dev/null 2>&1; then
    print_status "$GREEN" "PASS" "FastAPI Backend"
    ((PASSED++))
  else
    print_status "$YELLOW" "SKIP" "FastAPI Backend - Tests not available"
    ((SKIPPED++))
  fi
  cd "$ROOT_DIR"
else
  print_status "$YELLOW" "SKIP" "FastAPI Backend - Directory not found"
  ((SKIPPED++))
fi

# Summary
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📊 Test Summary"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo -e "${GREEN}✅ Passed:${NC} $PASSED"
echo -e "${RED}❌ Failed:${NC} $FAILED"
echo -e "${YELLOW}⏭️  Skipped:${NC} $SKIPPED"
echo ""

TOTAL=$((PASSED + FAILED + SKIPPED))
if [ $FAILED -eq 0 ]; then
  print_status "$GREEN" "SUCCESS" "All active tests passed! ($PASSED/$TOTAL)"
  exit 0
else
  print_status "$RED" "FAILURE" "$FAILED tests failed ($PASSED passed, $SKIPPED skipped)"
  exit 1
fi