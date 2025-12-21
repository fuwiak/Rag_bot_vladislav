# Быстрый старт - Локальный запуск

## Вариант 1: Docker Compose (Рекомендуется)

### Шаг 1: Настройка переменных окружения

```bash
# Скопируйте файл с примером переменных
cp .env.example .env

# Отредактируйте .env и заполните необходимые значения:
# - QDRANT_API_KEY (ваш ключ от Qdrant Cloud)
# - OPENROUTER_API_KEY (ваш ключ от OpenRouter)
# - ADMIN_SECRET_KEY (любая случайная строка)
# - ADMIN_SESSION_SECRET (любая случайная строка)
```

### Шаг 2: Запуск через Docker Compose

```bash
docker-compose -f docker-compose.local.yml up
```

Это запустит:
- PostgreSQL на порту 5432
- Backend API на порту 8000
- Admin Panel на порту 3000

### Шаг 3: Инициализация базы данных

В отдельном терминале:

```bash
# Запустите миграции
docker-compose -f docker-compose.local.yml exec backend alembic upgrade head

# Создайте первого администратора (выполните в Python контейнере)
docker-compose -f docker-compose.local.yml exec backend python
```

В Python консоли:

```python
from app.core.database import AsyncSessionLocal
from app.models.admin_user import AdminUser
from app.services.auth_service import AuthService
import asyncio

async def create_admin():
    async with AsyncSessionLocal() as db:
        auth_service = AuthService(db)
        admin = AdminUser(
            username="admin",
            password_hash=auth_service.get_password_hash("admin123")
        )
        db.add(admin)
        await db.commit()
        print("Admin created: username=admin, password=admin123")

asyncio.run(create_admin())
```

### Шаг 4: Доступ к приложению

- **Admin Panel**: http://localhost:3000
  - Логин: `admin`
  - Пароль: `admin123` (или тот, который вы установили)

- **Backend API**: http://localhost:8000
  - Health check: http://localhost:8000/health
  - API docs: http://localhost:8000/docs

---

## Вариант 2: Без Docker (для разработки)

### Предварительные требования

- Python 3.11+
- Node.js 18+
- PostgreSQL 15+ (локально установленный)

### Шаг 1: Настройка PostgreSQL

```bash
# Создайте базу данных
createdb rag_bot_db

# Или через psql:
psql -U postgres
CREATE DATABASE rag_bot_db;
\q
```

### Шаг 2: Настройка Backend

```bash
cd backend

# Создайте виртуальное окружение
python -m venv venv

# Активируйте виртуальное окружение
# Linux/Mac:
source venv/bin/activate
# Windows:
# venv\Scripts\activate

# Установите зависимости
# Если grpcio kompiluje się zbyt długo, użyj skryptu:
# Linux/Mac:
./install-fast.sh
# Windows (PowerShell):
# pip install --only-binary :all: grpcio grpcio-tools
# pip install -r requirements.txt

# Или zwykła instalacja:
pip install -r requirements.txt

# Создайте .env файл в папке backend (или используйте корневой)
cp ../.env.example .env
# Отредактируйте .env и настройте DATABASE_URL:
# DATABASE_URL=postgresql://user:password@localhost:5432/rag_bot_db

# Запустите миграции
alembic upgrade head

# Создайте администратора
python create_admin.py
```

### Шаг 3: Запуск Backend

```bash
# В папке backend, с активированным venv
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Шаг 4: Настройка Admin Panel

Откройте новый терминал:

```bash
cd admin-panel

# Установите зависимости
npm install

# Создайте .env.local файл
echo "NEXT_PUBLIC_BACKEND_URL=http://localhost:8000" > .env.local

# Запустите dev сервер
npm run dev
```

### Шаг 5: Доступ к приложению

- **Admin Panel**: http://localhost:3000
- **Backend API**: http://localhost:8000/docs

---

## Проверка работы

1. Откройте http://localhost:3000
2. Войдите с учетными данными администратора
3. Создайте новый проект
4. Загрузите документы (.txt, .docx, или .pdf)
5. Настройте Telegram бота (получите токен от @BotFather)
6. Протестируйте бота в Telegram

---

## Устранение проблем

### Порт уже занят

Если порты 3000, 8000 или 5432 заняты, измените их в:
- `docker-compose.local.yml` (для Docker)
- Командах запуска (для локального запуска)

### Ошибки подключения к БД

Убедитесь, что:
- PostgreSQL запущен
- DATABASE_URL правильный в .env
- База данных создана

### Ошибки Qdrant или OpenRouter

Проверьте, что:
- API ключи правильно указаны в .env
- У вас есть доступ к Qdrant Cloud
- У вас есть доступ к OpenRouter API

### Проблемы с установкой grpcio

Если установка `grpcio` занимает слишком много времени:

**Linux/Mac:**
```bash
# Użyj pre-built wheels
pip install --only-binary :all: grpcio grpcio-tools
pip install -r requirements.txt
```

**Или użyj skryptu:**
```bash
./install-fast.sh
```

**Windows:**
```powershell
pip install --only-binary :all: grpcio grpcio-tools
pip install -r requirements.txt
```

### Проблемы с миграциями

```bash
# Просмотр текущей версии
alembic current

# Применение всех миграций
alembic upgrade head

# Откат миграции (осторожно!)
alembic downgrade -1
```

---

## Остановка

### Docker Compose:
```bash
docker-compose -f docker-compose.local.yml down

# С удалением volumes (удалит данные БД):
# docker-compose -f docker-compose.local.yml down -v
```

### Локальный запуск:
- Нажмите Ctrl+C в терминалах, где запущены сервисы
