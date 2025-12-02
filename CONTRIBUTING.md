# Contributing to Janua

Thanks for considering contributing to Janua! We need your help to make self-hosted authentication accessible to everyone.

**First time contributing to open source?** No problem. We're here to help.

---

## 🎯 Quick Start for Contributors

**The fastest way to contribute:**

1. **Find an issue** - Check [Issues](https://github.com/madfam-io/janua/issues) for `good-first-issue` label
2. **Comment** - Say "I'd like to work on this"
3. **Fork & Code** - Make your changes
4. **Submit PR** - We'll review within 48 hours

**That's it.** No CLA, no bureaucracy, no BS.

---

## 🤝 Ways to Contribute

You don't need to be a coding expert. Here's how you can help:

### 🐛 Report Bugs
Found something broken?
1. Check if it's [already reported](https://github.com/madfam-io/janua/issues)
2. If not, [create a new issue](https://github.com/madfam-io/janua/issues/new)
3. Include: What happened, what you expected, steps to reproduce

**Good bug report:**
```
Title: Sign-in fails with Google OAuth on Safari

Environment: macOS Ventura, Safari 17
Steps:
1. Click "Sign in with Google"
2. Complete Google auth flow
3. Redirected back to app

Expected: User is signed in
Actual: Error "Invalid state parameter"

Logs: [attach screenshot or logs]
```

### 📚 Improve Documentation
Docs are never perfect. Help us fix them:
- Fix typos or unclear instructions
- Add examples that helped you
- Write guides for common use cases
- Translate docs (future)

**Where to start:**
- [Quick Start Guide](docs/guides/QUICK_START.md) - does it actually work in 5 minutes?
- [Deployment Guide](docs/DEPLOYMENT.md) - missing steps?
- [SDK Guides](docs/developers/) - need more examples?

### 🎨 Improve UI/UX
Make the components better:
- Accessibility improvements (ARIA labels, keyboard nav)
- Better error messages
- Loading states
- Mobile responsiveness

**Check out:**
- [UI Components](packages/ui/src/components/auth/)
- [Existing issues labeled "ui"](https://github.com/madfam-io/janua/labels/ui)

### 🔧 Fix Bugs
Pick an issue, fix it, submit a PR:
1. Look for [`bug` label](https://github.com/madfam-io/janua/labels/bug)
2. Comment that you're working on it
3. Fork, fix, test, PR

### ✨ Add Features
Want to add something new?
1. **First:** Open an issue to discuss it (avoid wasted work)
2. Wait for maintainer approval
3. Then code it up

**We prioritize:**
- Better DX (developer experience)
- Better self-hosting experience
- Better documentation
- NOT: Feature parity with Auth0/Clerk

### 🧪 Write Tests
We need more test coverage:
- Unit tests for services
- Integration tests for API endpoints
- E2E tests for auth flows

**Current coverage:** ~30% (we're honest about it)
**Goal:** 80%

---

## 🚀 Development Setup

### Prerequisites
- **Python 3.11+**
- **Node.js 18+**
- **PostgreSQL 14+**
- **Redis 6+**
- **Docker** (recommended)

### NPM Registry Configuration

Janua SDKs are published to MADFAM's private npm registry. Configure your `.npmrc`:

```bash
# Add to ~/.npmrc
@janua:registry=https://npm.madfam.io
//npm.madfam.io/:_authToken=${NPM_MADFAM_TOKEN}
```

Set the `NPM_MADFAM_TOKEN` environment variable with your registry token.

### Quick Setup

This is a **pnpm monorepo**. You'll need pnpm installed globally.

```bash
# Install pnpm (if not already installed)
npm install -g pnpm

# Clone your fork
git clone https://github.com/YOUR-USERNAME/janua.git
cd janua

# Install all dependencies (monorepo-wide)
pnpm install

# Backend setup
cd apps/api
docker-compose up -d postgres redis
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
pip install -r requirements-test.txt

# Run migrations
alembic upgrade head

# Start backend
uvicorn app.main:app --reload --port 8000

# In another terminal, start frontend
cd apps/website
pnpm dev
```

**Verify it works:**
- Backend API: http://localhost:8000/docs
- Website: http://localhost:3001

### Monorepo Commands

```bash
# From project root:
pnpm install          # Install all dependencies
pnpm build            # Build all packages
pnpm dev              # Run all apps in dev mode
pnpm lint             # Lint all packages
pnpm typecheck        # Type check all packages

# Run specific app:
pnpm --filter @janua/website dev
pnpm --filter @janua/dashboard dev
pnpm --filter @janua/api dev

# Add dependency to specific package:
pnpm --filter @janua/website add react-hook-form
```

### Running Tests

```bash
# Backend tests
cd apps/api
pytest

# With coverage
pytest --cov=app --cov-report=html

# Frontend tests
cd apps/demo
npm test

# E2E tests
npm run e2e
```

---

## 📝 Pull Request Process

### Before You Submit

1. **Test your changes**
   ```bash
   # Run tests
   pytest  # Backend
   npm test  # Frontend

   # Check code quality
   ruff check .  # Python linting
   black .  # Python formatting
   npm run lint  # Frontend linting
   ```

2. **Update documentation** if needed
   - Update README if you changed functionality
   - Update relevant docs/ files
   - Add JSDoc/docstrings for new functions

3. **Write a clear PR description**
   - What does this PR do?
   - Why is this change needed?
   - How did you test it?
   - Any breaking changes?

### PR Template

```markdown
## What
Brief description of changes

## Why
Why is this change needed?

## How
How did you implement it?

## Testing
- [ ] Unit tests added/updated
- [ ] Integration tests pass
- [ ] Tested manually (describe how)

## Screenshots
(if UI changes)

## Breaking Changes
(if any)
```

### Review Process

1. **Automated checks run** (tests, linting)
2. **Maintainer reviews** (usually within 48 hours)
3. **You address feedback** (if any)
4. **We merge** and celebrate! 🎉

**We merge fast.** Small PRs get merged same day. Large PRs within a week.

---

## 💻 Code Style Guidelines

### Python (Backend)

**We use:**
- **Black** for formatting (line length: 100)
- **Ruff** for linting
- **Type hints** everywhere
- **Async/await** for all I/O

**Example:**
```python
from typing import Optional
from app.models import User

async def get_user_by_email(email: str) -> Optional[User]:
    """Get user by email address.

    Args:
        email: User's email address

    Returns:
        User object if found, None otherwise
    """
    async with get_db_session() as session:
        result = await session.execute(
            select(User).where(User.email == email)
        )
        return result.scalar_one_or_none()
```

### TypeScript/React (Frontend)

**We use:**
- **TypeScript** with strict mode
- **ESLint** + **Prettier**
- **Functional components** with hooks
- **Tailwind CSS** for styling

**Example:**
```typescript
interface SignInProps {
  onSuccess?: (user: User) => void;
  redirectUrl?: string;
}

export function SignIn({ onSuccess, redirectUrl }: SignInProps) {
  const [email, setEmail] = useState('');
  const { signIn, isLoading } = useAuth();

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    const user = await signIn(email, password);
    onSuccess?.(user);
  };

  return (
    <form onSubmit={handleSubmit}>
      {/* ... */}
    </form>
  );
}
```

### General Principles

1. **Keep it simple** - Clever code is hard to maintain
2. **Write tests** - Future you will thank you
3. **Comment why, not what** - Code shows what, comments explain why
4. **No console.logs** - Use proper logging
5. **Handle errors** - Don't swallow exceptions

---

## 🏷️ Commit Messages

**Format:** `type: description`

**Types:**
- `feat:` New feature
- `fix:` Bug fix
- `docs:` Documentation changes
- `test:` Adding/updating tests
- `refactor:` Code refactoring
- `chore:` Maintenance tasks

**Examples:**
```bash
feat: add WebAuthn support for Safari
fix: OAuth redirect fails on mobile Safari
docs: improve Quick Start instructions
test: add integration tests for SSO flow
refactor: extract email service to separate module
chore: update dependencies
```

**Good commits:**
- Clear and descriptive
- Explain WHY, not just WHAT
- Reference issues: `fix: resolve SAML redirect loop (#123)`

**Bad commits:**
- "fix bug"
- "update code"
- "changes"

---

## 🤔 Questions?

**Before asking:**
1. Check the [documentation](docs/)
2. Search [existing issues](https://github.com/madfam-io/janua/issues)
3. Read this guide again

**Still stuck?**
- Open a [GitHub Discussion](https://github.com/madfam-io/janua/discussions)
- Tag your question with `question` label
- We'll respond within 24-48 hours

**For security issues:**
- **DO NOT** open a public issue
- Email: security@janua.dev
- We'll respond within 24 hours

---

## 🎖️ Recognition

All contributors get:
- ✅ Listed in our [Contributors](https://github.com/madfam-io/janua/graphs/contributors) page
- ✅ Mentioned in release notes (for significant contributions)
- ✅ Our eternal gratitude

**Top contributors** (when we have them):
- Shout-outs in README
- Special role in community (future Discord)
- Input on roadmap decisions

---

## 📜 License

By contributing, you agree that your contributions will be licensed under the AGPL-3.0 License.

**What this means:**
- Your code can be used by anyone, anywhere, for any purpose
- You retain copyright to your contributions
- No warranty is provided

---

## 🚫 Code of Conduct

**Be nice. Be respectful. Be professional.**

We don't tolerate:
- Harassment or discrimination
- Trolling or insulting comments
- Personal attacks
- Sharing private information

**Violations:** First warning, then ban. We keep this space welcoming.

---

## 💡 Good First Issues

New to the project? Start here:

**Documentation:**
- [ ] Fix typos in Quick Start guide
- [ ] Add examples to SDK documentation
- [ ] Improve error messages in UI components

**Code:**
- [ ] Add loading states to buttons
- [ ] Improve accessibility (ARIA labels)
- [ ] Add unit tests to untested services

**Testing:**
- [ ] Write E2E test for OAuth flow
- [ ] Add integration tests for SAML
- [ ] Test mobile responsiveness

[**See all good first issues →**](https://github.com/madfam-io/janua/labels/good-first-issue)

---

## 🎯 What We're Looking For

**High priority:**
1. **Better documentation** - Help others get started
2. **More tests** - Increase coverage to 80%
3. **Bug fixes** - Make it more stable
4. **Accessibility** - Make it usable for everyone
5. **Better error messages** - Help users debug issues

**Not a priority:**
- New auth methods (we have enough)
- Admin dashboards (use existing tools)
- Analytics features (not core value)
- AI/ML features (please no)

**When in doubt, ask first.** Open an issue to discuss before building.

---

**Ready to contribute?**

🎉 [**Pick a good first issue →**](https://github.com/madfam-io/janua/labels/good-first-issue)

Thank you for making Janua better! 🙏
