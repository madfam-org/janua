# Resend webhook signing secret (per tenant account)

> [!IMPORTANT]
> MADFAM-ENCLII-FIRST-LEGACY-RAW v1: This document contains legacy raw infrastructure command examples.
> Routine production operations must use Enclii web, API, or CLI. Treat raw
> `kubectl`, `helm`, SSH, provider CLI/API, `docker exec`, and direct container
> access as platform bootstrap or documented break-glass only, and record any
> missing Enclii adapter gap.

## Overview

Resend signs every webhook delivery Svix-style with the signing secret of the
webhook endpoint (`whsec_...`). An endpoint belongs to one Resend **account**, so
Janua keeps one secret per account and verifies each delivery with the secret of
the account named in the URL:

| Account | Receiver | Env var in janua-api | Vault key (`secret/janua`) | Secret key (`janua-secrets`) |
|---|---|---|---|---|
| A tenant's own Resend account | `POST /api/v1/email/webhooks/resend/<account>` | `RESEND_WEBHOOK_SECRET_<ACCOUNT>` | `resend_webhook_secret_<account>` | `resend-webhook-secret-<account>` |
| MADFAM platform account | `POST /api/v1/email/webhooks/resend/platform` | `RESEND_WEBHOOK_SECRET_PLATFORM` | `resend_webhook_secret_platform` | `resend-webhook-secret-platform` |

Every tenant account follows the same naming: `RESEND_WEBHOOK_SECRET_<ACCOUNT>`
(an entry in `WEBHOOK_SECRET_SETTINGS`, `apps/api/app/services/email_events.py`),
Vault key `resend_webhook_secret_<account>`, Secret key
`resend-webhook-secret-<account>`, where `<account>` is the slug in the receiver URL.

The steps below are written for a tenant account. For the platform account
substitute the names from the table. What the receiver stores and the rest of the setup live in
[`../resend-email-events.md`](../resend-email-events.md).

**Location:** Vault `secret/janua` → enclii-managed ExternalSecret `janua-secrets` → env var in `janua-api`
**Policy:** on demand (a new or recreated Resend webhook endpoint issues a new secret)
**Registry id:** `janua-resend-webhook-secret-<account>` in `infra/secrets/SECRETS_REGISTRY.yaml`

## How the value reaches the pod

```
Resend webhook page (signing secret, whsec_...)
  → Vault KV  secret/janua  key resend_webhook_secret_<account>
  → ExternalSecret janua-secrets (managed in the enclii repo)  key resend-webhook-secret-<account>
  → Secret janua-secrets
  → env RESEND_WEBHOOK_SECRET_<ACCOUNT> in janua-api (optional secretKeyRef, read at process start)
```

- The Deployment (`k8s/base/deployments/janua-api.yaml`) reads the key with
  `optional: true`: with no key the pod still starts and the receiver answers
  **404** for that account.
- The ExternalSecret is all-or-nothing: a mapping whose Vault property does not
  exist makes the whole `janua-secrets` sync fail. Write Vault first, then add
  the mapping (in the enclii repo), never the other way round.
- Env vars are read when the process starts. A new value in the Secret changes
  nothing until janua-api restarts.

## What the receiver answers

| Answer | Meaning |
|---|---|
| `200 {"status":"stored"}` | Signature verified, event stored. (`"duplicate"` for a redelivery, `"ignored"` for a type Janua does not store.) |
| `404 {"detail":"Not found"}` | The pod has no secret for this account (env var unset or blank). Same answer as an unknown account. |
| `401 {"detail":"Invalid webhook signature"}` | A secret is present but the signature does not match it: wrong value stored, or a stale/missing Svix header. |

The receiver strips surrounding whitespace from the value (a trailing newline
is harmless), drops the `whsec_` prefix and base64-decodes the rest. A value
that is not a signing secret at all (for example a pasted command) cannot be
decoded, and every delivery gets **401**, never a 500. The pod logs
`email_webhook.rejected` with a `reason` (never the secret):
`signing secret is not valid base64` means the stored value is not a secret;
`no matching v1 signature` means a well-formed secret from a different endpoint
or account.

## Rotation / first install

Resend shows the signing secret on the webhook's page once the endpoint exists.
Deliveries that arrive before the secret reaches the pod get 404 or 401, and
Resend retries them; they can also be replayed from the webhook page.

### Step 1: Write the secret to Vault without exposing it

Rules:

- Use `vault kv patch`, never `vault kv put`: `put` replaces **every** key at
  `secret/janua` with only the keys on its command line.
- The value never goes on a command line, in shell history, or in a file. It is
  typed (pasted) into a hidden prompt and reaches Vault on stdin (`key=-`).
