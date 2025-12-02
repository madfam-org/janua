# @janua/config

> **Centralized configuration management** for the Janua platform

**Version:** 0.1.0 · **Type:** Configuration Layer · **Status:** Production Ready

## 📋 Overview

@janua/config provides centralized, type-safe configuration management across all Janua services and applications. It supports environment-based configs, runtime validation, secret management, feature flags, and dynamic configuration updates without restarts.

## 🚀 Quick Start

### Installation

```bash
# Install package
yarn add @janua/config

# Install optional integrations
yarn add dotenv joi
```

### Basic Usage

```typescript
import { Config } from '@janua/config';

// Load configuration
const config = Config.load({
  appName: 'auth-api',
  environment: process.env.NODE_ENV || 'development'
});

// Access configuration
console.log(config.get('database.url'));
console.log(config.get('redis.host'));
console.log(config.get('auth.jwtSecret'));

// Type-safe access
const dbConfig = config.getTyped<DatabaseConfig>('database');
```

### Environment-Based Config

```typescript
// config/default.ts
export default {
  app: {
    name: 'Janua',
    version: '1.0.0'
  },
  server: {
    port: 3000,
    host: 'localhost'
  }
};

// config/production.ts
export default {
  server: {
    port: 8080,
    host: '0.0.0.0'
  },
  database: {
    pool: {
      max: 20,
      min: 5
    }
  }
};
```

## 🏗️ Architecture

### Package Structure

```
packages/config/
├── src/
│   ├── core/              # Core configuration
│   │   ├── config.ts     # Main config class
│   │   ├── loader.ts     # Config loader
│   │   ├── validator.ts  # Validation
│   │   └── types.ts      # Type definitions
│   ├── sources/          # Configuration sources
│   │   ├── env.ts        # Environment variables
│   │   ├── file.ts       # File-based config
│   │   ├── remote.ts     # Remote config
│   │   ├── vault.ts      # Secret management
│   │   └── consul.ts     # Consul integration
│   ├── schemas/          # Validation schemas
│   │   ├── app.ts        # App config schema
│   │   ├── database.ts   # Database schema
│   │   ├── redis.ts      # Redis schema
│   │   ├── auth.ts       # Auth schema
│   │   └── api.ts        # API schema
│   ├── features/         # Feature management
│   │   ├── flags.ts      # Feature flags
│   │   ├── toggles.ts    # Feature toggles
│   │   ├── experiments.ts # A/B testing
│   │   └── rollout.ts    # Gradual rollout
│   ├── secrets/          # Secret management
│   │   ├── manager.ts    # Secret manager
│   │   ├── encryption.ts # Encryption utils
│   │   ├── rotation.ts   # Secret rotation
│   │   └── providers.ts  # Secret providers
│   ├── utils/           # Utilities
│   │   ├── merge.ts     # Config merging
│   │   ├── interpolate.ts # Variable interpolation
│   │   ├── watch.ts     # File watching
│   │   └── cache.ts     # Config caching
│   └── index.ts        # Main export
├── configs/           # Default configurations
│   ├── default.ts    # Base configuration
│   ├── development.ts # Dev overrides
│   ├── staging.ts    # Staging overrides
│   └── production.ts # Production overrides
├── schemas/          # JSON schemas
└── package.json     # Package config
```

### Configuration Architecture

```
┌─────────────────────────────────────┐
│         Application Layer           │
├─────────────────────────────────────┤
│         @janua/config              │
│  ┌───────────────────────────────┐  │
│  │   Configuration Manager       │  │
│  │  ┌──────────────────────┐     │  │
│  │  │ Loader │ Validator │Cache│  │  │
│  │  └──────────────────────┘     │  │
│  └───────────────────────────────┘  │
├─────────────────────────────────────┤
│       Configuration Sources         │
│  ┌──────┬──────┬──────┬──────┐     │
│  │ Env  │Files │Vault │Remote│     │
│  └──────┴──────┴──────┴──────┘     │
└─────────────────────────────────────┘
```

## ⚙️ Configuration Management

### Loading Configuration

```typescript
import { Config } from '@janua/config';

// Simple loading
const config = Config.load();

// With options
const config = Config.load({
  appName: 'auth-api',
  environment: 'production',
  configPath: './config',
  sources: ['env', 'file', 'vault'],
  validation: true,
  cache: true
});

// Async loading (for remote sources)
const config = await Config.loadAsync({
  sources: ['consul', 'vault'],
  consul: {
    host: 'consul.example.com',
    key: 'janua/config'
  }
});
```

