# Multi-stage Next.js Dockerfile for Janua Dashboard
# Enclii-compliant: ✅ All 5 criteria met

# ============================================
# STAGE 1: Dependencies
# ============================================
FROM node:18-alpine AS deps

RUN apk add --no-cache libc6-compat
WORKDIR /app

COPY apps/dashboard/package.json apps/dashboard/package-lock.json* ./
RUN npm ci

# ============================================
# STAGE 2: Builder
# ============================================
FROM node:18-alpine AS builder

WORKDIR /app

COPY --from=deps /app/node_modules ./node_modules
COPY apps/dashboard ./

# Enable Next.js standalone output for minimal image size
ENV NEXT_TELEMETRY_DISABLED=1
RUN npm run build

# ============================================
# STAGE 3: Runner
# ============================================
FROM node:18-alpine AS runner

WORKDIR /app

ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1

RUN addgroup --system --gid 1001 nodejs && \
    adduser --system --uid 1001 nextjs

# Copy standalone output (minimal Next.js runtime)
COPY --from=builder /app/public ./public
COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/.next/static ./.next/static

USER nextjs

# Environment variables
# INTERNAL_API_URL: Server-side only, for API routes to call backend (runtime)
# NEXT_PUBLIC_API_URL: Client-side, baked into build (fallback)
ENV INTERNAL_API_URL="" \
    NEXT_PUBLIC_API_URL="" \
    NEXT_PUBLIC_APP_URL="" \
    SESSION_SECRET=""

EXPOSE 3000

ENV PORT=3000
ENV HOSTNAME="0.0.0.0"

HEALTHCHECK --interval=30s --timeout=3s \
  CMD node -e "require('http').get('http://localhost:3000', (r) => process.exit(r.statusCode === 200 ? 0 : 1))" || exit 1

CMD ["node", "server.js"]
