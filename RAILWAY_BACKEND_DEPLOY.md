# Развертывание Backend на Railway

Пошаговая инструкция по развертыванию Backend сервиса на Railway.

## Шаг 1: Создание Backend Service

1. В Railway Dashboard откройте ваш проект
2. Нажмите **"New"** → **"GitHub Repo"**
3. Выберите репозиторий `Rag_bot_vladislav`
4. Railway создаст новый сервис

## Шаг 2: Настройка Build

1. Откройте настройки сервиса (Settings)
2. Перейдите в раздел **"Build"**
3. Настройте:
   - **Root Directory:** оставьте **ПУСТЫМ** (root проекта)
   - **Dockerfile Path:** `backend/Dockerfile` (автоматически из railway.json)

## Шаг 3: Создание и подключение Volume

1. Если volume еще не создан:
   - В проекте Railway нажмите **"New"** → **"Volume"**
   - Название: `sqlite-data`
   - Размер: минимум 1 GB

2. Подключите volume к Backend Service:
   - Settings → **"Volumes"**
   - Нажмите **"Add Volume"**
   - Выберите volume `sqlite-data`
   - **Mount Path:** `/data`
   - Сохраните

## Шаг 4: Переменные окружения

Settings → **"Variables"** → добавьте следующие переменные:

### Обязательные переменные:

```bash
# База данных (SQLite)
DATABASE_URL=sqlite+aiosqlite:////data/rag_bot.db

# Qdrant (векторная БД)
QDRANT_URL=https://your-cluster-id.us-east4-0.gcp.cloud.qdrant.io
QDRANT_API_KEY=your_qdrant_api_key

# OpenRouter (LLM API)
OPENROUTER_API_KEY=your_openrouter_api_key

# Admin Panel Secrets (сгенерируйте случайные строки)
ADMIN_SECRET_KEY=сгенерируйте_случайную_строку
ADMIN_SESSION_SECRET=сгенерируйте_случайную_строку
```

### Переменные для CORS (заполните после получения URL):

```bash
# URL вашего backend (заполните после деплоя)
BACKEND_URL=https://your-backend-service.railway.app

# URL вашего frontend (заполните после создания frontend)
CORS_ORIGINS=https://your-frontend-service.railway.app
```

## Шаг 5: Генерация секретных ключей

Для `ADMIN_SECRET_KEY` и `ADMIN_SESSION_SECRET` сгенерируйте случайные строки:

```bash
# В терминале
openssl rand -hex 32

# Или через Python
python -c "import secrets; print(secrets.token_hex(32))"
```

Используйте сгенерированные строки для обеих переменных.

## Шаг 6: Деплой и получение URL

1. Railway автоматически начнет деплой после сохранения настроек
2. Дождитесь завершения (зеленый статус)
3. Скопируйте URL сервиса (например: `https://backend-production-xxxx.up.railway.app`)
4. Обновите переменные:
   - `BACKEND_URL` = ваш URL backend
   - `CORS_ORIGINS` = URL frontend (после создания frontend)

## Шаг 7: Проверка работы

1. **Проверьте health endpoint:**
   - Откройте: `https://your-backend.railway.app/health`
   - Должен вернуться: `{"status":"healthy"}`

2. **Проверьте логи:**
   - Railway Dashboard → Backend Service → Logs
   - Убедитесь, что нет ошибок
   - Должны быть сообщения о запуске сервера и миграциях

## Шаг 8: Создание администратора

После успешного деплоя создайте первого администратора:

### Способ 1: Через Railway CLI (рекомендуется)

```bash
# Установите Railway CLI
npm i -g @railway/cli

# Войдите в Railway
railway login

# Подключитесь к проекту
railway link

# Создайте администратора
railway run --service backend python create_admin_auto.py
```

### Способ 2: Через Railway Dashboard

1. Откройте Backend Service
2. Перейдите в **Settings** → **Deployments**
3. Используйте **"Run Command"** или создайте новый deployment
4. Введите команду:
   ```
   python create_admin_auto.py
   ```

По умолчанию создается администратор:
- **Username:** `admin`
- **Password:** `admin`

## Важные замечания

### Порядок развертывания

1. **Сначала** создайте Backend и получите его URL
2. **Затем** создайте Frontend с правильным `NEXT_PUBLIC_BACKEND_URL`
3. **После** получения URL Frontend обновите `CORS_ORIGINS` в Backend

### SQLite Volume

- Volume должен быть подключен к Backend Service (обязательно)
- Путь монтирования: `/data`
- База данных будет создана автоматически при первом запуске

### Миграции базы данных

- Backend автоматически запускает миграции при старте
- Проверьте логи на наличие ошибок миграций
- Если миграции не прошли, проверьте права доступа к `/data`

### Переменные окружения

- Все секретные ключи должны быть в переменных окружения Railway
- Не храните credentials в коде или Docker образах
- Используйте сильные случайные значения для `ADMIN_SECRET_KEY` и `ADMIN_SESSION_SECRET`

## Troubleshooting

### Backend не запускается

1. **Проверьте логи:**
   - Railway Dashboard → Backend Service → Logs
   - Ищите ошибки подключения к БД или миграций

2. **Проверьте переменные окружения:**
   - Убедитесь, что все обязательные переменные установлены
   - Проверьте формат `DATABASE_URL`: `sqlite+aiosqlite:////data/rag_bot.db` (4 слеша!)

3. **Проверьте volume:**
   - Убедитесь, что volume создан и подключен
   - Проверьте путь монтирования: `/data`

### Ошибки базы данных

1. **Проверьте права доступа:**
   - Убедитесь, что backend может писать в `/data`
   - Проверьте формат `DATABASE_URL`

2. **Проверьте миграции:**
   - Логи должны показывать успешное выполнение миграций
   - Если миграции не прошли, проверьте логи

### Health endpoint не отвечает

1. **Проверьте, что backend запущен:**
   - Логи должны показывать `Application startup complete`
   - Проверьте, что нет ошибок при старте

2. **Проверьте URL:**
   - Убедитесь, что используете правильный URL backend
   - Проверьте, что сервис не в режиме sleep (Railway может усыплять неактивные сервисы)

## Следующие шаги

После успешного развертывания backend:

1. ✅ Создайте администратора (см. Шаг 8)
2. ✅ Создайте Frontend Service (см. `RAILWAY_QUICK_DEPLOY.md`)
3. ✅ Обновите `CORS_ORIGINS` в Backend после получения URL Frontend
4. ✅ Войдите в админ-панель и создайте первый проект

---

**Готово!** Backend должен быть развернут и работать на Railway.









