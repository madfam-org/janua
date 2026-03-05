import { defineNuxtModule, addPlugin, addImports, createResolver } from '@nuxt/kit';

export default defineNuxtModule({
  meta: {
    name: '@janua/vue-sdk/nuxt',
    configKey: 'janua',
    compatibility: {
      nuxt: '>=3.0.0',
    },
  },
  defaults: {},
  setup(_options, nuxt) {
    const { resolve } = createResolver(import.meta.url);

    // Register the runtime plugin that creates the Janua instance
    addPlugin(resolve('./nuxt-plugin'));

    // Auto-import all composables from @janua/vue-sdk
    const composables = [
      'useJanua',
      'useAuth',
      'useUser',
      'useSession',
      'useOrganizations',
      'useSignIn',
      'useSignUp',
      'useSignOut',
      'useMagicLink',
      'useOAuth',
      'usePasskeys',
      'useMFA',
    ] as const;

    addImports(
      composables.map((name) => ({
        name,
        from: '@janua/vue-sdk',
      })),
    );
  },
});
