# Финальное исправление проблемы с переменными окружения

## Проблема

Переменные `NEXT_PUBLIC_BACKEND_URL` и `NEXT_PUBLIC_USE_MOCK_API` установлены в Railway, но frontend все еще пытается подключиться к `localhost:8000`.

## Причина

Переменные `NEXT_PUBLIC_*` встраиваются в JavaScript код во время сборки Next.js. Если они не были установлены ДО сборки, они не появятся в коде.

## Решение

Реализован fallback механизм через API route `/api/config`, который читает переменные окружения на сервере и возвращает их клиенту в runtime.

## Что было сделано

1. ✅ Создан API route `/api/config` - читает переменные на сервере
2. ✅ Обновлен `api-helpers.ts` - автоматически загружает конфигурацию из API route, если переменные не встроились
3. ✅ Все компоненты обновлены - используют асинхронную версию `getApiUrl()`

## Что нужно сделать в Railway

### 1. Убедитесь, что переменные установлены правильно

**Frontend сервис** → Settings → Variables:

```bash
NEXT_PUBLIC_BACKEND_URL=https://ragbotvladislav-backend.up.railway.app
NEXT_PUBLIC_USE_MOCK_API=false
```

**Важно:**
- Без кавычек
- Без trailing slash (`/` в конце)
- Без пробелов вокруг `=`

### 2. Пересоберите приложение

**Критично:** После установки/изменения переменных нужно пересобрать:

1. Railway Dashboard → Frontend сервис → Settings → Deploy
2. Нажмите **"Redeploy"** или **"Deploy Latest"**
3. Дождитесь завершения сборки (может занять несколько минут)

### 3. Проверьте работу API route

После деплоя откройте в браузере:
```
https://ragbotvladislav-test.up.railway.app/api/config
```

**Ожидаемый результат:**
```json
{
  "backendUrl": "https://ragbotvladislav-backend.up.railway.app",
  "useMockApi": false
}
```

Если видите `localhost:8000` - переменные не установлены в Railway или установлены неправильно.

### 4. Проверьте в консоли браузера

1. Откройте frontend: `https://ragbotvladislav-test.up.railway.app/telegram-bots`
2. Откройте консоль браузера (F12)
3. Должны увидеть сообщение: `[API Helpers] Using config from API route: { backendUrl: 'https://...', useMockApi: false }`

## Как это работает

1. **При первом запросе** код проверяет встроенные переменные `NEXT_PUBLIC_*`
2. **Если их нет или это localhost** - загружает конфигурацию из `/api/config`
3. **API route** читает переменные на сервере (они всегда доступны там)
4. **Конфигурация кэшируется** для последующих запросов
5. **Все API запросы** используют правильный URL

## Отладка

### Проверка API route

Откройте: `https://ragbotvladislav-test.up.railway.app/api/config`

**Если возвращает localhost:**
- Переменные не установлены в Railway
- Или установлены неправильно (с кавычками, с пробелами)

**Если возвращает правильный URL:**
- API route работает
- Проблема в загрузке конфигурации на клиенте

### Проверка консоли браузера

Откройте консоль (F12) и найдите сообщения:
- `[API Helpers] Using config from API route:` - конфигурация загружена успешно
- `[API Helpers] Failed to load config from API route:` - ошибка загрузки
- `[API Helpers] Config from API route still has localhost:` - переменные не установлены в Railway

### Проверка Network tab

1. Консоль браузера (F12) → вкладка **Network**
2. Обновите страницу
3. Найдите запрос к `/api/config`
4. Проверьте Response - должен содержать правильный `backendUrl`

## Если проблема сохраняется

1. **Удалите все переменные** `NEXT_PUBLIC_*` из Frontend сервиса
2. **Сохраните** и дождитесь пересборки
3. **Добавьте переменные заново** (правильные значения, без кавычек)
4. **Сохраните** и дождитесь пересборки
5. **Проверьте** `/api/config` - должен вернуть правильный URL
6. **Проверьте** frontend - должен подключиться к backend

## Готово!

После пересборки frontend должен автоматически загрузить конфигурацию из API route и подключиться к backend на Railway.


