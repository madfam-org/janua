# @janua/monitoring

> **Comprehensive observability and monitoring** for the Janua platform

**Version:** 0.1.0 · **Stack:** OpenTelemetry, Prometheus, Sentry · **Status:** Production Ready

## 📋 Overview

@janua/monitoring provides unified observability across all Janua services with distributed tracing, metrics collection, error tracking, and performance monitoring. Built on OpenTelemetry standards with support for multiple backends including Prometheus, Grafana, Sentry, and Datadog.

## 🚀 Quick Start

### Installation

```bash
# Install package
yarn add @janua/monitoring

# Install optional backends
yarn add @sentry/node @opentelemetry/api @opentelemetry/sdk-node
```

### Basic Setup

```typescript
import { Monitor } from '@janua/monitoring';

// Initialize monitoring
const monitor = Monitor.init({
  serviceName: 'auth-api',
  environment: 'production',
  version: '1.0.0',
  
  // Enable features
  tracing: true,
  metrics: true,
  errorTracking: true,
  profiling: true,
  
  // Configure backends
  sentry: {
    dsn: process.env.SENTRY_DSN
  },
  prometheus: {
    port: 9090
  }
});

// Start monitoring
await monitor.start();

// Use in application
monitor.trackEvent('user.signup', { plan: 'pro' });
monitor.captureError(error, { userId });
```

## 🏗️ Architecture

### Package Structure

```
packages/monitoring/
├── src/
│   ├── core/              # Core monitoring
│   │   ├── monitor.ts    # Main monitor class
│   │   ├── config.ts     # Configuration
│   │   └── types.ts      # Type definitions
│   ├── tracing/          # Distributed tracing
│   │   ├── tracer.ts     # OpenTelemetry tracer
│   │   ├── spans.ts      # Span management
│   │   ├── context.ts    # Trace context
│   │   └── exporters.ts  # Trace exporters
│   ├── metrics/          # Metrics collection
│   │   ├── collector.ts  # Metrics collector
│   │   ├── counters.ts   # Counter metrics
│   │   ├── gauges.ts     # Gauge metrics
│   │   ├── histograms.ts # Histogram metrics
│   │   └── exporters.ts  # Metrics exporters
│   ├── errors/           # Error tracking
│   │   ├── tracker.ts    # Error tracker
│   │   ├── sentry.ts     # Sentry integration
│   │   ├── context.ts    # Error context
│   │   └── filters.ts    # Error filtering
│   ├── performance/      # Performance monitoring
│   │   ├── profiler.ts   # CPU/Memory profiling
│   │   ├── vitals.ts     # Web vitals
│   │   ├── transactions.ts # Transaction tracking
│   │   └── benchmarks.ts # Performance benchmarks
│   ├── logging/          # Structured logging
│   │   ├── logger.ts     # Logger implementation
│   │   ├── formatters.ts # Log formatters
│   │   ├── transports.ts # Log transports
│   │   └── context.ts    # Logging context
│   ├── alerts/           # Alerting system
│   │   ├── manager.ts    # Alert manager
│   │   ├── rules.ts      # Alert rules
│   │   ├── channels.ts   # Alert channels
│   │   └── templates.ts  # Alert templates
│   ├── dashboards/       # Dashboard configs
│   │   ├── grafana/      # Grafana dashboards
│   │   ├── kibana/       # Kibana dashboards
│   │   └── datadog/      # Datadog dashboards
│   └── index.ts         # Main export
├── configs/             # Configuration files
│   ├── prometheus.yml   # Prometheus config
│   ├── grafana/        # Grafana dashboards
│   └── alerts/         # Alert rule configs
├── tests/              # Test files
└── package.json       # Package config
```

### Monitoring Architecture

```
┌─────────────────────────────────────┐
│         Application Layer           │
├─────────────────────────────────────┤
│       @janua/monitoring            │
│  ┌───────────────────────────────┐  │
│  │   OpenTelemetry SDK           │  │
│  │  ┌──────────────────────┐     │  │
│  │  │  Traces │ Metrics │ Logs │  │  │
│  │  └──────────────────────┘     │  │
│  └───────────────────────────────┘  │
├─────────────────────────────────────┤
│         Export Backends             │
│  ┌──────┬──────┬──────┬──────┐     │
│  │Jaeger│Prom. │Sentry│Datadog│     │
│  └──────┴──────┴──────┴──────┘     │
└─────────────────────────────────────┘
```

## 🔍 Distributed Tracing

### Basic Tracing

