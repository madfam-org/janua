# Plinto Pricing & Feature Matrix

## Pricing Tiers

### 🆓 Community Edition (Open Source)
**Price**: Free forever
**Target**: Individuals, startups, open source projects

#### Features Included:
- ✅ **Core Authentication**
  - Email/password authentication
  - User registration and management
  - Password reset and email verification

- ✅ **Multi-Factor Authentication (MFA)**
  - TOTP (Google Authenticator, Authy)
  - SMS (basic)

- ✅ **Basic Organizations**
  - Single organization
  - Up to 100 users

- ✅ **Basic Webhooks**
  - Up to 5 webhooks
  - Standard events

- ✅ **Community Support**
  - GitHub issues
  - Community forum
  - Documentation

#### Limits:
- 100 users per organization
- 1 organization
- 1,000 API requests/hour
- 5 webhooks

---

### 💼 Professional
**Price**: $99/month or $990/year (2 months free)
**Target**: Growing businesses, small teams

#### Everything in Community, plus:
- ✅ **Advanced MFA**
  - Hardware security keys (WebAuthn)
  - Backup codes
  - Device trust

- ✅ **Team Management**
  - Up to 10 organizations
  - Up to 10,000 users
  - Role-based access control (RBAC)

- ✅ **API Keys & Access Control**
  - Multiple API keys
  - Scoped permissions
  - IP allowlisting

- ✅ **Custom Domains**
  - White-label authentication pages
  - Custom email domains

- ✅ **Analytics Dashboard**
  - User analytics
  - Authentication metrics
  - Security insights

- ✅ **Priority Support**
  - Email support (24h response)
  - Priority bug fixes
  - Migration assistance

#### Limits:
- 10,000 users total
- 10 organizations
- 10,000 API requests/hour
- 50 webhooks

---

### 🏢 Enterprise
**Price**: Custom pricing (contact sales)
**Target**: Large organizations, enterprises

#### Everything in Professional, plus:
- ✅ **Single Sign-On (SSO)**
  - SAML 2.0
  - OpenID Connect (OIDC)
  - Custom identity providers

- ✅ **Advanced Security**
  - Audit logs with retention
  - Security compliance reports
  - Advanced threat detection
  - Session management

- ✅ **Custom Roles & Permissions**
  - Unlimited custom roles
  - Fine-grained permissions
  - Attribute-based access control (ABAC)

- ✅ **White Labeling**
  - Complete UI customization
  - Custom branding
  - Private labeling options

- ✅ **Compliance & Reporting**
  - SOC 2 Type II reports
  - GDPR compliance tools
  - Custom compliance reports
  - Data residency options

- ✅ **Infrastructure Options**
  - On-premise deployment
  - Private cloud deployment
  - Multi-region support
  - Custom SLA

- ✅ **Premium Support**
  - Dedicated account manager
  - 24/7 phone & email support
  - Custom integration support
  - Professional services

#### Limits:
- Unlimited users
- Unlimited organizations
- Unlimited API requests
- Unlimited webhooks
- Custom rate limits

---

## Feature Comparison Matrix

