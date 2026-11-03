# Isolated Janua staging: held source and native activation contract

Last updated: 2026-11-02

Boundary note: public-safe source contracts only. Actual object IDs, endpoint
observations and custody receipts stay in the [private operations record](https://github.com/madfam-org/internal-devops).
This change **does not bootstrap staging**, provision credentials/databases,
register a service, apply manifests, issue tokens, or authorize production promotion.

## Source prepared here

The flat API-only overlay uses the separate identity `janua-api-staging` for its
Deployment, Service, container, selectors and `enclii.dev/service` label. The image
remains `ghcr.io/madfam-org/janua-api`. Production's `janua-api` identity is separate.
The proposed route targets `janua-api-staging.janua-staging.svc.cluster.local:80`.
Both staging API and Redis remain at **zero replicas**. A separate reviewed
activation change may release those holds after native prerequisites are proven.
The Argo declaration is still only source; its existence is not a running App.

The existing profile already requires staging-only ExternalSecrets, a fresh RSA
pair, symmetric/Fernet keys, host-only cookies, dedicated authenticated Redis,
separate DB/CA custody and PostgreSQL `verify-full`. Email, magic links, signups,
provider credentials, tracking and federation remain off; runtime migrations are
off. No production identity/client data or database clone may enter staging.

`python scripts/staging/public_probe.py` makes only five fixed public GETs:
staging health, dependency-strict readiness, discovery and JWKS, plus production's
**public** JWKS. It rejects degraded/missing dependencies, the wrong environment,
foreign issuer/endpoints, weak/private/duplicate public key metadata and any shared
RSA modulus, including different exponents or encodings of the same modulus.
It emits only verdicts, never payloads or keys. Run it only after the public route
exists; no hosted login, lookup, email or token issuance is attempted by this probe.

A successful public probe explicitly does **not** prove native image identity,
workload ownership, network/database isolation, custody or runtime soak.
`promotion_runtime_guard.py` therefore refuses promotion unconditionally until a
reviewed Enclii native qualification adapter supplies those facts. It has no
argument, environment-variable, handwritten-JSON or pin-age bypass. The promote
workflow depends on this guard; disabled scheduled auto-promotes stay quiet.
This is an interim safety hold, not completion of the bootstrap work below.

## Existing supported capabilities and limits

| Capability | Source implementation | What remains unproven |
| --- | --- | --- |
| Namespace preparation | Enclii `POST /v1/admin/projects/:slug/environments/staging/bootstrap`; persisted environment/repository ownership; DNS-only default-deny | Actual namespace/policy ownership and additive-policy denial |
| Held preregistration | `ops apps staging-intent`; immutable operation/actor identity | Creates no service, source authority, Argo App or workload |
| Addon plan/admission | `addon staging-plan` / `addon staging-admission`; fixed Janua profile and native dry-run | No actual addon creation, role readiness or migration |
| Fresh crypto/Redis custody | Typed initialization-only `janua-staging/runtime-crypto` and `janua-staging/redis` targets | Deployed target policy, actual custody/ESO readiness |
| DB/CA targets | Supplied-only `janua-staging/database` and `janua-staging/database-ca` | No supported Janua-specific owner-to-runtime custody exporter |
| Generic runtime profile | Synthetic `*_sim` validation | It intentionally refuses `janua_staging`; do not weaken it or rename staging to evade it |

The detailed platform contracts are [held source identity](https://github.com/madfam-org/enclii/blob/main/docs/runbooks/JANUA_STAGING_PREREGISTRATION_DESIGN.md),
[addon plan/admission](https://github.com/madfam-org/enclii/blob/main/docs/runbooks/JANUA_STAGING_ADDON_PLAN.md)
and [typed custody](https://github.com/madfam-org/enclii/blob/main/docs/runbooks/ISOLATED_TRAINING_CUSTODY.md).
Existing Karafiel typed staging code supplies useful patterns, but its adoption
path requires already-existing native objects. It cannot bootstrap Janua's absent
Application and Deployment or substitute its project/service identity.

## Minimum native implementation sequence

1. **Environment-specific source authority.** Add an immutable same-project and
   same-environment source registration for the fixed Janua repo/ref/overlay.
   Link the completed global onboarding record as repository ownership only.
   Never overwrite its production `argocd_app_name`/snapshot. Require a durable
   operation UUID, current platform operator, fresh exact-plan CAS and a retained
   uncertain-result receipt. Keep the proposed service outside active service
   inventories until all build/preview/webhook/domain/discovery writers reject
   held registrations. `auto_deploy=false` alone is insufficient: existing
   `GetByGitRepo` and preview consumers do not establish environment identity.
2. **Materialize only inert native objects.** After reviewed namespace/default-deny
   and signature admission, add the separate staging App through the centrally
   owned GitOps source. Its exact repo/ref/path must match the new authority.
   Reconcile only the zero-replica API/Redis profile and reviewed PVC allocation.
   Verify actual namespace, App, Deployment and Service UIDs, source revision,
   selectors, tracking and absence of competing environment owners. Then bind the
   separate service/environment target using a validator extended to the new
   source authority. Do not invent native UIDs to satisfy migration `043` early.
3. **Dedicated Janua DB typed apply.** Extend the fixed Janua addon admission
   profile with a durable exact-plan apply operation. Use fresh dedicated CNPG,
   retained storage, signature-verified image/admission and narrow API/DB rules.
   Database `janua_staging`, runtime `janua_staging_runtime`, migrator
   `enclii_migrator` are fixed server-side. Runtime is nonowner, non-superuser,
   no BYPASSRLS/role creation/database creation/replication/inheritance. Never
   adopt a shared production addon. Reuse the operation/custody isolation patterns
   from Karafiel's typed apply, not its project/database/role constants.
4. **Owner/runtime/CA custody and fixed migration.** Verify Cluster ownership,
   managed-role readiness and CA host binding. Transfer only the runtime DSN and
   verified public CA server-to-server to their fixed intake targets; no password,
   owner DSN or CA private key may be returned or pasted. Keep the migrator
   credential exclusively in a fixed bounded native migration Job. Migrate the
   exact approved API image, then grant only required application DML/sequence
   privileges to runtime and verify actual role flags. Record Alembic revision
   independently. No generic caller SQL, bootstrap password, image or DSN selector.
5. **Release the replicas hold deliberately.** Verify typed fresh crypto/Redis
   custody, Secret projection and DB migration without reading values. Review an
   activation PR setting the exact staging workloads to one replica. Observe
   actual image IDs, Ready state and narrow CNI allow/deny results. Prove no access
   from staging to production Janua/data namespaces or mail/provider endpoints.
6. **Synthetic identity/auth and recovery.** Add a fixed staging-only synthetic
   seed/auth executor against the fresh DB; real users, clients and prod clones
   are excluded. Outbound email remains blocked. Qualify human authorization-code
   + PKCE, issuer/audience/scope denials, original `auth_time` on refresh and refresh
   rotation using synthetic actors. Also test DB transport/role denial and a
   synthetic backup/restore before calling the stage usable.
7. **Native continuous runtime qualification.** Add a read-only Enclii qualification
   endpoint/recorder bound to the exact environment/source/workload target. Every
   sample must freshly verify App/namespace/Deployment ownership, generation,
   running pod image IDs against the intended staging pin, Ready replicas,
   public discovery/JWKS separation and strict readiness. Sample continuously for
   at least 1,800 seconds; replacement pods, revision/digest/key changes, unhealthy
   samples or observation gaps reset the interval. Store server-authenticated,
   append-only observations and perform synthetic auth at the beginning/end.
   Return a bounded verdict/evidence ID, never raw pods, identities, keys or DSNs.
8. **Replace the interim promotion hold.** The promotion workflow must read that
   native record through authenticated Enclii, validate its current digest/source,
   healthy duration and freshness, then recheck it immediately before each fresh-main
   production write. Public-probe success, Git pin age, caller JSON and a boolean
   approval never substitute for runtime evidence. Keep the migration guard and
   independent production promote approval. No #758 promotion precedes this proof.

These are separate reviewable platform increments: source authority/writer
exclusions; inert native materialization/binding; typed DB/custody/migration;
activation/synthetic seed; native soak/promotion adapter. They require source and
native tests, not a single broad bootstrap endpoint or manual SQL substitute.
The existing Enclii extension points include `internal/stagingintents`,
`internal/workloadtargets`, `internal/k8s/staging_namespace.go`,
`internal/api/janua_staging_addon_{plan,admission}.go`, `internal/addons`, and
`internal/secretsintake`; preserve the fixed Janua profile boundaries there.

## Owner commands available today

These read-only commands inspect supported prerequisites after verifying the
released Enclii API/CLI. They do not authorize bootstrap or promotion:

```sh
enclii ops capabilities --json
enclii ops apps staging-intent --project janua --operation-id "${JANUA_STAGE_OPERATION_ID:?}" --json
enclii addon staging-plan --project janua --plan standard-0 --json
enclii secrets intake targets --json
```

After separate custody approval and verification that the live targets expose
the typed policies, the owner can initialize the **complete** fresh crypto group:

```sh
enclii secrets intake submit janua-staging/runtime-crypto \
  --generate jwt_private_key,jwt_public_key,jwt_secret_key,secret_key,field_encryption_key \
  --reason "initialize fresh isolated Janua staging crypto"
```

Review the redacted receipt before separately initializing Redis:

```sh
enclii secrets intake submit janua-staging/redis \
  --generate redis_password,redis_url \
  --reason "initialize fresh isolated Janua staging Redis"
```

These targets refuse existing/partial groups and concurrent changes; do not retry
or rotate around a refusal. No custody command has been executed by this change.
The namespace bootstrap's current API contract accepts only
`repo_full_name: madfam-org/janua`, `dry_run: true|false` and an apply reason at
`POST /v1/admin/projects/janua/environments/staging/bootstrap`; no published CLI
materialization command exists. Inspect its dry-run and current authority before
any separately authorized apply. No direct cluster/Vault command is supplied.

**There is currently no supported Janua DB apply, owner/runtime grant/migration,
service materialization or native soak command.** Implement the typed adapters
above before providing owner execution commands. The absence of those capabilities
is an engineering blocker, not a request to paste database credentials or run a
legacy addon create command. Secrets/DB grants and production promotion remain
separate owner actions under the session's authorization rules.
