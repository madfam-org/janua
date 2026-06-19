# Janua — Coupler Program (ConnectedAccount / Keyring)

**Status:** P1 implementation in progress (migration 008, connections API shipped 2026-06-19)  
**Program start:** 2026-06-16 (target)  
**ADR:** [architecture/ADR-002_UNIVERSAL_KEYRING.md](./architecture/ADR-002_UNIVERSAL_KEYRING.md) — **ACCEPTED** (implementation in progress)  
**Cross-repo plan:** [enclii/docs/strategy/COUPLER_REMEDIATION_PLAN.md](https://github.com/madfam-org/enclii/blob/main/docs/strategy/COUPLER_REMEDIATION_PLAN.md)

---

## 1. Janua role in the Agent Tool Plane

Janua owns **identity, org/RBAC, and credential vault** for end-user delegated SaaS access. Coupler (`madfam-org/coupler`, AGPL-3.0) owns tool registry, execute, MCP, sandbox, and triggers.

| Janua owns | Janua does NOT own |
|------------|-------------------|
| `ConnectedAccount` model + encryption | Connector-specific API calls (Slack, Gmail, etc.) |
| OAuth authorize/callback for SaaS providers | MCP servers for third-party SaaS |
| Short-lived token delegation API for ATP | Tool execution state or logs |
| Audit ingest for `connection.*`, `tool.delegation.*` | Long-lived refresh tokens outside vault |

**Policy:** zero Composio spend; no dependency on `backend.composio.dev`.

---

## 2. Phase 1 deliverables (J1-*)

| ID | Deliverable | Exit criteria |
|----|-------------|---------------|
| J1-1 | DB migrations: `connected_accounts`, `provider_types` | Applied staging + prod |
| J1-2 | Encrypt/decrypt service (Vault or AES-GCM per ADR) | Unit tests pass |
| J1-3 | `GET/POST/DELETE /api/v1/connections` | OpenAPI + integration tests |
| J1-4 | OAuth authorize + callback (GitHub, Slack) | E2E connect flow |
| J1-5 | `POST /api/v1/connections/:id/token` (ATP service scope) | Coupler executor smoke |
| J1-6 | Audit ingest: `connection.*`, `tool.delegation.*` | Events queryable |
| J1-7 | Provider registry seed: github, slack, google, notion, linear | Admin UI list |
| J1-8 | This document + cross-links | Linked from Coupler README |

**P1 gate:** Coupler staging executes GitHub `list_repos` with a delegated token from Janua.

---

## 3. API contract (Coupler consumer)

### 3.1 Connection metadata (user/org JWT)

```
GET /api/v1/connections
Authorization: Bearer <user_or_org_jwt>
```

Returns connection list (id, provider_type, provider_name, scopes, expires_at) — **no secrets**.

### 3.2 Start OAuth

```
POST /api/v1/connections/:provider/authorize
Authorization: Bearer <user_jwt>
Body: { "redirect_uri": "...", "scopes": ["..."] }
```

Returns `{ "authorization_url": "..." }`.

### 3.3 Token delegation (ATP service account only)

```
POST /api/v1/connections/:id/token
Authorization: Bearer <coupler_service_jwt>
X-Acting-User-Id: <janua_sub>
Body: { "purpose": "tool_execute", "ttl_seconds": 300 }
```

Returns short-lived access token or opaque delegation handle. Coupler MUST NOT persist refresh tokens.

### 3.4 Audit ingest

```
POST /api/v1/audit/events
Authorization: Bearer <coupler_service_jwt>
Body: { "type": "tool.delegation.issued", "subject_id": "...", "metadata": {...} }
```

---

## 4. OAuth client registration

Coupler gateway registers as ecosystem client:

| Field | Value |
|-------|-------|
| Name | `coupler-api` |
| Audience | `coupler-api` |
| Scopes | `openid`, `profile`, `email`, `connections:delegate` (TBD in OpenAPI) |

Use `janua provision apply -f janua.client.yaml` from the Coupler repo (Phase 0).

---

## 5. Security requirements

- Refresh tokens and API secrets encrypted at rest (ADR-002).
- Token delegation endpoint restricted to Coupler service JWT + explicit user context header.
- Rate limit delegation requests per user/org.
- Audit every delegation and connection revoke.
- No connector code in `janua-api` beyond generic OAuth broker.

---

## 6. Dependencies and sequencing

```text
P0 (Coupler repo bootstrap) ──► Janua client `coupler-api` registered
P1 (this epic) ──► blocks Coupler P2 prod execute
Enclii Commercial GA ──► parallel; does not block P1
```

---

## 7. References

- [ADR-002 Universal Keyring](./architecture/ADR-002_UNIVERSAL_KEYRING.md)
- [Ecosystem Integration — Appendix C](./guides/ECOSYSTEM_INTEGRATION.md#appendix-c-coupler-agent-tool-plane)
- [AGENT_TOOL_PLANE.md](https://github.com/madfam-org/enclii/blob/main/docs/strategy/AGENT_TOOL_PLANE.md)
- [COUPLER_EXECUTION_CHECKLIST.md](https://github.com/madfam-org/enclii/blob/main/docs/strategy/COUPLER_EXECUTION_CHECKLIST.md)