```typescript
import { Tracer } from '@janua/monitoring';

const tracer = new Tracer('auth-service');

// Create span
const span = tracer.startSpan('auth.login');
span.setAttributes({
  'user.email': email,
  'auth.method': 'password'
});

try {
  // Do work
  const user = await authenticateUser(email, password);
  span.setStatus({ code: SpanStatusCode.OK });
  return user;
} catch (error) {
  span.recordException(error);
  span.setStatus({ code: SpanStatusCode.ERROR });
  throw error;
} finally {
  span.end();
}
```

### Automatic Instrumentation

```typescript
import { autoInstrument } from '@janua/monitoring';

// Auto-instrument HTTP
autoInstrument.http({
  ignoreIncomingPaths: ['/health', '/metrics'],
  ignoreOutgoingHosts: ['localhost']
});

// Auto-instrument databases
autoInstrument.postgres();
autoInstrument.redis();
autoInstrument.mongodb();

// Auto-instrument frameworks
autoInstrument.express(app);
autoInstrument.fastify(server);
autoInstrument.graphql(schema);
```

### Context Propagation

```typescript
import { Context, propagation } from '@janua/monitoring';

// Extract context from incoming request
const context = propagation.extract(req.headers);

// Run with context
Context.with(context, async () => {
  // All operations here are traced together
  await processRequest();
});

// Inject context for outgoing requests
const headers = {};
propagation.inject(headers);
await fetch(url, { headers });
```

### Custom Spans

```typescript
import { trace } from '@janua/monitoring';

// Decorator for automatic tracing
class UserService {
  @trace('UserService.createUser')
  async createUser(data: CreateUserDto) {
    // Automatically traced
    return await this.db.users.create(data);
  }
}

// Manual span creation
async function complexOperation() {
  return tracer.startActiveSpan('complex.operation', async (span) => {
    span.addEvent('Starting processing');
    
    const phase1 = await tracer.startActiveSpan('phase1', async (childSpan) => {
      // Nested span
      return await doPhase1();
    });
    
    span.addEvent('Phase 1 complete', { result: phase1 });
    
    const phase2 = await doPhase2();
    
    span.setAttributes({
      'operation.phases': 2,
      'operation.result': 'success'
    });
    
    return { phase1, phase2 };
  });
}
```

## 📊 Metrics Collection

### Metric Types

```typescript
import { Metrics } from '@janua/monitoring';

const metrics = new Metrics('auth-service');

// Counter - monotonically increasing value
const loginCounter = metrics.createCounter('auth.login.count', {
  description: 'Number of login attempts',
  unit: 'attempts'
});

loginCounter.add(1, { method: 'password', success: true });

// Gauge - value that can go up or down
const activeUsers = metrics.createGauge('users.active', {
  description: 'Currently active users'
});

activeUsers.record(150);

// Histogram - distribution of values
const requestDuration = metrics.createHistogram('http.request.duration', {
  description: 'HTTP request duration',
  unit: 'ms',
  boundaries: [0, 5, 10, 25, 50, 100, 250, 500, 1000]
});

requestDuration.record(234, { endpoint: '/api/auth/login' });
```

### Custom Metrics

```typescript
// Business metrics
metrics.createCounter('revenue.total', {
  description: 'Total revenue',
  unit: 'USD'
});

metrics.createHistogram('checkout.duration', {
  description: 'Checkout process duration',
  unit: 'seconds'
});

metrics.createGauge('inventory.items', {
  description: 'Items in inventory'
});

// Record business events
metrics.increment('revenue.total', 99.99, {
  plan: 'pro',
  currency: 'USD'
});
```

### Prometheus Export

```typescript
import { PrometheusExporter } from '@janua/monitoring';

// Configure Prometheus exporter
const exporter = new PrometheusExporter({
  port: 9090,
  endpoint: '/metrics',
  prefix: 'janua_'
});

// Start metrics server
await exporter.start();

// Metrics available at http://localhost:9090/metrics
```

## 🚨 Error Tracking

### Sentry Integration

```typescript
import { ErrorTracker } from '@janua/monitoring';

const errorTracker = new ErrorTracker({
  dsn: process.env.SENTRY_DSN,
  environment: 'production',
  release: '1.0.0',
  tracesSampleRate: 0.1,
  beforeSend: (event) => {
    // Filter sensitive data
    delete event.request?.cookies;
    return event;
  }
});

// Capture errors
try {
  await riskyOperation();
} catch (error) {
  errorTracker.captureException(error, {
    user: { id: userId, email: userEmail },
    tags: { feature: 'authentication' },
    extra: { attemptNumber: 3 }
  });
}

// Capture messages
errorTracker.captureMessage('Payment webhook failed', 'error', {
  tags: { webhook: 'stripe' }
});
```

### Error Context

