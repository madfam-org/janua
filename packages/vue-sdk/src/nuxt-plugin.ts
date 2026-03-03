import { defineNuxtPlugin, useRuntimeConfig } from '#app';
import { createJanua } from '@janua/vue-sdk';
import type { JanuaPluginOptions } from '@janua/vue-sdk';

export default defineNuxtPlugin((nuxtApp) => {
  const config = useRuntimeConfig().public.janua as JanuaPluginOptions;

  const januaPlugin = createJanua({
    ...config,
    // Prevent polling and URL inspection during SSR;
    // the JanuaVue constructor already guards on `typeof window`,
    // but we explicitly set pollInterval to 0 on the server so
    // no timers are ever scheduled in an SSR context.
    ...(import.meta.server ? { pollInterval: 0 } : {}),
  });

  nuxtApp.vueApp.use(januaPlugin);
});
