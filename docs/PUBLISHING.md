# SDK Publishing Guide

> **NPM release instructions superseded.** Use the canonical
> [Publish SDKs workflow](../.github/workflows/publish-sdks.yml) with an
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

Complete guide for publishing all Janua SDKs to their respective package registries.

## Prerequisites

### For NPM Packages (TypeScript, React, Next.js, Vue)
- NPM account with access to `@janua` organization
- Logged in: `npm login`
- 2FA configured

### For Python Package
- PyPI account
- API token configured in `~/.pypirc` or via environment variable
- Optional: TestPyPI account for testing

### For Go Module
- Git repository access
- Permission to create and push tags

## Quick Start

### Unified Publish Script

```bash
# Publish any SDK
./scripts/publish-sdk.sh <sdk-name> [options]

# Examples
./scripts/publish-sdk.sh typescript-sdk --dry-run
./scripts/publish-sdk.sh python-sdk --test-pypi
./scripts/publish-sdk.sh vue-sdk --tag beta
```

### Available SDKs
- `typescript-sdk` - Core TypeScript SDK
- `react-sdk` - React bindings
- `nextjs-sdk` - Next.js integration
- `vue-sdk` - Vue 3 composables
- `python-sdk` - Python client library
- `go-sdk` - Go client library

## NPM Package Publishing

### Pre-publish Checklist

1. **Update version** in `package.json`:
   ```json
   {
     "version": "1.0.0"
   }
   ```

2. **Build the package**:
   ```bash
   cd packages/<sdk-name>
   npm run build
   ```

3. **Run tests**:
   ```bash
   npm test
   npm run lint
   npm run typecheck
   ```

4. **Commit changes**:
   ```bash
   git add .
   git commit -m "chore: prepare <sdk-name> v1.0.0 for release"
   ```

### Publishing Process

**Using the publish script** (recommended):
```bash
# Dry run first
./scripts/publish-npm-sdk.sh typescript-sdk --dry-run

# Actual publish
./scripts/publish-npm-sdk.sh typescript-sdk

# Publish with beta tag
./scripts/publish-npm-sdk.sh typescript-sdk --tag beta
```

**Manual publishing**:
```bash
cd packages/<sdk-name>
npm publish --access public
```

### Post-publish

1. **Verify on NPM**:
   ```bash
   npm view @janua/<sdk-name>@<version>
   ```

2. **Test installation**:
   ```bash
   npm install @janua/<sdk-name>@<version>
   ```

3. **Create git tag**:
   ```bash
   git tag -a <sdk-name>-v<version> -m "Release <version>"
   git push origin <sdk-name>-v<version>
   ```

4. **Create GitHub release** (via GitHub UI or CLI)

## Python Package Publishing

### Pre-publish Checklist

1. **Update version** in `pyproject.toml`:
   ```toml
   [project]
   version = "1.0.0"
   ```

2. **Clean and rebuild**:
   ```bash
   cd packages/python-sdk
   rm -rf dist/ build/ *.egg-info
   python -m build
   ```

3. **Run tests**:
   ```bash
   python -m pytest tests/ -v
   ```

4. **Check package**:
   ```bash
   twine check dist/*
   ```

5. **Commit changes**:
   ```bash
   git add .
   git commit -m "chore: prepare python-sdk v1.0.0 for release"
   ```

### Publishing Process

**Using the publish script** (recommended):
```bash
# Test on TestPyPI first
./scripts/publish-python-sdk.sh --test-pypi

# Dry run for PyPI
./scripts/publish-python-sdk.sh --dry-run

# Actual publish to PyPI
./scripts/publish-python-sdk.sh
```

**Manual publishing**:
```bash
cd packages/python-sdk

# Build
python -m build

# Upload to TestPyPI
twine upload --repository testpypi dist/*

# Upload to PyPI
twine upload --repository pypi dist/*
```

### Post-publish

1. **Verify on PyPI**:
   ```bash
   pip index versions janua
   ```

2. **Test installation**:
   ```bash
   pip install janua==<version>
   ```

3. **Create git tag**:
   ```bash
   git tag -a python-sdk-v<version> -m "Release <version>"
   git push origin python-sdk-v<version>
   ```

## Go Module Publishing

Go modules are published via git tags, not a package registry.

### Publishing Process

