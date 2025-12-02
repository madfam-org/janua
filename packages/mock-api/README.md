# @janua/mock-api

> **Mock API server and testing utilities** for Janua development

**Version:** 0.1.0 · **Purpose:** Development & Testing · **Status:** Production Ready

## 📋 Overview

@janua/mock-api provides a fully-featured mock API server that mirrors the production Janua API, enabling frontend development, integration testing, and demos without requiring the actual backend. Includes realistic data generation, configurable responses, and testing utilities.

## 🚀 Quick Start

### Installation

```bash
# Install package
yarn add -D @janua/mock-api

# Or globally for CLI usage
npm install -g @janua/mock-api
```

### Basic Usage

#### CLI Usage

```bash
# Start mock server with defaults
janua-mock

# With custom configuration
janua-mock --port 8080 --delay 500 --seed 12345

# With specific scenarios
janua-mock --scenario auth-error --verbose
```

#### Programmatic Usage

```typescript
import { MockServer } from '@janua/mock-api';

// Start mock server
const server = new MockServer({
  port: 8080,
  delay: 100, // Simulate network delay
  errorRate: 0.1, // 10% error rate
  seed: 12345 // Reproducible random data
});

await server.start();

// Server running at http://localhost:8080
```

#### In Tests

```typescript
import { createMockClient } from '@janua/mock-api/testing';

const mockApi = createMockClient();

// Configure responses
mockApi.onPost('/auth/login').reply(200, {
  user: { id: 'user_123', email: 'test@example.com' },
  tokens: { accessToken: 'mock_token' }
});

// Use in tests
const response = await fetch('http://localhost:8080/auth/login');
```

## 🏗️ Architecture

### Package Structure

```
packages/mock-api/
├── src/
│   ├── server/            # Mock server
│   │   ├── index.ts      # Server setup
│   │   ├── middleware.ts # Express middleware
│   │   ├── router.ts     # Route definitions
│   │   └── websocket.ts  # WebSocket support
│   ├── handlers/         # Request handlers
│   │   ├── auth.ts       # Auth endpoints
│   │   ├── users.ts      # User endpoints
│   │   ├── orgs.ts       # Organization endpoints
│   │   ├── sessions.ts   # Session endpoints
│   │   └── webhooks.ts   # Webhook simulation
│   ├── data/            # Data generation
│   │   ├── generator.ts # Data generator
│   │   ├── factories.ts # Model factories
│   │   ├── fixtures.ts  # Static fixtures
│   │   └── seeds.ts     # Seed data
│   ├── scenarios/       # Test scenarios
│   │   ├── auth.ts      # Auth scenarios
│   │   ├── errors.ts    # Error scenarios
│   │   ├── edge.ts      # Edge cases
│   │   └── load.ts      # Load testing
│   ├── database/        # In-memory database
│   │   ├── store.ts     # Data store
│   │   ├── query.ts     # Query engine
│   │   └── persistence.ts # Optional persistence
│   ├── utils/          # Utilities
│   │   ├── delay.ts    # Response delays
│   │   ├── errors.ts   # Error simulation
│   │   ├── validation.ts # Request validation
│   │   └── jwt.ts      # JWT mocking
│   ├── cli/           # CLI tool
│   │   └── index.ts   # CLI entry point
│   └── index.ts      # Main export
├── fixtures/         # Static test data
│   ├── users.json   # User fixtures
│   ├── orgs.json    # Organization fixtures
│   └── ...
├── scenarios/       # Scenario definitions
├── tests/          # Test files
└── package.json   # Package config
```

### Mock Architecture

