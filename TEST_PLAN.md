# План тестирования системы RAG Bot

## Анализ соответствия ТЗ

### ✅ Реализованные функции

1. **Админ-панель**
   - ✅ Авторизация администратора (логин/пароль)
   - ✅ Создание, редактирование, удаление проектов
   - ✅ Загрузка документов (.txt, .docx, .pdf)
   - ✅ Управление пользователями (список, блокировка)
   - ✅ Настройка промпта для каждого проекта
   - ✅ Настройка максимального размера ответа
   - ✅ Привязка Telegram-бота к проекту

2. **Telegram-бот**
   - ✅ Приветственное сообщение и запрос пароля
   - ✅ Проверка пароля
   - ✅ Запрос номера телефона (через Telegram кнопку)
   - ✅ Команды /start, /help
   - ✅ Обработка свободнотекстовых вопросов
   - ✅ Генерация ответов на основе документов

3. **Модуль работы с документами**
   - ✅ Парсинг .txt, .docx, .pdf
   - ✅ Разбивка на чанки
   - ✅ Создание эмбеддингов
   - ✅ Векторный поиск в Qdrant
   - ✅ Изоляция документов по проектам

4. **RAG и LLM**
   - ✅ Поиск релевантных фрагментов
   - ✅ Генерация ответов на основе документов
   - ✅ Ограничение "галлюцинаций" через промпт
   - ✅ Сообщение при отсутствии информации
   - ✅ Учет контекста диалога

5. **Масштабирование**
   - ✅ Поддержка множественных проектов
   - ✅ Поддержка множественных ботов
   - ✅ Автоматический запуск ботов

6. **Безопасность**
   - ✅ Изоляция данных между проектами
   - ✅ Авторизация по паролю
   - ✅ Управление доступом пользователей

---

## План тестирования

### 1. Unit тесты (Модульное тестирование)

#### 1.1. Тесты парсинга документов
```python
# backend/tests/test_document_parser.py
- test_parse_txt_file()
- test_parse_docx_file()
- test_parse_pdf_file()
- test_parse_invalid_file()
- test_parse_empty_file()
- test_parse_large_file()
- test_parse_special_characters()
```

#### 1.2. Тесты разбивки на чанки
```python
# backend/tests/test_chunker.py
- test_chunk_text_small()
- test_chunk_text_large()
- test_chunk_text_with_overlap()
- test_chunk_empty_text()
- test_chunk_unicode_text()
```

#### 1.3. Тесты создания эмбеддингов
```python
# backend/tests/test_embedding_service.py
- test_create_embedding()
- test_create_embedding_empty_text()
- test_create_embedding_long_text()
- test_embedding_dimension()
```

#### 1.4. Тесты векторного поиска
```python
# backend/tests/test_vector_store.py
- test_store_vector()
- test_search_similar()
- test_search_with_threshold()
- test_delete_vector()
- test_collection_isolation()
```

#### 1.5. Тесты промптов
```python
# backend/tests/test_prompt_builder.py
- test_build_prompt_with_chunks()
- test_build_prompt_with_history()
- test_build_prompt_with_max_length()
- test_prompt_template_substitution()
```

#### 1.6. Тесты RAG сервиса
```python
# backend/tests/test_rag_service.py
- test_generate_answer_with_chunks()
- test_generate_answer_no_chunks()
- test_generate_answer_with_history()
- test_respect_max_length()
- test_project_isolation()
```

#### 1.7. Тесты сервисов
```python
# backend/tests/test_project_service.py
- test_create_project()
- test_get_project()
- test_update_project()
- test_delete_project()
- test_get_all_projects()

# backend/tests/test_user_service.py
- test_create_user()
- test_get_user_by_phone()
- test_block_user()
- test_project_isolation()

# backend/tests/test_document_service.py
- test_upload_document()
- test_get_project_documents()
- test_delete_document()
```

---

