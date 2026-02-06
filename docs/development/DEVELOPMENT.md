# Janua Development Guide

> **Complete guide for contributing to and developing the Janua platform**

## Table of Contents

- [Prerequisites](#prerequisites)
- [Getting Started](#getting-started)
- [Project Structure](#project-structure)
- [Development Workflow](#development-workflow)
- [Testing](#testing)
- [Code Style](#code-style)
- [Common Tasks](#common-tasks)
- [Troubleshooting](#troubleshooting)
- [Architecture Decisions](#architecture-decisions)

## Prerequisites

### Required Software

- **Node.js** 18.x or higher (use `nvm` for version management)
- **Yarn** 1.22.x (for workspace management)
- **Docker** (for local database and services)
- **Git** 2.x or higher

### Recommended Tools

- **VS Code** with recommended extensions (see `.vscode/extensions.json`)
- **Postman** or similar for API testing
- **TablePlus** or similar for database inspection

## Getting Started

### 1. Clone the Repository

```bash
git clone https://github.com/madfam-org/janua.git
cd janua
```

### 2. Install Dependencies

```bash
# Install all workspace dependencies
yarn install

# Install git hooks
yarn husky install
```

### 3. Environment Setup

Create `.env.local` files in each app directory:

#### Core API (`apps/api/.env.local`)

```env
DATABASE_URL=postgresql://user:password@localhost:5432/janua
REDIS_URL=redis://localhost:6379
JWT_SECRET=development-secret-change-in-production
JWKS_PATH=.well-known/jwks.json
TURNSTILE_SECRET_KEY=your-turnstile-secret
```

#### Admin Panel (`apps/admin/.env.local`)

```env
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_ADMIN_API_URL=http://localhost:8000/admin
NEXT_PUBLIC_APP_URL=http://localhost:3004
NEXT_PUBLIC_REQUIRE_MFA=true
ADMIN_SECRET_KEY=admin-secret-key
```

#### Dashboard (`apps/dashboard/.env.local`)

```env
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_APP_URL=http://localhost:3000
JANUA_ISSUER=http://localhost:8000
JANUA_AUDIENCE=janua.dev
```

### 4. Start Development Services

```bash
# Start all services (using Turborepo)
yarn dev

# Or start specific apps
yarn workspace @janua/api dev        # API on :8000
yarn workspace @janua/admin dev      # Admin on :3004
yarn workspace @janua/dashboard dev  # Dashboard on :3000
```

### 5. Database Setup

```bash
# Run migrations
yarn workspace @janua/database migrate

# Seed development data
yarn workspace @janua/database seed
```

## Project Structure

```
janua/
├── apps/                    # Application packages
│   ├── api/                # Core API (NestJS)
│   ├── admin/              # Admin panel (Next.js)
│   ├── dashboard/          # User dashboard (Next.js)
│   ├── docs/               # Documentation site (Docusaurus)
│   ├── marketing/          # Marketing website (Next.js)
│   └── edge-verify/        # Edge verification service
│
├── packages/               # Shared packages
│   ├── core/              # Core business logic
│   ├── database/          # Database schemas and migrations
│   ├── ui/                # Shared UI components
│   ├── config/            # Shared configuration
│   ├── typescript-sdk/    # TypeScript SDK
│   ├── react/             # React components
│   ├── jwt-utils/         # JWT utilities
│   └── monitoring/        # Monitoring utilities
│
├── docs/                   # Documentation
│   ├── architecture/      # Architecture decisions
│   ├── deployment/        # Deployment guides
│   └── development/       # Development guides
│
└── infra/                  # Infrastructure
    ├── monitoring/        # Alerts and dashboards
    ├── secrets/           # Secrets registry
    └── postgres/          # Database init scripts
```

## Development Workflow

### Branch Strategy

```
main                    # Production-ready code
├── develop            # Integration branch
│   ├── feature/*     # New features
│   ├── fix/*        # Bug fixes
│   └── chore/*      # Maintenance tasks
└── release/*         # Release preparation
```

### Commit Convention

We follow [Conventional Commits](https://www.conventionalcommits.org/):

```bash
feat: add user impersonation feature
fix: resolve session timeout issue
docs: update API documentation
chore: upgrade dependencies
test: add integration tests for auth
refactor: simplify token validation logic
perf: optimize database queries
```

### Pull Request Process

1. Create feature branch from `develop`
2. Make changes following code style guidelines
3. Write/update tests
4. Update documentation if needed
5. Run `yarn test` and `yarn lint`
6. Create PR with description template
7. Request review from team members
8. Address feedback
9. Merge after approval

## Testing

### Running Tests

```bash
# Run all tests
yarn test

# Run tests in watch mode
yarn test:watch

# Run tests with coverage
yarn test:coverage

# Run specific workspace tests
yarn workspace @janua/api test
yarn workspace @janua/admin test

# Run E2E tests
yarn test:e2e
```

### Test Structure

```typescript
// Example test structure
describe('AuthService', () => {
  describe('signIn', () => {
    it('should authenticate valid credentials', async () => {
      // Arrange
      const credentials = { email: 'test@example.com', password: 'password' };
      
      // Act
      const result = await authService.signIn(credentials);
      
      // Assert
      expect(result).toHaveProperty('accessToken');
      expect(result).toHaveProperty('refreshToken');
    });
    
    it('should reject invalid credentials', async () => {
      // Test implementation
    });
  });
});
```

## Code Style

### TypeScript Configuration

We use strict TypeScript configuration:

```json
{
  "compilerOptions": {
    "strict": true,
    "noImplicitAny": true,
    "strictNullChecks": true,
    "noUnusedLocals": true,
    "noUnusedParameters": true
  }
}
```

### Linting and Formatting

```bash
# Run ESLint
yarn lint

# Fix ESLint issues
yarn lint:fix

# Format with Prettier
yarn format

# Check formatting
yarn format:check
```

### Import Organization

```typescript
// 1. External imports
import React from 'react';
import { useRouter } from 'next/router';

// 2. Internal imports
import { Button } from '@janua/ui';
import { useAuth } from '@janua/react-sdk';

// 3. Relative imports
import { UserProfile } from './components/UserProfile';
import { formatDate } from './utils';
```

## Common Tasks

### Adding a New Package

```bash
# Create new package
mkdir packages/new-package
cd packages/new-package
yarn init -y

# Update package.json
{
  "name": "@janua/new-package",
  "version": "0.0.1",
  "main": "dist/index.js",
  "types": "dist/index.d.ts"
}

# Add to workspace
yarn install
```

### Database Migrations

```bash
# Create new migration
yarn workspace @janua/database migrate:create add_user_preferences

# Run migrations
yarn workspace @janua/database migrate:up

# Rollback migration
yarn workspace @janua/database migrate:down
```

### Updating Dependencies

```bash
# Update all dependencies
yarn upgrade-interactive --latest

# Update specific workspace
yarn workspace @janua/api upgrade-interactive --latest

# Security audit
yarn audit
yarn audit fix
```

### Building for Production

```bash
# Build all packages
yarn build

# Build specific app
yarn workspace @janua/admin build

# Type check
yarn typecheck

# Run all checks
yarn precommit
```

## Troubleshooting

### Common Issues

#### 1. Build Failures

**Issue**: `Cannot find module '@/components/ui/...'

**Solution**: Ensure all UI components are properly installed:
```bash
cd apps/admin
yarn add @radix-ui/react-* # Add missing Radix UI components
```

#### 2. Database Connection Issues

**Issue**: `ECONNREFUSED 127.0.0.1:5432`

**Solution**: Ensure PostgreSQL is running:
```bash
docker-compose up -d postgres
```

#### 3. Type Errors

**Issue**: Type mismatches in SDK packages

**Solution**: Rebuild TypeScript declarations:
```bash
yarn workspace @janua/typescript-sdk build
yarn typecheck
```

#### 4. Environment Variable Issues

**Issue**: `Missing required environment variable`

**Solution**: Check `.env.local` files exist and contain all required variables. See environment setup section above.

### Debug Mode

Enable debug logging:

```bash
# API debug mode
DEBUG=janua:* yarn workspace @janua/api dev

# Next.js verbose logging
NEXT_PUBLIC_DEBUG=true yarn workspace @janua/admin dev
```

## Architecture Decisions

### Technology Choices

| Component | Technology | Rationale |
|-----------|------------|-----------|
| API | NestJS | Enterprise-grade, TypeScript-first, modular architecture |
| Frontend | Next.js 14 | App Router, RSC, edge runtime support |
| Database | PostgreSQL | ACID compliance, JSON support, proven scale |
| Cache | Redis | Session storage, rate limiting, job queues |
| Auth | Custom + Passkeys | Full control, WebAuthn support, edge-compatible |
| UI | Radix UI + Tailwind | Accessible, customizable, consistent design |
| Testing | Jest + Playwright | Unit/integration + E2E coverage |
| Monorepo | Turborepo + Yarn | Fast builds, workspace management |

### Design Patterns

1. **Repository Pattern**: Data access abstraction
2. **Service Layer**: Business logic encapsulation
3. **DTO Validation**: Input/output validation with class-validator
4. **Dependency Injection**: NestJS DI container
5. **Event-Driven**: Webhooks and audit events
6. **Edge-First**: CDN-cached JWKS, edge verification

### Security Practices

- All sessions are JWT-based with refresh rotation
- Passwords hashed with bcrypt (12 rounds)
- Rate limiting per IP and tenant
- CORS configured per environment
- CSP headers on all responses
- Input validation at all boundaries
- SQL injection prevention via parameterized queries
- XSS protection via React and sanitization

## Contributing

### Before Contributing

1. Read this development guide completely
2. Check existing issues and PRs
3. Discuss major changes in an issue first
4. Follow the code of conduct

### Contribution Process

1. Fork the repository
2. Create your feature branch
3. Make your changes
4. Add tests for new functionality
5. Update documentation
6. Submit a pull request

### Review Checklist

- [ ] Tests pass (`yarn test`)
- [ ] No linting errors (`yarn lint`)
- [ ] Types check (`yarn typecheck`)
- [ ] Documentation updated
- [ ] Commit messages follow convention
- [ ] PR description complete
- [ ] No console.logs or debug code

## Resources

### Internal Documentation

- [API Specification](./docs/reference/API_SPECIFICATION.md)
- [Database Design](./docs/technical/DATABASE_DESIGN.md)
- [Architecture Overview](./docs/architecture/ARCHITECTURE.md)
- [Deployment Guide](./docs/deployment/DEPLOYMENT.md)
- [Security Assessment](./docs/SECURITY_ASSESSMENT_REPORT.md)

### External Resources

- [Next.js Documentation](https://nextjs.org/docs)
- [NestJS Documentation](https://docs.nestjs.com)
- [Turborepo Documentation](https://turbo.build/repo/docs)
- [Radix UI Documentation](https://www.radix-ui.com/docs)
- [WebAuthn Guide](https://webauthn.guide)

### Getting Help

- **Discord**: Join our developer Discord (invite link in admin panel)
- **Issues**: Open an issue with the `question` label
- **Email**: dev-support@janua.dev

## License

Copyright © Aureo Labs (MADFAM). See [LICENSE](./LICENSE) for details.