# Mock API для Frontend

Этот модуль предоставляет Mock API сервер для работы frontend без backend. Используется для демонстрации UI и независимого деплоя frontend на Railway.

## Как это работает

Когда `NEXT_PUBLIC_USE_MOCK_API=true`, все API запросы перенаправляются на локальные Next.js API Routes (`/api/mock/*`), которые возвращают тестовые данные.

## Структура

```
app/api/mock/
├── data.ts                    # Тестовые данные
├── auth/
│   └── login/route.ts         # Mock авторизации
├── projects/
│   ├── route.ts              # Список проектов
│   └── [id]/route.ts         # Детали проекта
├── documents/
│   ├── [projectId]/route.ts  # Документы проекта
│   └── [id]/route.ts         # Удаление документа
├── users/
│   ├── project/[projectId]/route.ts  # Пользователи проекта
│   ├── [id]/route.ts         # Обновление/удаление пользователя
│   └── [id]/status/route.ts  # Изменение статуса
├── bots/
│   ├── info/route.ts         # Информация о ботах
│   └── [projectId]/verify/route.ts  # Проверка токена
└── models/
    ├── available/route.ts    # Доступные модели
    └── global-settings/route.ts  # Глобальные настройки
```

## Использование

### Включение моков

Установите переменную окружения:
```bash
NEXT_PUBLIC_USE_MOCK_API=true
```

### Использование в компонентах

Используйте helper функцию вместо прямого `process.env.NEXT_PUBLIC_BACKEND_URL`:

```typescript
import { getApiUrl } from '../lib/api-helpers'

// Вместо:
// const backendUrl = process.env.NEXT_PUBLIC_BACKEND_URL || 'https://ragbotvladislav-backend.up.railway.app'
// fetch(`${backendUrl}/api/projects`)

// Используйте:
const response = await fetch(getApiUrl('/api/projects'))
```

## Тестовые данные

Mock API предоставляет:

- **3 тестовых проекта** с разными настройками
- **Документы** для каждого проекта
- **Пользователи** для каждого проекта
- **Информация о ботах** для проектов с токенами
- **Список моделей** LLM

## Особенности

- Все операции (GET, POST, PUT, DELETE, PATCH) поддерживаются
- Данные хранятся в памяти (не сохраняются после перезапуска)
- Авторизация всегда успешна в режиме моков
- Формат ответов идентичен реальному API

## Переключение на реальный API

Чтобы переключиться на реальный backend:

1. Установите `NEXT_PUBLIC_USE_MOCK_API=false`
2. Установите `NEXT_PUBLIC_BACKEND_URL=https://your-backend.railway.app`
3. Перезапустите приложение

