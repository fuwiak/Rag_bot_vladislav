# Dockerfile для Telegram Bots Service
FROM python:3.11-slim

WORKDIR /app

# Установка зависимостей
RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Копирование requirements из backend
COPY backend/requirements.txt requirements.txt

# Установка Python зависимостей
RUN pip install --no-cache-dir --user -r requirements.txt

# Копирование кода приложения
COPY backend/ ./backend/
COPY telegram-bots/ ./telegram-bots/

# Добавление локальных пакетов в PATH
ENV PATH=/root/.local/bin:$PATH
ENV PYTHONPATH=/app

# Создание entrypoint скрипта с применением миграций перед запуском
RUN echo '#!/bin/bash\n\
set -e\n\
echo "Waiting for database..."\n\
python -c "import asyncio, sys; sys.path.insert(0, '\''/app'\''); from app.core.database import wait_for_db; asyncio.run(wait_for_db(max_retries=10, retry_interval=2))"\n\
echo "Applying Alembic migrations..."\n\
cd /app/backend\n\
alembic upgrade head 2>&1 || {\n\
  echo "Migration failed, retrying..."\n\
  sleep 2\n\
  alembic upgrade head 2>&1 || echo "Warning: Migration failed, but continuing..."\n\
}\n\
echo "Starting Telegram Bots Service..."\n\
exec "$@"' > /entrypoint.sh && \
    chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]

# Команда запуска
CMD ["python", "-m", "telegram-bots.main"]