| Feature | Community | Professional | Enterprise |
|---------|-----------|--------------|------------|
| **Authentication** |
| Email/Password | ✅ | ✅ | ✅ |
| Social Login | ✅ | ✅ | ✅ |
| Magic Links | ✅ | ✅ | ✅ |
| MFA (TOTP) | ✅ | ✅ | ✅ |
| MFA (SMS) | Basic | ✅ | ✅ |
| WebAuthn/Passkeys | ❌ | ✅ | ✅ |
| SSO (SAML) | ❌ | ❌ | ✅ |
| SSO (OIDC) | ❌ | ❌ | ✅ |
| **User Management** |
| User Profiles | ✅ | ✅ | ✅ |
| User Search | Basic | ✅ | ✅ |
| Bulk Operations | ❌ | ✅ | ✅ |
| Custom Attributes | ❌ | Limited | ✅ |
| **Organizations** |
| Multi-tenancy | Basic | ✅ | ✅ |
| Team Management | ❌ | ✅ | ✅ |
| Custom Roles | ❌ | Basic | ✅ |
| ABAC | ❌ | ❌ | ✅ |
| **Security** |
| Rate Limiting | Basic | ✅ | Custom |
| IP Allowlisting | ❌ | ✅ | ✅ |
| Audit Logs | ❌ | 30 days | Unlimited |
| Session Management | Basic | ✅ | ✅ |
| Device Trust | ❌ | ✅ | ✅ |
| **Compliance** |
| GDPR Tools | Basic | ✅ | ✅ |
| SOC 2 Reports | ❌ | ❌ | ✅ |
| HIPAA Ready | ❌ | ❌ | ✅ |
| Data Residency | ❌ | ❌ | ✅ |
| **Developer Tools** |
| REST API | ✅ | ✅ | ✅ |
| SDKs | ✅ | ✅ | ✅ |
| Webhooks | 5 | 50 | Unlimited |
| API Keys | 1 | Unlimited | Unlimited |
| Rate Limits | 1K/hour | 10K/hour | Custom |
| **Support** |
| Documentation | ✅ | ✅ | ✅ |
| Community Forum | ✅ | ✅ | ✅ |
| Email Support | ❌ | 24h | Priority |
| Phone Support | ❌ | ❌ | 24/7 |
| Dedicated Manager | ❌ | ❌ | ✅ |
| SLA | ❌ | 99.9% | Custom |
| **Infrastructure** |
| Cloud Hosting | Shared | Shared | Dedicated |
| On-Premise | ❌ | ❌ | ✅ |
| Multi-Region | ❌ | ❌ | ✅ |
| Custom Domain | ❌ | ✅ | ✅ |
| White Label | ❌ | Partial | ✅ |

---

## Add-Ons (Professional & Enterprise)

### 📊 Advanced Analytics
**Price**: $49/month
- Real-time dashboards
- Custom reports
- Data export (CSV, JSON)
- API analytics

### 📧 Email Add-on
**Price**: $29/month per 10,000 emails
- Transactional emails
- Custom templates
- Email analytics
- Dedicated IP

### 💾 Extended Data Retention
**Price**: $99/month per TB
- Extended audit logs
- Long-term user data
- Compliance archives

### 🌍 Additional Regions
**Price**: $199/month per region
- Data residency
- Low-latency access
- Regional compliance

---

## Frequently Asked Questions

### Can I switch plans?
Yes, you can upgrade or downgrade at any time. Upgrades are instant, downgrades take effect at the next billing cycle.

### Is there a free trial for paid plans?
Yes, Professional plan includes a 14-day free trial. Enterprise plans include POC periods.

### What happens if I exceed my limits?
- **Community**: API calls are rate-limited
- **Professional**: Soft limits with notifications
- **Enterprise**: Custom handling based on agreement

### Can I self-host the Community Edition?
Yes, the Community Edition can be self-hosted. See our [deployment guide](./DEPLOYMENT.md).

### Do you offer discounts?
- **Nonprofits**: 50% discount on Professional
- **Education**: 80% discount on Professional
- **Startups**: Special programs available
- **Annual billing**: Save 2 months

### What payment methods do you accept?
- Credit/debit cards (Stripe)
- ACH transfers (Professional+)
- Wire transfers (Enterprise)
- Invoicing (Enterprise)

### How is user count calculated?
Monthly Active Users (MAU) - unique users who authenticate at least once per month.

### Can I get a custom plan?
Yes, contact sales@plinto.dev for custom requirements.

---

## Contact Sales

For Enterprise inquiries or custom requirements:
- 📧 Email: sales@plinto.dev
- 🌐 Website: https://plinto.dev/contact
- 📅 Book a demo: https://plinto.dev/demo

---

## License Terms

- **Community**: MIT License (open source)
- **Professional**: Commercial License
- **Enterprise**: Custom Enterprise Agreement

See [LICENSE](./LICENSE) for Community Edition terms.