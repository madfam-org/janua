#!/bin/bash
# Enterprise Deployment Validation Script
# Validates deployment readiness for enterprise environments

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
API_URL="${API_URL:-http://localhost:8000}"
TIMEOUT="${TIMEOUT:-30}"
POSTGRES_HOST="${POSTGRES_HOST:-localhost}"
POSTGRES_PORT="${POSTGRES_PORT:-5432}"
REDIS_HOST="${REDIS_HOST:-localhost}"
REDIS_PORT="${REDIS_PORT:-6379}"

# Counters
TOTAL_CHECKS=0
PASSED_CHECKS=0
FAILED_CHECKS=0
WARNING_CHECKS=0

# Logging
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[PASS]${NC} $1"
    ((PASSED_CHECKS++))
}

log_warning() {
    echo -e "${YELLOW}[WARN]${NC} $1"
    ((WARNING_CHECKS++))
}

log_error() {
    echo -e "${RED}[FAIL]${NC} $1"
    ((FAILED_CHECKS++))
}

check_command() {
    ((TOTAL_CHECKS++))
    if command -v "$1" >/dev/null 2>&1; then
        log_success "Command '$1' is available"
        return 0
    else
        log_error "Command '$1' is not available"
        return 1
    fi
}

check_port() {
    ((TOTAL_CHECKS++))
    local host=$1
    local port=$2
    local service=$3

    if timeout 5 bash -c "</dev/tcp/$host/$port" 2>/dev/null; then
        log_success "$service is accessible on $host:$port"
        return 0
    else
        log_error "$service is not accessible on $host:$port"
        return 1
    fi
}

check_http_endpoint() {
    ((TOTAL_CHECKS++))
    local url=$1
    local description=$2
    local expected_status=${3:-200}

    if command -v curl >/dev/null 2>&1; then
        local status=$(curl -s -o /dev/null -w "%{http_code}" --max-time $TIMEOUT "$url" || echo "000")
        if [[ "$status" -eq "$expected_status" ]] || [[ "$status" -ge 200 && "$status" -lt 400 ]]; then
            log_success "$description (HTTP $status)"
            return 0
        else
            log_error "$description failed (HTTP $status)"
            return 1
        fi
    else
        log_warning "$description - curl not available, skipping"
        return 1
    fi
}

check_environment_variables() {
    log_info "Checking environment variables..."

    local required_vars=(
        "DATABASE_URL"
        "SECRET_KEY"
        "JWT_SECRET_KEY"
    )

    local optional_vars=(
        "REDIS_URL"
        "SENTRY_DSN"
        "SLACK_WEBHOOK_URL"
        "SMTP_HOST"
        "ENVIRONMENT"
    )

    for var in "${required_vars[@]}"; do
        ((TOTAL_CHECKS++))
        if [[ -n "${!var:-}" ]]; then
            log_success "Required environment variable '$var' is set"
        else
            log_error "Required environment variable '$var' is not set"
        fi
    done

    for var in "${optional_vars[@]}"; do
        ((TOTAL_CHECKS++))
        if [[ -n "${!var:-}" ]]; then
            log_success "Optional environment variable '$var' is set"
        else
            log_warning "Optional environment variable '$var' is not set"
        fi
    done
}

check_dependencies() {
    log_info "Checking system dependencies..."

    # Required commands
    check_command "python3"
    check_command "pip"
    check_command "psql"

    # Optional but recommended
    check_command "docker" || log_warning "Docker not available - manual deployment"
    check_command "curl" || log_warning "curl not available - limited HTTP testing"
    check_command "jq" || log_warning "jq not available - limited JSON processing"
}

