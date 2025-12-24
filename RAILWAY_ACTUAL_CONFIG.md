# Конфигурация для вашего Railway проекта

## Ваши URL

- **Frontend:** `https://ragbotvladislav-production.up.railway.app`
- **Backend:** `ragbotvladislav-production-back.up.railway.app` (должен быть с `https://`)

## Настройка переменных окружения

### Backend Service Variables

В Railway Dashboard → Backend Service → Settings → Variables добавьте/обновите:

```bash
DATABASE_URL=sqlite+aiosqlite:////data/rag_bot.db
ADMIN_SECRET_KEY=сгенерируйте_случайную_строку_здесь
ADMIN_SESSION_SECRET=сгенерируйте_другую_случайную_строку_здесь
BACKEND_URL=https://ragbotvladislav-production-back.up.railway.app
CORS_ORIGINS=https://ragbotvladislav-production.up.railway.app
QDRANT_URL=your_qdrant_url
QDRANT_API_KEY=your_qdrant_key
OPENROUTER_API_KEY=your_openrouter_key
```

**Важно:**
- Замените `сгенерируйте_случайную_строку_здесь` на реальные случайные строки
- Используйте `https://` в URL backend (если Railway не добавил автоматически)
- `CORS_ORIGINS` должен точно совпадать с URL frontend

### Frontend Service Variables

В Railway Dashboard → Frontend Service → Settings → Variables добавьте/обновите:

```bash
NEXT_PUBLIC_BACKEND_URL=https://ragbotvladislav-production-back.up.railway.app
PORT=3000
NODE_ENV=production
```

**Важно:**
- URL должен быть с `https://`
- Проверьте, что URL backend правильный (может быть другой поддомен)

---

## Генерация секретных ключей

Для `ADMIN_SECRET_KEY` и `ADMIN_SESSION_SECRET` сгенерируйте случайные строки:

```bash
# В терминале
openssl rand -hex 32

# Или через Python
python -c "import secrets; print(secrets.token_hex(32))"
```

Используйте разные строки для каждого ключа!

---

## Проверка конфигурации

### 1. Проверьте Backend

Откройте в браузере:
```
https://ragbotvladislav-production-back.up.railway.app/health
```

Должен вернуться: `{"status":"healthy"}`

### 2. Проверьте Frontend

Откройте:
```
https://ragbotvladislav-production.up.railway.app/login
```

Должна открыться страница входа.

### 3. Проверьте подключение

1. Откройте консоль браузера (F12)
2. Попробуйте войти с `admin/admin`
3. Проверьте Network tab:
   - Запрос должен идти на `https://ragbotvladislav-production-back.up.railway.app/api/auth/login`
   - Должен вернуться статус 200
   - Должен вернуться токен

---

## Создание администратора

После настройки переменных создайте администратора:

```bash
railway run --service backend python create_admin_auto.py
```

Или через Railway Dashboard:
1. Backend Service → Settings → Deployments
2. Run Command: `python create_admin_auto.py`

По умолчанию создается:
- Username: `admin`
- Password: `admin`

---

## Troubleshooting

### Ошибка CORS

Если видите ошибку CORS в браузере:

1. Проверьте `CORS_ORIGINS` в Backend:
   ```
   CORS_ORIGINS=https://ragbotvladislav-production.up.railway.app
   ```
2. Убедитесь, что URL точно совпадает (включая `https://`)
3. Перезапустите Backend после изменения

### Ошибка подключения

Если frontend не может подключиться к backend:

1. Проверьте `NEXT_PUBLIC_BACKEND_URL` в Frontend:
   ```
   NEXT_PUBLIC_BACKEND_URL=https://ragbotvladislav-production-back.up.railway.app
   ```
2. Проверьте, что backend доступен: `https://ragbotvladislav-production-back.up.railway.app/health`
3. Убедитесь, что URL правильный (может быть другой поддомен от Railway)

### Неправильный URL backend

Railway может использовать другой поддомен. Проверьте:

1. Railway Dashboard → Backend Service
2. Settings → Networking
3. Скопируйте точный URL (может быть `ragbotvladislav-production-backend-xxxx.up.railway.app`)

---

## Быстрая проверка

1. ✅ Backend `/health` работает?
2. ✅ Frontend открывается?
3. ✅ `NEXT_PUBLIC_BACKEND_URL` правильный?
4. ✅ `CORS_ORIGINS` содержит URL frontend?
5. ✅ `ADMIN_SECRET_KEY` установлен?
6. ✅ Администратор создан?

Если все ✅, вход должен работать!




