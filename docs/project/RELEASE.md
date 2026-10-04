# Janua Package Release Management

> **NPM release instructions superseded.** Use the canonical
> [Publish SDKs workflow](../../.github/workflows/publish-sdks.yml) with an
> allowlisted package directory and the exact version already committed in its
> manifest (or its matching `<directory>-v<version>` tag). It builds workspace
> dependencies, tests the package, packs with pnpm, inspects the rewritten
> manifest, and publishes that exact tarball to `https://npm.madfam.io` with
> restricted access. Already-published versions and registry lookup errors stop
> the run. Existing release tags must resolve to the selected commit. Internal
> runtime dependencies must already have published versions satisfying the
> packed exact, caret, or tilde range; publish dependencies before consumers.
> The former `publish.yml` bulk publisher is retired. The legacy manual
> npm/public-registry commands below are historical, not an approved release path.
> Package publication and release tags require explicit operator authorization.

## 🚀 Release Process

### Quick Release
```bash
# Automated release with version bump
./scripts/publish.sh patch --dry-run  # Test first
./scripts/publish.sh patch            # Publish patch version
```

### Manual Release Steps

1. **Prepare Release**
   ```bash
   git checkout main
   git pull origin main
   npm ci
   npm run test
   ```

2. **Build All Packages**
   ```bash
   # TypeScript packages
   cd packages/typescript-sdk && npm run build
   cd packages/react-sdk && npm run build
   cd packages/vue-sdk && npm run build
   # ... repeat for other packages
   
   # Python package
   cd packages/python-sdk && python -m build
   ```

3. **Version Management**
   ```bash
   # Bump versions across all packages
   for dir in packages/*/; do
     if [ -f "$dir/package.json" ] && ! grep -q '"private": true' "$dir/package.json"; then
       cd "$dir" && npm version patch && cd -
     fi
   done
   ```

4. **Publishing**
   ```bash
   # Ensure npm authentication
   npm whoami
   
   # Publish each package
   cd packages/typescript-sdk && npm publish --access public
   cd packages/react-sdk && npm publish --access public
   # ... repeat for other packages
   
   # Python package (requires PYPI_TOKEN)
   cd packages/python-sdk && python -m twine upload dist/*
   ```

5. **Git Tagging**
   ```bash
   VERSION=$(node -p "require('./packages/typescript-sdk/package.json').version")
   git add .
   git commit -m "chore: release v$VERSION"
   git tag "v$VERSION"
   git push origin "v$VERSION"
   git push origin main
   ```

## 📦 Package Status

### Core SDKs (v1.0.0)
- ✅ `@janua/typescript-sdk` - Main SDK for TypeScript/JavaScript
- ✅ `@janua/react-sdk` - React hooks and components  
- ✅ `@janua/vue-sdk` - Vue.js integration
- ✅ `@janua/react-native-sdk` - React Native mobile SDK
- ✅ `@janua/nextjs-sdk` - Next.js specific SDK (v1.0.0)
- ✅ `@janua/flutter-sdk` - Flutter/Dart SDK
- ✅ `@janua/go-sdk` - Go language SDK
- ✅ `janua-sdk` - Python SDK

### Utility Packages (v1.0.0)
- ✅ `@janua/core` - Shared business logic
- ✅ `@janua/ui` - Component library (v1.0.0)
- ✅ `@janua/jwt-utils` - JWT utilities (v1.0.0)
- ✅ `@janua/edge` - Edge function utilities (v1.0.0)
- ✅ `@janua/monitoring` - Monitoring tools (v1.0.0)

### Private Packages
- 🔒 `@janua/mock-api` - Development testing (v1.0.0, private)

## 🔧 CI/CD Integration

### GitHub Actions
- **Workflow**: `.github/workflows/publish.yml`
- **Trigger**: Manual workflow dispatch
- **Features**: 
  - Version bumping (patch/minor/major)
  - Dry run mode
  - Multi-language support (Node.js + Python)
  - Automated git tagging

### Environment Variables Required
```bash
# NPM Registry
NPM_TOKEN=npm_xxxxxxxxxxxxx

# PyPI Registry  
PYPI_TOKEN=pypi-xxxxxxxxxxxxx

# GitHub
GITHUB_TOKEN=ghp_xxxxxxxxxxxxx (auto-provided)
```

## 📋 Release Checklist

### Pre-Release
- [ ] All tests passing
- [ ] All packages building successfully
- [ ] Version numbers synchronized
- [ ] Documentation updated
- [ ] CHANGELOG.md updated

### Release
- [ ] NPM packages published
- [ ] Python package published to PyPI
- [ ] Git tag created and pushed
- [ ] GitHub release created
- [ ] Documentation deployed

### Post-Release
- [ ] Verify packages installable via npm/pip
- [ ] Test imports in sample projects
- [ ] Update dependent projects
- [ ] Announce release

## 🎯 Version Strategy

- **Major (x.0.0)**: Breaking API changes
- **Minor (1.x.0)**: New features, backward compatible
- **Patch (1.0.x)**: Bug fixes, backward compatible

### Synchronized Versioning
All packages maintain the same version number for consistency and easier dependency management.

## 🚨 Troubleshooting

### Build Failures
```bash
# Clean and rebuild
rm -rf packages/*/dist packages/*/node_modules
npm ci
npm run build
```

### Publishing Failures
```bash
# Check npm authentication
npm whoami

# Check package permissions
npm access list packages @janua

# Force publish if needed
npm publish --force --access public
```

### Version Conflicts
```bash
# Reset versions to current
git checkout -- packages/*/package.json

# Manual version update
npm version --workspace=packages/typescript-sdk patch
```

## 📊 Registry Links

- **NPM Organization**: https://www.npmjs.com/org/janua
- **PyPI Project**: https://pypi.org/project/janua-sdk/
- **GitHub Releases**: https://github.com/madfam-org/janua/releases