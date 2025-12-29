# Исправление ошибки "Ошибка подключения к серверу"

Если вы видите ошибку: **"Ошибка подключения к серверу. Проверьте, что backend запущен на http://localhost:8000"**, это означает, что переменная окружения `NEXT_PUBLIC_BACKEND_URL` не установлена в Railway.

## Быстрое решение

### Шаг 1: Получить URL Backend сервиса

1. Откройте [Railway Dashboard](https://railway.app)
2. Выберите ваш проект
3. Откройте **Backend сервис**
4. Перейдите в **Settings** → **Networking**
5. Найдите **Public Domain** или скопируйте URL из раздела **Domains**
6. URL будет выглядеть примерно так: `https://your-backend-service.up.railway.app`

### Шаг 2: Установить переменную окружения Frontend

1. В Railway Dashboard откройте **Frontend сервис**
2. Перейдите в **Settings** → **Variables**
3. Найдите переменную `NEXT_PUBLIC_BACKEND_URL`
4. Если её нет - нажмите **"Add Variable"**
5. Установите значение:
   ```bash
   NEXT_PUBLIC_BACKEND_URL=https://your-backend-service.up.railway.app
   ```
   (Замените `your-backend-service.up.railway.app` на реальный URL вашего backend)

6. Нажмите **"Save"**

### Шаг 3: Перезапустить Frontend

1. Railway автоматически перезапустит сервис после изменения переменных
2. Или вручную: **Settings** → **Deploy** → **Redeploy**

### Шаг 4: Проверить

1. Откройте frontend: `https://ragbotvladislav-test.up.railway.app/dashboard`
2. Откройте консоль браузера (F12)
3. Проверьте, что запросы идут на правильный URL backend (не на `localhost:8000`)

## Альтернативный способ: Использование Service Reference

Railway позволяет использовать переменные других сервисов автоматически:

1. В настройках Frontend сервиса → **Variables**
2. Добавьте или измените:
   ```bash
   NEXT_PUBLIC_BACKEND_URL=${{Backend.RAILWAY_PUBLIC_DOMAIN}}
   ```

Это автоматически подставит URL backend сервиса.

**Важно:** Убедитесь, что у Backend сервиса включен публичный домен:
- Backend сервис → **Settings** → **Networking** → включите **"Generate Domain"**

## Проверка переменных окружения

Убедитесь, что в Frontend сервисе установлены:

```bash
# Отключить Mock API
NEXT_PUBLIC_USE_MOCK_API=false

# URL Backend (обязательно!)
NEXT_PUBLIC_BACKEND_URL=https://your-backend-service.up.railway.app
# Или используйте service reference:
# NEXT_PUBLIC_BACKEND_URL=${{Backend.RAILWAY_PUBLIC_DOMAIN}}
```

## Отладка

Если проблема сохраняется:

1. **Проверьте консоль браузера (F12)**
   - Откройте вкладку **Network**
   - Посмотрите, на какой URL идут запросы
   - Если видите `localhost:8000` - переменная не установлена

2. **Проверьте переменные в Railway**
   - Frontend сервис → **Settings** → **Variables**
   - Убедитесь, что `NEXT_PUBLIC_BACKEND_URL` установлена
   - Убедитесь, что значение правильное (начинается с `https://`)

3. **Проверьте, что Backend запущен**
   - Backend сервис → **Deployments** → проверьте последний деплой
   - Убедитесь, что статус **"Active"**
   - Откройте URL backend: `https://your-backend.up.railway.app/health`
   - Должно вернуться: `{"status": "healthy"}`

4. **Проверьте CORS**
   - В Backend сервисе переменная `CORS_ORIGINS` должна содержать URL frontend
   - Например: `CORS_ORIGINS=https://ragbotvladislav-test.up.railway.app`

## Частые ошибки

### Ошибка: "Failed to fetch"

**Причина:** Backend недоступен или CORS не настроен

**Решение:**
1. Проверьте, что backend запущен
2. Проверьте `CORS_ORIGINS` в backend
3. Проверьте, что `NEXT_PUBLIC_BACKEND_URL` правильный

### Ошибка: "Network error"

**Причина:** Неправильный URL backend

**Решение:**
1. Проверьте `NEXT_PUBLIC_BACKEND_URL` - должен начинаться с `https://`
2. Убедитесь, что URL не содержит `localhost`

### Frontend все еще использует Mock API

**Причина:** `NEXT_PUBLIC_USE_MOCK_API` установлен в `true`

**Решение:**
1. Установите `NEXT_PUBLIC_USE_MOCK_API=false`
2. Перезапустите frontend сервис

## Готово!

После настройки переменных frontend должен подключиться к backend на Railway.


