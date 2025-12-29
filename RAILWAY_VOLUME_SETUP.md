# Создание и подключение Volume на Railway

## Проблема

Volume не создан, поэтому SQLite база данных не может сохраняться между перезапусками.

---

## Шаг 1: Создание Volume

1. Railway Dashboard → ваш проект
2. Нажмите **"New"** → **"Volume"**
3. Настройте:
   - **Name:** `sqlite-data` (или любое другое название)
   - **Size:** минимум 1 GB (можно больше)
4. Нажмите **"Add Volume"**

---

## Шаг 2: Подключение Volume к Backend Service

1. Railway Dashboard → **Backend Service**
2. Перейдите в **Settings** → **Volumes**
3. Нажмите **"Add Volume"**
4. Выберите созданный volume (`sqlite-data`)
5. **Mount Path:** `/data`
6. Нажмите **"Add"**

---

## Шаг 3: Проверка переменных

Убедитесь, что в Backend Service → Settings → Variables установлено:

```bash
DATABASE_URL=sqlite+aiosqlite:////data/rag_bot.db
```

**Важно:** 4 слеша `////` перед `/data`

---

## Шаг 4: Перезапуск Backend

После подключения volume:

1. Railway Dashboard → **Backend Service** → **Settings** → **Deployments**
2. Нажмите **"Redeploy"** или дождитесь автоматического перезапуска
3. Проверьте логи - не должно быть ошибок о базе данных

---

## Шаг 5: Создание администратора

После перезапуска создайте администратора:

```bash
railway run --service backend python create_admin_auto.py
```

Или через Railway Dashboard:
- Backend Service → Settings → Deployments → Run Command
- Команда: `python create_admin_auto.py`

---

## Проверка

1. **Логи Backend:**
   - Не должно быть ошибок о базе данных
   - Должно быть: `Application startup complete`

2. **Health endpoint:**
   ```
   https://ragbotvladislav-production-back.up.railway.app/health
   ```
   Должен вернуться: `{"status":"healthy"}`

3. **Попробуйте войти:**
   - Откройте: `https://ragbotvladislav-production.up.railway.app/login`
   - Username: `admin`
   - Password: `admin`

---

## Важно

- Volume должен быть подключен **ПЕРЕД** созданием администратора
- База данных будет создана автоматически при первом запуске
- Все данные будут сохраняться в volume между перезапусками

---

**После создания volume и подключения его к backend, создайте администратора и вход должен работать!**