```
┌─────────────────────────────────────┐
│         Client Application          │
├─────────────────────────────────────┤
│         Mock API Server             │
│  ┌───────────────────────────────┐  │
│  │    Request Processing         │  │
│  │  ┌──────────────────────┐     │  │
│  │  │ Validation │ Delay │Error│  │  │
│  │  └──────────────────────┘     │  │
│  └───────────────────────────────┘  │
│  ┌───────────────────────────────┐  │
│  │    In-Memory Database         │  │
│  │  ┌──────────────────────┐     │  │
│  │  │ Users │ Orgs │Sessions│    │  │
│  │  └──────────────────────┘     │  │
│  └───────────────────────────────┘  │
└─────────────────────────────────────┘
```

## 🎯 API Endpoints

### Authentication

```typescript
// All endpoints match production API
POST   /auth/signup
POST   /auth/login
POST   /auth/logout
POST   /auth/refresh
POST   /auth/forgot-password
POST   /auth/reset-password
POST   /auth/verify-email
GET    /auth/me
```

### Users

```typescript
GET    /users                 // List users
GET    /users/:id            // Get user
PUT    /users/:id            // Update user
DELETE /users/:id            // Delete user
POST   /users/:id/avatar     // Upload avatar
GET    /users/:id/sessions   // User sessions
```

### Organizations

```typescript
GET    /organizations              // List organizations
POST   /organizations             // Create organization
GET    /organizations/:id         // Get organization
PUT    /organizations/:id         // Update organization
DELETE /organizations/:id         // Delete organization
GET    /organizations/:id/members // List members
POST   /organizations/:id/invite  // Invite member
```

### Sessions

```typescript
GET    /sessions              // List sessions
GET    /sessions/:id         // Get session
DELETE /sessions/:id         // Revoke session
DELETE /sessions/revoke-all  // Revoke all sessions
```

## 🎭 Scenarios

### Predefined Scenarios

```typescript
import { MockServer, Scenarios } from '@janua/mock-api';

const server = new MockServer();

// Load predefined scenario
server.loadScenario(Scenarios.AUTH_ERROR);
// All auth requests will fail

server.loadScenario(Scenarios.SLOW_NETWORK);
// All requests delayed by 2-5 seconds

server.loadScenario(Scenarios.RATE_LIMITED);
// Triggers rate limiting after 5 requests

server.loadScenario(Scenarios.MAINTENANCE_MODE);
// Returns 503 for all requests
```

### Custom Scenarios

```typescript
// Define custom scenario
const customScenario = {
  name: 'payment-failure',
  description: 'Simulates payment processing failures',
  setup: (server: MockServer) => {
    server.on('/payments/*', () => {
      throw new Error('Payment gateway unavailable');
    });
    
    server.on('/users/*/subscription', () => {
      return { status: 'payment_failed' };
    });
  }
};

server.loadScenario(customScenario);
```

### Scenario Chains

```typescript
// Chain multiple scenarios
server
  .loadScenario(Scenarios.NEW_USER)
  .then(Scenarios.EMAIL_VERIFICATION)
  .then(Scenarios.ONBOARDING)
  .then(Scenarios.FIRST_LOGIN);

// Scenarios execute in sequence
```

## 🎲 Data Generation

### Factories

```typescript
import { UserFactory, OrgFactory } from '@janua/mock-api/factories';

// Generate single user
const user = UserFactory.create({
  email: 'custom@example.com'
});

// Generate multiple users
const users = UserFactory.createMany(10);

// Generate with relationships
const org = OrgFactory.create({
  members: UserFactory.createMany(5)
});
```

### Custom Generators

```typescript
import { Generator } from '@janua/mock-api';

// Configure data generator
const generator = new Generator({
  seed: 12345, // Reproducible data
  locale: 'en_US'
});

// Generate data
const email = generator.email();
const name = generator.name();
const company = generator.company();
const avatar = generator.avatar();
const uuid = generator.uuid();
```

### Fixtures

```typescript
import { Fixtures } from '@janua/mock-api';

// Load fixtures
const fixtures = new Fixtures();
await fixtures.load('users', 'organizations');

// Access fixture data
const adminUser = fixtures.users.admin;
const testOrg = fixtures.organizations.test;

// Reset to fixtures
await fixtures.reset();
```

