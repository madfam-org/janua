# @janua/core

> **Shared core utilities and business logic** for the Janua platform

**Version:** 0.1.0 · **Type:** Internal Package · **Status:** Production Ready

## 📋 Overview

@janua/core provides the foundational utilities, types, constants, and business logic shared across all Janua applications and services. This package ensures consistency, reduces duplication, and centralizes critical platform functionality.

## 🚀 Quick Start

### Installation

```bash
# From within a Janua workspace
yarn add @janua/core

# External usage (not recommended)
npm install @janua/core
```

### Basic Usage

```typescript
import {
  validateEmail,
  hashPassword,
  generateId,
  JanuaError,
  Logger
} from '@janua/core';

// Use validation utilities
if (!validateEmail(email)) {
  throw new JanuaError('Invalid email format', 'VALIDATION_ERROR');
}

// Use crypto utilities
const hashedPassword = await hashPassword(plainPassword);

// Use ID generation
const userId = generateId('user');

// Use logger
const logger = new Logger('auth-service');
logger.info('User authenticated', { userId });
```

## 🏗️ Architecture

### Package Structure

```
packages/core/
├── src/
│   ├── constants/          # Platform constants
│   │   ├── errors.ts      # Error codes and messages
│   │   ├── limits.ts      # Rate limits, quotas
│   │   ├── regex.ts       # Validation patterns
│   │   └── enums.ts       # Platform enumerations
│   ├── types/             # TypeScript definitions
│   │   ├── auth.ts        # Authentication types
│   │   ├── user.ts        # User-related types
│   │   ├── organization.ts # Organization types
│   │   ├── api.ts         # API response types
│   │   └── common.ts      # Shared types
│   ├── utils/            # Utility functions
│   │   ├── validation.ts # Input validation
│   │   ├── crypto.ts     # Cryptographic utilities
│   │   ├── datetime.ts   # Date/time helpers
│   │   ├── id.ts         # ID generation
│   │   ├── format.ts     # Formatting utilities
│   │   └── async.ts      # Async helpers
│   ├── errors/          # Error handling
│   │   ├── base.ts      # Base error class
│   │   ├── auth.ts      # Auth-specific errors
│   │   ├── validation.ts # Validation errors
│   │   └── api.ts       # API errors
│   ├── services/        # Core services
│   │   ├── logger.ts    # Logging service
│   │   ├── metrics.ts   # Metrics collection
│   │   ├── feature-flags.ts # Feature toggles
│   │   └── audit.ts     # Audit logging
│   ├── middleware/      # Shared middleware
│   │   ├── auth.ts      # Authentication
│   │   ├── rate-limit.ts # Rate limiting
│   │   ├── validation.ts # Request validation
│   │   └── cors.ts      # CORS configuration
│   └── index.ts        # Main export
├── tests/             # Test files
├── dist/             # Built files
└── package.json     # Package config
```

### Core Architecture

```
┌─────────────────────────────────────┐
│            @janua/core             │
├─────────────────────────────────────┤
│  Constants & Types                  │
│  ├─ Error Definitions               │
│  ├─ Platform Limits                 │
│  └─ TypeScript Types                │
├─────────────────────────────────────┤
│  Utilities                          │
│  ├─ Validation & Formatting         │
│  ├─ Cryptography & Security         │
│  └─ ID Generation & Datetime        │
├─────────────────────────────────────┤
│  Services                           │
│  ├─ Logging & Metrics               │
│  ├─ Feature Flags                   │
│  └─ Audit Trail                     │
└─────────────────────────────────────┘
```

## 🔧 Core Utilities

### Validation Utilities

```typescript
import {
  validateEmail,
  validatePassword,
  validatePhone,
  validateUrl,
  sanitizeInput
} from '@janua/core/utils';

// Email validation
const isValid = validateEmail('user@example.com');

// Password strength validation
const passwordCheck = validatePassword('SecurePass123!');
// Returns: { valid: true, strength: 'strong', issues: [] }

// Phone number validation (international)
const phoneValid = validatePhone('+1234567890');

// URL validation
const urlValid = validateUrl('https://example.com');

// Input sanitization
const clean = sanitizeInput('<script>alert("xss")</script>');
```

### Cryptographic Utilities

```typescript
import {
  hashPassword,
  verifyPassword,
  generateToken,
  generateSecureCode,
  encrypt,
  decrypt
} from '@janua/core/crypto';

// Password hashing (Argon2)
const hash = await hashPassword('plaintext');
const isMatch = await verifyPassword('plaintext', hash);

// Token generation
const token = generateToken(32); // 32 bytes, URL-safe
const code = generateSecureCode(6); // 6-digit code

// Encryption (AES-256-GCM)
const encrypted = await encrypt(data, key);
const decrypted = await decrypt(encrypted, key);
```

### ID Generation

