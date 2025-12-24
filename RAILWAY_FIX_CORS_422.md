# Исправление ошибок CORS и 422 при создании проекта

## Проблемы

1. **CORS ошибка**: `No 'Access-Control-Allow-Origin' header is present`
2. **422 ошибка валидации**: Backend отклоняет данные проекта

## Решение

### 1. Исправить CORS на Backend

**Railway Dashboard → Backend сервис → Settings → Variables**

Добавьте или обновите переменную `CORS_ORIGINS`:

```
CORS_ORIGINS=https://ragbotvladislav-test.up.railway.app
```

**Важно:**
- БЕЗ кавычек
- БЕЗ пробелов
- Если нужно несколько URL, разделите запятой: `https://frontend1.railway.app,https://frontend2.railway.app`

После изменения переменной Railway автоматически пересоберет backend.

### 2. Проверить данные проекта

После исправления CORS, если ошибка 422 сохраняется:

1. Откройте консоль браузера (F12)
2. Найдите сообщение `Sending project data:` - там будет видно, какие данные отправляются
3. Проверьте, что все обязательные поля заполнены:
   - `name` - не пустая строка
   - `access_password` - минимум 4 символа
   - `prompt_template` - минимум 10 символов
   - `max_response_length` - число от 100 до 10000

### 3. Проверить ответ backend

В консоли браузера будет видно детали ошибки валидации:
```
Error creating project: { detail: [...] }
```

Каждая ошибка показывает:
- `loc` - какое поле не прошло валидацию
- `msg` - причина ошибки

## Проверка CORS

После добавления `CORS_ORIGINS` проверьте:

1. Откройте: `https://ragbotvladislav-backend.up.railway.app/api/test-connection`
2. Должно вернуть JSON с `cors_origins`, где будет виден ваш frontend URL

## Если проблема сохраняется

1. **Проверьте логи backend:**
   - Railway Dashboard → Backend сервис → Logs
   - Ищите ошибки валидации или CORS

2. **Проверьте переменные окружения:**
   - Убедитесь, что `CORS_ORIGINS` установлена правильно
   - Убедитесь, что нет лишних пробелов или кавычек

3. **Проверьте данные в консоли:**
   - Откройте консоль браузера (F12)
   - Посмотрите `Sending project data:` - все поля должны быть правильного типа

