import { defineConfig } from 'vitest/config';
import { resolve } from 'path';

const REACT_DOM_18 = resolve(
  __dirname,
  '../../node_modules/.pnpm/react-dom@18.3.1_react@18.3.1/node_modules/react-dom'
);

export default defineConfig({
  resolve: {
    alias: {
      // Force react-dom 18.3.1 (matches react peer); the package's own
      // node_modules symlink points to 19 due to pnpm hoisting.
      'react-dom/client': resolve(REACT_DOM_18, 'client.js'),
      'react-dom/test-utils': resolve(REACT_DOM_18, 'test-utils.js'),
      'react-dom': REACT_DOM_18,
    },
  },
  test: {
    environment: 'jsdom',
    globals: true,
    include: ['src/**/*.test.ts', 'src/**/*.test.tsx'],
  },
});
