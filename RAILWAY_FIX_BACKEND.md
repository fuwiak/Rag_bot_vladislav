# Исправление Backend на Railway

## Что было исправлено:

1. **Восстановлена проверка пароля** - теперь `/api/auth/login` проверяет пароль правильно
2. **Упрощена логика БД** - не переключается на in-memory если `DATABASE_URL` установлен
3. **Улучшено логирование** - видно когда администратор создается

---

## Что нужно сделать на Railway:

### 1. Проверьте переменные окружения Backend Service:

```
DATABASE_URL=sqlite+aiosqlite:////data/rag_bot.db
ADMIN_SECRET_KEY=your-secret-key-here-change-in-production
ADMIN_SESSION_SECRET=your-session-secret-here-change-in-production
CORS_ORIGINS=https://ragbotvladislav-production.up.railway.app
BACKEND_URL=https://ragbotvladislav-production-back.up.railway.app
```

**ВАЖНО:**
- `DATABASE_URL` должен быть **БЕЗ кавычек**
- Путь `/data/rag_bot.db` - это где mounted volume
- `ADMIN_SECRET_KEY` должен быть установлен (любая строка, минимум 32 символа)

---

### 2. Проверьте Volume:

- Railway Dashboard → Backend Service → Settings → Volumes
- Volume должен быть **mounted** на путь `/data`
- Размер: минимум 1 GB

---

### 3. Перезапустите Backend:

1. Railway Dashboard → Backend Service → Settings → Deployments
2. Нажмите **"Redeploy"** или дождитесь автоматического перезапуска после изменений в GitHub
3. Дождитесь завершения deployment

---

### 4. Проверьте логи:

Railway Dashboard → Backend Service → Logs

Должны увидеть:
```
WARNING: Admin user 'admin' created automatically with password 'admin'
```

Или:
```
INFO: Admin user exists: admin
```

---

### 5. Проверьте вход:

1. Откройте: `https://ragbotvladislav-production.up.railway.app/login`
2. Username: `admin`
3. Password: `admin`
4. Должен работать вход!

---

## Если не работает:

### Проверка 1: DATABASE_URL

В логах не должно быть:
```
WARNING: DATABASE_URL not set, using in-memory SQLite
```

Если видите это - проверьте переменную `DATABASE_URL` в Railway.

---

### Проверка 2: Администратор не создается

Попробуйте вызвать endpoint:
```bash
curl -X POST https://ragbotvladislav-production-back.up.railway.app/api/auth/create-admin
```

Должен вернуть:
```json
{
  "message": "Администратор создан успешно",
  "username": "admin",
  "password": "admin"
}
```

---

### Проверка 3: Проверка пароля

Если администратор создан, но вход не работает:

1. Проверьте `ADMIN_SECRET_KEY` - должен быть установлен
2. Проверьте логи - должны быть ошибки если что-то не так
3. Попробуйте создать администратора через endpoint еще раз

---

## Локальная проверка:

Для проверки локально:

```bash
cd backend
python -m uvicorn app.main:app --reload --port 8000
```

Затем в другом терминале:
```bash
# Создать администратора
curl -X POST http://localhost:8000/api/auth/create-admin

# Проверить вход
curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "admin"}'
```

Должен вернуть токен!

---

**После исправлений - перезапустите Backend на Railway и попробуйте войти!**




