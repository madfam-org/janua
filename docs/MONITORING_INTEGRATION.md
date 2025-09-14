# Monitoring Stack Integration

This document describes the complete monitoring integration for the Plinto platform, including Prometheus metrics collection, health checks, and frontend monitoring.

## Overview

The monitoring stack consists of:
- **Backend Monitoring**: FastAPI with Prometheus metrics and health checks
- **Frontend Monitoring**: Next.js applications with custom metrics collection
- **Infrastructure Monitoring**: Prometheus + Grafana + AlertManager
- **Health Checks**: Comprehensive application and infrastructure health monitoring

## Architecture

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Frontend      │    │    Backend       │    │  Monitoring     │
│   (Next.js)     │────│   (FastAPI)      │────│  Stack          │
│                 │    │                  │    │                 │
│ • /api/metrics  │    │ • /metrics       │    │ • Prometheus    │
│ • Monitoring    │    │ • /health        │    │ • Grafana       │
│   Utilities     │    │ • Health Checks  │    │ • AlertManager  │
└─────────────────┘    └──────────────────┘    └─────────────────┘
```

## Backend Integration (FastAPI)

### Metrics Endpoints

1. **Prometheus Metrics**: `GET /metrics`
   - System metrics (CPU, memory, disk)
   - Application metrics (HTTP requests, errors)
   - Database connection pool status
   - Redis connection status

2. **Health Checks**: `GET /api/v1/health/detailed`
   - Database connectivity
   - Redis connectivity
   - System resource status

3. **Performance Metrics**: `GET /metrics/performance`
   - API performance statistics
   - Cache hit rates
   - Response time distributions

### Implementation Details

The backend uses:
- `prometheus-client` for metrics collection
- `MetricsCollector` service for custom metrics
- `HealthChecker` service for health monitoring
- `AlertManager` for automated alerting

Key files:
- `apps/api/app/services/monitoring.py` - Core monitoring services
- `apps/api/app/routers/v1/health.py` - Health check endpoints
- `apps/api/app/main.py` - Integration and startup configuration

## Frontend Integration (Next.js)

### Dashboard Application

**Metrics Endpoint**: `GET /apps/dashboard/api/metrics`

Tracks:
- Page views
- API calls
- Client-side errors
- Application uptime

**Usage**:
```typescript
import { useMonitoring } from '@/lib/monitoring'

function MyComponent() {
  const { trackPageView, trackUserAction } = useMonitoring()
  
  useEffect(() => {
    trackPageView('/dashboard')
  }, [])
  
  const handleClick = () => {
    trackUserAction('button_click', 'navigation')
  }
}
```

### Admin Application

**Metrics Endpoint**: `GET /apps/admin/api/metrics`

Tracks:
- Admin actions
- User operations
- Configuration changes
- Security events

**Usage**:
```typescript
import { useAdminMonitoring } from '@/lib/monitoring'

function AdminPanel() {
  const { trackAdminAction, trackConfigChange } = useAdminMonitoring()
  
  const updateUserRole = async (userId: string, newRole: string) => {
    await updateRole(userId, newRole)
    trackAdminAction('user_role_update', 'users', userId)
  }
}
```

## Prometheus Configuration

The monitoring stack expects the following endpoints:

```yaml
scrape_configs:
  - job_name: 'plinto-api'
    static_configs:
      - targets: ['localhost:8000']
    metrics_path: '/metrics'

  - job_name: 'plinto-dashboard'
    static_configs:
      - targets: ['localhost:3001']
    metrics_path: '/api/metrics'

  - job_name: 'plinto-admin'
    static_configs:
      - targets: ['localhost:3004']
    metrics_path: '/api/metrics'
```

## Health Checks

### Backend Health Endpoints

1. **Basic Health**: `GET /health`
   - Simple alive check
   - Returns 200 if service is running

2. **Detailed Health**: `GET /api/v1/health/detailed`
   - Database connectivity test
   - Redis connectivity test
   - System resource checks
   - Returns detailed status for each component

3. **Readiness Probe**: `GET /api/v1/health/ready`
   - Kubernetes readiness check
   - Returns 503 if not ready for traffic

4. **Liveness Probe**: `GET /api/v1/health/live`
   - Kubernetes liveness check
   - Returns 200 if process is alive

### Integration with Kubernetes

```yaml
apiVersion: v1
kind: Pod
spec:
  containers:
  - name: plinto-api
    livenessProbe:
      httpGet:
        path: /api/v1/health/live
        port: 8000
      initialDelaySeconds: 30
      periodSeconds: 10
    readinessProbe:
      httpGet:
        path: /api/v1/health/ready
        port: 8000
      initialDelaySeconds: 5
      periodSeconds: 5
