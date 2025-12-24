# Быстрое подключение Backend к Frontend на Railway

Краткая инструкция для быстрого подключения.

## Предварительные требования

- ✅ Frontend уже работает на Railway
- ✅ У вас есть доступ к Railway Dashboard
- ✅ У вас есть API ключи: Qdrant, OpenRouter

## Быстрые шаги

### 1. Создать Backend сервис

1. Railway Dashboard → ваш проект → **"New"** → **"GitHub Repo"**
2. Выберите `Rag_bot_vladislav`
3. Railway автоматически определит backend

### 2. Создать PostgreSQL

1. **"New"** → **"Database"** → **"PostgreSQL"**
2. Готово! Railway автоматически подключит к backend

### 3. Настроить переменные Backend

**Settings** → **Variables** → скопируйте из `backend/.env.example.railway`:

**Обязательно измените:**
- `QDRANT_URL` и `QDRANT_API_KEY` - ваши ключи Qdrant
- `OPENROUTER_API_KEY` - ваш ключ OpenRouter
- `CORS_ORIGINS` - URL вашего frontend (например: `https://ragbotvladislav-test.up.railway.app`)
- `ADMIN_SECRET_KEY` и `ADMIN_SESSION_SECRET` - свои секретные ключи (минимум 32 символа)

**Остальное можно оставить как есть** (Railway автоматически подставит `DATABASE_URL` и `BACKEND_URL`)

### 4. Дождаться деплоя Backend

1. Railway автоматически начнет деплой
2. Дождитесь успешного завершения
3. Запишите URL backend (в настройках сервиса)

### 5. Обновить переменные Frontend

**Settings** → **Variables** → измените:

```bash
NEXT_PUBLIC_USE_MOCK_API=false
NEXT_PUBLIC_BACKEND_URL=${{Backend.RAILWAY_PUBLIC_DOMAIN}}
```

Или явно:
```bash
NEXT_PUBLIC_BACKEND_URL=https://your-backend-service.up.railway.app
```

### 6. Проверить

1. Откройте: `https://your-backend.up.railway.app/health` → должно быть `{"status": "healthy"}`
2. Откройте: `https://your-backend.up.railway.app/api/test-cors` → должно быть JSON
3. Откройте frontend → консоль браузера (F12) → проверьте, что запросы идут на backend

### 7. Создать администратора

Railway Dashboard → Backend сервис → **Shell** → выполните:
```bash
python backend/create_admin_auto.py
```

## Готово!

Теперь frontend подключен к backend. Все запросы идут на реальный API.

## Проблемы?

См. подробную инструкцию: `RAILWAY_BACKEND_FRONTEND_CONNECT.md`