check_database_connectivity() {
    log_info "Checking database connectivity..."

    if [[ -n "${DATABASE_URL:-}" ]]; then
        # Extract host and port from DATABASE_URL
        if [[ "$DATABASE_URL" =~ postgresql://.*@([^:/]+):?([0-9]*) ]]; then
            local db_host="${BASH_REMATCH[1]}"
            local db_port="${BASH_REMATCH[2]:-5432}"
            check_port "$db_host" "$db_port" "PostgreSQL database"
        else
            log_warning "Could not parse DATABASE_URL for connectivity check"
        fi
    else
        check_port "$POSTGRES_HOST" "$POSTGRES_PORT" "PostgreSQL database"
    fi

    # Test database connection with psql if available
    if command -v psql >/dev/null 2>&1 && [[ -n "${DATABASE_URL:-}" ]]; then
        ((TOTAL_CHECKS++))
        if psql "$DATABASE_URL" -c "SELECT 1;" >/dev/null 2>&1; then
            log_success "Database connection successful"
        else
            log_error "Database connection failed"
        fi
    fi
}

check_redis_connectivity() {
    log_info "Checking Redis connectivity..."

    if [[ -n "${REDIS_URL:-}" ]]; then
        # Extract host and port from REDIS_URL
        if [[ "$REDIS_URL" =~ redis://([^:/]+):?([0-9]*) ]]; then
            local redis_host="${BASH_REMATCH[1]}"
            local redis_port="${BASH_REMATCH[2]:-6379}"
            check_port "$redis_host" "$redis_port" "Redis"
        else
            log_warning "Could not parse REDIS_URL for connectivity check"
        fi
    else
        check_port "$REDIS_HOST" "$REDIS_PORT" "Redis"
    fi

    # Test Redis connection if redis-cli is available
    if command -v redis-cli >/dev/null 2>&1; then
        ((TOTAL_CHECKS++))
        if redis-cli -h "$REDIS_HOST" -p "$REDIS_PORT" ping >/dev/null 2>&1; then
            log_success "Redis connection successful"
        else
            log_error "Redis connection failed"
        fi
    fi
}

check_api_endpoints() {
    log_info "Checking API endpoints..."

    # Core endpoints
    check_http_endpoint "$API_URL/api/v1/health" "Health check endpoint"
    check_http_endpoint "$API_URL/api/v1/health/ready" "Readiness probe"
    check_http_endpoint "$API_URL/api/v1/health/live" "Liveness probe"

    # Authentication endpoints
    check_http_endpoint "$API_URL/api/v1/auth/signin" "Authentication endpoint" 405
    check_http_endpoint "$API_URL/api/v1/auth/signup" "Registration endpoint" 405

    # Enterprise endpoints
    check_http_endpoint "$API_URL/api/v1/organizations" "Organizations endpoint" 401
    check_http_endpoint "$API_URL/api/v1/sso/providers" "SSO providers endpoint" 401
    check_http_endpoint "$API_URL/api/v1/audit-logs" "Audit logs endpoint" 401
}

check_security_configuration() {
    log_info "Checking security configuration..."

    # Check HTTPS in production
    if [[ "${ENVIRONMENT:-}" == "production" ]] && [[ "$API_URL" == http://* ]]; then
        log_error "Production deployment should use HTTPS"
    else
        log_success "URL protocol appropriate for environment"
    fi

    # Check security headers
    if command -v curl >/dev/null 2>&1; then
        local headers=$(curl -s -I "$API_URL/api/v1/health" || echo "")

        ((TOTAL_CHECKS++))
        if echo "$headers" | grep -qi "x-content-type-options"; then
            log_success "X-Content-Type-Options header present"
        else
            log_warning "X-Content-Type-Options header missing"
        fi

        ((TOTAL_CHECKS++))
        if echo "$headers" | grep -qi "x-frame-options"; then
            log_success "X-Frame-Options header present"
        else
            log_warning "X-Frame-Options header missing"
        fi

        ((TOTAL_CHECKS++))
        if echo "$headers" | grep -qi "strict-transport-security"; then
            log_success "Strict-Transport-Security header present"
        else
            log_warning "Strict-Transport-Security header missing (OK for non-HTTPS)"
        fi
    fi
}

check_performance() {
    log_info "Checking performance characteristics..."

    if command -v curl >/dev/null 2>&1; then
        # Response time check
        ((TOTAL_CHECKS++))
        local start_time=$(date +%s%N)
        curl -s "$API_URL/api/v1/health" >/dev/null
        local end_time=$(date +%s%N)
        local response_time=$(( (end_time - start_time) / 1000000 )) # Convert to milliseconds

        if [[ $response_time -lt 1000 ]]; then
            log_success "Response time acceptable (${response_time}ms)"
        elif [[ $response_time -lt 3000 ]]; then
            log_warning "Response time slow (${response_time}ms)"
        else
            log_error "Response time too slow (${response_time}ms)"
        fi

        # Concurrent request test
        ((TOTAL_CHECKS++))
        log_info "Testing concurrent request handling..."
        local concurrent_pids=()
        for i in {1..5}; do
            curl -s "$API_URL/api/v1/health" >/dev/null &
            concurrent_pids+=($!)
        done

        local failed_requests=0
        for pid in "${concurrent_pids[@]}"; do
            if ! wait "$pid"; then
                ((failed_requests++))
            fi
        done

        if [[ $failed_requests -eq 0 ]]; then
            log_success "Concurrent request handling works"
        else
            log_error "Failed $failed_requests/5 concurrent requests"
        fi
    fi
}

check_docker_deployment() {
    if command -v docker >/dev/null 2>&1; then
        log_info "Checking Docker deployment readiness..."

        # Check for Dockerfile
        ((TOTAL_CHECKS++))
        if [[ -f "Dockerfile" ]]; then
            log_success "Dockerfile present"
        else
            log_warning "Dockerfile not found"
        fi

        # Check for docker-compose
        ((TOTAL_CHECKS++))
        if [[ -f "docker-compose.yml" ]] || [[ -f "docker-compose.yaml" ]]; then
            log_success "Docker Compose configuration present"
        else
            log_warning "Docker Compose configuration not found"
        fi

        # Check Docker daemon
        ((TOTAL_CHECKS++))
        if docker info >/dev/null 2>&1; then
            log_success "Docker daemon is running"
        else
            log_error "Docker daemon is not running"
        fi
    fi
}

check_monitoring_setup() {
    log_info "Checking monitoring setup..."

    # Check for monitoring endpoints
    check_http_endpoint "$API_URL/api/v1/metrics" "Metrics endpoint" 200

    # Check for APM configuration
    ((TOTAL_CHECKS++))
    if [[ -n "${SENTRY_DSN:-}" ]]; then
        log_success "Sentry APM configured"
    else
        log_warning "Sentry APM not configured"
    fi

    # Check for log configuration
    ((TOTAL_CHECKS++))
    if [[ -f "logging.conf" ]] || [[ -n "${LOG_LEVEL:-}" ]]; then
        log_success "Logging configuration present"
    else
        log_warning "Logging configuration not found"
    fi
}

generate_report() {
    echo ""
    echo "=================================="
    echo "🏢 ENTERPRISE DEPLOYMENT VALIDATION"
    echo "=================================="
    echo ""
    echo "📊 Summary:"
    echo "  Total Checks: $TOTAL_CHECKS"
    echo "  ✅ Passed: $PASSED_CHECKS"
    echo "  ⚠️  Warnings: $WARNING_CHECKS"
    echo "  ❌ Failed: $FAILED_CHECKS"
    echo ""

    local success_rate=$(( (PASSED_CHECKS * 100) / TOTAL_CHECKS ))
    echo "📈 Success Rate: $success_rate%"
    echo ""

    if [[ $FAILED_CHECKS -eq 0 ]] && [[ $success_rate -ge 80 ]]; then
        echo "🎉 Deployment validation PASSED"
        echo "✅ Ready for enterprise deployment"
        exit 0
    elif [[ $FAILED_CHECKS -eq 0 ]]; then
        echo "⚠️  Deployment validation PASSED with warnings"
        echo "🔧 Address warnings before enterprise deployment"
        exit 0
    else
        echo "❌ Deployment validation FAILED"
        echo "🚨 Critical issues must be resolved before deployment"
        exit 1
    fi
}

main() {
    echo "🚀 Starting Enterprise Deployment Validation..."
    echo "Target: $API_URL"
    echo "Timeout: ${TIMEOUT}s"
    echo ""

    check_environment_variables
    check_dependencies
    check_database_connectivity
    check_redis_connectivity
    check_api_endpoints
    check_security_configuration
    check_performance
    check_docker_deployment
    check_monitoring_setup

    generate_report
}

# Handle script arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --url)
            API_URL="$2"
            shift 2
            ;;
        --timeout)
            TIMEOUT="$2"
            shift 2
            ;;
        --postgres-host)
            POSTGRES_HOST="$2"
            shift 2
            ;;
        --redis-host)
            REDIS_HOST="$2"
            shift 2
            ;;
        --help)
            echo "Enterprise Deployment Validation Script"
            echo ""
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --url URL           API base URL (default: http://localhost:8000)"
            echo "  --timeout SECONDS   Request timeout (default: 30)"
            echo "  --postgres-host HOST PostgreSQL host (default: localhost)"
            echo "  --redis-host HOST   Redis host (default: localhost)"
            echo "  --help              Show this help message"
            echo ""
            echo "Environment Variables:"
            echo "  DATABASE_URL        PostgreSQL connection URL"
            echo "  REDIS_URL           Redis connection URL"
            echo "  SECRET_KEY          Application secret key"
            echo "  JWT_SECRET_KEY      JWT signing key"
            echo "  ENVIRONMENT         Deployment environment (production, staging, etc.)"
            echo ""
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            echo "Use --help for usage information"
            exit 1
            ;;
    esac
done

# Run main function
main