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

# Команда запуска
CMD ["python", "-m", "telegram-bots.main"]
