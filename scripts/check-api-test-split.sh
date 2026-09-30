#!/usr/bin/env bash
# Prove that the two API test jobs in .github/workflows/tests.yml partition the
# suite: every test selected by API_ALL_TESTS_MARKERS is selected by exactly one
# of API_TESTS_MARKERS (job "API Tests (Python)") and
# API_POSTGRES_TESTS_MARKERS (job "API Tests (PostgreSQL)").
#
# Run from apps/api with the three variables exported (the workflow sets them).
# Collection also runs the marker check in apps/api/tests/postgres_service.py.
set -euo pipefail

: "${API_ALL_TESTS_MARKERS:?}" "${API_TESTS_MARKERS:?}" "${API_POSTGRES_TESTS_MARKERS:?}"

dir=$(mktemp -d)
trap 'rm -rf "$dir"' EXIT

collect() {
  # -qq: pytest.ini adds --verbose, so one -q would print the collection tree.
  if ! pytest --collect-only -qq --no-cov -p no:cacheprovider -m "$1" \
    --ignore=tests/integration --ignore=tests/archived --ignore=tests/quarantine \
    >"$dir/$2.log" 2>&1; then
    cat "$dir/$2.log"
    echo "::error::test collection failed for -m \"$1\""
    exit 1
  fi
  # Some parametrize ids embed a fresh uuid4 per collection; normalise them so
  # the three collections compare. Duplicates after that are kept and counted.
  grep -E '^tests/[^ ]+::' "$dir/$2.log" |
    sed -E 's/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/<uuid>/g' |
    LC_ALL=C sort >"$dir/$2" || true
}

collect "$API_ALL_TESTS_MARKERS" all
collect "$API_TESTS_MARKERS" main
collect "$API_POSTGRES_TESTS_MARKERS" postgres

LC_ALL=C sort "$dir/main" "$dir/postgres" >"$dir/union"
both=$(LC_ALL=C comm -12 "$dir/main" "$dir/postgres")
neither=$(LC_ALL=C comm -23 "$dir/all" "$dir/union")
outside=$(LC_ALL=C comm -13 "$dir/all" "$dir/union")

echo "selected: all=$(wc -l <"$dir/all") api-tests=$(wc -l <"$dir/main") api-postgres-tests=$(wc -l <"$dir/postgres")"
status=0
if [ ! -s "$dir/postgres" ]; then
  echo "::error::API_POSTGRES_TESTS_MARKERS selects no tests"
  status=1
fi
if [ -n "$both" ]; then
  echo "::error::tests selected by both jobs:"
  echo "$both"
  status=1
fi
if [ -n "$neither" ]; then
  echo "::error::tests selected by neither job:"
  echo "$neither"
  status=1
fi
if [ -n "$outside" ]; then
  echo "::error::tests selected outside API_ALL_TESTS_MARKERS:"
  echo "$outside"
  status=1
fi
echo "api-postgres-tests selection:"
cat "$dir/postgres"
exit "$status"