### 2. Integration тесты (Интеграционное тестирование)

#### 2.1. Тесты API endpoints
```python
# backend/tests/test_api_projects.py
- test_create_project()
- test_get_projects_list()
- test_get_project_by_id()
- test_update_project()
- test_delete_project()
- test_project_with_bot_token()
- test_project_prompt_template()

# backend/tests/test_api_documents.py
- test_upload_txt_document()
- test_upload_docx_document()
- test_upload_pdf_document()
- test_upload_multiple_documents()
- test_get_project_documents()
- test_delete_document()
- test_document_processing_async()

# backend/tests/test_api_users.py
- test_get_project_users()
- test_create_user()
- test_block_user()
- test_unblock_user()
- test_user_isolation_by_project()

# backend/tests/test_api_bots.py
- test_get_bots_info()
- test_verify_bot_token()
- test_start_bot()
- test_stop_bot()
```

#### 2.2. Тесты авторизации
```python
# backend/tests/test_auth.py
- test_admin_login()
- test_admin_login_wrong_password()
- test_admin_logout()
- test_token_validation()
```

#### 2.3. Тесты работы с базой данных
```python
# backend/tests/test_database.py
- test_database_connection()
- test_migrations()
- test_project_relationships()
- test_user_relationships()
- test_document_relationships()
```

#### 2.4. Тесты Celery задач
```python
# backend/tests/test_celery_tasks.py
- test_process_document_task()
- test_task_with_invalid_file()
- test_task_with_large_file()
- test_task_error_handling()
```

---

### 3. E2E тесты (End-to-End тестирование)

#### 3.1. Сценарий: Создание нового проекта
```python
# backend/tests/e2e/test_create_project_flow.py
def test_create_project_full_flow():
    """
    1. Администратор логинится в админ-панель
    2. Создает новый проект с настройками:
       - Название, описание
       - Пароль доступа
       - Промпт шаблон
       - Максимальная длина ответа
    3. Загружает документы (.txt, .docx, .pdf)
    4. Привязывает Telegram-бота
    5. Проверяет, что проект создан и бот запущен
    """
```

#### 3.2. Сценарий: Авторизация пользователя в боте
```python
# backend/tests/e2e/test_bot_auth_flow.py
def test_user_authentication_flow():
    """
    1. Пользователь отправляет /start боту
    2. Бот запрашивает пароль
    3. Пользователь вводит правильный пароль
    4. Бот запрашивает номер телефона
    5. Пользователь отправляет контакт
    6. Проверяет, что пользователь создан в БД
    7. Проверяет, что пользователь авторизован
    """
```

#### 3.3. Сценарий: Задание вопроса и получение ответа
```python
# backend/tests/e2e/test_question_answer_flow.py
def test_question_answer_flow():
    """
    1. Авторизованный пользователь задает вопрос
    2. Система ищет релевантные фрагменты в документах
    3. Генерирует ответ на основе найденных фрагментов
    4. Проверяет, что ответ соответствует документам
    5. Проверяет, что ответ не превышает max_length
    6. Проверяет время ответа (5-7 секунд)
    """
```

#### 3.4. Сценарий: Ответ при отсутствии информации
```python
# backend/tests/e2e/test_no_information_response.py
def test_no_information_response():
    """
    1. Пользователь задает вопрос, на который нет ответа в документах
    2. Система должна вернуть сообщение:
       "В загруженных документах нет информации по этому вопросу"
    3. Проверяет, что не было "галлюцинаций"
    """
```

#### 3.5. Сценарий: Контекст диалога
```python
# backend/tests/e2e/test_conversation_context.py
def test_conversation_context():
    """
    1. Пользователь задает вопрос
    2. Получает ответ
    3. Задает уточняющий вопрос
    4. Проверяет, что система учитывает предыдущий контекст
    """
```

