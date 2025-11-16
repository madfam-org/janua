#!/bin/bash

# Lighthouse audit script for all showcase pages
# Week 5 Day 5: Performance Testing

OUTPUT_DIR="lighthouse-reports"
mkdir -p "$OUTPUT_DIR"

PAGES=(
  "/"
  "/auth"
  "/auth/signin-showcase"
  "/auth/signup-showcase"
  "/auth/user-profile-showcase"
  "/auth/password-reset-showcase"
  "/auth/verification-showcase"
  "/auth/mfa-showcase"
  "/auth/security-showcase"
  "/auth/organization-showcase"
  "/auth/compliance-showcase"
)

echo "🚀 Starting Lighthouse audits for all showcase pages..."
echo "📊 Testing ${#PAGES[@]} pages"
echo ""

for PAGE in "${PAGES[@]}"; do
  SAFE_NAME=$(echo "$PAGE" | sed 's/\//-/g' | sed 's/^-//')
  if [ -z "$SAFE_NAME" ]; then
    SAFE_NAME="home"
  fi

  echo "🔍 Auditing: $PAGE"
  npx lighthouse "http://localhost:3000$PAGE" \
    --output=json \
    --output=html \
    --output-path="$OUTPUT_DIR/$SAFE_NAME" \
    --chrome-flags="--headless --no-sandbox --disable-dev-shm-usage" \
    --throttling-method=provided \
    --only-categories=performance,accessibility,best-practices,seo \
    --quiet

  if [ $? -eq 0 ]; then
    echo "✅ Completed: $SAFE_NAME"
  else
    echo "❌ Failed: $SAFE_NAME"
  fi
  echo ""
done

echo "📈 All audits complete!"
echo "📂 Reports saved to: $OUTPUT_DIR/"
