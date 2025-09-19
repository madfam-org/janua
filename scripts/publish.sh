#!/bin/bash

# Plinto Package Publishing Script
# Usage: ./scripts/publish.sh [patch|minor|major] [--dry-run]

set -e

VERSION_TYPE=${1:-patch}
DRY_RUN=${2}

if [[ "$VERSION_TYPE" != "patch" && "$VERSION_TYPE" != "minor" && "$VERSION_TYPE" != "major" ]]; then
    echo "❌ Invalid version type. Use: patch, minor, or major"
    exit 1
fi

echo "🚀 Plinto Package Publishing"
echo "Version bump: $VERSION_TYPE"

if [[ "$DRY_RUN" == "--dry-run" ]]; then
    echo "🧪 DRY RUN MODE - No actual publishing"
fi

echo ""

# Check if we're on main branch
CURRENT_BRANCH=$(git branch --show-current)
if [[ "$CURRENT_BRANCH" != "main" ]]; then
    echo "⚠️  Warning: Not on main branch (current: $CURRENT_BRANCH)"
    read -p "Continue anyway? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# Check working directory is clean
if [[ -n $(git status --porcelain) ]]; then
    echo "❌ Working directory is not clean. Commit or stash changes first."
    exit 1
fi

echo "📦 Building all packages..."

# Build TypeScript packages
for dir in packages/*/; do
    if [ -f "$dir/package.json" ] && [ -f "$dir/tsconfig.json" ]; then
        echo "  Building $(basename $dir)"
        cd "$dir"
        npm run build || {
            echo "❌ Build failed for $(basename $dir)"
            exit 1
        }
        cd - > /dev/null
    fi
done

# Build Python package
if [ -d "packages/python-sdk" ]; then
    echo "  Building Python SDK"
    cd packages/python-sdk
    python -m build || {
        echo "❌ Python build failed"
        exit 1
    }
    cd - > /dev/null
fi

echo "✅ All packages built successfully"

# Run tests
echo "🧪 Running tests..."
npm run test || {
    echo "⚠️  Tests failed, but continuing..."
}

# Update versions
if [[ "$DRY_RUN" != "--dry-run" ]]; then
    echo "📝 Updating package versions..."
    
    for dir in packages/*/; do
        if [ -f "$dir/package.json" ] && ! grep -q '"private": true' "$dir/package.json"; then
            PACKAGE_NAME=$(node -p "require('$dir/package.json').name")
            echo "  Updating $PACKAGE_NAME"
            cd "$dir"
            npm version $VERSION_TYPE --no-git-tag-version
            cd - > /dev/null
        fi
    done
fi

# Get version for tagging
VERSION=$(node -p "require('./packages/typescript-sdk/package.json').version")

echo ""
echo "📋 Publishing Summary:"
echo "  Version: $VERSION"
echo "  Packages to publish:"

PACKAGES_TO_PUBLISH=()
for dir in packages/*/; do
    if [ -f "$dir/package.json" ] && ! grep -q '"private": true' "$dir/package.json"; then
        PACKAGE_NAME=$(node -p "require('$dir/package.json').name")
        echo "    - $PACKAGE_NAME"
        PACKAGES_TO_PUBLISH+=("$dir")
    fi
done

if [[ "$DRY_RUN" == "--dry-run" ]]; then
    echo ""
    echo "🧪 DRY RUN COMPLETED - No packages were actually published"
    exit 0
fi

echo ""
read -p "🚨 Proceed with publishing? (y/N): " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "❌ Publishing cancelled"
    exit 1
fi

# Check for npm authentication
if ! npm whoami > /dev/null 2>&1; then
    echo "❌ Not logged in to npm. Run 'npm login' first."
    exit 1
fi

echo "📤 Publishing to npm..."

for dir in "${PACKAGES_TO_PUBLISH[@]}"; do
    PACKAGE_NAME=$(node -p "require('$dir/package.json').name")
    echo "  Publishing $PACKAGE_NAME"
    cd "$dir"
    
    if npm publish --access public; then
        echo "  ✅ $PACKAGE_NAME published successfully"
    else
        echo "  ❌ Failed to publish $PACKAGE_NAME"
        exit 1
    fi
    
    cd - > /dev/null
done

# Publish Python package if PyPI token is available
if [ -n "$PYPI_TOKEN" ] && [ -d "packages/python-sdk" ]; then
    echo "📤 Publishing Python package to PyPI..."
    cd packages/python-sdk
    
    export TWINE_USERNAME=__token__
    export TWINE_PASSWORD=$PYPI_TOKEN
    
    if python -m twine upload dist/*; then
        echo "  ✅ Python package published successfully"
    else
        echo "  ❌ Failed to publish Python package"
    fi
    
    cd - > /dev/null
fi

# Create git tag and push
echo "🏷️  Creating git tag v$VERSION..."
git add .
git commit -m "chore: release v$VERSION"
git tag "v$VERSION"
git push origin "v$VERSION"
git push origin main

echo ""
echo "🎉 Publishing completed successfully!"
echo "   Version: v$VERSION"
echo "   Packages published: ${#PACKAGES_TO_PUBLISH[@]}"
echo ""
echo "📊 Check packages:"
echo "   npm: https://www.npmjs.com/org/plinto"
echo "   PyPI: https://pypi.org/project/plinto-sdk/"