#### 3.6. Сценарий: Управление пользователями
```python
# backend/tests/e2e/test_user_management.py
def test_user_management():
    """
    1. Администратор видит список пользователей проекта
    2. Блокирует пользователя
    3. Заблокированный пользователь не может задавать вопросы
    4. Администратор разблокирует пользователя
    5. Пользователь снова может задавать вопросы
    """
```

#### 3.7. Сценарий: Множественные проекты
```python
# backend/tests/e2e/test_multiple_projects.py
def test_multiple_projects_isolation():
    """
    1. Создается проект A с документами A
    2. Создается проект B с документами B
    3. Пользователь проекта A задает вопрос
    4. Проверяет, что ответ основан только на документах A
    5. Пользователь проекта B задает вопрос
    6. Проверяет, что ответ основан только на документах B
    """
```

---

### 4. Performance тесты (Тестирование производительности)

#### 4.1. Тесты времени ответа
```python
# backend/tests/performance/test_response_time.py
- test_answer_generation_time_under_7s()
- test_answer_generation_time_large_documents()
- test_concurrent_requests()
- test_document_processing_time()
```

#### 4.2. Тесты нагрузки
```python
# backend/tests/performance/test_load.py
- test_multiple_users_concurrent()
- test_multiple_bots_concurrent()
- test_large_document_upload()
- test_memory_usage_document_processing()
```

#### 4.3. Тесты масштабирования
```python
# backend/tests/performance/test_scalability.py
- test_20_projects_simultaneous()
- test_30_projects_simultaneous()
- test_multiple_documents_per_project()
- test_large_number_of_users()
```

---

### 5. Security тесты (Тестирование безопасности)

#### 5.1. Тесты авторизации
```python
# backend/tests/security/test_authentication.py
- test_wrong_password_rejected()
- test_unauthorized_access_blocked()
- test_token_expiration()
- test_password_validation()
```

#### 5.2. Тесты изоляции данных
```python
# backend/tests/security/test_data_isolation.py
- test_project_data_isolation()
- test_user_cannot_access_other_project()
- test_document_isolation()
- test_vector_search_isolation()
```

#### 5.3. Тесты валидации входных данных
```python
# backend/tests/security/test_input_validation.py
- test_sql_injection_prevention()
- test_xss_prevention()
- test_file_upload_validation()
- test_path_traversal_prevention()
```

---

### 6. UI/UX тесты (Тестирование интерфейса)

#### 6.1. Тесты админ-панели
```python
# admin-panel/tests/e2e/test_admin_panel.py
- test_login_page()
- test_dashboard_loads()
- test_create_project_form()
- test_upload_documents()
- test_user_management()
- test_bot_configuration()
```

#### 6.2. Тесты кэширования
```python
# admin-panel/tests/test_cache.py
- test_cache_projects_list()
- test_cache_project_details()
- test_cache_documents()
- test_cache_users()
- test_cache_expiration()
```

---

### 7. Тесты Telegram-бота

#### 7.1. Тесты команд бота
```python
# backend/tests/bot/test_bot_commands.py
- test_start_command()
- test_help_command()
- test_start_without_auth()
- test_start_with_auth()
```

#### 7.2. Тесты авторизации в боте
```python
# backend/tests/bot/test_bot_auth.py
- test_password_verification()
- test_phone_collection()
- test_user_creation()
- test_blocked_user_access()
```

#### 7.3. Тесты обработки вопросов
```python
# backend/tests/bot/test_bot_questions.py
- test_question_processing()
- test_answer_generation()
- test_error_handling()
- test_timeout_handling()
```

#### 7.4. Тесты множественных ботов
```python
# backend/tests/bot/test_bot_factory.py
- test_create_bot()
- test_start_all_bots()
- test_bot_with_multiple_projects()
- test_bot_stop()
```

---

### 8. Тесты обработки документов

#### 8.1. Тесты загрузки документов
```python
# backend/tests/test_document_upload.py
- test_upload_txt()
- test_upload_docx()
- test_upload_pdf()
- test_upload_multiple_files()
- test_upload_large_file()
- test_upload_invalid_format()
```

