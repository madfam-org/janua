# Compliance Features Guide

**Version**: 1.0.0-beta  
**Last Updated**: November 16, 2025  
**Compliance Standards**: GDPR, CCPA, SOC 2

> [!NOTE]
> **Claim status:** These features support compliance *workflows*; they are
> not certifications. Per the
> [GA claim matrix](../enterprise/GA_CLAIM_MATRIX.md), compliance exports are
> **roadmap** until export/delete evidence exists, and SOC 2 Type II is a
> future compliance program, not a current certification.

## Table of Contents

1. [Overview](#overview)
2. [GDPR Compliance](#gdpr-compliance)
3. [Consent Management](#consent-management)
4. [Data Subject Rights](#data-subject-rights)
5. [Privacy Settings](#privacy-settings)
6. [Data Export & Portability](#data-export--portability)
7. [Audit Logging](#audit-logging)
8. [CCPA Compliance](#ccpa-compliance)
9. [Implementation Guide](#implementation-guide)
10. [Best Practices](#best-practices)

---

## Overview

Janua provides comprehensive compliance features to help your organization meet GDPR, CCPA, and other privacy regulations.

### Compliance Framework

```
┌─────────────────────────────────────────────────────┐
│           Janua Compliance Features                │
├─────────────────────────────────────────────────────┤
│                                                     │
│  ┌─────────────┐  ┌──────────────┐  ┌───────────┐ │
│  │  Consent    │  │   Data       │  │  Privacy  │ │
│  │  Management │  │   Subject    │  │  Settings │ │
│  │             │  │   Rights     │  │           │ │
│  └─────────────┘  └──────────────┘  └───────────┘ │
│                                                     │
│  ┌─────────────┐  ┌──────────────┐  ┌───────────┐ │
│  │  Audit      │  │   Data       │  │  Cookie   │ │
│  │  Logging    │  │   Export     │  │  Consent  │ │
│  │             │  │              │  │           │ │
│  └─────────────┘  └──────────────┘  └───────────┘ │
│                                                     │
└─────────────────────────────────────────────────────┘
```

### Key Features

✅ **Granular Consent**: Purpose-based consent management  
✅ **Data Subject Rights**: GDPR Articles 15-22 support  
✅ **Privacy Controls**: User-facing privacy settings  
✅ **Data Portability**: Export in machine-readable formats  
✅ **Audit Trail**: Complete activity logging  
✅ **Cookie Management**: Cookie consent tracking  

---

## GDPR Compliance

### Supported GDPR Articles

| Article | Right | Implementation |
|---------|-------|----------------|
| **Article 6** | Lawful basis | Consent management system |
| **Article 7** | Consent conditions | Explicit consent tracking |
| **Article 13/14** | Information | Privacy policy integration |
| **Article 15** | Access | Data export functionality |
| **Article 16** | Rectification | Profile update API |
| **Article 17** | Erasure | Account deletion |
| **Article 18** | Restriction | Processing restriction flags |
| **Article 20** | Portability | JSON/CSV export |
| **Article 21** | Objection | Opt-out mechanisms |
| **Article 22** | Automated decisions | Manual review options |

### Legal Bases

Janua supports all six GDPR legal bases:

1. **Consent** - Explicit user agreement
2. **Contract** - Necessary for service delivery
3. **Legal Obligation** - Compliance requirements
4. **Vital Interests** - Protection of life
5. **Public Task** - Public authority functions
6. **Legitimate Interests** - Business interests

---

## Consent Management

### Consent Purposes

Define processing purposes with legal basis:

```javascript
// Example consent purposes
const consentPurposes = [
  {
    id: "analytics",
    name: "Analytics and Performance",
    description: "Track usage patterns to improve the product",
    legalBasis: "consent", // GDPR Article 6(1)(a)
    required: false,
    gdprArticle: "Article 6(1)(a)",
  },
  {
    id: "marketing",
    name: "Marketing Communications",
    description: "Send promotional emails and product updates",
    legalBasis: "consent",
    required: false,
    gdprArticle: "Article 6(1)(a)",
  },
  {
    id: "essential",
    name: "Essential Services",
    description: "Core platform functionality and security",
    legalBasis: "contract", // GDPR Article 6(1)(b)
    required: true,
    gdprArticle: "Article 6(1)(b)",
  },
];
```

### Consent Flow

```
┌──────────┐
│  User    │
│  Visits  │
└────┬─────┘
     │
     ▼
┌────────────────┐
│ Display        │
│ Consent Banner │
└────┬───────────┘
     │
     ├──────────┐
     │          │
     ▼          ▼
┌─────────┐  ┌───────────┐
│ Accept  │  │  Reject   │
│ All     │  │  All      │
└────┬────┘  └─────┬─────┘
     │             │
     └──────┬──────┘
            │
            ▼
    ┌───────────────┐
    │ Save Consent  │
    │ Record        │
    └───────┬───────┘
            │
            ▼
    ┌───────────────┐
    │ IP + Timestamp│
    │ User Agent    │
    └───────────────┘
```

### API: Grant Consent

```javascript
// Grant consent for a purpose
POST /api/compliance/consent

{
  "purpose": "analytics",
  "granted": true
}

// Response
{
  "id": "consent_123abc",
  "userId": "user_456def",
  "purpose": "analytics",
  "granted": true,
  "grantedAt": "2025-11-16T15:30:00Z",
  "ipAddress": "192.168.1.1",
  "userAgent": "Mozilla/5.0..."
}
```

### API: Withdraw Consent

```javascript
// Withdraw consent
DELETE /api/compliance/consent/analytics

// Response (204 No Content)
```

### API: Get Consent Records

```javascript
// Get all consent records for current user
GET /api/compliance/consent

// Response
[
  {
    "id": "consent_123abc",
    "purpose": "analytics",
    "granted": true,
    "grantedAt": "2025-11-16T15:30:00Z",
    "withdrawnAt": null
  },
  {
    "id": "consent_456def",
    "purpose": "marketing",
    "granted": false,
    "grantedAt": null,
    "withdrawnAt": "2025-11-16T16:00:00Z"
  }
]
```

### UI Component

```tsx
import { ConsentManager } from '@janua/ui/compliance';

function App() {
  return (
    <ConsentManager
      purposes={consentPurposes}
      onConsentChange={(purpose, granted) => {
        // Handle consent change
        console.log(`${purpose}: ${granted}`);
      }}
      showBanner={true}
      position="bottom" // or "top"
    />
  );
}
```

---

## Data Subject Rights

### Article 15: Right of Access

Users can request all personal data held about them.

**API:**
```javascript
// Submit access request
POST /api/compliance/data-subject-request

{
  "requestType": "access",
  "description": "Request all my personal data per GDPR Article 15"
}

// Response
{
  "id": "dsr_123abc",
  "userId": "user_456def",
  "requestType": "access",
  "status": "pending",
  "gdprArticle": "Article 15",
  "responseDeadline": "2025-12-16T15:30:00Z", // 30 days
  "createdAt": "2025-11-16T15:30:00Z"
}
```

**Who can read the export:** `GET /api/v1/compliance/data-subject-request/{request_id}/data`
serves the export only to the request's data subject and to platform
administrators. Any other caller, including an organization administrator
who is not a platform administrator, gets the same 404 as an unknown request
id. The rule, its tests and the read-only audit script are in
[runbooks/data-subject-request-access-audit.md](../runbooks/data-subject-request-access-audit.md).

**UI Component:**
```tsx
import { DataRightsRequest } from '@janua/ui/compliance';

function PrivacyPage() {
  return (
    <DataRightsRequest
      onSubmit={(requestType, description) => {
        // Handle submission
      }}
    />
  );
}
```

### Article 16: Right to Rectification

Users can update incorrect personal data.

**API:**
```javascript
// Update profile
PATCH /api/users/me

{
  "name": "Corrected Name",
  "email": "corrected@example.com"
}
```

### Article 17: Right to Erasure

Users can request deletion of their personal data.

**API:**
```javascript
// Submit erasure request
POST /api/compliance/data-subject-request

{
  "requestType": "erasure",
  "description": "Delete all my data per GDPR Article 17"
}

// Or direct account deletion
DELETE /api/users/me
```

**Erasure Process:**
```
1. User submits erasure request
2. Verification step (re-authentication)
3. 30-day grace period (optional)
4. Data anonymization or deletion
5. Confirmation email
6. Audit log entry
```

### Article 18: Right to Restriction

Users can request processing restriction.

**API:**
```javascript
// Submit restriction request
POST /api/compliance/data-subject-request

{
  "requestType": "restriction",
  "description": "Restrict processing while I verify accuracy"
}
```

### Article 20: Right to Portability

Users can export their data in machine-readable format.

**API:**
```javascript
// Request data export
POST /api/compliance/data-export

{
  "format": "json", // or "csv"
  "includeAttachments": true
}

// Response
{
  "id": "export_123abc",
  "status": "processing",
  "format": "json",
  "estimatedCompletionTime": "2025-11-16T15:45:00Z"
}

// Download when ready
GET /api/compliance/data-export/export_123abc/download

// Response (JSON)
{
  "userData": {
    "profile": {
      "id": "user_456def",
      "email": "user@example.com",
      "name": "John Doe",
      "createdAt": "2025-01-15T10:30:00Z"
    },
    "consentRecords": [...],
    "activityLog": [...],
    "preferences": {...}
  },
  "metadata": {
    "exportedAt": "2025-11-16T15:45:00Z",
    "format": "json",
    "version": "1.0"
  }
}
```

### Article 21: Right to Object

Users can object to certain processing.

**API:**
```javascript
// Object to marketing
PATCH /api/compliance/preferences

{
  "marketing": {
    "email": false,
    "sms": false,
    "push": false
  }
}
```

### Request Status Tracking

```javascript
// Get all data subject requests
GET /api/compliance/data-subject-requests

// Response
[
  {
    "id": "dsr_123abc",
    "requestType": "access",
    "status": "completed",
    "gdprArticle": "Article 15",
    "createdAt": "2025-10-16T15:30:00Z",
    "completedAt": "2025-10-20T10:00:00Z",
    "responseDeadline": "2025-11-15T15:30:00Z"
  },
  {
    "id": "dsr_456def",
    "requestType": "erasure",
    "status": "pending",
    "gdprArticle": "Article 17",
    "createdAt": "2025-11-16T15:30:00Z",
    "responseDeadline": "2025-12-16T15:30:00Z"
  }
]
```

---

## Privacy Settings

### User-Facing Privacy Controls

```tsx
import { PrivacySettings } from '@janua/ui/compliance';

function PrivacyPage() {
  return (
    <PrivacySettings
      settings={{
        analytics: true,
        marketing: false,
        profileVisibility: "private",
        shareData: false
      }}
      onSettingsChange={(settings) => {
        // Save settings
      }}
    />
  );
}
```

### Privacy Setting Categories

```javascript
// Example privacy settings structure
const privacySettings = {
  tracking: {
    analytics: false,
    performance: true,
    advertising: false
  },
  marketing: {
    email: false,
    sms: false,
    push: false,
    thirdParty: false
  },
  profile: {
    visibility: "private", // public, private, contacts
    showEmail: false,
    showPhone: false
  },
  dataSharing: {
    analytics: false,
    research: false,
    partners: false
  },
  cookies: {
    essential: true,  // Cannot be disabled
    functional: true,
    analytics: false,
    advertising: false
  }
};
```

### API: Update Privacy Settings

```javascript
// Update privacy settings
PATCH /api/compliance/privacy-settings

{
  "tracking": {
    "analytics": false
  },
  "marketing": {
    "email": false
  }
}

// Response
{
  "tracking": {
    "analytics": false,
    "performance": true,
    "advertising": false
  },
  "marketing": {
    "email": false,
    "sms": false,
    "push": false
  },
  "updatedAt": "2025-11-16T15:30:00Z"
}
```

---

## Data Export & Portability

### Export Formats

**JSON Export** (Machine-readable):
```json
{
  "user": {
    "id": "user_456def",
    "email": "user@example.com",
    "name": "John Doe",
    "phone": "+1234567890",
    "createdAt": "2025-01-15T10:30:00Z"
  },
  "profile": {
    "bio": "Software developer",
    "avatar": "https://..."
  },
  "activity": [
    {
      "action": "login",
      "timestamp": "2025-11-16T08:00:00Z",
      "ipAddress": "192.168.1.1"
    }
  ],
  "consent": [
    {
      "purpose": "analytics",
      "granted": true,
      "timestamp": "2025-11-16T15:30:00Z"
    }
  ]
}
```

**CSV Export** (Human-readable):
```csv
Section,Field,Value
Profile,Email,user@example.com
Profile,Name,John Doe
Profile,Created At,2025-01-15T10:30:00Z
Consent,Analytics,Granted
Consent,Marketing,Withdrawn
Activity,Last Login,2025-11-16T08:00:00Z
```

### Export Process

```
1. User requests export
   ├─ Select format (JSON/CSV)
   └─ Choose data scope

2. System generates export
   ├─ Collect user data
   ├─ Anonymize sensitive info
   └─ Package in selected format

3. Notification sent
   ├─ Email with download link
   └─ Link expires in 7 days

4. User downloads
   ├─ Secure download (HTTPS)
   └─ Audit log entry
```

---

## Audit Logging

### Compliance Audit Events

```javascript
// Example audit log entries
const auditLog = [
  {
    "id": "audit_123abc",
    "timestamp": "2025-11-16T15:30:00Z",
    "userId": "user_456def",
    "action": "consent_granted",
    "resource": "consent",
    "resourceId": "consent_analytics",
    "details": {
      "purpose": "analytics",
      "ipAddress": "192.168.1.1",
      "userAgent": "Mozilla/5.0..."
    }
  },
  {
    "id": "audit_456def",
    "timestamp": "2025-11-16T16:00:00Z",
    "userId": "user_456def",
    "action": "data_export_requested",
    "resource": "export",
    "resourceId": "export_789ghi",
    "details": {
      "format": "json",
      "requestedBy": "user_456def"
    }
  }
];
```

### Auditable Events

| Category | Events |
|----------|--------|
| **Consent** | Grant, withdraw, update |
| **Data Subject Rights** | Request submission, processing, completion |
| **Data Access** | Export, download, view |
| **Profile** | Update, delete |
| **Privacy** | Settings change |
| **Authentication** | Login, logout, MFA |

### API: Query Audit Logs

```javascript
// Get audit logs for current user
GET /api/compliance/audit-log?startDate=2025-11-01&endDate=2025-11-30

// Response
{
  "logs": [
    {
      "timestamp": "2025-11-16T15:30:00Z",
      "action": "consent_granted",
      "details": "Granted consent for analytics"
    }
  ],
  "total": 42,
  "page": 1
}
```

---

## CCPA Compliance

### CCPA-Specific Features

| CCPA Right | Implementation |
|------------|----------------|
| **Right to Know** | Data export (Article 15 equivalent) |
| **Right to Delete** | Account deletion (Article 17 equivalent) |
| **Right to Opt-Out** | "Do Not Sell" preference |
| **Right to Non-Discrimination** | No service denial for opt-outs |

### Do Not Sell My Personal Information

```javascript
// API: Set "Do Not Sell" preference
PATCH /api/compliance/ccpa-preferences

{
  "doNotSell": true
}

// Response
{
  "doNotSell": true,
  "effectiveDate": "2025-11-16T15:30:00Z",
  "ipAddress": "192.168.1.1"
}
```

### CCPA Privacy Notice

Display on website:

```html
<a href="/privacy/ccpa">Do Not Sell My Personal Information</a>
```

---

## Implementation Guide

### Step 1: Enable Compliance Features

```javascript
// In your Janua organization settings
{
  "compliance": {
    "enabled": true,
    "gdpr": true,
    "ccpa": true,
    "dataRetentionDays": 2555, // 7 years
    "automaticDeletion": false
  }
}
```

### Step 2: Integrate Consent Manager

```tsx
// app/layout.tsx
import { ConsentManager } from '@janua/ui/compliance';

export default function RootLayout({ children }) {
  return (
    <html>
      <body>
        {children}
        <ConsentManager
          purposes={[
            {
              id: "analytics",
              name: "Analytics",
              description: "Help us improve",
              required: false
            },
            {
              id: "marketing",
              name: "Marketing",
              description: "Product updates",
              required: false
            }
          ]}
          onConsentChange={(purpose, granted) => {
            // Track consent change
            if (granted) {
              // Enable analytics/marketing
            } else {
              // Disable analytics/marketing
            }
          }}
        />
      </body>
    </html>
  );
}
```

### Step 3: Add Privacy Settings Page

```tsx
// app/privacy/page.tsx
import { PrivacySettings, DataRightsRequest } from '@janua/ui/compliance';

export default function PrivacyPage() {
  return (
    <div>
      <h1>Privacy Center</h1>
      
      <section>
        <h2>Privacy Settings</h2>
        <PrivacySettings />
      </section>
      
      <section>
        <h2>Your Data Rights</h2>
        <DataRightsRequest />
      </section>
    </div>
  );
}
```

### Step 4: Handle Data Subject Requests

```typescript
// Server-side handler
import { JanuaClient } from '@janua/sdk';

async function handleDataSubjectRequest(
  userId: string,
  requestType: 'access' | 'erasure' | 'portability'
) {
  const janua = new JanuaClient({ apiKey: process.env.JANUA_API_KEY });
  
  // Submit request
  const request = await janua.compliance.submitDataSubjectRequest({
    userId,
    requestType,
    description: `User requested ${requestType}`
  });
  
  // Process based on type
  switch (requestType) {
    case 'access':
      // Generate data export
      return await janua.compliance.exportUserData(userId);
      
    case 'erasure':
      // Schedule account deletion
      return await janua.users.delete(userId);
      
    case 'portability':
      // Export in portable format
      return await janua.compliance.exportUserData(userId, { format: 'json' });
  }
}
```

---

## Best Practices

### 1. Consent Management

✅ **Do:**
- Request consent before processing
- Make consent easy to withdraw
- Keep consent records with timestamp + IP
- Provide granular consent options
- Re-request consent on significant changes

❌ **Don't:**
- Use pre-checked boxes
- Bundle unrelated purposes
- Hide withdrawal option
- Require consent for essential services

### 2. Data Subject Requests

✅ **Do:**
- Respond within 30 days (GDPR) or 45 days (CCPA)
- Verify user identity
- Provide data in readable format
- Log all requests
- Automate where possible

❌ **Don't:**
- Charge excessive fees
- Request unnecessary information
- Delay responses
- Ignore requests

### 3. Privacy by Design

✅ **Do:**
- Minimize data collection
- Implement data retention policies
- Use pseudonymization
- Enable privacy settings by default
- Regular privacy audits

❌ **Don't:**
- Collect unnecessary data
- Store data indefinitely
- Share without consent
- Use dark patterns

### 4. Transparency

✅ **Do:**
- Clear privacy policy
- Easy-to-understand language
- Prominent privacy controls
- Regular privacy updates
- Audit log access for users

❌ **Don't:**
- Hide privacy settings
- Use legal jargon
- Change policies without notice
- Restrict data access

---

## Compliance Checklist

### GDPR Readiness

- [ ] **Consent Management**
  - [ ] Granular consent purposes
  - [ ] Withdrawal mechanism
  - [ ] Consent record keeping

- [ ] **Data Subject Rights**
  - [ ] Access (Article 15)
  - [ ] Rectification (Article 16)
  - [ ] Erasure (Article 17)
  - [ ] Portability (Article 20)

- [ ] **Privacy Controls**
  - [ ] Privacy settings page
  - [ ] Data export functionality
  - [ ] Account deletion

- [ ] **Documentation**
  - [ ] Privacy policy
  - [ ] Cookie policy
  - [ ] Data processing records

- [ ] **Security**
  - [ ] Encryption at rest
  - [ ] Encryption in transit
  - [ ] Access controls
  - [ ] Audit logging

### CCPA Readiness

- [ ] **Consumer Rights**
  - [ ] Right to know
  - [ ] Right to delete
  - [ ] Right to opt-out

- [ ] **Notices**
  - [ ] Privacy notice
  - [ ] "Do Not Sell" link
  - [ ] CCPA disclosure

- [ ] **Processes**
  - [ ] Verified request handling
  - [ ] 45-day response timeline
  - [ ] Non-discrimination policy

---

## Support & Resources

- **Documentation**: https://docs.janua.dev/compliance
- **Privacy Policy**: https://madfam.io/en/privacy
- **GDPR Guide**: https://docs.janua.dev/gdpr
- **CCPA Guide**: https://docs.janua.dev/ccpa
- **Email Support**: compliance@janua.dev

---

**Last Updated**: November 16, 2025  
**Version**: 1.0.0-beta  
**Support**: compliance@janua.dev
