// Mock API responses and handlers
export const mockApiResponse = <T>(data: T, status = 200, ok = true) => ({
  ok,
  status,
  statusText: ok ? 'OK' : 'Error',
  json: () => Promise.resolve(data),
  text: () => Promise.resolve(JSON.stringify(data)),
});

// Authentication API mocks
export const authMocks = {
  login: {
    success: mockApiResponse({
      success: true,
      data: {
        token: 'mock-jwt-token',
        user: {
          id: 'user-123',
          email: 'test@example.com',
          name: 'Test User',
          verified: true,
        },
      },
    }),
    error: mockApiResponse(
      {
        success: false,
        error: 'Invalid credentials',
      },
      401,
      false
    ),
  },
  
  register: {
    success: mockApiResponse({
      success: true,
      data: {
        user: {
          id: 'user-123',
          email: 'test@example.com',
          name: 'Test User',
          verified: false,
        },
        verificationRequired: true,
      },
    }),
    error: mockApiResponse(
      {
        success: false,
        error: 'Email already exists',
      },
      409,
      false
    ),
  },
  
  verify: {
    success: mockApiResponse({
      success: true,
      data: {
        verified: true,
        user: {
          id: 'user-123',
          email: 'test@example.com',
          name: 'Test User',
          verified: true,
        },
      },
    }),
    error: mockApiResponse(
      {
        success: false,
        error: 'Invalid verification code',
      },
      400,
      false
    ),
  },
};

// Identity verification API mocks
export const identityMocks = {
  startVerification: {
    success: mockApiResponse({
      success: true,
      data: {
        verificationId: 'verification-123',
        status: 'pending',
        requiredDocuments: ['passport', 'drivers_license'],
      },
    }),
  },
  
  uploadDocument: {
    success: mockApiResponse({
      success: true,
      data: {
        documentId: 'doc-123',
        status: 'uploaded',
        analysis: {
          confidence: 0.95,
          valid: true,
        },
      },
    }),
  },
  
  getVerificationStatus: {
    pending: mockApiResponse({
      success: true,
      data: {
        verificationId: 'verification-123',
        status: 'pending',
        progress: 0.5,
      },
    }),
    completed: mockApiResponse({
      success: true,
      data: {
        verificationId: 'verification-123',
        status: 'verified',
        progress: 1.0,
        result: {
          identity: {
            firstName: 'John',
            lastName: 'Doe',
            dateOfBirth: '1990-01-01',
            nationality: 'US',
          },
          confidence: 0.98,
        },
      },
    }),
  },
};

// Edge verification API mocks
export const edgeMocks = {
  verify: {
    success: mockApiResponse({
      success: true,
      data: {
        verified: true,
        confidence: 0.96,
        timestamp: new Date().toISOString(),
      },
    }),
    error: mockApiResponse(
      {
        success: false,
        error: 'Verification failed',
        details: 'Document quality insufficient',
      },
      400,
      false
    ),
  },
};

// Admin API mocks
export const adminMocks = {
  getUsers: {
    success: mockApiResponse({
      success: true,
      data: {
        users: [
          {
            id: 'user-1',
            email: 'user1@example.com',
            name: 'User One',
            verified: true,
            createdAt: '2023-01-01T00:00:00Z',
          },
          {
            id: 'user-2',
            email: 'user2@example.com',
            name: 'User Two',
            verified: false,
            createdAt: '2023-01-02T00:00:00Z',
          },
        ],
        pagination: {
          total: 2,
          page: 1,
          limit: 10,
        },
      },
    }),
  },
  
  getVerifications: {
    success: mockApiResponse({
      success: true,
      data: {
        verifications: [
          {
            id: 'verification-1',
            userId: 'user-1',
            type: 'identity',
            status: 'verified',
            createdAt: '2023-01-01T01:00:00Z',
            completedAt: '2023-01-01T01:30:00Z',
          },
        ],
        pagination: {
          total: 1,
          page: 1,
          limit: 10,
        },
      },
    }),
  },
};

// Generic error responses
export const errorMocks = {
  unauthorized: mockApiResponse(
    {
      success: false,
      error: 'Unauthorized',
    },
    401,
    false
  ),
  forbidden: mockApiResponse(
    {
      success: false,
      error: 'Forbidden',
    },
    403,
    false
  ),
  notFound: mockApiResponse(
    {
      success: false,
      error: 'Not found',
    },
    404,
    false
  ),
  serverError: mockApiResponse(
    {
      success: false,
      error: 'Internal server error',
    },
    500,
    false
  ),
};