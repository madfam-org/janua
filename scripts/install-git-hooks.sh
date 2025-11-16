#!/bin/bash
# Install Git Pre-Commit Hooks
# Provides two-tier protection for the Plinto codebase

set -e

echo "Installing Git pre-commit hooks..."

# Create the pre-commit hook
cat > .git/hooks/pre-commit << 'EOF'
#!/usr/bin/env sh

# Prevent environment files from being committed
if git diff --cached --name-only | grep -qE "^\.env$|\.env\.local$|\.env\.production$|\.env\.staging$|\.env\.development$"; then
  echo "❌ ERROR: Environment files detected in commit!"
  echo ""
  echo "The following environment files should NOT be committed:"
  git diff --cached --name-only | grep -E "^\.env|\.env\."
  echo ""
  echo "These files may contain sensitive information."
  echo "Please use .env.example files for documentation instead."
  echo ""
  echo "To unstage these files, run:"
  echo "  git reset HEAD <file>"
  exit 1
fi

# Prevent debug statements in production code (warning only)
DEBUG_FILES=$(git diff --cached --name-only --diff-filter=ACM | grep -E "\.(ts|tsx|js|jsx|py)$" | grep -v "test\|spec\|\\.example")
if [ -n "$DEBUG_FILES" ]; then
  DEBUG_COUNT=0
  for file in $DEBUG_FILES; do
    # Check for console.log/console.error/print() in non-test files
    if git diff --cached "$file" | grep -E "^\+.*console\.(log|error|warn|debug)\(|^\+.*print\(" | grep -v "logger\." > /dev/null; then
      if [ $DEBUG_COUNT -eq 0 ]; then
        echo "⚠️  WARNING: Debug statements detected in staged files:"
        echo ""
      fi
      DEBUG_COUNT=$((DEBUG_COUNT + 1))
      echo "  - $file"
    fi
  done

  if [ $DEBUG_COUNT -gt 0 ]; then
    echo ""
    echo "Consider using the logger utility instead:"
    echo "  TypeScript: import { createLogger } from '@plinto/core/utils/logger'"
    echo "  Python: from app.utils.logger import create_logger"
    echo ""
    echo "Press Ctrl+C to cancel commit, or Continue to commit anyway."
    sleep 2
  fi
fi

echo "✅ Pre-commit checks passed"
EOF

# Make the hook executable
chmod +x .git/hooks/pre-commit

echo "✅ Pre-commit hook installed successfully!"
echo ""
echo "Hook protects against:"
echo "  🔒 Environment file commits (BLOCKS)"
echo "  ⚠️  Debug statements (WARNS)"
echo ""
echo "Test the hook by attempting to commit a .env file."
