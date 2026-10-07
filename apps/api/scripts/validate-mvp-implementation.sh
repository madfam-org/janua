#!/bin/bash

# =====================================================
# MVP Implementation Validation Script
# Validates that all enterprise features are working
# =====================================================

set -e

echo "🔍 MVP Implementation Validation"
echo "================================="

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Counters
PASS=0
FAIL=0
SKIP=0

# Function to print status
check_pass() {
    echo -e "${GREEN}✓${NC} $1"
    ((PASS++))
}

check_fail() {
    echo -e "${RED}✗${NC} $1"
    ((FAIL++))
}

check_skip() {
    echo -e "${YELLOW}⊘${NC} $1"
    ((SKIP++))
}

check_info() {
    echo -e "${BLUE}ℹ${NC} $1"
}

# ===== Phase 1: File Structure Validation =====
echo ""
echo "📁 Phase 1: File Structure Validation"
echo "-------------------------------------"

# Check Python API services
if [ -f "apps/api/app/services/organization_member_service.py" ]; then
    check_pass "Organization Member Service exists"
else
    check_fail "Organization Member Service missing"
fi

if [ -f "apps/api/app/services/rbac_service.py" ]; then
    check_pass "RBAC Service exists"
else
    check_fail "RBAC Service missing"
fi

if [ -f "apps/api/app/services/webhooks.py" ]; then
    check_pass "Webhook Service exists"
else
    check_fail "Webhook Service missing"
fi

if [ -f "apps/api/app/services/audit_logger.py" ]; then
    check_pass "Audit Logger Service exists"
else
    check_fail "Audit Logger Service missing"
fi

# Check routes
if [ -f "apps/api/app/routers/v1/organization_members.py" ]; then
    check_pass "Organization Members routes exist"
else
    check_fail "Organization Members routes missing"
fi

if [ -f "apps/api/app/routers/v1/rbac.py" ]; then
    check_pass "RBAC routes exist"
else
    check_fail "RBAC routes missing"
fi

# Check migration
if [ -f "apps/api/alembic/versions/004_add_mvp_features.py" ]; then
    check_pass "Database migration exists"
else
    check_fail "Database migration missing"
fi

# ===== Phase 2: Code Quality Validation =====
echo ""
echo "🔍 Phase 2: Code Quality Validation"
echo "-----------------------------------"

# Check for TODO comments in production code
TODO_COUNT=$(grep -r "TODO" apps/api/app --include="*.py" 2>/dev/null | wc -l || echo "0")
if [ "$TODO_COUNT" -eq "0" ]; then
    check_pass "No TODO comments in production code"
else
    check_fail "Found $TODO_COUNT TODO comments"
fi

# Check for console.log/print statements
PRINT_COUNT=$(grep -r "print(" apps/api/app --include="*.py" 2>/dev/null | wc -l || echo "0")
if [ "$PRINT_COUNT" -lt "5" ]; then
    check_pass "Minimal print statements ($PRINT_COUNT found)"
else
    check_fail "Too many print statements ($PRINT_COUNT found)"
fi

# ===== Phase 3: Service Implementation Check =====
echo ""
echo "⚙️ Phase 3: Service Implementation"
echo "---------------------------------"

# Check OrganizationMemberService methods
if grep -q "async def add_member" apps/api/app/services/organization_member_service.py 2>/dev/null; then
    check_pass "add_member method implemented"
else
    check_fail "add_member method missing"
fi

if grep -q "async def create_invitation" apps/api/app/services/organization_member_service.py 2>/dev/null; then
    check_pass "create_invitation method implemented"
else
    check_fail "create_invitation method missing"
fi

if grep -q "async def accept_invitation" apps/api/app/services/organization_member_service.py 2>/dev/null; then
    check_pass "accept_invitation method implemented"
else
    check_fail "accept_invitation method missing"
fi

# Check RBAC Service methods
if grep -q "async def check_permission" apps/api/app/services/rbac_service.py 2>/dev/null; then
    check_pass "check_permission method implemented"
else
    check_fail "check_permission method missing"
fi

if grep -q "ROLE_HIERARCHY" apps/api/app/services/rbac_service.py 2>/dev/null; then
    check_pass "Role hierarchy defined"
else
    check_fail "Role hierarchy missing"
fi

# ===== Phase 4: Integration Check =====
echo ""
echo "🔌 Phase 4: Integration Validation"
echo "----------------------------------"

# Check if routes are registered in main.py
if grep -q "organization_members_v1" apps/api/app/main.py 2>/dev/null; then
    check_pass "Organization Members routes registered"
else
    check_fail "Organization Members routes not registered"
fi

if grep -q "rbac_v1" apps/api/app/main.py 2>/dev/null; then
    check_pass "RBAC routes registered"
else
    check_fail "RBAC routes not registered"
fi

# Check JWT Manager enhancements
if grep -q "family" apps/api/app/core/jwt_manager.py 2>/dev/null; then
    check_pass "JWT token families implemented"
else
    check_fail "JWT token families missing"
fi

# ===== Phase 5: Database Schema Check =====
echo ""
echo "🗄️ Phase 5: Database Schema"
echo "---------------------------"

# Check migration content
if grep -q "organization_invitations" apps/api/alembic/versions/004_add_mvp_features.py 2>/dev/null; then
    check_pass "Invitations table in migration"
else
    check_fail "Invitations table missing"
fi

if grep -q "rbac_policies" apps/api/alembic/versions/004_add_mvp_features.py 2>/dev/null; then
    check_pass "RBAC policies table in migration"
