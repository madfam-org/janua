// The previous config declared `preset: 'ts-jest'`, but ts-jest is not a
// dependency of this app and pnpm's strict node_modules meant it could never
// resolve -- so jest failed before collecting a single test. There was also no
// `test` script, so nothing invoked it either way.
//
// Runner choice: these tests are written for jest (jest.mock, jest.fn,
// jest.MockedFunction). packages/ui is on vitest because its files import from
// 'vitest'. Neither set can adopt the other's runner without rewriting the test
// files, so the split is deliberate.
const createNextAppJestConfig = require('../../jest.next-app')

module.exports = createNextAppJestConfig({
  testEnvironmentOptions: { url: 'https://app.janua.dev' },
  setupFilesAfterEnv: ['<rootDir>/../../tests/setup.js', '<rootDir>/console-runtime.setup.ts'],
})
