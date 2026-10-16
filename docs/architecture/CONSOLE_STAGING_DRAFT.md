# Isolated console runtime — local draft handoff

This is an incomplete local checkpoint, not an approved release or activation.
Work stopped when the owner prioritized public/internal Tulana catalogue delivery.
Base: `f19a556efb1684a4e3bb3245dca80801c5eb9888`; branch:
`feat/isolated-console-staging`. Do not add this work to the account-switch/API
release merely because its unit checks pass.

## Implemented source

- Closed nonsecret runtime schema for surface, environment, console/API origin,
  issuer, audience and public JWKS URI. Unknown/missing fields fail closed.
- Request-local server resolution from `JANUA_CONSOLE_ENVIRONMENT`,
  `JANUA_CONSOLE_ORIGIN`, `JANUA_CONSOLE_API_URL`, `JANUA_CONSOLE_ISSUER`,
  `JANUA_CONSOLE_AUDIENCE`, `JANUA_CONSOLE_JWKS_URL`. There is no legacy
  `NEXT_PUBLIC_*` fallback in the console authentication path.
- Dynamic root rendering passes validated React props to auth providers and
  serializes exactly these fields in a React-escaped `data-config` attribute.
  No inline executable bootstrap, global window property or asynchronous fetch
  initializes configuration. Existing imperative callers use a lazy browser SDK
  bridge that validates the same markup and exact page origin before creation.
  Server imports do not instantiate that singleton; SSR providers use their
  explicit props, not request-global mutable state.
- Request middleware computes CSP from the validated runtime configuration.
  Admin/Dashboard image builds no longer bake their production API URLs.
- Staging uses `__Host-janua_stage_session`, Secure, Path=/, without Domain.
  Console gates ignore inherited `janua_access_token`; Admin does not adopt a
  shared production cookie in staging and does not expire legacy cookie names.
  SDK storage remains scoped to the browser origin. SDK HTTP requests use the
  existing same-origin credentials default; server transports omit cookies and
  reject redirects. Stage WebSockets are disabled, using existing polling,
  because browser WebSockets have no credentials:omit option.
- Stage Admin verifies the exact public issuer/audience while fetching JWKS and
  current authorization only from the exact owned internal API service. Neither
  token claims nor remote discovery choose a fetch URL.

## Candidate staging contract — NOT approved bindings

The draft validator currently proposes:

| Field | Candidate |
| --- | --- |
| Dashboard origin | `https://staging-app.madfam.io` |
| Admin origin | `https://staging-admin.madfam.io` |
| Public API/issuer | `https://staging-auth.madfam.io` |
| Audience | `janua-staging` |
| Public JWKS | `https://staging-auth.madfam.io/.well-known/jwks.json` |
| Server-only `JANUA_CONSOLE_INTERNAL_API_URL` | `http://janua-api.janua-staging.svc.cluster.local` |

These names do not establish domain ownership, availability or cookie isolation.
`.madfam.io` is shared by other services. The owner must review actual inherited
cookie names/domains and host/registrable-domain choices before activation.
Do not copy production identities, clients, tokens, memberships, credentials,
keys or datasets into staging.

## Validation recorded before stopping

- Admin: 150 tests passed, 1 existing skip; TypeScript passed.
- Dashboard: 135 tests passed, 11 existing skips; TypeScript passed.
- Focused ESLint on changed app TypeScript: 0 errors (Admin 7 warnings,
  Dashboard 38 warnings). The shared helper has not had a separate package lint.
- New tests exercise strict/missing/foreign configuration, public-field
  serialization, lazy SSR behavior, cookie isolation, dynamic CSP and pinned
  stage issuer/audience/JWKS plus rejection of production tokens.
- No production build, browser acceptance, Docker/image validation, independent
  security review, remote CI or live proof was performed for this draft.

## Remaining work before any release

1. Reconcile later account-feature build-guard commits without editing its
   frozen release worktree. Run fresh production builds of both consoles with
   no deployment variables, then prove one artifact serves two runtime profiles.
2. Finish the source audit for remaining navigation/provider behavior. For
   example, Admin's access-denied page still links to the production Dashboard.
   Review SDK credential transport and bootstrap behavior in real SSR/hydration.
3. Review nonsecret production deployment settings separately. Existing
   production manifests do not supply the new required runtime contract; shipping
   these images now would deliberately return configuration-unavailable.
4. Create the **not yet written** flat inactive `staging-console` profile with
   only console Deployments and ClusterIP Services in the owned stage namespace.
   No production base imports, credentials, DB/Redis workloads, Namespace or
   product-owned NetworkPolicies. Review exact resources and GHCR pull custody.
5. Prepare the exact API CORS-origin addition as a separate reviewed proposal;
   current API staging permits only staging-auth. No current API profile changed.
6. Prepare a central Enclii ApplicationSet registration with disjoint console
   resource ownership. A product-local staging config alone is not registration.
   Persisted environment metadata/pin age does not establish deployed workloads.
7. Obtain final operator approval for exact hosts, ingress, network/resource
   bindings and stage actor provisioning, using governed Enclii capabilities.
   Resolve API baseline activation/migrator/intake/pull-custody gaps first.
8. Verify actual signed running digests, readiness bodies and synthetic human
   login/MFA, switching/cancel, identity/role refresh and Admin authorization.
   Record at least 30 healthy runtime minutes. Only then review a future narrow
   frontend promotion enablement change; keep one immutable image per promotion.

The existing API-only staging resources, isolation tests and promotion guard
remain unchanged. No push, CI dispatch, deployment, client/domain/registry/CORS
write, credential creation, migration, membership/grant change or purchase occurred.
