# Telegram RAG Bot System

Система для создания Telegram-ботов с RAG (Retrieval-Augmented Generation) для работы с документами отделов компании.

## Описание

Система позволяет сотрудникам разных отделов компании обращаться к текстовым документам своего отдела через Telegram-бота и получать ответы строго на основании загруженных документов (справочники, инструкции, регламенты и т.д.).

## Технологический стек

- **Backend**: Python 3.11+, FastAPI, SQLAlchemy, Pydantic
- **Telegram**: aiogram 3.x
- **Database**: PostgreSQL (для метаданных)
- **Vector DB**: Qdrant Cloud (для векторного поиска)
- **LLM**: OpenRouter API (x-ai/grok-4.1-fast с fallback на openai/gpt-oss-120b:free)
- **Admin Panel**: Next.js 14, React, Tailwind CSS

## Быстрый старт

См. **[QUICKSTART.md](QUICKSTART.md)** для подробной инструкции по локальному запуску.

### Краткая инструкция (Docker Compose)

1. Скопируйте `.env.example` в `.env` и заполните переменные окружения
2. Запустите:
   ```bash
   docker-compose -f docker-compose.local.yml up
   ```
3. Создайте администратора:
   ```bash
   docker-compose -f docker-compose.local.yml exec backend python create_admin.py
   ```
4. Откройте http://localhost:3000 для доступа к админ-панели

## Структура проекта

```
/
  backend/          # FastAPI backend
  admin-panel/      # Next.js admin panel
  docs/             # Документация
```

## Документация

- [SETUP.md](docs/SETUP.md) - подробная инструкция по установке
- [DEPLOYMENT.md](docs/DEPLOYMENT.md) - руководство по развертыванию
- [RAILWAY.md](docs/RAILWAY.md) - деплой на Railway
- [ADMIN_GUIDE.md](docs/ADMIN_GUIDE.md) - руководство администратора
- [API.md](docs/API.md) - описание API endpoints
- [TESTING.md](docs/TESTING.md) - инструкция по тестированию

## Разработка

См. [TESTING.md](docs/TESTING.md) для инструкций по запуску тестов.

## Лицензия

[Укажите лицензию]

## Контакты

[Укажите контакты]

