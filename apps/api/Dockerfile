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

# Create non-root user and set ownership
RUN useradd -m -u 1001 janua && \
    chown -R janua:janua /app

USER janua

# Environment variables (inject via Docker Compose)
ENV DATABASE_URL="" \
    JWT_SECRET="" \
    CORS_ORIGINS="" \
    EMAIL_PROVIDER="" \
    LOG_LEVEL="info"

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=3s --start-period=10s \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
