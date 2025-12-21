# Исправление UUID в SQLite

## Что было исправлено:

1. **Создан универсальный тип GUID** - работает с SQLite (String) и PostgreSQL (UUID)
2. **Все модели обновлены** - используют GUID вместо UUID
3. **Исправлена ошибка** `no such table: admin_users` и `can't render element of type UUID`

---

## Что нужно сделать на Railway:

### 1. Убедитесь что переменные установлены:

```
DATABASE_URL=sqlite+aiosqlite:////data/rag_bot.db
DISABLE_PASSWORD_CHECK=true
ADMIN_SECRET_KEY=your-secret-key-here
```

### 2. Перезапустите Backend:

Railway Dashboard → Backend Service → Redeploy

### 3. Проверьте логи:

Должны увидеть:
```
INFO: Database initialized successfully: sqlite+aiosqlite:////data/rag_bot.db
WARNING: Admin user 'admin' created automatically with password 'admin'
```

**НЕ должно быть:**
- `can't render element of type UUID`
- `no such table: admin_users`

---

## Теперь должно работать:

1. Таблицы создаются правильно в SQLite
2. Администратор создается автоматически
3. Вход работает без проверки пароля (если `DISABLE_PASSWORD_CHECK=true`)

---

**Попробуйте войти: `admin` / любой пароль (если DISABLE_PASSWORD_CHECK=true)**

