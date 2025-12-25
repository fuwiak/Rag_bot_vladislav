# Создание администратора на Railway - простой способ

## Проблема

Railway CLI недоступен в контейнере. Используйте Railway Dashboard.

---

## Способ 1: Через Railway Dashboard (рекомендуется)

### Шаг 1: Откройте Backend Service

1. Railway Dashboard → ваш проект
2. Откройте **Backend Service**

### Шаг 2: Запустите команду

1. Перейдите в **Settings** → **Deployments**
2. Найдите последний deployment или нажмите **"New Deployment"**
3. В разделе **"Run Command"** или **"Execute Command"** введите:
   ```
   python create_admin_auto.py
   ```
4. Нажмите **"Run"** или **"Execute"**

### Шаг 3: Проверьте вывод

В логах должно появиться:
```
✅ Администратор создан успешно!
   Username: admin
   Password: admin
```

---

## Способ 2: Через Shell в контейнере

Если Railway Dashboard не поддерживает Run Command:

1. Railway Dashboard → **Backend Service** → **Settings** → **Deployments**
2. Найдите последний deployment
3. Откройте **"Shell"** или **"Terminal"** (если доступно)
4. Выполните:
   ```bash
   python create_admin_auto.py
   ```

---

## Способ 3: Создать через API endpoint (если есть)

Если в коде есть endpoint для создания администратора, можно использовать его через curl или Postman.

---

## Проверка

После создания администратора:

1. Откройте: `https://ragbotvladislav-production.up.railway.app/login`
2. Username: `admin`
3. Password: `admin`
4. Попробуйте войти

---

## Если команда не выполняется

### Вариант 1: Проверьте путь к скрипту

Попробуйте полный путь:
```
cd /app && python create_admin_auto.py
```

### Вариант 2: Проверьте рабочую директорию

В Railway контейнере рабочая директория обычно `/app`. Попробуйте:
```
python /app/create_admin_auto.py
```

### Вариант 3: Используйте Python напрямую

```
python -c "import asyncio; from create_admin_auto import create_admin_auto; asyncio.run(create_admin_auto())"
```

---

## Альтернатива: Создать администратора через код

Если ничего не работает, можно временно добавить endpoint для создания администратора в API.

---

**Самый простой способ - через Railway Dashboard → Backend Service → Deployments → Run Command!**









