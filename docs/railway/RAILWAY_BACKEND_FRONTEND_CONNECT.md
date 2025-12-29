# Подключение Backend к Frontend на Railway

Пошаговая инструкция по подключению backend к существующему frontend сервису на Railway.

## Текущая ситуация

- ✅ Frontend работает: `https://ragbotvladislav-test.up.railway.app`
- ✅ Frontend использует Mock API
- ⏳ Backend нужно развернуть и подключить

## Шаг 1: Создание Backend сервиса

1. Откройте [Railway Dashboard](https://railway.app)
2. В проекте, где находится frontend сервис, нажмите **"New"** → **"GitHub Repo"**
3. Выберите репозиторий `Rag_bot_vladislav`
4. Railway автоматически определит сервис на основе `backend/railway.json`

### Настройка Build

1. Откройте настройки нового backend сервиса
2. Перейдите в **Settings** → **Build**
3. Убедитесь, что:
   - **Root Directory:** пусто (корень проекта)
   - **Dockerfile Path:** `backend/Dockerfile` (должно быть автоматически)

## Шаг 2: Создание PostgreSQL

1. В том же проекте Railway нажмите **"New"** → **"Database"** → **"PostgreSQL"**
2. Railway автоматически создаст PostgreSQL инстанс
3. PostgreSQL автоматически предоставит `DATABASE_URL` через service reference

## Шаг 3: Настройка переменных окружения Backend

В настройках Backend сервиса (**Settings** → **Variables**) добавьте следующие переменные:

### Обязательные переменные

```bash
# База данных (Railway автоматически предоставит через service reference)
# Но можно указать явно:
DATABASE_URL=${{Postgres.DATABASE_URL}}

# Qdrant (векторная БД)
QDRANT_URL=https://your-cluster-id.us-east4-0.gcp.cloud.qdrant.io
QDRANT_API_KEY=your_qdrant_api_key_here

# OpenRouter (LLM API)
OPENROUTER_API_KEY=your_openrouter_api_key_here
OPENROUTER_MODEL_PRIMARY=x-ai/grok-4.1-fast
OPENROUTER_MODEL_FALLBACK=openai/gpt-oss-120b:free
OPENROUTER_TIMEOUT_PRIMARY=30

# Embeddings
EMBEDDING_MODEL=text-embedding-3-small
EMBEDDING_DIMENSION=1536

# Admin Panel Secrets (измените на свои!)
ADMIN_SECRET_KEY=your-secret-key-change-in-production-min-32-chars
ADMIN_SESSION_SECRET=your-session-secret-change-in-production-min-32-chars

# CORS - КРИТИЧНО! URL вашего frontend
CORS_ORIGINS=https://ragbotvladislav-test.up.railway.app

# Application URLs
APP_URL=https://ragbotvladislav-test.up.railway.app
BACKEND_URL=${{Backend.RAILWAY_PUBLIC_DOMAIN}}
```

### Важно про CORS

`CORS_ORIGINS` должен содержать **точный URL** вашего frontend сервиса, включая протокол `https://`. Без этого frontend не сможет делать запросы к backend.

## Шаг 4: Деплой Backend

1. После настройки переменных Railway автоматически начнет деплой
2. Дождитесь успешного завершения сборки
3. Проверьте логи на наличие ошибок
4. Запишите публичный URL backend сервиса (будет в настройках сервиса)

## Шаг 5: Обновление переменных окружения Frontend

В настройках Frontend сервиса (**Settings** → **Variables**) измените:

### Отключение Mock API

```bash
# Изменить с true на false
NEXT_PUBLIC_USE_MOCK_API=false
```

### Указание URL Backend

Используйте service reference (рекомендуется):
```bash
NEXT_PUBLIC_BACKEND_URL=${{Backend.RAILWAY_PUBLIC_DOMAIN}}
```

Или укажите явно URL backend (после получения его из Railway):
```bash
NEXT_PUBLIC_BACKEND_URL=https://your-backend-service.up.railway.app
```

## Шаг 6: Проверка подключения

### 6.1 Проверка Health Check Backend

Откройте в браузере:
```
https://your-backend-service.up.railway.app/health
```

Должен вернуться:
```json
{"status": "healthy"}
```

### 6.2 Проверка CORS

Откройте в браузере:
```
https://your-backend-service.up.railway.app/api/test-cors
```

Должен вернуться JSON с сообщением о работе CORS.

### 6.3 Проверка Frontend

1. Откройте frontend: `https://ragbotvladislav-test.up.railway.app/dashboard`
2. Откройте консоль браузера (F12) → вкладка **Network**
3. Проверьте, что запросы идут на backend URL (не на `/api/mock`)
4. Убедитесь, что нет CORS ошибок в консоли

## Шаг 7: Создание администратора

После успешного деплоя backend создайте администратора:

### Вариант 1: Через Railway Shell

1. В Railway Dashboard откройте Backend сервис
2. Перейдите в **Settings** → **Deploy** → найдите кнопку **"Shell"** или **"Connect"**
3. Выполните:
   ```bash
   python backend/create_admin_auto.py
   ```

### Вариант 2: Через Railway CLI

```bash
railway run python backend/create_admin_auto.py
```

### Вариант 3: Интерактивное создание

```bash
python backend/create_admin.py
```

## Решение проблем

### Backend не запускается

1. Проверьте логи в Railway Dashboard → Backend сервис → **Deployments** → выберите последний деплой → **Logs**
2. Убедитесь, что все обязательные переменные окружения установлены
3. Проверьте подключение к PostgreSQL (должна быть переменная `DATABASE_URL`)

### CORS ошибки в браузере

1. Убедитесь, что `CORS_ORIGINS` содержит **точный URL** frontend (с `https://`)
2. Проверьте, что URL не содержит trailing slash: `https://ragbotvladislav-test.up.railway.app` (не `https://ragbotvladislav-test.up.railway.app/`)
3. Перезапустите backend после изменения `CORS_ORIGINS`

### Frontend не подключается к backend

1. Проверьте, что `NEXT_PUBLIC_USE_MOCK_API=false` в переменных frontend
2. Убедитесь, что `NEXT_PUBLIC_BACKEND_URL` указывает на правильный URL backend
3. Перезапустите frontend после изменения переменных
4. Проверьте консоль браузера (F12) на наличие ошибок

### База данных не инициализируется

1. Проверьте, что PostgreSQL сервис запущен
2. Убедитесь, что `DATABASE_URL` правильно настроен
3. Проверьте логи backend на ошибки миграций Alembic

### Service References не работают

Если `${{Backend.RAILWAY_PUBLIC_DOMAIN}}` не работает:
1. Убедитесь, что backend сервис имеет публичный домен (включен в настройках)
2. Можно указать URL явно: `NEXT_PUBLIC_BACKEND_URL=https://your-backend.up.railway.app`

## Порядок выполнения (чеклист)

- [ ] Создать Backend сервис в Railway
- [ ] Настроить Build конфигурацию (Root Directory пусто, Dockerfile: backend/Dockerfile)
- [ ] Создать PostgreSQL сервис
- [ ] Настроить переменные окружения Backend (все обязательные переменные)
- [ ] Дождаться успешного деплоя Backend
- [ ] Получить публичный URL Backend
- [ ] Обновить переменные Frontend (NEXT_PUBLIC_USE_MOCK_API=false, NEXT_PUBLIC_BACKEND_URL)
- [ ] Проверить health check backend
- [ ] Проверить CORS
- [ ] Проверить подключение frontend к backend
- [ ] Создать администратора

## Полезные ссылки

- [Railway Dashboard](https://railway.app)
- [Railway Documentation](https://docs.railway.app)
- [Service References в Railway](https://docs.railway.app/develop/variables#service-variables)


