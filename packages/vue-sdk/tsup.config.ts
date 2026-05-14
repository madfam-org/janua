import { createHash } from 'node:crypto';
import { readFile } from 'node:fs/promises';
import { basename } from 'node:path';
import { compileScript, parse } from '@vue/compiler-sfc';
import { defineConfig } from 'tsup';

const vueSfcPlugin = () => ({
  name: 'janua-vue-sfc',
  setup(build: {
    onLoad: (
      options: { filter: RegExp },
      callback: (args: { path: string }) => Promise<{ contents: string; loader: 'ts' }>,
    ) => void;
  }) {
    build.onLoad({ filter: /\.vue$/ }, async ({ path: filename }) => {
      const source = await readFile(filename, 'utf8');
      const { descriptor, errors } = parse(source, { filename });

      if (errors.length > 0) {
        throw new Error(
          `Failed to parse ${filename}: ${errors.map((error) => String(error)).join('; ')}`,
        );
      }

      const id = createHash('sha256').update(filename).digest('hex').slice(0, 8);
      const compiled = compileScript(descriptor, {
        id,
        inlineTemplate: true,
        templateOptions: {
          filename,
          compilerOptions: {
            scopeId: descriptor.styles.some((style) => style.scoped) ? `data-v-${id}` : undefined,
          },
        },
      });

      if (!compiled.content.includes('export default')) {
        throw new Error(`Expected ${filename} to compile to a default Vue component export`);
      }

      const component = compiled.content.replace(/\bexport default\b/, 'const __sfc__ =');

      return {
        contents: `${component}\n__sfc__.__file = ${JSON.stringify(basename(filename))};\nexport default __sfc__;\n`,
        loader: 'ts',
      };
    });
  },
});

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
  esbuildPlugins: [vueSfcPlugin()],
});
