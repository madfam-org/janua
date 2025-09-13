// Standard Jest configuration template for Next.js apps
module.exports = {
  preset: '../../jest.preset.js',
  testEnvironment: 'jsdom',
  displayName: 'APP_NAME', // Replace with actual app name
  
  // Setup files
  setupFilesAfterEnv: [
    '<rootDir>/../../tests/setup.js',
    '<rootDir>/__tests__/setup.ts', // App-specific setup
  ],
  
  // Module name mapping for Next.js apps
  moduleNameMapper: {
    '^@/(.*)$': '<rootDir>/$1',
    '^@plinto/(.*)$': '<rootDir>/../../packages/$1/src',
    '\\.(css|less|scss|sass)$': 'identity-obj-proxy',
    '\\.(jpg|jpeg|png|gif|eot|otf|webp|svg|ttf|woff|woff2|mp4|webm|wav|mp3|m4a|aac|oga)$': 'jest-transform-stub',
  },
  
  // Test patterns
  testMatch: [
    '<rootDir>/app/**/__tests__/**/*.[jt]s?(x)',
    '<rootDir>/app/**/?(*.)+(spec|test).[jt]s?(x)',
    '<rootDir>/components/**/__tests__/**/*.[jt]s?(x)',
    '<rootDir>/components/**/?(*.)+(spec|test).[jt]s?(x)',
    '<rootDir>/lib/**/__tests__/**/*.[jt]s?(x)',
    '<rootDir>/lib/**/?(*.)+(spec|test).[jt]s?(x)',
    '<rootDir>/__tests__/**/*.[jt]s?(x)',
  ],
  
  // Ignore patterns
  testPathIgnorePatterns: [
    '/node_modules/',
    '/.next/',
    '/dist/',
    '/build/',
  ],
  
  // Coverage configuration
  collectCoverageFrom: [
    'app/**/*.{js,jsx,ts,tsx}',
    'components/**/*.{js,jsx,ts,tsx}',
    'lib/**/*.{js,jsx,ts,tsx}',
    '!**/*.d.ts',
    '!**/*.stories.{js,jsx,ts,tsx}',
    '!**/layout.{js,jsx,ts,tsx}', // Usually just wrappers
    '!**/loading.{js,jsx,ts,tsx}', // Usually simple components
    '!**/not-found.{js,jsx,ts,tsx}', // Usually simple components
  ],
  
  coverageThreshold: {
    global: {
      branches: 75, // Slightly lower for apps due to Next.js boilerplate
      functions: 75,
      lines: 75,
      statements: 75,
    },
  },
  
  // Transform configuration
  transform: {
    '^.+\\.(ts|tsx)$': ['ts-jest', {
      tsconfig: '<rootDir>/tsconfig.json',
      isolatedModules: true,
    }],
  },
  
  // Module resolution
  moduleFileExtensions: ['ts', 'tsx', 'js', 'jsx', 'json'],
  
  // Test environment options
  testEnvironmentOptions: {
    customExportConditions: [''],
  },
};