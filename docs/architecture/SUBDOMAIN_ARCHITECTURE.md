# Janua Subdomain Architecture

## Domain & Folder Mapping

Clear separation of concerns with dedicated subdomains and corresponding folder structure:

### Production Domains

| Subdomain | Folder | Purpose | Deployment |
|-----------|--------|---------|------------|
| `janua.dev` / `www.janua.dev` | `/apps/marketing` | Marketing & public website | Vercel |
| `app.janua.dev` | `/apps/dashboard` | Customer dashboard (tenant admins) | Vercel |
| `admin.janua.dev` | `/apps/admin` | Internal superadmin tools | Vercel (restricted) |
| `api.janua.dev` | `/apps/api` | Core API (FastAPI/Python) | Railway |
| `docs.janua.dev` | `/apps/docs` | Documentation (future) | Mintlify/Vercel |
| `status.janua.dev` | External | Status page | Better Stack |

### Local Development Ports

```bash
# Frontend Applications
http://localhost:3003  # Marketing (janua.dev)
http://localhost:3001  # Dashboard (app.janua.dev)
http://localhost:3002  # Admin (admin.janua.dev)
http://localhost:3004  # Docs (docs.janua.dev) - future

# Backend Services
http://localhost:8000  # API (api.janua.dev)
http://localhost:5432  # PostgreSQL
http://localhost:6379  # Redis
```

## Folder Structure

```
janua/
├── apps/
│   ├── marketing/        # Public marketing site
│   │   └── package.json  # @janua/marketing
│   │
│   ├── dashboard/        # Customer dashboard (was: admin)
│   │   └── package.json  # @janua/dashboard
│   │
│   ├── admin/            # Internal superadmin tools (new)
│   │   └── package.json  # @janua/admin
│   │
│   └── api/              # Core API (Python/FastAPI)
│       └── README.md     # API documentation
│
├── packages/
│   ├── ui/               # Shared UI components
│   ├── sdk-js/           # JavaScript SDK
│   └── react/            # React SDK
│
└── infra/
    ├── monitoring/       # Alerts and dashboards
    └── postgres/         # Database init scripts
```

## Application Responsibilities

### 🌐 Marketing (`janua.dev`)
**Public-facing website and product information**
- Landing pages and product features
- Pricing and comparison tables
- Company information and blog
- Sign up/Sign in CTAs → redirect to `app.janua.dev`
- Documentation links → redirect to `docs.janua.dev`

### 📊 Customer Dashboard (`app.janua.dev`)
**Where paying customers manage their authentication**
- Tenant configuration and settings
- User management for their organization
- API keys and SDK configuration
- Analytics and usage metrics
- Billing and subscription management
- Team member invitations
- Webhook configuration
- Audit logs for their tenant

### 🔧 Internal Admin (`admin.janua.dev`)
**Janua team superadmin access only**
- Platform-wide tenant management
- Customer support tools
- System health monitoring
- Feature flags management
- Database administration
- Security incident response
- Billing overrides and adjustments
- Platform analytics and metrics

### 🚀 API (`api.janua.dev`)
**Core authentication and identity services**
- Authentication endpoints (`/auth/*`)
- Session management (`/sessions/*`)
- JWT issuance and verification
- User CRUD operations
- Organization and RBAC management
- Webhook delivery
- Policy evaluation (OPA)
- Analytics ingestion

## Security & Access Control

### Public Access
- `janua.dev` - Fully public
- `docs.janua.dev` - Fully public
- `status.janua.dev` - Fully public

### Authenticated Access
- `app.janua.dev` - Requires tenant user authentication
- `api.janua.dev` - Requires valid API key or JWT

### Restricted Access
- `admin.janua.dev` - Janua team only (separate auth)

## Environment Variables

### Marketing App
```env
NEXT_PUBLIC_APP_URL=https://app.janua.dev
NEXT_PUBLIC_API_URL=https://api.janua.dev
NEXT_PUBLIC_DOCS_URL=https://docs.janua.dev
```

### Dashboard App
```env
NEXT_PUBLIC_API_URL=https://api.janua.dev
NEXT_PUBLIC_MARKETING_URL=https://janua.dev
JANUA_API_KEY=<api_key>
```

### Admin App
```env
NEXT_PUBLIC_API_URL=https://api.janua.dev
ADMIN_AUTH_SECRET=<secret>
ADMIN_ALLOWED_EMAILS=team@janua.dev
```

### API Service
```env
DATABASE_URL=postgresql://...
REDIS_URL=redis://...
JWT_SECRET=<secret>
CORS_ORIGINS=https://app.janua.dev,https://admin.janua.dev
```

## Deployment Commands

```bash
# Deploy marketing to janua.dev
cd apps/marketing && vercel --prod

# Deploy dashboard to app.janua.dev
cd apps/dashboard && vercel --prod --scope janua

# Deploy admin to admin.janua.dev
cd apps/admin && vercel --prod --scope janua

# Deploy API to Railway
railway up -p janua-api
```

## DNS Configuration

```dns
# Root domain
janua.dev          A     76.76.21.21 (Vercel)
www.janua.dev      CNAME cname.vercel-dns.com

# Subdomains
app.janua.dev      CNAME cname.vercel-dns.com
admin.janua.dev    CNAME cname.vercel-dns.com
api.janua.dev      CNAME janua-api.up.railway.app
docs.janua.dev     CNAME cname.vercel-dns.com
status.janua.dev   CNAME status.betterstack.com
```

## Migration Status

- [x] Rename `apps/admin` → `apps/dashboard`
- [x] Create new `apps/admin` for internal tools
- [x] Update package.json names
- [x] Configure development ports
- [ ] Deploy dashboard to `app.janua.dev`
- [ ] Deploy admin to `admin.janua.dev`
- [ ] Update environment variables
- [ ] Configure DNS records
- [ ] Update CORS policies