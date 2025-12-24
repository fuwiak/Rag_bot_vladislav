# Исправление проблемы входа - пошаговая инструкция

## Проблема

Видно в логах:
```
Using default DATABASE_URL (localhost) - this may not work in Railway!
```

Это означает, что переменная `DATABASE_URL` не установлена в Railway.

---

## Шаг 1: Установите DATABASE_URL в Backend

1. Railway Dashboard → **Backend Service** → **Settings** → **Variables**
2. Добавьте/обновите переменную:

```bash
DATABASE_URL=sqlite+aiosqlite:////data/rag_bot.db
```

**Важно:** 
- Используйте **4 слеша** `////` перед `/data`
- Убедитесь, что volume подключен на путь `/data`

---

## Шаг 2: Проверьте подключение Volume

1. Railway Dashboard → **Backend Service** → **Settings** → **Volumes**
2. Должен быть подключен volume:
   - **Volume:** `sqlite-data` (или другое название)
   - **Mount Path:** `/data`

Если volume не подключен:
1. Создайте volume: **New** → **Volume** → название `sqlite-data`
2. Подключите к Backend Service: **Add Volume** → выберите volume → Mount Path: `/data`

---

## Шаг 3: Установите остальные переменные Backend

В Railway Dashboard → **Backend Service** → **Settings** → **Variables** добавьте:

```bash
DATABASE_URL=sqlite+aiosqlite:////data/rag_bot.db
ADMIN_SECRET_KEY=сгенерируйте_случайную_строку
ADMIN_SESSION_SECRET=сгенерируйте_другую_случайную_строку
BACKEND_URL=https://ragbotvladislav-production-back.up.railway.app
CORS_ORIGINS=https://ragbotvladislav-production.up.railway.app
QDRANT_URL=your_qdrant_url
QDRANT_API_KEY=your_key
OPENROUTER_API_KEY=your_key
```

**Генерация секретов:**
```bash
openssl rand -hex 32
```
Выполните дважды для двух разных ключей.

---

## Шаг 4: Установите переменные Frontend

В Railway Dashboard → **Frontend Service** → **Settings** → **Variables**:

```bash
NEXT_PUBLIC_BACKEND_URL=https://ragbotvladislav-production-back.up.railway.app
PORT=3000
NODE_ENV=production
```

---

## Шаг 5: Перезапустите Backend

После установки переменных:

1. Railway Dashboard → **Backend Service** → **Settings** → **Deployments**
2. Нажмите **"Redeploy"** или дождитесь автоматического перезапуска

Проверьте логи - не должно быть предупреждения о DATABASE_URL.

---

## Шаг 6: Создайте администратора

После перезапуска backend создайте администратора:

### Способ 1: Через Railway CLI

```bash
railway login
railway link
railway run --service backend python create_admin_auto.py
```

### Способ 2: Через Railway Dashboard

1. Railway Dashboard → **Backend Service** → **Settings** → **Deployments**
2. Нажмите **"Run Command"** или создайте новый deployment
3. Введите команду:
   ```
   python create_admin_auto.py
   ```

По умолчанию создается:
- **Username:** `admin`
- **Password:** `admin`

---

## Шаг 7: Проверка

1. **Проверьте backend:**
   ```
   https://ragbotvladislav-production-back.up.railway.app/health
   ```
   Должен вернуться: `{"status":"healthy"}`

2. **Проверьте логи backend:**
   - Не должно быть предупреждения о DATABASE_URL
   - Должно быть: `Application startup complete`

3. **Попробуйте войти:**
   - Откройте: `https://ragbotvladislav-production.up.railway.app/login`
   - Username: `admin`
   - Password: `admin`

4. **Проверьте консоль браузера (F12):**
   - Network tab → запрос к `/api/auth/login`
   - Должен быть статус 200
   - Должен вернуться токен

---

## Troubleshooting

### Все еще видите предупреждение о DATABASE_URL

1. Проверьте, что переменная установлена:
   - Railway Dashboard → Backend Service → Variables
   - Убедитесь, что `DATABASE_URL` есть в списке

2. Проверьте формат:
   ```
   sqlite+aiosqlite:////data/rag_bot.db
   ```
   (4 слеша перед `/data`)

3. Перезапустите backend после изменения переменных

### Ошибка при создании администратора

Если видите ошибку о базе данных:

1. Проверьте, что volume подключен
2. Проверьте, что `DATABASE_URL` правильный
3. Проверьте логи backend на наличие ошибок

### Все еще не могу войти

1. **Проверьте CORS:**
   - `CORS_ORIGINS` должен содержать точный URL frontend
   - Перезапустите backend после изменения

2. **Проверьте URL в frontend:**
   - `NEXT_PUBLIC_BACKEND_URL` должен быть правильным
   - URL должен быть с `https://`

3. **Проверьте консоль браузера:**
   - Откройте F12 → Console
   - Ищите ошибки CORS или подключения
   - Network tab → проверьте запрос к `/api/auth/login`

---

## Важно

- **404 на `/`** - это нормально! Backend API находится в `/api/*`
- Frontend должен обращаться к `/api/auth/login`, а не просто `/login`
- Все переменные окружения должны быть установлены перед созданием администратора

---

**После выполнения всех шагов вход должен работать!**





