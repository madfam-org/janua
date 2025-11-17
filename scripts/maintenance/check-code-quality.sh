#!/bin/bash
# Code Quality Check Script
# Runs comprehensive code quality checks for Plinto project

set -e

echo "🔍 Plinto Code Quality Check - $(date)"
echo "================================================"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Counter for issues
TOTAL_ISSUES=0

# 1. Check for TODO/FIXME in production code
echo ""
echo "📝 Checking for TODOs in production code..."
TODO_COUNT=$(grep -r "TODO\|FIXME" apps packages --include="*.ts" --include="*.tsx" --include="*.js" --include="*.py" --exclude-dir=node_modules --exclude-dir=dist --exclude-dir=.next --exclude-dir=__pycache__ 2>/dev/null | grep -v "\.test\." | grep -v "\.spec\." | wc -l | tr -d ' ')

if [ "$TODO_COUNT" -gt 60 ]; then
    echo -e "${RED}❌ Found $TODO_COUNT TODOs in production code (threshold: 60)${NC}"
    TOTAL_ISSUES=$((TOTAL_ISSUES + 1))
elif [ "$TODO_COUNT" -gt 40 ]; then
    echo -e "${YELLOW}⚠️  Found $TODO_COUNT TODOs in production code (warning: >40)${NC}"
else
    echo -e "${GREEN}✅ Found $TODO_COUNT TODOs in production code (acceptable)${NC}"
fi

# 2. Check for console.log in production code
echo ""
echo "🖨️  Checking for console statements in production code..."
CONSOLE_COUNT=$(grep -r "console\.log\|console\.debug" apps packages --include="*.ts" --include="*.tsx" --include="*.js" --exclude-dir=node_modules --exclude-dir=dist --exclude-dir=.next 2>/dev/null | grep -v "\.test\." | grep -v "\.spec\." | grep -v "showcase" | grep -v "demo" | wc -l | tr -d ' ')

if [ "$CONSOLE_COUNT" -gt 100 ]; then
    echo -e "${RED}❌ Found $CONSOLE_COUNT console statements in production code (threshold: 100)${NC}"
    TOTAL_ISSUES=$((TOTAL_ISSUES + 1))
elif [ "$CONSOLE_COUNT" -gt 50 ]; then
    echo -e "${YELLOW}⚠️  Found $CONSOLE_COUNT console statements (warning: >50)${NC}"
else
    echo -e "${GREEN}✅ Found $CONSOLE_COUNT console statements (acceptable)${NC}"
fi

# 3. Check for .env files in git
echo ""
echo "🔒 Checking for .env files in git tracking..."
ENV_FILES=$(git ls-files | grep "\.env$" | wc -l | tr -d ' ')

if [ "$ENV_FILES" -gt 0 ]; then
    echo -e "${RED}❌ Found $ENV_FILES .env files tracked in git${NC}"
    git ls-files | grep "\.env$"
    TOTAL_ISSUES=$((TOTAL_ISSUES + 1))
else
    echo -e "${GREEN}✅ No .env files tracked in git${NC}"
fi

# 4. Check build system health
echo ""
echo "🏗️  Checking build system..."
if npm run build:core > /dev/null 2>&1; then
    echo -e "${GREEN}✅ Core package builds successfully${NC}"
else
    echo -e "${RED}❌ Core package build failed${NC}"
    TOTAL_ISSUES=$((TOTAL_ISSUES + 1))
fi

if npm run build:sdk > /dev/null 2>&1; then
    echo -e "${GREEN}✅ TypeScript SDK builds successfully${NC}"
else
    echo -e "${RED}❌ TypeScript SDK build failed${NC}"
    TOTAL_ISSUES=$((TOTAL_ISSUES + 1))
fi

# 5. Check for large files
echo ""
echo "📦 Checking for large files..."
LARGE_FILES=$(find . -type f -size +1M -not -path "*/node_modules/*" -not -path "*/.next/*" -not -path "*/dist/*" | wc -l | tr -d ' ')

if [ "$LARGE_FILES" -gt 10 ]; then
    echo -e "${YELLOW}⚠️  Found $LARGE_FILES files >1MB${NC}"
else
    echo -e "${GREEN}✅ Large file count acceptable ($LARGE_FILES)${NC}"
fi

# 6. Summary
echo ""
echo "================================================"
if [ "$TOTAL_ISSUES" -eq 0 ]; then
    echo -e "${GREEN}✅ All code quality checks passed!${NC}"
    exit 0
else
    echo -e "${RED}❌ Found $TOTAL_ISSUES critical issues${NC}"
    echo "Run this script regularly to maintain code quality."
    exit 1
fi
