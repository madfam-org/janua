#!/bin/bash
# Documentation Maintenance Check Script
# Verifies documentation freshness, link validity, and consistency
# Exit codes: 0 = all checks pass, 1 = warnings found, 2 = critical issues

set -e

# Color codes for output
RED='\033[0;31m'
YELLOW='\033[1;33m'
GREEN='\033[0;32m'
NC='\033[0m' # No Color

echo "🔍 Running Documentation Maintenance Checks..."
echo

# Initialize counters
WARNINGS=0
ERRORS=0

# Check 1: Find outdated documentation (not updated in 90+ days)
echo "📅 Checking for outdated documentation..."
OUTDATED_DOCS=$(find docs -name "*.md" -type f -mtime +90 2>/dev/null || echo "")
if [ -n "$OUTDATED_DOCS" ]; then
    echo -e "${YELLOW}⚠️  Found documentation not updated in 90+ days:${NC}"
    echo "$OUTDATED_DOCS"
    WARNINGS=$((WARNINGS + 1))
else
    echo -e "${GREEN}✓${NC} All documentation recently updated"
fi
echo

# Check 2: Verify README files exist in key directories
echo "📄 Checking for missing README files..."
MISSING_READMES=0
for dir in apps/api apps/demo packages/core packages/react-sdk packages/typescript-sdk packages/vue-sdk; do
    if [ ! -f "$dir/README.md" ]; then
        echo -e "${RED}✗${NC} Missing README in $dir"
        MISSING_READMES=$((MISSING_READMES + 1))
        ERRORS=$((ERRORS + 1))
    fi
done
if [ $MISSING_READMES -eq 0 ]; then
    echo -e "${GREEN}✓${NC} All key directories have README files"
fi
echo

# Check 3: Check for broken internal links (markdown files)
echo "🔗 Checking for potentially broken internal links..."
BROKEN_LINKS=0
for md_file in $(find docs -name "*.md" -type f); do
    # Find markdown links [text](path)
    grep -oE '\[([^\]]+)\]\(([^)]+)\)' "$md_file" 2>/dev/null | while read -r link; do
        path=$(echo "$link" | sed -E 's/.*\]\(([^)]+)\)/\1/')
        # Skip external links (http/https)
        if [[ ! "$path" =~ ^https?:// ]]; then
            # Handle relative paths
            dir=$(dirname "$md_file")
            full_path="$dir/$path"
            if [ ! -f "$full_path" ] && [ ! -d "$full_path" ]; then
                echo -e "${YELLOW}⚠️${NC}  Potentially broken link in $md_file: $path"
                BROKEN_LINKS=$((BROKEN_LINKS + 1))
            fi
        fi
    done
done
if [ $BROKEN_LINKS -gt 0 ]; then
    WARNINGS=$((WARNINGS + 1))
else
    echo -e "${GREEN}✓${NC} No broken internal links detected"
fi
echo

# Check 4: Verify documentation index is up to date
echo "📚 Checking documentation index..."
if [ -f "docs/DOCUMENTATION_INDEX.md" ]; then
    # Count markdown files in docs
    TOTAL_DOCS=$(find docs -name "*.md" -type f | wc -l | tr -d ' ')
    # Count references in index (rough estimate)
    INDEX_REFS=$(grep -c "\.md" docs/DOCUMENTATION_INDEX.md 2>/dev/null || echo "0")

    # Allow 20% variance for meta-files
    MIN_EXPECTED=$((TOTAL_DOCS * 80 / 100))

    if [ "$INDEX_REFS" -lt "$MIN_EXPECTED" ]; then
        echo -e "${YELLOW}⚠️${NC}  Documentation index may be outdated (found $TOTAL_DOCS docs, index has ~$INDEX_REFS refs)"
        WARNINGS=$((WARNINGS + 1))
    else
        echo -e "${GREEN}✓${NC} Documentation index appears current"
    fi
else
    echo -e "${RED}✗${NC} docs/DOCUMENTATION_INDEX.md not found"
    ERRORS=$((ERRORS + 1))
fi
echo

# Check 5: Look for TODO/FIXME in documentation
echo "📝 Checking for documentation TODOs..."
DOC_TODOS=$(grep -r "TODO\|FIXME" docs --include="*.md" 2>/dev/null | wc -l | tr -d ' ')
if [ "$DOC_TODOS" -gt 10 ]; then
    echo -e "${YELLOW}⚠️${NC}  Found $DOC_TODOS TODOs in documentation (threshold: 10)"
    WARNINGS=$((WARNINGS + 1))
else
    echo -e "${GREEN}✓${NC} Documentation TODOs: $DOC_TODOS (acceptable)"
fi
echo

# Check 6: Verify implementation reports have dates
echo "📊 Checking implementation report naming..."
UNDATED_REPORTS=$(find docs/implementation-reports -name "*.md" -type f 2>/dev/null | grep -v -E "20[0-9]{2}-(0[1-9]|1[0-2])-([0-2][0-9]|3[01])" || echo "")
if [ -n "$UNDATED_REPORTS" ]; then
    echo -e "${YELLOW}⚠️${NC}  Found implementation reports without dates in filename:"
    echo "$UNDATED_REPORTS"
    WARNINGS=$((WARNINGS + 1))
else
    echo -e "${GREEN}✓${NC} All implementation reports have dates"
fi
echo

# Check 7: Verify archive structure
echo "📦 Checking archive organization..."
if [ -d "docs/historical" ]; then
    # Check for README in archive directories
    for archive_dir in docs/historical/*; do
        if [ -d "$archive_dir" ] && [ ! -f "$archive_dir/README.md" ]; then
            echo -e "${YELLOW}⚠️${NC}  Archive directory missing README: $archive_dir"
            WARNINGS=$((WARNINGS + 1))
        fi
    done
    echo -e "${GREEN}✓${NC} Archive structure verified"
else
    echo -e "${YELLOW}⚠️${NC}  No historical archive directory found"
fi
echo

# Summary
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
if [ $ERRORS -gt 0 ]; then
    echo -e "${RED}✗ FAILED${NC} - $ERRORS critical issues, $WARNINGS warnings"
    exit 2
elif [ $WARNINGS -gt 0 ]; then
    echo -e "${YELLOW}⚠️  WARNINGS${NC} - $WARNINGS issues found (recommend review)"
    exit 1
else
    echo -e "${GREEN}✓ PASSED${NC} - All documentation checks passed"
    exit 0
fi
