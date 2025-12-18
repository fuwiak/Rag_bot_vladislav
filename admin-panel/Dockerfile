# Multi-stage build для оптимизации размера образа

# Stage 1: Builder
FROM node:18-alpine AS builder

WORKDIR /app

# Копирование файлов зависимостей (build context jest root projektu)
COPY admin-panel/package*.json ./

# Установка зависимостей
RUN npm ci

# Копирование исходного кода (build context jest root projektu)
COPY admin-panel/ .

# Сборка приложения
RUN npm run build

# Stage 2: Runtime
FROM node:18-alpine AS runner

WORKDIR /app

ENV NODE_ENV production

# Создание непривилегированного пользователя
RUN addgroup --system --gid 1001 nodejs
RUN adduser --system --uid 1001 nextjs

# Копирование собранного приложения z builder
# Next.js standalone tworzy strukturę w .next/standalone/app
# Kopiujemy całą strukturę standalone do root (server.js jest w standalone)
COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/public ./public
COPY --from=builder --chown=nextjs:nodejs /app/.next/static ./.next/static

USER nextjs

# Railway will set PORT automatically (usually 8080 or dynamic)
EXPOSE 8080

# Next.js standalone server reads PORT from environment automatically
ENV HOSTNAME="0.0.0.0"
ENV PORT=8080

# Health check endpoint (uses PORT from environment)
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD node -e "require('http').get('http://localhost:' + (process.env.PORT || '8080') + '/api/health', (r) => {process.exit(r.statusCode === 200 ? 0 : 1)})" || exit 1

# Next.js standalone server automatically uses PORT from environment variable
# Railway sets PORT automatically via environment, Next.js will read it
# server.js is in the standalone directory (copied to root)
# Next.js standalone creates server.js in .next/standalone/app, but we copy it to root
CMD ["node", "server.js"]






