# Исправление ошибок клонирования репозитория

## Проблемы

### Проблема 1: Ошибка аутентификации
```
remote: Invalid username or token. Password authentication is not supported for Git operations.
fatal: Authentication failed
```
GitHub больше не поддерживает аутентификацию по паролю. Нужно использовать Personal Access Token или SSH ключ.

### Проблема 2: Директория не пуста
```
fatal: destination path '.' already exists and is not an empty directory.
```
Директория уже существует и содержит файлы. Нужно очистить её перед клонированием.

## Решения

### Быстрое решение для ошибки "directory not empty"

Если вы получили ошибку о том, что директория не пуста:

```bash
cd /opt/ragbot
# Очистить директорию
rm -rf * .[^.]* 2>/dev/null || true
# Теперь можно клонировать
git clone https://github.com/fuwiak/Rag_bot_vladislav.git .
```

### Решение для ошибки аутентификации

### Вариант 1: Использовать Personal Access Token (быстро)

1. **Создайте токен на GitHub:**
   - Откройте: https://github.com/settings/tokens
   - Нажмите "Generate new token (classic)"
   - Выберите scope: `repo`
   - Нажмите "Generate token"
   - **Скопируйте токен** (он больше не будет показан!)

2. **На сервере выполните:**

```bash
cd /opt/ragbot

# Очистить директорию если она не пуста
rm -rf * .[^.]* 2>/dev/null || true

# Клонировать с токеном
git clone https://github.com/fuwiak/Rag_bot_vladislav.git .

# При запросе:
# Username: fuwiak
# Password: вставьте ваш Personal Access Token (не пароль от GitHub!)
```

### Вариант 2: Использовать SSH ключ (рекомендуется для постоянного использования)

1. **На сервере создайте SSH ключ:**

```bash
ssh-keygen -t ed25519 -C "your_email@example.com"
# Нажмите Enter для всех вопросов (или укажите пароль)

# Показать публичный ключ
cat ~/.ssh/id_ed25519.pub
```

2. **Добавьте ключ в GitHub:**
   - Скопируйте вывод команды выше
   - Откройте: https://github.com/settings/keys
   - Нажмите "New SSH key"
   - Вставьте ключ и сохраните

3. **Клонируйте через SSH:**

```bash
cd /opt/ragbot

# Очистить директорию если она не пуста
rm -rf * .[^.]* 2>/dev/null || true

git clone git@github.com:fuwiak/Rag_bot_vladislav.git .
```

### Вариант 3: Использовать токен прямо в URL (для одноразового клонирования)

```bash
cd /opt/ragbot

# Очистить директорию если она не пуста
rm -rf * .[^.]* 2>/dev/null || true

# Замените YOUR_TOKEN на ваш Personal Access Token
git clone https://YOUR_TOKEN@github.com/fuwiak/Rag_bot_vladislav.git .
```

**⚠️ Внимание:** Этот метод оставляет токен в истории команд. Используйте только для быстрого клонирования, затем удалите из истории.

## Проверка

После успешного клонирования:

```bash
cd /opt/ragbot
ls -la
# Должны увидеть файлы проекта: docker-compose.prod.yml, deploy.sh и т.д.
```

## Продолжение установки

После успешного клонирования продолжайте с шага 3 в `REG_RU_QUICKSTART.md`:

```bash
# Создать .env файл
cp env.example.regru .env
nano .env
```

