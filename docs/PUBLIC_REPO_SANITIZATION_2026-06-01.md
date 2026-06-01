# Janua Public Repo Sanitization Contract

Date: 2026-06-01
Status: launch-blocking for identity, auth, SSO, tenant access, and platform gatekeeping readiness

## Position

Janua is an identity and access-control surface. Public repo sanitization must treat auth examples, SSO tests, webhook fixtures, certificate fixtures, staging templates, and deployment docs as high-risk until reviewed.

## Current remediation posture

- `infra/secrets/janua-staging-secrets.template.yaml` has been converted into a placeholder-only, scanner-safe public template.
- Scanner-valid dummy credential strings in the identified auth, webhook, certificate, deployment, and roadmap files were normalized to non-credential-shaped placeholders.
- No repo-level pass is granted until current-tree scan, history scan, public artifact review, and owner approval are recorded in Tulana.

## Launch-blocking checks

A Janua-linked platform/SKU cannot pass Product/Offer GA public-repo sanitization until evidence confirms:

- No real signing keys, OAuth client secrets, webhook secrets, database URLs, redis URLs, or encryption keys are present.
- Certificate and JWT fixtures are synthetic and cannot be confused for deployable secret material.
- Public deployment docs do not expose privileged production procedures.
- Staging templates are placeholders only and require the approved secret store.
- Buyer-facing claims around SSO, auth, tenancy, and enterprise features match production reality.

## Required Tulana evidence

Use `PUBLIC_GITHUB_REPO_SANITIZED` evidence attached to `P4`, `P8`, and `P9`; attach to `P0` when public Janua docs are used as buyer-facing proof.
