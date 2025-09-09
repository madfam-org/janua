# Plinto Implementation Guide

## Quick Start Development Path

This guide provides the optimal implementation strategy to build Plinto from zero to production-ready in 12 weeks.

---

## Week 1-2: Foundation Sprint

### Day 1: Project Setup

```bash
# Initialize monorepo
mkdir plinto && cd plinto
npm init -y
npm install -D turbo typescript @types/node

# Create project structure
mkdir -p apps/{api,admin,docs,edge-verify}
mkdir -p packages/{core,database,sdk-js,ui}
mkdir -p infrastructure/{docker,terraform,k8s}
```

### Day 2-3: Core API Skeleton

```python
# apps/api/main.py
from fastapi import FastAPI, Depends
from contextlib import asynccontextmanager
import asyncpg
import redis.asyncio as redis

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    app.state.db = await asyncpg.create_pool(DATABASE_URL)
    app.state.redis = await redis.from_url(REDIS_URL)
    yield
    # Shutdown
    await app.state.db.close()
    await app.state.redis.close()

app = FastAPI(lifespan=lifespan)

# Health check
@app.get("/health")
async def health():
    return {"status": "healthy"}

# Core auth endpoints
@app.post("/api/v1/identities")
async def create_identity(data: CreateIdentityRequest):
    # Implementation
    pass

@app.post("/api/v1/sessions")
async def create_session(data: CreateSessionRequest):
    # Implementation  
    pass
```

### Day 4-5: Database Setup

```sql
-- Run migrations
psql $DATABASE_URL < infrastructure/postgres/001_initial.sql
psql $DATABASE_URL < infrastructure/postgres/002_partitions.sql
```

### Day 6-7: JWT Implementation

```python
# apps/api/auth/jwt.py
import jwt
from datetime import datetime, timedelta

class TokenManager:
    def create_access_token(self, identity_id: str, tenant_id: str) -> str:
        payload = {
            "sub": identity_id,
            "tid": tenant_id,
            "iat": datetime.utcnow(),
            "exp": datetime.utcnow() + timedelta(minutes=15),
            "jti": str(uuid4())
        }
        return jwt.encode(payload, self.private_key, algorithm="RS256")
    
    def verify_token(self, token: str) -> dict:
        return jwt.decode(token, self.public_key, algorithms=["RS256"])
```

### Day 8-10: Edge Verification

```typescript
// apps/edge-verify/index.ts
export default {
  async fetch(request: Request): Promise<Response> {
    const authorization = request.headers.get('Authorization');
    if (!authorization?.startsWith('Bearer ')) {
      return new Response('Unauthorized', { status: 401 });
    }
    
    const token = authorization.slice(7);
    const jwks = await getJWKS();
    
    try {
      const payload = await verifyJWT(token, jwks);
      return new Response(JSON.stringify(payload), {
        headers: { 'Content-Type': 'application/json' }
      });
    } catch (error) {
      return new Response('Invalid token', { status: 401 });
    }
  }
};
```

### Day 11-14: Basic SDK

```typescript
// packages/sdk-js/src/index.ts
export class PlintoClient {
  constructor(private config: PlintoConfig) {}
  
  async createIdentity(data: CreateIdentityData) {
    return this.request('/identities', { method: 'POST', body: data });
  }
  
  async createSession(credentials: Credentials) {
    return this.request('/sessions', { method: 'POST', body: credentials });
  }
  
  async verifyToken(token: string) {
    // Local verification with cached JWKS
    const jwks = await this.getJWKS();
    return verifyJWT(token, jwks);
  }
}
```

---

## Week 3-4: Production Hardening

### Infrastructure as Code

```hcl
# infrastructure/terraform/main.tf
terraform {
  required_providers {
    railway = { source = "railway/railway" }
    vercel = { source = "vercel/vercel" }
    cloudflare = { source = "cloudflare/cloudflare" }
  }
}

module "backend" {
  source = "./modules/railway"
  
  project_name = "plinto-production"
  services = {
    api = {
      source = "../../apps/api"
      healthcheck = "/health"
      replicas = 2
    }
  }
  
  databases = {
    postgres = { version = "15" }
    redis = { version = "7" }
  }
}

module "frontend" {
  source = "./modules/vercel"
  
  projects = {
    admin = { path = "../../apps/admin" }
    docs = { path = "../../apps/docs" }
  }
}

module "edge" {
  source = "./modules/cloudflare"
  
  domain = "plinto.dev"
  workers = {
    verify = { source = "../../apps/edge-verify" }
  }
}
```

### Docker Compose for Development

