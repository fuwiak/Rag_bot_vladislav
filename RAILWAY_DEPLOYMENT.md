# Инструкция по развертыванию на Railway

Проект разделен на 3 независимых сервиса, которые можно развернуть отдельно на Railway.

## Структура сервисов

1. **Backend** - FastAPI API (`backend/Dockerfile`)
2. **Frontend** - Next.js админ-панель (`admin-panel/Dockerfile`)
3. **Telegram Bots Service** - сервис для управления ботами (`telegram-bots/Dockerfile`)

## Шаг 1: Создание проекта на Railway

1. Создайте новый проект в Railway
2. Добавьте 3 сервиса:
   - Backend Service
   - Frontend Service
   - Telegram Bots Service

## Шаг 2: Настройка SQLite Volume

1. В настройках проекта Railway создайте **Persistent Volume**
2. Назовите volume (например: `sqlite-data`)
3. Примонтируйте volume ко всем трем сервисам:
   - Путь монтирования: `/data`
   - Volume: `sqlite-data`

## Шаг 3: Настройка Backend Service

1. **Root Directory:** `backend`
2. **Dockerfile:** `backend/Dockerfile` (автоматически)
3. **Переменные окружения:**
   ```
   DATABASE_URL=sqlite+aiosqlite:////data/rag_bot.db
   QDRANT_URL=your_qdrant_url
   QDRANT_API_KEY=your_qdrant_key
   OPENROUTER_API_KEY=your_openrouter_key
   ADMIN_SECRET_KEY=your_secret_key
   ADMIN_SESSION_SECRET=your_session_secret
   BACKEND_URL=https://your-backend.railway.app
   CORS_ORIGINS=https://your-frontend.railway.app
   ```

## Шаг 4: Настройка Frontend Service

1. **Root Directory:** `admin-panel`
2. **Dockerfile:** `admin-panel/Dockerfile` (автоматически)
3. **Переменные окружения:**
   ```
   NEXT_PUBLIC_BACKEND_URL=https://your-backend.railway.app
   PORT=3000
   NODE_ENV=production
   ```

## Шаг 5: Настройка Telegram Bots Service

1. **Root Directory:** `telegram-bots`
2. **Dockerfile:** `telegram-bots/Dockerfile` (автоматически)
3. **Переменные окружения:**
   ```
   DATABASE_URL=sqlite+aiosqlite:////data/rag_bot.db
   QDRANT_URL=your_qdrant_url
   QDRANT_API_KEY=your_qdrant_key
   OPENROUTER_API_KEY=your_openrouter_key
   ```

## Шаг 6: Проверка развертывания

1. **Backend:** Проверьте `https://your-backend.railway.app/health`
2. **Frontend:** Откройте `https://your-frontend.railway.app`
3. **Bots Service:** Проверьте логи - должны быть сообщения о запуске ботов

## Важные замечания

- Все три сервиса должны иметь доступ к одному volume `/data`
- SQLite поддерживает множественные чтения, но только одно одновременное письмо
- Бот-сервис автоматически подхватывает изменения в БД каждые 20 секунд
- При первом запуске создайте администратора через скрипт `create_admin.py`

## Резервное копирование

Для создания бэкапа SQLite базы данных:

```bash
python backend/backup_database.py backup
```

Бэкап сохраняется в директории `backups/` в сжатом формате (.db.gz).

## Восстановление из бэкапа

```bash
python backend/backup_database.py restore backups/rag_bot_backup_YYYYMMDD_HHMMSS.db.gz
```

**Внимание:** Восстановление перезапишет текущие данные!









