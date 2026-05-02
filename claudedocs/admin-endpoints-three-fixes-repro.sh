#!/usr/bin/env bash
# Manual reproduction script for the three admin endpoint fixes shipped on
# branch fix/admin-endpoints-three-fixes.
#
# Symptoms (browser-verified for admin@madfam.io on app.janua.dev before fix):
#   1. GET /api/v1/admin/users?page=1&per_page=20 -> 500 Internal Server Error
#   2. SDK call to list sessions -> 404 Not Found (URL was /sessions, not /api/v1/sessions)
#      AND, even with the URL fixed, GET /api/v1/sessions -> 500 (column name bug)
#   3. GET /api/v1/admin/organizations -> 500 (presented in dashboard as "Network
#      request failed" because the SDK fallback to /api/v1/organizations also 500'd
#      with the same nullable-column root cause).
#
# Usage:
#   export JANUA_ADMIN_TOKEN="eyJhbGc..."          # admin@madfam.io access token
#   export JANUA_API="https://api.janua.dev"        # or http://localhost:4100 for local
#   bash claudedocs/admin-endpoints-three-fixes-repro.sh
#
# Expected output AFTER the fix:
#   [users]   200 (list of users including legacy NULL-flag rows)
#   [orgs]    200 (list of orgs including legacy NULL billing_plan rows)
#   [me]      200 (current session)
#   [list]    200 (active sessions list, ordered by last_activity desc)

set -euo pipefail

JANUA_API="${JANUA_API:-https://api.janua.dev}"
TOKEN="${JANUA_ADMIN_TOKEN:?JANUA_ADMIN_TOKEN must be set}"

curl_admin() {
  local label="$1"; shift
  local path="$1"; shift
  local code
  code=$(curl -sS -o /tmp/janua-${label}.json -w "%{http_code}" \
    -H "Authorization: Bearer ${TOKEN}" \
    -H "Origin: https://app.janua.dev" \
    "${JANUA_API}${path}")
  printf "[%-7s] %s %s\n" "${label}" "${code}" "${path}"
  if [ "${code}" -ge 400 ]; then
    head -c 400 /tmp/janua-${label}.json; echo
  fi
}

echo "=== Fix 1: /api/v1/admin/users (was 500 on legacy NULL booleans) ==="
curl_admin users "/api/v1/admin/users?page=1&per_page=20"

echo
echo "=== Fix 2a: /api/v1/sessions (SDK now uses correct prefix; was 404) ==="
curl_admin me   "/api/v1/sessions/current"
curl_admin list "/api/v1/sessions"

echo
echo "=== Fix 3: /api/v1/admin/organizations (was 500 on legacy NULL billing_plan) ==="
curl_admin orgs "/api/v1/admin/organizations?page=1&per_page=20"

echo
echo "All four endpoints should report 200 after the fix is deployed."