```typescript
import {
  generateId,
  generateUuid,
  generateSlug,
  parseId
} from '@janua/core/utils';

// Prefixed IDs
const userId = generateId('user'); // user_ks8d7f9a8s7df
const orgId = generateId('org');   // org_j3k4l5m6n7o8

// UUID v4
const uuid = generateUuid(); // 550e8400-e29b-41d4-a716-446655440000

// URL-safe slugs
const slug = generateSlug('My Organization Name'); // my-organization-name

// Parse ID components
const { prefix, id, timestamp } = parseId('user_ks8d7f9a8s7df');
```

### Date/Time Utilities

```typescript
import {
  formatDate,
  parseDate,
  addDays,
  isExpired,
  getTimezone
} from '@janua/core/datetime';

// Date formatting
const formatted = formatDate(new Date(), 'YYYY-MM-DD HH:mm:ss');

// Date parsing
const date = parseDate('2024-01-01', 'YYYY-MM-DD');

// Date manipulation
const future = addDays(new Date(), 30);

// Expiration checking
const expired = isExpired(tokenExpiry);

// Timezone detection
const tz = getTimezone(); // 'America/New_York'
```

## 📊 Types & Interfaces

### Authentication Types

```typescript
import type {
  User,
  Session,
  AuthTokens,
  AuthProvider,
  MFAMethod
} from '@janua/core/types';

interface User {
  id: string;
  email: string;
  name?: string;
  avatar?: string;
  emailVerified: boolean;
  createdAt: Date;
  updatedAt: Date;
  metadata?: Record<string, any>;
}

interface Session {
  id: string;
  userId: string;
  deviceInfo: DeviceInfo;
  ipAddress: string;
  expiresAt: Date;
  lastActiveAt: Date;
}

interface AuthTokens {
  accessToken: string;
  refreshToken: string;
  expiresIn: number;
  tokenType: 'Bearer';
}
```

### API Response Types

```typescript
import type {
  ApiResponse,
  PaginatedResponse,
  ErrorResponse
} from '@janua/core/types';

interface ApiResponse<T> {
  success: boolean;
  data?: T;
  error?: ErrorResponse;
  meta?: Record<string, any>;
}

interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  pageSize: number;
  hasMore: boolean;
}

interface ErrorResponse {
  code: string;
  message: string;
  details?: Record<string, any>;
  timestamp: string;
  requestId: string;
}
```

## 🛠️ Core Services

### Logger Service

```typescript
import { Logger } from '@janua/core/services';

const logger = new Logger('auth-service', {
  level: 'info',
  format: 'json',
  destination: 'stdout'
});

// Structured logging
logger.info('User authenticated', {
  userId: 'user_123',
  method: 'password',
  ip: '192.168.1.1'
});

logger.error('Authentication failed', {
  error: error.message,
  stack: error.stack,
  userId: 'user_123'
});

// Child loggers
const requestLogger = logger.child({ requestId: 'req_456' });
```

### Metrics Service

```typescript
import { Metrics } from '@janua/core/services';

const metrics = new Metrics({
  service: 'auth-api',
  environment: 'production'
});

// Counter metrics
metrics.increment('auth.attempts');
metrics.increment('auth.success', { provider: 'google' });

// Gauge metrics
metrics.gauge('active.sessions', 150);

// Histogram metrics
metrics.histogram('request.duration', 235, { endpoint: '/auth/login' });

// Timing metrics
const timer = metrics.timer('database.query');
// ... perform query
timer.end({ query: 'SELECT * FROM users' });
```

### Feature Flags

```typescript
import { FeatureFlags } from '@janua/core/services';

const flags = new FeatureFlags({
  provider: 'local',
  defaults: {
    'new-auth-flow': false,
    'passkeys': true
  }
});

// Check feature flag
if (await flags.isEnabled('passkeys', { userId })) {
  // Enable passkey authentication
}

// Get all flags for user
const userFlags = await flags.getAllFlags({ userId });

// Update flag value
await flags.setFlag('new-auth-flow', true, {
  rolloutPercentage: 50
});
```

### Audit Service

```typescript
import { AuditLog } from '@janua/core/services';

const audit = new AuditLog({
  storage: 'database',
  retention: 90 // days
});

// Log audit event
await audit.log({
  actor: userId,
  action: 'user.update',
  resource: 'user_456',
  changes: {
    name: { from: 'John', to: 'Jane' }
  },
  ip: request.ip,
  userAgent: request.headers['user-agent']
});

// Query audit logs
const logs = await audit.query({
  actor: userId,
  startDate: new Date('2024-01-01'),
  endDate: new Date()
});
```

## 🚨 Error Handling

### Custom Error Classes

```typescript
import {
  JanuaError,
  ValidationError,
  AuthenticationError,
  AuthorizationError,
  NotFoundError,
  ConflictError,
  RateLimitError
} from '@janua/core/errors';

// Base error
throw new JanuaError('Something went wrong', 'INTERNAL_ERROR', {
  statusCode: 500,
  details: { reason: 'Database connection failed' }
});

// Validation error
throw new ValidationError('Invalid input', {
  fields: {
    email: 'Invalid email format',
    password: 'Password too weak'
  }
});

// Authentication error
throw new AuthenticationError('Invalid credentials');

// Rate limit error
throw new RateLimitError('Too many requests', {
  retryAfter: 60,
  limit: 100
});
```

