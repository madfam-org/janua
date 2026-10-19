# PP.3b — Janua staging pipeline and consumer provisioning

> Updated: 2026-10-19. Source profile prepared; deployment and runtime soak
> require their own operational receipts.

Janua uses the RFC 0001 manual promotion gate because it is the ecosystem
identity provider. The isolated staging profile currently deploys **the API
and its private Redis only**. Built frontend images are not staged frontend
proof; promotion accepts only `api` until separate frontend staging is reviewed.

## Source and runtime boundaries

The staging Kustomization is flat and self-contained: `api.yaml`, `service.yaml`,
`redis.yaml`, and `secrets.yaml`. It does not import the production base,
namespace, HPA, frontend origins or integration credentials. This keeps the
existing governed flat-manifest admission preflight usable without a general
Kustomize interpreter or an exception.

The API uses the staging issuer and origin, host-only cookies, fresh staging
RSA keys and fresh symmetric/Fernet keys. Email, SMTP, Resend, tracking,
federation, magic links and public signup remain off. No production identity or
client dataset is copied. Stage smoke uses synthetic identities registered
through the approved staging flow, with no invitation or email delivery.

Runtime PostgreSQL requires a dedicated fresh addon with a separate migrator,
a nonowner role and `DATABASE_SSL_MODE=verify-full`. Mount the verified public
CA at `/var/run/janua-staging/ca/ca.crt`; runtime never receives the migrator
credential. The shared transport helper propagates this CA and hostname
verification into router, health, metadata and Alembic engines. Missing explicit
CA files, invalid modes and incomplete client-certificate pairs fail closed;
default disabled transport and prepared-statement cache compatibility remain.

Redis is a private authenticated deployment with its own staging password and
1Gi persistent volume. The image reuses the platform's governed digest. The
API may reach only its own bound addon and this Redis; no shared data namespace,
production Janua, provider/mail or generic internet egress is required.

ExternalSecrets read only `secret/janua-staging` through the existing Vault
ClusterSecretStore. They project runtime keys, public CA and Redis password
separately. Fresh material must enter through reviewed Enclii intake targets;
there are no committed values or direct Vault/cluster secret commands.

## Normal activation and promotion

1. Prepare a persisted `staging` environment and its exact owned namespace
   through the supported project-scoped Enclii bootstrap. Require matching
   repository/project ownership and default-deny; never use production
   onboarding `ensure` to retarget its existing registration.
2. Provision the dedicated addon, verify managed role Ready and public CA
   ownership, and establish fresh staging custody. Migrate through a separately
   approved migrator job before activating the nonowner API; runtime auto-DDL
   and `JANUA_APPLY_MIGRATIONS` remain false.
3. Review exact signed API digest, resource/storage allocation, image admission,
   namespace/network policy and secret readiness. Register the separate
   ApplicationSet declaration through the normal central GitOps PR. Production
   registration stays separate.
4. Verify actual stage readiness **body**, database/Redis health, pod/image
   digest parity, real human authorization-code/PKCE, protected-resource
   audience/scope isolation and rotating refresh using synthetic stage actors.
   HTTP200 or a source pin alone is insufficient.
5. Record a continuous healthy runtime soak of at least 30 minutes after the
   intended digest is actually running. The existing workflow also checks
   staging pin age; elapsed pin time is not operational soak evidence.
6. Check the normal migration-drift guard, serialize with key/client changes,
   then dispatch `promote-to-prod.yml` through the supported Enclii promotion
   adapter for `api` with the verified digest and reason. An absent adapter
   blocks production promotion; direct provider dispatch is not a substitute.
   No break-glass soak override. Confirm actual production digest, readiness and
   hosted synthetic boundary receipts after promotion.

`docker-publish.yml` signs builds and commits candidate digests only to the
staging overlay. The production pointer changes through the manual promotion
workflow. An explicit digest must equal the current staging API pin; it cannot
select a historical candidate. Every fresh-main retry checks that binding again
before writing production, and refuses a changed, missing or ambiguous staging
pin. Requalify the running candidate and its soak after a staging replacement.
These source checks do not establish runtime health or custody. This document
does not claim staging activation, soak or production promotion has occurred.

## Platform prerequisites still needing runtime evidence

The product manifests do not create or relabel namespaces and do not own
NetworkPolicies. Enclii owns namespace/default-deny/bootstrap and the exact
addon-bound and same-namespace Redis rules. A source helper or CI proof does not
establish live role attributes, certificate transport, RLS, workload network
denial, resource placement, migration or application readiness. Preserve a
concrete adapter gap instead of substituting raw infrastructure access.

