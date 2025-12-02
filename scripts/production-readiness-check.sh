#!/bin/bash

# Janua Production Readiness Automated Check
# This script performs comprehensive health checks for production readiness
# Run: bash scripts/production-readiness-check.sh

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
API_URL="${API_URL:-http://localhost:8000}"
STAGING_URL="${STAGING_URL:-https://staging.api.janua.dev}"
PROD_URL="${PROD_URL:-https://api.janua.dev}"
MIN_ALPHA_SCORE=60
MIN_BETA_SCORE=80

# Counters
READY_COUNT=0
TOTAL_COUNT=0
CRITICAL_FAIL=0

echo -e "${BLUE}╔══════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║        Janua Production Readiness Assessment            ║${NC}"
echo -e "${BLUE}╚══════════════════════════════════════════════════════════╝${NC}"
echo -e "Date: $(date)"
echo -e "Environment: ${JANUA_ENV:-development}\n"

# Function to check a requirement
check_requirement() {
    local name="$1"
    local command="$2"
    local critical="${3:-false}"
    
    TOTAL_COUNT=$((TOTAL_COUNT + 1))
    
    if eval "$command" 2>/dev/null; then
        echo -e "${GREEN}✅${NC} $name"
        READY_COUNT=$((READY_COUNT + 1))
        return 0
    else
        if [ "$critical" = "true" ]; then
            echo -e "${RED}❌ [CRITICAL]${NC} $name"
            CRITICAL_FAIL=$((CRITICAL_FAIL + 1))
        else
            echo -e "${YELLOW}⚠️${NC} $name"
        fi
        return 1
    fi
}

# Function to check with score
check_with_score() {
    local category="$1"
    local checks="$2"
    local weight="$3"
    
    echo -e "\n${BLUE}━━━ $category (Weight: $weight%) ━━━${NC}"
    
    local category_total=0
    local category_ready=0
    local old_total=$TOTAL_COUNT
    local old_ready=$READY_COUNT
    
    eval "$checks"
    
    category_total=$((TOTAL_COUNT - old_total))
    category_ready=$((READY_COUNT - old_ready))
    
    if [ $category_total -gt 0 ]; then
        local percentage=$((category_ready * 100 / category_total))
        echo -e "Category Score: $category_ready/$category_total (${percentage}%)"
    fi
}

# 1. INFRASTRUCTURE CHECKS
infrastructure_checks() {
    check_requirement "Local development environment running" "curl -s -o /dev/null -w '%{http_code}' $API_URL/health | grep -qE '200|301|302'" true
    check_requirement "PostgreSQL database connected" "cd apps/api && python -c 'from app.core.database import engine; print(\"connected\")' 2>/dev/null | grep -q connected"
    check_requirement "Redis cache available" "python -c 'import redis; r=redis.Redis(); r.ping()' 2>/dev/null"
    check_requirement "Environment variables configured" "test -f apps/api/.env"
    check_requirement "Production deployment configured" "test -f deployment/production/docker-compose.production.yml || test -f Dockerfile.api"
    check_requirement "Staging environment defined" "grep -q STAGING .github/workflows/*.yml 2>/dev/null"
    check_requirement "Domain configured" "grep -qE 'janua\.(dev|io|com)' apps/*/package.json 2>/dev/null"
}

# 2. SECURITY CHECKS
security_checks() {
    check_requirement "JWT authentication implemented" "grep -q 'JWTService' apps/api/app/services/*.py" true
    check_requirement "Password hashing configured" "grep -q 'bcrypt\|argon2' apps/api/requirements.txt" true
    check_requirement "Rate limiting implemented" "grep -q 'RateLimitMiddleware' apps/api/app/middleware/*.py"
    check_requirement "CORS configuration present" "grep -q 'CORSMiddleware' apps/api/app/main.py"
    check_requirement "Input validation configured" "grep -q 'pydantic\|marshmallow' apps/api/requirements.txt"
    check_requirement "SQL injection protection (ORM)" "grep -q 'sqlalchemy' apps/api/requirements.txt" true
    check_requirement "Environment secrets separated" "! grep -q 'SECRET.*=.*[a-zA-Z0-9]' apps/api/app/**/*.py"
    check_requirement "Security headers middleware" "grep -q 'SecurityHeadersMiddleware' apps/api/app/middleware/*.py"
}

# 3. DATA MANAGEMENT CHECKS
data_checks() {
    check_requirement "Database migrations configured" "test -d apps/api/alembic" true
    check_requirement "Backup script exists" "test -f scripts/backup-database.sh"
    check_requirement "Database models defined" "test -f apps/api/app/models/user.py" true
    check_requirement "Transaction management" "grep -q 'async with.*session' apps/api/app/**/*.py"
    check_requirement "Data validation schemas" "test -f apps/api/app/schemas/user.py"
    check_requirement "Audit logging prepared" "grep -q 'AuditLogger' apps/api/app/services/*.py"
}

