# Secrets Management System - Deployment Guide

> [!IMPORTANT]
> MADFAM-ENCLII-FIRST-LEGACY-RAW v1: This document contains legacy raw infrastructure command examples.
> Routine production operations must use Enclii web, API, or CLI. Treat raw
> `kubectl`, `helm`, SSH, provider CLI/API, `docker exec`, and direct container
> access as platform bootstrap or documented break-glass only, and record any
> missing Enclii adapter gap.


This guide covers deploying and configuring the secrets rotation management system.

## Prerequisites

- [ ] Python 3.x installed (`python3 --version`)
- [ ] kubectl configured with cluster access
- [ ] GitHub repository admin access (for Actions secrets)
- [ ] Slack workspace admin access (for webhook)
- [ ] Grafana admin access
- [ ] Prometheus Operator deployed (for alert rules)

## Step 1: Verify Local Tools

```bash
# Verify pyyaml is installed
python3 -c "import yaml; print('PyYAML:', yaml.__version__)"

# If not installed:
pip install -r scripts/secrets/requirements.txt

# Test the rotation checker
python3 scripts/secrets/check-rotation-schedule.py

# Test the CLI
./scripts/secrets/manage-secrets.sh status
```

## Step 2: Configure Slack Webhook

### 2.1 Create Slack App & Webhook

