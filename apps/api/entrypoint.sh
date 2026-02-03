#!/bin/bash
# No set -e — the API must start even if DB/migrations fail.
# FastAPI handles DB unavailability at request time.

echo "=== Janua API Startup ==="

# Run database migrations if DATABASE_URL is set
if [ -n "$DATABASE_URL" ]; then
    echo "Running database migrations..."

    # Wait for database to be ready (max 30 seconds)
    DB_READY=false
    for i in {1..30}; do
        if python -c "
import asyncio
import asyncpg

async def check():
    try:
        conn = await asyncpg.connect('$DATABASE_URL', timeout=5)
        await conn.close()
        return True
    except:
        return False

exit(0 if asyncio.run(check()) else 1)
" 2>/dev/null; then
            echo "Database is ready"
            DB_READY=true
            break
        fi
        echo "Waiting for database... ($i/30)"
        sleep 1
    done

    # Run Alembic migrations only if DB is reachable
    if [ "$DB_READY" = true ]; then
        cd /app
        if alembic upgrade head 2>&1; then
            echo "✅ Database migrations completed successfully"
        else
            echo "⚠️ Migration failed — starting API anyway"
        fi
    else
        echo "⚠️ Database not reachable after 30s — starting API anyway"
    fi
else
    echo "⚠️ DATABASE_URL not set, skipping migrations"
fi

echo "Starting Janua API..."
exec "$@"
