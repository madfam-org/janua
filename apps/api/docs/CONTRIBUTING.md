# Contributing to Janua API

> **Thank you for your interest in contributing to the Janua authentication platform!**

This guide will help you understand our contribution process, development standards, and how to get your contributions merged successfully.

## 🎯 How to Contribute

### Types of Contributions

We welcome various types of contributions:

- **🐛 Bug Reports**: Help us identify and fix issues
- **✨ Feature Requests**: Suggest new functionality
- **📝 Documentation**: Improve docs, guides, and examples
- **🔧 Code Contributions**: Bug fixes, features, optimizations
- **🧪 Testing**: Add tests, improve test coverage
- **🔒 Security**: Report security issues responsibly

### Before You Start

1. **Check Existing Issues**: Search for existing issues/PRs related to your contribution
2. **Discuss First**: For large features, create an issue to discuss the approach
3. **Read Documentation**: Familiarize yourself with the architecture and patterns
4. **Setup Development Environment**: Follow our [development setup guide](development/getting-started.md)

## 🚀 Quick Start for Contributors

### 1. Fork and Clone

```bash
# Fork the repository on GitHub
# Then clone your fork
git clone https://github.com/yourusername/janua.git
cd janua/apps/api

# Add upstream remote
git remote add upstream https://github.com/original-org/janua.git
```

### 2. Development Setup

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
pip install -r requirements-test.txt

# Install pre-commit hooks
pre-commit install

# Setup environment
cp .env.example .env
# Edit .env with your development settings
```

### 3. Start Development

```bash
# Create feature branch
git checkout -b feature/your-feature-name

# Start development server
uvicorn app.main:app --reload --port 8000

# Run tests to ensure everything works
pytest
```

## 📋 Development Standards

### Code Quality Requirements

All contributions must meet these standards:

#### Code Style
- **Formatting**: Black with 88-character line length
- **Import Sorting**: isort with Black profile
- **Linting**: Ruff for code quality
- **Type Hints**: Full type annotations required
- **Documentation**: Docstrings for all public functions

```bash
# Run before committing
make check  # Runs all quality checks

# Or individually:
black app/ tests/
isort app/ tests/
ruff check app/ tests/
mypy app/
```

#### Testing Requirements
- **Coverage**: Minimum 80% test coverage for new code
- **Test Types**: Unit tests required, integration tests for complex features
- **Test Organization**: Follow existing test structure
- **Async Testing**: Use pytest-asyncio for async code

```bash
# Run tests with coverage
pytest --cov=app --cov-report=term-missing

# Run specific test categories
pytest tests/unit/      # Unit tests
pytest tests/integration/  # Integration tests
```

#### Security Standards
- **Security Scan**: All code must pass Bandit security scan
- **Dependencies**: No known vulnerabilities in dependencies
- **Secrets**: No hardcoded secrets or credentials
- **Input Validation**: Proper validation for all inputs

```bash
# Security checks
bandit -r app/
safety check
```

### Git Workflow

#### Branch Naming
- `feature/feature-name` - New features
- `fix/issue-description` - Bug fixes
- `docs/documentation-update` - Documentation changes
- `test/test-improvements` - Testing improvements
- `refactor/code-improvements` - Code refactoring

#### Commit Messages
Follow [Conventional Commits](https://www.conventionalcommits.org/):

```
type(scope): description

- Detailed explanation of changes
- Why the change was made
- Any breaking changes

Closes #123
```

Examples:
```
feat(auth): add WebAuthn passkey support

- Implement WebAuthn registration and authentication
- Add passkey management endpoints
- Include comprehensive tests and documentation
- Support multiple passkeys per user

Closes #456

fix(security): resolve JWT token validation issue

- Fix token expiration validation logic
- Add additional security checks
- Update tests to cover edge cases

Closes #789

docs(api): update authentication flow documentation

- Add WebAuthn examples
- Clarify token refresh process
- Include troubleshooting section
```

#### Pull Request Process

1. **Create PR**: Against `develop` branch
2. **Title**: Clear, descriptive title
3. **Description**: Comprehensive PR description
4. **Checklist**: Complete our PR checklist
5. **Review**: Address all review feedback
6. **Merge**: Squash and merge after approval

### PR Template

```markdown
## Description
Brief description of changes and motivation.

## Type of Change
- [ ] Bug fix (non-breaking change that fixes an issue)
- [ ] New feature (non-breaking change that adds functionality)
- [ ] Breaking change (fix or feature that would cause existing functionality to not work as expected)
- [ ] Documentation update

## Changes Made
- List specific changes
- Include implementation details
- Mention any architectural decisions

## Testing
- [ ] Unit tests added/updated
- [ ] Integration tests added/updated
- [ ] All tests pass locally
- [ ] Coverage meets requirements

