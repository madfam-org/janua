#!/bin/bash

# Deploy to Vercel using webhook
# Usage: ./deploy.sh [message]

DEPLOY_HOOK_URL="https://api.vercel.com/v1/integrations/deploy/prj_wjDIoQwFGq9iia26nmy3yIpiysmZ/InROqsM8vY"
MESSAGE="${1:-Manual deployment from $(whoami) at $(date)}"

echo "🚀 Triggering Vercel deployment..."
echo "📝 Message: $MESSAGE"

RESPONSE=$(curl -s -X POST "$DEPLOY_HOOK_URL" \
  -H "Content-Type: application/json" \
  -d "{\"message\":\"$MESSAGE\"}")

echo "📡 Response: $RESPONSE"

JOB_ID=$(echo "$RESPONSE" | grep -o '"id":"[^"]*"' | cut -d'"' -f4)

if [ -n "$JOB_ID" ]; then
    echo "✅ Deployment queued successfully!"
    echo "🆔 Job ID: $JOB_ID"
    echo "🌐 Check status at: https://vercel.com/dashboard"
else
    echo "❌ Deployment failed or unexpected response"
    exit 1
fi