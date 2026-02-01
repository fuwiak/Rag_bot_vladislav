# Добавление колонки fast_mode на продакшн

## Проблема
Колонка `fast_mode` отсутствует в продакшн базе данных, что вызывает ошибку при загрузке файлов.

## Решение

### Вариант 1: Через Railway Dashboard (самый простой) ⭐

1. Откройте [Railway Dashboard](https://railway.app)
2. Выберите ваш проект
3. Найдите сервис **PostgreSQL** (база данных)
4. Откройте вкладку **"Query"** или **"Data"**
5. Вставьте SQL запрос:
```sql
ALTER TABLE documents 
ADD COLUMN IF NOT EXISTS fast_mode BOOLEAN DEFAULT FALSE;
```
6. Нажмите **"Run"** или **"Execute"**

### Вариант 2: Через Railway CLI с psql

1. Установите Railway CLI (если еще не установлен):
```bash
npm i -g @railway/cli
```

2. Войдите в Railway:
```bash
railway login
```

3. Выберите проект:
```bash
railway link
```

4. Подключитесь к PostgreSQL через psql:
```bash
railway connect postgres
```

5. Выполните SQL запрос:
```sql
ALTER TABLE documents 
ADD COLUMN IF NOT EXISTS fast_mode BOOLEAN DEFAULT FALSE;
```

6. Выйдите из psql:
```sql
\q
```

### Вариант 3: Через Railway CLI с Python скриптом

1. Установите Railway CLI:
```bash
npm i -g @railway/cli
```

2. Войдите и выберите проект:
```bash
railway login
railway link
```

3. Запустите скрипт:
```bash
railway run python backend/add_fast_mode_production.py
```

### Вариант 4: Через Railway Shell

1. Откройте Railway Dashboard
2. Выберите сервис **backend**
3. Откройте вкладку **"Shell"** или **"Terminal"**
4. Выполните:
```bash
cd backend
python add_fast_mode_production.py
```

### Вариант 5: Прямой SQL через Railway CLI

Если у вас есть доступ к DATABASE_URL:

1. Получите DATABASE_URL из переменных окружения Railway
2. Используйте psql напрямую:
```bash
psql $DATABASE_URL -c "ALTER TABLE documents ADD COLUMN IF NOT EXISTS fast_mode BOOLEAN DEFAULT FALSE;"
```

Или через Railway:
```bash
railway run psql $DATABASE_URL -c "ALTER TABLE documents ADD COLUMN IF NOT EXISTS fast_mode BOOLEAN DEFAULT FALSE;"
```

## Проверка

После добавления колонки проверьте:

```sql
SELECT column_name 
FROM information_schema.columns 
WHERE table_name = 'documents' AND column_name = 'fast_mode';
```

Должна вернуться строка с `fast_mode`.

## Примечание

Код теперь работает даже без колонки `fast_mode` - он автоматически определяет её наличие и использует соответствующий способ вставки данных. Но для лучшей работы рекомендуется добавить колонку.