## 💾 Data Persistence

### In-Memory Store

```typescript
import { DataStore } from '@janua/mock-api';

const store = new DataStore();

// CRUD operations
await store.create('users', userData);
await store.findById('users', userId);
await store.update('users', userId, updates);
await store.delete('users', userId);

// Queries
const users = await store.find('users', {
  where: { active: true },
  orderBy: 'createdAt',
  limit: 10
});
```

### File Persistence

```typescript
// Enable file persistence
const server = new MockServer({
  persistence: {
    enabled: true,
    path: './mock-data.json',
    autoSave: true,
    interval: 5000 // Save every 5 seconds
  }
});

// Manual save/load
await server.saveData('./backup.json');
await server.loadData('./backup.json');
```

## 🔧 Configuration

### Server Options

```typescript
const server = new MockServer({
  // Network
  port: 8080,
  host: '0.0.0.0',
  cors: true,
  
  // Response behavior
  delay: {
    min: 100,
    max: 500,
    distribution: 'normal' // or 'uniform', 'exponential'
  },
  
  // Error simulation
  errorRate: 0.05, // 5% of requests fail
  errorCodes: [400, 401, 403, 500],
  
  // Data
  seed: 12345,
  dataSize: 'small', // 'small', 'medium', 'large'
  
  // Features
  auth: true,
  webhooks: true,
  websockets: true,
  
  // Logging
  verbose: true,
  logLevel: 'debug'
});
```

### Response Customization

```typescript
// Global response interceptor
server.intercept((req, res, next) => {
  res.headers['X-Mock-Server'] = 'true';
  res.delay = Math.random() * 1000;
  next();
});

// Route-specific customization
server.customize('/auth/login', {
  delay: 2000,
  errorRate: 0.2,
  response: (req) => ({
    user: UserFactory.create(),
    tokens: generateTokens(req.body.email)
  })
});
```

## 🧪 Testing Utilities

### Mock Client

```typescript
import { MockClient } from '@janua/mock-api/testing';

describe('Auth Flow', () => {
  let client: MockClient;
  
  beforeEach(() => {
    client = new MockClient();
  });
  
  test('login succeeds', async () => {
    client.onPost('/auth/login').reply(200, {
      user: { id: '123' },
      tokens: { accessToken: 'token' }
    });
    
    const response = await client.post('/auth/login', {
      email: 'test@example.com',
      password: 'password'
    });
    
    expect(response.status).toBe(200);
    expect(response.data.user.id).toBe('123');
  });
});
```

### Request Assertions

```typescript
// Verify requests
client.onPost('/auth/login').reply(200);

await makeLoginRequest();

expect(client.history.post).toHaveLength(1);
expect(client.history.post[0].body).toEqual({
  email: 'test@example.com',
  password: 'password'
});

// Assert specific calls
client.expectRequest('POST', '/auth/login', {
  body: { email: 'test@example.com' }
});
```

### WebSocket Testing

```typescript
import { MockWebSocket } from '@janua/mock-api/testing';

const ws = new MockWebSocket('ws://localhost:8080');

// Simulate messages
ws.simulateMessage({ type: 'user.updated', data: userData });

// Assert messages sent
ws.send({ type: 'subscribe', channel: 'users' });
expect(ws.sentMessages).toContainEqual({
  type: 'subscribe',
  channel: 'users'
});
```

## 🌐 WebSocket Support

### WebSocket Server

```typescript
const server = new MockServer({
  websockets: true
});

// WebSocket available at ws://localhost:8080

// Server-side events
server.broadcast('user.created', userData);
server.sendToUser(userId, 'notification', data);
```

### WebSocket Client

```javascript
const ws = new WebSocket('ws://localhost:8080');

ws.on('open', () => {
  ws.send(JSON.stringify({
    type: 'auth',
    token: 'mock_token'
  }));
});

ws.on('message', (data) => {
  const message = JSON.parse(data);
  console.log('Received:', message);
});
```

