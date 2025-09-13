import { render, RenderOptions } from '@testing-library/react';
import { ReactElement } from 'react';
import userEvent from '@testing-library/user-event';

// Re-export everything
export * from '@testing-library/react';

// Custom render function with providers
export const renderWithProviders = (
  ui: ReactElement,
  options?: Omit<RenderOptions, 'wrapper'>
) => {
  return {
    user: userEvent.setup(),
    ...render(ui, options),
  };
};

// Custom matcher for testing async components
export const waitForAsync = (timeout = 3000) => {
  return new Promise(resolve => setTimeout(resolve, timeout));
};

// Mock data generators
export const createMockUser = (overrides: any = {}) => ({
  id: 'test-user-id',
  email: 'test@example.com',
  name: 'Test User',
  verified: true,
  ...overrides,
});

export const createMockVerification = (overrides: any = {}) => ({
  id: 'test-verification-id',
  userId: 'test-user-id',
  type: 'identity',
  status: 'verified',
  createdAt: new Date().toISOString(),
  ...overrides,
});

// Environment helpers
export const mockEnvironment = (env: Record<string, string>) => {
  const originalEnv = process.env;
  beforeEach(() => {
    process.env = { ...originalEnv, ...env };
  });
  afterEach(() => {
    process.env = originalEnv;
  });
};

// Local storage mock
export const mockLocalStorage = () => {
  const localStorageMock = {
    getItem: jest.fn(),
    setItem: jest.fn(),
    removeItem: jest.fn(),
    clear: jest.fn(),
  };
  
  beforeEach(() => {
    Object.defineProperty(window, 'localStorage', {
      value: localStorageMock,
      writable: true,
    });
  });
  
  return localStorageMock;
};

// Fetch mock helper
export const mockFetch = (response: any, ok = true) => {
  const mockResponse = {
    ok,
    status: ok ? 200 : 400,
    json: jest.fn().mockResolvedValue(response),
    text: jest.fn().mockResolvedValue(JSON.stringify(response)),
  };
  
  (global.fetch as jest.Mock).mockResolvedValue(mockResponse);
  
  return mockResponse;
};

// Error boundary test helper
export const expectToThrow = async (fn: () => Promise<void>) => {
  let error: Error | undefined;
  try {
    await fn();
  } catch (e) {
    error = e as Error;
  }
  expect(error).toBeDefined();
  return error;
};

// Component prop validation
export const testComponentProps = (
  Component: React.ComponentType<any>,
  defaultProps: any,
  testCases: Array<{
    props: any;
    expectedResult: string | RegExp;
    description: string;
  }>
) => {
  testCases.forEach(({ props, expectedResult, description }) => {
    it(description, () => {
      const { container } = render(<Component {...defaultProps} {...props} />);
      if (typeof expectedResult === 'string') {
        expect(container).toHaveTextContent(expectedResult);
      } else {
        expect(container.textContent).toMatch(expectedResult);
      }
    });
  });
};