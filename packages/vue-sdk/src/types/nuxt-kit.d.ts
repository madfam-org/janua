declare module '@nuxt/kit' {
  export type NuxtModule<TOptions = Record<string, never>> = {
    meta?: {
      name?: string;
      configKey?: string;
      compatibility?: Record<string, string>;
    };
    defaults?: TOptions;
    setup?: (options: TOptions, nuxt: unknown) => void;
  };

  export function defineNuxtModule<TOptions = Record<string, never>>(
    module: NuxtModule<TOptions>,
  ): NuxtModule<TOptions>;

  export function addPlugin(path: string): void;

  export function addImports(
    imports: Array<{
      name: string;
      from: string;
    }>,
  ): void;

  export function createResolver(base: string): {
    resolve(path: string): string;
  };
}
