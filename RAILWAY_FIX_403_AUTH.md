# Исправление ошибки 403 (Not authenticated)

## Проблема

Frontend получает ошибки 403 при попытке подключиться к backend:
```
Failed to load resource: the server responded with a status of 403 ()
Fetch error: Error: Not authenticated
```

## Причина

Backend требует JWT токен авторизации для всех API запросов, но:
1. Frontend использует фиктивный токен (`auto-login-token`)
2. Не все fetch запросы добавляют заголовок `Authorization`

## Решение

### Вариант 1: Создать настоящего администратора (РЕКОМЕНДУЕТСЯ)

1. **Подключитесь к Railway Backend сервису:**
   - Railway Dashboard → Backend сервис → Settings → Deployments
   - Найдите последний деплой → View Logs
   - Или используйте Railway CLI: `railway shell`

2. **Создайте администратора:**
   ```bash
   # В Railway Backend сервисе выполните:
   python backend/create_admin_auto.py
   ```
   
   Или вручную через Python:
   ```python
   from backend.app.database import SessionLocal
   from backend.app.models import User
   from backend.app.auth import get_password_hash
   
   db = SessionLocal()
   admin = User(
       username="admin",
       email="admin@example.com",
       hashed_password=get_password_hash("your-secure-password"),
       is_admin=True
   )
   db.add(admin)
   db.commit()
   ```

3. **Получите токен:**
   - Откройте: `https://ragbotvladislav-backend.up.railway.app/docs`
   - Используйте `/api/auth/login` endpoint:
     ```json
     {
       "username": "admin",
       "password": "your-secure-password"
     }
     ```
   - Скопируйте `access_token` из ответа

4. **Установите токен в браузере:**
   - Откройте консоль браузера (F12)
   - Выполните:
     ```javascript
     localStorage.setItem('token', 'ваш-токен-из-ответа')
     ```
   - Обновите страницу

### Вариант 2: Обновить все fetch запросы (временное решение)

Код уже обновлен для использования функции `apiFetch`, которая автоматически добавляет токен. Но нужно убедиться, что токен установлен.

**Проверьте токен в браузере:**
```javascript
// В консоли браузера (F12):
console.log('Token:', localStorage.getItem('token'))
```

Если токен отсутствует или это `auto-login-token`, установите настоящий токен (см. Вариант 1).

## Что было исправлено в коде

1. ✅ Создана функция `apiFetch` в `api-helpers.ts` - автоматически добавляет токен
2. ✅ Обновлен `dashboard/page.tsx` - использует `apiFetch`
3. ✅ Обновлен `telegram-bots/page.tsx` - использует `apiFetch`
4. ⚠️ Остальные файлы (`models/page.tsx`, `users/page.tsx`, `projects/[id]/page.tsx`) все еще используют прямой `fetch`

## Следующие шаги

1. **Создайте администратора** (Вариант 1)
2. **Получите токен** через `/api/auth/login`
3. **Установите токен** в `localStorage`
4. **Проверьте работу** - ошибки 403 должны исчезнуть

## Отладка

Если ошибки 403 продолжаются:

1. **Проверьте токен:**
   ```javascript
   // В консоли браузера:
   const token = localStorage.getItem('token')
   console.log('Token exists:', !!token)
   console.log('Token length:', token?.length)
   ```

2. **Проверьте заголовки запроса:**
   - Откройте Network tab (F12 → Network)
   - Найдите запрос к `/api/bots/info`
   - Проверьте Headers → Request Headers
   - Должен быть: `Authorization: Bearer <token>`

3. **Проверьте backend логи:**
   - Railway Dashboard → Backend сервис → Logs
   - Ищите ошибки аутентификации

4. **Проверьте CORS:**
   - Убедитесь, что `CORS_ORIGINS` в Backend сервисе содержит URL frontend:
     ```
     CORS_ORIGINS=https://ragbotvladislav-test.up.railway.app
     ```

