# Установка NEXT_PUBLIC_BACKEND_URL в Railway

## Проблема

API route `/api/config` возвращает:
```json
{"backendUrl":"http://localhost:8000","useMockApi":false}
```

Это означает, что переменная `NEXT_PUBLIC_BACKEND_URL` **не установлена** в Railway для Frontend сервиса.

---

## Решение: Установите переменную в Railway

### Шаг 1: Откройте Railway Dashboard

1. Перейдите на [Railway Dashboard](https://railway.app)
2. Выберите ваш проект
3. Откройте **Frontend сервис** (тот, который деплоит `admin-panel`)

### Шаг 2: Добавьте переменную окружения

1. В сервисе Frontend перейдите в **Settings** → **Variables**
2. Нажмите **"+ New Variable"** или найдите существующую `NEXT_PUBLIC_BACKEND_URL`
3. Установите:

   **Key:**
   ```
   NEXT_PUBLIC_BACKEND_URL
   ```

   **Value:**
   ```
   https://ragbotvladislav-backend.up.railway.app
   ```

   **ВАЖНО:**
   - ✅ БЕЗ кавычек (`"` или `'`)
   - ✅ БЕЗ слеша в конце (`/`)
   - ✅ Полный URL с `https://`
   - ✅ БЕЗ пробелов вокруг `=`

### Шаг 3: Сохраните и пересоберите

1. Нажмите **"Add"** или **"Update"**
2. Railway автоматически начнет пересборку
3. Дождитесь завершения деплоя (обычно 2-5 минут)

### Шаг 4: Проверьте результат

После пересборки откройте в браузере:
```
https://ragbotvladislav-test.up.railway.app/api/config
```

**Должно быть:**
```json
{"backendUrl":"https://ragbotvladislav-backend.up.railway.app","useMockApi":false}
```

**НЕ должно быть:**
```json
{"backendUrl":"http://localhost:8000","useMockApi":false}
```

---

## Полный список переменных для Frontend сервиса

Убедитесь, что у вас установлены:

```bash
NEXT_PUBLIC_BACKEND_URL=https://ragbotvladislav-backend.up.railway.app
NEXT_PUBLIC_USE_MOCK_API=false
PORT=3000
NODE_ENV=production
```

**Удалите** (если есть):
- ❌ `PYTHONPATH` - это для Backend, не для Frontend
- ❌ `BACKEND_URL` - используйте только `NEXT_PUBLIC_BACKEND_URL`

---

## Если не помогло

1. **Проверьте URL Backend сервиса:**
   - Railway Dashboard → Backend сервис → Settings → Networking
   - Скопируйте **Public Domain** (например: `ragbotvladislav-backend.up.railway.app`)
   - Используйте его в `NEXT_PUBLIC_BACKEND_URL`

2. **Принудительно пересоберите:**
   - Frontend сервис → Settings → Deploy
   - Нажмите **"Redeploy"**

3. **Проверьте логи сборки:**
   - Frontend сервис → Deployments → выберите последний деплой → View Logs
   - Убедитесь, что нет ошибок

---

## Как это работает

API route `/api/config` читает переменные окружения **на сервере** (в Railway):
- `process.env.NEXT_PUBLIC_BACKEND_URL` - основная переменная
- `process.env.BACKEND_URL` - fallback
- Если обе отсутствуют → возвращает `http://localhost:8000`

После установки переменной в Railway, она будет доступна на сервере, и API route вернет правильный URL.


