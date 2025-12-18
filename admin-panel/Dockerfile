# Multi-stage build для оптимизации размера образа

# Stage 1: Builder
FROM node:18-alpine AS builder

WORKDIR /app

# Копирование файлов зависимостей
COPY package*.json ./

# Установка зависимостей
RUN npm ci

# Копирование исходного кода
COPY . .

# Сборка приложения
RUN npm run build

# Stage 2: Runtime
FROM node:18-alpine AS runner

WORKDIR /app

ENV NODE_ENV production

# Создание непривилегированного пользователя
RUN addgroup --system --gid 1001 nodejs
RUN adduser --system --uid 1001 nextjs

# Копирование собранного приложения из builder
COPY --from=builder /app/public ./public
COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/.next/static ./.next/static

USER nextjs

EXPOSE 3000

# PORT will be provided by Railway via environment variable
ENV PORT=${PORT:-3000}
ENV HOSTNAME="0.0.0.0"

# Health check (uses PORT from environment, defaults to 3000)
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD sh -c "node -e \"require('http').get('http://localhost:' + (process.env.PORT || '3000') + '/api/health', (r) => {process.exit(r.statusCode === 200 ? 0 : 1)})\"" || exit 1

# Next.js standalone server automatically uses PORT from environment
CMD ["node", "server.js"]






