# Пошаговое развертывание на Railway

## Быстрый старт

### 1. Подключение GitHub репозитория

1. Зайдите на [railway.app](https://railway.app)
2. Нажмите **"New Project"**
3. Выберите **"Deploy from GitHub repo"**
4. Выберите репозиторий `Rag_bot_vladislav`
5. Railway автоматически обнаружит проект

---

### 2. Создание Volume для SQLite

1. В проекте нажмите **"New"** → **"Volume"**
2. Название: `sqlite-data`
3. Размер: 1 GB
4. Нажмите **"Add"**

---

### 3. Backend Service

#### 3.1. Создание сервиса

1. **"New"** → **"GitHub Repo"** → выберите тот же репозиторий
2. Назовите сервис: `backend`

#### 3.2. Настройки Build

1. Settings → Build
2. **Root Directory:** `backend`
3. **Dockerfile Path:** `backend/Dockerfile` (автоматически)

#### 3.3. Подключение Volume

1. Settings → Volumes
2. **Add Volume** → выберите `sqlite-data`
3. **Mount Path:** `/data`

#### 3.4. Переменные окружения

Settings → Variables → добавьте:

```bash
DATABASE_URL=sqlite+aiosqlite:////data/rag_bot.db
QDRANT_URL=https://your-cluster-id.us-east4-0.gcp.cloud.qdrant.io
QDRANT_API_KEY=your_key
OPENROUTER_API_KEY=your_key
ADMIN_SECRET_KEY=сгенерируйте_случайную_строку
ADMIN_SESSION_SECRET=сгенерируйте_случайную_строку
```

**Пока не заполняйте:**
- `BACKEND_URL` - заполните после деплоя
- `CORS_ORIGINS` - заполните после создания frontend

#### 3.5. Деплой и получение URL

1. Railway автоматически начнет деплой
2. Дождитесь завершения (зеленый статус)
3. Скопируйте URL сервиса (например: `https://backend-production-xxxx.up.railway.app`)
4. Обновите переменные:
   - `BACKEND_URL` = ваш URL
   - Пока оставьте `CORS_ORIGINS` пустым

---

### 4. Frontend Service

#### 4.1. Создание сервиса

1. **"New"** → **"GitHub Repo"** → выберите тот же репозиторий
2. Назовите сервис: `frontend`

#### 4.2. Настройки Build

1. Settings → Build
2. **Root Directory:** `admin-panel`
3. **Dockerfile Path:** `admin-panel/Dockerfile` (автоматически)

#### 4.3. Переменные окружения

Settings → Variables → добавьте:

```bash
NEXT_PUBLIC_BACKEND_URL=https://your-backend-service.railway.app
PORT=3000
NODE_ENV=production
```

**Важно:** Замените `https://your-backend-service.railway.app` на реальный URL вашего backend из шага 3.5.

#### 4.4. Деплой и получение URL

1. Railway автоматически начнет деплой
2. Дождитесь завершения
3. Скопируйте URL frontend сервиса

#### 4.5. Обновление CORS в Backend

1. Вернитесь в Backend Service → Settings → Variables
2. Обновите `CORS_ORIGINS`:
   ```
   CORS_ORIGINS=https://your-frontend-service.railway.app
   ```
3. Railway автоматически перезапустит backend

---

### 5. Проверка работы

1. **Backend:** Откройте `https://your-backend.railway.app/health`
   - Должен вернуться: `{"status":"healthy"}`

2. **Frontend:** Откройте URL frontend сервиса
   - Должна открыться страница входа

3. **Создание администратора:**
   ```bash
   # Через Railway CLI
   railway run --service backend python create_admin.py
   ```

---

## Генерация секретных ключей

```bash
# В терминале
openssl rand -hex 32

# Или Python
python -c "import secrets; print(secrets.token_hex(32))"
```

Используйте сгенерированные строки для:
- `ADMIN_SECRET_KEY`
- `ADMIN_SESSION_SECRET`

---

## Важные моменты

1. **Порядок:** Сначала backend, потом frontend
2. **URL:** Сначала получите URL backend, затем используйте его в frontend
3. **CORS:** Обновите `CORS_ORIGINS` после получения URL frontend
4. **Volume:** Обязательно подключите volume к backend
5. **Переменные:** Все секреты только в Railway Variables, не в коде

---

## Troubleshooting

### Backend не запускается
- Проверьте логи в Railway
- Убедитесь, что volume подключен
- Проверьте формат `DATABASE_URL`: `sqlite+aiosqlite:////data/rag_bot.db` (4 слеша!)

### Frontend не подключается
- Проверьте `NEXT_PUBLIC_BACKEND_URL`
- Проверьте `CORS_ORIGINS` в backend
- Проверьте логи обоих сервисов

### Ошибки базы данных
- Убедитесь, что volume создан и подключен
- Проверьте права доступа к `/data`

---

Готово! После этого ваш проект будет работать на Railway.





