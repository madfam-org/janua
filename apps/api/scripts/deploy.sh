#!/bin/bash

# Janua API Deployment Script (Docker/Enclii)
# Usage: ./deploy.sh [staging|production]

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
ENVIRONMENT=${1:-staging}
IMAGE_NAME="janua-api"
REGISTRY="ghcr.io/madfam-io"
PORT=4100  # MADFAM standard port for Janua API

echo -e "${GREEN}🚀 Janua API Deployment${NC}"
echo -e "${YELLOW}Environment: ${ENVIRONMENT}${NC}"
echo ""

# Function to check prerequisites
check_prerequisites() {
    echo -e "${YELLOW}Checking prerequisites...${NC}"

    # Check Docker
    if ! command -v docker &> /dev/null; then
        echo -e "${RED}❌ Docker is not installed${NC}"
        exit 1
    fi

    # Check Python
    if ! command -v python &> /dev/null && ! command -v python3 &> /dev/null; then
        echo -e "${RED}❌ Python is not installed${NC}"
        exit 1
    fi

    echo -e "${GREEN}✅ All prerequisites met${NC}"
}

# Function to run tests
run_tests() {
    echo -e "${YELLOW}Running tests...${NC}"

    # Activate venv if it exists
    if [ -f "venv/bin/activate" ]; then
        source venv/bin/activate
    fi

    # Run pytest
    python -m pytest tests/ -v --tb=short || echo -e "${YELLOW}⚠️ Some tests failed${NC}"

    echo -e "${GREEN}✅ Tests completed${NC}"
}

# Function to build Docker image
build_docker() {
    echo -e "${YELLOW}Building Docker image...${NC}"

    # Get git commit hash for tagging
    GIT_SHA=$(git rev-parse --short HEAD 2>/dev/null || echo "latest")

    # Build from repo root using Dockerfile.api
    cd ../..

    # Build image
    docker build \
        -f Dockerfile.api \
        -t $REGISTRY/$IMAGE_NAME:$GIT_SHA \
        -t $REGISTRY/$IMAGE_NAME:latest \
        .

    echo -e "${GREEN}✅ Docker image built: $REGISTRY/$IMAGE_NAME:$GIT_SHA${NC}"

    cd apps/api
}

# Function to push to registry
push_registry() {
    echo -e "${YELLOW}Pushing to registry...${NC}"

    GIT_SHA=$(git rev-parse --short HEAD 2>/dev/null || echo "latest")

    docker push $REGISTRY/$IMAGE_NAME:$GIT_SHA
    docker push $REGISTRY/$IMAGE_NAME:latest

    echo -e "${GREEN}✅ Image pushed to $REGISTRY${NC}"
}

# Function to deploy locally with Docker
deploy_local() {
    echo -e "${YELLOW}Starting local container...${NC}"

    # Stop existing container if running
    docker stop $IMAGE_NAME-local 2>/dev/null || true
    docker rm $IMAGE_NAME-local 2>/dev/null || true

    # Run container on MADFAM port
    docker run -d \
        --name $IMAGE_NAME-local \
        -p $PORT:8000 \
        --restart unless-stopped \
        -e ENVIRONMENT=development \
        -e DATABASE_URL=${DATABASE_URL:-postgresql://janua:janua_dev@host.docker.internal:5432/janua_dev} \
        -e REDIS_URL=${REDIS_URL:-redis://host.docker.internal:6379} \
        -e SECRET_KEY=${SECRET_KEY:-dev-secret-key-32-chars-minimum} \
        $REGISTRY/$IMAGE_NAME:latest

    echo -e "${GREEN}✅ Container started on port $PORT${NC}"
}

# Function to validate deployment
validate_deployment() {
    echo -e "${YELLOW}Validating deployment...${NC}"

    if [ "$ENVIRONMENT" = "production" ]; then
        URL="https://api.janua.dev/health"
    else
        URL="http://localhost:$PORT/health"
    fi

    # Wait for service to be ready
    echo "Waiting for service to start..."
    sleep 5

    # Check HTTP status
    HTTP_STATUS=$(curl -s -o /dev/null -w "%{http_code}" $URL || echo "000")

    if [ "$HTTP_STATUS" = "200" ]; then
        echo -e "${GREEN}✅ API is healthy at $URL${NC}"
        # Show health response
        curl -s $URL | python -m json.tool 2>/dev/null || curl -s $URL
    else
        echo -e "${YELLOW}⚠️  API returned HTTP $HTTP_STATUS${NC}"
    fi
}

# Function to run database migrations
run_migrations() {
    echo -e "${YELLOW}Running database migrations...${NC}"

    docker exec $IMAGE_NAME-local alembic upgrade head

    echo -e "${GREEN}✅ Migrations completed${NC}"
}

# Main deployment flow
main() {
    echo -e "${GREEN}Starting deployment process...${NC}"
    echo "================================="

    check_prerequisites

    # Choose deployment method
    echo ""
    echo -e "${YELLOW}Select deployment action:${NC}"
    echo "1) Build Docker image only"
    echo "2) Build and push to registry (production)"
    echo "3) Build and run locally"
    echo "4) Run tests only"
    read -p "Enter choice [1-4]: " choice

    case $choice in
        1)
            build_docker
            ;;
        2)
            ENVIRONMENT=production
            run_tests
            build_docker
            push_registry
            ;;
        3)
            build_docker
            deploy_local
            validate_deployment
            echo ""
            echo -e "${YELLOW}Run migrations? (y/n)${NC}"
            read -p "" migrate
            if [ "$migrate" = "y" ]; then
                run_migrations
            fi
            ;;
        4)
            run_tests
            ;;
        *)
            echo -e "${RED}Invalid choice${NC}"
            exit 1
            ;;
    esac

    echo ""
    echo "================================="
    echo -e "${GREEN}🎉 Deployment completed!${NC}"
    echo ""

    # Display next steps
    echo -e "${YELLOW}Information:${NC}"
    echo "  Registry: $REGISTRY/$IMAGE_NAME"
    echo "  Port: $PORT (MADFAM standard)"
    echo "  Health: http://localhost:$PORT/health"
    echo "  Docs: http://localhost:$PORT/docs (if enabled)"
    echo ""
}

# Run main function
main
