#!/usr/bin/env bash

# Plinto Platform Deployment Script
# Usage: ./scripts/deploy.sh [environment] [component]
# Examples:
#   ./scripts/deploy.sh production all
#   ./scripts/deploy.sh staging api
#   ./scripts/deploy.sh production frontend

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
ENVIRONMENT=${1:-production}
COMPONENT=${2:-all}
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
DEPLOY_LOG="logs/deploy_${ENVIRONMENT}_${TIMESTAMP}.log"

# Create log directory if it doesn't exist
mkdir -p logs

# Logging function
log() {
    echo -e "${2:-$BLUE}[$(date +'%Y-%m-%d %H:%M:%S')] $1${NC}" | tee -a "$DEPLOY_LOG"
}

error() {
    echo -e "${RED}[ERROR] $1${NC}" | tee -a "$DEPLOY_LOG"
    exit 1
}

success() {
    echo -e "${GREEN}[SUCCESS] $1${NC}" | tee -a "$DEPLOY_LOG"
}

warning() {
    echo -e "${YELLOW}[WARNING] $1${NC}" | tee -a "$DEPLOY_LOG"
}

# Check prerequisites
check_prerequisites() {
    log "Checking prerequisites..."
    
    # Check required tools
    command -v git >/dev/null 2>&1 || error "git is required but not installed"
    command -v node >/dev/null 2>&1 || error "node is required but not installed"
    command -v yarn >/dev/null 2>&1 || error "yarn is required but not installed"
    command -v docker >/dev/null 2>&1 || warning "docker is not installed (required for API deployment)"
    
    # Check environment file
    if [[ "$ENVIRONMENT" == "production" ]]; then
        if [[ ! -f ".env.production" ]]; then
            error "Production environment file (.env.production) not found"
        fi
    fi
    
    # Check git status
    if [[ -n $(git status -s) ]]; then
        warning "There are uncommitted changes in the repository"
        read -p "Continue anyway? (y/N) " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            error "Deployment cancelled"
        fi
    fi
    
    success "Prerequisites check passed"
}

# Run tests
run_tests() {
    log "Running tests..."
    
    # Run unit tests
    yarn test:unit || error "Unit tests failed"
    
    # Run integration tests
    yarn test:integration || warning "Integration tests failed (non-blocking)"
    
    # Run type checking
    yarn typecheck || error "Type checking failed"
    
    # Run linting
    yarn lint || warning "Linting issues found (non-blocking)"
    
    success "Tests completed"
}

# Build application
build_application() {
    log "Building application..."
    
    # Install dependencies
    yarn install --frozen-lockfile || error "Failed to install dependencies"
    
    # Build based on component
    case $COMPONENT in
        all)
            yarn build || error "Build failed"
            ;;
        api)
            cd apps/api
            if [[ -f "requirements.txt" ]]; then
                pip install -r requirements.txt || error "Failed to install Python dependencies"
            fi
            cd ../..
            ;;
        frontend)
            yarn workspace @plinto/marketing build || error "Marketing site build failed"
            yarn workspace @plinto/app build || error "App dashboard build failed"
            yarn workspace @plinto/admin build || error "Admin dashboard build failed"
            yarn workspace @plinto/docs build || error "Docs build failed"
            ;;
        *)
            yarn workspace @plinto/$COMPONENT build || error "Build failed for $COMPONENT"
            ;;
    esac
    
    success "Build completed"
}

# Deploy to Vercel
deploy_vercel() {
    log "Deploying frontends to Vercel..."
    
    # Check Vercel CLI
    command -v vercel >/dev/null 2>&1 || error "Vercel CLI is required but not installed"
    
    # Deploy each frontend app
    if [[ "$COMPONENT" == "all" || "$COMPONENT" == "frontend" || "$COMPONENT" == "marketing" ]]; then
        log "Deploying marketing site..."
        cd apps/marketing
        if [[ "$ENVIRONMENT" == "production" ]]; then
            vercel --prod --yes || error "Marketing site deployment failed"
        else
            vercel --yes || error "Marketing site deployment failed"
        fi
        cd ../..
    fi
    
    if [[ "$COMPONENT" == "all" || "$COMPONENT" == "frontend" || "$COMPONENT" == "app" ]]; then
        log "Deploying app dashboard..."
        cd apps/app
        if [[ "$ENVIRONMENT" == "production" ]]; then
            vercel --prod --yes || error "App dashboard deployment failed"
        else
            vercel --yes || error "App dashboard deployment failed"
        fi
        cd ../..
    fi
    
    if [[ "$COMPONENT" == "all" || "$COMPONENT" == "frontend" || "$COMPONENT" == "admin" ]]; then
        log "Deploying admin dashboard..."
        cd apps/admin
        if [[ "$ENVIRONMENT" == "production" ]]; then
            vercel --prod --yes || error "Admin dashboard deployment failed"
        else
            vercel --yes || error "Admin dashboard deployment failed"
        fi
        cd ../..
    fi
    
    if [[ "$COMPONENT" == "all" || "$COMPONENT" == "frontend" || "$COMPONENT" == "docs" ]]; then
        log "Deploying documentation..."
        cd apps/docs
        if [[ "$ENVIRONMENT" == "production" ]]; then
            vercel --prod --yes || error "Documentation deployment failed"
        else
            vercel --yes || error "Documentation deployment failed"
        fi
        cd ../..
    fi
    
    success "Vercel deployment completed"
}

