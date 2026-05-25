#!/usr/bin/env bash
# Hosted Janua auth synthetic probe.
#
# Public mode validates health, OIDC discovery, and JWKS without secrets.
# Strict mode validates token exchange when synthetic client credentials are
# supplied. The script never prints tokens or secret values.

set -euo pipefail

API_URL="${API_URL:-https://api.janua.dev}"
ISSUER_URL="${ISSUER_URL:-https://auth.madfam.io}"
EXPECTED_ISSUER="${EXPECTED_ISSUER:-$ISSUER_URL}"
TIMEOUT="${TIMEOUT:-10}"
SUMMARY_PATH="${SUMMARY_PATH:-janua-hosted-auth-synthetic-summary.json}"
REQUIRE_STRICT_TOKEN="${REQUIRE_STRICT_TOKEN:-false}"

CLIENT_ID="${JANUA_SYNTHETIC_CLIENT_ID:-}"
CLIENT_SECRET="${JANUA_SYNTHETIC_CLIENT_SECRET:-}"
TOKEN_AUDIENCE="${JANUA_SYNTHETIC_TOKEN_AUDIENCE:-}"
TOKEN_SCOPE="${JANUA_SYNTHETIC_SCOPE:-openid profile email}"

PASS_COUNT=0
FAIL_COUNT=0
SKIP_COUNT=0
DISCOVERY_FILE="$(mktemp)"
JWKS_FILE="$(mktemp)"
TOKEN_FILE="$(mktemp)"
MISSING_FIELDS_FILE="$(mktemp)"

cleanup() {
  rm -f "$DISCOVERY_FILE" "$JWKS_FILE" "$TOKEN_FILE" "$MISSING_FIELDS_FILE"
}
trap cleanup EXIT

record() {
  local status="$1"
  local name="$2"
  local detail="${3:-}"

  case "$status" in
    pass)
      PASS_COUNT=$((PASS_COUNT + 1))
      printf "PASS %s" "$name"
      ;;
    fail)
      FAIL_COUNT=$((FAIL_COUNT + 1))
      printf "FAIL %s" "$name"
      ;;
    skip)
      SKIP_COUNT=$((SKIP_COUNT + 1))
      printf "SKIP %s" "$name"
      ;;
    *)
      FAIL_COUNT=$((FAIL_COUNT + 1))
      printf "FAIL %s" "$name"
      detail="invalid synthetic status: $status"
      ;;
  esac

  if [ -n "$detail" ]; then
    printf " - %s" "$detail"
  fi
  printf "\n"
}

http_json() {
  local url="$1"
  local output="$2"
  local code

  code="$(curl -sS --max-time "$TIMEOUT" -H "Accept: application/json" -o "$output" -w "%{http_code}" "$url")" || return 1
  [ "$code" = "200" ]
}

json_get() {
  local file="$1"
  local expr="$2"

  python3 - "$file" "$expr" <<'PY'
import json
import sys

path, expr = sys.argv[1], sys.argv[2]
with open(path, "r", encoding="utf-8") as f:
    data = json.load(f)

value = data
for part in expr.split("."):
    if not part:
        continue
    if isinstance(value, dict):
        value = value.get(part)
    else:
        value = None
        break

if value is None:
    sys.exit(1)
if isinstance(value, (dict, list)):
    print(json.dumps(value, separators=(",", ":")))
else:
    print(value)
PY
}

json_require_fields() {
  local file="$1"
  shift

  python3 - "$file" "$@" <<'PY'
import json
import sys

path = sys.argv[1]
fields = sys.argv[2:]
with open(path, "r", encoding="utf-8") as f:
    data = json.load(f)

missing = [field for field in fields if not data.get(field)]
if missing:
    print(",".join(missing))
    sys.exit(1)
PY
}

write_summary() {
  python3 - "$SUMMARY_PATH" "$PASS_COUNT" "$FAIL_COUNT" "$SKIP_COUNT" "$API_URL" "$ISSUER_URL" <<'PY'
import json
import sys
from datetime import datetime, timezone

path, passed, failed, skipped, api_url, issuer_url = sys.argv[1:]
payload = {
    "checked_at": datetime.now(timezone.utc).isoformat(),
    "api_url": api_url,
    "issuer_url": issuer_url,
    "passed": int(passed),
    "failed": int(failed),
    "skipped": int(skipped),
}
with open(path, "w", encoding="utf-8") as f:
    json.dump(payload, f, indent=2)
    f.write("\n")
PY
}

