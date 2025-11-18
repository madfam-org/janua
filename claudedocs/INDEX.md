# Claude Internal Documentation Index

**Purpose**: Internal documentation for Claude Code sessions, implementation progress, and technical analysis.  
**Audience**: Development team, future Claude sessions  
**Last Updated**: November 17, 2025

---

## Current Documentation (Nov 17, 2025)

All documentation reflects the **latest comprehensive audit** and **active implementation work**.

### 📊 Implementation Reports

**Location**: `claudedocs/implementation-reports/`

#### Active Reports (Nov 17, 2025)
1. **[Codebase Status Report](implementation-reports/codebase-status-nov17-2025.md)** ⭐
   - Evidence-based comprehensive codebase analysis
   - 374,697 LOC across 1,015 source files
   - 75-80% production readiness assessment
   - All enterprise features verified

2. **[Cleanup Analysis](implementation-reports/cleanup-analysis-nov17-2025.md)** ⭐
   - Code quality and technical debt assessment
   - 30 production TODOs identified and categorized
   - Cleanup automation system implemented
   - Quick wins and production roadmap

3. **[Distributed Session Manager Testing](implementation-reports/distributed-session-manager-testing-complete.md)**
   - Complete testing implementation
   - Comprehensive test coverage
   - Service validation

4. **[JWT Service Bug Report](implementation-reports/jwt-service-bugs-found.md)**
   - Bug identification and analysis
   - Critical issues documented

5. **[JWT Service Fixes](implementation-reports/jwt-service-fixes-applied.md)**
   - Bug resolution implementation
   - Service improvements

---

## Archive

**Location**: `claudedocs/archive/`

Archived documents are preserved for historical context but **superseded by current comprehensive reports**.

### November 2025 Archive
- Session notes from Nov 13 (pre-comprehensive audit)
- Week 1 guides (superseded by current implementation status)

**Rule**: Documents older than current sprint or superseded by comprehensive reports → archived.

---

## Document Structure

```
claudedocs/
├── INDEX.md                          # This file
├── implementation-reports/           # Current active reports
│   ├── codebase-status-nov17-2025.md        ⭐ Primary reference
│   ├── cleanup-analysis-nov17-2025.md       ⭐ Quality/debt tracking
│   ├── distributed-session-manager-testing-complete.md
│   ├── jwt-service-bugs-found.md
│   └── jwt-service-fixes-applied.md
└── archive/                          # Historical documents
    └── 2025-11/                      # November 2025 archive
        ├── 2025-11-13-auth-endpoints.md
        ├── 2025-11-13-breakthrough-final.md
        ├── week1-foundation-complete.md
        └── week1-implementation-guide.md
```

---

## Usage Guidelines

### For Development Team

**Before Starting Work**:
1. Read [Codebase Status Report](implementation-reports/codebase-status-nov17-2025.md)
2. Review [Cleanup Analysis](implementation-reports/cleanup-analysis-nov17-2025.md) for TODOs
3. Check relevant implementation reports

**After Completing Work**:
1. Create new implementation report if significant milestone
2. Update this INDEX if new active documentation added

### For Future Claude Sessions

**Session Start**:
1. Read this INDEX
2. Load [Codebase Status Report](implementation-reports/codebase-status-nov17-2025.md) for context
3. Review latest implementation reports

**Session Work**:
1. Reference existing reports for context
2. Create new reports for significant work

**Session End**:
1. Create session report if major breakthrough/milestone
2. Update INDEX if new active documentation

---

## Key Principles

### ✅ Keep Active
- **Latest comprehensive reports** (Nov 17, 2025)
- **Current sprint documentation**
- **Actionable implementation guides**

### 📦 Archive When
- Superseded by comprehensive reports
- Implementation phase complete (historical reference only)
- Age > 1 month and no longer actively referenced
- Duplicate/redundant information

### ❌ Delete When
- Temporary debugging notes
- Incomplete drafts with no value
- Outdated without historical significance

---

## Recent Cleanup (Nov 17, 2025)

### ✅ Actions Taken
1. **Consolidated**: All active docs in `implementation-reports/`
2. **Archived**: Old session notes and guides (Nov 13) to `archive/2025-11/`
3. **Removed**: Scattered app-specific claudedocs (superseded)
   - `apps/api/claudedocs/` → Removed (consolidated into main reports)
   - `apps/marketing/claudedocs/` → Removed (outdated)
   - `packages/claudedocs/` → Removed (consolidated)

### 📊 Result
- **Active docs**: 5 implementation reports (all Nov 17, 2025)
- **Archived docs**: 4 historical documents (Nov 13, 2025)
- **Structure**: Clean, focused, current

---

## Maintenance Schedule

- **Weekly**: Add new implementation reports as created
- **Monthly**: Archive superseded documents
- **Per Sprint**: Major cleanup and consolidation

**Last Cleanup**: November 17, 2025  
**Next Review**: December 17, 2025

---

## Quick Reference

**Most Important Document**: [Codebase Status Report](implementation-reports/codebase-status-nov17-2025.md)

**For TODO Tracking**: [Cleanup Analysis](implementation-reports/cleanup-analysis-nov17-2025.md)

**For Historical Context**: Check `archive/2025-11/` for pre-audit session notes

---

**Maintained by**: Claude Code sessions  
**Repository**: github.com/madfam-io/plinto
