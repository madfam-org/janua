# 📚 Janua Documentation System

## Overview

The Janua documentation system implements a robust content pipeline with automated validation to ensure high-quality, consistent documentation across internal and public-facing materials.

## 🏗️ Architecture

```
Documentation System
├── Content Sources
│   ├── /docs (Internal)
│   └── /apps/docs (Public)
├── Pipeline Tools
│   ├── Content Management
│   ├── Validation
│   └── Automation
└── Quality Assurance
    ├── Pre-commit Hooks
    ├── CI/CD Validation
    └── Health Monitoring
```

## 🔧 Components

### 1. Content Pipeline (`scripts/docs-pipeline.sh`)

Interactive tool for managing documentation workflow:

```bash
# Interactive menu
npm run docs:pipeline

# Direct commands
npm run docs:pipeline list           # List drafts
npm run docs:pipeline promote <file> <target>  # Promote draft
npm run docs:pipeline check          # Check duplicates
npm run docs:pipeline health         # Health check
```

**Features:**
- Draft management and promotion
- Content validation before publishing
- Duplicate detection
- Archive management
- Interactive workflow

### 2. Automated Validation (`scripts/maintenance/check-docs.sh`)

Comprehensive validation suite:

```bash
npm run docs:validate
```

**Checks:**
- ✅ No duplicate content
- ✅ No sensitive information
- ✅ No internal URLs in public docs
- ✅ No broken links
- ✅ Draft age monitoring
- ✅ File size limits
- ✅ TODO/FIXME detection

### 3. Pre-commit Hooks (`.husky/pre-commit-docs`)

Automatic validation on commit:

**Validates:**
- Sensitive information detection
- Internal URL prevention
- Duplicate file prevention
- Broken link detection
- TODO comments in public docs
- File size warnings

### 4. CI/CD Pipeline (`.github/workflows/docs-validation.yml`)

GitHub Actions workflow:

**Jobs:**
- `validate-structure` - Directory structure validation
- `check-duplicates` - Duplicate content detection
- `check-sensitive-info` - Security scanning
- `check-broken-links` - Link validation
- `validate-drafts` - Draft age monitoring
- `quality-metrics` - Documentation coverage

### 5. Health Dashboard (`scripts/generate-docs-dashboard.js`)

Real-time documentation health metrics:

```bash
npm run docs:dashboard
```

**Generates:**
- Overall health score (0-100)
- Key metrics tracking
- Risk assessment
- Coverage analysis
- Active issues list
- Trend analysis

## 📋 Content Guidelines

### Directory Structure

```
/docs/                      # Internal documentation
├── internal/              # Team-only docs
│   ├── architecture/
│   ├── reports/
│   └── operations/
├── drafts/               # Content being prepared
├── archive/              # Historical content
└── CONTENT_GUIDELINES.md # Full guidelines

/apps/docs/               # Public documentation
├── content/             # Markdown content
│   ├── api/
│   ├── sdks/
│   └── guides/
└── app/                # MDX pages
```

### Content Rules

1. **No Duplication**: Single source of truth
2. **Clear Ownership**: Each doc has one location
3. **Content Pipeline**: drafts → review → public
4. **Security First**: No sensitive info in public

## 🚀 Quick Start

### Initial Setup

```bash
# Install dependencies
npm install

# Make scripts executable
chmod +x scripts/*.sh

# Generate initial dashboard
npm run docs:dashboard
```

### Daily Workflow

```bash
# Check documentation health
npm run docs:health

# Validate before committing
npm run docs:validate

# Promote draft to public
npm run docs:pipeline promote drafts/my-doc.md guides

# Update dashboard
npm run docs:dashboard
```

### Common Commands

| Command | Description |
|---------|-------------|
| `npm run docs:validate` | Run full validation suite |
| `npm run docs:health` | Quick health check |
| `npm run docs:dashboard` | Generate health dashboard |
| `npm run docs:pipeline` | Interactive pipeline manager |
| `npm run docs:check` | Check for duplicates |

## 📊 Health Metrics

### Scoring System

The health score (0-100) is calculated based on:

- **Structure** (30 points)
  - Proper directory organization
  - No forbidden directories
  - Reasonable draft count

- **Quality** (40 points)
  - No duplicate content
  - No sensitive information
  - No TODOs in public
  - Reasonable file sizes

- **Coverage** (30 points)
  - API documentation present
  - SDK documentation complete
  - User guides available
  - Quick start exists

### Health Indicators

- 🟢 **90-100**: Excellent health
- 🟡 **70-89**: Good, minor issues
- 🟠 **50-69**: Needs attention
- 🔴 **0-49**: Critical issues

## 🔄 Automation

### Pre-commit Validation

Automatically runs on `git commit`:
- Validates changed documentation files
- Prevents commits with critical issues
- Provides actionable feedback

### CI/CD Integration

Runs on every PR:
- Full validation suite
- Security scanning
- Link checking
- Coverage analysis

### Weekly Reports

GitHub Actions generates weekly:
- Health dashboard update
- Trend analysis
- Issue tracking

## 🛠️ Troubleshooting

### Common Issues

**Issue**: Duplicate content detected
```bash
# Find duplicates
npm run docs:check

# Review and consolidate
# Move to single location per guidelines
```

**Issue**: Old drafts warning
```bash
# List old drafts
npm run docs:pipeline list

# Promote or archive
npm run docs:pipeline promote <file> <target>
```

**Issue**: Validation failures
```bash
# Run detailed validation
npm run docs:validate

# Check specific file
./scripts/docs-pipeline.sh validate <file>
```

## 📈 Best Practices

1. **Regular Health Checks**: Run weekly dashboard updates
2. **Draft Management**: Review drafts monthly
3. **Link Validation**: Check before major releases
4. **Security Scanning**: Review warnings immediately
5. **Coverage Monitoring**: Ensure all features documented

## 🔗 Related Documentation

- [Content Guidelines](./CONTENT_GUIDELINES.md) - Detailed content rules
- [Documentation Health](./DOCUMENTATION_HEALTH.md) - Current health dashboard
- [Public Docs README](../apps/docs/README.md) - Frontend documentation

## 📞 Support

For documentation system issues:
1. Check this guide
2. Review error messages
3. Run validation tools
4. Check CI/CD logs

---

*Last Updated: January 2025*
*System Version: 1.0.0*