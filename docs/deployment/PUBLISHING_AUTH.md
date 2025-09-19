# Registry Authentication Setup

## npm (for TypeScript, React, Vue SDKs)

### 1. Create npm account
Go to https://www.npmjs.com/signup

### 2. Login to npm
```bash
npm login
# Enter username, password, email, and 2FA code if enabled
```

### 3. Verify authentication
```bash
npm whoami
# Should show your npm username
```

### 4. Set up automation token (for CI/CD)
1. Go to https://www.npmjs.com/settings/YOUR_USERNAME/tokens
2. Click "Generate New Token"
3. Select "Automation" type
4. Copy the token
5. Set as environment variable:
```bash
export NPM_TOKEN=your_token_here
```

### 5. Configure .npmrc for automation
```bash
echo "//registry.npmjs.org/:_authToken=\${NPM_TOKEN}" > ~/.npmrc
```

## PyPI (for Python SDK)

### 1. Create PyPI account
Go to https://pypi.org/account/register/

### 2. Create API token
1. Go to https://pypi.org/manage/account/token/
2. Create a token with scope "Entire account" (or specific to plinto package after first publish)
3. Copy the token

### 3. Configure .pypirc
Create `~/.pypirc`:
```ini
[distutils]
index-servers =
    pypi
    testpypi

[pypi]
username = __token__
password = pypi-YOUR_TOKEN_HERE

[testpypi]
username = __token__
password = pypi-YOUR_TEST_TOKEN_HERE
```

### 4. Secure the file
```bash
chmod 600 ~/.pypirc
```

## pub.dev (for Flutter SDK)

### 1. Create pub.dev account
Go to https://pub.dev/ and sign in with Google

### 2. Authenticate locally
```bash
dart pub login
# This will open a browser for authentication
```

### 3. Verify authentication
```bash
dart pub whoami
```

## Go Modules (for Go SDK)

### 1. No authentication needed for public modules
Go modules are published by pushing to GitHub

### 2. Create and push a git tag
```bash
git tag v1.0.0
git push origin v1.0.0
```

### 3. The module will be automatically available
Users can get it with:
```bash
go get github.com/madfam-io/plinto/go-sdk@v1.0.0
```

## Current Authentication Status

Run these commands to check your current auth status:

```bash
# npm
npm whoami

# PyPI (check if .pypirc exists)
ls -la ~/.pypirc

# pub.dev
dart pub whoami

# GitHub (for Go modules)
git remote -v
```

## Environment Variables for CI/CD

Set these in your CI/CD environment (GitHub Actions, etc.):

```yaml
NPM_TOKEN: ${{ secrets.NPM_TOKEN }}
PYPI_TOKEN: ${{ secrets.PYPI_TOKEN }}
PUB_TOKEN: ${{ secrets.PUB_TOKEN }}
```

## Security Best Practices

1. **Never commit tokens** to version control
2. **Use environment variables** for CI/CD
3. **Rotate tokens regularly**
4. **Use scoped tokens** when possible
5. **Enable 2FA** on all registry accounts
6. **Use test registries first** before production

## Test Publishing Commands

Before publishing to production, test with:

### npm (dry run)
```bash
npm publish --dry-run
```

### PyPI (test registry)
```bash
python -m twine upload --repository testpypi dist/*
```

### pub.dev (dry run)
```bash
dart pub publish --dry-run
```