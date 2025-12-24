# Руководство по миграции на REG.RU VPS

Подробная инструкция по переносу проекта RAG Bot с Railway на VPS REG.RU.

## Содержание

1. [Подготовка VPS](#1-подготовка-vps)
2. [Установка Docker](#2-установка-docker)
3. [Настройка домена](#3-настройка-домена)
4. [Подготовка проекта](#4-подготовка-проекта)
5. [Настройка Nginx](#5-настройка-nginx)
6. [Настройка SSL](#6-настройка-ssl)
7. [Миграция данных](#7-миграция-данных)
8. [Деплой приложения](#8-деплой-приложения)
9. [Настройка автозапуска](#9-настройка-автозапуска)
10. [Настройка бэкапов](#10-настройка-бэкапов)
11. [Тестирование](#11-тестирование)

---

## 1. Подготовка VPS

### 1.1 Заказ VPS на REG.RU

1. Войдите в панель управления REG.RU
2. Перейдите в раздел "VPS"
3. Выберите тариф:
   - **Минимум**: 2 CPU, 4GB RAM, 40GB SSD
   - **Рекомендуется**: 4 CPU, 8GB RAM, 80GB SSD
4. Выберите операционную систему: **Ubuntu 22.04 LTS**
5. Создайте VPS и дождитесь активации

### 1.2 Подключение к серверу

```bash
ssh root@your-server-ip
```

### 1.3 Первоначальная настройка

```bash
# Обновить систему
apt update && apt upgrade -y

# Установить необходимые пакеты
apt install -y curl wget git ufw

# Настроить firewall
ufw allow 22/tcp    # SSH
ufw allow 80/tcp    # HTTP
ufw allow 443/tcp  # HTTPS
ufw enable

# Создать пользователя для деплоя (опционально)
adduser deploy
usermod -aG sudo deploy
```

---

## 2. Установка Docker

### 2.1 Установка Docker Engine

```bash
# Установить Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sh get-docker.sh

# Добавить текущего пользователя в группу docker
usermod -aG docker $USER

# Проверить установку
docker --version
```

### 2.2 Установка Docker Compose

```bash
# Установить Docker Compose plugin
apt install docker-compose-plugin -y

# Проверить установку
docker compose version
```

---

## 3. Настройка домена

### 3.1 Регистрация домена (если нужно)

1. Зарегистрируйте домен на REG.RU
2. Дождитесь активации домена

### 3.2 Настройка DNS записей

В панели управления REG.RU:

1. Перейдите в управление доменом
2. Откройте раздел "DNS"
3. Добавьте A-записи:
   - `api` → IP вашего VPS
   - `admin` → IP вашего VPS

Пример:
```
api.yourdomain.ru    A    123.45.67.89
admin.yourdomain.ru  A    123.45.67.89
```

4. Дождитесь распространения DNS (обычно 5-30 минут)

---

## 4. Подготовка проекта

### 4.1 Клонирование репозитория

**Вариант 1: Используя Personal Access Token (рекомендуется)**

```bash
# Создать директорию для проекта
mkdir -p /opt/ragbot
cd /opt/ragbot

# Если директория не пуста, очистить её
rm -rf * .[^.]* 2>/dev/null || true

# Клонировать репозиторий
# При запросе username: fuwiak
# При запросе password: вставьте ваш Personal Access Token (не пароль!)
git clone https://github.com/fuwiak/Rag_bot_vladislav.git .

# Переключиться на нужную ветку (если нужно)
git checkout main
```

**Вариант 2: Используя SSH ключ**

```bash
# Сначала настройте SSH ключ на сервере (если еще не настроен)
ssh-keygen -t ed25519 -C "your_email@example.com"
cat ~/.ssh/id_ed25519.pub
# Скопируйте публичный ключ и добавьте в GitHub:
# Settings → SSH and GPG keys → New SSH key

# Создать директорию для проекта
mkdir -p /opt/ragbot
cd /opt/ragbot

# Если директория не пуста, очистить её
rm -rf * .[^.]* 2>/dev/null || true

# Клонировать репозиторий через SSH
git clone git@github.com:fuwiak/Rag_bot_vladislav.git .

# Переключиться на нужную ветку (если нужно)
git checkout main
```

**Как создать Personal Access Token на GitHub:**
1. Войдите в GitHub
2. Перейдите: Settings → Developer settings → Personal access tokens → Tokens (classic)
3. Нажмите "Generate new token (classic)"
4. Выберите scope: `repo` (полный доступ к репозиториям)
5. Нажмите "Generate token"
6. **Важно**: Скопируйте токен сразу, он больше не будет показан!
7. Используйте этот токен как пароль при клонировании

### 4.2 Создание .env файла

```bash
# Создать .env из шаблона
cp .env.example .env

# Отредактировать .env
nano .env
```

Заполните все переменные в `.env`:

```bash
# PostgreSQL
POSTGRES_USER=ragbot
POSTGRES_PASSWORD=your_secure_password_here
POSTGRES_DB=rag_bot

# Qdrant
QDRANT_URL=https://your-cluster-id.us-east4-0.gcp.cloud.qdrant.io
QDRANT_API_KEY=your_qdrant_api_key_here

# OpenRouter
OPENROUTER_API_KEY=your_openrouter_api_key_here
OPENROUTER_MODEL_PRIMARY=x-ai/grok-4.1-fast
OPENROUTER_MODEL_FALLBACK=openai/gpt-oss-120b:free

# Admin Panel Secrets (сгенерируйте новые)
ADMIN_SECRET_KEY=$(openssl rand -hex 32)
ADMIN_SESSION_SECRET=$(openssl rand -hex 32)

# URLs (замените на ваши домены)
APP_URL=https://admin.yourdomain.ru
BACKEND_URL=https://api.yourdomain.ru
CORS_ORIGINS=https://admin.yourdomain.ru
```

**Важно**: Замените `yourdomain.ru` на ваш реальный домен!

---

## 5. Настройка Nginx

### 5.1 Установка Nginx

```bash
apt install -y nginx certbot python3-certbot-nginx
```

### 5.2 Копирование конфигураций

```bash
# Скопировать конфигурации
cp nginx/api.conf /etc/nginx/sites-available/api
cp nginx/admin.conf /etc/nginx/sites-available/admin

# Отредактировать конфигурации (заменить yourdomain.ru)
nano /etc/nginx/sites-available/api
nano /etc/nginx/sites-available/admin
```

**Важно**: Замените `yourdomain.ru` на ваш реальный домен в обоих файлах!

### 5.3 Активация конфигураций

```bash
# Создать символические ссылки
ln -s /etc/nginx/sites-available/api /etc/nginx/sites-enabled/
ln -s /etc/nginx/sites-available/admin /etc/nginx/sites-enabled/

# Удалить дефолтную конфигурацию (если есть)
rm -f /etc/nginx/sites-enabled/default

# Проверить конфигурацию
nginx -t

# Перезапустить Nginx
systemctl restart nginx
```

---

## 6. Настройка SSL

### 6.1 Получение SSL сертификатов

```bash
# Получить сертификат для API
certbot --nginx -d api.yourdomain.ru

# Получить сертификат для Admin Panel
certbot --nginx -d admin.yourdomain.ru

# Настроить автообновление
certbot renew --dry-run
```

### 6.2 Проверка автообновления

Certbot автоматически настроит cron job для обновления сертификатов. Проверить можно:

```bash
systemctl status certbot.timer
```

---

## 7. Миграция данных

### 7.1 Экспорт данных с Railway

#### Вариант 1: Через Railway CLI

```bash
# Установить Railway CLI
npm i -g @railway/cli

# Войти в Railway
railway login

# Подключиться к проекту
railway link

# Экспортировать базу данных
railway run pg_dump $DATABASE_URL > backup.sql
```

#### Вариант 2: Через Railway Dashboard

1. Откройте Railway Dashboard
2. Перейдите в PostgreSQL сервис
3. Откройте "Data" → "Backup"
4. Скачайте бэкап базы данных

### 7.2 Импорт данных на REG.RU

```bash
# Запустить контейнеры (только PostgreSQL)
docker compose -f docker-compose.prod.yml up -d postgres

# Дождаться готовности PostgreSQL
sleep 10

# Импортировать бэкап
docker compose -f docker-compose.prod.yml exec -T postgres psql -U ragbot -d rag_bot < backup.sql

# Или если бэкап сжат
gunzip -c backup.sql.gz | docker compose -f docker-compose.prod.yml exec -T postgres psql -U ragbot -d rag_bot
```

---

## 8. Деплой приложения

### 8.1 Использование скрипта деплоя

```bash
# Сделать скрипт исполняемым
chmod +x deploy.sh

# Запустить деплой
./deploy.sh
```

### 8.2 Ручной деплой

```bash
# Остановить существующие контейнеры
docker compose -f docker-compose.prod.yml down

# Собрать и запустить контейнеры
docker compose -f docker-compose.prod.yml up -d --build

# Проверить статус
docker compose -f docker-compose.prod.yml ps

# Проверить логи
docker compose -f docker-compose.prod.yml logs -f
```

### 8.3 Создание администратора

```bash
# Выполнить миграции (автоматически при старте)
# Создать администратора
docker compose -f docker-compose.prod.yml exec backend python create_admin.py
```

---

## 9. Настройка автозапуска

### 9.1 Установка systemd сервиса

```bash
# Скопировать сервис
cp systemd/ragbot.service /etc/systemd/system/ragbot.service

# Отредактировать путь (если нужно)
nano /etc/systemd/system/ragbot.service
# Убедитесь, что WorkingDirectory=/opt/ragbot

# Перезагрузить systemd
systemctl daemon-reload

# Включить автозапуск
systemctl enable ragbot.service

# Запустить сервис
systemctl start ragbot.service

# Проверить статус
systemctl status ragbot.service
```

---

## 10. Настройка бэкапов

### 10.1 Создание директории для бэкапов

```bash
mkdir -p /opt/ragbot/backups
```

### 10.2 Настройка cron для автоматических бэкапов

```bash
# Открыть crontab
crontab -e

# Добавить задачу (бэкап каждый день в 2:00)
0 2 * * * cd /opt/ragbot && ./backup.sh >> /var/log/ragbot_backup.log 2>&1
```

### 10.3 Ручной бэкап

```bash
# Сделать скрипт исполняемым
chmod +x backup.sh

# Создать бэкап
./backup.sh
```

### 10.4 Восстановление из бэкапа

```bash
# Сделать скрипт исполняемым
chmod +x restore.sh

# Восстановить из бэкапа
./restore.sh backups/ragbot_backup_20240101_120000.sql.gz
```

---

## 11. Тестирование

### 11.1 Проверка сервисов

```bash
# Проверить Backend
curl https://api.yourdomain.ru/health

# Проверить Frontend
curl https://admin.yourdomain.ru/api/health

# Проверить контейнеры
docker compose -f docker-compose.prod.yml ps
```

### 11.2 Функциональное тестирование

1. Откройте `https://admin.yourdomain.ru` в браузере
2. Войдите в админ-панель
3. Создайте тестовый проект
4. Загрузите тестовый документ
5. Проверьте работу Telegram бота

### 11.3 Проверка безопасности

```bash
# Проверить открытые порты
netstat -tulpn | grep LISTEN

# Должны быть открыты только:
# - 22 (SSH)
# - 80 (HTTP)
# - 443 (HTTPS)
# - 8000 (Backend, только localhost)
# - 3000 (Frontend, только localhost)
```

---

## Полезные команды

### Управление контейнерами

```bash
# Просмотр логов
docker compose -f docker-compose.prod.yml logs -f

# Перезапуск сервиса
docker compose -f docker-compose.prod.yml restart backend

# Остановка всех сервисов
docker compose -f docker-compose.prod.yml down

# Запуск всех сервисов
docker compose -f docker-compose.prod.yml up -d
```

### Обновление приложения

```bash
# Обновить код
git pull

# Пересобрать и перезапустить
./deploy.sh
```

### Мониторинг

```bash
# Использование ресурсов
docker stats

# Логи Nginx
tail -f /var/log/nginx/api_error.log
tail -f /var/log/nginx/admin_error.log
```

---

## Решение проблем

### Backend не запускается

1. Проверьте логи: `docker compose -f docker-compose.prod.yml logs backend`
2. Проверьте переменные окружения в `.env`
3. Проверьте подключение к PostgreSQL: `docker compose -f docker-compose.prod.yml exec postgres psql -U ragbot -d rag_bot`

### Frontend не подключается к Backend

1. Проверьте `NEXT_PUBLIC_BACKEND_URL` в `.env`
2. Проверьте CORS настройки в Backend
3. Проверьте, что Backend доступен: `curl http://localhost:8000/health`

### Проблемы с SSL

1. Проверьте DNS записи: `dig api.yourdomain.ru`
2. Проверьте сертификаты: `certbot certificates`
3. Обновите сертификаты: `certbot renew`

---

## Поддержка

При возникновении проблем:

1. Проверьте логи всех сервисов
2. Убедитесь, что все переменные окружения установлены
3. Проверьте, что все порты правильно настроены
4. Убедитесь, что DNS записи правильно настроены

---

**Готово!** Ваше приложение должно быть доступно по адресам:
- Backend API: `https://api.yourdomain.ru`
- Admin Panel: `https://admin.yourdomain.ru`