## Security
- [ ] Security review completed
- [ ] No hardcoded secrets
- [ ] Input validation implemented
- [ ] Authentication/authorization considered

## Documentation
- [ ] Code comments added
- [ ] API documentation updated
- [ ] User documentation updated
- [ ] README updated if needed

## Checklist
- [ ] Code follows style guidelines
- [ ] Self-review completed
- [ ] Breaking changes documented
- [ ] Related issues linked

## Screenshots (if applicable)
Include screenshots for UI changes.

Closes #issue_number
```

## 🐛 Bug Reports

### Before Reporting
1. **Search Existing Issues**: Check if the bug is already reported
2. **Reproduce**: Ensure you can reproduce the issue consistently
3. **Environment**: Test in a clean development environment
4. **Minimal Example**: Create minimal reproduction case

### Bug Report Template

```markdown
## Bug Description
Clear and concise description of the bug.

## Steps to Reproduce
1. Go to '...'
2. Click on '....'
3. Scroll down to '....'
4. See error

## Expected Behavior
What you expected to happen.

## Actual Behavior
What actually happened.

## Environment
- OS: [e.g., macOS 13.0]
- Python Version: [e.g., 3.11.2]
- API Version: [e.g., 1.0.0]
- Browser: [if applicable]

## Additional Context
- Error logs
- Screenshots
- Related issues
- Possible solutions

## Minimal Reproduction
```python
# Minimal code to reproduce the issue
import requests

response = requests.post("http://localhost:8000/api/v1/auth/signin", json={
    "email": "test@example.com",
    "password": "test123"
})
print(response.status_code)  # Expected: 200, Actual: 500
```

## ✨ Feature Requests

