# Диагностика проблемы входа на Railway

## Volume подключен, но вход не работает

Если volume подключен, но вход все еще не работает, проверьте следующее:

---

## Шаг 1: Проверьте переменные окружения Backend

Railway Dashboard → **Backend Service** → **Settings** → **Variables**

Должны быть установлены **ВСЕ** эти переменные:

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

**Проверьте:**
- ✅ `DATABASE_URL` установлен (4 слеша `////`)
- ✅ `ADMIN_SECRET_KEY` установлен (не пустой)
- ✅ `ADMIN_SESSION_SECRET` установлен (не пустой)
- ✅ `CORS_ORIGINS` содержит URL frontend

---

## Шаг 2: Проверьте переменные Frontend

Railway Dashboard → **Frontend Service** → **Settings** → **Variables**

Должны быть **ТОЛЬКО**:

```bash
NEXT_PUBLIC_BACKEND_URL=https://ragbotvladislav-production-back.up.railway.app
NODE_ENV=production
```

**Убедитесь, что:**
- ❌ НЕТ лишних переменных (ADMIN_SECRET_KEY, DATABASE_URL и т.д.)
- ✅ `NEXT_PUBLIC_BACKEND_URL` правильный (без слеша в конце)

---

## Шаг 3: Перезапустите оба сервиса

1. Railway Dashboard → **Backend Service** → **Redeploy**
2. Railway Dashboard → **Frontend Service** → **Redeploy**
3. Дождитесь завершения перезапуска

---

## Шаг 4: Создайте администратора

**ОБЯЗАТЕЛЬНО!** Создайте администратора после перезапуска:

```bash
railway run --service backend python create_admin_auto.py
```

Или через Railway Dashboard:
- Backend Service → Settings → Deployments → Run Command
- Команда: `python create_admin_auto.py`

**Проверьте вывод:**
- Должно быть: `✅ Администратор создан успешно!`
- Если видите: `ℹ️ Администратор с username 'admin' уже существует!` - это нормально

---

## Шаг 5: Проверьте логи Backend

Railway Dashboard → **Backend Service** → **Logs**

**Не должно быть:**
- ❌ `Using default DATABASE_URL (localhost)`
- ❌ Ошибок подключения к базе данных
- ❌ Ошибок CORS

**Должно быть:**
- ✅ `Application startup complete`
- ✅ `Uvicorn running on http://0.0.0.0:8080`

---

## Шаг 6: Проверьте в браузере

1. Откройте: `https://ragbotvladislav-production.up.railway.app/login`
2. Откройте консоль браузера (F12) → **Network** tab
3. Попробуйте войти с `admin/admin`
4. Проверьте запрос к `/api/auth/login`:
   - **URL:** должен быть `https://ragbotvladislav-production-back.up.railway.app/api/auth/login`
   - **Method:** POST
   - **Status:** должен быть **200** (не 304, не 404, не 500)
   - **Response:** должен вернуться токен `{"access_token":"...","token_type":"bearer"}`

---

## Диагностика по статусам

### Если статус 404

**Проблема:** Неправильный URL backend

**Решение:**
1. Проверьте точный URL backend:
   - Railway Dashboard → Backend Service → Settings → Networking
   - Скопируйте точный URL
2. Обновите `NEXT_PUBLIC_BACKEND_URL` в Frontend
3. Перезапустите Frontend

### Если статус 500

**Проблема:** Ошибка на backend

**Решение:**
1. Проверьте логи Backend
2. Ищите ошибки при обработке запроса `/api/auth/login`
3. Проверьте, что `ADMIN_SECRET_KEY` установлен

### Если статус CORS error

**Проблема:** Неправильный CORS

**Решение:**
1. Проверьте `CORS_ORIGINS` в Backend
2. Убедитесь, что содержит точный URL frontend
3. Перезапустите Backend

### Если статус 200, но токен не сохраняется

**Проблема:** Проблема с frontend

**Решение:**
1. Проверьте консоль браузера (F12) → Console
2. Ищите ошибки JavaScript
3. Проверьте, что токен сохраняется в localStorage

---

## Быстрая проверка всех настроек

### Backend Checklist:
- [ ] Volume подключен на `/data`
- [ ] `DATABASE_URL=sqlite+aiosqlite:////data/rag_bot.db` установлен
- [ ] `ADMIN_SECRET_KEY` установлен (не пустой)
- [ ] `ADMIN_SESSION_SECRET` установлен (не пустой)
- [ ] `CORS_ORIGINS` содержит URL frontend
- [ ] Администратор создан (`python create_admin_auto.py`)
- [ ] Backend перезапущен после изменений

### Frontend Checklist:
- [ ] `NEXT_PUBLIC_BACKEND_URL` установлен (правильный URL backend)
- [ ] НЕТ лишних переменных
- [ ] Frontend перезапущен

### Проверка работы:
- [ ] Backend `/health` работает
- [ ] Frontend открывается
- [ ] Запрос к `/api/auth/login` возвращает 200
- [ ] Токен сохраняется в localStorage

---

## Если все еще не работает

1. **Проверьте точные URL:**
   - Railway Dashboard → Backend Service → Settings → Networking
   - Скопируйте точный URL backend
   - Обновите `NEXT_PUBLIC_BACKEND_URL` и `CORS_ORIGINS`

2. **Проверьте логи подробно:**
   - Backend logs: ищите ошибки при запросе `/api/auth/login`
   - Frontend logs: ищите ошибки при сборке или запуске

3. **Попробуйте в режиме инкогнито:**
   - Это обойдет кэш браузера
   - Chrome: Ctrl+Shift+N / Cmd+Shift+N

4. **Проверьте Network в браузере:**
   - F12 → Network → попробуйте войти
   - Посмотрите на запрос к `/api/auth/login`
   - Проверьте Request URL, Status, Response

---

**Главное: убедитесь, что администратор создан и все переменные окружения установлены правильно!**





