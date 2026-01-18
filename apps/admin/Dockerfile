# Multi-stage Next.js Dockerfile for Janua Admin
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
COPY apps/admin/package.json ./apps/admin/

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

# Copy admin source
COPY apps/admin ./apps/admin

# Set working directory to admin
WORKDIR /app/apps/admin

# Enable Next.js standalone output for minimal image size
ENV NEXT_TELEMETRY_DISABLED=1
RUN pnpm build

# Debug: List standalone output structure
RUN ls -la .next/standalone/ || true
RUN ls -la .next/standalone/apps/admin/ || true

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
COPY --from=builder --chown=nextjs:nodejs /app/apps/admin/.next/standalone ./apps/admin/.next/standalone

# Copy the ROOT workspace's node_modules/.pnpm to where symlinks resolve
COPY --from=builder --chown=nextjs:nodejs /app/node_modules/.pnpm ./apps/admin/.next/node_modules/.pnpm

# Fix the symlinks: Remove broken symlinks and replace with copies from pnpm store
# The symlinks in standalone point to relative paths that don't exist
# Use find to dynamically locate the correct package paths (avoids hardcoding version hashes)
RUN cd /app/apps/admin/.next/standalone/node_modules && \
    rm -f next react react-dom && \
    NEXT_PATH=$(find ../../node_modules/.pnpm -type d -name "next" -path "*/node_modules/next" | head -1) && \
    REACT_PATH=$(find ../../node_modules/.pnpm -type d -name "react" -path "*/react@*/node_modules/react" | head -1) && \
    REACT_DOM_PATH=$(find ../../node_modules/.pnpm -type d -name "react-dom" -path "*/react-dom@*/node_modules/react-dom" | head -1) && \
    ln -s "$NEXT_PATH" next && \
    ln -s "$REACT_PATH" react && \
    ln -s "$REACT_DOM_PATH" react-dom

# Copy static files
COPY --from=builder --chown=nextjs:nodejs /app/apps/admin/.next/static ./apps/admin/.next/standalone/.next/static

# Copy public folder
COPY --from=builder /app/apps/admin/public ./apps/admin/.next/standalone/public

# Fix ownership after RUN command
RUN chown -R nextjs:nodejs /app/apps/admin/.next/standalone/node_modules

USER nextjs

# Set working directory to where server.js is located
WORKDIR /app/apps/admin/.next/standalone

# Environment variables
ENV INTERNAL_API_URL="" \
    NEXT_PUBLIC_API_URL="" \
    NEXT_PUBLIC_JANUA_API_URL="" \
    NEXT_PUBLIC_APP_URL=""

EXPOSE 3000

ENV PORT=3000
ENV HOSTNAME="0.0.0.0"

HEALTHCHECK --interval=30s --timeout=3s \
  CMD node -e "require('http').get('http://localhost:3000', (r) => process.exit(r.statusCode === 200 ? 0 : 1))" || exit 1

CMD ["node", "server.js"]