### Configuration Sources

#### Environment Variables

```typescript
// Automatically loads from process.env
const config = Config.load({
  sources: ['env']
});

// With prefix
const config = Config.load({
  sources: ['env'],
  envPrefix: 'JANUA_'
});

// .env file
DATABASE_URL=postgresql://localhost/janua
REDIS_URL=redis://localhost:6379
JWT_SECRET=secret123
```

#### File-Based Config

```typescript
// config/default.json
{
  "app": {
    "name": "Janua",
    "version": "1.0.0"
  },
  "database": {
    "host": "localhost",
    "port": 5432
  }
}

// Load JSON/YAML/JS/TS files
const config = Config.load({
  sources: ['file'],
  configPath: './config',
  filePattern: 'config.{json,yml,js,ts}'
});
```

#### Remote Configuration

```typescript
// Consul integration
const config = await Config.loadAsync({
  sources: ['consul'],
  consul: {
    host: 'consul.example.com',
    port: 8500,
    key: 'janua/config',
    watch: true // Auto-reload on changes
  }
});

// HTTP endpoint
const config = await Config.loadAsync({
  sources: ['remote'],
  remote: {
    url: 'https://config.example.com/janua',
    headers: {
      'Authorization': 'Bearer token'
    },
    pollInterval: 60000 // Refresh every minute
  }
});
```

### Configuration Merging

```typescript
// Priority order (highest to lowest):
// 1. Environment variables
// 2. Environment-specific file (production.json)
// 3. Default file (default.json)
// 4. Remote configuration

const config = Config.load({
  sources: ['env', 'file', 'remote'],
  mergeStrategy: 'deep' // 'deep' or 'shallow'
});

// Custom merge function
const config = Config.load({
  merge: (target, source) => {
    // Custom merge logic
    return mergedConfig;
  }
});
```

## 🔒 Secret Management

### Secret Providers

```typescript
import { SecretManager } from '@janua/config/secrets';

// AWS Secrets Manager
const secrets = new SecretManager({
  provider: 'aws',
  region: 'us-east-1',
  credentials: {
    accessKeyId: process.env.AWS_ACCESS_KEY_ID,
    secretAccessKey: process.env.AWS_SECRET_ACCESS_KEY
  }
});

// HashiCorp Vault
const secrets = new SecretManager({
  provider: 'vault',
  endpoint: 'https://vault.example.com',
  token: process.env.VAULT_TOKEN
});

// Azure Key Vault
const secrets = new SecretManager({
  provider: 'azure',
  vaultUrl: 'https://myvault.vault.azure.net',
  credentials: {
    tenantId: process.env.AZURE_TENANT_ID,
    clientId: process.env.AZURE_CLIENT_ID,
    clientSecret: process.env.AZURE_CLIENT_SECRET
  }
});
```

### Loading Secrets

```typescript
// Load secrets into config
const config = await Config.loadAsync({
  sources: ['vault'],
  vault: {
    provider: secrets,
    paths: [
      'secret/data/database',
      'secret/data/redis',
      'secret/data/jwt'
    ]
  }
});

// Direct secret access
const dbPassword = await secrets.getSecret('database/password');
const apiKey = await secrets.getSecret('external/api-key');
```

### Secret Rotation

```typescript
import { SecretRotation } from '@janua/config/secrets';

const rotation = new SecretRotation({
  provider: secrets,
  schedule: '0 0 * * 0', // Weekly
  secrets: [
    {
      path: 'database/password',
      generator: () => generateSecurePassword(),
      onRotate: async (newSecret) => {
        // Update database password
        await updateDatabasePassword(newSecret);
      }
    }
  ]
});

await rotation.start();
```

## ✅ Validation

### Schema Validation

```typescript
import { Schema } from '@janua/config';

// Define schema
const schema = Schema.object({
  app: Schema.object({
    name: Schema.string().required(),
    version: Schema.string().pattern(/^\d+\.\d+\.\d+$/)
  }),
  server: Schema.object({
    port: Schema.number().min(1).max(65535),
    host: Schema.string().hostname()
  }),
  database: Schema.object({
    url: Schema.string().uri().required(),
    pool: Schema.object({
      min: Schema.number().min(0),
      max: Schema.number().min(1)
    })
  })
});

// Validate config
const config = Config.load({
  validation: true,
  schema
});
```

