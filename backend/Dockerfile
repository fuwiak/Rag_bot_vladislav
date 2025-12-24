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
cd /app\n\
# Применяем все head ревизии (если есть несколько веток)\n\
alembic upgrade heads 2>&1 | tee /tmp/migration.log || {\n\
  echo "Migration failed, checking current state..."\n\
  alembic current 2>&1 || true\n\
  echo "Retrying migration..."\n\
  sleep 3\n\
  alembic upgrade heads 2>&1 | tee -a /tmp/migration.log || {\n\
    echo "Migration failed again, trying to apply manually..."\n\
    python -c "\n\
import asyncio\n\
import sys\n\
sys.path.insert(0, '\''/app'\'')\n\
from sqlalchemy import text\n\
from app.core.database import AsyncSessionLocal\n\
async def apply_manual():\n\
    async with AsyncSessionLocal() as db:\n\
        try:\n\
            # Проверяем и добавляем bot_is_active если нужно\n\
            result = await db.execute(text(\"\"\"\n\
                SELECT column_name FROM information_schema.columns \n\
                WHERE table_name = '\''projects'\'' AND column_name = '\''bot_is_active'\''\n\
            \"\"\"))\n\
            if result.first() is None:\n\
                await db.execute(text(\"\"\"\n\
                    ALTER TABLE projects \n\
                    ADD COLUMN bot_is_active VARCHAR(10) DEFAULT '\''false'\'' NOT NULL\n\
                \"\"\"))\n\
                await db.execute(text(\"\"\"\n\
                    UPDATE projects SET bot_is_active = '\''true'\'' WHERE bot_token IS NOT NULL\n\
                \"\"\"))\n\
                await db.commit()\n\
                print(\"✅ Column bot_is_active added\")\n\
            else:\n\
                print(\"Column bot_is_active already exists\")\n\
            \n\
            # Проверяем и добавляем summary если нужно\n\
            result = await db.execute(text(\"\"\"\n\
                SELECT column_name FROM information_schema.columns \n\
                WHERE table_name = '\''documents'\'' AND column_name = '\''summary'\''\n\
            \"\"\"))\n\
            if result.first() is None:\n\
                await db.execute(text(\"\"\"\n\
                    ALTER TABLE documents \n\
                    ADD COLUMN summary TEXT\n\
                \"\"\"))\n\
                await db.commit()\n\
                print(\"✅ Column summary added\")\n\
            else:\n\
                print(\"Column summary already exists\")\n\
            \n\
            # Проверяем и добавляем telegram_id если нужно\n\
            result = await db.execute(text(\"\"\"\n\
                SELECT column_name FROM information_schema.columns \n\
                WHERE table_name = '\''users'\'' AND column_name = '\''telegram_id'\''\n\
            \"\"\"))\n\
            if result.first() is None:\n\
                await db.execute(text(\"\"\"\n\
                    ALTER TABLE users \n\
                    ADD COLUMN telegram_id VARCHAR(50)\n\
                \"\"\"))\n\
                await db.commit()\n\
                print(\"✅ Column telegram_id added\")\n\
            else:\n\
                print(\"Column telegram_id already exists\")\n\
            \n\
            print(\"✅ All manual migrations applied successfully!\")\n\
        except Exception as e:\n\
            print(f\"Manual migration error: {e}\")\n\
            await db.rollback()\n\
asyncio.run(apply_manual())\n\
    "\n\
  }\n\
}\n\
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









