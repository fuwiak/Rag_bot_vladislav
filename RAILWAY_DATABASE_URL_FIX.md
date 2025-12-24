# Исправление проблемы DATABASE_URL на Railway

## Проблема

В логах backend видно:
```
Using default DATABASE_URL (localhost) - this may not work in Railway!
```

Это означает, что переменная `DATABASE_URL` **не установлена** или **не читается** правильно.

---

## Решение

### Шаг 1: Проверьте переменные в Railway

1. Railway Dashboard → **Backend Service** → **Settings** → **Variables**
2. **Убедитесь**, что переменная `DATABASE_URL` есть в списке
3. **Проверьте значение:**
   ```
   sqlite+aiosqlite:////data/rag_bot.db
   ```
   **Важно:** 4 слеша `////` перед `/data`

### Шаг 2: Проверьте формат

Правильный формат:
```bash
DATABASE_URL=sqlite+aiosqlite:////data/rag_bot.db
```

**Неправильно:**
- ❌ `sqlite+aiosqlite:///data/rag_bot.db` (3 слеша)
- ❌ `sqlite+aiosqlite:////data/rag_bot.db/` (слеш в конце)
- ❌ `DATABASE_URL="sqlite+aiosqlite:////data/rag_bot.db"` (кавычки не нужны в Railway)

**Правильно:**
- ✅ `sqlite+aiosqlite:////data/rag_bot.db` (4 слеша, без кавычек)

### Шаг 3: Перезапустите Backend

После установки/изменения переменной:

1. Railway Dashboard → **Backend Service** → **Settings** → **Deployments**
2. Нажмите **"Redeploy"** или дождитесь автоматического перезапуска
3. Проверьте логи - не должно быть предупреждения о DATABASE_URL

### Шаг 4: Проверьте Volume

Убедитесь, что volume подключен:

1. Railway Dashboard → **Backend Service** → **Settings** → **Volumes**
2. Должен быть подключен volume:
   - **Volume:** `sqlite-data` (или другое название)
   - **Mount Path:** `/data`

Если volume не подключен:
1. Создайте volume: **New** → **Volume** → название `sqlite-data`
2. Подключите к Backend: **Add Volume** → выберите volume → Mount Path: `/data`

---

## Полный список переменных Backend

Убедитесь, что все переменные установлены:

```bash
DATABASE_URL=sqlite+aiosqlite:////data/rag_bot.db
ADMIN_SECRET_KEY=сгенерируйте_случайную_строку
ADMIN_SESSION_SECRET=сгенерируйте_другую_строку
BACKEND_URL=https://ragbotvladislav-production-back.up.railway.app
CORS_ORIGINS=https://ragbotvladislav-production.up.railway.app
QDRANT_URL=your_qdrant_url
QDRANT_API_KEY=your_qdrant_key
OPENROUTER_API_KEY=your_openrouter_key
```

---

## Создание администратора

После того, как `DATABASE_URL` правильно установлен и backend перезапущен:

```bash
railway run --service backend python create_admin_auto.py
```

Или через Railway Dashboard:
- Backend Service → Settings → Deployments → Run Command
- Команда: `python create_admin_auto.py`

---

## Проверка

### 1. Проверьте логи Backend

После перезапуска в логах НЕ должно быть:
- ❌ `Using default DATABASE_URL (localhost)`
- ❌ Предупреждений о базе данных

Должно быть:
- ✅ `Application startup complete`
- ✅ `Uvicorn running on http://0.0.0.0:8080`

### 2. Проверьте health endpoint

```
https://ragbotvladislav-production-back.up.railway.app/health
```

Должен вернуться: `{"status":"healthy"}`

### 3. Попробуйте войти

1. Откройте: `https://ragbotvladislav-production.up.railway.app/login`
2. Username: `admin`
3. Password: `admin`
4. Откройте консоль браузера (F12) → Network
5. Проверьте запрос к `/api/auth/login`:
   - Должен быть статус **200**
   - Должен вернуться токен

---

## Если все еще видите предупреждение

### Вариант 1: Пересоздайте переменную

1. Railway Dashboard → Backend Service → Settings → Variables
2. **Удалите** переменную `DATABASE_URL` (если есть)
3. **Добавьте** заново:
   - Key: `DATABASE_URL`
   - Value: `sqlite+aiosqlite:////data/rag_bot.db`
4. **Сохраните**
5. Дождитесь перезапуска

### Вариант 2: Проверьте через Railway CLI

```bash
railway variables --service backend
```

Проверьте, что `DATABASE_URL` есть в списке.

### Вариант 3: Проверьте формат

Убедитесь, что:
- Нет кавычек вокруг значения
- Правильное количество слешей (4 перед `/data`)
- Нет пробелов в начале/конце

---

## Troubleshooting

### Backend все еще использует localhost

1. **Проверьте переменные:**
   - Убедитесь, что `DATABASE_URL` установлен
   - Проверьте формат (4 слеша)

2. **Перезапустите backend:**
   - Railway Dashboard → Backend Service → Redeploy

3. **Проверьте логи:**
   - После перезапуска не должно быть предупреждения

### Вход все еще не работает

1. **Создайте администратора:**
   ```bash
   railway run --service backend python create_admin_auto.py
   ```

2. **Проверьте CORS:**
   - Откройте консоль браузера (F12) → Console
   - Ищите ошибки CORS
   - Проверьте `CORS_ORIGINS` в Backend

3. **Проверьте URL:**
   - `NEXT_PUBLIC_BACKEND_URL` в Frontend должен быть правильным
   - `BACKEND_URL` в Backend должен быть без слеша в конце

---

**Главное: убедитесь, что `DATABASE_URL` установлен БЕЗ кавычек и с 4 слешами!**





