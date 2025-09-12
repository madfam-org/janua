import { defineConfig } from 'tsup';

export default defineConfig({
  entry: {
    index: 'src/index.ts',
    'app/index': 'src/app/index.ts',
    middleware: 'src/middleware.ts',
  },
  format: ['cjs', 'esm'],
  dts: true,
  splitting: false,
  sourcemap: true,
  clean: true,
  external: ['react', 'react-dom', 'next', '@plinto/js'],
  noExternal: [],
  target: 'es2020',
});