```typescript
// Set user context
errorTracker.setUser({
  id: 'user_123',
  email: 'user@example.com',
  subscription: 'pro'
});

// Set tags
errorTracker.setTags({
  feature: 'checkout',
  version: '2.0.0'
});

// Add breadcrumbs
errorTracker.addBreadcrumb({
  message: 'User clicked checkout',
  category: 'ui',
  level: 'info',
  data: { itemCount: 3 }
});

// Create transaction
const transaction = errorTracker.startTransaction({
  name: 'checkout-process',
  op: 'transaction'
});
```

## ⚡ Performance Monitoring

### Web Vitals

```typescript
import { WebVitals } from '@janua/monitoring';

const vitals = new WebVitals();

// Measure Core Web Vitals
vitals.onLCP((metric) => {
  console.log('Largest Contentful Paint:', metric.value);
});

vitals.onFID((metric) => {
  console.log('First Input Delay:', metric.value);
});

vitals.onCLS((metric) => {
  console.log('Cumulative Layout Shift:', metric.value);
});

// Custom performance marks
performance.mark('feature-start');
// ... feature code
performance.mark('feature-end');
performance.measure('feature-duration', 'feature-start', 'feature-end');
```

### CPU/Memory Profiling

```typescript
import { Profiler } from '@janua/monitoring';

const profiler = new Profiler();

// CPU profiling
const cpuProfile = await profiler.profileCPU({
  duration: 10000, // 10 seconds
  samplingInterval: 100 // microseconds
});

await cpuProfile.save('cpu-profile.cpuprofile');

// Memory profiling
const heapSnapshot = await profiler.takeHeapSnapshot();
await heapSnapshot.save('heap.heapsnapshot');

// Continuous monitoring
profiler.startContinuousProfiling({
  cpu: true,
  memory: true,
  interval: 60000 // Every minute
});
```

### Transaction Monitoring

```typescript
import { Transaction } from '@janua/monitoring';

// Monitor API transactions
app.use((req, res, next) => {
  const transaction = new Transaction({
    name: `${req.method} ${req.path}`,
    type: 'http.server'
  });
  
  transaction.start();
  
  res.on('finish', () => {
    transaction.setHttpStatus(res.statusCode);
    transaction.finish();
  });
  
  next();
});

// Monitor background jobs
async function processJob(job: Job) {
  const transaction = new Transaction({
    name: `job.${job.type}`,
    type: 'background'
  });
  
  try {
    transaction.start();
    await handleJob(job);
    transaction.setStatus('success');
  } catch (error) {
    transaction.setStatus('error');
    throw error;
  } finally {
    transaction.finish();
  }
}
```

## 📝 Structured Logging

### Logger Configuration

```typescript
import { Logger } from '@janua/monitoring';

const logger = new Logger({
  service: 'auth-api',
  level: 'info',
  format: 'json',
  transports: [
    { type: 'console', level: 'debug' },
    { type: 'file', filename: 'app.log', level: 'info' },
    { type: 'elasticsearch', node: 'http://localhost:9200' }
  ]
});

// Log with structure
logger.info('User authenticated', {
  userId: 'user_123',
  method: 'oauth',
  provider: 'google',
  duration: 234
});

// Log levels
logger.debug('Debug information');
logger.info('Informational message');
logger.warn('Warning message');
logger.error('Error occurred', { error });
logger.fatal('Fatal error', { error });
```

### Context Logging

```typescript
// Create child logger with context
const requestLogger = logger.child({
  requestId: req.id,
  userId: req.user?.id
});

requestLogger.info('Processing request');
// Automatically includes requestId and userId

// With middleware
app.use((req, res, next) => {
  req.logger = logger.child({
    requestId: req.id,
    method: req.method,
    path: req.path
  });
  next();
});
```

## 🔔 Alerting

### Alert Rules

```typescript
import { AlertManager } from '@janua/monitoring';

const alerts = new AlertManager();

// Define alert rules
alerts.addRule({
  name: 'HighErrorRate',
  query: 'rate(errors[5m]) > 0.05',
  duration: '5m',
  severity: 'critical',
  annotations: {
    summary: 'High error rate detected',
    description: 'Error rate is above 5% for 5 minutes'
  }
});

alerts.addRule({
  name: 'LowDiskSpace',
  query: 'disk_free_percent < 10',
  duration: '10m',
  severity: 'warning',
  annotations: {
    summary: 'Low disk space',
    description: 'Less than 10% disk space remaining'
  }
});

// Configure channels
alerts.addChannel('slack', {
  webhook: process.env.SLACK_WEBHOOK,
  channel: '#alerts'
});

alerts.addChannel('pagerduty', {
  apiKey: process.env.PAGERDUTY_KEY,
  serviceId: 'service_123'
});
```

