# Применение миграции для поля summary

## Проблема
Если вы видите ошибку `column documents.summary does not exist`, нужно применить миграцию.

## Решение

### Вариант 1: Автоматическое применение (рекомендуется)
Миграция должна применяться автоматически при деплое, но если это не произошло:

```bash
cd backend
alembic upgrade head
```

### Вариант 2: Ручное применение
Если автоматическое применение не работает:

```bash
cd backend
python -m alembic upgrade head
```

### Вариант 3: Прямой SQL (если Alembic недоступен)
Выполните в базе данных:

```sql
ALTER TABLE documents ADD COLUMN IF NOT EXISTS summary TEXT;
```

## Проверка
После применения миграции проверьте:

```sql
SELECT column_name FROM information_schema.columns 
WHERE table_name = 'documents' AND column_name = 'summary';
```

Должна вернуться строка с `summary`.

## Примечание
Код теперь работает даже без поля `summary` - он будет использовать содержимое документов напрямую. Но для лучшей работы рекомендуется применить миграцию.

