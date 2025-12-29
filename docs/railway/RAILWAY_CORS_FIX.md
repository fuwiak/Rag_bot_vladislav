# RAILWAY CORS FIX - Решение проблемы CORS

## Проблема
Ваш фронтенд на `https://ragbotvladislav-test.up.railway.app` не может получить доступ к бэкенду на `https://ragbotvladislav-backend.up.railway.app` из-за CORS политики.

**Ошибка:**
```
Access to fetch at 'https://ragbotvladislav-backend.up.railway.app/api/projects' 
from origin 'https://ragbotvladislav-test.up.railway.app' has been blocked by CORS policy: 
No 'Access-Control-Allow-Origin' header is present on the requested resource.
```

## Причина
Бэкенд не знает, что нужно разрешить запросы от вашего фронтенда. По умолчанию разрешены только `localhost` origins.

## Решение

### Шаг 1: Добавьте переменную окружения CORS_ORIGINS на Railway

1. Откройте Railway Dashboard: https://railway.app/
2. Выберите ваш проект
3. Откройте сервис **Backend** (ragbotvladislav-backend)
4. Перейдите на вкладку **Variables**
5. Нажмите **New Variable**
6. Добавьте новую переменную:
   - **Name:** `CORS_ORIGINS`
   - **Value:** `https://ragbotvladislav-test.up.railway.app,http://localhost:3000`
   
   ⚠️ **ВАЖНО:** Используйте точное имя вашего фронтенда без слеша в конце!

### Шаг 2: Пересоберите бэкенд

После добавления переменной окружения:
1. Railway автоматически перезапустит сервис
2. ИЛИ нажмите **Redeploy** в правом верхнем углу

### Шаг 3: Проверьте что CORS работает

После перезапуска бэкенда:
1. Откройте ваш фронтенд: `https://ragbotvladislav-test.up.railway.app`
2. Откройте Developer Console (F12)
3. Обновите страницу (Cmd/Ctrl + R)
4. Проверьте что больше нет CORS ошибок

## Проверка переменных Railway

Убедитесь что на Railway установлены следующие переменные для **Backend**:

```bash
DATABASE_URL=${{POSTGRES_URL}}
QDRANT_URL=https://239a4026-d673-4b8b-bfab-a99c7044e6b1.us-east4-0.gcp.cloud.qdrant.io
QDRANT_API_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJhY2Nlc3MiOiJtIn0.NXuYO50jGwjYKe_C8sdDkvSoBEb6-BJhfY7zVlEja3I
OPENROUTER_API_KEY=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
OPENROUTER_MODEL_PRIMARY=x-ai/grok-4.1-fast
OPENROUTER_MODEL_FALLBACK=openai/gpt-oss-120b:free
OPENROUTER_TIMEOUT_PRIMARY=30
OPENROUTER_TIMEOUT_FALLBACK=60
EMBEDDING_MODEL=text-embedding-3-small
EMBEDDING_DIMENSION=1536
ADMIN_SECRET_KEY=admin
ADMIN_SESSION_SECRET=admin
BACKEND_URL=https://ragbotvladislav-backend.up.railway.app
APP_URL=https://ragbotvladislav-test.up.railway.app
CORS_ORIGINS=https://ragbotvladislav-test.up.railway.app,http://localhost:3000
```

⚠️ **САМАЯ ВАЖНАЯ переменная для CORS:**
```
CORS_ORIGINS=https://ragbotvladislav-test.up.railway.app,http://localhost:3000
```

## Дополнительная отладка

Если после этого все еще есть проблемы:

### 1. Проверьте логи бэкенда
```bash
# В Railway Dashboard -> Backend -> Deployments -> Latest -> View Logs
# Найдите строку:
# INFO: Parsed CORS origins: ['https://ragbotvladislav-test.up.railway.app', 'http://localhost:3000']
```

### 2. Проверьте что бэкенд доступен
```bash
curl https://ragbotvladislav-backend.up.railway.app/health
# Должно вернуть: {"status":"healthy"}
```

### 3. Проверьте CORS напрямую
```bash
curl -I -X OPTIONS https://ragbotvladislav-backend.up.railway.app/api/projects \
  -H "Origin: https://ragbotvladislav-test.up.railway.app" \
  -H "Access-Control-Request-Method: GET"

# Должно быть в ответе:
# Access-Control-Allow-Origin: https://ragbotvladislav-test.up.railway.app
```

## Что делает CORS_ORIGINS

Когда вы устанавливаете `CORS_ORIGINS`, бэкенд:
1. Читает список разрешенных origins из переменной окружения
2. Добавляет CORS заголовки для всех запросов от этих origins
3. Разрешает браузеру делать запросы с фронтенда на бэкенд

## Альтернативное решение (если не помогло)

Если CORS все еще не работает, можно временно разрешить все origins (НЕ для продакшена!):

```bash
CORS_ORIGINS=*
```

Но это **небезопасно** для продакшена! Используйте только для тестирования.

## Готово! ✅

После выполнения всех шагов:
- ✅ Фронтенд может делать запросы к бэкенду
- ✅ Нет CORS ошибок в консоли
- ✅ API запросы работают нормально
- ✅ Приложение больше не "блокируется и не сбрасывается"

## Проблема с загрузкой файлов

Если приложение "блокируется и сбрасывается" при загрузке файлов, это может быть связано с:

1. **Размером файлов** - проверьте лимиты Railway
2. **Timeout** - большие файлы могут обрабатываться долго
3. **Memory limits** - Railway имеет лимит памяти

Для решения проблем с файлами смотрите: `RAILWAY_FIX_MEMORY_ISSUES.md`
