# Production Directory Structure - CANONICAL PATHS

## Updated: 2025-12-06

## Canonical Production Paths

All MADFAM repos live under `/opt/solarpunk/`:

```
/opt/solarpunk/
├── enclii/          # Enclii repo
├── janua/           # Janua repo
├── configs/         # Shared configuration files
├── scripts/         # Shared utility scripts
└── secrets/         # Shared secrets (JWT keys, API keys, etc.)
    ├── jwt_private.pem
    ├── jwt_public.pem
    ├── jwt_secret.txt
    ├── encryption_key.txt
    ├── session_secret.txt
    └── webhook_signing_secret.txt
```

## NEVER USE (Removed)

- `/opt/janua/` - **REMOVED** on 2025-12-06 (was orphaned duplication)
  - Backup saved at `/tmp/opt-janua-backup-20251206.tar.gz` before removal

## Docker & Kubernetes

### Docker Compose (docker-compose.prod.yml)
- Location: `/opt/solarpunk/janua/runtime/docker-compose.prod.yml`
- Volume mounts use: `/opt/solarpunk/secrets:/app/keys:ro`

### Kubernetes
- Janua services run in `janua` namespace
- Secrets managed via k8s secrets (not hostPath volumes)
- No references to `/opt/janua`

## Cloudflare Tunnel
- Service: `cloudflared-janua.service`
- Config: `/etc/systemd/system/cloudflared-janua.service`
- Domain: `ssh.madfam.io` → Server SSH access

## Port Allocation (MADFAM Standard)
- API: 4100 (also 8000 legacy)
- Dashboard: 4101
- Admin: 4102
- Docs: 4103
- Website: 4104

## References
- Production deployment uses k8s primarily
- Docker containers run separately for some services
- janua-api docker container mounts `/opt/solarpunk/secrets:/secrets:ro`
