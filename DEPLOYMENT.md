# Plinto Deployment Guide

## 🚀 Quick Deploy to Vercel

This project is configured for easy deployment to Vercel with our mock API for demo purposes.

### Prerequisites

1. [Vercel Account](https://vercel.com/signup)
2. [GitHub Account](https://github.com)
3. Node.js 18+ installed locally

### Deployment Steps

#### 1. Fork & Clone Repository

```bash
git clone https://github.com/aureolabs/plinto.git
cd plinto
yarn install
```

#### 2. Deploy Marketing Site

```bash
# From project root
cd apps/marketing
vercel --prod
```

When prompted:
- Set up and deploy: Y
- Which scope: Select your Vercel account
- Link to existing project: N
- Project name: `plinto-marketing`
- Directory: `./`
- Override settings: N

#### 3. Deploy Auth App

```bash
# From project root
cd apps/auth
vercel --prod
```

When prompted:
- Project name: `plinto-auth`
- Follow same steps as marketing

#### 4. Deploy Mock API (Vercel Functions)

Create `api/` directory in `apps/auth`:

```bash
mkdir -p apps/auth/api
cp packages/mock-api/src/server.ts apps/auth/api/index.ts
```

Then redeploy auth app:
```bash
cd apps/auth
vercel --prod
```

#### 5. Configure Custom Domains

In Vercel Dashboard:

1. **Marketing Site** (`plinto-marketing`):
   - Add domain: `plinto.dev`
   - Add domain: `www.plinto.dev` (redirect to plinto.dev)

2. **Auth App** (`plinto-auth`):
   - Add domain: `app.plinto.dev`

#### 6. Set Environment Variables

In Vercel Dashboard for both projects:

```env
NEXT_PUBLIC_API_URL=https://app.plinto.dev/api
NEXT_PUBLIC_APP_URL=https://app.plinto.dev
```

### Local Development

#### Start All Services

```bash
# Terminal 1: Marketing site
cd apps/marketing
yarn dev
# Runs on http://localhost:3001

# Terminal 2: Auth app
cd apps/auth
yarn dev
# Runs on http://localhost:3002

# Terminal 3: Mock API
cd packages/mock-api
yarn dev
# Runs on http://localhost:4000
```

#### Test Credentials

```
Email: demo@plinto.dev
Password: DemoPassword123!
```

### Project Structure

```
plinto/
├── apps/
│   ├── marketing/        # Public website (plinto.dev)
│   └── auth/            # Auth app (app.plinto.dev)
├── packages/
│   ├── sdk/             # JavaScript SDK
│   ├── ui/              # Shared UI components
│   └── mock-api/        # Mock API server
└── vercel.json          # Vercel configuration
```

### Available URLs

After deployment:

- **Marketing**: https://plinto.dev
- **Auth App**: https://app.plinto.dev
  - Sign In: https://app.plinto.dev/signin
  - Sign Up: https://app.plinto.dev/signup
  - Dashboard: https://app.plinto.dev/dashboard
- **API**: https://app.plinto.dev/api

### Features Included

✅ **Authentication Pages**
- Sign In with email/password
- Sign Up with validation
- User Dashboard

✅ **Marketing Site**
- Landing page with all sections
- Pricing page
- About page
- Responsive design

✅ **Mock API**
- JWT token generation
- Session management
- User CRUD operations
- In-memory database

### Next Steps

1. **Production API**: Replace mock API with Railway deployment
2. **Database**: Connect PostgreSQL and Redis
3. **Email**: Configure SendGrid for email verification
4. **Monitoring**: Add Sentry and PostHog
5. **CDN**: Configure Cloudflare

### Troubleshooting

#### Build Errors

```bash
# Clear cache and reinstall
rm -rf node_modules .next
yarn install
yarn build
```

#### Port Conflicts

```bash
# Kill processes on ports
lsof -ti:3001 | xargs kill -9
lsof -ti:3002 | xargs kill -9
lsof -ti:4000 | xargs kill -9
```

#### Environment Variables

Ensure `.env.local` exists in both apps:

```bash
cp .env.example apps/marketing/.env.local
cp .env.example apps/auth/.env.local
```

### Support

- Documentation: https://docs.plinto.dev
- GitHub Issues: https://github.com/aureolabs/plinto/issues
- Email: support@plinto.dev

---

**Note**: This is a demo deployment using mock data. For production, you'll need to:
1. Set up Railway for the API
2. Configure PostgreSQL and Redis
3. Implement real authentication logic
4. Add proper security headers and CORS