### Custom Alerts

```typescript
// Trigger custom alerts
alerts.trigger('PaymentFailure', {
  severity: 'high',
  message: 'Multiple payment failures detected',
  data: {
    failures: 10,
    timeframe: '5 minutes',
    affectedUsers: ['user_1', 'user_2']
  }
});

// Alert on thresholds
monitor.onThreshold('memory.usage', 90, () => {
  alerts.trigger('HighMemoryUsage', {
    severity: 'warning',
    message: 'Memory usage above 90%'
  });
});
```

## 📈 Dashboards

### Grafana Dashboard

```json
// configs/grafana/auth-service.json
{
  "dashboard": {
    "title": "Auth Service Metrics",
    "panels": [
      {
        "title": "Request Rate",
        "targets": [{
          "expr": "rate(http_requests_total[5m])"
        }]
      },
      {
        "title": "Error Rate",
        "targets": [{
          "expr": "rate(http_errors_total[5m])"
        }]
      },
      {
        "title": "P95 Latency",
        "targets": [{
          "expr": "histogram_quantile(0.95, http_duration_seconds)"
        }]
      }
    ]
  }
}
```

### Custom Dashboards

```typescript
import { Dashboard } from '@janua/monitoring/dashboards';

const dashboard = new Dashboard({
  title: 'Business Metrics',
  refresh: '30s'
});

dashboard.addPanel({
  title: 'Revenue',
  type: 'graph',
  query: 'sum(revenue_total)',
  unit: 'USD'
});

dashboard.addPanel({
  title: 'Active Users',
  type: 'stat',
  query: 'users_active',
  thresholds: [
    { value: 0, color: 'red' },
    { value: 100, color: 'yellow' },
    { value: 1000, color: 'green' }
  ]
});

// Export dashboard
await dashboard.export('grafana');
```

## 🧪 Testing

### Mock Monitoring

```typescript
import { MockMonitor } from '@janua/monitoring/testing';

const monitor = new MockMonitor();

// Test metrics
monitor.expectMetric('auth.login.count', 5);
monitor.expectSpan('auth.login', { duration: 100 });

// Verify calls
expect(monitor.getMetric('auth.login.count')).toBe(5);
expect(monitor.getSpans('auth.login')).toHaveLength(1);
```

## 🚀 Performance Optimization

### Sampling Strategies

```typescript
// Trace sampling
const monitor = Monitor.init({
  tracing: {
    sampler: {
      type: 'probability',
      probability: 0.1 // Sample 10% of traces
    }
  }
});

// Adaptive sampling
const monitor = Monitor.init({
  tracing: {
    sampler: {
      type: 'adaptive',
      targetRate: 100, // 100 traces per second
      maxRate: 1000
    }
  }
});
```

### Batching & Buffering

```typescript
// Configure batching
const monitor = Monitor.init({
  metrics: {
    batchSize: 1000,
    flushInterval: 10000 // 10 seconds
  },
  traces: {
    batchSize: 100,
    flushInterval: 5000 // 5 seconds
  }
});
```

## 🛠️ Development

### Local Development

```bash
# Clone the repo
git clone https://github.com/madfam-io/janua.git

# Navigate to monitoring package
cd packages/monitoring

# Install dependencies
yarn install

# Run tests
yarn test

# Build package
yarn build

# Start local monitoring stack
docker-compose up -d
```

### Monitoring Stack

```yaml
# docker-compose.yml
services:
  prometheus:
    image: prometheus/prometheus
    ports: ["9090:9090"]
  
  grafana:
    image: grafana/grafana
    ports: ["3000:3000"]
  
  jaeger:
    image: jaegertracing/all-in-one
    ports: ["16686:16686"]
```

## 📚 Resources

- [OpenTelemetry Documentation](https://opentelemetry.io/docs/)
- [Prometheus Best Practices](https://prometheus.io/docs/practices/)
- [Grafana Dashboard Guide](https://grafana.com/docs/)
- [Sentry Integration](https://docs.sentry.io/)

## 🎯 Roadmap

### Current Version (0.1.0)
- ✅ OpenTelemetry integration
- ✅ Prometheus metrics
- ✅ Sentry error tracking
- ✅ Basic dashboards

### Next Release (0.2.0)
- [ ] Custom metrics SDK
- [ ] Advanced sampling
- [ ] Cost optimization
- [ ] ML-based anomaly detection

## 🤝 Contributing

See [Monitoring Contributing Guide](../../docs/contributing/monitoring.md) for development guidelines.

## 📄 License

Part of the Janua platform. See [LICENSE](../../LICENSE) in the root directory.