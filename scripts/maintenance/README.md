# Plinto Maintenance System

Automated maintenance infrastructure for code quality, documentation health, and system monitoring.

## Overview

The maintenance system provides automated checks, scheduled workflows, and manual utilities to keep the Plinto codebase healthy and production-ready.

## Quick Start

```bash
# Run all maintenance checks
./scripts/maintenance/check-code-quality.sh
./scripts/maintenance/check-docs.sh

# Update Serena project memories
./scripts/maintenance/update-memory.sh 1  # Project status
./scripts/maintenance/update-memory.sh 4  # All memories
```

## Automated Scripts

### 1. Code Quality Check (`check-code-quality.sh`)

**Purpose**: Monitor code quality metrics and enforce quality gates

**Checks**:
- ✅ TODO/FIXME count in production code (threshold: 60)
- ✅ console.log statements (threshold: 100)
- ✅ .env files tracked in git (should be 0)
- ✅ Build system health (all SDKs)
- ✅ Large files >1MB (excluding assets)

**Exit Codes**:
- `0`: All checks passed
- `1`: Warnings found (review recommended)
- `2`: Critical issues (immediate action required)

**Usage**:
```bash
# Run locally
./scripts/maintenance/check-code-quality.sh

# In CI/CD (already configured)
# Runs automatically on push/PR to main
```

**Output Example**:
```
🔍 Running Code Quality Checks...

✓ TODO/FIXME count: 45 (threshold: 60)
⚠️  console.log count: 112 (threshold: 100) - 12 over limit
✓ No .env files tracked in git
✓ Build system health: 5/6 SDKs passing
✓ No large files found

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
⚠️  WARNINGS - 1 issue found (recommend review)
```

### 2. Documentation Check (`check-docs.sh`)

**Purpose**: Verify documentation freshness, accuracy, and completeness

**Checks**:
- 📅 Outdated documentation (>90 days)
- 📄 Missing README files in key directories
- 🔗 Broken internal links
- 📚 Documentation index currency
- 📝 Documentation TODOs (threshold: 10)
- 📊 Implementation report dating
- 📦 Archive structure compliance

**Exit Codes**:
- `0`: All checks passed
- `1`: Warnings found (review recommended)
- `2`: Critical issues (immediate action required)

**Usage**:
```bash
# Run locally
./scripts/maintenance/check-docs.sh

# In CI/CD (already configured)
# Runs automatically on push/PR to main
```

**Output Example**:
```
🔍 Running Documentation Maintenance Checks...

✓ All documentation recently updated
⚠️  Missing README in apps/demo
✓ No broken internal links detected
✓ Documentation index appears current
✓ Documentation TODOs: 7 (acceptable)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
⚠️  WARNINGS - 1 issue found (recommend review)
```

### 3. Memory Update Utility (`update-memory.sh`)

**Purpose**: Keep Serena MCP project memories current with codebase state

**Generates**:
1. **Project Status**: Current metrics, feature status, build health
2. **Recent Changes**: Last 7 days git activity, changed files
3. **Technical Debt**: TODOs by directory, large files, code smells

**Usage**:
```bash
# Interactive mode
./scripts/maintenance/update-memory.sh

# Direct selection
./scripts/maintenance/update-memory.sh 1  # Project status only
./scripts/maintenance/update-memory.sh 2  # Recent changes only
./scripts/maintenance/update-memory.sh 3  # Technical debt only
./scripts/maintenance/update-memory.sh 4  # All memories
```

**Output**:
- Generates markdown files in `/tmp/plinto_*.md`
- Provides instructions for updating Serena memories
- Auto-refreshes metrics from current codebase state

**Recommended Schedule**:
- Project Status: Weekly (Monday)
- Recent Changes: Weekly (Friday)
- Technical Debt: Monthly (1st of month)

## GitHub Actions Workflow

Automated maintenance runs daily and on every push/PR to main.

**Configuration**: `.github/workflows/maintenance.yml`

**Jobs**:
1. **code-quality**: Run code quality checks
2. **documentation**: Run documentation checks
3. **dependency-audit**: Security vulnerability scanning
4. **build-verification**: Full build + typecheck + lint
5. **test-suite**: Unit tests with coverage tracking
6. **maintenance-summary**: Consolidated status report

**Schedule**:
- Daily: 6 AM UTC (automated checks)
- Push/PR: On every commit to main
- Manual: Via workflow_dispatch

**Artifacts**:
- Code coverage reports (7 days retention)
- Test results
- Build logs

