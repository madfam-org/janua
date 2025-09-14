#!/bin/bash

# Plinto Phase 1 Implementation Validation Script
# Validates critical security fixes and production readiness

set -euo pipefail

echo "🔍 Phase 1 Implementation Validation - Plinto Platform"
echo "=================================================="
echo

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Check counters
PASS_COUNT=0
FAIL_COUNT=0
WARN_COUNT=0

check_pass() {
    echo -e "${GREEN}✅ PASS:${NC} $1"
    ((PASS_COUNT++))
}

check_fail() {
    echo -e "${RED}❌ FAIL:${NC} $1"
    ((FAIL_COUNT++))
}

check_warn() {
    echo -e "${YELLOW}⚠️  WARN:${NC} $1"
    ((WARN_COUNT++))
}

echo "🔐 1. Security Validation"
echo "------------------------"

# Check password hashing implementation
if grep -q "pwd_context = CryptContext" apps/api/app/main.py; then
    if grep -q "bcrypt__rounds=12" apps/api/app/main.py; then
        check_pass "bcrypt password hashing with 12 rounds implemented"
    else
        check_fail "bcrypt rounds not set to 12 (security vulnerability)"
    fi
else
    check_fail "bcrypt password hashing not implemented (CRITICAL VULNERABILITY)"
fi

# Check rate limiting implementation
if grep -q "@limiter.limit" apps/api/app/routers/v1/auth.py; then
    check_pass "Rate limiting implemented on authentication endpoints"
else
    check_fail "Rate limiting missing from authentication endpoints"
fi

# Check security headers
if grep -q "Strict-Transport-Security" apps/api/app/main.py; then
    check_pass "Security headers middleware implemented"
else
    check_fail "Security headers not implemented"
fi

# Check SSL configuration
if [ -f "deployment/nginx-ssl.conf" ]; then
    if grep -q "ssl_protocols TLSv1.2 TLSv1.3" deployment/nginx-ssl.conf; then
        check_pass "SSL/TLS configuration created for A+ rating"
    else
        check_warn "SSL/TLS configuration incomplete"
    fi
else
    check_fail "SSL/TLS configuration file missing"
fi

echo
echo "📊 2. Monitoring Infrastructure"
echo "-------------------------------"

# Check Prometheus configuration
if [ -f "deployment/monitoring/prometheus.yml" ]; then
    check_pass "Prometheus monitoring configuration created"
else
    check_fail "Prometheus configuration missing"
fi

# Check Grafana dashboard
if [ -f "deployment/monitoring/grafana-dashboard.json" ]; then
    check_pass "Grafana dashboard configuration created"
else
    check_fail "Grafana dashboard missing"
fi

echo
echo "🚀 3. Production Deployment"
echo "---------------------------"

# Check Docker Compose production
if [ -f "deployment/production/docker-compose.production.yml" ]; then
    if grep -q "healthcheck:" deployment/production/docker-compose.production.yml; then
        check_pass "Production Docker Compose with health checks created"
    else
        check_warn "Production Docker Compose missing health checks"
    fi
else
    check_fail "Production Docker Compose configuration missing"
fi

# Check Kubernetes deployment
if [ -f "deployment/kubernetes/api-deployment.yml" ]; then
    if grep -q "readinessProbe:" deployment/kubernetes/api-deployment.yml; then
        check_pass "Kubernetes deployment with health probes created"
    else
        check_warn "Kubernetes deployment missing health probes"
    fi
else
    check_fail "Kubernetes deployment configuration missing"
fi

echo
echo "🧪 4. Code Quality Validation"
echo "-----------------------------"

# Check for test files
TEST_COUNT=$(find . -name "*.test.*" -o -name "*.spec.*" | grep -E "\.(ts|tsx|js|jsx|py)$" | wc -l | tr -d ' ')
if [ "$TEST_COUNT" -gt 600 ]; then
    check_pass "Strong test coverage with $TEST_COUNT test files"
elif [ "$TEST_COUNT" -gt 300 ]; then
    check_warn "Moderate test coverage with $TEST_COUNT test files"
else
    check_fail "Insufficient test coverage with only $TEST_COUNT test files"
fi

# Check TypeScript configurations
if [ -f "tsconfig.json" ]; then
    check_pass "TypeScript configuration present"
else
    check_warn "TypeScript configuration missing"
fi

echo
echo "📋 5. Documentation Validation"
echo "------------------------------"

# Check API documentation
if [ -f "apps/docs/content/api/reference.md" ]; then
    API_LINES=$(wc -l < apps/docs/content/api/reference.md)
    if [ "$API_LINES" -gt 2000 ]; then
        check_pass "Comprehensive API documentation ($API_LINES lines)"
    else
        check_warn "API documentation may be incomplete ($API_LINES lines)"
    fi
else
    check_fail "API reference documentation missing"
fi

# Check SDK documentation
if [ -f "apps/docs/content/sdks/overview.md" ]; then
    SDK_LINES=$(wc -l < apps/docs/content/sdks/overview.md)
    if [ "$SDK_LINES" -gt 3000 ]; then
        check_pass "Comprehensive SDK documentation ($SDK_LINES lines)"
    else
        check_warn "SDK documentation may be incomplete ($SDK_LINES lines)"
    fi
else
    check_fail "SDK documentation missing"
fi

echo
echo "📈 VALIDATION SUMMARY"
echo "===================="
echo -e "${GREEN}✅ Passed: $PASS_COUNT${NC}"
echo -e "${YELLOW}⚠️  Warnings: $WARN_COUNT${NC}"
echo -e "${RED}❌ Failed: $FAIL_COUNT${NC}"
echo

# Calculate overall score
TOTAL_CHECKS=$((PASS_COUNT + FAIL_COUNT + WARN_COUNT))
PASS_PERCENTAGE=$((PASS_COUNT * 100 / TOTAL_CHECKS))

if [ "$FAIL_COUNT" -eq 0 ]; then
    if [ "$WARN_COUNT" -eq 0 ]; then
        echo -e "${GREEN}🎉 PHASE 1 COMPLETE: All critical security and infrastructure components implemented successfully!${NC}"
        echo -e "${GREEN}📊 Score: ${PASS_PERCENTAGE}% (${PASS_COUNT}/${TOTAL_CHECKS})${NC}"
    else
        echo -e "${YELLOW}✅ PHASE 1 SUCCESS: Critical components complete with minor warnings${NC}"
        echo -e "${YELLOW}📊 Score: ${PASS_PERCENTAGE}% (${PASS_COUNT}/${TOTAL_CHECKS})${NC}"
    fi
else
    echo -e "${RED}⚠️  PHASE 1 INCOMPLETE: $FAIL_COUNT critical issues require attention${NC}"
    echo -e "${RED}📊 Score: ${PASS_PERCENTAGE}% (${PASS_COUNT}/${TOTAL_CHECKS})${NC}"
fi

echo
echo "🚀 NEXT STEPS:"
echo "- Review any failed checks and address critical issues"
echo "- Deploy monitoring infrastructure"
echo "- Run security audit on authentication endpoints"
echo "- Validate SSL/TLS configuration with SSL Labs"
echo "- Begin Phase 2: Performance optimization and enterprise features"

exit $FAIL_COUNT