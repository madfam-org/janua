#!/bin/bash

# Deploy to Vercel using CLI
# Usage: ./scripts/deploy-vercel.sh [production|preview]

set -e

ENVIRONMENT=${1:-preview}
PROJECT_NAME="plinto"

echo "🚀 Deploying Plinto to Vercel ($ENVIRONMENT)..."

# Ensure we're in the right directory
cd "$(dirname "$0")/.."

# Install dependencies if needed
if [ ! -d "node_modules" ]; then
  echo "📦 Installing dependencies..."
  yarn install --frozen-lockfile
fi

# Build the project
echo "🏗️  Building project..."
yarn build

# Deploy to Vercel
if [ "$ENVIRONMENT" = "production" ]; then
  echo "🌟 Deploying to production..."
  npx vercel --prod --confirm
else
  echo "🔄 Deploying preview..."
  npx vercel --confirm
fi

echo "✅ Deployment complete!"