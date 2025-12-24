# Объяснение портов на Railway - Backend и Frontend

## Важно: порты независимы!

**Backend и Frontend - это разные сервисы с разными портами!** Они не связаны между собой.

## Как это работает

### Backend Service
- Railway автоматически устанавливает `PORT` для backend (может быть 8000, 8080, или другой)
- Backend читает `process.env.PORT` и запускается на этом порту
- Внешний URL: `https://ragbotvladislav-production-back.up.railway.app`

### Frontend Service
- Railway автоматически устанавливает `PORT` для frontend (может быть 3000, 8080, или другой)
- Next.js читает `process.env.PORT` и запускается на этом порту
- Внешний URL: `https://ragbotvladislav-production.up.railway.app`

## Нужно ли что-то настраивать?

**НЕТ!** Railway автоматически управляет портами для каждого сервиса.

### Backend Service Variables

```bash
DATABASE_URL=sqlite+aiosqlite:////data/rag_bot.db
ADMIN_SECRET_KEY=ваш_ключ
ADMIN_SESSION_SECRET=ваш_ключ
BACKEND_URL=https://ragbotvladislav-production-back.up.railway.app
CORS_ORIGINS=https://ragbotvladislav-production.up.railway.app
# PORT не нужен - Railway установит автоматически!
```

### Frontend Service Variables

```bash
NEXT_PUBLIC_BACKEND_URL=https://ragbotvladislav-production-back.up.railway.app
NODE_ENV=production
# PORT не нужен - Railway установит автоматически!
```

## Почему это работает?

1. **Каждый сервис - отдельный контейнер:**
   - Backend контейнер имеет свой PORT (например, 8000)
   - Frontend контейнер имеет свой PORT (например, 8080)
   - Они независимы

2. **Railway проксирует трафик:**
   - Внешний URL → Railway прокси → внутренний порт контейнера
   - Пользователь не видит внутренние порты
   - Все работает через внешние URL

3. **Связь между сервисами:**
   - Frontend обращается к Backend через **внешний URL**
   - Не через внутренние порты!
   - `NEXT_PUBLIC_BACKEND_URL=https://ragbotvladislav-production-back.up.railway.app`

## Пример

```
Пользователь → https://ragbotvladislav-production.up.railway.app
              ↓
         Railway прокси
              ↓
    Frontend контейнер (порт 8080 внутри)

Frontend → https://ragbotvladislav-production-back.up.railway.app
              ↓
         Railway прокси
              ↓
    Backend контейнер (порт 8000 внутри)
```

## Важно

- ❌ **НЕ нужно** устанавливать PORT в переменных окружения
- ❌ **НЕ нужно** синхронизировать порты между сервисами
- ✅ Railway автоматически управляет портами
- ✅ Используйте внешние URL для связи между сервисами

## Проверка

1. **Backend:**
   - Логи покажут: `Uvicorn running on http://0.0.0.0:XXXX`
   - XXXX - это порт, который Railway установил автоматически
   - Внешний URL работает независимо от этого порта

2. **Frontend:**
   - Логи покажут: `Local: http://localhost:XXXX`
   - XXXX - это порт, который Railway установил автоматически
   - Внешний URL работает независимо от этого порта

---

**Вывод: Не нужно ничего настраивать! Railway автоматически управляет портами для каждого сервиса независимо.**