printf "Janua hosted auth synthetic\n"
printf "API_URL=%s\n" "$API_URL"
printf "ISSUER_URL=%s\n" "$ISSUER_URL"
printf "EXPECTED_ISSUER=%s\n" "$EXPECTED_ISSUER"

if http_json "$API_URL/health" "$TOKEN_FILE" && grep -q '"healthy"' "$TOKEN_FILE"; then
  record pass "api health"
else
  record fail "api health" "expected HTTP 200 JSON containing healthy"
fi

DISCOVERY_URL="${ISSUER_URL%/}/.well-known/openid-configuration"
if http_json "$DISCOVERY_URL" "$DISCOVERY_FILE"; then
  record pass "oidc discovery fetch"
else
  record fail "oidc discovery fetch" "expected HTTP 200 from $DISCOVERY_URL"
fi

if json_require_fields "$DISCOVERY_FILE" issuer jwks_uri authorization_endpoint token_endpoint >"$MISSING_FIELDS_FILE" 2>/dev/null; then
  record pass "oidc required fields"
else
  missing="$(cat "$MISSING_FIELDS_FILE" 2>/dev/null || true)"
  record fail "oidc required fields" "missing ${missing:-unknown fields}"
fi

issuer="$(json_get "$DISCOVERY_FILE" issuer 2>/dev/null || true)"
if [ "$issuer" = "$EXPECTED_ISSUER" ]; then
  record pass "issuer match"
else
  record fail "issuer match" "expected $EXPECTED_ISSUER got ${issuer:-empty}"
fi

jwks_uri="$(json_get "$DISCOVERY_FILE" jwks_uri 2>/dev/null || true)"
if [ -n "$jwks_uri" ] && http_json "$jwks_uri" "$JWKS_FILE"; then
  record pass "jwks fetch"
else
  record fail "jwks fetch" "expected HTTP 200 from jwks_uri"
fi

key_count="$(
  python3 - "$JWKS_FILE" <<'PY' 2>/dev/null || true
import json
import sys

with open(sys.argv[1], "r", encoding="utf-8") as f:
    data = json.load(f)
keys = data.get("keys") or []
valid = [k for k in keys if k.get("kid") and k.get("kty")]
print(len(valid))
PY
)"
if [ "${key_count:-0}" -gt 0 ]; then
  record pass "jwks key material" "valid_keys=$key_count"
else
  record fail "jwks key material" "no public keys with kid and kty"
fi

token_endpoint="$(json_get "$DISCOVERY_FILE" token_endpoint 2>/dev/null || true)"
if [ -n "$CLIENT_ID" ] && [ -n "$CLIENT_SECRET" ] && [ -n "$token_endpoint" ]; then
  args=(-sS --max-time "$TIMEOUT" -o "$TOKEN_FILE" -w "%{http_code}" -X POST "$token_endpoint")
  args+=(-H "Content-Type: application/x-www-form-urlencoded")
  args+=(-u "$CLIENT_ID:$CLIENT_SECRET")
  args+=(--data-urlencode "grant_type=client_credentials")
  args+=(--data-urlencode "scope=$TOKEN_SCOPE")
  if [ -n "$TOKEN_AUDIENCE" ]; then
    args+=(--data-urlencode "audience=$TOKEN_AUDIENCE")
  fi

  code="$(curl "${args[@]}")" || code="curl_error"
  if [ "$code" = "200" ] && json_get "$TOKEN_FILE" access_token >/dev/null 2>&1; then
    record pass "client credentials token exchange" "token received without printing secret material"
  else
    record fail "client credentials token exchange" "HTTP $code"
  fi
elif [ "$REQUIRE_STRICT_TOKEN" = "true" ]; then
  record fail "client credentials token exchange" "strict token mode requires JANUA_SYNTHETIC_CLIENT_ID and JANUA_SYNTHETIC_CLIENT_SECRET"
else
  record skip "client credentials token exchange" "set JANUA_SYNTHETIC_CLIENT_ID and JANUA_SYNTHETIC_CLIENT_SECRET for strict proof"
fi

write_summary
printf "Summary written to %s\n" "$SUMMARY_PATH"
printf "passed=%s failed=%s skipped=%s\n" "$PASS_COUNT" "$FAIL_COUNT" "$SKIP_COUNT"

if [ "$FAIL_COUNT" -gt 0 ]; then
  exit 1
fi
