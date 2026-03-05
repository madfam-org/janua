import { defineConfig } from 'tsup';

export default defineConfig({
  entry: {
    index: 'src/index.ts',
    nuxt: 'src/nuxt.ts',
  },
  format: ['cjs', 'esm'],
  dts: true,
  splitting: false,
  sourcemap: true,
  clean: true,
  external: ['vue', '@janua/typescript-sdk', '@janua/ui', '@nuxt/kit', '#app'],
  target: 'es2020',
});
