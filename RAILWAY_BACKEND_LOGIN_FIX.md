# Исправление проблемы входа в админ-панель на Railway

## Проблема

Не удается войти с `admin/admin` на Railway, хотя локально работает.

## Причины

1. **404 на `/`** - это нормально! API endpoints находятся в `/api/*`
2. **Backend работает на порту 8080** - Railway автоматически устанавливает PORT
3. **Авторизация может не работать** из-за отключенной проверки пароля

## Решения

### 1. Проверьте правильный endpoint

Frontend должен обращаться к:
- `https://your-backend.railway.app/api/login` (не `/login`)

Проверьте в коде frontend, что используется правильный URL:
```typescript
// Правильно
const response = await fetch(`${backendUrl}/api/login`, ...)

// Неправильно
const response = await fetch(`${backendUrl}/login`, ...)
```

### 2. Проверьте переменные окружения Backend

В Railway Dashboard → Backend Service → Settings → Variables:

```bash
DATABASE_URL=sqlite+aiosqlite:////data/rag_bot.db
ADMIN_SECRET_KEY=your_secret_key
ADMIN_SESSION_SECRET=your_session_secret
BACKEND_URL=https://your-backend.railway.app
CORS_ORIGINS=https://your-frontend.railway.app
```

**Важно:**
- `ADMIN_SECRET_KEY` должен быть установлен (используется для JWT токенов)
- `CORS_ORIGINS` должен содержать URL frontend

### 3. Проверьте переменные окружения Frontend

В Railway Dashboard → Frontend Service → Settings → Variables:

```bash
NEXT_PUBLIC_BACKEND_URL=https://your-backend.railway.app
```

**Важно:** URL должен быть правильным и доступным.

### 4. Создайте администратора

Даже если пароль отключен, лучше создать администратора в базе данных:

```bash
railway run --service backend python create_admin_auto.py
```

Это создаст администратора с username `admin` и password `admin`.

### 5. Проверьте CORS

Если видите ошибки CORS в браузере:

1. Проверьте `CORS_ORIGINS` в Backend
2. Убедитесь, что URL frontend точно совпадает
3. Перезапустите Backend после изменения переменных

---

## Диагностика

### Проверка Backend

1. **Health check:**
   ```
   https://your-backend.railway.app/health
   ```
   Должен вернуться: `{"status":"healthy"}`

2. **API endpoint:**
   ```
   https://your-backend.railway.app/api/login
   ```
   Должен быть доступен (POST запрос)

3. **Проверка в браузере:**
   Откройте консоль (F12) и проверьте:
   - Нет ошибок CORS
   - Запросы идут на правильный URL
   - Ответы приходят от backend

### Проверка Frontend

1. **Откройте консоль браузера (F12)**
2. **Попробуйте войти**
3. **Проверьте Network tab:**
   - Запрос должен идти на `/api/login`
   - Должен быть POST запрос
   - Должен вернуться токен

---

## Быстрое исправление

### Вариант 1: Проверьте URL в frontend

Убедитесь, что frontend использует правильный URL backend:

1. Откройте Railway Dashboard → Frontend Service → Variables
2. Проверьте `NEXT_PUBLIC_BACKEND_URL`
3. Убедитесь, что URL правильный (с `https://`, без слеша в конце)

### Вариант 2: Создайте администратора

```bash
railway run --service backend python create_admin_auto.py
```

### Вариант 3: Проверьте CORS

1. Railway Dashboard → Backend Service → Variables
2. Проверьте `CORS_ORIGINS`
3. Убедитесь, что содержит URL frontend
4. Перезапустите Backend

---

## Проверка работы

1. **Откройте frontend URL**
2. **Попробуйте войти с `admin/admin`**
3. **Проверьте консоль браузера (F12):**
   - Нет ошибок
   - Запрос на `/api/login` успешен
   - Получен токен

---

## Если все еще не работает

1. **Проверьте логи Backend:**
   - Railway Dashboard → Backend Service → Logs
   - Ищите ошибки при запросе `/api/login`

2. **Проверьте логи Frontend:**
   - Railway Dashboard → Frontend Service → Logs
   - Ищите ошибки при сборке или запуске

3. **Проверьте Network в браузере:**
   - Откройте DevTools (F12) → Network
   - Попробуйте войти
   - Посмотрите на запрос к `/api/login`
   - Проверьте статус ответа и содержимое

---

**Важно:** Убедитесь, что frontend обращается к `/api/login`, а не просто `/login`!

