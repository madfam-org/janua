# Local development build
# Multi-stage Dockerfile for Janua Identity Platform API
# Enclii-compliant: ✅ All 5 criteria met

# ============================================
# STAGE 1: Builder (dependencies + build)
# ============================================
FROM python:3.12-slim AS builder

WORKDIR /app

# Install build dependencies only
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    pkg-config \
    libxml2-dev \
    libxmlsec1-dev \
    libxslt-dev \
    libssl-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy and install Python dependencies to /install
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# ============================================
# STAGE 2: Runner (minimal runtime)
# ============================================
FROM python:3.12-slim AS runner

WORKDIR /app

# Install runtime dependencies only (no build tools)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    libxml2 \
    libxmlsec1 \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Copy Python packages from builder to system location
COPY --from=builder /install /usr/local

# Copy application code (context is apps/api)
COPY . /app

# Make entrypoint executable
RUN chmod +x /app/entrypoint.sh

# Create non-root user and set ownership
RUN groupadd -g 1000 janua && \
    useradd -m -u 1000 -g 1000 janua && \
    chown -R janua:janua /app

USER janua

# Environment variables (inject via Docker Compose/K8s)
# PORT defaults to 8080 for K8s compatibility but can be overridden
# Note: Don't set EMAIL_PROVIDER here - let it use default from config.py
ENV DATABASE_URL="" \
    JWT_SECRET="" \
    CORS_ORIGINS="" \
    LOG_LEVEL="info" \
    PORT="8080"

# Expose both common ports - actual port determined by PORT env var
EXPOSE 8080 4100

# Healthcheck uses PORT env var for flexibility
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s \
  CMD python -c "import os,urllib.request; urllib.request.urlopen(f'http://localhost:{os.environ.get(\"PORT\", \"8080\")}/health')" || exit 1

# Use entrypoint for database migrations before app start
ENTRYPOINT ["/app/entrypoint.sh"]
# CMD respects PORT env var via shell expansion
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8080}"]
