# Исправление переменных окружения в Railway

## Проблема

Если вы видите ошибку "Ошибка подключения к серверу" и URL показывает `localhost:8000`, это означает, что переменные окружения `NEXT_PUBLIC_*` не были правильно встроены в сборку Next.js.

## Важно: NEXT_PUBLIC_* переменные встраиваются при сборке!

**Критично:** Переменные окружения с префиксом `NEXT_PUBLIC_*` встраиваются в JavaScript код во время сборки Next.js. Это означает:

1. ✅ Изменение переменных требует **пересборки** приложения
2. ✅ Railway автоматически пересобирает при изменении переменных
3. ⚠️ Но нужно убедиться, что переменные установлены **ДО** сборки

## Решение

### Шаг 1: Проверьте переменные в Railway

1. Откройте [Railway Dashboard](https://railway.app)
2. Выберите **Frontend сервис**
3. Перейдите в **Settings** → **Variables**

### Шаг 2: Установите правильные переменные

**Важно:** Убедитесь, что переменные установлены **БЕЗ кавычек** и **БЕЗ trailing slash**:

```bash
# Правильно:
NEXT_PUBLIC_BACKEND_URL=https://ragbotvladislav-backend.up.railway.app
NEXT_PUBLIC_USE_MOCK_API=false

# Неправильно (с кавычками):
NEXT_PUBLIC_BACKEND_URL="https://ragbotvladislav-backend.up.railway.app/"

# Неправильно (с trailing slash):
NEXT_PUBLIC_BACKEND_URL=https://ragbotvladislav-backend.up.railway.app/
```

### Шаг 3: Удалите лишние переменные

Удалите переменную `PYTHONPATH` из Frontend сервиса - она нужна только для Backend:
- ❌ `PYTHONPATH="/app:/app/backend"` - удалите из Frontend

### Шаг 4: Пересоберите приложение

После изменения переменных:

1. Railway автоматически начнет пересборку
2. Или вручную: **Settings** → **Deploy** → **Redeploy**
3. Дождитесь завершения сборки

### Шаг 5: Проверьте результат

1. Откройте frontend: `https://ragbotvladislav-test.up.railway.app/telegram-bots`
2. Откройте консоль браузера (F12) → вкладка **Network**
3. Проверьте, что запросы идут на правильный URL:
   - ✅ Должно быть: `https://ragbotvladislav-backend.up.railway.app/api/bots/info`
   - ❌ Не должно быть: `http://localhost:8000/api/bots/info`

## Правильная конфигурация переменных

### Frontend сервис:

```bash
NEXT_PUBLIC_BACKEND_URL=https://ragbotvladislav-backend.up.railway.app
NEXT_PUBLIC_USE_MOCK_API=false
PORT=3000
NODE_ENV=production
```

**Без кавычек, без trailing slash!**

### Backend сервис:

```bash
DATABASE_URL=${{Postgres.DATABASE_URL}}
QDRANT_URL=https://your-cluster-id.us-east4-0.gcp.cloud.qdrant.io
QDRANT_API_KEY=your_key
OPENROUTER_API_KEY=your_key
CORS_ORIGINS=https://ragbotvladislav-test.up.railway.app
# ... и другие переменные
```

## Отладка

### Проверка переменных в браузере

1. Откройте консоль браузера (F12)
2. Выполните:
   ```javascript
   console.log('BACKEND_URL:', process.env.NEXT_PUBLIC_BACKEND_URL)
   console.log('USE_MOCK_API:', process.env.NEXT_PUBLIC_USE_MOCK_API)
   ```

Если видите `undefined` или `localhost:8000` - переменные не встроились в сборку.

### Проверка логов сборки

1. Railway Dashboard → Frontend сервис → **Deployments**
2. Выберите последний деплой → **Logs**
3. Проверьте, что переменные видны во время сборки

### Принудительная пересборка

Если переменные не применяются:

1. Удалите все переменные `NEXT_PUBLIC_*`
2. Сохраните
3. Добавьте их заново (правильные значения, без кавычек)
4. Сохраните
5. Railway автоматически пересоберет

## Частые ошибки

### Ошибка: Переменные в кавычках

```bash
# Неправильно:
NEXT_PUBLIC_BACKEND_URL="https://ragbotvladislav-backend.up.railway.app"

# Правильно:
NEXT_PUBLIC_BACKEND_URL=https://ragbotvladislav-backend.up.railway.app
```

Railway автоматически обрабатывает значения, кавычки не нужны.

### Ошибка: Trailing slash

```bash
# Неправильно:
NEXT_PUBLIC_BACKEND_URL=https://ragbotvladislav-backend.up.railway.app/

# Правильно:
NEXT_PUBLIC_BACKEND_URL=https://ragbotvladislav-backend.up.railway.app
```

Код теперь автоматически убирает trailing slash, но лучше установить правильно.

### Ошибка: Переменные не применяются

**Причина:** Next.js встраивает `NEXT_PUBLIC_*` переменные во время сборки.

**Решение:**
1. Убедитесь, что переменные установлены ДО сборки
2. Пересоберите приложение после изменения переменных
3. Проверьте логи сборки

## Готово!

После правильной настройки переменных и пересборки frontend должен подключиться к backend.