# 4. PERFORMANCE CHECKS
performance_checks() {
    check_requirement "Database connection pooling" "grep -q 'pool_size' apps/api/app/core/database.py"
    check_requirement "Async request handling" "grep -q 'async def' apps/api/app/api/**/*.py"
    check_requirement "Caching layer configured" "grep -q 'redis\|cache' apps/api/app/**/*.py"
    check_requirement "Pagination implemented" "grep -q 'limit.*offset\|page.*per_page' apps/api/app/**/*.py"
    check_requirement "Query optimization" "grep -q 'joinedload\|selectinload' apps/api/app/**/*.py"
    check_requirement "Response compression" "grep -q 'GZipMiddleware' apps/api/app/main.py"
}

# 5. MONITORING CHECKS
monitoring_checks() {
    check_requirement "Health check endpoint" "test -f apps/api/app/api/health.py" true
    check_requirement "Logging configured" "grep -q 'logging\|logger' apps/api/app/**/*.py"
    check_requirement "Error tracking setup" "grep -q 'sentry\|rollbar' apps/api/requirements.txt"
    check_requirement "Metrics collection" "grep -q 'prometheus\|statsd' apps/api/requirements.txt"
    check_requirement "Structured logging" "grep -q 'structlog\|python-json-logger' apps/api/requirements.txt"
    check_requirement "Request ID tracking" "grep -q 'request_id\|correlation_id' apps/api/app/**/*.py"
}

# 6. USER EXPERIENCE CHECKS
ux_checks() {
    check_requirement "User registration flow" "test -f apps/api/app/api/auth/register.py"
    check_requirement "User login flow" "test -f apps/api/app/api/auth/login.py" true
    check_requirement "Password reset flow" "grep -q 'reset_password\|forgot_password' apps/api/app/**/*.py"
    check_requirement "Email templates" "test -d apps/api/templates || grep -q 'email.*template' apps/api/app/**/*.py"
    check_requirement "Frontend routing" "test -f apps/dashboard/app/layout.tsx" true
    check_requirement "Error boundaries" "grep -q 'ErrorBoundary\|error.tsx' apps/dashboard/**/*.tsx"
    check_requirement "Loading states" "grep -q 'loading\|Skeleton\|Spinner' apps/dashboard/**/*.tsx"
}

# 7. API & INTEGRATION CHECKS
api_checks() {
    check_requirement "OpenAPI documentation" "grep -q 'openapi\|swagger' apps/api/app/main.py"
    check_requirement "API versioning" "grep -qE 'v[0-9]+' apps/api/app/api/*.py"
    check_requirement "SDK available" "test -d packages/sdk"
    check_requirement "CORS headers" "grep -q 'allow_origins' apps/api/app/main.py"
    check_requirement "Request validation" "grep -q 'BaseModel\|Schema' apps/api/app/schemas/*.py"
    check_requirement "Response serialization" "grep -q 'response_model' apps/api/app/api/**/*.py"
}

# 8. TESTING CHECKS
testing_checks() {
    check_requirement "Backend test files exist" "test -d apps/api/tests" true
    check_requirement "Frontend test files exist" "test -f jest.config.js" true
    check_requirement "Test configuration" "test -f apps/api/pytest.ini"
    check_requirement "CI/CD pipeline configured" "test -f .github/workflows/test.yml" true
    check_requirement "E2E test setup" "test -f playwright.config.ts"
    check_requirement "Test coverage reporting" "grep -q 'pytest-cov\|coverage' apps/api/requirements*.txt"
    
    # Try to get actual coverage if possible
    if command -v python >/dev/null 2>&1; then
        echo -e "\n${BLUE}Test Coverage Analysis:${NC}"
        cd apps/api 2>/dev/null && python -m pytest --cov=app --cov-report=term-missing --tb=no -q 2>/dev/null | grep -E 'TOTAL|app' || echo "  Coverage data not available"
        cd - >/dev/null 2>&1
    fi
}

# 9. OPERATIONS CHECKS
operations_checks() {
    check_requirement "CI/CD workflows exist" "test -f .github/workflows/ci.yml" true
    check_requirement "Deployment configuration" "test -f deployment/production/docker-compose.production.yml || test -f Dockerfile.api"
    check_requirement "Environment management" "test -f .env.example"
    check_requirement "Database migration scripts" "test -f apps/api/alembic.ini"
    check_requirement "Monitoring configuration" "grep -q 'health\|metrics' apps/api/app/**/*.py"
    check_requirement "Backup procedures documented" "test -f docs/deployment/BACKUP_PROCEDURES.md || test -f scripts/backup-database.sh"
}

# 10. DOCUMENTATION CHECKS
documentation_checks() {
    check_requirement "README exists" "test -f README.md" true
    check_requirement "API documentation" "test -f docs/api/API_REFERENCE.md || grep -q 'openapi' apps/api/app/main.py"
    check_requirement "Setup instructions" "grep -q 'Installation\|Setup\|Getting Started' README.md"
    check_requirement "Architecture documentation" "test -f docs/architecture/ARCHITECTURE.md"
    check_requirement "Security documentation" "test -f docs/security/SECURITY.md || test -f SECURITY.md"
    check_requirement "Contributing guidelines" "test -f CONTRIBUTING.md"
}

