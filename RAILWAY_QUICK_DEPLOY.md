# Быстрое развертывание на Railway

Пошаговая инструкция по развертыванию Frontend и Backend на Railway.

## Предварительные требования

- Аккаунт на [Railway](https://railway.app)
- GitHub репозиторий с кодом (уже готов)
- API ключи: Qdrant, OpenRouter

---

## Шаг 1: Создание проекта на Railway

1. Войдите в [Railway](https://railway.app)
2. Нажмите **"New Project"**
3. Выберите **"Deploy from GitHub repo"**
4. Выберите ваш репозиторий `Rag_bot_vladislav`
5. Railway автоматически обнаружит проект

---

## Шаг 2: Создание Persistent Volume для SQLite

1. В проекте Railway нажмите **"New"** → **"Volume"**
2. Назовите volume: `sqlite-data`
3. Размер: минимум 1 GB (можно больше)
4. Нажмите **"Add Volume"**

**Важно:** Volume будет использоваться для хранения SQLite базы данных.

---

## Шаг 3: Создание Backend Service

### 3.1. Добавление сервиса

1. В проекте Railway нажмите **"New"** → **"GitHub Repo"**
2. Выберите тот же репозиторий `Rag_bot_vladislav`
3. Railway создаст новый сервис

### 3.2. Настройка Build

1. Откройте настройки сервиса (Settings)
2. В разделе **"Build"**:
   - **Root Directory:** `backend`
   - **Dockerfile Path:** `backend/Dockerfile` (автоматически)
3. Сохраните изменения

### 3.3. Подключение Volume

1. В настройках сервиса перейдите в **"Volumes"**
2. Нажмите **"Add Volume"**
3. Выберите volume `sqlite-data`
4. **Mount Path:** `/data`
5. Сохраните

### 3.4. Переменные окружения

В настройках сервиса перейдите в **"Variables"** и добавьте:

```bash
# База данных
DATABASE_URL=sqlite+aiosqlite:////data/rag_bot.db

# Qdrant (замените на свои значения)
QDRANT_URL=https://your-cluster-id.us-east4-0.gcp.cloud.qdrant.io
QDRANT_API_KEY=your_qdrant_api_key

# OpenRouter (замените на свой ключ)
OPENROUTER_API_KEY=your_openrouter_api_key

# Admin Panel Secrets (сгенерируйте случайные строки)
ADMIN_SECRET_KEY=generate-random-string-here
ADMIN_SESSION_SECRET=generate-random-string-here

# Application URLs (заполните после получения URL от Railway)
BACKEND_URL=https://your-backend-service.railway.app
CORS_ORIGINS=https://your-frontend-service.railway.app
```

**Как сгенерировать секретные ключи:**
```bash
# В терминале
openssl rand -hex 32
# Или
python -c "import secrets; print(secrets.token_hex(32))"
```

### 3.5. Получение URL Backend

1. После деплоя Railway присвоит URL сервису
2. Скопируйте URL (например: `https://backend-production-xxxx.up.railway.app`)
3. Обновите переменные:
   - `BACKEND_URL` = ваш URL backend
   - `CORS_ORIGINS` = URL frontend (заполните после создания frontend)

---

## Шаг 4: Создание Frontend Service

### 4.1. Добавление сервиса

1. В проекте Railway нажмите **"New"** → **"GitHub Repo"**
2. Выберите тот же репозиторий `Rag_bot_vladislav`
3. Railway создаст новый сервис

### 4.2. Настройка Build

1. Откройте настройки сервиса (Settings)
2. В разделе **"Build"**:
   - **Root Directory:** `admin-panel`
   - **Dockerfile Path:** `admin-panel/Dockerfile` (автоматически)
3. Сохраните изменения

### 4.3. Подключение Volume (опционально, если нужен доступ к БД)

1. В настройках сервиса перейдите в **"Volumes"**
2. Нажмите **"Add Volume"**
3. Выберите volume `sqlite-data`
4. **Mount Path:** `/data`
5. Сохраните

### 4.4. Переменные окружения

В настройках сервиса перейдите в **"Variables"** и добавьте:

```bash
# Backend URL (замените на URL вашего backend сервиса)
NEXT_PUBLIC_BACKEND_URL=https://your-backend-service.railway.app

# Port (Railway установит автоматически, но можно указать явно)
PORT=3000

# Environment
NODE_ENV=production
```

**Важно:** `NEXT_PUBLIC_BACKEND_URL` должен быть URL вашего backend сервиса из шага 3.5.

### 4.5. Получение URL Frontend

1. После деплоя Railway присвоит URL сервису
2. Скопируйте URL (например: `https://frontend-production-xxxx.up.railway.app`)
3. Обновите переменную `CORS_ORIGINS` в Backend Service:
   - Вернитесь в настройки Backend Service
   - Обновите `CORS_ORIGINS=https://your-frontend-service.railway.app`

---

## Шаг 5: Проверка развертывания

### 5.1. Проверка Backend

1. Откройте URL backend сервиса
2. Добавьте `/health` в конец URL
3. Должен вернуться ответ: `{"status":"healthy"}`

Пример: `https://your-backend.railway.app/health`

### 5.2. Проверка Frontend

1. Откройте URL frontend сервиса
2. Должна открыться страница входа в админ-панель

### 5.3. Создание администратора

После первого запуска нужно создать администратора:

1. Подключитесь к Backend Service через Railway CLI или используйте скрипт локально
2. Запустите:
```bash
cd backend
python create_admin.py
```

Или через Railway CLI:
```bash
railway run --service backend python create_admin.py
```

---

## Шаг 6: Настройка доменов (опционально)

Railway автоматически предоставляет домены, но можно настроить кастомные:

1. В настройках сервиса перейдите в **"Settings"** → **"Networking"**
2. Нажмите **"Generate Domain"** для получения постоянного домена
3. Или добавьте свой кастомный домен

---

## Важные замечания

### Порядок развертывания

1. Сначала создайте Backend и получите его URL
2. Затем создайте Frontend с правильным `NEXT_PUBLIC_BACKEND_URL`
3. Обновите `CORS_ORIGINS` в Backend после получения URL Frontend

### Переменные окружения

- Все секретные ключи должны быть в переменных окружения Railway
- Не храните credentials в коде или Docker образах
- Используйте сильные случайные значения для `ADMIN_SECRET_KEY` и `ADMIN_SESSION_SECRET`

### SQLite Volume

- Volume должен быть подключен к Backend Service (обязательно)
- Volume можно подключить к Frontend (опционально, если нужен доступ к БД)
- Все сервисы, использующие БД, должны иметь доступ к одному volume

### Логи и отладка

- Просматривайте логи в Railway Dashboard
- Backend логи: Settings → Logs
- Frontend логи: Settings → Logs
- При ошибках проверяйте переменные окружения

---

## Troubleshooting

### Backend не запускается

1. Проверьте логи в Railway
2. Убедитесь, что все переменные окружения установлены
3. Проверьте, что volume подключен правильно
4. Убедитесь, что `DATABASE_URL` указывает на `/data/rag_bot.db`

### Frontend не подключается к Backend

1. Проверьте `NEXT_PUBLIC_BACKEND_URL` в переменных окружения Frontend
2. Проверьте `CORS_ORIGINS` в Backend (должен содержать URL Frontend)
3. Проверьте логи Backend на наличие CORS ошибок
4. Убедитесь, что Backend доступен по своему URL

### Ошибки базы данных

1. Убедитесь, что volume создан и подключен
2. Проверьте права доступа к `/data`
3. Проверьте формат `DATABASE_URL`: `sqlite+aiosqlite:////data/rag_bot.db` (4 слеша!)

### Проблемы с миграциями

Если возникают ошибки миграций:
1. Проверьте логи Backend
2. Убедитесь, что alembic может создать таблицы
3. При необходимости выполните миграции вручную через Railway CLI

---

## Следующие шаги

После успешного развертывания:

1. Создайте администратора (см. шаг 5.3)
2. Войдите в админ-панель
3. Создайте первый проект
4. Загрузите документы
5. Настройте Telegram бота

**Примечание:** Telegram Bots Service можно развернуть позже, если нужно. Он не обязателен для работы Frontend и Backend.

---

## Полезные команды Railway CLI

```bash
# Установка Railway CLI
npm i -g @railway/cli

# Вход в Railway
railway login

# Подключение к проекту
railway link

# Просмотр переменных окружения
railway variables

# Запуск команды в сервисе
railway run --service backend python create_admin.py

# Просмотр логов
railway logs --service backend
```

---

**Готово!** Ваш проект должен быть доступен на Railway.







