# Root Directory Structure

This document describes the proper organization of files in the Janua project root directory.

## ✅ Files That Belong in Root

### Configuration Files
- **README.md** - Main project documentation
- **package.json** - Node.js dependencies and scripts
- **package-lock.json** / **yarn.lock** - Dependency lock files
- **tsconfig.json** - TypeScript configuration
- **.gitignore** - Git ignore patterns
- **turbo.json** - Turborepo configuration
- **Makefile** - Build and development commands

### Environment Files
- **.env.example** - Example environment variables
- **.env.production.example** - Production environment example

### Build Configuration
- **jest.config.js** - Jest testing configuration
- **playwright.config.ts** - Playwright E2E testing configuration
- **.babelrc** - Babel transpiler configuration

## 📁 Directory Structure

```
janua/
├── apps/                 # Application packages (monorepo)
│   ├── api/             # Python FastAPI backend
│   ├── marketing/       # Marketing website
│   ├── dashboard/       # User dashboard
│   ├── admin/          # Admin interface
│   └── ...
├── packages/            # Shared packages and SDKs
│   ├── nextjs-sdk/     # Next.js SDK
│   ├── react-sdk/      # React SDK
│   ├── ui/             # Shared UI components
│   └── ...
├── docs/                # All documentation
│   ├── production/     # Production readiness reports
│   ├── technical/      # Technical documentation
│   ├── deployment/     # Deployment guides
│   ├── architecture/   # Architecture documents
│   └── ...
├── tests/               # Test files and configurations
│   └── e2e/             # End-to-end tests (Playwright)
├── scripts/             # Utility scripts
├── infra/               # Infrastructure (monitoring, secrets, postgres)
├── config/              # Configuration files (docker-compose, agent manifest)
├── assets/              # Static assets
├── .github/             # GitHub configurations
├── .claude/             # Claude configuration
└── .serena/            # Serena project configuration
```

## 🚫 Files That Should NOT Be in Root

### Documentation Files
These have been moved to `docs/`:
- ~~CHANGELOG.md~~ → `docs/CHANGELOG.md`
- ~~QUICK_START.md~~ → `docs/guides/QUICK_START.md`
- ~~DEMO_WALKTHROUGH.md~~ → `docs/guides/DEMO_WALKTHROUGH.md`
- ~~LOCAL_DEMO_GUIDE.md~~ → `docs/guides/LOCAL_DEMO_GUIDE.md`
- ~~VERSION_GUIDE.md~~ → `docs/guides/VERSION_GUIDE.md`
- ~~SECURITY.md~~ → `docs/security/SECURITY.md`
- ~~TEST_FIXES_PROGRESS.md~~ → `docs/testing/TEST_FIXES_PROGRESS.md`
- ~~TEST_STABILIZATION_PLAN.md~~ → `docs/testing/TEST_STABILIZATION_PLAN.md`

### Configuration Files
These have been moved to `config/`:
- ~~vercel.json~~ → `config/vercel.json`
- ~~railway.json~~ → `config/railway.json`
- ~~docker-compose.test.yml~~ → `config/docker-compose.test.yml`

### Temporary Files
Should be automatically cleaned:
- *.tmp
- *.log (except intentional log files)
- .DS_Store (macOS)
- Thumbs.db (Windows)
- *.swp (Vim swap files)

### Build Artifacts
Should be in .gitignore:
- node_modules/
- dist/
- build/
- .next/
- *.pyc
- __pycache__/

## Recent Cleanup (November 2025)

The root directory has been comprehensively organized:

### Documentation Reorganization
- All documentation files moved to appropriate `docs/` subdirectories
- Guides (QUICK_START, DEMO_WALKTHROUGH, etc.) moved to `docs/guides/`
- Security documentation moved to `docs/security/`
- Testing documentation moved to `docs/testing/`
- Project status files moved to `docs/project/`

### Configuration Consolidation
- Deployment configs moved to `config/` directory
- Test infrastructure (docker-compose.test.yml) moved to `config/`
- Build artifacts properly ignored in .gitignore

### Build Artifacts Removed
- Database files (*.db, *.sqlite)
- Test reports (junit.xml)
- Storybook build output
- Orphaned/empty code directories

The root now contains only essential configuration files and standard project structure directories.