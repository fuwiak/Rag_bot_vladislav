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
cd /app/backend\n\
python -c "import asyncio, sys; sys.path.insert(0, '\''/app/backend'\''); from app.core.database import wait_for_db; asyncio.run(wait_for_db(max_retries=10, retry_interval=2))"\n\
echo "Applying Alembic migrations..."\n\
alembic upgrade head 2>&1 || {\n\
  echo "Migration failed, trying manual migration..."\n\
  python -c "\n\
import asyncio\n\
import sys\n\
sys.path.insert(0, '\''/app/backend'\'')\n\
from sqlalchemy import text\n\
from app.core.database import AsyncSessionLocal\n\
async def apply_manual():\n\
    async with AsyncSessionLocal() as db:\n\
        try:\n\
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
                print(\"✅ Manual migration applied successfully!\")\n\
            else:\n\
                print(\"Column bot_is_active already exists\")\n\
        except Exception as e:\n\
            print(f\"Manual migration error: {e}\")\n\
            await db.rollback()\n\
asyncio.run(apply_manual())\n\
    "\n\
}\n\
echo "Starting Telegram Bots Service..."\n\
cd /app\n\
exec "$@"' > /entrypoint.sh && \
    chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]

# Команда запуска
CMD ["python", "-m", "telegram-bots.main"]
