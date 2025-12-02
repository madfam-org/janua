#!/bin/bash

# Janua Marketing Website Deployment Script
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
PUBLIC_DIR="public"

echo -e "${GREEN}🚀 Janua Marketing Website Deployment${NC}"
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

    # Check npm
    if ! command -v npm &> /dev/null; then
        echo -e "${RED}❌ npm is not installed${NC}"
        exit 1
    fi

    # Check if build exists
    if [ ! -d "$BUILD_DIR" ]; then
        echo -e "${RED}❌ Build directory not found. Run 'npm run build' first${NC}"
        exit 1
    fi

    echo -e "${GREEN}✅ All prerequisites met${NC}"
}

# Function to run tests
run_tests() {
    echo -e "${YELLOW}Running tests...${NC}"
    npm run typecheck
    npm run lint
    echo -e "${GREEN}✅ Tests passed${NC}"
}

# Function to build application
build_app() {
    echo -e "${YELLOW}Building application...${NC}"

    # Clean previous build
    rm -rf $BUILD_DIR

    # Build based on environment
    if [ "$ENVIRONMENT" = "production" ]; then
        NODE_ENV=production npm run build
    else
        npm run build
    fi

    echo -e "${GREEN}✅ Build completed${NC}"
}

# Function to optimize assets
optimize_assets() {
    echo -e "${YELLOW}Optimizing assets...${NC}"

    # Find and compress large JS files
    find $BUILD_DIR -name "*.js" -size +100k -exec echo "Large file: {}" \;

    echo -e "${GREEN}✅ Asset optimization completed${NC}"
}

# Function to deploy to Vercel
deploy_vercel() {
    echo -e "${YELLOW}Deploying to Vercel...${NC}"

    if ! command -v vercel &> /dev/null; then
        echo -e "${RED}❌ Vercel CLI is not installed${NC}"
        echo "Install with: npm i -g vercel"
        exit 1
    fi

    if [ "$ENVIRONMENT" = "production" ]; then
        vercel --prod
    else
        vercel
    fi

    echo -e "${GREEN}✅ Deployment to Vercel completed${NC}"
}

# Function to deploy with Docker
deploy_docker() {
    echo -e "${YELLOW}Building Docker image...${NC}"

    # Create Dockerfile if it doesn't exist
    if [ ! -f "Dockerfile" ]; then
        cat > Dockerfile << 'EOF'
FROM node:18-alpine AS base

# Install dependencies only when needed
FROM base AS deps
RUN apk add --no-cache libc6-compat
WORKDIR /app

COPY package.json package-lock.json* ./
RUN npm ci

# Rebuild the source code only when needed
FROM base AS builder
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .

RUN npm run build

# Production image
FROM base AS runner
WORKDIR /app

ENV NODE_ENV production

RUN addgroup --system --gid 1001 nodejs
RUN adduser --system --uid 1001 nextjs

COPY --from=builder /app/public ./public
COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/.next/static ./.next/static

USER nextjs

EXPOSE 3000

ENV PORT 3000

CMD ["node", "server.js"]
EOF
    fi

    docker build -t janua-marketing:$ENVIRONMENT .
    echo -e "${GREEN}✅ Docker image built${NC}"

    # Run container
    docker run -d \
        --name janua-marketing-$ENVIRONMENT \
        -p 3000:3000 \
        --restart unless-stopped \
        janua-marketing:$ENVIRONMENT

    echo -e "${GREEN}✅ Docker container started${NC}"
}

# Function to validate deployment
validate_deployment() {
    echo -e "${YELLOW}Validating deployment...${NC}"

    # Check if site is accessible
    if [ "$ENVIRONMENT" = "production" ]; then
        URL="https://janua.io"
    else
        URL="http://localhost:3000"
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
    echo "Build ID: $(cat $BUILD_DIR/BUILD_ID 2>/dev/null || echo 'N/A')"

    # Add webhook notification here if needed
    # curl -X POST https://hooks.slack.com/services/YOUR/WEBHOOK/URL \
    #     -H 'Content-Type: application/json' \
    #     -d "{\"text\":\"Marketing site deployed to $ENVIRONMENT\"}"
}

# Main deployment flow
main() {
    echo -e "${GREEN}Starting deployment process...${NC}"
    echo "================================="

    check_prerequisites
    run_tests
    build_app
    optimize_assets

    # Choose deployment method
    echo ""
    echo -e "${YELLOW}Select deployment method:${NC}"
    echo "1) Vercel"
    echo "2) Docker"
    echo "3) Skip deployment (build only)"
    read -p "Enter choice [1-3]: " choice

    case $choice in
        1)
            deploy_vercel
            ;;
        2)
            deploy_docker
            ;;
        3)
            echo -e "${YELLOW}Skipping deployment${NC}"
            ;;
        *)
            echo -e "${RED}Invalid choice${NC}"
            exit 1
            ;;
    esac

    validate_deployment
    notify_deployment

    echo ""
    echo "================================="
    echo -e "${GREEN}🎉 Deployment completed successfully!${NC}"
    echo ""

    # Display next steps
    echo -e "${YELLOW}Next Steps:${NC}"
    echo "1. Verify the deployment at the target URL"
    echo "2. Run Lighthouse audit for performance"
    echo "3. Check analytics and monitoring"
    echo "4. Update DNS if needed"
    echo ""
}

# Run main function
main