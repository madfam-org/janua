# MADFAM DevOps Deployment Procedures

## Core Principle

**Never directly manipulate production systems.** All changes must flow through the proper DevOps pipeline:

```
Local Dev → Git Commit → Build Image → Push to Registry → Deploy via Enclii
```

Direct database manipulation, kubectl exec, or env var injection should ONLY be used for:
- Critical security incidents requiring immediate response
- Data recovery from catastrophic failures
- One-time migration fixes that cannot be automated

## Standard Deployment Flow

### 1. Local Development
```bash
# Make code changes locally
# Test on localhost ports (4100-4199 for Janua, 4200-4299 for Enclii)
# Verify functionality works as expected
```

### 2. Git Commit
```bash
git add -A
git commit -m "feat(component): description

🤖 Generated with Claude Code"
git push origin main
```

### 3. Build Container Images
```bash
# For Janua API
cd apps/api
docker build -t ghcr.io/madfam-io/janua-api:v0.1.x .

# For frontend apps
cd apps/dashboard
docker build -t ghcr.io/madfam-io/janua-dashboard:v0.1.x .
```

### 4. Push to Registry
```bash
docker push ghcr.io/madfam-io/janua-api:v0.1.x
docker push ghcr.io/madfam-io/janua-dashboard:v0.1.x
```

### 5. Deploy via Enclii
```bash
# Update Enclii service spec with new image tag
# OR use Enclii CLI when available
enclii deploy --service janua-api --tag v0.1.x
```

## Secrets Management

### Environment Variables
- **NEVER** set secrets via `kubectl set env` directly
- Use Kubernetes Secrets managed via Enclii
- Store in `infra/k8s/secrets/` (gitignored, encrypted at rest)

### Admin Bootstrap Password
```yaml
# infra/k8s/secrets/janua-secrets.yaml (encrypted)
apiVersion: v1
kind: Secret
metadata:
  name: janua-admin-bootstrap
  namespace: janua
type: Opaque
stringData:
  ADMIN_BOOTSTRAP_PASSWORD: "secure-password-here"
```

### Applying Secrets
```bash
# Apply via Enclii or kubectl with proper RBAC
kubectl apply -f infra/k8s/secrets/janua-secrets.yaml
```

## Database Migrations

### Proper Approach
1. Migrations are part of the codebase (`apps/api/alembic/versions/`)
2. Run on API startup via `alembic upgrade head`
3. New migrations added via `alembic revision --autogenerate`
4. Tested locally before deployment

### Migration Recovery (Emergency Only)
If migration state is corrupted:
1. Document the issue
2. Create a one-time fix script in `scripts/migrations/`
3. Apply via kubectl exec (emergency)
4. Document in post-incident report

## Port Allocation

| Service | Local Port | Prod Domain |
|---------|------------|-------------|
| Janua API | 4100 | api.janua.dev |
| Janua Dashboard | 4101 | app.janua.dev |
| Janua Admin | 4102 | admin.janua.dev |
| Janua Docs | 4103 | docs.janua.dev |
| Janua Website | 4104 | janua.dev |
| Enclii API | 4200 | api.enclii.dev |

## Incident Response

When direct manipulation is required:
1. **Document** the emergency in `claudedocs/incidents/`
2. **Execute** minimal necessary changes
3. **Create** proper fix in codebase
4. **Deploy** fix through standard pipeline
5. **Write** post-incident report

## Related Files
- `dogfooding/*.yaml` - Enclii service specs
- `infra/terraform/` - Infrastructure as Code
- `scripts/deploy-production.sh` - Deployment automation
- `.github/workflows/` - CI/CD pipelines
