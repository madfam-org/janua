# Dependabot sweep decisions - 2026-04-18

Sweep of 7 open Dependabot PRs (repo had 7 open from @dependabot, not 11 as listed).
All bumps validated against `packages/core` jest suite (36 tests) and typecheck.

## Merged (bundled into this sweep branch)

### PR #299 - express-rate-limit 7.5.1 -> 8.3.1
- Single consumer: `packages/mock-api/src/server.ts`
- v8 deprecated but still accepts `max` option, no code change required
- Tests: 36/36 pass (no tests directly exercise rate limit; typecheck clean)

### PR #310 - production-dependencies group (graphql-ws 6.0.7->6.0.8, zustand 5.0.11->5.0.12)
- Patch-level bumps, zero behavior change expected
- PR diff was stale (branch predates tailwind-merge 3.5 and algoliasearch 5.49 landing on main)
- Applied only the two forward bumps to avoid downgrading unrelated deps

### PR #311 - dev-dependencies group (20 updates, all minor/patch within major)
- @babel/preset-env 7.29.0 -> 7.29.2
- @playwright/test 1.58.2 -> 1.59.1 (root + apps/website)
- @storybook/addon-essentials 8.6.17 -> 8.6.18 (root + packages/ui)
- @storybook/addon-interactions 8.6.17 -> 8.6.18 (root + packages/ui)
- @storybook/blocks 8.6.17 -> 8.6.18 (root + packages/ui)
- @storybook/react-vite 10.2.13 -> 10.3.5 (root + packages/ui)
- @typescript-eslint/eslint-plugin 8.56.1 -> 8.58.1 (packages/core, packages/typescript-sdk)
- @typescript-eslint/parser 8.56.1 -> 8.58.1 (packages/core, packages/typescript-sdk)
- ts-jest 29.1.1 -> 29.4.9 (packages/core, packages/react-sdk, packages/typescript-sdk)
- @cloudflare/workers-types 4.20260305.0 -> 4.20260413.1 (apps/edge-verify, packages/edge)
- rollup 4.59.0 -> 4.60.1 (packages/typescript-sdk)
- rollup-plugin-dts 6.1.0 -> 6.4.1 (packages/typescript-sdk)
- typedoc 0.28.17 -> 0.28.19 (packages/typescript-sdk)
- @csstools/css-syntax-patches-for-csstree 1.0.29 -> 1.1.3 (packages/ui)
- postcss 8.4.32 -> 8.5.9 (apps/admin, apps/dashboard, apps/website)
- tailwindcss 4.2.1 -> 4.2.2 (apps/admin, apps/dashboard, apps/docs, apps/website)
- wrangler 4.69.0 -> 4.81.1 (apps/edge-verify)

PR diff was stale (would have downgraded tailwind-merge, algoliasearch, and
deleted `infra/argocd/config.json` by mistake). Applied only the forward bumps.

## Held (require follow-up PRs)

### PR #286 - @react-native-async-storage/async-storage 1.24.0 -> 3.0.1 - HOLD
React Native SDK migration explicitly out of scope for this sweep.
v2/v3 change native module config (Turbo Modules / New Architecture). Requires
RN SDK coordination and physical device smoke test.

### PR #298 - @simplewebauthn/server 9.0.3 -> 13.3.0 - HOLD
**Latent runtime break.** Tests falsely appear green:

1. `packages/core/tsconfig.json` excludes `src/services/**/*` from typecheck
2. Unit tests `jest.mock('@simplewebauthn/server')` and supply mocks carrying
   both old (v9) and new (v13) shape
3. Real v13 `VerifiedRegistrationResponse.registrationInfo` no longer has
   `credentialID`, `credentialPublicKey`, or `counter` at top level - they
   moved under `.credential.{id,publicKey,counter}`
4. `packages/core/src/services/webauthn.service.ts` lines 160-164 still use
   the v9 shape: passkey creation will throw at runtime

Fix path: rewrite `webauthn.service.ts` registration + authentication verify
paths to use the new nested `credential` shape, add `@simplewebauthn/types` v13
(replacing deprecated `@simplewebauthn/typescript-types` v8), and either remove
the `src/services/**/*` tsconfig exclude or add a typed integration test.

### PR #300 - inquirer 9.3.8 -> 13.3.2 - HOLD
`packages/cli/src/utils/prompts.ts` uses the legacy `inquirer.prompt([...])`
monolithic API. v10+ split into modular per-prompt packages (@inquirer/input,
@inquirer/confirm, etc.) and moved to ESM-first. Out of scope per sweep
constraints.

### PR #301 - @prisma/client 6.1.0 -> 7.5.0 - HOLD
Major engine bump. Requires coordinated `prisma` CLI upgrade, regenerated
client, and schema compatibility review. Explicitly out of scope per sweep
constraints.

## Validation

- `pnpm install --no-frozen-lockfile` - clean (peer warnings unchanged vs main baseline)
- `packages/core`: `npm test` 36/36 pass, `npm run typecheck` clean, `npm run build` clean
- `packages/typescript-sdk`: `npm run build` clean
- `packages/mock-api`: `npx tsc --noEmit` produces same 6 pre-existing TS2742 errors as main baseline (pre-existing express type portability warnings, not caused by this sweep)

## Summary

- Merged: 3 PRs (299, 310, 311) - bundled into this sweep branch
- Held: 4 PRs (286, 298, 300, 301) - comments posted with migration notes
