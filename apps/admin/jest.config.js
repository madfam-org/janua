// Runner choice: these tests are written for jest (jest.mock, jest.fn).
// packages/ui is on vitest because its files import from 'vitest'. Neither set
// can adopt the other's runner without rewriting the test files, so the split
// is deliberate.
const createNextAppJestConfig = require('../../jest.next-app')

module.exports = createNextAppJestConfig({
  testEnvironmentOptions: { url: 'https://admin.janua.dev' },
  setupFilesAfterEnv: ['<rootDir>/../../tests/setup.js', '<rootDir>/console-runtime.setup.ts'],
})
