# Создание администратора на Railway

## Проблема

Пароль не работает при входе в админ-панель. Это происходит потому, что:
1. Администратор еще не создан в базе данных
2. Или база данных не инициализирована

## Решение: Создание администратора

### Способ 1: Через Railway CLI (рекомендуется)

1. **Установите Railway CLI:**
   ```bash
   npm i -g @railway/cli
   ```

2. **Войдите в Railway:**
   ```bash
   railway login
   ```

3. **Подключитесь к проекту:**
   ```bash
   railway link
   ```
   Выберите ваш проект и backend service.

4. **Создайте администратора:**
   ```bash
   railway run --service backend python create_admin.py
   ```
   
   Введите данные:
   - Username: `admin` (или любой другой)
   - Password: `admin` (или любой другой)

### Способ 2: Через Railway Dashboard (One-Click Deploy)

1. Откройте Railway Dashboard
2. Выберите **Backend Service**
3. Перейдите в **Settings** → **Deployments**
4. Нажмите **"New Deployment"** или используйте **"Run Command"**
5. Введите команду:
   ```
   python create_admin.py
   ```
6. Следуйте инструкциям в логах

### Способ 3: Через локальный скрипт (если есть доступ к БД)

Если у вас есть доступ к базе данных SQLite:

1. **Скачайте базу данных с Railway:**
   - Через Railway Dashboard → Backend Service → Volumes
   - Скачайте файл `/data/rag_bot.db`

2. **Локально запустите скрипт:**
   ```bash
   cd backend
   # Установите DATABASE_URL на локальный файл
   export DATABASE_URL=sqlite+aiosqlite:///./rag_bot.db
   python create_admin.py
   ```

3. **Загрузите базу обратно на Railway**

## Проверка

После создания администратора:

1. Откройте frontend URL
2. Войдите с созданными credentials:
   - Username: `admin` (или тот, который вы указали)
   - Password: `admin` (или тот, который вы указали)

## Важно

- По умолчанию скрипт создает администратора с username `admin` и password `admin`
- Вы можете указать свои значения при запуске скрипта
- Если администратор уже существует, скрипт сообщит об этом

## Если все еще не работает

1. **Проверьте логи backend:**
   - Railway Dashboard → Backend Service → Logs
   - Убедитесь, что нет ошибок подключения к БД

2. **Проверьте переменные окружения:**
   - `DATABASE_URL=sqlite+aiosqlite:////data/rag_bot.db`
   - Убедитесь, что volume подключен

3. **Проверьте миграции:**
   - Backend должен автоматически запустить миграции при старте
   - Проверьте логи на наличие ошибок миграций

4. **Сбросьте пароль (если нужно):**
   ```bash
   railway run --service backend python reset_admin_password.py
   ```

---

**Готово!** После создания администратора вы сможете войти в админ-панель.