1. Go to [Slack API Apps](https://api.slack.com/apps)
2. Click **"Create New App"** → **"From scratch"**
3. Name: `MADFAM Secrets Rotation`
4. Select your workspace
5. Click **"Create App"**

### 2.2 Enable Incoming Webhooks

1. In the app settings, go to **"Incoming Webhooks"**
2. Toggle **"Activate Incoming Webhooks"** to ON
3. Click **"Add New Webhook to Workspace"**
4. Select channel: `#security-alerts` or `#infrastructure`
5. Click **"Allow"**
6. Copy the **Webhook URL** (starts with `https://hooks.slack.com/services/...`)

### 2.3 Add to GitHub Secrets

1. Go to your repository → **Settings** → **Secrets and variables** → **Actions**
2. Click **"New repository secret"**
3. Name: `SLACK_WEBHOOK_URL`
4. Value: Paste the webhook URL
5. Click **"Add secret"**

### 2.4 Test Slack Integration

```bash
# Test webhook directly
curl -X POST "YOUR_WEBHOOK_URL" \
  -H 'Content-Type: application/json' \
  -d '{"text": "Test: Secrets rotation system configured!"}'
```

## Step 3: Test Rotation Scripts (Staging First!)

### 3.1 Database Password Rotation (Dry Run)

```bash
# Dry run - shows what would happen without making changes
./scripts/secrets/rotate-db-password.sh --project janua --dry-run

# Expected output:
# [INFO] Project: janua
# [DRY-RUN] Would execute: ALTER USER janua PASSWORD '***';
# [DRY-RUN] Would patch secret 'janua-secrets'
# [DRY-RUN] Would restart: deployment/janua-api
```

### 3.2 JWT Key Rotation (Dry Run)

```bash
./scripts/secrets/rotate-jwt-keys.sh --project janua --dry-run

# Expected output:
# [DRY-RUN] Would generate new keypair
# [DRY-RUN] Would update secret with new keys
# [DRY-RUN] Would restart deployments
```

### 3.3 Full Test in Staging

```bash
# Switch to staging context
kubectl config use-context staging-cluster

# Run actual rotation
./scripts/secrets/rotate-db-password.sh --project janua

# Verify
kubectl get pods -n janua
kubectl logs -n janua -l app=janua-api --since=5m | grep -i "database\|connection"
```

## Step 4: Import Grafana Dashboard

### Option A: Grafana UI Import

1. Log in to Grafana
2. Go to **Dashboards** → **Import**
3. Click **"Upload JSON file"**
4. Select `infra/monitoring/dashboards/secrets-rotation.json`
5. Select the Prometheus data source
6. Click **"Import"**

### Option B: Grafana API Import

```bash
# Set variables
GRAFANA_URL="https://grafana.janua.io"
GRAFANA_API_KEY="YOUR_API_KEY"

# Import dashboard
curl -X POST "$GRAFANA_URL/api/dashboards/db" \
  -H "Authorization: Bearer $GRAFANA_API_KEY" \
  -H "Content-Type: application/json" \
  -d @infra/monitoring/dashboards/secrets-rotation.json
```

### Option C: Grafana Provisioning (GitOps)

If using Grafana provisioning, copy to the dashboards directory:

```bash
# Example for Helm-based Grafana
cp infra/monitoring/dashboards/secrets-rotation.json \
   /path/to/grafana/provisioning/dashboards/
```

### Verify Dashboard

1. Open Grafana
2. Search for "Secrets Rotation Status"
3. Verify panels load (may show "No data" if metrics exporter not deployed)

## Step 5: Deploy Prometheus Alert Rules

### Option A: kubectl Apply

```bash
# Verify Prometheus Operator is installed
kubectl get crd prometheusrules.monitoring.coreos.com

# Deploy alert rules
kubectl apply -f infra/monitoring/alerts/secrets-rotation.yaml -n monitoring

# Verify deployment
kubectl get prometheusrules -n monitoring
kubectl describe prometheusrule secrets-rotation-alerts -n monitoring
```

### Option B: Helm Values (if using kube-prometheus-stack)

```yaml
# values.yaml
additionalPrometheusRulesMap:
  secrets-rotation:
    groups:
      - name: secrets.rotation
        rules:
          # ... copy rules from secrets-rotation.yaml
```

### Option C: ArgoCD/Flux GitOps

Add the alert rules file to your GitOps repository and let it sync.

### Verify Alerts

```bash
# Check Prometheus for the rules
kubectl port-forward -n monitoring svc/prometheus-operated 9090:9090

# Visit http://localhost:9090/rules
# Search for "secrets"
```

## Step 6: Deploy Metrics Exporter (Optional)

The Grafana dashboard and Prometheus alerts expect metrics from a secrets exporter. Create a simple exporter or configure existing monitoring to expose:

```
madfam_secret_days_until_rotation{secret_id="...", project="...", owner="...", policy="...", risk_level="..."}
madfam_secret_rotation_total{secret_id="...", project="...", status="success|failure"}
```

### Quick Metrics Script

Create a CronJob that runs the check script and exposes metrics:

```yaml
# infra/monitoring/secrets-exporter-cronjob.yaml
apiVersion: batch/v1
kind: CronJob
metadata:
  name: secrets-metrics-exporter
  namespace: monitoring
spec:
  schedule: "0 * * * *"  # Every hour
  jobTemplate:
    spec:
      template:
        spec:
          containers:
            - name: exporter
              image: python:3.11-slim
              command:
                - /bin/sh
                - -c
                - |
                  pip install pyyaml prometheus_client
                  python /scripts/export-metrics.py
              volumeMounts:
                - name: scripts
                  mountPath: /scripts
          volumes:
            - name: scripts
              configMap:
                name: secrets-exporter-scripts
          restartPolicy: OnFailure
```

## Step 7: Verify Complete Setup

### Checklist

```bash
# 1. Local tools work
./scripts/secrets/manage-secrets.sh audit

# 2. GitHub Actions workflow syntax is valid
# Go to Actions tab, check for syntax errors

# 3. Trigger workflow manually
gh workflow run secrets-rotation-reminder.yml

# 4. Verify Slack notification received

# 5. Check Grafana dashboard loads
# (May need metrics exporter for full functionality)

# 6. Verify Prometheus alerts are loaded
kubectl get prometheusrules -n monitoring | grep secrets
```

### Expected Audit Output

```
═══ Security Audit ═══

[INFO] Checking registry...
[OK] Registry found
[INFO] Checking rotation status...
[ERROR] 6 secrets are overdue for rotation
[INFO] Checking Kubernetes access...
[OK] Kubernetes cluster accessible
[INFO]   janua namespace: 12 secrets
[INFO]   enclii namespace: 8 secrets
[INFO] Checking runbooks...
[OK]   EMERGENCY_ROTATION.md exists
[OK]   oauth-google-rotation.md exists
[OK]   ghcr-pat-rotation.md exists

Audit complete: 1 issues found
```

## Troubleshooting

### Slack Notifications Not Working

```bash
# Test webhook manually
curl -X POST "$SLACK_WEBHOOK_URL" \
  -H 'Content-Type: application/json' \
  -d '{"text": "Test message"}'

# Check GitHub Actions logs for errors
# Go to Actions → secrets-rotation-reminder → View logs
```

### Grafana Dashboard Shows "No Data"

1. Verify Prometheus data source is configured
2. Check if metrics exporter is running
3. Verify metric names match dashboard queries
4. Check time range (dashboard defaults to 30d)

### Prometheus Alerts Not Firing

```bash
# Check if rules are loaded
kubectl exec -n monitoring prometheus-0 -- promtool check rules /etc/prometheus/rules/

# Check Prometheus logs
kubectl logs -n monitoring prometheus-0 | grep -i "secret"

# Verify metrics exist
kubectl port-forward -n monitoring svc/prometheus 9090:9090
# Visit http://localhost:9090/graph
# Query: madfam_secret_days_until_rotation
```

### Rotation Script Fails

```bash
# Check kubectl context
kubectl config current-context

# Verify namespace access
kubectl get secrets -n janua

# Check pod exists
kubectl get pods -n janua | grep postgres

# Run with debug output
bash -x ./scripts/secrets/rotate-db-password.sh --project janua --dry-run
```

## Maintenance

### Weekly Tasks
- Review GitHub Actions run results
- Check for any failed notifications
- Address overdue secrets

### Monthly Tasks
- Review and update SECRETS_REGISTRY.yaml
- Verify all runbooks are current
- Test one rotation procedure end-to-end

### Quarterly Tasks
- Audit all secret access permissions
- Review and update rotation policies
- Test emergency rotation procedures

---

**Deployment Complete!**

Your secrets rotation management system is now operational. Run `./scripts/secrets/manage-secrets.sh status` regularly to monitor rotation schedules.
