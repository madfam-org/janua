#!/bin/bash
# Console.log Cleanup Script
# Removes debug console.log statements from production code
# Keeps console.error and console.warn for actual error handling

set -e

# Color codes
RED='\033[0;31m'
YELLOW='\033[1;33m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}🧹 Console.log Cleanup - Week 1 Target: <50 remaining${NC}"
echo

# Count current console statements
CURRENT_COUNT=$(grep -r "console\.log" apps/demo packages/ui packages/react-sdk packages/vue-sdk packages/typescript-sdk --include="*.ts" --include="*.tsx" --include="*.js" --include="*.jsx" 2>/dev/null | grep -v node_modules | grep -v ".next" | grep -v "dist" | wc -l | tr -d ' ')

echo -e "${YELLOW}📊 Current console.log count: ${CURRENT_COUNT}${NC}"
echo

# Phase 1: Remove obvious debug console.logs
echo -e "${BLUE}Phase 1: Removing debug console.logs from showcase pages${NC}"

# List of files to clean (showcase pages are debug/demo only)
DEMO_SHOWCASE_FILES=(
  "apps/demo/app/auth/compliance-enterprise-showcase/page.tsx"
  "apps/demo/app/auth/compliance-showcase/page.tsx"
  "apps/demo/app/auth/security-showcase/page.tsx"
  "apps/demo/app/auth/sso-showcase/page.tsx"
  "apps/demo/app/auth/scim-rbac-showcase/page.tsx"
  "apps/demo/app/auth/password-reset-showcase/page.tsx"
  "apps/demo/app/auth/signin-showcase/page.tsx"
  "apps/demo/app/auth/signup-showcase/page.tsx"
  "apps/demo/app/auth/verification-showcase/page.tsx"
  "apps/demo/app/auth/user-profile-showcase/page.tsx"
  "apps/demo/app/auth/invitations-showcase/page.tsx"
  "apps/demo/app/auth/organization-showcase/page.tsx"
  "apps/demo/app/auth/mfa-showcase/page.tsx"
)

REMOVED=0

for file in "${DEMO_SHOWCASE_FILES[@]}"; do
  if [ -f "$file" ]; then
    # Count console.logs in this file
    FILE_COUNT=$(grep -c "console\.log" "$file" 2>/dev/null || echo "0")

    if [ "$FILE_COUNT" -gt 0 ]; then
      echo -e "  ${YELLOW}Cleaning${NC} $file (${FILE_COUNT} console.logs)"

      # Remove console.log lines (commented out for safety)
      sed -i.bak '/^\s*console\.log(/d' "$file"

      # Also remove console.log in inline contexts
      sed -i.bak "s/console\.log([^)]*)[;,]*/\/\/ removed console.log/g" "$file"

      REMOVED=$((REMOVED + FILE_COUNT))
      echo -e "    ${GREEN}✓${NC} Removed ${FILE_COUNT} console.logs"
    fi
  fi
done

echo
echo -e "${GREEN}✓ Phase 1 Complete: Removed ${REMOVED} console.logs from showcase pages${NC}"
echo

# Phase 2: Replace console.log with proper error handling in production code
echo -e "${BLUE}Phase 2: Identifying console.logs in production code (manual review needed)${NC}"

# Find console.logs in SDK packages (these need proper error handling)
SDK_LOGS=$(grep -r "console\.log" packages/react-sdk packages/vue-sdk packages/typescript-sdk --include="*.ts" --include="*.tsx" 2>/dev/null | grep -v node_modules | grep -v dist || echo "")

if [ -n "$SDK_LOGS" ]; then
  echo -e "${YELLOW}⚠️  Found console.logs in SDK packages (require manual review):${NC}"
  echo "$SDK_LOGS" | head -10
  echo
  echo -e "${YELLOW}Recommendation: Replace with proper error handling or remove${NC}"
else
  echo -e "${GREEN}✓ No console.logs found in SDK packages${NC}"
fi

echo

# Phase 3: Check UI component console.logs
UI_LOGS=$(grep -r "console\.log" packages/ui/src --include="*.tsx" --include="*.ts" 2>/dev/null | grep -v node_modules | grep -v dist || echo "")

if [ -n "$UI_LOGS" ]; then
  echo -e "${YELLOW}⚠️  Found console.logs in UI components:${NC}"
  echo "$UI_LOGS" | head -10
  echo
  echo -e "${YELLOW}Recommendation: Replace with onError callbacks or remove${NC}"
else
  echo -e "${GREEN}✓ No console.logs found in UI components${NC}"
fi

echo

# Final count
FINAL_COUNT=$(grep -r "console\.log" apps/demo packages/ui packages/react-sdk packages/vue-sdk packages/typescript-sdk --include="*.ts" --include="*.tsx" --include="*.js" --include="*.jsx" 2>/dev/null | grep -v node_modules | grep -v ".next" | grep -v "dist" | wc -l | tr -d ' ')

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo -e "${BLUE}Summary:${NC}"
echo -e "  Starting count: ${CURRENT_COUNT}"
echo -e "  Removed: ${REMOVED}"
echo -e "  Current count: ${FINAL_COUNT}"
echo

if [ "$FINAL_COUNT" -lt 50 ]; then
  echo -e "${GREEN}✅ SUCCESS: Achieved Week 1 target (<50 console.logs)${NC}"
  exit 0
elif [ "$FINAL_COUNT" -lt 100 ]; then
  echo -e "${YELLOW}⚠️  PARTIAL: ${FINAL_COUNT} remaining (target: <50)${NC}"
  echo -e "Next steps:"
  echo -e "  1. Review SDK console.logs and replace with proper error handling"
  echo -e "  2. Review UI component console.logs"
  echo -e "  3. Remove or replace remaining debug statements"
  exit 1
else
  echo -e "${RED}❌ INCOMPLETE: ${FINAL_COUNT} remaining (target: <50)${NC}"
  echo -e "More aggressive cleanup needed"
  exit 2
fi
