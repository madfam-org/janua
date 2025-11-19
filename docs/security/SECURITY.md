# Security Policy

## Supported Versions

We provide security updates for the following versions of Plinto:

| Version | Supported          |
| ------- | ------------------ |
| 1.0.x   | ✅ Active support  |
| < 1.0   | ❌ Pre-release     |

## Vulnerability Disclosure

### Reporting a Vulnerability

The Plinto team takes security vulnerabilities seriously. We appreciate your efforts to responsibly disclose your findings and will make every effort to acknowledge your contributions.

### How to Report

**DO NOT** report security vulnerabilities through public GitHub issues, discussions, or pull requests.

Instead, please report them using one of the following methods:

#### 1. GitHub Security Advisory (Preferred)
Report directly through GitHub's Security Advisory feature:
- Go to https://github.com/madfam-io/plinto/security/advisories
- Click "Report a vulnerability"
- Provide detailed information about the vulnerability

#### 2. Email Disclosure
Send an email to **security@plinto.dev** with:
- Type of vulnerability
- Full paths of source files related to the vulnerability
- Location of affected source code (tag/branch/commit or direct URL)
- Step-by-step reproduction instructions
- Proof-of-concept or exploit code (if possible)
- Impact assessment and potential attack scenarios

#### 3. Encrypted Communication
For sensitive vulnerabilities, use our PGP key:
```
-----BEGIN PGP PUBLIC KEY BLOCK-----
[PGP key would be inserted here in production]
-----END PGP PUBLIC KEY BLOCK-----
```

### What to Expect

- **Acknowledgment**: Within 48 hours of your report
- **Initial Assessment**: Within 5 business days
- **Status Updates**: Every 5-7 days during investigation
- **Resolution Timeline**: 
  - Critical: 7-14 days
  - High: 14-30 days
  - Medium: 30-60 days
  - Low: 60-90 days

### Security Vulnerability Criteria

We consider the following types of issues as security vulnerabilities:

- **Authentication Bypass**: Circumventing authentication mechanisms
- **Authorization Flaws**: Accessing resources without proper permissions
- **Data Exposure**: Unintended disclosure of sensitive information
- **Injection Attacks**: SQL, NoSQL, command injection vulnerabilities
- **Cross-Site Scripting (XSS)**: Stored, reflected, or DOM-based XSS
- **Cross-Site Request Forgery (CSRF)**: State-changing operations without proper validation
- **Cryptographic Issues**: Weak encryption, improper key management
- **Session Management**: Session hijacking, fixation, or improper invalidation
- **Rate Limiting Bypass**: Circumventing rate limits or throttling
- **Denial of Service**: Application-level DoS vulnerabilities

### Out of Scope

The following are **not** considered vulnerabilities:

- Vulnerabilities in dependencies without a proof of exploitability
- Missing security headers that don't directly lead to a vulnerability
- Information disclosure of non-sensitive data
- Issues requiring unlikely user interaction or social engineering
- Vulnerabilities requiring physical access to user's device
- Issues in pre-release or beta versions
- Recently disclosed 0-day vulnerabilities (give us 30 days)
- SSL/TLS best practices (unless demonstrating specific attack)

## Security Best Practices

### For SDK Users

1. **Keep SDKs Updated**: Always use the latest version of Plinto SDKs
2. **Secure Token Storage**: Never store tokens in localStorage for production
3. **Use HTTPS**: Always use HTTPS in production environments
4. **Environment Variables**: Store API keys in environment variables, never in code
5. **Rate Limiting**: Implement rate limiting on your authentication endpoints
6. **Input Validation**: Always validate and sanitize user inputs
7. **Error Handling**: Don't expose sensitive information in error messages

### For API Integration

```typescript
// ✅ Good: Secure token storage
import { PlintoClient } from '@plinto/typescript-sdk';

const client = new PlintoClient({
  baseURL: process.env.PLINTO_API_URL,
  apiKey: process.env.PLINTO_API_KEY,
  // Use secure storage for tokens
  tokenStorage: 'secure', // Uses httpOnly cookies or secure mobile storage
});

// ❌ Bad: Insecure token storage
const client = new PlintoClient({
  baseURL: 'https://api.plinto.dev',
  apiKey: 'pk_live_abc123', // Never hardcode keys
  tokenStorage: 'localStorage', // Vulnerable to XSS
});
```

### Security Headers

Ensure your application implements these security headers:

```javascript
// Next.js example
module.exports = {
  headers: async () => [
    {
      source: '/:path*',
      headers: [
        { key: 'X-Frame-Options', value: 'DENY' },
        { key: 'X-Content-Type-Options', value: 'nosniff' },
        { key: 'X-XSS-Protection', value: '1; mode=block' },
        { key: 'Referrer-Policy', value: 'strict-origin-when-cross-origin' },
        { 
          key: 'Content-Security-Policy',
          value: "default-src 'self'; script-src 'self' 'unsafe-inline' 'unsafe-eval'; style-src 'self' 'unsafe-inline';"
        },
        { 
          key: 'Strict-Transport-Security',
          value: 'max-age=31536000; includeSubDomains'
        },
      ],
    },
  ],
};
```

## Recognition

We maintain a Hall of Fame for security researchers who have responsibly disclosed vulnerabilities:

### 2025
- *Your name could be here*

## Security Audits

Plinto undergoes regular security audits:

- **Latest Audit**: Pending Q1 2025
- **Audit Firm**: TBD
- **Compliance**: Working towards SOC2 Type II

## Contact

- **Security Team**: security@plinto.dev
- **Bug Bounty Program**: Coming Q2 2025
- **Status Page**: https://status.plinto.dev

## Resources

- [OWASP Top 10](https://owasp.org/www-project-top-ten/)
- [Security Best Practices](https://docs.plinto.dev/security/best-practices)
- [Secure Development Guide](https://docs.plinto.dev/security/development)
- [Penetration Testing Reports](https://security.plinto.dev/reports) (authenticated)

---

Last updated: January 18, 2025
Next review: April 18, 2025