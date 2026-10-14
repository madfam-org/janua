#!/bin/bash
set -e

# Janua API Docker Entrypoint
# Runs database migrations before starting the application

echo "=== Janua API Startup ==="

# Wait for database to be ready (with timeout)
echo "Waiting for database..."
MAX_RETRIES=30
RETRY_COUNT=0

while [ $RETRY_COUNT -lt $MAX_RETRIES ]; do
    # The readiness probe uses the same explicit transport settings as the
    # runtime and Alembic engines. DATABASE_SSL_MODE=disable (the default)
    # leaves connect_args empty, so unconfigured environments are unchanged.
    if python -c "
from sqlalchemy import create_engine, text
import os
from app.config import settings
from app.core.database_ssl import sync_postgres_options
engine = create_engine(os.environ.get('DATABASE_URL', ''), connect_args=sync_postgres_options(settings))
with engine.connect() as conn:
    conn.execute(text('SELECT 1'))
print('Database is ready')
" 2>/dev/null; then
        break
    fi
    RETRY_COUNT=$((RETRY_COUNT + 1))
    echo "  Attempt $RETRY_COUNT/$MAX_RETRIES - Database not ready, waiting..."
    sleep 2
done

if [ $RETRY_COUNT -eq $MAX_RETRIES ]; then
    echo "ERROR: Database connection failed after $MAX_RETRIES attempts"
    exit 1
fi

# Run database migrations if alembic is available
if [ -f "alembic.ini" ] && [ -d "alembic" ]; then
    echo "Running database migrations..."

    # ---------------------------------------------------------------------
    # 1. Pre-flight: the revision tree must be well-formed.
    #
    # This is a pure repo-integrity check -- it reads alembic/versions/ and
    # needs no database, so it behaves identically in every environment and
    # can never fail because of local schema drift. A tree that does not
    # resolve, or that has forked into multiple heads, is a code defect that
    # makes EVERY later migration unapplyable, so it is fatal.
    #
    # This exact check would have caught the dangling `down_revision` in
    # 004_add_guest_invites ("003_add_product_tiers", an id that never
    # existed) at the first deploy instead of letting production sit seven
    # migrations behind while the log claimed "Migrations complete".
    # ---------------------------------------------------------------------
    if ! HEADS_OUT=$(alembic heads 2>&1); then
        echo "❌ FATAL: alembic revision tree does not resolve."
        echo "$HEADS_OUT"
        echo "   This is a defect in alembic/versions/, not an environment problem."
        exit 1
    fi

    HEAD_COUNT=$(printf '%s\n' "$HEADS_OUT" | grep -c '(head)' || true)
    if [ "$HEAD_COUNT" -ne 1 ]; then
        echo "❌ FATAL: expected exactly 1 alembic head, found ${HEAD_COUNT}."
        echo "$HEADS_OUT"
        echo "   Add a merge revision (alembic merge) to reunify the tree."
        exit 1
    fi

    CURRENT_OUT=$(alembic current 2>/dev/null || echo "unknown")
    echo "  Revision tree OK (1 head). Database at: ${CURRENT_OUT:-<empty>}"

    # ---------------------------------------------------------------------
    # 2. Applying migrations is opt-in.
    #
    # Schema changes to the identity database are a deliberate, operator-run
    # action, not a side effect of a pod restart. Two replicas start
    # concurrently, so auto-upgrade also raced DDL between them.
    # Set JANUA_APPLY_MIGRATIONS=true to apply on boot.
    # ---------------------------------------------------------------------
    if [ "${JANUA_APPLY_MIGRATIONS:-false}" = "true" ]; then
        echo "  JANUA_APPLY_MIGRATIONS=true - applying pending migrations..."
        if alembic upgrade head; then
            echo "✅ Migrations applied; database is at head."
        else
            # No swallowing: a migration that was asked to run and failed is
            # a hard failure. Booting on a half-known schema is what hid the
            # broken chain for months.
            echo "❌ FATAL: alembic upgrade head failed. Refusing to start on an unmigrated schema."
            exit 1
        fi
    else
        # Not applying. Report drift loudly so it is greppable/alertable
        # rather than silently normal.
        #
        # `alembic current` appends "(head)" only when the database is at the
        # single head, so that marker -- not `alembic check`, which diffs
        # models against the DB rather than listing unapplied revisions -- is
        # the correct up-to-date test.
        if printf '%s' "$CURRENT_OUT" | grep -q '(head)'; then
            echo "  No pending migrations."
        else
            echo "⚠️  MIGRATION_DRIFT: pending migrations are NOT applied (JANUA_APPLY_MIGRATIONS is not 'true')."
            echo "⚠️  MIGRATION_DRIFT: database=${CURRENT_OUT:-<empty>} head=${HEADS_OUT}"
            echo "⚠️  MIGRATION_DRIFT: starting API on the CURRENT schema. Apply deliberately when ready."
        fi
    fi
else
    echo "  Skipping migrations (alembic not configured)"
fi

echo "Starting Janua API..."
exec "$@"