### Custom Validators

```typescript
// Add custom validator
Config.addValidator('email', (value) => {
  const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
  if (!emailRegex.test(value)) {
    throw new Error('Invalid email format');
  }
  return value;
});

// Use in schema
const schema = Schema.object({
  admin: Schema.object({
    email: Schema.string().custom('email')
  })
});
```

### Runtime Validation

```typescript
// Validate on access
const config = Config.load({
  validateOnAccess: true
});

try {
  const port = config.get('server.port'); // Validates automatically
} catch (error) {
  console.error('Invalid configuration:', error);
}
```

## 🎛️ Feature Flags

### Feature Flag Management

```typescript
import { FeatureFlags } from '@janua/config/features';

const flags = new FeatureFlags({
  provider: 'local', // or 'launchdarkly', 'split', 'unleash'
  defaults: {
    'new-auth-flow': false,
    'beta-features': false,
    'maintenance-mode': false
  }
});

// Check feature flag
if (flags.isEnabled('new-auth-flow')) {
  // Use new authentication flow
}

// With user context
if (flags.isEnabled('beta-features', { userId, plan: 'pro' })) {
  // Show beta features
}
```

### A/B Testing

```typescript
import { Experiments } from '@janua/config/features';

const experiments = new Experiments({
  provider: 'optimizely',
  projectId: 'project_123'
});

// Get variation
const variation = experiments.getVariation('checkout-flow', userId);

switch (variation) {
  case 'control':
    // Original checkout
    break;
  case 'variant-a':
    // New checkout flow A
    break;
  case 'variant-b':
    // New checkout flow B
    break;
}

// Track conversion
experiments.track('purchase-completed', userId, {
  amount: 99.99,
  items: 3
});
```

### Gradual Rollout

```typescript
import { Rollout } from '@janua/config/features';

const rollout = new Rollout({
  feature: 'new-dashboard',
  stages: [
    { percentage: 10, duration: '1d' },
    { percentage: 25, duration: '3d' },
    { percentage: 50, duration: '1w' },
    { percentage: 100 }
  ]
});

// Check if user should see feature
if (rollout.isEnabled(userId)) {
  // Show new dashboard
}

// Manual rollout control
await rollout.advance(); // Move to next stage
await rollout.rollback(); // Go back one stage
```

## 🔄 Dynamic Configuration

### Hot Reload

```typescript
// Enable hot reload
const config = Config.load({
  watch: true,
  watchOptions: {
    interval: 1000, // Check every second
    debounce: 500  // Wait 500ms after change
  }
});

// Listen for changes
config.on('change', (changes) => {
  console.log('Config changed:', changes);
  // Restart services or update runtime
});

// Specific key watching
config.watch('database.pool.max', (newValue, oldValue) => {
  console.log(`Pool size changed from ${oldValue} to ${newValue}`);
  // Update connection pool
});
```

### Runtime Updates

```typescript
// Update configuration at runtime
config.set('feature.enabled', true);
config.set('api.rateLimit', 1000);

// Batch updates
config.update({
  'feature.enabled': true,
  'api.rateLimit': 1000,
  'cache.ttl': 3600
});

// Temporary override
config.override('maintenance.mode', true);
// ... maintenance work
config.removeOverride('maintenance.mode');
```

## 📝 Type Safety

### TypeScript Support

```typescript
// Define configuration interface
interface AppConfig {
  app: {
    name: string;
    version: string;
  };
  database: {
    url: string;
    pool: {
      min: number;
      max: number;
    };
  };
  redis: {
    host: string;
    port: number;
  };
}

// Type-safe config
const config = Config.load<AppConfig>();

// Auto-completion and type checking
const dbUrl = config.get('database.url'); // string
const poolMax = config.get('database.pool.max'); // number
```

### Config Generator

```typescript
// Generate TypeScript types from schema
import { generateTypes } from '@janua/config/generator';

const types = generateTypes(schema);
// Outputs TypeScript interface definitions

// Generate from config files
const types = generateTypesFromFiles('./config/*.json');
```

