# npm Workspace Protocol Fix

**Date**: November 14, 2025
**Issue**: `npm ci` failing with "Unsupported URL Type 'workspace:'" error
**Status**: ✅ RESOLVED

---

## Problem Summary

GitHub Actions workflows were failing during `npm ci` with the error:

```
npm error code EUNSUPPORTEDPROTOCOL
npm error Unsupported URL Type "workspace:": workspace:*
```

## Root Cause

Two package.json files in the monorepo used **pnpm/Yarn workspace protocol syntax** (`workspace:*`) instead of **npm workspace syntax** (`*`):

1. `tests/test-app/package.json`
2. `apps/landing/package.json`

Both files had:
```json
"@plinto/typescript-sdk": "workspace:*"
```

The `workspace:` protocol is specific to **pnpm** and **Yarn 2+** but is **not supported by npm**, even though npm has its own workspace functionality.

## Package Manager Comparison

| Package Manager | Workspace Dependency Syntax | Supported? |
|----------------|---------------------------|-----------|
| **npm** | `"@plinto/typescript-sdk": "*"` | ✅ Correct |
| **pnpm** | `"@plinto/typescript-sdk": "workspace:*"` | ❌ Wrong for our project |
| **Yarn 2+** | `"@plinto/typescript-sdk": "workspace:*"` | ❌ Wrong for our project |

## Project Configuration

The root `package.json` specifies:
```json
{
  "packageManager": "npm@10.8.2",
  "workspaces": [
    "packages/*",
    "apps/*"
  ]
}
```

This means the project **uses npm workspaces**, not pnpm or Yarn.

## Solution

Changed the workspace dependency syntax from pnpm/Yarn format to npm format:

### Before (Incorrect - pnpm/Yarn syntax)
```json
{
  "dependencies": {
    "@plinto/typescript-sdk": "workspace:*"
  }
}
```

### After (Correct - npm syntax)
```json
{
  "dependencies": {
    "@plinto/typescript-sdk": "*"
  }
}
```

## Files Modified

### 1. `tests/test-app/package.json`
**Line 14**: Changed `"workspace:*"` → `"*"`

### 2. `apps/landing/package.json`
**Line 16**: Changed `"workspace:*"` → `"*"`

### 3. `package-lock.json`
Regenerated to reflect the corrected dependency references

## How npm Workspaces Work

When you use `"*"` as a version in an npm workspace:

1. **Local Resolution**: npm checks if the package exists in the workspace
2. **Automatic Linking**: If found, npm creates a symlink to the local workspace package
3. **Version Matching**: `"*"` matches any version of the local package
4. **Fallback**: If not in workspace, npm would fetch from registry (but won't because package is local)

Example:
```json
// In apps/landing/package.json
{
  "dependencies": {
    "@plinto/typescript-sdk": "*"  // Links to packages/typescript-sdk
  }
}
```

npm resolves this to the local `packages/typescript-sdk` workspace package.

## Verification

To verify the fix:

```bash
# Clean install should now work
npm ci

# Or test with dry-run first
npm ci --dry-run

# Verify workspace linking
npm ls @plinto/typescript-sdk
```

## Affected GitHub Actions Workflows

This fix resolves failures in workflows that run `npm ci`:

- `.github/workflows/validate-user-journeys.yml`
- `.github/workflows/docs-validation.yml`
- `.github/workflows/marketing-deploy.yml`
- Any other workflow with `npm ci` steps

## Prevention

To prevent this issue in the future:

1. **Check package manager configuration** in root `package.json`:
   ```json
   "packageManager": "npm@10.8.2"
   ```

2. **Use correct workspace syntax** for the configured package manager:
   - **npm**: `"package-name": "*"`
   - **pnpm**: `"package-name": "workspace:*"`
   - **Yarn 2+**: `"package-name": "workspace:*"`

3. **Test locally before CI**:
   ```bash
   npm ci --dry-run  # Catch syntax errors before pushing
   ```

4. **Lock file validation**: Ensure `package-lock.json` is committed after dependency changes

## Why the Syntax Differs

### npm Workspaces
- Uses standard semver version syntax (`*`, `^1.0.0`, etc.)
- Automatically resolves to workspace packages when available
- No special protocol needed

### pnpm Workspaces
- Uses explicit `workspace:` protocol
- More explicit about workspace vs registry resolution
- Supports `workspace:*`, `workspace:^`, `workspace:~`

### Yarn 2+ (Berry)
- Also uses explicit `workspace:` protocol
- Provides workspace version aliasing
- Designed for Plug'n'Play (PnP) architecture

Our project uses **npm**, so we must use npm's simpler `"*"` syntax.

## Related Documentation

- [npm workspaces documentation](https://docs.npmjs.com/cli/v10/using-npm/workspaces)
- [pnpm workspace protocol](https://pnpm.io/workspaces#workspace-protocol-workspace)
- [Yarn workspace protocol](https://yarnpkg.com/features/workspaces#workspace-ranges-workspace)

## Testing

Verified fix with:
```bash
# Test in root (full monorepo)
npm ci --dry-run  # ✅ Success

# Test in specific workspace
cd apps/landing
npm install  # ✅ Correctly links @plinto/typescript-sdk
```

## Lock File Regeneration

After fixing the package.json files, regenerated the lock file:

```bash
npm install  # Regenerates package-lock.json with correct references
```

This ensures:
- ✅ Workspace dependencies resolved correctly
- ✅ Lock file matches package.json
- ✅ `npm ci` works in CI/CD pipelines
- ✅ No "unsupported protocol" errors

## Summary

**Problem**: Used pnpm/Yarn workspace syntax in npm monorepo
**Solution**: Changed `"workspace:*"` → `"*"` in package.json files
**Impact**: Fixed all npm ci failures in GitHub Actions workflows
**Prevention**: Use correct workspace syntax for configured package manager
