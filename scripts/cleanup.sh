#!/bin/bash
# cleanup.sh - Safe cleanup of temporary files and cache
# Part of Plinto monorepo maintenance
# Usage: bash scripts/cleanup.sh

set -e

echo "🧹 Plinto Codebase Cleanup"
echo "=========================="
echo ""

# Counter for removed items
TOTAL_REMOVED=0

# Python cache cleanup
echo "📦 Cleaning Python cache..."
PYCACHE_COUNT=$(find . -type d -name "__pycache__" 2>/dev/null | wc -l | tr -d ' ')
if [ "$PYCACHE_COUNT" -gt 0 ]; then
    find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
    echo "   ✅ Removed $PYCACHE_COUNT __pycache__ directories"
    TOTAL_REMOVED=$((TOTAL_REMOVED + PYCACHE_COUNT))
else
    echo "   ✓ No __pycache__ directories found"
fi

PYC_COUNT=$(find . -name "*.pyc" 2>/dev/null | wc -l | tr -d ' ')
if [ "$PYC_COUNT" -gt 0 ]; then
    find . -name "*.pyc" -delete 2>/dev/null || true
    echo "   ✅ Removed $PYC_COUNT .pyc files"
    TOTAL_REMOVED=$((TOTAL_REMOVED + PYC_COUNT))
else
    echo "   ✓ No .pyc files found"
fi

PYO_COUNT=$(find . -name "*.pyo" 2>/dev/null | wc -l | tr -d ' ')
if [ "$PYO_COUNT" -gt 0 ]; then
    find . -name "*.pyo" -delete 2>/dev/null || true
    echo "   ✅ Removed $PYO_COUNT .pyo files"
    TOTAL_REMOVED=$((TOTAL_REMOVED + PYO_COUNT))
fi

echo ""

# macOS metadata cleanup
echo "🍎 Cleaning macOS metadata..."
DS_COUNT=$(find . -name ".DS_Store" 2>/dev/null | wc -l | tr -d ' ')
if [ "$DS_COUNT" -gt 0 ]; then
    find . -name ".DS_Store" -delete 2>/dev/null || true
    echo "   ✅ Removed $DS_COUNT .DS_Store files"
    TOTAL_REMOVED=$((TOTAL_REMOVED + DS_COUNT))
else
    echo "   ✓ No .DS_Store files found"
fi

echo ""

# Test artifacts cleanup
echo "🧪 Cleaning test artifacts..."
COV_COUNT=$(find . -name ".coverage" 2>/dev/null | wc -l | tr -d ' ')
if [ "$COV_COUNT" -gt 0 ]; then
    find . -name ".coverage" -delete 2>/dev/null || true
    echo "   ✅ Removed $COV_COUNT .coverage files"
    TOTAL_REMOVED=$((TOTAL_REMOVED + COV_COUNT))
else
    echo "   ✓ No .coverage files found"
fi

PYTEST_COUNT=$(find . -type d -name ".pytest_cache" 2>/dev/null | wc -l | tr -d ' ')
if [ "$PYTEST_COUNT" -gt 0 ]; then
    find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
    echo "   ✅ Removed $PYTEST_COUNT .pytest_cache directories"
    TOTAL_REMOVED=$((TOTAL_REMOVED + PYTEST_COUNT))
else
    echo "   ✓ No .pytest_cache directories found"
fi

HTMLCOV_COUNT=$(find . -type d -name "htmlcov" 2>/dev/null | wc -l | tr -d ' ')
if [ "$HTMLCOV_COUNT" -gt 0 ]; then
    find . -type d -name "htmlcov" -exec rm -rf {} + 2>/dev/null || true
    echo "   ✅ Removed $HTMLCOV_COUNT htmlcov directories"
    TOTAL_REMOVED=$((TOTAL_REMOVED + HTMLCOV_COUNT))
fi

echo ""

# Log files cleanup
echo "📝 Cleaning log files..."
LOG_COUNT=$(find . -name "*.log" -type f ! -path "*/node_modules/*" 2>/dev/null | wc -l | tr -d ' ')
if [ "$LOG_COUNT" -gt 0 ]; then
    find . -name "*.log" -type f ! -path "*/node_modules/*" -delete 2>/dev/null || true
    echo "   ✅ Removed $LOG_COUNT .log files"
    TOTAL_REMOVED=$((TOTAL_REMOVED + LOG_COUNT))
else
    echo "   ✓ No .log files found"
fi

echo ""
echo "=========================="
echo "✅ Cleanup complete!"
echo "   Total items removed: $TOTAL_REMOVED"
echo ""
echo "💡 Tip: Run 'yarn clean' or 'npm run clean' to use this script"
echo ""