#### 8.2. Тесты обработки документов
```python
# backend/tests/test_document_processing.py
- test_document_parsing()
- test_chunking()
- test_embedding_creation()
- test_vector_storage()
- test_celery_task_processing()
```

---

### 9. Тесты надежности (Reliability)

#### 9.1. Тесты отказоустойчивости
```python
# backend/tests/reliability/test_resilience.py
- test_database_connection_loss()
- test_qdrant_connection_loss()
- test_llm_api_failure()
- test_graceful_degradation()
- test_error_recovery()
```

#### 9.2. Тесты восстановления
```python
# backend/tests/reliability/test_recovery.py
- test_service_restart()
- test_data_persistence()
- test_backup_restore()
```

---

### 10. Тесты валидации данных

#### 10.1. Тесты валидации проектов
```python
# backend/tests/validation/test_project_validation.py
- test_project_name_required()
- test_password_required()
- test_prompt_template_required()
- test_max_length_validation()
- test_bot_token_validation()
```

#### 10.2. Тесты валидации пользователей
```python
# backend/tests/validation/test_user_validation.py
- test_phone_required()
- test_phone_format()
- test_unique_phone_per_project()
```

---

## Чек-лист соответствия ТЗ

### Раздел 1: Цель проекта
- [x] Упрощение доступа к документам
- [x] Снижение нагрузки на руководителей
- [x] Защищенный доступ к документам

### Раздел 2: Общая концепция
- [x] Несколько отделов/проектов
- [x] Отдельный бот для каждого отдела
- [x] Авторизация по паролю и телефону
- [x] Ответы только на основе документов
- [x] Сообщение при отсутствии информации

### Раздел 3: Роли
- [x] Администраторы (создание проектов, управление)
- [x] Сотрудники (авторизация, вопросы)

### Раздел 4: Основные сценарии
- [x] Настройка нового отдела/проекта
- [x] Настройка Telegram-бота
- [x] Управление доступом сотрудников
- [x] Задание вопроса и получение ответа
- [x] Масштабирование (20-30 проектов)

### Раздел 5: Функциональные требования
- [x] Админ-панель (все функции)
- [x] Telegram-бот (все функции)
- [x] Модуль работы с документами и нейросетью

### Раздел 6: Нефункциональные требования
- [x] Безопасность (изоляция, авторизация)
- [x] Надежность (сохранение данных, обработка ошибок)
- [x] Производительность (5-7 секунд ответ, Celery для обработки)

---

## Рекомендации по тестированию

### Приоритет 1 (Критичные тесты)
1. E2E тесты основных сценариев
2. Тесты изоляции данных между проектами
3. Тесты обработки документов
4. Тесты генерации ответов

### Приоритет 2 (Важные тесты)
1. Performance тесты
2. Security тесты
3. Тесты множественных ботов
4. Тесты управления пользователями

### Приоритет 3 (Дополнительные тесты)
1. UI/UX тесты
2. Тесты кэширования
3. Тесты надежности
4. Тесты валидации

---

## Инструменты для тестирования

### Backend
- `pytest` - основной фреймворк
- `pytest-asyncio` - для async тестов
- `httpx` - для тестирования API
- `aiogram-test` - для тестирования ботов (если доступен)

### Frontend
- `Jest` - для unit тестов
- `React Testing Library` - для компонентов
- `Playwright` или `Cypress` - для E2E тестов

### Performance
- `locust` - для нагрузочного тестирования
- `pytest-benchmark` - для бенчмарков

---

## Метрики успешности тестов

1. **Покрытие кода**: минимум 80%
2. **Время ответа**: 95% запросов < 7 секунд
3. **Успешность E2E**: 100% критичных сценариев
4. **Изоляция данных**: 100% тестов проходят
5. **Безопасность**: все security тесты проходят

