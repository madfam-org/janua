module.exports = {
  projects: [
    '<rootDir>/apps/*/jest.config.{js,cjs}',
    '<rootDir>/packages/*/jest.config.{js,cjs}',
  ],
  collectCoverageFrom: [
    '**/*.{js,jsx,ts,tsx}',
    '!**/*.d.ts',
    '!**/node_modules/**',
    '!**/.next/**',
    '!**/coverage/**',
    '!**/jest.config.js',
    '!**/next.config.js',
    '!**/postcss.config.js',
    '!**/tailwind.config.{js,ts}',
    '!**/dist/**',
    '!**/build/**',
  ],
  coverageThreshold: {
    global: {
      branches: 100,
      functions: 100,
      lines: 100,
      statements: 100,
    },
  },
  testMatch: [
    '**/__tests__/**/*.[jt]s?(x)',
    '**/?(*.)+(spec|test).[jt]s?(x)',
  ],
  testPathIgnorePatterns: [
    '/node_modules/',
    '/.next/',
    '/dist/',
    '/build/',
  ],
  moduleNameMapper: {
    '^@/(.*)$': '<rootDir>/$1',
    '^@plinto/(.*)$': '<rootDir>/packages/$1/src',
    '\\.(css|less|scss|sass)$': 'identity-obj-proxy',
    '\\.(jpg|jpeg|png|gif|eot|otf|webp|svg|ttf|woff|woff2|mp4|webm|wav|mp3|m4a|aac|oga)$': '<rootDir>/tests/__mocks__/fileMock.js',
  },
  setupFilesAfterEnv: ['<rootDir>/tests/setup.js'],
  testEnvironment: 'jsdom',
  verbose: true,
  bail: false,
  coverageReporters: ['text', 'lcov', 'html', 'json-summary'],
  reporters: [
    'default',
    ['jest-junit', {
      outputDirectory: './coverage',
      outputName: 'junit.xml',
    }],
  ],
  maxWorkers: '50%',
  testTimeout: 10000,
};