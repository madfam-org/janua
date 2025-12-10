# Multi-stage Next.js Dockerfile for Janua Dashboard
# Enclii-compliant: ✅ All 5 criteria met

# ============================================
# STAGE 1: Dependencies (full workspace)
# ============================================
FROM node:18-alpine AS deps

RUN apk add --no-cache libc6-compat
RUN corepack enable && corepack prepare pnpm@9 --activate
WORKDIR /app

# Copy workspace files
COPY pnpm-lock.yaml pnpm-workspace.yaml package.json .npmrc ./
COPY packages/ ./packages/
COPY apps/dashboard/package.json ./apps/dashboard/

# Install all workspace dependencies
RUN pnpm install --frozen-lockfile

# ============================================
# STAGE 2: Builder
# ============================================
FROM node:18-alpine AS builder

RUN corepack enable && corepack prepare pnpm@9 --activate
WORKDIR /app

# Copy dependencies from deps stage
COPY --from=deps /app/node_modules ./node_modules
COPY --from=deps /app/packages ./packages

# Copy dashboard source
COPY apps/dashboard ./apps/dashboard

# Set working directory to dashboard
WORKDIR /app/apps/dashboard

# Enable Next.js standalone output for minimal image size
ENV NEXT_TELEMETRY_DISABLED=1
RUN pnpm build

# Debug: List standalone output structure
RUN ls -la .next/standalone/ || true
RUN ls -la .next/standalone/apps/dashboard/ || true

# ============================================
# STAGE 3: Runner
# ============================================
FROM node:18-alpine AS runner

WORKDIR /app

ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1

RUN addgroup --system --gid 1001 nodejs && \
    adduser --system --uid 1001 nextjs

# Copy the standalone output
COPY --from=builder --chown=nextjs:nodejs /app/apps/dashboard/.next/standalone ./apps/dashboard/.next/standalone

# Copy the ROOT workspace's node_modules/.pnpm to where symlinks resolve
COPY --from=builder --chown=nextjs:nodejs /app/node_modules/.pnpm ./apps/dashboard/.next/node_modules/.pnpm

# Fix the symlinks: Remove broken symlinks and replace with copies from pnpm store
# The symlinks in standalone point to relative paths that don't exist
RUN cd /app/apps/dashboard/.next/standalone/node_modules && \
    rm -f next react react-dom && \
    # Create proper symlinks to the pnpm store we copied
    ln -s ../../node_modules/.pnpm/next@15.1.6_@babel+core@7.28.5_@opentelemetry+api@1.9.0_@playwright+test@1.57.0_react-dom@18._adk77sadgjhptgvo6lh42iohzq/node_modules/next next && \
    ln -s ../../node_modules/.pnpm/react@18.3.1/node_modules/react react && \
    ln -s ../../node_modules/.pnpm/react-dom@18.3.1_react@18.3.1/node_modules/react-dom react-dom

# Copy static files
COPY --from=builder --chown=nextjs:nodejs /app/apps/dashboard/.next/static ./apps/dashboard/.next/standalone/.next/static

# Copy public folder
COPY --from=builder /app/apps/dashboard/public ./apps/dashboard/.next/standalone/public

# Fix ownership after RUN command
RUN chown -R nextjs:nodejs /app/apps/dashboard/.next/standalone/node_modules

USER nextjs

# Set working directory to where server.js is located
WORKDIR /app/apps/dashboard/.next/standalone

# Environment variables
# INTERNAL_API_URL: Server-side only, for API routes to call backend (runtime)
# NEXT_PUBLIC_API_URL: Client-side, baked into build (fallback)
ENV INTERNAL_API_URL="" \
    NEXT_PUBLIC_API_URL="" \
    NEXT_PUBLIC_APP_URL=""

EXPOSE 3000

ENV PORT=3000
ENV HOSTNAME="0.0.0.0"

HEALTHCHECK --interval=30s --timeout=3s \
  CMD node -e "require('http').get('http://localhost:3000', (r) => process.exit(r.statusCode === 200 ? 0 : 1))" || exit 1

CMD ["node", "server.js"]