### Error Constants

```typescript
import { ErrorCodes, ErrorMessages } from '@janua/core/constants';

// Error codes
ErrorCodes.VALIDATION_ERROR // 'VALIDATION_ERROR'
ErrorCodes.AUTH_FAILED     // 'AUTH_FAILED'
ErrorCodes.NOT_FOUND       // 'NOT_FOUND'

// Error messages
ErrorMessages[ErrorCodes.AUTH_FAILED] // 'Authentication failed'
```

## 🔒 Security Utilities

### Input Sanitization

```typescript
import {
  sanitizeHtml,
  escapeHtml,
  preventSqlInjection,
  validateCsrfToken
} from '@janua/core/security';

// HTML sanitization
const safe = sanitizeHtml(userInput);

// HTML escaping
const escaped = escapeHtml('<script>alert("xss")</script>');

// SQL injection prevention
const query = preventSqlInjection(userQuery);

// CSRF validation
const isValid = validateCsrfToken(token, session);
```

### Rate Limiting

```typescript
import { RateLimiter } from '@janua/core/middleware';

const limiter = new RateLimiter({
  windowMs: 15 * 60 * 1000, // 15 minutes
  max: 100, // limit each IP to 100 requests
  message: 'Too many requests',
  keyGenerator: (req) => req.ip
});

// Apply to routes
app.use('/api', limiter.middleware());
```

## 📏 Constants & Limits

### Platform Limits

```typescript
import { Limits } from '@janua/core/constants';

Limits.MAX_EMAIL_LENGTH      // 254
Limits.MAX_PASSWORD_LENGTH   // 128
Limits.MIN_PASSWORD_LENGTH   // 8
Limits.MAX_NAME_LENGTH       // 100
Limits.MAX_UPLOAD_SIZE       // 10 * 1024 * 1024 (10MB)
Limits.MAX_API_REQUESTS      // 1000 per hour
Limits.SESSION_DURATION      // 24 * 60 * 60 (24 hours)
```

### Regex Patterns

```typescript
import { Patterns } from '@janua/core/constants';

Patterns.EMAIL     // Email validation regex
Patterns.PASSWORD  // Password complexity regex
Patterns.PHONE     // International phone regex
Patterns.URL       // URL validation regex
Patterns.UUID      // UUID v4 regex
```

## 🧪 Testing Utilities

### Test Helpers

```typescript
import {
  createMockUser,
  createMockSession,
  createMockOrganization,
  setupTestDatabase,
  cleanupTestData
} from '@janua/core/testing';

// Create mock data
const user = createMockUser({
  email: 'test@example.com'
});

const session = createMockSession({
  userId: user.id
});

// Test database
const db = await setupTestDatabase();
// ... run tests
await cleanupTestData(db);
```

## 📦 Bundle Information

### Package Exports

```javascript
// Main export
import * from '@janua/core';

// Specific imports for tree shaking
import { validateEmail } from '@janua/core/utils';
import { Logger } from '@janua/core/services';
import { JanuaError } from '@janua/core/errors';
import type { User } from '@janua/core/types';
```

### Bundle Sizes

| Export | Size | Gzipped |
|--------|------|---------|
| Full | 85KB | 22KB |
| Utils only | 25KB | 8KB |
| Types only | 0KB | 0KB |
| Services | 35KB | 10KB |

## 🛠️ Development

### Local Development

```bash
# Clone the repo
git clone https://github.com/madfam-io/janua.git

# Navigate to core package
cd packages/core

# Install dependencies
yarn install

# Run tests
yarn test

# Build package
yarn build

# Watch mode
yarn dev
```

### Testing

```bash
# Run all tests
yarn test

# Run specific test suite
yarn test validation

# Coverage report
yarn test:coverage

# Watch mode
yarn test:watch
```

## 📚 Resources

- [Core API Documentation](https://docs.janua.dev/packages/core)
- [Type Definitions](https://docs.janua.dev/packages/core/types)
- [Security Guide](https://docs.janua.dev/security)
- [Contributing Guide](../../docs/contributing/core.md)

## 🎯 Roadmap

### Current Version (0.1.0)
- ✅ Core utilities and helpers
- ✅ Type definitions
- ✅ Error handling
- ✅ Basic services

### Next Release (0.2.0)
- [ ] Event bus system
- [ ] Caching utilities
- [ ] Advanced metrics
- [ ] Plugin system

## 🤝 Contributing

See [Core Contributing Guide](../../docs/contributing/core.md) for development guidelines.

## 📄 License

Part of the Janua platform. See [LICENSE](../../LICENSE) in the root directory.