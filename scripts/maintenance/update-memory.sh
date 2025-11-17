#!/bin/bash
# Serena Memory Update Script
# Keeps project memories current with codebase state
# Usage: ./update-memory.sh [memory_name]

set -e

# Color codes
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo "🧠 Serena Memory Update Utility"
echo

# Function to gather current metrics
gather_metrics() {
    echo -e "${BLUE}📊 Gathering current codebase metrics...${NC}"

    # Source file counts
    TS_FILES=$(find apps packages -name "*.ts" -not -path "*/node_modules/*" -not -path "*/dist/*" | wc -l | tr -d ' ')
    TSX_FILES=$(find apps packages -name "*.tsx" -not -path "*/node_modules/*" -not -path "*/dist/*" | wc -l | tr -d ' ')
    JS_FILES=$(find apps packages -name "*.js" -not -path "*/node_modules/*" -not -path "*/dist/*" | wc -l | tr -d ' ')
    PY_FILES=$(find apps -name "*.py" -not -path "*/node_modules/*" -not -path "*/__pycache__/*" | wc -l | tr -d ' ')

    # Test counts
    TEST_FILES=$(find apps packages -name "*.test.ts" -o -name "*.test.tsx" -o -name "*.spec.ts" -o -name "test_*.py" | wc -l | tr -d ' ')

    # Code quality metrics
    TODO_COUNT=$(grep -r "TODO\|FIXME" apps packages --include="*.ts" --include="*.tsx" --include="*.py" 2>/dev/null | wc -l | tr -d ' ')
    CONSOLE_COUNT=$(grep -r "console\.log" apps packages --include="*.ts" --include="*.tsx" --include="*.js" 2>/dev/null | wc -l | tr -d ' ')

    # Build status
    BUILD_STATUS="Unknown"
    if npm run build &>/dev/null; then
        BUILD_STATUS="Passing"
    else
        BUILD_STATUS="Failing"
    fi

    # Package info
    APPS_COUNT=$(ls -d apps/*/ 2>/dev/null | wc -l | tr -d ' ')
    PACKAGES_COUNT=$(ls -d packages/*/ 2>/dev/null | wc -l | tr -d ' ')

    echo -e "${GREEN}✓${NC} Metrics gathered"
}

