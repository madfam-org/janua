# Explicit organization selection for human OAuth grants

A person can belong to several organizations without moving their identity
between email namespaces. Registered OAuth clients may request an explicit
organization with `organization_id=<UUID>` on `/api/v1/oauth/authorize`.
The TypeScript SDK exposes the same request as `JanuaSSOOptions.organizationId`:

```typescript
await client.auth.switchAccount({
  clientId: 'registered-rp-client',
  redirectUri: 'https://rp.example.test/auth/callback',
  organizationId: '00000000-0000-4000-8000-000000000001',
});
```

The example UUID is synthetic. The callback, state and PKCE contract remains the
RP's existing one. A selection requests context; it grants no membership, role,
subscription or permission. Both account selection and ordinary authorization
can carry it. `prompt=select_account` selects a held identity; `organization_id`
selects the organization for this grant. They are separate decisions.

Janua requires an active membership in the selected organization. If the OAuth
client is organization-bound, the selection must match that organization.
Malformed IDs, foreign organizations, removed memberships and unverifiable
membership reads are refused. They never fall back to another organization.
The optional selection is currently supported for registered human OAuth
clients, not protected-resource/CIMD flows or client-credentials requests.

The selected UUID travels through the existing Redis pre-login and consent
records, the authorization code and the signed refresh grant. Password, MFA,
magic-link and chooser continuations reconstruct the same request. Consent
cancellation returns the original state to the validated registered callback
and changes no app session. Expired pending requests must restart the RP flow;
the RP must include its desired selection again on a fresh request.

Code exchange and refresh revalidate the selected membership and current
client restriction. An `organization_id` supplied at the token endpoint cannot
override a refresh grant: its organization comes only from the signed token.
Revoking membership prevents the next exchange/refresh. Removing an application
grant removes that role at the next mint. Existing access tokens retain their
normal lifetime and revocation behavior.

The selected organization supplies `org_id`, `tenant_id`, `org_slug`, its
namespaced membership role, its explicit application grants, organization
subscription tier and inherited product entitlements. Explicit per-user grants
and platform-admin bootstrap retain their existing precedence. No grants are
inferred from organization owner/admin labels. The ID token keeps its existing
identity claims; the access token carries the authorization context.

When `organization_id` is absent, existing behavior is preserved: a single
active membership resolves automatically; multiple memberships resolve only
when the identity-pool field already identifies one, otherwise no primary-org
application grants are issued. This feature never writes `User.tenant_id`,
changes memberships, creates credential storage or requires a database migration.

`User.tenant_id` defines the user's email uniqueness/login pool. It is not an
active-organization preference. Changing it to repair a token would alter
identity lookup semantics. The SDK's visual organization switcher remains a
consumer callback; it does not silently mutate that field or refresh claims.
