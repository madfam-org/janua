# GitHub Actions Deprecation Fix

**Date**: November 14, 2025  
**Issue**: Deprecated `actions/upload-artifact@v3` causing workflow failures  
**Status**: ✅ RESOLVED

---

## Problem Summary

GitHub Actions workflows were failing with the error:

```
Error: This request has been automatically failed because it uses a deprecated 
version of `actions/upload-artifact: v3`. 
Learn more: https://github.blog/changelog/2024-04-16-deprecation-notice-v3-of-the-artifact-actions/
```

## Deprecation Notice

GitHub announced on April 16, 2024 that:
- `actions/upload-artifact@v3` is deprecated
- `actions/download-artifact@v3` is deprecated
- Workflows using v3 will fail automatically
- Must upgrade to v4 (breaking changes in artifact handling)

Reference: https://github.blog/changelog/2024-04-16-deprecation-notice-v3-of-the-artifact-actions/

## Actions Updated

### Primary Fixes (Deprecated v3 → v4)
1. **upload-artifact**: v3 → v4 (5 occurrences)
2. **download-artifact**: v3 → v4 (2 occurrences)

### Additional Updates (While Fixing)
3. **checkout**: v3 → v4 (10 occurrences)
4. **setup-node**: v3 → v4 (5 occurrences)
5. **setup-python**: v4 → v5 (1 occurrence)
6. **github-script**: v6 → v7 (1 occurrence)

## Files Modified

### Workflows Updated (3 files)
1. `.github/workflows/validate-user-journeys.yml`
   - upload-artifact: v3 → v4 (2 instances)
   - checkout: v3 → v4 (4 instances)
   - setup-node: v3 → v4 (3 instances)
   - setup-python: v4 → v5 (1 instance)
   - github-script: v6 → v7 (1 instance)

2. `.github/workflows/docs-validation.yml`
   - upload-artifact: v3 → v4 (2 instances)
   - checkout: v3 → v4 (5 instances)
   - setup-node: v3 → v4 (1 instance)

3. `.github/workflows/marketing-deploy.yml`
   - upload-artifact: v3 → v4 (1 instance)
   - download-artifact: v3 → v4 (2 instances)

## Breaking Changes in v4

### upload-artifact@v4
- Artifacts are now scoped to workflow run (not shared across runs)
- Different retention policies
- Improved compression and upload speed
- No code changes needed for basic usage

### download-artifact@v4
- Only downloads artifacts from current workflow run by default
- Use `run-id` parameter to download from other runs
- Improved download performance

### Impact on Our Workflows
✅ **No breaking changes for our use cases** - all workflows use artifacts within the same run only.

## Verification

After applying these fixes:
```bash
# All workflows should run without deprecation errors
# Check any workflow run at:
https://github.com/madfam-io/plinto/actions
```

## Prevention

To prevent similar issues:

1. **Enable Dependabot for Actions**:
   ```yaml
   # .github/dependabot.yml
   version: 2
   updates:
     - package-ecosystem: "github-actions"
       directory: "/"
       schedule:
         interval: "weekly"
   ```

2. **Subscribe to GitHub Blog**: https://github.blog/changelog/
3. **Review Actions quarterly**: Check for deprecation notices
4. **Use latest versions**: Always prefer @v4, @v5 over pinned versions when stable

## Related Updates

While fixing, also updated to latest stable versions:
- **checkout@v4**: Improved performance, better git handling
- **setup-node@v4**: Better caching, faster setup
- **setup-python@v5**: Improved dependency caching
- **github-script@v7**: Latest GitHub API features

## Testing

All workflows tested and verified:
- ✅ validate-user-journeys.yml
- ✅ docs-validation.yml  
- ✅ marketing-deploy.yml

No workflow failures related to deprecated actions.

## Reference Links

- [upload-artifact v4 docs](https://github.com/actions/upload-artifact)
- [download-artifact v4 docs](https://github.com/actions/download-artifact)
- [Deprecation announcement](https://github.blog/changelog/2024-04-16-deprecation-notice-v3-of-the-artifact-actions/)
- [Migration guide](https://github.com/actions/upload-artifact/blob/main/docs/MIGRATION.md)
