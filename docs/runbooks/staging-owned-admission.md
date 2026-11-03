# Owned staging admission preparation

This is a source preparation and inspection guide. It does not authorize
provisioning, migration, secret intake, hosted authentication or promotion.
Production remains on the manual promotion path.

## Exact identity

Use project `janua`, its persisted `staging` environment and namespace
`janua-staging`, repository `madfam-org/janua`, app path `apps/api` and logical
service/Deployment/Service `janua-api-staging`. The container and repository
remain `janua-api` and `ghcr.io/madfam-org/janua-api`. Do not retarget the
production service or repository registration.

An older identity proposal retained `app: janua-api` while adding the exact
service label to selectors. The complete correction instead uses
`app: janua-api-staging` consistently and keeps the canonical
`enclii.dev/service: janua-api-staging` pod label. Integrate one identity change;
do not merge both proposals independently. Carry forward the old-object,
backend and monitoring review from the earlier proposal.

## Read-only inspection interfaces

Commands below require the corresponding released CLI and a current authorized
operator login. A missing CLI command is an interface gap, not permission to
use raw cluster access. The equivalent documented Enclii HTTPS API is supported.
Never print its bearer credential or automatically change identities on refusal.

```sh
enclii projects environments janua --json
enclii projects services janua --json
enclii addon ls --project janua --json
enclii ops apps status janua-staging-services --namespace argocd --json
enclii ops pods diagnose --namespace janua-staging --json
enclii ops secrets external --namespace janua-staging --json
enclii addon staging-plan --project janua --plan standard-0 --json
```

The plan's equivalent GET is
`/v1/admin/projects/janua/environments/staging/addon-plan?plan=standard-0`.
It reads ownership, catalog and infrastructure metadata without credentials or
provisioning. Only after an independently materialized exact staging service
exists may an optional `service_id` name that service. Do not select production.
The observation fingerprint is not an apply token.

The namespace-bootstrap API is
`POST /v1/admin/projects/janua/environments/staging/bootstrap` with
`{"repo_full_name":"madfam-org/janua","dry_run":true}`. Its source dry-run
returns before namespace/policy writes. An apply request is a separate mutation
requiring a reason and authorization; it prepares only namespace/default-deny,
not workloads, domains or secret custody. Reconfirm the deployed route and
ownership contract before either request.

The held-intent API is
`POST /v1/admin/projects/janua/environments/staging/preregistration-intents`.
Its plan body is `{"operation_id":"<CANONICAL_UUID>","record":false}`.
The corresponding released CLI is `enclii ops apps staging-intent --project
janua --operation-id <CANONICAL_UUID> --json`. Recording is a durable write;
do not add `--record` to an inspection. Even a recorded intent cannot create
a service or activate an Application.

## Native dry admission

After actual service/namespace prerequisites and signature policy are qualified,
the separate source adapter supports:

```sh
enclii addon staging-admission --project janua --plan standard-0 \
  --service-id <OWNED_STAGING_API_SERVICE_UUID> --json
```

This maps to a bodyless POST at
`/v1/admin/projects/janua/environments/staging/addon-admission` with only
`plan` and `service_id`. It hardcodes server-side `DryRunAll` for the closed
Cluster, two policies and representative image-admission Pod; it persists no
resource, row or credential and executes no Pod or SQL. Missing ownership,
isolation or signature prerequisites refuse. Never invent a service identifier
to bypass an unresolved prerequisite. `apply_supported` remains false.

## Missing apply and migration boundaries

The source plan/admission/intent contracts explicitly retain these implementation
gaps; they are not optional policy waivers:

| Boundary | Required next result |
| --- | --- |
| Environment-specific source registration | Separate faithful stage authority; preserve production registration |
| Service materialization | Durable exact held-to-service operation, native binding and background-writer exclusion |
| Dedicated database apply | Typed idempotent operation identity, current authority and plan, actual capacity and CNI qualification |
| Custody | Cluster-owned migrator credential kept server-side, separate nonowner runtime credential and verified public CA |
| Migration | Fixed source/digest-bound Janua stage executor; generic service jobs inherit runtime custody and are unsuitable |
| Central Application | Separate reviewed declaration only after activation prerequisites; merging it can auto-sync workloads |

The fixed database proposal is `janua-staging-db` / `janua_staging`, owner
`enclii_migrator`, runtime `janua_staging_runtime`, with `verify-full` transport.
The runtime must remain nonowner, NOSUPERUSER, NOBYPASSRLS, NOCREATEDB,
NOCREATEROLE, NOREPLICATION and NOINHERIT. The addon and app namespaces each
need proven ownership and centrally managed default-deny. Unknown additive
policies, shared production database reuse, generic addon create or generic
`jobs run-once` do not close these gaps.

Registered intake identifiers are `janua-staging/runtime-crypto`,
`janua-staging/redis`, `janua-staging/database` and `janua-staging/database-ca`.
Only the first two have fresh, atomic server-generation profiles. Database/CA
intakes reject generation and require independently verified typed custody.
Intake submit is a write and is not part of this inspection. The runtime receives
only the nonowner URI; it never receives an owner/migrator URL.

Before requesting migration approval, produce the actual reviewed Job from the
fixed executor: exact candidate source/digest, database/role/TLS checks, bounded
time/resources, concurrency protection, native identity, owner-secret provenance,
public-CA mount and aggregate-only receipt. The image works in `/app`, and the
reviewed command must bypass the ordinary API startup entrypoint. A template with
unresolved candidate/custody fields is preparation, not an executable approval
request. No stage migration or hosted synthetic is authorized by this document.

## Application and readiness order

The central ApplicationSet reads Enclii
`infra/argocd/projects/*/config.json`; Janua's own
`infra/argocd/staging-config.json` is only an input proposal. A separate central
declaration would name `janua-staging`, point to `k8s/overlays/staging` and
namespace `janua-staging`, producing Application `janua-staging-services`.
That ApplicationSet enables automated prune/self-heal and namespace creation:
its declaration merge is an activation, not a harmless metadata-only step.

After supported apply/custody/migration and route admission, verify actual imageID,
dependency-readiness response body, database/Redis isolation and the exact
candidate's continuous healthy runtime for at least 30 minutes. Source pins,
elapsed pin age and HTTP200 alone are insufficient. Requalify if the candidate
changes. Production promotion remains a separate explicitly authorized supported
Enclii operation, with no clock-only soak or direct-provider substitute.
