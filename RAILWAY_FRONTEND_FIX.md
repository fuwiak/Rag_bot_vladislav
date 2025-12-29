# Исправление ошибки Frontend на Railway

## Проблема

Ошибка при деплое frontend:
```
dockerfile invalid: flag '--mount=type=bind,from=builder,source=/app/.next/static,target=/mnt/static' is missing a type=cache argument (other mount types are not supported)
```

## Решение

Dockerfile для frontend был исправлен - убран `--mount=type=bind`, который Railway не поддерживает.

## Что было исправлено

1. **admin-panel/Dockerfile:**
   - Убран `--mount=type=bind` 
   - Использован безопасный способ копирования `.next/static`
   - Теперь копируется через временную директорию и shell команды

2. **telegram-bots/Dockerfile:**
   - Обновлен для работы без Root Directory
   - Build context должен быть root проекта

## Как развернуть Frontend на Railway

### Вариант 1: С Root Directory (рекомендуется)

1. Создайте новый сервис в Railway
2. Подключите GitHub репозиторий
3. **Settings → Build:**
   - **Root Directory:** `admin-panel`
   - **Dockerfile Path:** `admin-panel/Dockerfile` (автоматически)
4. **Settings → Variables:**
   ```
   NEXT_PUBLIC_BACKEND_URL=https://your-backend.railway.app
   PORT=3000
   NODE_ENV=production
   ```
5. Дождитесь деплоя

### Вариант 2: Без Root Directory

1. Создайте новый сервис
2. **Settings → Build:**
   - **Root Directory:** оставьте пустым
   - **Dockerfile Path:** `admin-panel/Dockerfile`
3. Остальное как в варианте 1

## Проверка

После деплоя:
1. Откройте URL frontend сервиса
2. Должна открыться страница входа в админ-панель
3. Если видите ошибку подключения к backend - проверьте `NEXT_PUBLIC_BACKEND_URL`

## Если все еще есть ошибки

1. Проверьте логи в Railway Dashboard
2. Убедитесь, что backend запущен и доступен
3. Проверьте переменные окружения
4. Убедитесь, что `NEXT_PUBLIC_BACKEND_URL` указывает на правильный URL backend

---

**Изменения уже отправлены в GitHub и готовы к использованию!**











