# Отладка переменных окружения в Railway

## Проблема: переменные NEXT_PUBLIC_* не применяются

Если вы видите ошибки с `localhost:8000`, это означает, что переменные `NEXT_PUBLIC_*` не встроились в код при сборке.

## Критически важно

**Переменные `NEXT_PUBLIC_*` встраиваются в JavaScript код во время сборки Next.js!**

Это означает:
- ✅ Изменение переменных требует **пересборки** приложения
- ✅ Railway автоматически пересобирает после изменения переменных
- ⚠️ Но переменные должны быть установлены **ДО** начала сборки

## Пошаговая инструкция

### Шаг 1: Проверьте текущие переменные

1. Railway Dashboard → **Frontend сервис** → **Settings** → **Variables**
2. Проверьте наличие:
   - `NEXT_PUBLIC_BACKEND_URL`
   - `NEXT_PUBLIC_USE_MOCK_API`

### Шаг 2: Удалите и пересоздайте переменные

**Важно:** Иногда Railway кэширует старые значения. Лучше пересоздать:

1. **Удалите** переменные:
   - `NEXT_PUBLIC_BACKEND_URL`
   - `NEXT_PUBLIC_USE_MOCK_API`
2. **Сохраните** изменения
3. **Дождитесь** завершения пересборки (если началась)
4. **Добавьте** переменные заново:

```bash
NEXT_PUBLIC_BACKEND_URL=https://ragbotvladislav-backend.up.railway.app
NEXT_PUBLIC_USE_MOCK_API=false
```

**Критично:**
- ❌ Без кавычек: `https://...` (не `"https://..."`)
- ❌ Без trailing slash: `...railway.app` (не `...railway.app/`)
- ❌ Без пробелов вокруг `=`

5. **Сохраните** изменения
6. Railway автоматически начнет пересборку

### Шаг 3: Проверьте логи сборки

1. Railway Dashboard → Frontend сервис → **Deployments**
2. Выберите последний деплой → **Logs**
3. Найдите строки с `NEXT_PUBLIC_BACKEND_URL` или `Building`
4. Убедитесь, что переменные видны во время сборки

### Шаг 4: Проверьте в браузере

1. Откройте frontend: `https://ragbotvladislav-test.up.railway.app/telegram-bots`
2. Откройте консоль браузера (F12)
3. Выполните:
   ```javascript
   console.log('BACKEND_URL:', process.env.NEXT_PUBLIC_BACKEND_URL)
   console.log('USE_MOCK_API:', process.env.NEXT_PUBLIC_USE_MOCK_API)
   ```

**Ожидаемый результат:**
```
BACKEND_URL: https://ragbotvladislav-backend.up.railway.app
USE_MOCK_API: false
```

**Если видите `undefined` или `localhost:8000`:**
- Переменные не встроились в сборку
- Нужно пересобрать приложение

### Шаг 5: Принудительная пересборка

Если переменные все еще не применяются:

1. Railway Dashboard → Frontend сервис → **Settings** → **Deploy**
2. Нажмите **"Redeploy"** или **"Deploy Latest"**
3. Дождитесь завершения сборки

## Альтернативное решение: Runtime конфигурация

Если переменные не работают через `NEXT_PUBLIC_*`, можно использовать runtime конфигурацию через API route.

### Создайте API route для конфигурации

Создайте файл `admin-panel/app/api/config/route.ts`:

```typescript
import { NextResponse } from 'next/server'

export async function GET() {
  return NextResponse.json({
    backendUrl: process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000',
    useMockApi: process.env.NEXT_PUBLIC_USE_MOCK_API === 'true',
  })
}
```

Затем в компонентах загружайте конфигурацию при монтировании.

**Но это не рекомендуется** - лучше исправить переменные окружения.

## Проверка правильности установки

### Правильно:
```bash
NEXT_PUBLIC_BACKEND_URL=https://ragbotvladislav-backend.up.railway.app
NEXT_PUBLIC_USE_MOCK_API=false
```

### Неправильно:
```bash
# С кавычками
NEXT_PUBLIC_BACKEND_URL="https://ragbotvladislav-backend.up.railway.app"

# С trailing slash
NEXT_PUBLIC_BACKEND_URL=https://ragbotvladislav-backend.up.railway.app/

# С пробелами
NEXT_PUBLIC_BACKEND_URL = https://ragbotvladislav-backend.up.railway.app
```

## Отладка через Network tab

1. Откройте консоль браузера (F12) → вкладка **Network**
2. Обновите страницу
3. Найдите запрос к `/api/bots/info`
4. Посмотрите на **Request URL**:
   - ✅ Должно быть: `https://ragbotvladislav-backend.up.railway.app/api/bots/info`
   - ❌ Не должно быть: `http://localhost:8000/api/bots/info`

Если видите `localhost:8000` - переменные не применились.

## Если ничего не помогает

1. **Удалите все переменные** `NEXT_PUBLIC_*`
2. **Сохраните** и дождитесь пересборки
3. **Добавьте переменные заново** (правильные значения)
4. **Сохраните** и дождитесь пересборки
5. **Проверьте** в браузере

## Контакты для поддержки

Если проблема сохраняется после всех шагов:
- Проверьте логи сборки в Railway
- Убедитесь, что backend сервис запущен и доступен
- Проверьте CORS настройки в backend

