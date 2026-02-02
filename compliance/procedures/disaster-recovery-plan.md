# Janua Disaster Recovery Plan

**Document Owner**: Platform Engineering
**Last Reviewed**: 2026-02-01
**Review Cadence**: Quarterly
**SOC 2 Control**: CF-05 (Availability)

---

## Recovery Objectives

| Metric | Target | Rationale |
|--------|--------|-----------|
| **RTO** (Recovery Time Objective) | < 4 hours | Restore full service within 4h of declared incident |
| **RPO** (Recovery Point Objective) | < 1 hour | Automated backups run daily; WAL archiving provides point-in-time recovery |

---

## Scope

This plan covers recovery of:
1. PostgreSQL database (primary data store)
2. Redis (sessions, cache, rate limiting)
3. Janua API service (K8s deployment)
4. DNS / Cloudflare Tunnel routing
5. Cryptographic key material (JWT signing keys, field encryption keys)

---

## Recovery Procedures

### 1. Database (PostgreSQL)

**Failure scenario**: Data corruption, accidental deletion, host failure.

1. Identify the most recent verified backup from S3 (`s3://$BACKUP_S3_BUCKET/backups/`)
2. Provision a new PostgreSQL instance (or restore the existing host)
3. Restore from backup:
   ```bash
   pg_restore -h $DB_HOST -U $DB_USER -d janua --clean --if-exists backup_file.sql.gz
   ```
4. Apply any WAL segments for point-in-time recovery (if WAL archiving is enabled)
5. Verify data integrity: row counts, recent audit log entries, user login test
6. Update `DATABASE_URL` in K8s secrets if host changed
7. Restart API pods: `kubectl rollout restart deployment/janua-api -n janua`

### 2. Redis

**Failure scenario**: Node failure, data eviction, connection loss.

1. Redis data is ephemeral (sessions, cache). Recovery = restart.
2. Deploy new Redis instance or restart existing: `kubectl rollout restart deployment/redis -n janua`
3. Active sessions will be invalidated — users must re-authenticate (acceptable).
4. Rate limit counters reset automatically.

### 3. API Service

**Failure scenario**: Pod crash loop, bad deployment, OOM.

1. Check pod status: `kubectl get pods -n janua -l app=janua-api`
2. Review logs: `kubectl logs -n janua -l app=janua-api --tail=100`
3. If bad deployment, rollback: `kubectl rollout undo deployment/janua-api -n janua`
4. If resource issue, scale: `kubectl scale deployment/janua-api -n janua --replicas=3`
5. Verify health: `curl https://api.janua.dev/health/detailed`

### 4. DNS / Cloudflare Tunnel

**Failure scenario**: Tunnel disconnection, DNS propagation issue.

1. Check tunnel status in Cloudflare dashboard
2. Restart cloudflared pod: `kubectl rollout restart deployment/cloudflared -n cloudflare-tunnel`
3. Verify routing: `curl -v https://api.janua.dev/health`
4. If Cloudflare is down (unlikely), update DNS to direct-to-origin as fallback

### 5. Cryptographic Key Material

**Failure scenario**: Key loss, compromise, rotation failure.

1. JWT signing keys are stored in `jwk_keys` database table — recovered with DB restore
2. `FIELD_ENCRYPTION_KEY` is stored in K8s secrets — verify after any infrastructure recovery
3. If key is compromised: rotate immediately, re-encrypt affected fields, revoke all active tokens

---

## Quarterly DR Test Schedule

| Quarter | Test Type | Scope |
|---------|-----------|-------|
| Q1 | Full restore drill | Database backup → restore → verify |
| Q2 | Failover test | Kill API pods, verify auto-recovery |
| Q3 | Full restore drill | Database + Redis + tunnel recovery |
| Q4 | Tabletop exercise | Walk through complete DC failure scenario |

### DR Test Checklist
- [ ] Backup file exists and is recent (< 24h)
- [ ] Backup can be downloaded from S3 within 15 minutes
- [ ] Restore completes without errors
- [ ] User login works after restore
- [ ] Audit log integrity verified (hash chain valid)
- [ ] API health check returns healthy
- [ ] All K8s deployments running expected replica count
- [ ] DR test results documented and filed

---

## Escalation Contacts

| Role | Contact | Escalation Time |
|------|---------|-----------------|
| On-call Engineer | (configure in PagerDuty/OpsGenie) | Immediate |
| Platform Lead | (configure) | 15 minutes |
| CTO / Security | (configure) | 30 minutes |
| External DB Support | (if applicable) | 1 hour |

---

## Document History

| Date | Change | Author |
|------|--------|--------|
| 2026-02-01 | Initial creation (SOC 2 CF-05 remediation) | Platform Engineering |
