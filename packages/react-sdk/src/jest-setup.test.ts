import * as jestSetupExports from './jest-setup'

describe('jest-setup', () => {
  it('should export expected functions', () => {
    expect(jestSetupExports).toBeDefined()
  })
})
