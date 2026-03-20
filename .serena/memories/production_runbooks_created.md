# Production Runbooks Created

**Date**: 2025-12-06
**Location**: `/Users/aldoruizluna/labspace/solarpunk-foundry/docs/runbooks/`

## Runbooks Created

1. **README.md** - Index and quick reference
2. **incident-response.md** - SEV1/2/3 handling, common issues
3. **backup-restore.md** - PostgreSQL, Redis, ZFS, secrets
4. **rollback.md** - K8s and Docker rollback procedures
5. **scaling.md** - Horizontal/vertical scaling, HPA
6. **certificates.md** - SSL/TLS management (Cloudflare + internal)

## Also Deployed

- `/opt/solarpunk/scripts/build-and-tag.sh` - Image versioning with git SHA

## Access Commands

All runbooks use SSH via Cloudflare tunnel:
```bash
ssh ssh.madfam.io
```

## Key Paths Referenced

- `/opt/solarpunk/janua` - Janua repo
- `/opt/solarpunk/enclii` - Enclii repo
- `/opt/solarpunk/scripts` - Operational scripts
- `/opt/solarpunk/secrets` - Sensitive configuration
- `/tank/backups` - ZFS backup destination