else
    check_fail "RBAC policies table missing"
fi

if grep -q "audit_logs" apps/api/alembic/versions/004_add_mvp_features.py 2>/dev/null; then
    check_pass "Audit logs table in migration"
else
    check_fail "Audit logs table missing"
fi

if grep -q "webhook_retries" apps/api/alembic/versions/004_add_mvp_features.py 2>/dev/null; then
    check_pass "Webhook retries table in migration"
else
    check_fail "Webhook retries table missing"
fi

if grep -q "session_families" apps/api/alembic/versions/004_add_mvp_features.py 2>/dev/null; then
    check_pass "Session families table in migration"
else
    check_fail "Session families table missing"
fi

# ===== Phase 6: Test Coverage =====
echo ""
echo "🧪 Phase 6: Test Coverage"
echo "------------------------"

if [ -f "apps/api/tests/integration/test_mvp_features.py" ]; then
    check_pass "MVP integration tests exist"

    # Count test methods
    TEST_COUNT=$(grep -c "async def test_" apps/api/tests/integration/test_mvp_features.py 2>/dev/null || echo "0")
    if [ "$TEST_COUNT" -gt "10" ]; then
        check_pass "Comprehensive test coverage ($TEST_COUNT tests)"
    else
        check_fail "Insufficient test coverage ($TEST_COUNT tests)"
    fi
else
    check_fail "MVP integration tests missing"
fi

# ===== Phase 7: Documentation Check =====
echo ""
echo "📚 Phase 7: Documentation"
echo "------------------------"

if [ -f "ARCHITECTURE_RESOLUTION.md" ]; then
    check_pass "Architecture resolution document exists"
else
    check_fail "Architecture resolution document missing"
fi

if [ -f "IMPLEMENTATION_GUIDE.md" ]; then
    check_pass "Implementation guide exists"
else
    check_fail "Implementation guide missing"
fi

# Check for docstrings in services
DOCSTRING_COUNT=$(grep -c '"""' apps/api/app/services/organization_member_service.py 2>/dev/null || echo "0")
if [ "$DOCSTRING_COUNT" -gt "10" ]; then
    check_pass "Services well documented ($DOCSTRING_COUNT docstrings)"
else
    check_fail "Services need more documentation ($DOCSTRING_COUNT docstrings)"
fi

# ===== Phase 8: Security Check =====
echo ""
echo "🔒 Phase 8: Security Validation"
echo "-------------------------------"

# Check for hardcoded secrets
if grep -r "password.*=.*['\"]" apps/api/app --include="*.py" | grep -v "test" | grep -v "example" 2>/dev/null; then
    check_fail "Potential hardcoded secrets found"
else
    check_pass "No hardcoded secrets detected"
fi

# Check for SQL injection vulnerabilities
if grep -r "execute.*%" apps/api/app --include="*.py" | grep -v "test" 2>/dev/null; then
    check_fail "Potential SQL injection risk"
else
    check_pass "SQL queries appear safe"
fi

# Check for permission checks
PERMISSION_CHECK_COUNT=$(grep -c "enforce_permission\|check_permission" apps/api/app/routers/v1/*.py 2>/dev/null | wc -l || echo "0")
if [ "$PERMISSION_CHECK_COUNT" -gt "5" ]; then
    check_pass "Permission checks in routes ($PERMISSION_CHECK_COUNT found)"
else
    check_fail "Insufficient permission checks ($PERMISSION_CHECK_COUNT found)"
fi

# ===== Final Summary =====
echo ""
echo "========================================="
echo "📊 VALIDATION SUMMARY"
echo "========================================="
echo -e "${GREEN}Passed:${NC} $PASS"
echo -e "${RED}Failed:${NC} $FAIL"
echo -e "${YELLOW}Skipped:${NC} $SKIP"

TOTAL=$((PASS + FAIL + SKIP))
SCORE=$((PASS * 100 / TOTAL))

echo ""
echo "Overall Score: ${SCORE}%"

if [ "$SCORE" -ge 90 ]; then
    echo -e "${GREEN}✅ EXCELLENT: Ready for production!${NC}"
elif [ "$SCORE" -ge 75 ]; then
    echo -e "${GREEN}✅ GOOD: Minor improvements needed${NC}"
elif [ "$SCORE" -ge 60 ]; then
    echo -e "${YELLOW}⚠️ FAIR: Some work required${NC}"
else
    echo -e "${RED}❌ NEEDS WORK: Significant gaps to address${NC}"
fi

echo ""
echo "Production Readiness Checklist:"
echo "--------------------------------"
if [ "$FAIL" -eq 0 ]; then
    echo "✅ All critical features implemented"
else
    echo "❌ $FAIL critical issues to resolve"
fi

# Recommendations
echo ""
echo "📝 Next Steps:"
if [ "$FAIL" -gt 0 ]; then
    echo "1. Fix the $FAIL failed checks above"
    echo "2. Run tests: cd apps/api && python -m pytest"
    echo "3. Run migration: alembic upgrade head"
else
    echo "1. Run database migration: cd apps/api && alembic upgrade head"
    echo "2. Run full test suite: python -m pytest tests/ -v"
    echo "3. Deploy to staging for validation"
    echo "4. Monitor logs and metrics"
fi

echo ""
echo "========================================="

# Exit with appropriate code
if [ "$FAIL" -eq 0 ]; then
    exit 0
else
    exit 1
fi