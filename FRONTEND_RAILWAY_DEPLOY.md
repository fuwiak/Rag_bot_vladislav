# Деплой Frontend на Railway (без Backend)

Инструкция по деплою только frontend части приложения на Railway с использованием моков API для демонстрации UI.

## Преимущества

- ✅ Независимый деплой frontend
- ✅ Работает без backend
- ✅ Демонстрация UI с тестовыми данными
- ✅ Легко переключиться на реальный backend позже

## Предварительные требования

- Аккаунт на Railway
- GitHub репозиторий с проектом
- Доступ к Railway Dashboard

## Шаг 1: Подготовка репозитория

Убедитесь, что в репозитории есть:
- `admin-panel/railway.frontend.json` - конфигурация Railway для frontend
- `admin-panel/Dockerfile` - Dockerfile для сборки
- Все необходимые файлы Mock API в `admin-panel/app/api/mock/`

## Шаг 2: Создание сервиса на Railway

1. Войдите в [Railway Dashboard](https://railway.app)
2. Нажмите **"New Project"**
3. Выберите **"Deploy from GitHub repo"**
4. Выберите ваш репозиторий `Rag_bot_vladislav`

## Шаг 3: Настройка сервиса

1. Railway автоматически определит сервис
2. Если нужно, укажите:
   - **Root Directory**: `admin-panel` (или оставьте корень проекта)
   - **Dockerfile Path**: `admin-panel/Dockerfile`

## Шаг 4: Настройка переменных окружения

Перейдите в **Settings** → **Variables** и добавьте:

```bash
# Включить режим моков
NEXT_PUBLIC_USE_MOCK_API=true

# Port (Railway установит автоматически, но можно указать явно)
PORT=3000

# Node environment
NODE_ENV=production
```

**Важно:**
- `NEXT_PUBLIC_USE_MOCK_API=true` - обязательно для работы без backend
- `NEXT_PUBLIC_BACKEND_URL` - не нужен в режиме моков, оставьте пустым

## Шаг 5: Деплой

1. Railway автоматически начнет деплой после настройки
2. Дождитесь завершения сборки
3. Railway предоставит URL вашего приложения

## Шаг 6: Проверка

После деплоя:

1. Откройте URL, предоставленный Railway
2. Должна открыться страница логина
3. В режиме моков авторизация всегда успешна
4. Проверьте работу всех страниц:
   - Dashboard с проектами
   - Детали проекта
   - Документы
   - Пользователи
   - Telegram боты
   - Модели

## Переключение на реальный Backend

Когда backend будет готов:

1. Railway Dashboard → Frontend Service → Variables
2. Измените переменные:
   ```bash
   NEXT_PUBLIC_USE_MOCK_API=false
   NEXT_PUBLIC_BACKEND_URL=https://your-backend.railway.app
   ```
3. Перезапустите сервис (Railway автоматически пересоберет)

## Структура Mock API

Mock API реализован через Next.js API Routes:

- `/api/mock/auth/login` - авторизация
- `/api/mock/projects` - список проектов
- `/api/mock/projects/[id]` - детали проекта
- `/api/mock/documents/[projectId]` - документы проекта
- `/api/mock/users/project/[projectId]` - пользователи проекта
- `/api/mock/bots/info` - информация о ботах
- `/api/mock/models/available` - доступные модели

Все моки возвращают данные в том же формате, что и реальный API.

## Тестовые данные

В режиме моков доступны:

- 3 тестовых проекта
- Документы для каждого проекта
- Пользователи для каждого проекта
- Информация о ботах
- Список доступных моделей

## Решение проблем

### Frontend не запускается

1. Проверьте логи в Railway Dashboard
2. Убедитесь, что `NEXT_PUBLIC_USE_MOCK_API=true`
3. Проверьте, что Dockerfile правильный

### Моки не работают

1. Убедитесь, что `NEXT_PUBLIC_USE_MOCK_API=true`
2. Проверьте консоль браузера на ошибки
3. Убедитесь, что все файлы Mock API на месте

### Ошибки сборки

1. Проверьте логи сборки в Railway
2. Убедитесь, что все зависимости установлены
3. Проверьте версию Node.js в Dockerfile

## Полезные команды

### Локальный запуск с моками

```bash
cd admin-panel
cp .env.example.frontend .env.local
# Отредактируйте .env.local: NEXT_PUBLIC_USE_MOCK_API=true
npm run dev
```

### Проверка Mock API локально

```bash
# После запуска dev сервера
curl http://localhost:3000/api/mock/projects
curl http://localhost:3000/api/mock/auth/login -X POST -H "Content-Type: application/json" -d '{"username":"admin"}'
```

## Дополнительная информация

- Mock API использует in-memory хранилище (данные не сохраняются после перезапуска)
- Все операции (POST, PUT, DELETE) работают в памяти
- Для production с реальными данными подключите backend

## Следующие шаги

После деплоя frontend:

1. ✅ Frontend работает на Railway с моками
2. ⏳ Подготовьте backend
3. ⏳ Деплой backend на Railway
4. ⏳ Переключите frontend на реальный API

---

**Готово!** Ваш frontend теперь работает независимо на Railway с демонстрационными данными.


