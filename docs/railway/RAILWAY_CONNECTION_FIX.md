# Исправление ошибки "Ошибка подключения к серверу"

## Проблема:

Frontend не может подключиться к Backend.

---

## Решение:

### 1. Проверьте переменную NEXT_PUBLIC_BACKEND_URL в Frontend:

Railway Dashboard → **Frontend Service** → **Variables**

Должна быть установлена:
```
NEXT_PUBLIC_BACKEND_URL=https://ragbotvladislav-production-back.up.railway.app
```

**ВАЖНО:**
- БЕЗ слеша в конце (`/`)
- БЕЗ кавычек
- Полный URL с `https://`

---

### 2. Проверьте что Backend доступен:

Откройте в браузере:
```
https://ragbotvladislav-production-back.up.railway.app/health
```

Должно вернуть: `{"status":"healthy"}`

Если не работает:
- Railway Dashboard → Backend Service → Logs
- Проверьте что backend запущен
- Проверьте что нет ошибок

---

### 3. Проверьте CORS в Backend:

Railway Dashboard → **Backend Service** → **Variables**

Должна быть установлена:
```
CORS_ORIGINS=https://ragbotvladislav-production.up.railway.app
```

**ВАЖНО:**
- БЕЗ слеша в конце
- БЕЗ кавычек
- URL Frontend сервиса

---

### 4. Перезапустите оба сервиса:

1. Railway Dashboard → Frontend Service → Redeploy
2. Railway Dashboard → Backend Service → Redeploy
3. Дождитесь завершения deployment

---

### 5. Проверьте консоль браузера:

Откройте страницу логина и консоль (`F12` → `Console`)

Должны увидеть:
```
🔐 Environment check:
  - NEXT_PUBLIC_BACKEND_URL: https://ragbotvladislav-production-back.up.railway.app
  - Computed backendUrl: https://ragbotvladislav-production-back.up.railway.app
  - Full login URL: https://ragbotvladislav-production-back.up.railway.app/api/auth/login
🏥 Health check status: 200
```

Если видите ошибки:
- `NEXT_PUBLIC_BACKEND_URL: undefined` → переменная не установлена
- `Failed to fetch` → проблема с CORS или backend недоступен
- `404` → неправильный URL

---

## Быстрая проверка:

### Проверка 1: Backend доступен?

```bash
curl https://ragbotvladislav-production-back.up.railway.app/health
```

Должен вернуть: `{"status":"healthy"}`

### Проверка 2: Логин работает?

```bash
curl -X POST https://ragbotvladislav-production-back.up.railway.app/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "any"}'
```

Должен вернуть токен.

### Проверка 3: CORS настроен?

В консоли браузера при ошибке должно быть:
```
Access to fetch at '...' from origin '...' has been blocked by CORS policy
```

Если видите это → проверьте `CORS_ORIGINS` в Backend.

---

## Если все еще не работает:

1. **Проверьте логи Backend:**
   - Railway Dashboard → Backend Service → Logs
   - Ищите ошибки при старте

2. **Проверьте логи Frontend:**
   - Railway Dashboard → Frontend Service → Logs
   - Ищите ошибки при сборке

3. **Проверьте переменные окружения:**
   - Убедитесь что все переменные установлены правильно
   - БЕЗ кавычек, БЕЗ лишних пробелов

---

**После исправления переменных - перезапустите оба сервиса!**











