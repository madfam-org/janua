# Production Monitoring Setup Guide

This guide helps you set up free monitoring services for Plinto's alpha launch.

## 1. Uptime Monitoring (UptimeRobot - Free)

### Setup Steps:
1. **Create Account**: Go to https://uptimerobot.com and sign up (free)
2. **Add Monitors** for each domain:

```
Monitor 1: API Health
- Monitor Type: HTTP(s)
- Friendly Name: Plinto API
- URL: https://api.plinto.dev/health
- Monitoring Interval: 5 minutes

Monitor 2: Main App
- Monitor Type: HTTP(s)
- Friendly Name: Plinto App
- URL: https://app.plinto.dev
- Monitoring Interval: 5 minutes

Monitor 3: Marketing Site
- Monitor Type: HTTP(s)
- Friendly Name: Plinto Website
- URL: https://www.plinto.dev
- Monitoring Interval: 5 minutes

Monitor 4: Documentation
- Monitor Type: HTTP(s)
- Friendly Name: Plinto Docs
- URL: https://docs.plinto.dev
- Monitoring Interval: 5 minutes
```

### Alert Configuration:
- Add your email for instant notifications
- Optional: Add Slack webhook for team notifications
- Set up SMS alerts (free tier includes 20 SMS/month)

## 2. Error Tracking (Sentry - Free Tier)

### Setup Steps:
1. **Create Account**: Go to https://sentry.io and sign up
2. **Create Project**:
   - Platform: Python (FastAPI)
   - Project Name: plinto-api
3. **Get DSN**: Copy your DSN from project settings
4. **Add to Environment**:

```bash
# Add to Railway environment variables
SENTRY_DSN=https://YOUR_KEY@sentry.io/YOUR_PROJECT_ID
```

### Already Configured in Code:
- FastAPI integration ✅
- SQLAlchemy integration ✅
- Error filtering by environment ✅
- PII protection enabled ✅

## 3. Status Page (Free Options)

### Option A: GitHub Pages (Recommended)
Create a simple status page using GitHub Pages:

```html
<!-- Create repo: plinto-status -->
<!DOCTYPE html>
<html>
<head>
    <title>Plinto Status</title>
    <meta http-equiv="refresh" content="60">
</head>
<body>
    <h1>Plinto Platform Status</h1>
    <div id="status"></div>
    <script>
        // Check API health
        fetch('https://api.plinto.dev/health')
            .then(r => r.json())
            .then(data => {
                document.getElementById('status').innerHTML = 
                    '<p>✅ All Systems Operational</p>';
            })
            .catch(err => {
                document.getElementById('status').innerHTML = 
                    '<p>🔴 Experiencing Issues</p>';
            });
    </script>
</body>
</html>
```

### Option B: Statuspage.io (Free Tier)
- Sign up at https://www.atlassian.com/software/statuspage
- Free for 1 page, unlimited subscribers

## 4. Performance Monitoring (Free Tier)

### Google PageSpeed Insights
Monitor frontend performance:
```bash
# Check weekly
https://pagespeed.web.dev/?url=https://www.plinto.dev
https://pagespeed.web.dev/?url=https://app.plinto.dev
```

### GTmetrix (Free Tier)
- Sign up at https://gtmetrix.com
- Monitor up to 3 URLs daily

## 5. Simple Health Check Script

Create a local monitoring script:

```bash
#!/bin/bash
# scripts/monitor-production.sh

echo "🔍 Checking Plinto Production Status..."

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m'

# Check each service
check_service() {
    local name=$1
    local url=$2
    
    if curl -s -f -o /dev/null "$url"; then
        echo -e "${GREEN}✅ $name is UP${NC}"
    else
        echo -e "${RED}❌ $name is DOWN${NC}"
        # Send alert (example using curl to webhook)
        # curl -X POST your-webhook-url -d "Service $name is down"
    fi
}

# Check all services
check_service "API Health" "https://api.plinto.dev/health"
check_service "Main App" "https://app.plinto.dev"
check_service "Marketing" "https://www.plinto.dev"
check_service "Documentation" "https://docs.plinto.dev"
check_service "Admin Panel" "https://admin.plinto.dev"
check_service "Demo App" "https://demo.plinto.dev"

# Check API response time
response_time=$(curl -o /dev/null -s -w '%{time_total}' https://api.plinto.dev/health)
echo "API Response Time: ${response_time}s"

# Run every 5 minutes via cron
# */5 * * * * /path/to/monitor-production.sh
```

## 6. Railway Platform Monitoring

Railway provides built-in monitoring:

1. **Metrics Dashboard**: 
   - Go to Railway dashboard → Your project → Metrics
   - Monitor CPU, Memory, Network

2. **Logs**:
   - Real-time logs in Railway dashboard
   - Set up log drains to external services

3. **Alerts**:
   - Configure webhook alerts for deployments
   - Set resource usage alerts

## 7. Browser Monitoring (Free)

### Chrome UX Report
Monitor real user metrics:
```javascript
// Add to frontend apps
if ('connection' in navigator) {
    // Log connection quality
    console.log('Connection:', navigator.connection.effectiveType);
}

// Web Vitals monitoring
import {getCLS, getFID, getLCP} from 'web-vitals';

getCLS(console.log);
getFID(console.log);
getLCP(console.log);
```

## 8. Quick Setup Checklist

### Immediate (15 minutes):
- [ ] Sign up for UptimeRobot
- [ ] Add all 6 domain monitors
- [ ] Configure email alerts
- [ ] Test alerts work

### Within 1 Hour:
- [ ] Sign up for Sentry
- [ ] Add SENTRY_DSN to Railway env vars
- [ ] Deploy and verify error tracking works
- [ ] Create simple status page

### Daily Checks:
- [ ] Review uptime reports
- [ ] Check Sentry for new errors
- [ ] Monitor Railway metrics
- [ ] Review response times

## 9. Alert Response Plan

### When Downtime Alert Received:
1. Check Railway logs immediately
2. Check health endpoint manually
3. Review recent deployments
4. Rollback if needed: `git revert HEAD && git push`
5. Communicate on status page

### When Error Spike in Sentry:
1. Identify error pattern
2. Check if it's affecting users
3. Deploy hotfix if critical
4. Schedule fix if non-critical

## 10. Alpha Launch Monitoring

### Key Metrics to Track:
- **Uptime Target**: >99% (allows 7 hours downtime/month)
- **Response Time**: <500ms p95
- **Error Rate**: <1%
- **Daily Active Users**: Track growth
- **Successful Signups**: Monitor conversion

### Daily Report Template:
```
Date: [DATE]
Uptime: [X]%
Avg Response Time: [X]ms
Errors: [X]
New Users: [X]
Active Users: [X]
Issues: [List any problems]
Actions: [What was fixed]
```

---

## Required Environment Variables

Add these to Railway:

```bash
# Error Tracking (get from Sentry)
SENTRY_DSN=https://your-key@sentry.io/project-id

# Optional: Webhook for alerts
ALERT_WEBHOOK_URL=https://hooks.slack.com/services/YOUR/WEBHOOK/URL

# Optional: Status page
STATUS_PAGE_URL=https://status.plinto.dev
```

## Verification

After setup, verify monitoring works:

```bash
# 1. Trigger a test error
curl -X POST https://api.plinto.dev/test-error

# 2. Check Sentry received it
# Go to Sentry dashboard

# 3. Stop a service temporarily
# Check UptimeRobot sends alert

# 4. Check metrics
curl https://api.plinto.dev/metrics
```

---

**For Alpha Launch**: UptimeRobot + Sentry is sufficient. Add more advanced monitoring as you scale.