# Run all checks
check_with_score "Infrastructure & Deployment" infrastructure_checks 20
check_with_score "Security & Compliance" security_checks 25
check_with_score "Data Management" data_checks 15
check_with_score "Performance & Scalability" performance_checks 10
check_with_score "Monitoring & Observability" monitoring_checks 10
check_with_score "User Experience" ux_checks 10
check_with_score "API & Integration" api_checks 5
check_with_score "Testing" testing_checks 10
check_with_score "Operations" operations_checks 10
check_with_score "Documentation" documentation_checks 5

# Calculate final score
echo -e "\n${BLUE}══════════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}                    ASSESSMENT SUMMARY                      ${NC}"
echo -e "${BLUE}══════════════════════════════════════════════════════════${NC}\n"

PERCENTAGE=$((READY_COUNT * 100 / TOTAL_COUNT))

echo -e "Total Checks: $TOTAL_COUNT"
echo -e "Passed: ${GREEN}$READY_COUNT${NC}"
echo -e "Failed: ${RED}$((TOTAL_COUNT - READY_COUNT))${NC}"
echo -e "Critical Failures: ${RED}$CRITICAL_FAIL${NC}"
echo -e "\nOverall Score: ${PERCENTAGE}%"

# Progress bar
echo -ne "\nProgress: ["
for i in $(seq 1 20); do
    if [ $((i * 5)) -le $PERCENTAGE ]; then
        echo -ne "█"
    else
        echo -ne "░"
    fi
done
echo -e "] ${PERCENTAGE}%"

# Readiness verdict
echo -e "\n${BLUE}══════════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}                    READINESS VERDICT                       ${NC}"
echo -e "${BLUE}══════════════════════════════════════════════════════════${NC}\n"

if [ $CRITICAL_FAIL -gt 0 ]; then
    echo -e "${RED}🔴 CRITICAL FAILURES DETECTED${NC}"
    echo -e "Cannot proceed to any user onboarding until critical issues are resolved.\n"
elif [ $PERCENTAGE -ge $MIN_BETA_SCORE ]; then
    echo -e "${GREEN}🟢 READY FOR BETA USERS${NC}"
    echo -e "Platform meets requirements for beta user onboarding.\n"
elif [ $PERCENTAGE -ge $MIN_ALPHA_SCORE ]; then
    echo -e "${YELLOW}🟡 READY FOR ALPHA USERS${NC}"
    echo -e "Platform meets minimum requirements for alpha testing.\n"
else
    echo -e "${RED}🔴 NOT READY FOR USERS${NC}"
    echo -e "Significant work required before user onboarding.\n"
fi

# Recommendations
echo -e "${BLUE}Key Recommendations:${NC}"
if [ $PERCENTAGE -lt 40 ]; then
    echo "1. Deploy to production environment (highest priority)"
    echo "2. Implement authentication and security features"
    echo "3. Setup monitoring and error tracking"
    echo "4. Create comprehensive test suite"
    echo "5. Document API and user flows"
elif [ $PERCENTAGE -lt 60 ]; then
    echo "1. Complete security implementation"
    echo "2. Setup database backups and recovery"
    echo "3. Implement comprehensive monitoring"
    echo "4. Increase test coverage to 60%+"
    echo "5. Create user documentation"
elif [ $PERCENTAGE -lt 80 ]; then
    echo "1. Implement advanced security (2FA, audit logs)"
    echo "2. Setup multi-region deployment"
    echo "3. Complete API documentation"
    echo "4. Achieve 80%+ test coverage"
    echo "5. Conduct security audit"
else
    echo "1. Conduct penetration testing"
    echo "2. Optimize performance metrics"
    echo "3. Complete disaster recovery planning"
    echo "4. Achieve 90%+ test coverage"
    echo "5. Prepare for scale"
fi

# Export results
REPORT_FILE="production-readiness-report-$(date +%Y%m%d-%H%M%S).json"
cat > "$REPORT_FILE" << EOF
{
  "timestamp": "$(date -u +"%Y-%m-%dT%H:%M:%SZ")",
  "environment": "${JANUA_ENV:-development}",
  "total_checks": $TOTAL_COUNT,
  "passed_checks": $READY_COUNT,
  "failed_checks": $((TOTAL_COUNT - READY_COUNT)),
  "critical_failures": $CRITICAL_FAIL,
  "percentage": $PERCENTAGE,
  "alpha_ready": $([ $PERCENTAGE -ge $MIN_ALPHA_SCORE ] && [ $CRITICAL_FAIL -eq 0 ] && echo "true" || echo "false"),
  "beta_ready": $([ $PERCENTAGE -ge $MIN_BETA_SCORE ] && [ $CRITICAL_FAIL -eq 0 ] && echo "true" || echo "false")
}
EOF

echo -e "\n${BLUE}Report saved to: $REPORT_FILE${NC}"
echo -e "\nRun this check daily: ${GREEN}bash scripts/production-readiness-check.sh${NC}"

# Exit with appropriate code
if [ $CRITICAL_FAIL -gt 0 ]; then
    exit 2
elif [ $PERCENTAGE -lt $MIN_ALPHA_SCORE ]; then
    exit 1
else
    exit 0
fi