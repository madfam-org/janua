"use strict";
// Setup for node environment tests
// This file is loaded only for tests that require node environment
// It doesn't set up browser-specific globals
// Only set up minimal required mocks for node environment
if (typeof global !== 'undefined') {
    // Mock fetch for Node environment
    global.fetch = jest.fn();
    // Set test environment variable
    process.env.NODE_ENV = 'test';
    process.env.PLINTO_ENV = 'test';
}
// Clean up after each test
afterEach(() => {
    jest.clearAllMocks();
});
//# sourceMappingURL=setup-node.js.map