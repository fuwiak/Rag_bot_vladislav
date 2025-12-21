# Multi-stage build для оптимизации размера образа

# Stage 1: Builder
FROM python:3.11-slim AS builder

WORKDIR /app

# Установка зависимостей для сборки
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Копирование файлов зависимостей
COPY telegram-bots/requirements.txt requirements.txt

# Установка Python зависимостей
RUN pip install --no-cache-dir --user -r requirements.txt

# Stage 2: Runtime
FROM python:3.11-slim

WORKDIR /app

# Копирование установленных пакетов из builder
COPY --from=builder /root/.local /root/.local

# Копирование кода приложения
# Копируем структуру backend для импорта модулей
COPY backend/app/ ./backend/app/
COPY backend/alembic.ini ./backend/
COPY backend/alembic/ ./backend/alembic/

# Копируем main.py бот-сервиса
COPY telegram-bots/main.py ./main.py

# Добавление локальных пакетов в PATH
ENV PATH=/root/.local/bin:$PATH

# Python path для импорта модулей
ENV PYTHONPATH=/app:/app/backend

# Health check - проверяем что процесс работает
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD pgrep -f "python.*main.py" || exit 1

# Запуск бот-сервиса
CMD ["python", "main.py"]