## 🌍 Multi-Environment Support

### Environment Detection

```typescript
const config = Config.load({
  environment: Config.detectEnvironment({
    // Custom detection logic
    production: () => process.env.NODE_ENV === 'production',
    staging: () => process.env.APP_ENV === 'staging',
    development: () => !process.env.NODE_ENV || process.env.NODE_ENV === 'development'
  })
});
```

### Environment-Specific Files

```typescript
// Automatically loads based on environment
// development: config/development.json
// staging: config/staging.json
// production: config/production.json

const config = Config.load({
  configPath: './config',
  environment: process.env.NODE_ENV
});
```

## 🧪 Testing

### Mock Configuration

```typescript
import { MockConfig } from '@janua/config/testing';

// Create mock config for tests
const mockConfig = new MockConfig({
  app: { name: 'test-app' },
  database: { url: 'sqlite::memory:' }
});

// Use in tests
beforeEach(() => {
  Config.setInstance(mockConfig);
});

// Override specific values
mockConfig.set('feature.enabled', true);
```

### Configuration Testing

```typescript
describe('Configuration', () => {
  test('loads valid configuration', () => {
    const config = Config.load({
      sources: ['file'],
      configPath: './test/fixtures'
    });
    
    expect(config.get('app.name')).toBe('Janua');
  });
  
  test('validates configuration', () => {
    expect(() => {
      Config.load({
        validation: true,
        schema: testSchema,
        configPath: './test/invalid'
      });
    }).toThrow('Validation error');
  });
});
```

## 🛠️ CLI Tools

### Configuration CLI

```bash
# Validate configuration
janua-config validate --schema ./schema.json

# Generate TypeScript types
janua-config generate-types --output ./types.ts

# Encrypt secrets
janua-config encrypt --key $ENCRYPTION_KEY

# Decrypt secrets
janua-config decrypt --key $ENCRYPTION_KEY

# Compare configurations
janua-config diff ./config/prod.json ./config/staging.json

# Export configuration
janua-config export --format json > config.json
```

## 📊 Monitoring

### Configuration Metrics

```typescript
import { ConfigMonitor } from '@janua/config/monitoring';

const monitor = new ConfigMonitor(config);

// Track config access patterns
const stats = monitor.getStats();
console.log('Most accessed keys:', stats.topKeys);
console.log('Unused keys:', stats.unusedKeys);

// Track changes
monitor.on('change', (event) => {
  logger.info('Config changed', {
    key: event.key,
    oldValue: event.oldValue,
    newValue: event.newValue,
    source: event.source
  });
});
```

## 🚀 Best Practices

### Configuration Structure

```typescript
// Good: Hierarchical and organized
{
  "app": {
    "name": "Janua",
    "version": "1.0.0"
  },
  "services": {
    "database": {
      "host": "localhost",
      "port": 5432
    }
  }
}

// Bad: Flat and unorganized
{
  "appName": "Janua",
  "appVersion": "1.0.0",
  "databaseHost": "localhost",
  "databasePort": 5432
}
```

### Security

```typescript
// Never commit secrets
// ❌ Bad
{
  "database": {
    "password": "actualPassword123"
  }
}

// ✅ Good
{
  "database": {
    "password": "${DB_PASSWORD}" // Use env var or secret manager
  }
}
```

## 🛠️ Development

### Local Development

```bash
# Clone the repo
git clone https://github.com/madfam-io/janua.git

# Navigate to config package
cd packages/config

# Install dependencies
yarn install

# Run tests
yarn test

# Build package
yarn build
```

## 📚 Resources

- [Configuration Best Practices](https://docs.janua.dev/config/best-practices)
- [Schema Documentation](https://docs.janua.dev/config/schemas)
- [Secret Management Guide](https://docs.janua.dev/config/secrets)

## 🎯 Roadmap

### Current Version (0.1.0)
- ✅ Multiple config sources
- ✅ Schema validation
- ✅ Secret management
- ✅ Feature flags

### Next Release (0.2.0)
- [ ] GraphQL config schema
- [ ] Config versioning
- [ ] Distributed config sync
- [ ] Config analytics

## 🤝 Contributing

See [Config Contributing Guide](../../docs/contributing/config.md) for development guidelines.

## 📄 License

Part of the Janua platform. See [LICENSE](../../LICENSE) in the root directory.