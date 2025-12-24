# Настройка Telegram Bots Service на Railway

## Обзор

Telegram Bots Service - это отдельный сервис, который управляет всеми Telegram ботами. Он должен работать параллельно с Backend сервисом.

## Шаги настройки на Railway

### 1. Создать новый сервис в Railway проекте

1. В Railway проекте нажмите **"New"** → **"GitHub Repo"**
2. Выберите тот же репозиторий, что и для Backend
3. Настройте сервис:
   - **Name**: `telegram-bots` (или любое другое имя)
   - **Root Directory**: (пусто)
   - **Dockerfile Path**: `telegram-bots/Dockerfile`
   - **Start Command**: (оставить пустым, используется CMD из Dockerfile)

### 2. Настроить переменные окружения

Скопируйте **ВСЕ** переменные окружения из Backend сервиса в telegram-bots сервис:

**Обязательные переменные:**
- `DATABASE_URL` - URL базы данных PostgreSQL
- `QDRANT_URL` - URL Qdrant векторной базы
- `QDRANT_API_KEY` - API ключ Qdrant
- `OPENROUTER_API_KEY` - API ключ OpenRouter
- `CORS_ORIGINS` - (опционально, не критично для бот-сервиса)

**Redis (опционально, если используете Celery):**
- `REDIS_URL` или `REDIS_HOST`, `REDIS_PORT`, `REDIS_PASSWORD`, `REDIS_DB`

**Другие настройки:**
- `SKIP_DB_INIT` - установите в `true` (бот-сервис не создает таблицы, только использует их)
- Все остальные переменные из Backend

### 3. Проверить работу

После деплоя проверьте логи telegram-bots сервиса. Должны появиться сообщения:

```
Starting Telegram Bots Service...
Database initialized
All active bots started
Telegram Bots Service started successfully
Projects changed, updating bots...
Bot {token}... is active for projects: [...]
```

### 4. Проверить работу бота

1. Добавьте токен бота через UI (страница "Управление Telegram ботами")
2. Бот автоматически активируется (`bot_is_active="true"`)
3. Подождите до 20 секунд (бот-сервис проверяет изменения каждые 20 секунд)
4. Попробуйте отправить `/start` боту в Telegram
5. Бот должен ответить приветственным сообщением

## Структура сервисов на Railway

```
Railway Project
├── backend (FastAPI сервер)
│   ├── Обрабатывает HTTP запросы
│   ├── Создает/обновляет проекты
│   ├── Загружает документы
│   └── Управляет пользователями
│
├── telegram-bots (Bot Service)
│   ├── Мониторит БД на изменения проектов
│   ├── Запускает/останавливает боты
│   ├── Обрабатывает сообщения от пользователей
│   └── Использует RAG для генерации ответов
│
└── backend-worker (Celery Worker, опционально)
    └── Обрабатывает документы в фоне
```

## Мониторинг

### Логи Backend:
- `[VERIFY TOKEN]` - проверка токена
- `[START BOT]` / `[STOP BOT]` - управление ботами

### Логи telegram-bots:
- `Starting Telegram Bots Service...` - запуск сервиса
- `All active bots started` - все боты запущены
- `Projects changed, updating bots...` - обнаружены изменения
- `Bot {token}... is active for projects: [...]` - бот активирован
- `Stopping bot with token...` - бот остановлен

## Troubleshooting

### Бот не отвечает

1. **Проверьте, что telegram-bots сервис запущен:**
   - Откройте сервис в Railway
   - Проверьте статус (должен быть "Running")
   - Проверьте логи на наличие ошибок

2. **Проверьте, что бот активирован:**
   - В UI проверьте статус бота (должно быть "Настроен" или "Активен")
   - В логах telegram-bots должны быть сообщения о запуске бота

3. **Проверьте токен:**
   - Убедитесь, что токен правильный
   - Проверьте, что бот не заблокирован в Telegram

4. **Проверьте переменные окружения:**
   - `DATABASE_URL` должен быть установлен
   - `OPENROUTER_API_KEY` должен быть установлен
   - `QDRANT_URL` и `QDRANT_API_KEY` должны быть установлены

### Миграция не применяется

1. **Проверьте логи Backend при деплое:**
   - Должно быть: `Applying Alembic migrations...`
   - Должно быть: `Running upgrade ... -> 2025_12_24_bot_is_active`

2. **Если миграция не применяется автоматически, примените вручную через SQL:**
   ```sql
   ALTER TABLE projects ADD COLUMN IF NOT EXISTS bot_is_active VARCHAR(10) DEFAULT 'false' NOT NULL;
   UPDATE projects SET bot_is_active = 'true' WHERE bot_token IS NOT NULL;
   ```

3. **Или используйте скрипт:**
   - В Railway откройте Backend сервис
   - Перейдите в раздел "Deployments" → "Latest" → "Shell"
   - Выполните: `cd /app/backend && python apply_migration_manually.py`

4. **Если ошибка с constraint:**
   - Миграция теперь проверяет существование constraint перед удалением
   - Ошибка должна исчезнуть после следующего деплоя

### Бот-сервис не видит изменения

1. **Проверьте интервал мониторинга:**
   - По умолчанию 20 секунд
   - Подождите до 20 секунд после изменения

2. **Проверьте логи:**
   - Должны быть сообщения `Projects changed, updating bots...`
   - Если нет, проверьте подключение к БД

## Важно

- **Бот-сервис должен иметь доступ к той же БД, что и Backend**
- **Все переменные окружения должны быть одинаковыми**
- **Бот-сервис не создает таблицы, только использует их**
- **Боты активируются автоматически при добавлении токена**

