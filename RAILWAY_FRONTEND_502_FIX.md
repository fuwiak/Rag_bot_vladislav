# Исправление ошибки 502 на Frontend Railway

## Проблема

Ошибка 502 "Application failed to respond" на frontend означает, что приложение не запустилось или упало при старте.

## Причины и решения

### 1. Проверьте логи Railway

**Самое важное!** Откройте Railway Dashboard → Frontend Service → **Logs**

Ищите ошибки типа:
- `Error: Cannot find module`
- `Port already in use`
- `EADDRINUSE`
- `Failed to start server`

---

### 2. Проверьте переменные окружения

В Railway Dashboard → Frontend Service → Settings → Variables должны быть:

```bash
NEXT_PUBLIC_BACKEND_URL=https://your-backend.railway.app
PORT=3000
NODE_ENV=production
```

**Важно:**
- `PORT` должен быть установлен (Railway может установить автоматически, но лучше указать явно)
- `NEXT_PUBLIC_BACKEND_URL` должен быть правильным URL backend (с `https://`)

---

### 3. Проблема с портом

Next.js standalone может не читать PORT из переменных окружения правильно.

**Решение:** Обновите Dockerfile или добавьте скрипт запуска.

Проверьте, что в Dockerfile используется правильная команда запуска:
```dockerfile
CMD ["node", "server.js"]
```

И что Next.js настроен на чтение PORT:
```javascript
// next.config.js уже настроен правильно
```

---

### 4. Проблема с сборкой

Если сборка не завершилась успешно, приложение не запустится.

**Проверьте:**
1. Railway Dashboard → Frontend Service → **Deployments**
2. Посмотрите на последний deployment - был ли он успешным?
3. Если есть ошибки сборки - исправьте их

---

### 5. Проблема с .next/static

Если Next.js не может найти статические файлы, приложение может не запуститься.

**Решение:** Это уже исправлено в Dockerfile, но проверьте логи на наличие ошибок о missing files.

---

## Пошаговая диагностика

### Шаг 1: Проверьте логи

1. Railway Dashboard → Frontend Service
2. Откройте вкладку **Logs**
3. Ищите последние ошибки перед 502

**Типичные ошибки:**

```
Error: listen EADDRINUSE: address already in use :::3000
```
**Решение:** Убедитесь, что `PORT` установлен правильно

```
Error: Cannot find module 'server.js'
```
**Решение:** Проблема со сборкой - проверьте build logs

```
TypeError: Cannot read property 'PORT' of undefined
```
**Решение:** Добавьте `PORT=3000` в переменные окружения

---

### Шаг 2: Проверьте переменные окружения

Убедитесь, что все переменные установлены:

```bash
# Обязательные
NEXT_PUBLIC_BACKEND_URL=https://your-backend.railway.app
NODE_ENV=production

# Опциональные (но рекомендуется)
PORT=3000
```

---

### Шаг 3: Проверьте health check

Railway использует health check для проверки работоспособности.

Проверьте, что endpoint `/api/health` работает:
- Откройте: `https://your-frontend.railway.app/api/health`
- Должен вернуться статус 200

Если health check не работает, Railway будет показывать 502.

---

### Шаг 4: Пересоберите сервис

1. Railway Dashboard → Frontend Service
2. Settings → **Deployments**
3. Нажмите **"Redeploy"** или **"Deploy Latest"**
4. Дождитесь завершения сборки и деплоя

---

## Быстрое исправление

### Вариант 1: Добавить PORT явно

1. Railway Dashboard → Frontend Service → Settings → Variables
2. Добавьте/обновите:
   ```
   PORT=3000
   ```
3. Сохраните и дождитесь перезапуска

### Вариант 2: Проверить NEXT_PUBLIC_BACKEND_URL

1. Убедитесь, что `NEXT_PUBLIC_BACKEND_URL` установлен
2. URL должен быть правильным (с `https://`)
3. URL должен быть доступен (проверьте backend `/health`)

### Вариант 3: Очистить кэш и пересобрать

1. Railway Dashboard → Frontend Service → Settings → **Advanced**
2. Нажмите **"Clear Build Cache"**
3. Пересоберите сервис

---

## Проверка конфигурации

### Правильная конфигурация Frontend:

**Variables:**
```bash
NEXT_PUBLIC_BACKEND_URL=https://backend-production-xxxx.up.railway.app
PORT=3000
NODE_ENV=production
```

**Build Settings:**
- Root Directory: пусто (root проекта)
- Dockerfile Path: `admin-panel/Dockerfile`

**Health Check:**
- Path: `/api/health`
- Timeout: 100

---

## Если ничего не помогает

1. **Проверьте логи backend:**
   - Убедитесь, что backend работает
   - Проверьте `/health` endpoint

2. **Проверьте сеть:**
   - Frontend должен иметь доступ к backend
   - Проверьте, что backend URL правильный

3. **Создайте новый сервис:**
   - Иногда помогает пересоздать сервис с нуля
   - Скопируйте все переменные окружения

4. **Проверьте Railway статус:**
   - Убедитесь, что Railway не имеет проблем
   - Проверьте статус на status.railway.app

---

## Частые ошибки

### Ошибка: "Cannot find module 'server.js'"

**Причина:** Next.js не собрался правильно или standalone output не создан.

**Решение:**
1. Проверьте build logs
2. Убедитесь, что `output: 'standalone'` в `next.config.js`
3. Пересоберите сервис

### Ошибка: "Port 3000 already in use"

**Причина:** Конфликт портов.

**Решение:**
1. Убедитесь, что `PORT` установлен в переменных окружения
2. Railway должен автоматически назначить порт, но лучше указать явно

### Ошибка: "Failed to connect to backend"

**Причина:** `NEXT_PUBLIC_BACKEND_URL` неправильный или backend недоступен.

**Решение:**
1. Проверьте URL backend
2. Убедитесь, что backend запущен
3. Проверьте CORS настройки в backend

---

**Самый важный шаг - проверьте логи в Railway Dashboard!** Там будет точная причина ошибки.

