# Конфигурационные файлы

Каждая услуга в Railway должна иметь свой собственный набор конфигурационных файлов.

## Структура конфигурации

```
backend/config/
├── qdrant.yaml      # Конфигурация Qdrant
├── llm.yaml         # Конфигурация LLM
└── config_loader.py # Загрузчик конфигурации
```

## Файлы конфигурации

### config/qdrant.yaml

Конфигурация для подключения к Qdrant:

```yaml
qdrant:
  host: "${QDRANT_HOST}"           # Хост Qdrant
  port: "${QDRANT_PORT:-6333}"       # Порт (по умолчанию 6333)
  url: "${QDRANT_URL}"              # Полный URL (альтернатива host+port)
  api_key: "${QDRANT_API_KEY}"      # API ключ для Qdrant Cloud
  collection_name: "hr2137_bot_knowledge_base"  # Имя коллекции
  target_dimension: 1536            # Размерность векторов
  default_limit: 5                  # Лимит результатов по умолчанию
```

### config/llm.yaml

Конфигурация для LLM и embeddings:

```yaml
llm:
  embeddings:
    api_key: "${OPENROUTER_API_KEY}"
    api_url: "${EMBEDDING_API_URL:-https://openrouter.ai/api/v1/embeddings}"
    model: "${EMBEDDING_MODEL:-qwen/qwen3-embedding-8b}"
    dimension: 1536
```

## Использование переменных окружения

Конфигурационные файлы поддерживают переменные окружения в формате:
- `${VAR_NAME}` - обязательная переменная
- `${VAR_NAME:-default}` - переменная с значением по умолчанию

## Использование в коде

### Загрузка конфигурации

```python
from config.config_loader import load_qdrant_config, load_llm_config, get_qdrant_config_value, get_llm_config_value

# Загрузить всю конфигурацию
qdrant_config = load_qdrant_config()
llm_config = load_llm_config()

# Получить конкретное значение
host = get_qdrant_config_value("host", default="localhost")
api_key = get_llm_config_value("embeddings.api_key", default="")
```

## Fallback на settings

Если конфигурационный файл не найден или значение отсутствует, код автоматически использует значения из `app.core.config.settings` для обратной совместимости.
