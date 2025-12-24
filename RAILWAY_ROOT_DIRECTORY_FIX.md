# Исправление ошибки Root Directory на Railway

## Проблема

Ошибка при деплое:
```
Build Failed: build daemon returned an error < failed to solve: failed to compute cache key: failed to calculate checksum of ref ... "/package.json": not found >
```

## Причина

Когда в Railway установлен **Root Directory** (например, `admin-panel` или `backend`), build context уже находится в этой директории. Поэтому:

1. **dockerfilePath** в `railway.json` должен быть `Dockerfile`, а не `admin-panel/Dockerfile`
2. Dockerfile должен копировать файлы из текущей директории, а не из поддиректории

## Решение

### Для Frontend (admin-panel)

1. **В Railway Dashboard:**
   - Settings → Build
   - **Root Directory:** `admin-panel`
   - **Dockerfile Path:** `Dockerfile` (автоматически, если railway.json правильный)

2. **railway.json** должен содержать:
   ```json
   {
     "build": {
       "dockerfilePath": "Dockerfile"
     }
   }
   ```

### Для Backend

1. **В Railway Dashboard:**
   - Settings → Build
   - **Root Directory:** `backend`
   - **Dockerfile Path:** `Dockerfile`

2. **railway.json** должен содержать:
   ```json
   {
     "build": {
       "dockerfilePath": "Dockerfile"
     }
   }
   ```

## Важно

- Когда Root Directory установлен, build context уже находится в этой директории
- Все пути в Dockerfile должны быть относительными к Root Directory
- `dockerfilePath` в railway.json должен быть `Dockerfile`, а не `admin-panel/Dockerfile` или `backend/Dockerfile`

## Проверка

После исправления:
1. Перезапустите деплой в Railway
2. Проверьте логи - не должно быть ошибок о не найденных файлах
3. Build должен успешно завершиться

---

**Изменения уже отправлены в GitHub!**