```yaml
# docker-compose.yml
version: '3.9'

services:
  api:
    build: ./apps/api
    ports: ["8000:8000"]
    environment:
      DATABASE_URL: postgresql://postgres:postgres@db:5432/plinto
      REDIS_URL: redis://redis:6379
    depends_on: [db, redis]
    volumes:
      - ./apps/api:/app
    command: uvicorn main:app --reload --host 0.0.0.0

  admin:
    build: ./apps/admin
    ports: ["3000:3000"]
    environment:
      NEXT_PUBLIC_API_URL: http://localhost:8000
    volumes:
      - ./apps/admin:/app
      - /app/node_modules
    command: npm run dev

  db:
    image: postgres:15-alpine
    environment:
      POSTGRES_PASSWORD: postgres
      POSTGRES_DB: plinto
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./infrastructure/postgres:/docker-entrypoint-initdb.d

  redis:
    image: redis:7-alpine
    command: redis-server --appendonly yes
    volumes:
      - redis_data:/data

volumes:
  postgres_data:
  redis_data:
```

---

## Week 5-6: WebAuthn Implementation

### Passkey Registration

```python
# apps/api/auth/passkeys.py
from webauthn import generate_registration_options, verify_registration_response

class PasskeyManager:
    async def begin_registration(self, identity_id: str) -> dict:
        identity = await self.get_identity(identity_id)
        
        options = generate_registration_options(
            rp_id="plinto.dev",
            rp_name="Plinto",
            user_id=identity_id.bytes,
            user_name=identity.email,
            user_display_name=identity.profile.get("name", identity.email),
            exclude_credentials=await self.get_existing_credentials(identity_id)
        )
        
        # Store challenge in Redis
        await self.redis.setex(
            f"passkey:challenge:{identity_id}",
            300,  # 5 minutes
            options.challenge
        )
        
        return options
    
    async def complete_registration(self, identity_id: str, credential: dict) -> Passkey:
        challenge = await self.redis.get(f"passkey:challenge:{identity_id}")
        
        verification = verify_registration_response(
            credential=credential,
            expected_challenge=challenge,
            expected_origin="https://plinto.dev",
            expected_rp_id="plinto.dev"
        )
        
        if verification.verified:
            return await self.save_passkey(identity_id, verification)
        
        raise ValueError("Invalid registration")
```

### Frontend Integration

```typescript
// apps/admin/components/PasskeyRegistration.tsx
import { startRegistration } from '@simplewebauthn/browser';

export function PasskeyRegistration() {
  const handleRegister = async () => {
    // Get options from server
    const options = await fetch('/api/v1/passkeys/registration/begin', {
      method: 'POST',
      credentials: 'include'
    }).then(r => r.json());
    
    // Start WebAuthn ceremony
    const credential = await startRegistration(options);
    
    // Complete registration
    await fetch('/api/v1/passkeys/registration/complete', {
      method: 'POST',
      body: JSON.stringify(credential),
      credentials: 'include'
    });
  };
  
  return (
    <button onClick={handleRegister}>
      Add Passkey
    </button>
  );
}
```

---

## Week 7-8: Organizations & RBAC

### Organization Management

```python
# apps/api/organizations/service.py
class OrganizationService:
    async def create_organization(
        self, 
        creator_id: str, 
        data: CreateOrgData
    ) -> Organization:
        async with self.db.transaction():
            # Create organization
            org = await self.db.fetchrow("""
                INSERT INTO organizations (tenant_id, name, slug)
                VALUES ($1, $2, $3)
                RETURNING *
            """, tenant_id, data.name, data.slug)
            
            # Add creator as owner
            await self.db.execute("""
                INSERT INTO organization_members 
                (organization_id, identity_id, role)
                VALUES ($1, $2, 'owner')
            """, org['id'], creator_id)
            
            # Create audit event
            await self.audit.log(
                event_type="organization.created",
                actor_id=creator_id,
                target_id=org['id']
            )
            
            return Organization(**org)
```

### Policy Evaluation

```python
# apps/api/policies/evaluator.py
from opa_client import OpaClient

class PolicyEvaluator:
    def __init__(self):
        self.opa = OpaClient()
    
    async def evaluate(
        self,
        subject: str,
        action: str,
        resource: str,
        context: dict = None
    ) -> PolicyDecision:
        # Get applicable policies
        policies = await self.get_policies(subject, resource)
        
        # Build input
        input_data = {
            "subject": subject,
            "action": action,
            "resource": resource,
            "context": context or {},
            "policies": policies
        }
        
        # Evaluate with OPA
        result = await self.opa.evaluate(input_data)
        
        return PolicyDecision(
            allowed=result.get("allow", False),
            reasons=result.get("reasons", [])
        )
```

---

## Week 9-10: Enterprise Features

### SAML Integration

```python
# apps/api/sso/saml.py
from onelogin.saml2.auth import OneLogin_Saml2_Auth

class SAMLProvider:
    async def initiate_sso(self, org_id: str) -> str:
        config = await self.get_saml_config(org_id)
        auth = OneLogin_Saml2_Auth(request, config)
        return auth.login()
    
    async def handle_callback(self, request) -> Identity:
        auth = OneLogin_Saml2_Auth(request, config)
        auth.process_response()
        
        if auth.is_authenticated():
            attributes = auth.get_attributes()
            return await self.find_or_create_identity(attributes)
        
        raise AuthenticationError(auth.get_last_error_reason())
```

### SCIM Server