**Notifications**:
- PR comments for quality issues
- GitHub Issues created for security vulnerabilities
- Workflow summary with status table

## Maintenance Schedule

See `docs/MAINTENANCE_SCHEDULE.md` for comprehensive checklist.

**Daily** (Automated):
- Build health
- Test suite
- Code quality checks

**Weekly** (Every Monday):
- Documentation review
- Dependency management
- Code quality deep dive
- Update Serena memories

**Bi-Weekly** (1st & 15th):
- Memory management review
- Performance monitoring

**Monthly** (1st of Month):
- Comprehensive audit
- Documentation freshness
- Dependency updates
- Security review

**Quarterly**:
- Strategic assessment
- Technical debt review
- Documentation overhaul
- Major dependency updates

## Integration with Development Workflow

### Pre-commit Hooks

Add to `.husky/pre-commit`:
```bash
#!/bin/bash
npm run lint-staged
./scripts/maintenance/check-code-quality.sh
```

### Pre-push Validation

Add to `.husky/pre-push`:
```bash
#!/bin/bash
npm run test
./scripts/maintenance/check-docs.sh
```

### Release Checklist

Before major releases:
1. Run all maintenance scripts
2. Update Serena memories (option 4)
3. Review documentation freshness
4. Run comprehensive security audit
5. Update CHANGELOG.md
6. Tag release

## Monitoring & Metrics

### Key Performance Indicators

| Metric | Target | Critical Threshold |
|--------|--------|-------------------|
| Build Success Rate | >95% | <90% |
| Test Pass Rate | 100% | <95% |
| Code Coverage | >60% | <50% |
| TODO Count | <60 | >100 |
| Documentation Age | <90 days | >180 days |
| Security Vulnerabilities | 0 high/critical | >5 moderate |

### Trend Tracking

Monitor these metrics over time:
- Code growth rate (lines added/removed)
- Test coverage trend
- TODO accumulation rate
- Documentation freshness
- Dependency update lag

## Troubleshooting

### Check Failing: Build System

```bash
# Diagnose build failures
npm run build 2>&1 | tee build-error.log

# Check specific packages
cd packages/core && npm run build
cd packages/react-sdk && npm run build
```

### Check Failing: Too Many TODOs

```bash
# Find TODO hotspots
grep -r "TODO\|FIXME" apps packages --include="*.ts" --include="*.tsx" | 
  cut -d: -f1 | sort | uniq -c | sort -rn | head -10

# Review and resolve highest-count files first
```

### Check Failing: Outdated Documentation

```bash
# Find oldest documentation
find docs -name "*.md" -type f -exec stat -f "%m %N" {} \; | 
  sort -n | head -10

# Review and update or archive
```

### Memory Update Issues

```bash
# Verify metrics manually
npm run build
npm run test
npm audit

# Check git status
git log --oneline -10
git status
```

## Extension Points

### Adding New Checks

1. Create script in `scripts/maintenance/check-*.sh`
2. Follow exit code convention (0=pass, 1=warning, 2=critical)
3. Add colored output for readability
4. Update `.github/workflows/maintenance.yml` to include new check
5. Document in this README

### Custom Metrics

Add to `update-memory.sh`:
```bash
# Example: Track API endpoint count
ENDPOINT_COUNT=$(grep -r "@app\." apps/api --include="*.py" | wc -l)

# Add to memory template
echo "- **API Endpoints**: ${ENDPOINT_COUNT}" >> /tmp/plinto_project_status.md
```

### Alert Thresholds

Modify thresholds in check scripts:
```bash
# In check-code-quality.sh
TODO_THRESHOLD=60  # Adjust as needed
CONSOLE_THRESHOLD=100
```

## Best Practices

1. **Run Locally First**: Test maintenance scripts locally before relying on CI/CD
2. **Review Warnings**: Don't ignore warnings; they indicate trends toward critical issues
3. **Update Regularly**: Keep Serena memories current (weekly minimum)
4. **Document Changes**: When fixing issues, document root cause and solution
5. **Automate Everything**: Prefer automated checks over manual reviews
6. **Monitor Trends**: Track metrics over time, not just current state

## Support

- **Issues**: Report maintenance system bugs via GitHub Issues with `maintenance` label
- **Enhancements**: Suggest improvements via GitHub Discussions
- **Documentation**: Update this README when adding new features

---

**Created**: 2025-11-17  
**Last Updated**: 2025-11-17  
**Version**: 1.0.0
