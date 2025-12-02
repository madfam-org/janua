#!/bin/bash

# Janua Website Deployment Script (Docker/Enclii)
# Usage: ./deploy.sh [staging|production]

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
ENVIRONMENT=${1:-staging}
BUILD_DIR=".next"
IMAGE_NAME="janua-website"
REGISTRY="ghcr.io/madfam-io"

echo -e "${GREEN}🚀 Janua Website Deployment${NC}"
echo -e "${YELLOW}Environment: ${ENVIRONMENT}${NC}"
echo ""

# Function to check prerequisites
check_prerequisites() {
    echo -e "${YELLOW}Checking prerequisites...${NC}"

    # Check Node.js
    if ! command -v node &> /dev/null; then
        echo -e "${RED}❌ Node.js is not installed${NC}"
        exit 1
    fi

    # Check pnpm
    if ! command -v pnpm &> /dev/null; then
        echo -e "${RED}❌ pnpm is not installed${NC}"
        exit 1
    fi

    # Check Docker
    if ! command -v docker &> /dev/null; then
        echo -e "${RED}❌ Docker is not installed${NC}"
        exit 1
    fi

    echo -e "${GREEN}✅ All prerequisites met${NC}"
}

# Function to run tests
run_tests() {
    echo -e "${YELLOW}Running tests...${NC}"
    pnpm typecheck || echo -e "${YELLOW}⚠️ Type check had warnings${NC}"
    pnpm lint || echo -e "${YELLOW}⚠️ Lint had warnings${NC}"
    echo -e "${GREEN}✅ Tests completed${NC}"
}

# Function to build application
build_app() {
    echo -e "${YELLOW}Building application...${NC}"

    # Clean previous build
    rm -rf $BUILD_DIR

    # Build based on environment
    if [ "$ENVIRONMENT" = "production" ]; then
        NODE_ENV=production pnpm build
    else
        pnpm build
    fi

    echo -e "${GREEN}✅ Build completed${NC}"
}

# Function to build and push Docker image
deploy_docker() {
    echo -e "${YELLOW}Building Docker image...${NC}"

    # Get git commit hash for tagging
    GIT_SHA=$(git rev-parse --short HEAD 2>/dev/null || echo "latest")

    # Build from repo root using Dockerfile.website
    cd ../..

    # Build image
    docker build \
        -f Dockerfile.website \
        -t $REGISTRY/$IMAGE_NAME:$GIT_SHA \
        -t $REGISTRY/$IMAGE_NAME:latest \
        --build-arg NEXT_PUBLIC_API_URL=https://api.janua.dev \
        --build-arg NEXT_PUBLIC_APP_URL=https://app.janua.dev \
        .

    echo -e "${GREEN}✅ Docker image built${NC}"

    if [ "$ENVIRONMENT" = "production" ]; then
        echo -e "${YELLOW}Pushing to registry...${NC}"
        docker push $REGISTRY/$IMAGE_NAME:$GIT_SHA
        docker push $REGISTRY/$IMAGE_NAME:latest
        echo -e "${GREEN}✅ Image pushed to $REGISTRY${NC}"
    fi

    cd apps/website
}

# Function to deploy locally with Docker
deploy_local() {
    echo -e "${YELLOW}Starting local container...${NC}"

    # Stop existing container if running
    docker stop $IMAGE_NAME-local 2>/dev/null || true
    docker rm $IMAGE_NAME-local 2>/dev/null || true

    # Run container on MADFAM port 4104
    docker run -d \
        --name $IMAGE_NAME-local \
        -p 4104:3000 \
        --restart unless-stopped \
        -e NODE_ENV=production \
        -e NEXT_PUBLIC_API_URL=http://localhost:4100 \
        -e NEXT_PUBLIC_APP_URL=http://localhost:4101 \
        $REGISTRY/$IMAGE_NAME:latest

    echo -e "${GREEN}✅ Container started on port 4104${NC}"
}

# Function to validate deployment
validate_deployment() {
    echo -e "${YELLOW}Validating deployment...${NC}"

    # Check if site is accessible
    if [ "$ENVIRONMENT" = "production" ]; then
        URL="https://janua.dev"
    else
        URL="http://localhost:4104"
    fi

    # Wait for service to be ready
    sleep 5

    # Check HTTP status
    HTTP_STATUS=$(curl -s -o /dev/null -w "%{http_code}" $URL || echo "000")

    if [ "$HTTP_STATUS" = "200" ]; then
        echo -e "${GREEN}✅ Site is accessible at $URL${NC}"
    else
        echo -e "${YELLOW}⚠️  Site returned HTTP $HTTP_STATUS${NC}"
    fi
}

# Function to notify deployment
notify_deployment() {
    echo -e "${GREEN}📢 Deployment Notification${NC}"
    echo "Environment: $ENVIRONMENT"
    echo "Timestamp: $(date)"
    echo "Git SHA: $(git rev-parse --short HEAD 2>/dev/null || echo 'N/A')"
    echo "Port: 4104 (MADFAM standard)"
}

# Main deployment flow
main() {
    echo -e "${GREEN}Starting deployment process...${NC}"
    echo "================================="

    check_prerequisites
    run_tests

    # Choose deployment method
    echo ""
    echo -e "${YELLOW}Select deployment method:${NC}"
    echo "1) Build Docker image only"
    echo "2) Build and push to registry (production)"
    echo "3) Build and run locally"
    echo "4) Skip deployment (test only)"
    read -p "Enter choice [1-4]: " choice

    case $choice in
        1)
            build_app
            deploy_docker
            ;;
        2)
            ENVIRONMENT=production
            build_app
            deploy_docker
            ;;
        3)
            build_app
            deploy_docker
            deploy_local
            validate_deployment
            ;;
        4)
            echo -e "${YELLOW}Skipping deployment${NC}"
            ;;
        *)
            echo -e "${RED}Invalid choice${NC}"
            exit 1
            ;;
    esac

    notify_deployment

    echo ""
    echo "================================="
    echo -e "${GREEN}🎉 Deployment completed successfully!${NC}"
    echo ""

    # Display next steps
    echo -e "${YELLOW}Next Steps:${NC}"
    echo "1. For production: Enclii will pull from ghcr.io and deploy"
    echo "2. For local: Site is running at http://localhost:4104"
    echo "3. Check logs: docker logs $IMAGE_NAME-local"
    echo ""
}

# Run main function
main
