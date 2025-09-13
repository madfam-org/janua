// Test data fixtures for consistent testing

// User fixtures
export const userFixtures = {
  verified: {
    id: 'user-verified-123',
    email: 'verified@example.com',
    name: 'Verified User',
    verified: true,
    createdAt: '2023-01-01T00:00:00Z',
    updatedAt: '2023-01-01T00:00:00Z',
    profile: {
      firstName: 'Verified',
      lastName: 'User',
      dateOfBirth: '1990-01-01',
      nationality: 'US',
    },
  },
  
  unverified: {
    id: 'user-unverified-123',
    email: 'unverified@example.com',
    name: 'Unverified User',
    verified: false,
    createdAt: '2023-01-02T00:00:00Z',
    updatedAt: '2023-01-02T00:00:00Z',
    profile: null,
  },
  
  admin: {
    id: 'admin-123',
    email: 'admin@example.com',
    name: 'Admin User',
    verified: true,
    role: 'admin',
    createdAt: '2023-01-01T00:00:00Z',
    updatedAt: '2023-01-01T00:00:00Z',
    permissions: ['read', 'write', 'admin'],
  },
};

// Verification fixtures
export const verificationFixtures = {
  pending: {
    id: 'verification-pending-123',
    userId: 'user-unverified-123',
    type: 'identity',
    status: 'pending',
    progress: 0.3,
    createdAt: '2023-01-02T01:00:00Z',
    updatedAt: '2023-01-02T01:15:00Z',
    documents: [
      {
        id: 'doc-passport-123',
        type: 'passport',
        status: 'uploaded',
        url: 'https://example.com/docs/passport.jpg',
      },
    ],
  },
  
  verified: {
    id: 'verification-verified-123',
    userId: 'user-verified-123',
    type: 'identity',
    status: 'verified',
    progress: 1.0,
    createdAt: '2023-01-01T01:00:00Z',
    updatedAt: '2023-01-01T01:30:00Z',
    completedAt: '2023-01-01T01:30:00Z',
    result: {
      identity: {
        firstName: 'Verified',
        lastName: 'User',
        dateOfBirth: '1990-01-01',
        nationality: 'US',
      },
      confidence: 0.98,
      checks: {
        documentValid: true,
        facialMatch: true,
        livenessCheck: true,
      },
    },
    documents: [
      {
        id: 'doc-passport-123',
        type: 'passport',
        status: 'verified',
        url: 'https://example.com/docs/passport.jpg',
        analysis: {
          confidence: 0.97,
          valid: true,
          extractedData: {
            firstName: 'Verified',
            lastName: 'User',
            dateOfBirth: '1990-01-01',
            nationality: 'US',
            documentNumber: 'P123456789',
            expiryDate: '2030-01-01',
          },
        },
      },
    ],
  },
  
  failed: {
    id: 'verification-failed-123',
    userId: 'user-unverified-123',
    type: 'identity',
    status: 'failed',
    progress: 0.8,
    createdAt: '2023-01-02T02:00:00Z',
    updatedAt: '2023-01-02T02:30:00Z',
    completedAt: '2023-01-02T02:30:00Z',
    error: {
      code: 'DOCUMENT_INVALID',
      message: 'Document quality insufficient for verification',
      details: {
        issues: ['blurry_image', 'incomplete_document'],
        confidence: 0.23,
      },
    },
    documents: [
      {
        id: 'doc-license-123',
        type: 'drivers_license',
        status: 'failed',
        url: 'https://example.com/docs/license.jpg',
        analysis: {
          confidence: 0.23,
          valid: false,
          issues: ['blurry_image', 'incomplete_document'],
        },
      },
    ],
  },
};

// Document fixtures
export const documentFixtures = {
  passport: {
    id: 'doc-passport-123',
    type: 'passport',
    fileName: 'passport.jpg',
    fileSize: 1024000,
    mimeType: 'image/jpeg',
    uploadedAt: '2023-01-01T01:00:00Z',
    status: 'uploaded',
    metadata: {
      width: 1920,
      height: 1080,
      format: 'JPEG',
    },
  },
  
  driversLicense: {
    id: 'doc-license-123',
    type: 'drivers_license',
    fileName: 'license.jpg',
    fileSize: 850000,
    mimeType: 'image/jpeg',
    uploadedAt: '2023-01-02T01:00:00Z',
    status: 'uploaded',
    metadata: {
      width: 1600,
      height: 900,
      format: 'JPEG',
    },
  },
  
  selfie: {
    id: 'doc-selfie-123',
    type: 'selfie',
    fileName: 'selfie.jpg',
    fileSize: 512000,
    mimeType: 'image/jpeg',
    uploadedAt: '2023-01-01T01:10:00Z',
    status: 'uploaded',
    metadata: {
      width: 1080,
      height: 1350,
      format: 'JPEG',
    },
  },
};

// JWT token fixtures
export const tokenFixtures = {
  valid: {
    token: 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJ1c2VyLXZlcmlmaWVkLTEyMyIsImVtYWlsIjoidmVyaWZpZWRAZXhhbXBsZS5jb20iLCJ2ZXJpZmllZCI6dHJ1ZSwiaWF0IjoxNjQwOTk1MjAwLCJleHAiOjE2NDA5OTg4MDB9',
    decoded: {
      sub: 'user-verified-123',
      email: 'verified@example.com',
      verified: true,
      iat: 1640995200,
      exp: 1640998800,
    },
  },
  
  expired: {
    token: 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJ1c2VyLXZlcmlmaWVkLTEyMyIsImVtYWlsIjoidmVyaWZpZWRAZXhhbXBsZS5jb20iLCJ2ZXJpZmllZCI6dHJ1ZSwiaWF0IjoxNjQwOTkxNjAwLCJleHAiOjE2NDA5OTUyMDB9',
    decoded: {
      sub: 'user-verified-123',
      email: 'verified@example.com',
      verified: true,
      iat: 1640991600,
      exp: 1640995200, // expired
    },
  },
  
  invalid: {
    token: 'invalid-token-format',
  },
};

// Configuration fixtures
export const configFixtures = {
  development: {
    apiUrl: 'http://localhost:4000',
    environment: 'development',
    debug: true,
    features: {
      enableAnalytics: false,
      enableLogging: true,
      enableMocks: true,
    },
  },
  
  production: {
    apiUrl: 'https://api.plinto.com',
    environment: 'production',
    debug: false,
    features: {
      enableAnalytics: true,
      enableLogging: false,
      enableMocks: false,
    },
  },
  
  test: {
    apiUrl: 'http://localhost:3000/api',
    environment: 'test',
    debug: false,
    features: {
      enableAnalytics: false,
      enableLogging: false,
      enableMocks: true,
    },
  },
};

// Error fixtures
export const errorFixtures = {
  validation: {
    code: 'VALIDATION_ERROR',
    message: 'Validation failed',
    errors: [
      {
        field: 'email',
        message: 'Invalid email format',
      },
      {
        field: 'password',
        message: 'Password must be at least 8 characters',
      },
    ],
  },
  
  authentication: {
    code: 'AUTHENTICATION_ERROR',
    message: 'Invalid credentials',
  },
  
  authorization: {
    code: 'AUTHORIZATION_ERROR',
    message: 'Insufficient permissions',
  },
  
  notFound: {
    code: 'NOT_FOUND',
    message: 'Resource not found',
  },
  
  serverError: {
    code: 'INTERNAL_ERROR',
    message: 'Internal server error',
    stack: process.env.NODE_ENV === 'development' ? 'Error stack trace...' : undefined,
  },
};