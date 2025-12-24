#!/bin/bash
# Скрипт для запуска backend сервера

# Убиваем процесс на порту 8000 если он занят
lsof -ti:8000 | xargs kill -9 2>/dev/null || true

# Применяем миграции
alembic upgrade head

# Запускаем сервер
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000