## 🎨 UI Integration

### React Integration

```tsx
import { MockProvider } from '@janua/mock-api/react';

function App() {
  return (
    <MockProvider
      enabled={process.env.NODE_ENV === 'development'}
      config={{ delay: 500 }}
    >
      <YourApp />
    </MockProvider>
  );
}
```

### Vue Integration

```javascript
import { createMockPlugin } from '@janua/mock-api/vue';

const app = createApp(App);
app.use(createMockPlugin({
  enabled: process.env.NODE_ENV === 'development'
}));
```

## 📊 Load Testing

### Load Simulation

```typescript
import { LoadTester } from '@janua/mock-api/load';

const tester = new LoadTester({
  baseUrl: 'http://localhost:8080',
  concurrent: 100,
  duration: 60000, // 1 minute
  scenario: 'mixed' // 'read-heavy', 'write-heavy', 'mixed'
});

const results = await tester.run();
console.log('Results:', {
  requests: results.totalRequests,
  errors: results.errorCount,
  avgLatency: results.avgLatency,
  p95Latency: results.p95Latency
});
```

## 🛠️ CLI Usage

### Commands

```bash
# Start server
janua-mock start

# With options
janua-mock start --port 8080 --delay 500

# Load scenario
janua-mock scenario auth-error

# Generate data
janua-mock generate users --count 100

# Export data
janua-mock export ./data.json

# Import data
janua-mock import ./data.json

# Reset data
janua-mock reset
```

### Configuration File

```yaml
# .janua-mock.yml
server:
  port: 8080
  delay: 200
  errorRate: 0.05

data:
  seed: 12345
  users: 100
  organizations: 10

scenarios:
  - new-user
  - email-verification

persistence:
  enabled: true
  path: ./mock-data.json
```

## 🚀 Production-Like Features

### Rate Limiting

```typescript
server.enableRateLimit({
  windowMs: 15 * 60 * 1000, // 15 minutes
  max: 100 // limit each IP to 100 requests
});
```

### Authentication

```typescript
// JWT token validation
server.validateTokens({
  secret: 'mock-secret',
  issuer: 'janua-mock',
  audience: 'janua-app'
});
```

### CORS

```typescript
server.configureCORS({
  origin: ['http://localhost:3000', 'http://localhost:3001'],
  credentials: true,
  methods: ['GET', 'POST', 'PUT', 'DELETE']
});
```

## 📈 Monitoring

### Request Logging

```typescript
server.on('request', (req, res) => {
  console.log(`${req.method} ${req.path} - ${res.statusCode}`);
});

// Get statistics
const stats = server.getStats();
console.log('Total requests:', stats.totalRequests);
console.log('Error rate:', stats.errorRate);
console.log('Avg response time:', stats.avgResponseTime);
```

## 🛠️ Development

### Local Development

```bash
# Clone the repo
git clone https://github.com/madfam-io/janua.git

# Navigate to mock-api package
cd packages/mock-api

# Install dependencies
yarn install

# Start development server
yarn dev

# Run tests
yarn test

# Build package
yarn build
```

## 📚 Resources

- [Mock API Documentation](https://docs.janua.dev/testing/mock-api)
- [Testing Guide](https://docs.janua.dev/testing)
- [Scenario Examples](https://github.com/madfam-io/mock-api-scenarios)

## 🎯 Roadmap

### Current Version (0.1.0)
- ✅ Complete API mocking
- ✅ Data generation
- ✅ WebSocket support
- ✅ Testing utilities

### Next Release (0.2.0)
- [ ] GraphQL support
- [ ] Record/replay mode
- [ ] Chaos engineering
- [ ] Performance profiling

## 🤝 Contributing

See [Mock API Contributing Guide](../../docs/contributing/mock-api.md) for development guidelines.

## 📄 License

Part of the Janua platform. See [LICENSE](../../LICENSE) in the root directory.