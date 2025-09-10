# Incident Response Playbook - Plinto Platform

**Last Updated:** 2025-09-10  
**Version:** 1.0  
**Owner:** Platform Team

## Quick Reference

### Severity Levels

| Level | Response Time | Examples | Escalation |
|-------|--------------|----------|------------|
| **P0 - Critical** | 15 min | Complete outage, data breach, security compromise | Immediate all-hands |
| **P1 - High** | 30 min | Auth system down, >50% users affected | Engineering lead + CTO |
| **P2 - Medium** | 2 hours | Partial outage, <50% users affected | Engineering lead |
| **P3 - Low** | 24 hours | Minor bugs, performance degradation | On-call engineer |

### Emergency Contacts

```yaml
on_call_primary: "+1-XXX-XXX-XXXX"
on_call_secondary: "+1-XXX-XXX-XXXX"
security_team: "security@plinto.dev"
cto_emergency: "+1-XXX-XXX-XXXX"
status_page: "https://status.plinto.dev"
war_room_link: "https://meet.google.com/plinto-incident"
```

## Phase 1: Detection & Triage (0-15 minutes)

### 1.1 Incident Detection Sources
- [ ] Monitoring alerts (DataDog/Sentry)
- [ ] User reports via support
- [ ] Health check failures
- [ ] Security scanner alerts
- [ ] Manual discovery

### 1.2 Initial Assessment Checklist
```bash
# Quick status check
curl -I https://api.plinto.dev/health
curl -I https://app.plinto.dev

# Check recent deployments
gh run list --limit 5

# Check error rates
# In Sentry/DataDog dashboard

# Check current traffic
# In Cloudflare/CDN dashboard
```

### 1.3 Severity Classification

**P0 - Critical (Complete Outage/Security Breach)**
- [ ] Authentication system completely down
- [ ] Database corruption or loss
- [ ] Security breach detected
- [ ] Customer data exposed
- [ ] Complete API unavailability

**P1 - High (Major Functionality Broken)**
- [ ] Login/Registration broken
- [ ] >50% of API endpoints failing
- [ ] Database performance critical
- [ ] Payment processing down

**P2 - Medium (Partial Outage)**
- [ ] Some API endpoints slow/failing
- [ ] Dashboard partially unavailable
- [ ] Email notifications not sending
- [ ] Minor data inconsistencies

**P3 - Low (Minor Issues)**
- [ ] UI glitches
- [ ] Non-critical features broken
- [ ] Documentation issues
- [ ] Performance degradation <20%

## Phase 2: Immediate Response (15-30 minutes)

### 2.1 Incident Commander Responsibilities
1. **Declare incident** in #incidents Slack channel
2. **Create war room** if P0/P1
3. **Assign roles:**
   - Technical Lead
   - Communications Lead
   - Customer Support Lead
   - Scribe (document timeline)

### 2.2 Communication Templates

**Initial Notification (Internal)**
```
🚨 INCIDENT DECLARED 🚨
Severity: P[0-3]
Issue: [Brief description]
Impact: [User impact]
Status: Investigating
War Room: [Link if applicable]
Incident Commander: @[name]
```

**Status Page Update (External)**
```
We are currently investigating reports of [issue description].
Impact: [Specific services affected]
Status: Investigating
Next Update: [Time, max 30 minutes]
```

### 2.3 Quick Mitigation Actions

**For Service Outages:**
```bash
# 1. Check deployment status
cd apps/api
git log --oneline -10

# 2. Rollback if recent deployment
git revert HEAD
git push origin main --force-with-lease

# 3. Scale up if load issue
# Via Railway/Vercel dashboard

# 4. Restart services
# Via platform dashboard
```

**For Database Issues:**
```bash
# 1. Check connection pool
psql $DATABASE_URL -c "SELECT count(*) FROM pg_stat_activity;"

# 2. Kill long-running queries
psql $DATABASE_URL -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE query_time > interval '5 minutes';"

# 3. Emergency backup
pg_dump $DATABASE_URL > emergency_backup_$(date +%s).sql
```

**For Security Incidents:**
```bash
# 1. Rotate secrets immediately
python scripts/rotate_secrets.py --emergency

# 2. Revoke all sessions
redis-cli FLUSHDB

# 3. Enable emergency mode
export EMERGENCY_MODE=true
# This disables non-essential features
```

## Phase 3: Investigation & Diagnosis (30-60 minutes)