```python
# apps/api/scim/server.py
from fastapi import APIRouter

scim_router = APIRouter(prefix="/scim/v2")

@scim_router.get("/Users")
async def list_users(
    startIndex: int = 1,
    count: int = 100,
    filter: str = None
):
    users = await fetch_users(filter, startIndex, count)
    return {
        "schemas": ["urn:ietf:params:scim:api:messages:2.0:ListResponse"],
        "totalResults": len(users),
        "Resources": users
    }

@scim_router.post("/Users")
async def create_user(user: SCIMUser):
    identity = await create_identity_from_scim(user)
    return scim_user_response(identity)
```

---

## Week 11-12: Production Readiness

### Monitoring & Observability

```python
# apps/api/monitoring.py
from opentelemetry import trace, metrics
from prometheus_client import Counter, Histogram

# Metrics
auth_requests = Counter('plinto_auth_requests_total', 'Total auth requests')
auth_latency = Histogram('plinto_auth_latency_seconds', 'Auth latency')
session_duration = Histogram('plinto_session_duration_seconds', 'Session duration')

# Tracing
tracer = trace.get_tracer(__name__)

@auth_latency.time()
async def authenticate(credentials):
    with tracer.start_as_current_span("authenticate") as span:
        span.set_attribute("auth.method", credentials.method)
        
        result = await perform_authentication(credentials)
        
        auth_requests.inc()
        span.set_attribute("auth.success", result.success)
        
        return result
```

### Load Testing

```javascript
// tests/load/k6-script.js
import http from 'k6/http';
import { check } from 'k6';

export let options = {
  stages: [
    { duration: '2m', target: 100 },
    { duration: '5m', target: 100 },
    { duration: '2m', target: 200 },
    { duration: '5m', target: 200 },
    { duration: '2m', target: 0 },
  ],
};

export default function() {
  // Create identity
  let createRes = http.post('https://plinto.dev/api/v1/identities', {
    email: `test${Date.now()}@example.com`,
    password: 'Test123!@#'
  });
  
  check(createRes, {
    'identity created': (r) => r.status === 201,
    'response time < 200ms': (r) => r.timings.duration < 200,
  });
  
  // Create session
  let sessionRes = http.post('https://plinto.dev/api/v1/sessions', {
    email: email,
    password: 'Test123!@#'
  });
  
  check(sessionRes, {
    'session created': (r) => r.status === 201,
    'has access token': (r) => r.json('accessToken') !== '',
  });
}
```

### Security Hardening

```python
# apps/api/security.py
from slowapi import Limiter
from slowapi.util import get_remote_address

# Rate limiting
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["100 per minute"]
)

@app.post("/api/v1/sessions")
@limiter.limit("10 per minute")
async def create_session(request: Request, data: CreateSessionRequest):
    # Check for suspicious activity
    if await is_suspicious(request):
        await trigger_captcha(request)
    
    # Validate credentials
    return await authenticate(data)

# Input validation
from pydantic import BaseModel, EmailStr, SecretStr

class CreateIdentityRequest(BaseModel):
    email: EmailStr
    password: SecretStr
    
    @validator('password')
    def validate_password(cls, v):
        if len(v.get_secret_value()) < 12:
            raise ValueError('Password too short')
        return v
```

---

## Deployment Checklist

### Pre-Production

- [ ] All tests passing (unit, integration, e2e)
- [ ] Security scan clean (SAST, DAST)
- [ ] Performance benchmarks met
- [ ] Documentation complete
- [ ] Runbooks written
- [ ] Monitoring configured
- [ ] Backups tested
- [ ] Disaster recovery plan

### Production Deployment

```bash
# 1. Database migrations
railway run --service postgres "psql < migrations/latest.sql"

# 2. Deploy backend
railway up --service api

# 3. Deploy edge workers
wrangler publish --env production

# 4. Deploy frontend
vercel --prod

# 5. Smoke tests
npm run test:production

# 6. Monitor
open https://plinto.dev/admin/monitoring
```

---

## Team Responsibilities

### Backend Team (2 engineers)
- Core API development
- Database design and optimization
- Authentication flows
- Policy engine

### Frontend Team (2 engineers)  
- Admin dashboard
- SDK development
- Documentation site
- UI components

### Infrastructure (1 engineer)
- CI/CD pipelines
- Monitoring and alerting
- Security hardening
- Performance optimization

### Product (1 engineer)
- Integration testing
- Documentation
- Customer onboarding
- Feedback loops

---

## Success Metrics

### Week 2
- [ ] Basic auth working end-to-end
- [ ] JWT verification < 100ms
- [ ] Docker compose running locally

### Week 4
- [ ] Deployed to staging
- [ ] 100 concurrent users stable
- [ ] All endpoints documented

### Week 8  
- [ ] Passkeys working
- [ ] Organizations implemented
- [ ] Forge Sight integrated

### Week 12
- [ ] Production ready
- [ ] SLAs met (99.95% uptime)
- [ ] Load tested to 10k RPS

This implementation guide provides a clear path from zero to production-ready platform in 12 weeks.