# Documentation Content Guidelines

## Purpose & Separation of Concerns

This document establishes clear guidelines for maintaining Janua's dual documentation structure to prevent redundancy and confusion.

## 📁 Documentation Structure

### `/docs` - Internal Development Documentation
**Purpose**: Internal team documentation for developers working ON Janua
**Audience**: Janua development team, contributors
**Access**: Private repository access only

**Content Types**:
- Architecture decisions and design documents
- Implementation reports and analysis
- Internal development guides
- Testing strategies and coverage reports
- Production readiness assessments
- Enterprise feature roadmaps
- Security assessments
- Incident response playbooks

**DO NOT INCLUDE**:
- User-facing SDK documentation
- Public API references
- External developer tutorials
- Marketing content

### `/apps/docs` - Public Documentation Portal
**Purpose**: User-facing documentation website at docs.janua.dev
**Audience**: External developers using Janua
**Access**: Public website

**Content Types**:
- API references
- SDK documentation
- Integration guides
- Authentication tutorials
- Code examples
- Quick start guides
- Troubleshooting guides for users

**DO NOT INCLUDE**:
- Internal implementation details
- Security-sensitive information
- Production infrastructure details
- Internal reports or analysis

## ✅ Content Rules

### Rule 1: No Duplication
- **Never** maintain the same content in both locations
- If content is needed in both places, choose ONE authoritative location
- Use references/links rather than copying content

### Rule 2: Clear Ownership
- Each piece of documentation has ONE owner location
- SDK docs → `/apps/docs/content/sdks/`
- API docs → `/apps/docs/content/api/`
- Architecture → `/docs/architecture/`
- Reports → `/docs/reports/` or `/docs/internal/`

### Rule 3: Content Pipeline
```
/docs/drafts/ → Review → /apps/docs/content/
```
- Use `/docs/drafts/` for content being prepared for public docs
- Once approved, move to `/apps/docs/` and delete from drafts
- Never leave content in both locations

### Rule 4: File Organization

#### Internal Docs Structure (`/docs`)
```
/docs/
├── internal/              # Team-only documentation
│   ├── architecture/      # System design docs
│   ├── reports/          # Analysis and assessments
│   └── operations/       # Deployment and ops guides
└── drafts/               # Content being prepared for public
    └── [temporary files that will move to /apps/docs]
    └── [old content for reference only]
```

#### Public Docs Structure (`/apps/docs`)
```
/apps/docs/
├── app/                  # Next.js app directory (pages)
├── content/              # Markdown content
│   ├── api/             # API documentation
│   ├── sdks/            # SDK guides
│   ├── guides/          # How-to guides
│   └── reference/       # Reference documentation
└── src/                 # React components and utilities
```

## 🔄 Content Workflows

### Creating New Documentation

1. **Determine Audience**
   - Internal team? → `/docs/internal/`
   - External developers? → `/apps/docs/content/`

2. **Check for Existing Content**
   - Search both locations before creating new files
   - Update existing content rather than creating duplicates

3. **Follow Naming Conventions**
   - Internal: `UPPERCASE_WITH_UNDERSCORES.md` for reports
   - Public: `lowercase-with-dashes.md` for web-friendly URLs

### Moving Content from Internal to Public

1. Create draft in `/docs/drafts/`
2. Review for security-sensitive information
3. Adapt tone and detail level for external audience
4. Move to appropriate location in `/apps/docs/content/`
5. Delete from `/docs/drafts/`
6. Update any internal references

## 🚫 Common Mistakes to Avoid

1. **Creating "quickstart" guides in `/docs`**
   - These belong in `/apps/docs/content/guides/`

2. **Copying API specs to both locations**
   - Maintain ONE source of truth in `/apps/docs/content/api/`

3. **Including internal URLs or credentials in public docs**
   - Always sanitize before moving to public

4. **Leaving draft content in multiple places**
   - Clean up after moving content

## 📝 Checklist for New Documentation

- [ ] Is the audience clearly identified?
- [ ] Have I checked for existing similar content?
- [ ] Is the content in the correct directory?
- [ ] Are all links and references correct?
- [ ] Has security-sensitive information been removed (if public)?
- [ ] Is there any duplication with existing docs?
- [ ] Have I removed any draft/temporary versions?

## 🔍 Regular Maintenance

### Monthly Review
- Check for orphaned content in `/docs/quickstart/` (should not exist)
- Verify no duplication between `/docs` and `/apps/docs`
- Clean up `/docs/drafts/` directory
- Archive outdated internal documentation

### Automated Checks
```bash
# Find potential duplicates (run from project root)
find docs apps/docs -name "*.md" -o -name "*.mdx" | xargs basename | sort | uniq -d

# Check for orphaned quickstart content
ls -la docs/quickstart/ 2>/dev/null && echo "WARNING: Orphaned quickstart directory exists"

# Find broken internal references
grep -r "quickstart/" docs/ --include="*.md"
```

## 📞 Questions?

If unclear about where documentation belongs:
1. Check this guide
2. Look for similar existing content
3. Default to `/apps/docs` for anything user-facing
4. Default to `/docs/internal/` for team documentation

---

*Last Updated: January 2025*
*Maintained by: Development Team*