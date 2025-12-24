# Multi-stage build для оптимизации размера образа

# Stage 1: Builder
FROM python:3.11-slim AS builder

WORKDIR /app

# Установка зависимостей для сборки
RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Копирование файлов зависимостей
# Build context всегда root проекта, поэтому указываем полный путь
COPY backend/requirements.txt requirements.txt

# Установка Python зависимостей
RUN pip install --no-cache-dir --user -r requirements.txt

# Stage 2: Runtime
FROM python:3.11-slim

WORKDIR /app

# Установка runtime зависимостей
RUN apt-get update && apt-get install -y \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Копирование установленных пакетов из builder
COPY --from=builder /root/.local /root/.local

# Копирование кода приложения
# Build context - root проекта, копируем из backend/
COPY backend/ .

# Создание entrypoint скрипта с применением миграций
RUN echo '#!/bin/bash\n\
set -e\n\
echo "Waiting for database..."\n\
python -c "import asyncio, sys; sys.path.insert(0, '\''/app'\''); from app.core.database import wait_for_db; asyncio.run(wait_for_db(max_retries=10, retry_interval=2))"\n\
echo "Applying Alembic migrations..."\n\
cd /app && alembic upgrade head || echo "Warning: Migration failed, but continuing..."\n\
echo "Starting application..."\n\
exec "$@"' > /entrypoint.sh && \
    chmod +x /entrypoint.sh

# Добавление локальных пакетов в PATH
ENV PATH=/root/.local/bin:$PATH

# Порт приложения (Railway will provide PORT via environment variable)
EXPOSE 8000

# Health check (uses PORT from environment, defaults to 8000)
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD sh -c "python -c \"import httpx, os; httpx.get('http://localhost:' + os.environ.get('PORT', '8000') + '/health', timeout=5)\"" || exit 1

ENTRYPOINT ["/entrypoint.sh"]
# Use PORT from environment variable (Railway provides this)
# Default to 8000 if PORT is not set
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]









