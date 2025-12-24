# Связь Frontend и Backend на Railway

Инструкция по настройке переменных окружения для связи Frontend и Backend сервисов на Railway.

## Шаг 1: Получение URL сервисов

После деплоя каждого сервиса Railway присваивает им URL:

1. **Backend URL:** `https://backend-production-xxxx.up.railway.app`
2. **Frontend URL:** `https://frontend-production-xxxx.up.railway.app`

Скопируйте эти URL из Railway Dashboard для каждого сервиса.

---

## Шаг 2: Настройка Backend Service

1. Откройте **Backend Service** в Railway Dashboard
2. Перейдите в **Settings** → **Variables**
3. Добавьте/обновите следующие переменные:

```bash
# URL вашего backend (после получения URL от Railway)
BACKEND_URL=https://your-backend-service.railway.app

# URL вашего frontend (после получения URL от Railway)
CORS_ORIGINS=https://your-frontend-service.railway.app
```

**Важно:** 
- Замените `your-backend-service.railway.app` на реальный URL вашего backend
- Замените `your-frontend-service.railway.app` на реальный URL вашего frontend
- Если у вас несколько frontend URL (например, для разных окружений), разделите их запятой: `https://frontend1.railway.app,https://frontend2.railway.app`

---

## Шаг 3: Настройка Frontend Service

1. Откройте **Frontend Service** в Railway Dashboard
2. Перейдите в **Settings** → **Variables**
3. Добавьте/обновите следующую переменную:

```bash
# URL вашего backend (после получения URL от Railway)
NEXT_PUBLIC_BACKEND_URL=https://your-backend-service.railway.app
```

**Важно:**
- Замените `your-backend-service.railway.app` на реальный URL вашего backend
- Переменная должна начинаться с `NEXT_PUBLIC_` чтобы быть доступной в браузере

---

## Шаг 4: Порядок настройки

### Вариант 1: Последовательная настройка (рекомендуется)

1. **Сначала** разверните Backend Service
2. **Получите** URL Backend из Railway Dashboard
3. **Добавьте** переменные в Backend:
   - `BACKEND_URL` = ваш URL backend
   - `CORS_ORIGINS` = пока оставьте пустым или временный URL
4. **Разверните** Frontend Service
5. **Получите** URL Frontend из Railway Dashboard
6. **Обновите** переменные:
   - В **Backend**: `CORS_ORIGINS` = URL frontend
   - В **Frontend**: `NEXT_PUBLIC_BACKEND_URL` = URL backend
7. **Перезапустите** оба сервиса (Railway сделает это автоматически при изменении переменных)

### Вариант 2: Одновременная настройка

Если оба сервиса уже развернуты:

1. Получите URL обоих сервисов
2. Настройте переменные одновременно:
   - **Backend**: `BACKEND_URL` и `CORS_ORIGINS`
   - **Frontend**: `NEXT_PUBLIC_BACKEND_URL`
3. Railway автоматически перезапустит сервисы

---

## Шаг 5: Проверка связи

### Проверка Backend

1. Откройте URL backend: `https://your-backend.railway.app/health`
2. Должен вернуться: `{"status":"healthy"}`

### Проверка Frontend

1. Откройте URL frontend в браузере
2. Должна открыться страница входа в админ-панель
3. Откройте консоль браузера (F12) и проверьте:
   - Нет ошибок CORS
   - Нет ошибок подключения к backend

### Проверка связи

1. Попробуйте войти в админ-панель
2. Если видите ошибку "Failed to fetch" или "Network error":
   - Проверьте `NEXT_PUBLIC_BACKEND_URL` в Frontend
   - Проверьте `CORS_ORIGINS` в Backend
   - Убедитесь, что URL правильные (без лишних слешей)

---

## Примеры правильных URL

### ✅ Правильно:

```bash
# Backend
BACKEND_URL=https://backend-production-abc123.up.railway.app
CORS_ORIGINS=https://frontend-production-xyz789.up.railway.app

# Frontend
NEXT_PUBLIC_BACKEND_URL=https://backend-production-abc123.up.railway.app
```

### ❌ Неправильно:

```bash
# Не добавляйте слеш в конце
BACKEND_URL=https://backend-production-abc123.up.railway.app/

# Не используйте localhost
NEXT_PUBLIC_BACKEND_URL=http://localhost:8000

# Не забывайте протокол
NEXT_PUBLIC_BACKEND_URL=backend-production-abc123.up.railway.app
```

---

## Troubleshooting

### Frontend не подключается к Backend

1. **Проверьте переменные:**
   - `NEXT_PUBLIC_BACKEND_URL` в Frontend должен быть URL backend
   - URL должен начинаться с `https://`

2. **Проверьте CORS:**
   - `CORS_ORIGINS` в Backend должен содержать URL frontend
   - URL должны совпадать точно (включая протокол)

3. **Проверьте логи:**
   - Backend logs: должны показывать CORS ошибки если проблема в CORS
   - Frontend logs: должны показывать ошибки подключения

### Ошибка CORS в браузере

Если видите ошибку типа:
```
Access to fetch at 'https://backend...' from origin 'https://frontend...' has been blocked by CORS policy
```

**Решение:**
1. Проверьте `CORS_ORIGINS` в Backend
2. Убедитесь, что URL frontend точно совпадает (включая `https://`)
3. Перезапустите Backend после изменения переменных

### Backend возвращает 404

Если frontend не может найти endpoints:

1. Проверьте `NEXT_PUBLIC_BACKEND_URL`
2. Убедитесь, что backend запущен (проверьте `/health`)
3. Проверьте, что URL правильный (без лишних путей)

---

## Автоматическое получение URL (Railway Private Networking)

Railway предоставляет внутренние переменные для связи между сервисами:

- `RAILWAY_PRIVATE_DOMAIN` - внутренний домен сервиса
- `PORT` - порт сервиса

Но для frontend лучше использовать публичные URL, так как frontend работает в браузере пользователя.

---

## Итоговая конфигурация

После настройки у вас должно быть:

### Backend Service Variables:
```bash
DATABASE_URL=sqlite+aiosqlite:////data/rag_bot.db
QDRANT_URL=your_qdrant_url
QDRANT_API_KEY=your_key
OPENROUTER_API_KEY=your_key
ADMIN_SECRET_KEY=your_secret
ADMIN_SESSION_SECRET=your_secret
BACKEND_URL=https://your-backend.railway.app
CORS_ORIGINS=https://your-frontend.railway.app
```

### Frontend Service Variables:
```bash
NEXT_PUBLIC_BACKEND_URL=https://your-backend.railway.app
PORT=3000
NODE_ENV=production
```

---

**Готово!** После настройки этих переменных Frontend и Backend будут связаны и работать вместе.







