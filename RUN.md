# Инструкция по запуску приложения

## Быстрый запуск

### 1. Backend (FastAPI) - Терминал 1

```bash
cd backend

# Убедитесь что активировано виртуальное окружение (если используете)
# source venv/bin/activate  # Mac/Linux
# или
# venv\Scripts\activate  # Windows

# Убедитесь что миграции применены
alembic upgrade head

# Запустите сервер
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Backend будет доступен на: **http://localhost:8000**
- API документация: http://localhost:8000/docs
- Health check: http://localhost:8000/health

### 2. Frontend (Next.js Admin Panel) - Терминал 2

```bash
cd admin-panel

# Установите зависимости (если еще не установлены)
npm install

# Запустите dev сервер
npm run dev
```

Frontend будет доступен на: **http://localhost:3000**

### 3. Вход в систему

1. Откройте http://localhost:3000
2. Войдите с учетными данными:
   - **Логин**: `admin`
   - **Пароль**: `admin`

> Если администратор еще не создан, создайте его:
> ```bash
> cd backend
> python create_admin.py
> ```

---

## Полная настройка с нуля

### Предварительные требования

- Python 3.11+
- Node.js 18+
- PostgreSQL (локально или удаленно)

### Шаг 1: Настройка базы данных

Убедитесь что PostgreSQL запущен и создана база данных:

```bash
# Через psql
psql -U postgres
CREATE DATABASE rag_bot_db;
\q
```

Или используйте существующую базу данных.

### Шаг 2: Настройка переменных окружения

Убедитесь что в корне проекта есть `.env` файл с настройками:

```env
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/rag_bot_db
QDRANT_URL=your_qdrant_url
QDRANT_API_KEY=your_qdrant_api_key
OPENROUTER_API_KEY=your_openrouter_api_key
ADMIN_SECRET_KEY=your_secret_key
ADMIN_SESSION_SECRET=your_session_secret
```

### Шаг 3: Backend Setup

```bash
cd backend

# Создайте виртуальное окружение (рекомендуется)
python -m venv venv
source venv/bin/activate  # Mac/Linux
# или venv\Scripts\activate  # Windows

# Установите зависимости
pip install -r requirements.txt

# Примените миграции
alembic upgrade head

# Создайте администратора
python create_admin.py

# Запустите сервер
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Шаг 4: Frontend Setup

```bash
cd admin-panel

# Установите зависимости
npm install

# Создайте .env.local (если нужно изменить URL бэкенда)
echo "NEXT_PUBLIC_BACKEND_URL=http://localhost:8000" > .env.local

# Запустите dev сервер
npm run dev
```

---

## Проверка работы

1. ✅ Backend запущен: http://localhost:8000/health должен вернуть `{"status": "healthy"}`
2. ✅ Frontend запущен: http://localhost:3000 должен открыть страницу логина
3. ✅ Войдите в систему с `admin/admin`
4. ✅ Создайте проект
5. ✅ Загрузите документы
6. ✅ Настройте Telegram бота

---

## Остановка

- **Backend**: Нажмите `Ctrl+C` в терминале с backend
- **Frontend**: Нажмите `Ctrl+C` в терминале с frontend

---

## Полезные команды

### Миграции базы данных

```bash
cd backend

# Применить все миграции
alembic upgrade head

# Посмотреть текущую версию
alembic current

# Создать новую миграцию
alembic revision --autogenerate -m "описание изменений"
```

### Создание администратора

```bash
cd backend
python create_admin.py
```

### Создание тестового пользователя

```bash
cd backend
python create_test_user.py
```

---

## Решение проблем

### Порт уже занят

Если порт 8000 или 3000 занят:

**Backend:**
```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8001
```

**Frontend:**
Измените порт в `admin-panel/package.json` или используйте:
```bash
npm run dev -- -p 3001
```

### Ошибка подключения к БД

Проверьте:
- PostgreSQL запущен
- DATABASE_URL правильный в .env
- База данных существует
- Права доступа настроены

### Ошибки с зависимостями

**Python:**
```bash
pip install --upgrade pip
pip install -r requirements.txt
```

**Node.js:**
```bash
rm -rf node_modules package-lock.json
npm install
```

















