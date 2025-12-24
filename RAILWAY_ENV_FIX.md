# Исправление переменных окружения на Railway

## Проблема

Переменные окружения настроены неправильно:
- В Frontend есть переменные, которые нужны только Backend
- В Backend не хватает важных переменных
- В BACKEND_URL лишний слеш

---

## Правильная конфигурация

### Frontend Service Variables

**УДАЛИТЕ лишние переменные!** В Frontend должны быть ТОЛЬКО:

```bash
NEXT_PUBLIC_BACKEND_URL=https://ragbotvladislav-production-back.up.railway.app
NODE_ENV=production
```

**УДАЛИТЕ из Frontend:**
- ❌ `ADMIN_SECRET_KEY` - это для backend
- ❌ `ADMIN_SESSION_SECRET` - это для backend
- ❌ `BACKEND_URL` - не нужно в frontend
- ❌ `CORS_ORIGINS` - это для backend
- ❌ `DATABASE_URL` - это для backend
- ❌ `OPENROUTER_API_KEY` - это для backend
- ❌ `QDRANT_API_KEY` - это для backend
- ❌ `QDRANT_URL` - это для backend

---

### Backend Service Variables

**ДОБАВЬТЕ недостающие переменные!** В Backend должны быть:

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

**ВАЖНО:**
- ❌ Уберите слеш в конце `BACKEND_URL` (было `...railway.app/`, должно быть `...railway.app`)
- ✅ `ADMIN_SECRET_KEY` и `ADMIN_SESSION_SECRET` должны быть **разными случайными строками**
- ✅ Используйте **4 слеша** в `DATABASE_URL`: `sqlite+aiosqlite:////data/rag_bot.db`

---

## Генерация секретных ключей

Для `ADMIN_SECRET_KEY` и `ADMIN_SESSION_SECRET`:

```bash
openssl rand -hex 32
```

Выполните **дважды** и используйте разные строки для каждого ключа.

---

## Пошаговая настройка

### Шаг 1: Очистите Frontend Variables

1. Railway Dashboard → **Frontend Service** → **Settings** → **Variables**
2. **Удалите** все переменные кроме:
   - `NEXT_PUBLIC_BACKEND_URL`
   - `NODE_ENV`
3. Сохраните

### Шаг 2: Настройте Backend Variables

1. Railway Dashboard → **Backend Service** → **Settings** → **Variables**
2. **Удалите** переменную `BACKEND_URL` (если есть со слешем)
3. **Добавьте/обновите** все переменные из списка выше
4. **Убедитесь**, что `BACKEND_URL` **БЕЗ слеша** в конце
5. Сохраните

### Шаг 3: Перезапустите сервисы

1. Railway автоматически перезапустит сервисы после изменения переменных
2. Дождитесь завершения перезапуска

### Шаг 4: Создайте администратора

```bash
railway run --service backend python create_admin_auto.py
```

Или через Railway Dashboard:
- Backend Service → Settings → Deployments → Run Command
- Команда: `python create_admin_auto.py`

---

## Проверка

### 1. Проверьте Backend

```
https://ragbotvladislav-production-back.up.railway.app/health
```

Должен вернуться: `{"status":"healthy"}`

### 2. Проверьте Frontend

```
https://ragbotvladislav-production.up.railway.app/login
```

Должна открыться страница входа.

### 3. Проверьте логи Backend

Railway Dashboard → Backend Service → Logs

Не должно быть:
- ❌ Предупреждения о DATABASE_URL
- ❌ Ошибок CORS
- ❌ Ошибок при старте

### 4. Попробуйте войти

1. Откройте frontend
2. Username: `admin`
3. Password: `admin`
4. Откройте консоль браузера (F12) → Network
5. Проверьте запрос к `/api/auth/login`:
   - Должен быть статус **200**
   - Должен вернуться токен

---

## Troubleshooting

### Все еще не работает

1. **Проверьте точный URL backend:**
   - Railway Dashboard → Backend Service → Settings → Networking
   - Скопируйте точный URL
   - Обновите `NEXT_PUBLIC_BACKEND_URL` в Frontend
   - Обновите `BACKEND_URL` и `CORS_ORIGINS` в Backend

2. **Проверьте CORS:**
   - Откройте консоль браузера (F12) → Console
   - Ищите ошибки CORS
   - Убедитесь, что `CORS_ORIGINS` содержит точный URL frontend

3. **Проверьте администратора:**
   - Убедитесь, что администратор создан
   - Попробуйте создать еще раз: `python create_admin_auto.py`

4. **Проверьте переменные:**
   - Убедитесь, что все переменные сохранены
   - Проверьте, что нет опечаток в URL
   - Убедитесь, что `BACKEND_URL` без слеша в конце

---

## Итоговая конфигурация

### Frontend (только 2 переменные):
```bash
NEXT_PUBLIC_BACKEND_URL=https://ragbotvladislav-production-back.up.railway.app
NODE_ENV=production
```

### Backend (все переменные):
```bash
DATABASE_URL=sqlite+aiosqlite:////data/rag_bot.db
ADMIN_SECRET_KEY=случайная_строка_1
ADMIN_SESSION_SECRET=случайная_строка_2
BACKEND_URL=https://ragbotvladislav-production-back.up.railway.app
CORS_ORIGINS=https://ragbotvladislav-production.up.railway.app
QDRANT_URL=your_url
QDRANT_API_KEY=your_key
OPENROUTER_API_KEY=your_key
```

---

**После исправления переменных и создания администратора вход должен работать!**





