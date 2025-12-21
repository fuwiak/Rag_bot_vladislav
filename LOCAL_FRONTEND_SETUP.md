# Локальный запуск Frontend

## Требования

- Node.js 18+ 
- npm или yarn

## Шаг 1: Установка зависимостей

```bash
cd admin-panel
npm install
```

## Шаг 2: Настройка переменных окружения (опционально)

Создайте файл `.env.local` в директории `admin-panel/`:

```bash
NEXT_PUBLIC_BACKEND_URL=http://localhost:8000
```

**Примечание:** Если не создавать `.env.local`, frontend будет использовать значение по умолчанию `http://localhost:8000`.

## Шаг 3: Запуск dev сервера

```bash
npm run dev
```

Frontend будет доступен по адресу: **http://localhost:3000**

## Шаг 4: Проверка работы

1. Откройте браузер: http://localhost:3000
2. Убедитесь, что backend запущен на http://localhost:8000
3. Войдите в админ-панель (создайте администратора если нужно)

## Проблемы и решения

### Frontend не подключается к backend

- Проверьте, что backend запущен: `curl http://localhost:8000/health`
- Проверьте переменную `NEXT_PUBLIC_BACKEND_URL` в `.env.local`
- Убедитесь, что нет CORS ошибок в консоли браузера

### Ошибки при установке зависимостей

```bash
# Очистите кэш и переустановите
rm -rf node_modules package-lock.json
npm install
```

### Порт 3000 занят

Измените порт:
```bash
PORT=3001 npm run dev
```

Или убейте процесс на порту 3000:
```bash
# macOS/Linux
lsof -ti:3000 | xargs kill -9
```

## Production сборка

Для production сборки:

```bash
npm run build
npm start
```

Это создаст оптимизированную сборку и запустит production сервер.