1. **Ensure all changes are committed**:
   ```bash
   git status
   git add .
   git commit -m "chore: prepare go-sdk v1.0.0 for release"
   ```

2. **Create and push version tag**:
   ```bash
   # Create tag with go-sdk/ prefix
   git tag -a go-sdk/v1.0.0 -m "Release v1.0.0"
   
   # Push tag
   git push origin go-sdk/v1.0.0
   ```

3. **Verify tag on GitHub**

### Usage by Consumers

```bash
# Install specific version
go get github.com/madfam-org/janua/packages/go-sdk@v1.0.0

# Install latest
go get github.com/madfam-org/janua/packages/go-sdk@latest
```

## Versioning Guidelines

### Semantic Versioning (SemVer)

All SDKs follow semantic versioning: `MAJOR.MINOR.PATCH`

- **MAJOR**: Breaking changes
- **MINOR**: New features (backward compatible)
- **PATCH**: Bug fixes (backward compatible)

### Version Bumping

```bash
# Patch (1.0.0 → 1.0.1)
npm version patch

# Minor (1.0.0 → 1.1.0)
npm version minor

# Major (1.0.0 → 2.0.0)
npm version major

# Specific version
npm version 1.2.3
```

### Pre-release Versions

```bash
# Alpha (1.0.0-alpha.0)
npm version prerelease --preid=alpha

# Beta (1.0.0-beta.0)
npm version prerelease --preid=beta

# Release candidate (1.0.0-rc.0)
npm version prerelease --preid=rc
```

### NPM Tags

```bash
# Publish as latest (default)
npm publish --tag latest

# Publish as beta
npm publish --tag beta

# Publish as next
npm publish --tag next
```

## Troubleshooting

### NPM Package Already Exists

```bash
# Error: You cannot publish over the previously published versions
# Solution: Bump version in package.json
npm version patch
```

### PyPI Version Already Exists

```bash
# Error: File already exists
# Solution: Bump version in pyproject.toml
# Note: You CANNOT overwrite existing PyPI versions
```

### NPM 2FA Issues

```bash
# If 2FA is required
npm publish --otp=<6-digit-code>
```

### PyPI Authentication

```bash
# Set PyPI token
export TWINE_PASSWORD=<your-api-token>
export TWINE_USERNAME=__token__

# Or configure in ~/.pypirc
[pypi]
username = __token__
password = <your-api-token>
```

### Permission Denied

```bash
# NPM: Ensure you're logged in and have access to @janua org
npm login
npm access ls-collaborators @janua/<package>

# PyPI: Ensure you have maintainer access
# Contact package owner to add you as maintainer
```

## Rollback / Unpublishing

### NPM

```bash
# Deprecate a version (preferred)
npm deprecate @janua/<package>@<version> "Deprecated due to security issue"

# Unpublish (within 72 hours only)
npm unpublish @janua/<package>@<version>

# Unpublish entire package (dangerous!)
npm unpublish @janua/<package> --force
```

### PyPI

```bash
# PyPI does not support unpublishing
# Use "yanked" releases instead to hide from installers
# This must be done via PyPI web interface
```

## Automated Publishing (GitHub Actions)

See `.github/workflows/publish-sdk.yml` for automated publishing on tag push.

Trigger automated publish:
```bash
# Create and push tag
git tag -a typescript-sdk-v1.0.0 -m "Release 1.0.0"
git push origin typescript-sdk-v1.0.0

# GitHub Actions will automatically build and publish
```

## Security Best Practices

1. **Enable 2FA** on NPM and PyPI accounts
2. **Use API tokens** instead of passwords
3. **Limit token scope** to specific packages
4. **Rotate tokens** regularly
5. **Review dependencies** before publishing
6. **Sign commits and tags** with GPG
7. **Scan for vulnerabilities**: `npm audit` / `pip-audit`

## Release Checklist

- [ ] Update version in package files
- [ ] Update CHANGELOG.md
- [ ] Run full test suite
- [ ] Build and verify dist/ artifacts
- [ ] Commit all changes
- [ ] Run publish script with --dry-run
- [ ] Publish to registry
- [ ] Verify package on registry
- [ ] Test fresh installation
- [ ] Create and push git tag
- [ ] Create GitHub release
- [ ] Update documentation
- [ ] Announce release (if major)