### 3.1 Investigation Checklist

**Application Layer:**
- [ ] Check application logs
- [ ] Review error tracking (Sentry)
- [ ] Check recent code changes
- [ ] Review deployment history
- [ ] Check feature flags

```bash
# View recent logs
heroku logs --tail -a plinto-api  # or platform equivalent

# Check for errors
grep -i error /var/log/plinto/*.log | tail -100

# Recent deployments
git log --since="2 hours ago" --oneline
```

**Infrastructure Layer:**
- [ ] Server health (CPU, Memory, Disk)
- [ ] Network connectivity
- [ ] Database performance
- [ ] Cache hit rates
- [ ] CDN status

```bash
# Database diagnostics
psql $DATABASE_URL << EOF
SELECT query, calls, mean_time, max_time 
FROM pg_stat_statements 
ORDER BY mean_time DESC 
LIMIT 10;
EOF

# Redis diagnostics
redis-cli INFO stats
redis-cli SLOWLOG GET 10
```

**Security Layer:**
- [ ] Check for unusual traffic patterns
- [ ] Review authentication logs
- [ ] Check for failed login attempts
- [ ] Review API rate limits
- [ ] Check WAF logs

### 3.2 Root Cause Analysis Questions
1. What changed recently? (code, config, infrastructure)
2. Is this affecting all users or subset?
3. Is this reproducible?
4. What do the metrics show?
5. Are there any patterns in the errors?

## Phase 4: Resolution & Recovery (60+ minutes)

### 4.1 Resolution Strategies

**Code Issues:**
1. Identify problematic commit
2. Create hotfix branch
3. Apply fix
4. Fast-track testing
5. Deploy with monitoring

**Database Issues:**
1. Identify problematic queries
2. Add indexes if needed
3. Optimize queries
4. Consider read replicas
5. Scale vertically if needed

**Infrastructure Issues:**
1. Scale horizontally
2. Increase resource limits
3. Clear caches
4. Restart services
5. Failover to backup region

### 4.2 Validation Checklist
- [ ] Primary functionality restored
- [ ] Error rates back to normal
- [ ] Performance metrics acceptable
- [ ] No data corruption
- [ ] Security posture verified

### 4.3 Recovery Verification
```bash
# Comprehensive health check
bash scripts/production-readiness-check.sh

# API functionality test
curl -X POST https://api.plinto.dev/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"test@test.com","password":"test"}'

# Check error rates
# Should see declining trend in monitoring

# Verify customer impact
# Check support tickets
```

## Phase 5: Post-Incident (Next 24-48 hours)

### 5.1 Immediate Actions
- [ ] Final status page update
- [ ] Customer communication
- [ ] Internal announcement
- [ ] Document timeline
- [ ] Backup verification

### 5.2 Post-Mortem Template

```markdown
# Incident Post-Mortem: [YYYY-MM-DD]

## Summary
- **Duration:** [Start time - End time]
- **Severity:** P[0-3]
- **Impact:** [Number of users, services affected]
- **Root Cause:** [Brief description]

## Timeline
- HH:MM - Event description
- HH:MM - Event description

## What Went Well
- Item 1
- Item 2

## What Went Wrong
- Item 1
- Item 2

## Root Cause Analysis
[Detailed explanation using 5 Whys]

## Action Items
- [ ] Action 1 - Owner - Due date
- [ ] Action 2 - Owner - Due date

## Lessons Learned
- Lesson 1
- Lesson 2
```

### 5.3 Follow-up Actions
1. **Within 24 hours:**
   - Send post-mortem to stakeholders
   - Update runbooks with learnings
   - Create tickets for action items

2. **Within 48 hours:**
   - Conduct blameless post-mortem meeting
   - Update monitoring based on gaps
   - Review and update this playbook

3. **Within 1 week:**
   - Implement critical fixes
   - Update documentation
   - Share learnings with team

## Specific Scenario Playbooks

### Scenario 1: Complete API Outage

```bash
#!/bin/bash
# Emergency API recovery script

echo "🚨 Starting emergency API recovery..."

# 1. Check if API is responding
if ! curl -f https://api.plinto.dev/health; then
    echo "API is down, proceeding with recovery..."
    
    # 2. Check recent deployments
    LAST_COMMIT=$(git rev-parse HEAD)
    echo "Current commit: $LAST_COMMIT"
    
    # 3. Rollback to last known good
    git revert HEAD --no-edit
    git push origin main
    
    # 4. Restart services
    # Platform specific commands
    
    # 5. Verify recovery
    sleep 30
    curl -I https://api.plinto.dev/health
fi
```