```

## Validation and Testing

### Automated Validation

Run the monitoring integration check:

```bash
# Install dependencies
pip install aiohttp

# Run validation script
python scripts/monitoring-integration-check.py
```

This script will:
- Test all monitoring endpoints
- Validate Prometheus metrics format
- Test metrics collection functionality
- Generate a comprehensive report

### Manual Testing

1. **Start all services**:
   ```bash
   # Backend
   cd apps/api && uvicorn app.main:app --port 8000

   # Dashboard
   cd apps/dashboard && npm run dev

   # Admin
   cd apps/admin && npm run dev
   ```

2. **Test endpoints**:
   ```bash
   # Backend metrics
   curl http://localhost:8000/metrics

   # Backend health
   curl http://localhost:8000/api/v1/health/detailed

   # Frontend metrics
   curl http://localhost:3001/api/metrics
   curl http://localhost:3004/api/metrics
   ```

3. **Test metrics collection**:
   ```bash
   # Test dashboard metrics collection
   curl -X POST http://localhost:3001/api/metrics \
     -H "Content-Type: application/json" \
     -d '{"type":"pageView","metadata":{"page":"/test"}}'

   # Test admin metrics collection
   curl -X POST http://localhost:3004/api/metrics \
     -H "Content-Type: application/json" \
     -d '{"type":"adminAction","metadata":{"action":"test"}}'
   ```

## Monitoring Stack Deployment

### Using Docker Compose

```yaml
# deployment/monitoring/docker-compose.yml
version: '3.8'
services:
  prometheus:
    image: prom/prometheus:latest
    ports:
      - "9090:9090"
    volumes:
      - ./prometheus.yml:/etc/prometheus/prometheus.yml

  grafana:
    image: grafana/grafana:latest
    ports:
      - "3000:3000"
    volumes:
      - ./grafana-dashboard.json:/var/lib/grafana/dashboards/
```

Start monitoring stack:
```bash
cd deployment/monitoring
docker-compose up -d
```

### Accessing Dashboards

- **Prometheus**: http://localhost:9090
- **Grafana**: http://localhost:3000 (admin/admin)

## Alerting

The monitoring system includes automated alerting for:

- API downtime
- High error rates (>10%)
- Database connection issues
- High memory usage (>90%)
- Security events

Alerts are configured in:
- `deployment/monitoring/prometheus.yml` - Alert rules
- `monitoring/dashboard-config.yaml` - Dashboard configuration

## Metrics Reference

### Backend Metrics

| Metric Name | Type | Description |
|-------------|------|-------------|
| `plinto_system_cpu_percent` | Gauge | System CPU usage percentage |
| `plinto_system_memory_percent` | Gauge | System memory usage percentage |
| `plinto_http_requests_total` | Counter | Total HTTP requests by method/endpoint/status |
| `plinto_http_request_duration_seconds` | Histogram | HTTP request duration |
| `plinto_database_connections_active` | Gauge | Active database connections |
| `plinto_redis_connected` | Gauge | Redis connection status |

### Frontend Metrics

| Metric Name | Type | Description |
|-------------|------|-------------|
| `plinto_dashboard_page_views_total` | Counter | Dashboard page views |
| `plinto_dashboard_api_calls_total` | Counter | Dashboard API calls |
| `plinto_admin_actions_total` | Counter | Admin actions performed |
| `plinto_admin_config_changes_total` | Counter | Configuration changes |

## Troubleshooting

### Common Issues

1. **Metrics endpoint returns 404**
   - Ensure monitoring services are initialized in startup
   - Check that health checker is properly injected

2. **Frontend metrics not collecting**
   - Verify `NEXT_PUBLIC_ENABLE_MONITORING=true` is set
   - Check browser console for JavaScript errors

3. **Prometheus can't scrape endpoints**
   - Verify all services are running on expected ports
   - Check firewall/network configuration
   - Validate Prometheus configuration file

### Debug Commands

```bash
# Check if monitoring is working
npm run test:monitoring

# View raw metrics
curl -s http://localhost:8000/metrics | grep plinto_

# Check health status
curl -s http://localhost:8000/api/v1/health/detailed | jq

# Validate integration
python scripts/monitoring-integration-check.py
```

## Next Steps

After integration:

1. **Configure Grafana dashboards** using `monitoring/dashboard-config.yaml`
2. **Set up alerting** channels (Slack, PagerDuty, email)
3. **Monitor resource usage** and adjust alert thresholds
4. **Set up log aggregation** for comprehensive observability
5. **Implement distributed tracing** for complex request flows

## Security Considerations

- Metrics endpoints expose system information - secure appropriately
- Admin metrics contain sensitive actions - limit access
- Health checks can be used for reconnaissance - consider authentication
- Log PII carefully in error tracking and metrics