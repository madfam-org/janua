# janua MCP server (pilot: transactional email)

This is the **pilot slice** of ecosystem strategic priority **P1 — every service's API
set has an MCP equivalent** (`internal-devops/roadmaps/2026-09-22-ecosystem-strategic-priorities.md`).
It exposes janua's transactional-email API endpoints as typed, purpose-named
[Model Context Protocol](https://modelcontextprotocol.io) tools, generated from
janua's own OpenAPI schema, behind janua's own auth gate.

It is **additive**: it does not change the HTTP API's behavior, and the API/worker
images do not import it. It ships as an optional entrypoint you run when you want an
MCP face on janua.

## What it exposes (the pilot slice)

Four tools, one per endpoint of the internal-email surface
(`/api/v1/internal/email`, defined in `app/routers/v1/email.py`):

| Tool | Endpoint | Purpose |
| --- | --- | --- |
| `janua_email_send` | `POST /api/v1/internal/email/send` | Send a custom transactional email (Resend-backed). |
| `janua_email_send_template` | `POST /api/v1/internal/email/send-template` | Send from the server-side template registry. |
| `janua_email_list_templates` | `GET /api/v1/internal/email/templates` | List renderable templates. |
| `janua_email_health` | `GET /api/v1/internal/email/health` | Report email-subsystem health. |

Why this slice and not all ~45 janua routers: it is the cleanest self-contained
sub-surface behind a single uniform auth gate, and none of the four is irreversible in
the way user provisioning or a fiscal stamp is. The other internal endpoints (user
lifecycle, app-role/capability/scope grants) are **explicitly exempted** in
`coverage.py` with reasons — they keep their HTTP gate, and an MCP tool for them belongs
in a later operator-gated slice. The end-user (JWT) surface is a further slice.

## Run it

The server talks to a **running janua API** over HTTP and authenticates the same way an
internal service caller does. It needs two environment variables and fails closed
without them:

```bash
export JANUA_API_BASE_URL=https://auth.madfam.io      # the janua API to drive
export JANUA_INTERNAL_API_KEY=...                       # the same X-Internal-API-Key the HTTP API requires
python -m app.mcp                                       # serves MCP over stdio
```

An MCP client (Claude Desktop, an agent runtime, `mcp` CLI) launches that command and
speaks MCP over stdio. Example client config entry:

```json
{
  "mcpServers": {
    "janua": {
      "command": "python",
      "args": ["-m", "app.mcp"],
      "env": {
        "JANUA_API_BASE_URL": "https://auth.madfam.io",
        "JANUA_INTERNAL_API_KEY": "..."
      }
    }
  }
}
```

## How the generator maps endpoints → tools

The mapping is done by `generator.py`, which knows nothing about janua beyond an
OpenAPI document and a small per-service override table. For each `(METHOD, path)`:

- **name** — a purpose name from the override table (`janua_email_send`), never
  `call(method, path, body)`. An agent reads intent, not routing.
- **description** — the override's one-line purpose + the endpoint's OpenAPI
  `summary`/`description`.
- **inputSchema** — a JSON Schema built from the operation's path params, query params
  and (for writes) its request-body schema, with `$ref`s inlined so the tool is
  self-describing. Required fields mirror the API's own (`source_app`, `subject`, `to`
  for send).
- **result shape** — the operation's success (2xx) response schema, carried as the
  tool's `outputSchema`.

The **source of truth** is janua's live OpenAPI (`app.main:app.openapi()`).
`scripts/mcp_generate_openapi.py` dumps the email subset of it into the committed
snapshot `app/mcp/openapi_snapshot.json`; the generator reads that snapshot at runtime,
so the MCP server and the offline tests run without importing the whole app. CI keeps
the snapshot honest (see the drift guard below).

```
app.main:app.openapi()  ──(scripts/mcp_generate_openapi.py)──►  openapi_snapshot.json
                                                                        │
                                              generator.generate_tools(snapshot, OVERRIDES)
                                                                        │
                                                                   list of ToolSpec
                                                                        │
                                                  server.JanuaMCPServer  ──►  MCP tools (stdio)
                                                                        │
                                              call_tool → http_client → janua HTTP API (auth gate runs)
```

## The auth model — no back door

This is the load-bearing property. **An MCP tool calls janua's own HTTP endpoint**; it
does not import a handler, touch the database, or re-implement anything. Each tool makes
the same request a service caller would, carrying the same `X-Internal-API-Key` header
the endpoint requires (`verify_internal_api_key` in `app/dependencies.py`). Therefore:

- Every gate the HTTP layer enforces runs, unchanged, on the server side: the internal
  API-key check (503 if janua has no key, 401 on a wrong key), the sender-domain gate
  (`resend_email_service` / `email_sender` — a client display name never pairs with a
  MADFAM address, unverified `from_email` is refused), the template whitelist, and
  per-tenant sender resolution. The MCP surface cannot reach an effect the HTTP endpoint
  would refuse.
- The API key comes from the environment, **never from a tool argument**. An agent
  driving the server chooses which typed tool to call and with what payload; it cannot
  supply, override, or read the key. The MCP process holds the credential the way any
  internal service does.
- The server **fails closed**: no base URL or no key → it refuses to start rather than
  issue unauthenticated calls.
- `POST /send` and `/send-template` return HTTP 200 with `success: false` when Resend
  rejects a message; the tool surfaces that as an error so an agent learns a send did
  not land.
- Endpoints whose action is irreversible/credentialed are marked `operator_gated` in the
  generator; a gated tool is refused before any HTTP call until a confirmation path is
  wired. The email pilot ships **no** gated tools (the destructive internal endpoints are
  exempted, not exposed), but the machinery is in place for the follow-on slice.

## The drift guard — a new endpoint can't ship un-tooled

Two guards, together satisfying P1's "a guard test tying the MCP surface to the API
schema so drift fails CI":

1. **`tests/unit/mcp/test_mcp_coverage_guard.py`** — asserts every email path in the
   snapshot has a tool, every tool maps to a real path, and (against the live app when
   importable) **every** `/api/v1/internal` endpoint is either in `PILOT_SCOPE` (a tool)
   or in `EXEMPTIONS` (a written deferral). A new internal endpoint that is neither
   fails this test.
2. **`scripts/mcp_generate_openapi.py --check`** (and `test_mcp_snapshot_drift.py`) —
   regenerates the snapshot from the live app and fails if the committed file is stale,
   so a change to the email models forces a snapshot update.

The coverage contract lives in `coverage.py` (scope + reasoned exemptions). This mirrors
the estate's coverage-guard style (crea-map's sweeps, tlacuilo's `check-schema`).

## How to extend

**Add an email endpoint to the pilot:** add its `Endpoint` to `PILOT_SCOPE` in
`coverage.py` (with a purpose name), then `python scripts/mcp_generate_openapi.py` to
refresh the snapshot. The generator picks it up; the guard goes green.

**Expose another internal router (later slice):** move its endpoints from `EXEMPTIONS`
to `PILOT_SCOPE`, widen `SUBSET_PREFIX` in the generate script (or capture the whole
`/api/v1/internal` prefix), and for any destructive/credentialed endpoint set
`operator_gated=True` on its override and wire the confirmation path in
`server.call_tool` before enabling it.

## Extraction note (roadmap follow-up)

`generator.py` and `http_client.py` are janua-agnostic — the only janua-specific state
is the `OVERRIDES` table and `coverage.py`. When the shared MCP-generator package the
roadmap calls for is extracted, those two modules move out roughly unchanged and each
service keeps only its scope contract + a thin server wiring its auth. This pilot was
built in-repo deliberately so the pattern is reviewable end to end first.
