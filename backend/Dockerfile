# Multi-stage build для оптимизации размера образа

# Stage 1: Builder
FROM python:3.11-slim as builder

WORKDIR /app

# Установка зависимостей для сборки
RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Копирование файлов зависимостей
COPY requirements.txt .

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
COPY . .

# Создание entrypoint скрипта
RUN echo '#!/bin/bash\n\
set -e\n\
echo "Running database migrations..."\n\
alembic upgrade head || echo "Migrations failed or already applied"\n\
echo "Starting application..."\n\
exec "$@"' > /entrypoint.sh && \
    chmod +x /entrypoint.sh

# Добавление локальных пакетов в PATH
ENV PATH=/root/.local/bin:$PATH

# Порт приложения
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import httpx; httpx.get('http://localhost:8000/health', timeout=5)" || exit 1

ENTRYPOINT ["/entrypoint.sh"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

