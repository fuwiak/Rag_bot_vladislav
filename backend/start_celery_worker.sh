#!/bin/bash
# Скрипт для запуска Celery воркера

# Применяем миграции (опционально)
alembic upgrade head 2>/dev/null || true

# Запускаем Celery воркер
# Используем --loglevel=info для детального логирования
# --concurrency=1 для обработки одной задачи за раз (предотвращает out of memory)
celery -A app.celery_app worker --loglevel=info --concurrency=1 --max-tasks-per-child=50

