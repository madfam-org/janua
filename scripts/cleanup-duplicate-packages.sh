#!/bin/bash

# Cleanup script for duplicate SDK packages
# Created: 2025-09-12
# Purpose: Remove duplicate and redundant package directories to fix npm workspace conflicts

echo "🧹 Cleaning up duplicate SDK packages..."

# Directories to remove (these are duplicates or empty shells)
DIRS_TO_REMOVE=(
  "packages/react-sdk"      # Duplicate of packages/react (renamed to @plinto/react-sdk-deprecated)
  "packages/sdk"            # Incomplete package without package.json
  "packages/sdk-js"         # Duplicate of packages/js-sdk (different name @plinto/sdk vs @plinto/js)
  "packages/typescript-sdk" # Appears to be redundant with js-sdk
)

echo "The following directories will be removed:"
for dir in "${DIRS_TO_REMOVE[@]}"; do
  if [ -d "$dir" ]; then
    echo "  ❌ $dir"
  fi
done

echo ""
echo "⚠️  WARNING: This will permanently delete these directories!"
read -p "Do you want to proceed? (y/N): " -n 1 -r
echo ""

if [[ $REPLY =~ ^[Yy]$ ]]; then
  for dir in "${DIRS_TO_REMOVE[@]}"; do
    if [ -d "$dir" ]; then
      echo "Removing $dir..."
      rm -rf "$dir"
    fi
  done
  echo "✅ Cleanup complete!"
  
  echo ""
  echo "📦 Remaining SDK packages:"
  ls -d packages/*sdk* packages/js* packages/react* packages/vue* 2>/dev/null | grep -v "\.json"
else
  echo "❌ Cleanup cancelled"
  exit 1
fi

echo ""
echo "💡 Next steps:"
echo "1. Build the core SDK: cd packages/js-sdk && npm install && npm run build"
echo "2. Build Next.js SDK: cd packages/nextjs-sdk && npm install && npm run build"
echo "3. Build React SDK: cd packages/react && npm install && npm run build"
echo "4. Deploy to Vercel: git add -A && git commit -m 'fix: resolve duplicate workspace names' && git push"