### Before Requesting
1. **Check Roadmap**: Review our [project roadmap](https://github.com/madfam-org/janua/projects)
2. **Search Issues**: Look for similar feature requests
3. **Consider Scope**: Ensure feature aligns with project goals
4. **Gather Feedback**: Discuss with community first

### Feature Request Template

```markdown
## Feature Description
Clear and concise description of the feature.

## Problem Statement
What problem does this feature solve?

## Proposed Solution
Detailed description of your proposed solution.

## Alternatives Considered
Other solutions you've considered.

## Use Cases
- Primary use case
- Secondary use cases
- Edge cases

## Implementation Notes
- Technical considerations
- Potential challenges
- Dependencies

## Additional Context
- Related features
- Industry standards
- User feedback
```

## 🔒 Security Reporting

### Responsible Disclosure

We take security seriously. Please follow responsible disclosure:

1. **Email**: Send security issues to [security@madfam.io](mailto:security@madfam.io)
2. **Encrypt**: Use our [PGP key](https://janua.dev/.well-known/security.txt) for sensitive reports
3. **Details**: Include reproduction steps and impact assessment
4. **Patience**: Allow time for investigation and fix
5. **Credit**: We'll credit you in security advisories (if desired)

### What to Include
- Vulnerability description
- Steps to reproduce
- Impact assessment
- Suggested fix (if any)
- Your contact information

### What NOT to Do
- Don't publicly disclose before we've addressed it
- Don't test on production systems
- Don't access user data beyond proof-of-concept

## 📝 Documentation Contributions

### Documentation Standards
- **Clarity**: Write for your intended audience
- **Examples**: Include working code examples
- **Structure**: Follow existing documentation structure
- **Links**: Use relative links for internal references
- **Updates**: Keep documentation current with code changes

### Documentation Types
- **API Documentation**: Endpoint documentation with examples
- **Guides**: Step-by-step tutorials and how-tos
- **Reference**: Technical reference materials
- **Architecture**: System design and patterns

### Documentation Workflow
1. **Identify Gap**: Find missing or outdated documentation
2. **Create Issue**: Document what needs to be updated
3. **Write Content**: Follow our style guide
4. **Review**: Get feedback from subject matter experts
5. **Update**: Keep content current with code changes

## 🧪 Testing Contributions

### Test Categories
- **Unit Tests**: Test individual functions and classes
- **Integration Tests**: Test component interactions
- **End-to-End Tests**: Test complete user workflows
- **Performance Tests**: Test system performance
- **Security Tests**: Test security measures

### Test Guidelines
- **Coverage**: Aim for >90% coverage on new code
- **Independence**: Tests should not depend on each other
- **Clarity**: Test names should clearly indicate what's tested
- **Data**: Use factories and fixtures for test data
- **Cleanup**: Ensure tests clean up after themselves

### Test Examples

```python
# Good unit test
class TestUserService:
    @pytest.mark.asyncio
    async def test_create_user_success(self, user_service, user_data):
        # Arrange
        user_service.user_repository.get_by_email.return_value = None

        # Act
        result = await user_service.create_user(user_data)

        # Assert
        assert result.email == user_data.email
        user_service.user_repository.create.assert_called_once()

# Good integration test
class TestAuthEndpoints:
    @pytest.mark.asyncio
    async def test_signup_and_signin_flow(self, client):
        # Test complete authentication flow
        signup_data = {
            "email": "test@example.com",
            "password": "SecurePassword123!",
            "name": "Test User"
        }

        # Sign up
        signup_response = await client.post("/api/v1/auth/signup", json=signup_data)
        assert signup_response.status_code == 201

        # Sign in
        signin_response = await client.post("/api/v1/auth/signin", json={
            "email": signup_data["email"],
            "password": signup_data["password"]
        })
        assert signin_response.status_code == 200
        assert "access_token" in signin_response.json()["data"]
```

## 🏷️ Issue Labels

We use labels to categorize and prioritize issues:

### Type Labels
- `bug` - Something isn't working
- `enhancement` - New feature or request
- `documentation` - Improvements or additions to documentation
- `security` - Security-related issues
- `performance` - Performance improvements
- `refactor` - Code improvements without functional changes

### Priority Labels
- `priority/critical` - Critical issues requiring immediate attention
- `priority/high` - High priority issues
- `priority/medium` - Medium priority issues
- `priority/low` - Low priority issues

### Status Labels
- `status/needs-review` - Needs review from maintainers
- `status/in-progress` - Currently being worked on
- `status/blocked` - Blocked by other issues or dependencies
- `status/ready` - Ready for development

### Difficulty Labels
- `good first issue` - Good for newcomers
- `help wanted` - Extra attention needed
- `difficulty/easy` - Easy to implement
- `difficulty/medium` - Moderate implementation complexity
- `difficulty/hard` - Complex implementation required

## 🎉 Recognition

### Contributor Recognition
- **Changelog**: Contributors mentioned in release notes
- **Hall of Fame**: Top contributors featured in documentation
- **Swag**: Contributor merchandise for significant contributions
- **Mentoring**: Opportunities to mentor new contributors

### Types of Recognition
- First-time contributor shoutouts
- Monthly contributor highlights
- Annual contributor awards
- Conference speaking opportunities

## 📚 Resources

### Development Resources
- **[Development Guide](development/README.md)** - Complete development setup
- **[Architecture Documentation](architecture/README.md)** - System architecture
- **[API Documentation](api/README.md)** - API reference
- **[Testing Guide](development/testing.md)** - Testing best practices

### Community Resources
- **[Code of Conduct](CODE_OF_CONDUCT.md)** - Community guidelines
- **[GitHub Discussions](https://github.com/madfam-org/janua/discussions)** - Community Q&A
- **[Discord](https://discord.gg/janua-dev)** - Real-time chat
- **[Stack Overflow](https://stackoverflow.com/questions/tagged/janua-api)** - Q&A platform

### Learning Resources
- **[FastAPI Documentation](https://fastapi.tiangolo.com/)** - Web framework
- **[SQLAlchemy Documentation](https://docs.sqlalchemy.org/)** - Database ORM
- **[Pytest Documentation](https://docs.pytest.org/)** - Testing framework
- **[Python Async/Await Guide](https://docs.python.org/3/library/asyncio.html)** - Async programming

## 🤝 Community

### Code of Conduct
We are committed to providing a welcoming and inclusive environment. Please read our [Code of Conduct](CODE_OF_CONDUCT.md).

### Communication Channels
- **GitHub Issues**: Bug reports and feature requests
- **GitHub Discussions**: Community discussions and Q&A
- **Discord**: Real-time community chat
- **Email**: Direct contact for sensitive issues

### Getting Help
1. **Documentation**: Check our comprehensive docs
2. **Search**: Look through existing issues and discussions
3. **Ask**: Post in GitHub Discussions or Discord
4. **Email**: Contact maintainers for complex issues

## 📞 Contact

### Maintainer Team
- **Lead Maintainer**: [lead@janua.dev](mailto:lead@janua.dev)
- **Security Team**: [security@madfam.io](mailto:security@madfam.io)
- **Documentation Team**: [docs@janua.dev](mailto:docs@janua.dev)

### Response Times
- **Bug Reports**: 2-3 business days
- **Feature Requests**: 1 week
- **Security Issues**: 24 hours
- **Pull Requests**: 3-5 business days

---

## 🙏 Thank You

Thank you for contributing to Janua! Your contributions help make authentication more secure and accessible for everyone.

---

<div align="center">

**[⬅️ Back to Documentation](README.md)** • **[🚀 Development Guide](development/README.md)** • **[🐛 Report Bug](https://github.com/madfam-org/janua/issues/new?template=bug-report.md)**

</div>