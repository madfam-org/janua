// Jest configuration for TypeScript SDK package
module.exports = {
  preset: '../../jest.preset.js',
  testEnvironment: 'jsdom',
  displayName: 'typescript-sdk',
  
  // Setup files
  setupFilesAfterEnv: [
    '<rootDir>/../../tests/setup.js',
    '<rootDir>/src/__tests__/setup.ts',
  ],
  
  // Module name mapping
  moduleNameMapper: {
    '^@/(.*)$': '<rootDir>/src/$1',
    '^@plinto/(.*)$': '<rootDir>/../../packages/$1/src',
    '\\.(css|less|scss|sass)$': 'identity-obj-proxy',
  },
  
  // Test patterns - exclude setup files
  testMatch: [
    '<rootDir>/src/**/__tests__/**/*.[jt]s?(x)',
    '<rootDir>/src/**/?(*.)+(spec|test).[jt]s?(x)',
  ],
  
  // Ignore patterns
  testPathIgnorePatterns: [
    '/node_modules/',
    '/dist/',
    '/build/',
    '/__tests__/setup\.ts$',
    '/__tests__/setup-node\.ts$',
  ],
  
  // Coverage configuration
  collectCoverageFrom: [
    'src/**/*.{js,jsx,ts,tsx}',
    '!src/**/*.d.ts',
    '!src/**/index.{js,jsx,ts,tsx}',
    '!src/**/__tests__/setup.{js,ts}',
  ],
  
  coverageThreshold: {
    global: {
      branches: 80,
      functions: 80,
      lines: 80,
      statements: 80,
    },
  },
  
  // Transform configuration
  transform: {
    '^.+\\.(ts|tsx)$': ['ts-jest', {
      tsconfig: '<rootDir>/tsconfig.json',
    }],
  },
};