## Consumer OAuth provisioning

### CLI path (recommended)

```bash
npm install -g @janua/cli   # @janua/cli@0.2.0 on npm.madfam.io

export JANUA_INTERNAL_API_KEY=...   # from Enclii/Vault
export JANUA_API_URL=https://auth.madfam.io   # or staging-auth for staging tenant

janua provision plan -f janua.client.yaml
janua provision apply -f janua.client.yaml
janua provision verify -f janua.client.yaml
janua provision export-env -f janua.client.yaml
```

Manifest example with **pinned client_id** (for consumers that require a fixed ID across environments):

```yaml
apiVersion: janua.dev/v1
kind: OAuthClient
metadata:
  name: ceq-studio
spec:
  client_id: jnc_2EJwBz8xGVsGYOO2r3ck5CJH7YrQw4Yk   # optional — API assigns jnc_* if omitted
  audience: ceq-api
  redirect_uris:
    - https://app.ceq.lol/auth/callback
    - http://localhost:5801/auth/callback
  allowed_scopes: [openid, profile, email]
  grant_types: [authorization_code, refresh_token]
  is_confidential: true
```

### Register API

```
POST /api/v1/oauth/clients/register
X-Internal-API-Key: <INTERNAL_API_KEY>
```

| Behavior | Detail |
|----------|--------|
| Idempotent by `name` | Returns 200 + existing client (no secret) |
| Idempotent by `client_id` | Same if name matches |
| Conflict | 409 if `client_id` registered to different name |
| New client | 201 + `client_secret` (shown once) |
| `client_id` format | Must match `jnc_[A-Za-z0-9_-]{8,56}` |

Implementation: [apps/api/app/routers/v1/oauth_clients.py](../apps/api/app/routers/v1/oauth_clients.py)

### Historical CEQ Studio handoff

The following records an earlier operational handoff. It is not authority for
new database inserts, production credential copying or staging bootstrap.

Janua prod registration completed via break-glass DB insert (register API auto-generates IDs). CEQ agent must:

1. Mount `JANUA_CLIENT_SECRET` from `ceq-secrets` in Studio deployment
2. Redeploy Studio
3. Run browser login + `production-smoke.sh`

Secret location: GitHub Actions secret `JANUA_CLIENT_SECRET` on `madfam-org/ceq` (not in repo).

---

## Historical PP.3b adapter-gap record

These workarounds are historical. New staging work uses the governed adapters
and source prerequisites above; missing capacity remains a blocker.

| Gap | Workaround used |
|-----|-----------------|
| OAuth client provisioning with fixed `client_id` | DB insert / register API `client_id` pin (PP.3b) |
| npm token rotation publish smoke | solarpunk-foundry `npm-madfam-auth` + ARC runners |
| Staging namespace + secrets bootstrap | Manual template apply |
| ArgoCD App registration for `janua-staging` | `infra/argocd/staging-config.json` + ops |

---

## Historical PP.3b compliance snapshot

This table describes the earlier plan and is not a current runtime receipt.
The isolated API-only staging namespace, migration and soak remain unverified.

| RFC 0001 area | Before PP.3 | After PP.3b merge + ops bootstrap |
|---------------|-------------|-----------------------------------|
| Staging overlay | Missing | In repo; needs ArgoCD + secrets |
| Prod overlay | Digests in base | `k8s/overlays/production` |
| CI → staging digests | Direct to prod | `docker-publish` → staging only |
| Promote / rollback | Missing on main | Workflows live; need overlay paths |
| Staging smoke in CI | Missing | **Still open** (future PR) |
| Staging subdomains | Missing | **Ops action** |
| Masked DB refresh | Deferred | Deferred |

Estimated compliance after code merge: **~55%** (structural + workflows).  
Estimated after full ops bootstrap: **~75%** (smoke + masked DB still deferred).

---

## Related docs

- [PP_3_STAGING_AUDIT.md](./PP_3_STAGING_AUDIT.md) — original gap analysis
- [AGENTS.md](../AGENTS.md) — deployment pipeline summary
- [internal-devops/runbooks/staging-bootstrap.md](https://github.com/madfam-org/internal-devops/blob/main/runbooks/staging-bootstrap.md)
- [packages/cli/README.md](../packages/cli/README.md) — CLI provisioning
- [examples/consumer-bootstrap/](../examples/consumer-bootstrap/) — manifest templates
