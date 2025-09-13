// TypeScript SDK test setup
import '@testing-library/jest-dom';

// Mock environment variables for SDK testing
process.env.PLINTO_API_URL = 'http://localhost:4000';
process.env.PLINTO_ENV = 'test';

// Mock fetch for API calls
global.fetch = jest.fn();

// Mock console methods to reduce noise in tests
const originalWarn = console.warn;
const originalError = console.error;

beforeAll(() => {
  console.warn = jest.fn();
  console.error = jest.fn();
});

afterAll(() => {
  console.warn = originalWarn;
  console.error = originalError;
});

// Clean up after each test
afterEach(() => {
  jest.clearAllMocks();
  // Reset fetch mock
  (global.fetch as jest.Mock).mockClear();
});