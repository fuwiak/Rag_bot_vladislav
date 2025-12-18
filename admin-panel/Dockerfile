# Multi-stage build dla Next.js standalone

# Stage 1: Builder
FROM node:18-alpine AS builder

WORKDIR /app

# Копирование файлов зависимостей
# Build context może być root (Railway) lub admin-panel/ (jeśli Root Directory jest ustawione)
COPY admin-panel/package.json admin-panel/package-lock.json* ./

# Установка зависимостей
RUN npm ci

# Копирование исходного kodu
# Build context może być root (Railway) lub admin-panel/ (jeśli Root Directory jest ustawione)
COPY admin-panel/ .

# Сборка приложения
RUN npm run build

# Stage 2: Runtime
FROM node:18-alpine AS runner

WORKDIR /app

ENV NODE_ENV=production

# Создание непривилегированного пользователя
RUN addgroup --system --gid 1001 nodejs
RUN adduser --system --uid 1001 nextjs

# Копирование собранного приложения z builder
# Next.js standalone tworzy strukturę w .next/standalone
COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/public ./public
COPY --from=builder --chown=nextjs:nodejs /app/.next/static ./.next/static

USER nextjs

# Railway will set PORT automatically (usually 3000 or dynamic)
# Next.js standalone reads PORT from environment variable automatically
EXPOSE 3000

# Next.js standalone server reads PORT from environment automatically
ENV HOSTNAME=0.0.0.0
# PORT will be set by Railway automatically - Next.js will read it from process.env.PORT

# Health check endpoint (uses PORT from environment, Railway sets it automatically)
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD node -e "require('http').get('http://localhost:' + (process.env.PORT || '3000') + '/api/health', (r) => {process.exit(r.statusCode === 200 ? 0 : 1)})" || exit 1

# Next.js standalone server automatically uses PORT from environment variable
# Railway sets PORT automatically via environment, Next.js will read it
# server.js should be in root after copying standalone directory
CMD ["node", "server.js"]