# Deploy to Railway
deploy_railway() {
    log "Deploying API to Railway..."
    
    # Check Railway CLI
    command -v railway >/dev/null 2>&1 || error "Railway CLI is required but not installed"
    
    if [[ "$COMPONENT" == "all" || "$COMPONENT" == "api" ]]; then
        cd apps/api
        
        # Deploy based on environment
        if [[ "$ENVIRONMENT" == "production" ]]; then
            railway up --environment production || error "API deployment to Railway failed"
        else
            railway up --environment staging || error "API deployment to Railway failed"
        fi
        
        cd ../..
    fi
    
    success "Railway deployment completed"
}

# Run database migrations
run_migrations() {
    log "Running database migrations..."
    
    cd apps/api
    
    # Run Alembic migrations
    if [[ "$ENVIRONMENT" == "production" ]]; then
        source .env.production
        alembic upgrade head || error "Database migrations failed"
    else
        alembic upgrade head || warning "Database migrations failed (non-blocking in staging)"
    fi
    
    cd ../..
    
    success "Database migrations completed"
}

# Clear caches
clear_caches() {
    log "Clearing caches..."
    
    # Clear Cloudflare cache
    if [[ -n "${CLOUDFLARE_API_TOKEN:-}" ]]; then
        curl -X POST "https://api.cloudflare.com/client/v4/zones/${CLOUDFLARE_ZONE_ID}/purge_cache" \
            -H "Authorization: Bearer ${CLOUDFLARE_API_TOKEN}" \
            -H "Content-Type: application/json" \
            --data '{"purge_everything":true}' || warning "Failed to clear Cloudflare cache"
    fi
    
    # Clear Redis cache
    if [[ -n "${REDIS_URL:-}" ]]; then
        redis-cli -u "${REDIS_URL}" FLUSHDB || warning "Failed to clear Redis cache"
    fi
    
    success "Caches cleared"
}

# Health check
health_check() {
    log "Running health checks..."
    
    # API health check
    if [[ "$COMPONENT" == "all" || "$COMPONENT" == "api" ]]; then
        API_URL="${API_BASE_URL:-https://plinto.dev/api/v1}"
        response=$(curl -s -o /dev/null -w "%{http_code}" "${API_URL}/health")
        if [[ "$response" == "200" ]]; then
            success "API health check passed"
        else
            error "API health check failed (HTTP $response)"
        fi
    fi
    
    # Frontend health checks
    if [[ "$COMPONENT" == "all" || "$COMPONENT" == "frontend" ]]; then
        for site in "plinto.dev" "app.plinto.dev" "admin.plinto.dev" "docs.plinto.dev"; do
            response=$(curl -s -o /dev/null -w "%{http_code}" "https://${site}")
            if [[ "$response" == "200" ]]; then
                success "${site} is responding"
            else
                warning "${site} returned HTTP ${response}"
            fi
        done
    fi
    
    success "Health checks completed"
}

# Send deployment notification
send_notification() {
    log "Sending deployment notification..."
    
    # Slack notification
    if [[ -n "${SLACK_WEBHOOK_URL:-}" ]]; then
        curl -X POST "${SLACK_WEBHOOK_URL}" \
            -H 'Content-Type: application/json' \
            -d "{
                \"text\": \"🚀 Deployment to ${ENVIRONMENT} completed\",
                \"attachments\": [{
                    \"color\": \"good\",
                    \"fields\": [
                        {\"title\": \"Environment\", \"value\": \"${ENVIRONMENT}\", \"short\": true},
                        {\"title\": \"Component\", \"value\": \"${COMPONENT}\", \"short\": true},
                        {\"title\": \"Timestamp\", \"value\": \"${TIMESTAMP}\", \"short\": true},
                        {\"title\": \"Deployed by\", \"value\": \"$(git config user.name)\", \"short\": true}
                    ]
                }]
            }" || warning "Failed to send Slack notification"
    fi
    
    success "Notifications sent"
}

# Rollback function
rollback() {
    error "Deployment failed, initiating rollback..."
    
    # Vercel rollback
    if [[ "$COMPONENT" == "all" || "$COMPONENT" == "frontend" ]]; then
        log "Rolling back Vercel deployments..."
        # Vercel automatically handles rollbacks through the dashboard
        warning "Please use Vercel dashboard to rollback frontend deployments"
    fi
    
    # Railway rollback
    if [[ "$COMPONENT" == "all" || "$COMPONENT" == "api" ]]; then
        log "Rolling back Railway deployment..."
        cd apps/api
        railway down || warning "Failed to rollback Railway deployment"
        cd ../..
    fi
    
    error "Rollback completed. Please investigate the issue."
}

# Main deployment flow
main() {
    log "Starting deployment to ${ENVIRONMENT} for ${COMPONENT}..."
    
    # Set up error handling
    trap rollback ERR
    
    # Run deployment steps
    check_prerequisites
    
    if [[ "$ENVIRONMENT" == "production" ]]; then
        run_tests
    fi
    
    build_application
    
    if [[ "$COMPONENT" == "all" || "$COMPONENT" == "api" ]]; then
        run_migrations
        deploy_railway
    fi
    
    if [[ "$COMPONENT" == "all" || "$COMPONENT" == "frontend" || "$COMPONENT" == "marketing" || "$COMPONENT" == "app" || "$COMPONENT" == "admin" || "$COMPONENT" == "docs" ]]; then
        deploy_vercel
    fi
    
    if [[ "$ENVIRONMENT" == "production" ]]; then
        clear_caches
    fi
    
    health_check
    send_notification
    
    success "Deployment completed successfully!"
    log "Deployment log saved to: $DEPLOY_LOG"
}

# Run main function
main