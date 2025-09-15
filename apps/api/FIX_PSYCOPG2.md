# Fix for Container Startup Error - Missing psycopg2

## Problem
The API container was failing to start with the error:
```
ModuleNotFoundError: No module named 'psycopg2'
```

This occurred when SQLAlchemy tried to create a PostgreSQL database connection.

## Root Cause
The `requirements.txt` file was missing the `psycopg2-binary` package, which is required by SQLAlchemy to connect to PostgreSQL databases. While `asyncpg` was present for async operations, SQLAlchemy's synchronous operations require `psycopg2`.

## Solution Applied

### 1. Added psycopg2-binary to requirements.txt
```diff
asyncpg==0.29.0
+psycopg2-binary==2.9.9
redis==5.0.1
```

### 2. Updated Dockerfile to include PostgreSQL development libraries
```diff
# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
+   libpq-dev \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*
```

### 3. Created docker-compose.yml for local testing
A complete docker-compose configuration was added to facilitate local development and testing with PostgreSQL and Redis.

## Testing Instructions

1. **Local Docker Testing:**
   ```bash
   cd apps/api
   docker-compose up --build
   ```

2. **Production Deployment:**
   The fix will be automatically applied when the container is rebuilt in production.

## Why psycopg2-binary?
- `psycopg2-binary` is the pre-compiled wheel package that includes PostgreSQL libraries
- It's suitable for development and production environments
- Alternative: `psycopg2` requires compilation but is slightly more performant
- For this project, `psycopg2-binary` is the better choice for easier deployment

## Verification
After applying this fix, the container should:
1. Start successfully without import errors
2. Connect to PostgreSQL database
3. Run database migrations via Alembic
4. Serve the FastAPI application on port 8000