### Scenario 2: Database Connection Pool Exhausted

```sql
-- Emergency database recovery
-- Run these in order

-- 1. Check current connections
SELECT count(*) as connection_count,
       state,
       usename
FROM pg_stat_activity
GROUP BY state, usename;

-- 2. Kill idle connections
SELECT pg_terminate_backend(pid)
FROM pg_stat_activity
WHERE state = 'idle'
  AND state_change < current_timestamp - interval '10 minutes';

-- 3. Kill long queries
SELECT pg_terminate_backend(pid)
FROM pg_stat_activity
WHERE state != 'idle'
  AND query_start < current_timestamp - interval '5 minutes';

-- 4. Reset connection pool
ALTER SYSTEM SET max_connections = 200;
SELECT pg_reload_conf();
```

### Scenario 3: Redis Memory Full

```bash
#!/bin/bash
# Redis emergency cleanup

# 1. Check memory usage
redis-cli INFO memory

# 2. Clear non-essential caches
redis-cli --scan --pattern "cache:*" | xargs redis-cli DEL

# 3. Clear old sessions (older than 7 days)
redis-cli --scan --pattern "session:*" | while read key; do
    TTL=$(redis-cli TTL "$key")
    if [ "$TTL" -lt 604800 ]; then
        redis-cli DEL "$key"
    fi
done

# 4. Set memory policy
redis-cli CONFIG SET maxmemory-policy allkeys-lru
```

### Scenario 4: Security Breach Response

```bash
#!/bin/bash
# Security breach emergency response

echo "🔒 SECURITY BREACH RESPONSE INITIATED"

# 1. Enable maintenance mode
export MAINTENANCE_MODE=true
echo "Site is now in maintenance mode"

# 2. Rotate all secrets
echo "Rotating all secrets..."
# Update all JWT keys
openssl rand -hex 32 > /tmp/new_jwt_secret
# Update database passwords
# Update API keys

# 3. Invalidate all sessions
redis-cli FLUSHDB
echo "All user sessions invalidated"

# 4. Audit recent access
psql $DATABASE_URL << EOF
SELECT user_id, ip_address, user_agent, created_at
FROM audit_logs
WHERE created_at > NOW() - INTERVAL '24 hours'
ORDER BY created_at DESC;
EOF

# 5. Notify security team
curl -X POST $SECURITY_WEBHOOK \
  -H "Content-Type: application/json" \
  -d '{"alert": "Security breach detected and contained"}'
```

## Tools & Resources

### Monitoring Dashboards
- **Application Metrics:** https://app.datadog.com/dashboard/plinto
- **Error Tracking:** https://sentry.io/organizations/plinto
- **Infrastructure:** https://dashboard.railway.app
- **CDN/WAF:** https://dash.cloudflare.com
- **Status Page:** https://status.plinto.dev

### Useful Commands

```bash
# Quick health check
curl -s https://api.plinto.dev/health | jq .

# Check recent errors
heroku logs --app plinto-api --tail | grep ERROR

# Database connection check
psql $DATABASE_URL -c "SELECT 1"

# Redis connection check
redis-cli ping

# View current deployment
git rev-parse HEAD

# Emergency rollback
git revert HEAD --no-edit && git push

# Clear all caches
redis-cli FLUSHALL

# Restart all services (platform specific)
heroku restart --app plinto-api
```

### Communication Channels
- **Incidents:** #incidents (Slack)
- **War Room:** https://meet.google.com/plinto-incident
- **Status Updates:** https://status.plinto.dev
- **Customer Support:** support@plinto.dev
- **Security Issues:** security@plinto.dev

## Training & Drills

### Monthly Incident Drills
- **Week 1:** Tabletop exercise (P0 scenario)
- **Week 2:** Runbook review and updates
- **Week 3:** Monitoring and alerting review
- **Week 4:** Post-mortem review session

### Required Training
- All engineers must complete incident commander training
- All team members must know how to declare an incident
- Customer support must know escalation procedures
- Leadership must understand communication protocols

---

**Remember:** 
- Stay calm and methodical
- Communicate frequently
- Document everything
- Focus on mitigation first, root cause second
- Blameless post-mortems only

**This playbook is a living document. Update it after every incident.**