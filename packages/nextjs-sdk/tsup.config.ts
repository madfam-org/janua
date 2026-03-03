import { defineConfig } from 'tsup';

export default defineConfig({
  entry: {
    index: 'src/index.ts',
    'app/index': 'src/app/index.ts',
    middleware: 'src/middleware.ts',
    edge: 'src/edge.ts',
  },
  format: ['cjs', 'esm'],
  dts: true,
  splitting: false,
  sourcemap: true,
  clean: true,
  external: ['react', 'react-dom', 'next', '@janua/typescript-sdk', '@janua/ui', 'jose'],
  noExternal: [],
  target: 'es2020',
});