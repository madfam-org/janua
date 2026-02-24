# Janua Dashboard

> **Customer tenant management portal** for the Janua platform

**Status:** Active Development · **Domain:** `app.janua.dev` · **Port:** 4101

## Overview

The Janua Dashboard is the primary customer-facing application where users manage their accounts, organizations, team members, and platform settings. Built with Next.js and modern React patterns for optimal performance and user experience.

## Quick Start

### Prerequisites

- Node.js 18+
- pnpm (workspace management)
- Access to Janua API (local or remote)

### Installation

```bash
# From monorepo root
pnpm install

# Navigate to dashboard
cd apps/dashboard

# Start development server
pnpm dev
```

The dashboard will be available at [http://localhost:4101](http://localhost:4101)

### Environment Setup

Create a `.env.local` file in the dashboard directory:

```env
# API Configuration
NEXT_PUBLIC_API_URL=http://localhost:4100
NEXT_PUBLIC_APP_URL=http://localhost:4101
```

## Architecture

### Project Structure

```
apps/dashboard/
├── app/                          # Next.js App Router
│   ├── page.tsx                  # Dashboard home (tabbed overview)
│   ├── login/                    # Login page
│   ├── profile/                  # Profile with MFA, passkeys, devices, sessions
│   ├── users/
│   │   ├── page.tsx              # User list (search, filter, pagination)
│   │   └── [id]/page.tsx         # User detail (profile, sessions, orgs, security, audit)
│   ├── organizations/
│   │   ├── page.tsx              # Organization list
│   │   └── [id]/page.tsx         # Org detail (members, roles, settings, danger zone)
│   ├── audit-logs/               # Audit log viewer
│   ├── compliance/               # Privacy & compliance tools
│   ├── settings/
│   │   ├── page.tsx              # Settings hub (card navigation)
│   │   ├── sso/                  # SAML/OIDC SSO configuration
│   │   ├── scim/                 # SCIM provisioning
│   │   ├── invitations/          # Team invitations
│   │   ├── api-keys/             # API key management
│   │   ├── oauth-clients/        # OAuth 2.0 client CRUD + secret rotation
│   │   ├── roles/                # Roles & permissions
│   │   ├── policies/             # Authorization policy CRUD + evaluation
│   │   ├── alerts/               # Security alert configuration
│   │   ├── branding/             # White-label branding
│   │   ├── billing/              # Plans, invoices, payment methods
│   │   ├── email-templates/      # Email template editor with live preview
│   │   └── system/               # CORS, sessions, password policy, rate limits
│   └── (dashboard)/              # Layout wrapper with sidebar
├── components/
│   ├── layout/
│   │   ├── sidebar.tsx           # Collapsible sidebar navigation
│   │   └── dashboard-layout.tsx  # Auth-gated layout wrapper
│   ├── dashboard/                # Overview stats & recent activity
│   ├── users/                    # User data table, columns, filters, badges
│   ├── sessions/                 # Session list with revoke
│   ├── organizations/            # Organization list
│   ├── webhooks/
│   │   ├── webhook-list.tsx      # Webhook endpoint table
│   │   ├── webhook-form.tsx      # Create/edit dialog
│   │   └── webhook-deliveries.tsx # Delivery history viewer
│   └── audit/                    # Audit log list
├── lib/
│   ├── auth.tsx                  # apiCall() with token refresh
│   ├── janua-client.ts           # SDK client config
│   └── utils.ts                  # Helpers
└── public/                       # Static assets
```

### Technology Stack

- **Framework:** Next.js (App Router)
- **UI Library:** @janua/ui (shared design system)
- **Tables:** TanStack Table v8
- **Styling:** Tailwind CSS + Radix UI
- **Icons:** lucide-react

## Features

### User Management
- Full user list with search, status filter, and server-side pagination
- User detail page with profile, sessions, organizations, security, and audit tabs
- Suspend, reactivate, unlock, delete actions
- Bulk operations support

### Session Management
- Active session list with device/browser/location info
- Individual session revocation
- Bulk revoke all sessions

### Organization Management
- Organization list and detail pages
- Member management (invite, role change, remove)
- Custom role creation
- Transfer ownership, delete org

### OAuth Client Management
- Create, edit, delete OAuth 2.0 clients
- Secret rotation with confirmation
- Client detail view with redirect URIs and grant types

### Webhook Management
- Endpoint list with status, events, and secret management
- Create/edit form with event type multi-select
- Delivery history with retry capability
- Test webhook delivery

### Profile & Security
- Profile info editing
- TOTP MFA setup with QR code and backup codes
- WebAuthn passkey registration and management
- Device trust management
- Password change

### Settings
- SSO/SAML configuration
- SCIM provisioning
- Team invitations
- API key management
- Roles & permissions
- Authorization policies with evaluation testing
- Branding & white-label
- Billing & plans
- Email template editor with live preview
- System settings (CORS, sessions, password policy, rate limiting)

## Testing

```bash
# Unit tests
pnpm test

# Type checking
pnpm typecheck

# Lint
pnpm lint
```

## Deployment

```bash
# Build for production
pnpm build

# Start production server
pnpm start
```

### Docker

```bash
docker build -t janua-dashboard .
docker run -p 4101:4101 janua-dashboard
```

## License

Part of the Janua platform. See [LICENSE](../../LICENSE) for details.