- **Copy the command first, run it, and only then copy the secret from Resend**
  and paste it at the prompt (see «Pitfall» below).

From a shell that has the `vault` CLI and a token allowed to patch
`secret/janua`:

```bash
# zsh
read -rs 'WHSEC?Resend signing secret (hidden): '; echo
# bash:  read -rsp 'Resend signing secret (hidden): ' WHSEC; echo

printf '%s' "$WHSEC" | vault kv patch secret/janua resend_webhook_secret_<account>=-
unset WHSEC
```

`printf` is a shell builtin, so the value does not appear in the process list.
If the `vault` CLI runs somewhere else (a bastion, or an exec into the Vault
pod), keep the value on stdin through the hop; never interpolate it into the
remote command string.

### Step 2: Check the stored value's shape (without printing it)

```bash
vault kv get -field=resend_webhook_secret_<account> secret/janua \
  | awk 'NR==1 { p = (substr($0, 1, 6) == "whsec_") ? "yes" : "NO"; l = length($0) }
         END   { printf "whsec_prefix=%s length=%d lines=%d\n", p, l, NR }'
```

Expected: `whsec_prefix=yes length=38 lines=1` (about 38 characters: `whsec_`
plus the base64 key). A missing prefix, a length far from that, or more than one
line means something other than the secret was pasted: repeat step 1.

### Step 3: Sync the ExternalSecret and restart janua-api

Enclii (preferred; mutating verbs are a dry-run plan until `--apply --reason`):

```bash
enclii ops secrets sync janua-secrets -n janua --apply --reason "Resend webhook secret (<account>) rotated"
enclii ops secrets external janua-secrets -n janua   # Ready, and resend-webhook-secret-<account> among the keys
enclii ops pods restart janua-api -n janua --apply --reason "Pick up RESEND_WEBHOOK_SECRET_<ACCOUNT>"
```

Break-glass equivalent:

```bash
kubectl annotate externalsecret janua-secrets -n janua force-sync="$(date +%s)" --overwrite
kubectl get externalsecret janua-secrets -n janua        # STATUS SecretSynced, READY True
kubectl rollout restart deployment/janua-api -n janua
kubectl rollout status deployment/janua-api -n janua --timeout=300s
```

Judge the sync by the ExternalSecret's Ready condition and refresh time, not by
the command's own success message. The same shape check can be run on the
Secret the pod reads, again without printing the value:

```bash
kubectl get secret janua-secrets -n janua -o jsonpath='{.data.resend-webhook-secret-<account>}' | base64 -d \
  | awk 'NR==1 { p = (substr($0, 1, 6) == "whsec_") ? "yes" : "NO"; l = length($0) }
         END   { printf "whsec_prefix=%s length=%d lines=%d\n", p, l, NR }'
```

Wait until the old pods are gone before judging: a tunnel's persistent
connection can keep reaching a draining old pod for a short while.

### Step 4: Verify

1. Trigger an event on the account (any send from it), or use **Replay** on a
   failed delivery in Resend's webhook page.
2. The delivery's response in Resend's webhook page is `200 {"status":"stored"}`.
3. If not:
   - **404**: the pod has no secret. The ExternalSecret did not sync the key, or
     janua-api was not restarted after it did (step 3).
   - **401 «Invalid webhook signature»**: the pod has a value, and it is the
     wrong one. Check the shape (step 2) and the `email_webhook.rejected`
     reason in the janua-api logs, then repeat from step 1.

## Pitfall: the clipboard held the command (2026-09-26)

The first tenant-account install stored the wrong value: the operator copied the secret
from Resend, then copied the command to run, and the command read the value from
the clipboard. The clipboard now held the command text, and that is what went
into Vault. The pod had a value, so the receiver answered 401 (not 404) to every
delivery.

Two changes prevent it: the value is entered at a hidden prompt, never read
from the clipboard by the command itself, and the command is copied **before**
the secret. Step 2's shape check catches it either way, without anyone seeing
the value.

## Rollback

There is nothing to roll back to: a previous signing secret stops being valid
once Resend issues a new one. If the new value is wrong, repeat steps 1-4 with
the value from Resend's webhook page. Deliveries missed meanwhile are retried
by Resend or can be replayed.

## Related Documents

- [`../resend-email-events.md`](../resend-email-events.md): receiver, stored fields, events feed, first-party measurement
- [`EMERGENCY_ROTATION.md`](./EMERGENCY_ROTATION.md)
- `apps/api/app/routers/v1/email_webhooks.py`, `apps/api/app/services/email_events.py`
- `apps/api/tests/unit/routers/test_email_webhooks_resend.py`

---

**Last Updated:** 2026-09-27
