import { defineConfig } from 'tsup';

export default defineConfig({
  entry: ['src/index.ts'],
  format: ['cjs', 'esm'],
  dts: false,
  splitting: false,
  sourcemap: false,
  clean: true,
  external: ['react', 'react-dom', '@plinto/typescript-sdk'],
  onSuccess: 'echo "Build completed successfully"'
});