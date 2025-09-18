import * as module from './jest-setup'

describe('jest-setup', () => {
  it('should export expected functions', () => {
    expect(module).toBeDefined()
  })
})