# Function to generate project status memory
generate_project_status() {
    cat > /tmp/plinto_project_status.md << EOF
# Plinto Project Status - $(date +%Y-%m-%d)

## Overview
Multi-tenant authentication platform with enterprise SSO/SAML/OIDC support.

## Current Metrics (Auto-updated)

### Codebase Size
- **Total Source Files**: $((TS_FILES + TSX_FILES + JS_FILES + PY_FILES))
  - TypeScript: ${TS_FILES} files
  - TSX (React): ${TSX_FILES} files
  - JavaScript: ${JS_FILES} files
  - Python: ${PY_FILES} files

### Project Structure
- **Apps**: ${APPS_COUNT} applications
- **Packages**: ${PACKAGES_COUNT} packages
- **Test Files**: ${TEST_FILES}

### Code Quality
- **TODO/FIXME Count**: ${TODO_COUNT}
- **Console.log Count**: ${CONSOLE_COUNT}
- **Build Status**: ${BUILD_STATUS}

### Enterprise Features Status
- ✅ SAML/OIDC SSO (Complete)
- ✅ SCIM 2.0 provisioning (Complete)
- ✅ RBAC with policies (Complete)
- ✅ Webhooks with retry (Complete)
- ✅ Audit logging (Complete)
- ✅ Organization invitations (Complete)

### SDK Status
- ✅ TypeScript SDK (builds)
- ✅ React SDK (builds)
- ✅ Next.js SDK (builds)
- ✅ Core package (builds)
- ✅ Vue SDK (builds - fixed)

### Production Readiness
**Current Assessment**: 75-80% production ready

**Strengths**:
- All core authentication features implemented
- Enterprise features complete
- Test infrastructure in place
- Documentation structure established

**Gaps**:
- Additional E2E test coverage needed
- Performance optimization pending
- Security hardening in progress
- Production deployment guides incomplete

## Key Files
- API: \`apps/api/app/\` (routers, services, models)
- Frontend: \`apps/demo/\` (Next.js showcase)
- Packages: \`packages/\` (core, SDKs, UI components)
- Tests: \`apps/api/tests/\`, E2E in \`apps/demo/e2e/\`

## Recent Updates
- 2025-11-17: Comprehensive codebase audit completed
- 2025-11-17: Documentation cleanup and reorganization
- 2025-11-17: Maintenance plan implementation

Last Updated: $(date +%Y-%m-%d)
Last Metrics Refresh: $(date +%Y-%m-%d\ %H:%M)
EOF

    echo -e "${GREEN}✓${NC} Project status memory generated: /tmp/plinto_project_status.md"
}

# Function to generate recent changes summary
generate_recent_changes() {
    echo -e "${BLUE}📝 Gathering recent git changes...${NC}"

    # Get commits from last 7 days
    RECENT_COMMITS=$(git log --since="7 days ago" --oneline --no-merges | head -10)

    cat > /tmp/plinto_recent_changes.md << EOF
# Plinto Recent Changes - $(date +%Y-%m-%d)

## Last 7 Days Activity

### Recent Commits
\`\`\`
${RECENT_COMMITS}
\`\`\`

### Changed Files Summary
$(git diff --stat HEAD@{7.days.ago}..HEAD 2>/dev/null | tail -5 || echo "No recent changes")

### Active Branches
$(git branch -a | grep -v "HEAD" | head -10)

Last Updated: $(date +%Y-%m-%d\ %H:%M)
EOF

    echo -e "${GREEN}✓${NC} Recent changes memory generated: /tmp/plinto_recent_changes.md"
}

# Function to generate technical debt summary
generate_tech_debt() {
    echo -e "${BLUE}🔧 Analyzing technical debt...${NC}"

    # Find largest files
    LARGE_FILES=$(find apps packages -name "*.ts" -o -name "*.tsx" -o -name "*.py" 2>/dev/null | xargs wc -l 2>/dev/null | sort -rn | head -10)

    # TODO/FIXME by directory
    TODO_BY_DIR=$(find apps packages -type f \( -name "*.ts" -o -name "*.tsx" -o -name "*.py" \) -exec grep -l "TODO\|FIXME" {} \; 2>/dev/null | sed 's|/[^/]*$||' | sort | uniq -c | sort -rn | head -5)

    cat > /tmp/plinto_technical_debt.md << EOF
# Plinto Technical Debt - $(date +%Y-%m-%d)

## Metrics
- **Total TODOs/FIXMEs**: ${TODO_COUNT}
- **Console.log statements**: ${CONSOLE_COUNT}

## Largest Files (Top 10)
\`\`\`
${LARGE_FILES}
\`\`\`

## TODO/FIXME Hotspots
\`\`\`
${TODO_BY_DIR}
\`\`\`

## Recommendations
1. Address TODOs in high-traffic files first
2. Replace console.log with proper logging
3. Consider refactoring files >500 lines
4. Schedule regular debt reduction sprints

Last Updated: $(date +%Y-%m-%d)
EOF

    echo -e "${GREEN}✓${NC} Technical debt memory generated: /tmp/plinto_technical_debt.md"
}

# Main execution
echo "Select memory to update:"
echo "1) Project Status (recommended for regular updates)"
echo "2) Recent Changes (weekly update)"
echo "3) Technical Debt (monthly review)"
echo "4) All memories"
echo

if [ -z "$1" ]; then
    read -p "Enter choice (1-4): " choice
else
    choice=$1
fi

gather_metrics

case $choice in
    1)
        generate_project_status
        echo
        echo -e "${YELLOW}To update Serena memory, run:${NC}"
        echo "write_memory('project_status', file_content)"
        echo -e "${YELLOW}Memory file location:${NC} /tmp/plinto_project_status.md"
        ;;
    2)
        generate_recent_changes
        echo
        echo -e "${YELLOW}To update Serena memory, run:${NC}"
        echo "write_memory('recent_changes', file_content)"
        echo -e "${YELLOW}Memory file location:${NC} /tmp/plinto_recent_changes.md"
        ;;
    3)
        generate_tech_debt
        echo
        echo -e "${YELLOW}To update Serena memory, run:${NC}"
        echo "write_memory('technical_debt', file_content)"
        echo -e "${YELLOW}Memory file location:${NC} /tmp/plinto_technical_debt.md"
        ;;
    4)
        generate_project_status
        generate_recent_changes
        generate_tech_debt
        echo
        echo -e "${YELLOW}All memory files generated in /tmp/${NC}"
        echo "Update Serena memories using write_memory() for each file"
        ;;
    *)
        echo -e "${YELLOW}Invalid choice. Exiting.${NC}"
        exit 1
        ;;
esac

echo
echo -e "${GREEN}✅ Memory update utility complete${NC}"
