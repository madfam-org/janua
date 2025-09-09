# Plinto Subdomain Architecture

## Domain & Folder Mapping

Clear separation of concerns with dedicated subdomains and corresponding folder structure:

### Production Domains

| Subdomain | Folder | Purpose | Deployment |
|-----------|--------|---------|------------|
| `plinto.dev` / `www.plinto.dev` | `/apps/marketing` | Marketing & public website | Vercel |
| `app.plinto.dev` | `/apps/dashboard` | Customer dashboard (tenant admins) | Vercel |
| `admin.plinto.dev` | `/apps/admin` | Internal superadmin tools | Vercel (restricted) |
| `api.plinto.dev` | `/apps/api` | Core API (FastAPI/Python) | Railway |
| `docs.plinto.dev` | `/apps/docs` | Documentation (future) | Mintlify/Vercel |
| `status.plinto.dev` | External | Status page | Better Stack |

### Local Development Ports

```bash
# Frontend Applications
http://localhost:3003  # Marketing (plinto.dev)
http://localhost:3001  # Dashboard (app.plinto.dev)
http://localhost:3002  # Admin (admin.plinto.dev)
http://localhost:3004  # Docs (docs.plinto.dev) - future

# Backend Services
http://localhost:8000  # API (api.plinto.dev)
http://localhost:5432  # PostgreSQL
http://localhost:6379  # Redis
```

## Folder Structure

```
plinto/
├── apps/
│   ├── marketing/        # Public marketing site
│   │   └── package.json  # @plinto/marketing
│   │
│   ├── dashboard/        # Customer dashboard (was: admin)
│   │   └── package.json  # @plinto/dashboard
│   │
│   ├── admin/            # Internal superadmin tools (new)
│   │   └── package.json  # @plinto/admin
│   │
│   └── api/              # Core API (Python/FastAPI)
│       └── README.md     # API documentation
│
├── packages/
│   ├── ui/               # Shared UI components
│   ├── sdk-js/           # JavaScript SDK
│   └── react/            # React SDK
│
└── infrastructure/
    ├── vercel.json       # Vercel configs
    └── railway.toml      # Railway configs
```

## Application Responsibilities

### 🌐 Marketing (`plinto.dev`)
**Public-facing website and product information**
- Landing pages and product features
- Pricing and comparison tables
- Company information and blog
- Sign up/Sign in CTAs → redirect to `app.plinto.dev`
- Documentation links → redirect to `docs.plinto.dev`

### 📊 Customer Dashboard (`app.plinto.dev`)
**Where paying customers manage their authentication**
- Tenant configuration and settings
- User management for their organization
- API keys and SDK configuration
- Analytics and usage metrics
- Billing and subscription management
- Team member invitations
- Webhook configuration
- Audit logs for their tenant

### 🔧 Internal Admin (`admin.plinto.dev`)
**Plinto team superadmin access only**
- Platform-wide tenant management
- Customer support tools
- System health monitoring
- Feature flags management
- Database administration
- Security incident response
- Billing overrides and adjustments
- Platform analytics and metrics

### 🚀 API (`api.plinto.dev`)
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
- `plinto.dev` - Fully public
- `docs.plinto.dev` - Fully public
- `status.plinto.dev` - Fully public

### Authenticated Access
- `app.plinto.dev` - Requires tenant user authentication
- `api.plinto.dev` - Requires valid API key or JWT

### Restricted Access
- `admin.plinto.dev` - Plinto team only (separate auth)

## Environment Variables

### Marketing App
```env
NEXT_PUBLIC_APP_URL=https://app.plinto.dev
NEXT_PUBLIC_API_URL=https://api.plinto.dev
NEXT_PUBLIC_DOCS_URL=https://docs.plinto.dev
```

### Dashboard App
```env
NEXT_PUBLIC_API_URL=https://api.plinto.dev
NEXT_PUBLIC_MARKETING_URL=https://plinto.dev
PLINTO_API_KEY=<api_key>
```

### Admin App
```env
NEXT_PUBLIC_API_URL=https://api.plinto.dev
ADMIN_AUTH_SECRET=<secret>
ADMIN_ALLOWED_EMAILS=team@plinto.dev
```

### API Service
```env
DATABASE_URL=postgresql://...
REDIS_URL=redis://...
JWT_SECRET=<secret>
CORS_ORIGINS=https://app.plinto.dev,https://admin.plinto.dev
```

## Deployment Commands

```bash
# Deploy marketing to plinto.dev
cd apps/marketing && vercel --prod

# Deploy dashboard to app.plinto.dev
cd apps/dashboard && vercel --prod --scope plinto

# Deploy admin to admin.plinto.dev
cd apps/admin && vercel --prod --scope plinto

# Deploy API to Railway
railway up -p plinto-api
```

## DNS Configuration

```dns
# Root domain
plinto.dev          A     76.76.21.21 (Vercel)
www.plinto.dev      CNAME cname.vercel-dns.com

# Subdomains
app.plinto.dev      CNAME cname.vercel-dns.com
admin.plinto.dev    CNAME cname.vercel-dns.com
api.plinto.dev      CNAME plinto-api.up.railway.app
docs.plinto.dev     CNAME cname.vercel-dns.com
status.plinto.dev   CNAME status.betterstack.com
```

## Migration Status

- [x] Rename `apps/admin` → `apps/dashboard`
- [x] Create new `apps/admin` for internal tools
- [x] Update package.json names
- [x] Configure development ports
- [ ] Deploy dashboard to `app.plinto.dev`
- [ ] Deploy admin to `admin.plinto.dev`
- [ ] Update environment variables
- [ ] Configure DNS records
- [ ] Update CORS policies