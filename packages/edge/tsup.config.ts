import { defineConfig } from 'tsup';

export default defineConfig({
  entry: ['src/index.ts'],
  format: ['cjs', 'esm'],
  dts: true,
  splitting: false,
  sourcemap: true,
  clean: true,
  minify: true,
  target: 'es2020',
  platform: 'neutral', // Works in both Node.js and browser/edge environments
  external: [],
  noExternal: ['jose'], // Bundle jose for edge environments
});