# Telegram Bots Service

Отдельный сервис для управления Telegram ботами.

## Описание

Этот сервис отвечает за запуск и управление всеми Telegram ботами системы. Он работает независимо от backend API и frontend.

## Функциональность

- Автоматический запуск всех ботов при старте
- Периодическая проверка БД на изменения (каждые 20 секунд)
- Автоматическое обновление ботов при изменении проектов
- Graceful shutdown при остановке сервиса

## Развертывание на Railway

1. Создайте новый сервис в Railway
2. Укажите Dockerfile: `telegram-bots/Dockerfile`
3. Настройте переменные окружения (см. ниже)
4. Примонтируйте volume для SQLite (если используется): `/data`

## Переменные окружения

- `DATABASE_URL` - подключение к SQLite (например: `sqlite+aiosqlite:////data/rag_bot.db`)
- `QDRANT_URL`, `QDRANT_API_KEY` - векторная БД
- `OPENROUTER_API_KEY` - LLM API
- И другие настройки из `backend/app/core/config.py`

## Локальный запуск

```bash
cd telegram-bots
python main.py
```

## Структура

- `main.py` - entry point сервиса
- `requirements.txt` - зависимости Python
- `Dockerfile` - образ для развертывания













