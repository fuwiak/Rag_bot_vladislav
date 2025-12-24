# Быстрый старт - Деплой на REG.RU VPS

Краткая инструкция для быстрого деплоя на REG.RU VPS.

## Предварительные требования

- VPS на REG.RU (минимум 2 CPU, 4GB RAM)
- Домен на REG.RU (или другой регистратор)
- SSH доступ к серверу

## Быстрая установка

### 1. Подготовка сервера

```bash
# Подключиться к серверу
ssh root@your-server-ip

# Обновить систему
apt update && apt upgrade -y

# Установить Git и необходимые пакеты
apt install -y git curl wget

# Установить Docker
curl -fsSL https://get.docker.com -o get-docker.sh && sh get-docker.sh
apt install docker-compose-plugin -y

# Настроить firewall
ufw allow 22/tcp && ufw allow 80/tcp && ufw allow 443/tcp && ufw enable
```

### 2. Клонирование проекта

**Вариант 1: Используя Personal Access Token (рекомендуется)**

```bash
# Создать или очистить директорию
mkdir -p /opt/ragbot
cd /opt/ragbot

# Если директория не пуста, очистить её
rm -rf * .[^.]* 2>/dev/null || true

# Используйте ваш GitHub Personal Access Token вместо пароля
git clone https://github.com/fuwiak/Rag_bot_vladislav.git .
# При запросе username: fuwiak
# При запросе password: вставьте ваш Personal Access Token
```

**Вариант 2: Используя SSH ключ**

```bash
# Сначала настройте SSH ключ на сервере (если еще не настроен)
ssh-keygen -t ed25519 -C "your_email@example.com"
cat ~/.ssh/id_ed25519.pub
# Скопируйте публичный ключ и добавьте в GitHub: Settings → SSH and GPG keys

# Создать или очистить директорию
mkdir -p /opt/ragbot
cd /opt/ragbot

# Если директория не пуста, очистить её
rm -rf * .[^.]* 2>/dev/null || true

git clone git@github.com:fuwiak/Rag_bot_vladislav.git .
```

**Как создать Personal Access Token:**
1. GitHub → Settings → Developer settings → Personal access tokens → Tokens (classic)
2. Generate new token (classic)
3. Выберите scope: `repo` (полный доступ к репозиториям)
4. Скопируйте токен и используйте его как пароль

### 3. Настройка переменных окружения

```bash
# Создать .env файл
cp env.example.regru .env
nano .env
```

**Важно**: Заполните все переменные, особенно:
- `POSTGRES_PASSWORD` - надежный пароль
- `QDRANT_URL` и `QDRANT_API_KEY`
- `OPENROUTER_API_KEY`
- `ADMIN_SECRET_KEY` и `ADMIN_SESSION_SECRET` (сгенерируйте: `openssl rand -hex 32`)
- `APP_URL` и `BACKEND_URL` (ваши домены)
- `CORS_ORIGINS` (URL вашего frontend)

### 4. Настройка DNS

В панели REG.RU добавьте A-записи:
- `api.yourdomain.ru` → IP вашего VPS
- `admin.yourdomain.ru` → IP вашего VPS

### 5. Настройка Nginx

```bash
# Установить Nginx и Certbot
apt install -y nginx certbot python3-certbot-nginx

# Скопировать конфигурации
cp nginx/api.conf /etc/nginx/sites-available/api
cp nginx/admin.conf /etc/nginx/sites-available/admin

# Заменить yourdomain.ru на ваш домен
sed -i 's/yourdomain.ru/ваш-домен.ru/g' /etc/nginx/sites-available/api
sed -i 's/yourdomain.ru/ваш-домен.ru/g' /etc/nginx/sites-available/admin

# Активировать конфигурации
ln -s /etc/nginx/sites-available/api /etc/nginx/sites-enabled/
ln -s /etc/nginx/sites-available/admin /etc/nginx/sites-enabled/
rm -f /etc/nginx/sites-enabled/default
nginx -t && systemctl restart nginx
```

### 6. Получение SSL сертификатов

```bash
# Получить сертификаты (замените yourdomain.ru)
certbot --nginx -d api.yourdomain.ru
certbot --nginx -d admin.yourdomain.ru
```

### 7. Деплой приложения

```bash
# Сделать скрипты исполняемыми
chmod +x deploy.sh backup.sh restore.sh

# Запустить деплой
./deploy.sh
```

### 8. Создание администратора

```bash
docker compose -f docker-compose.prod.yml exec backend python create_admin.py
```

### 9. Настройка автозапуска

```bash
# Установить systemd сервис
cp systemd/ragbot.service /etc/systemd/system/
# Отредактировать путь (если нужно)
nano /etc/systemd/system/ragbot.service
systemctl daemon-reload
systemctl enable ragbot.service
systemctl start ragbot.service
```

### 10. Настройка бэкапов

```bash
# Добавить в crontab
crontab -e
# Добавить строку:
0 2 * * * cd /opt/ragbot && ./backup.sh >> /var/log/ragbot_backup.log 2>&1
```

## Проверка

```bash
# Проверить сервисы
curl https://api.yourdomain.ru/health
curl https://admin.yourdomain.ru/api/health

# Проверить контейнеры
docker compose -f docker-compose.prod.yml ps
```

## Полезные команды

```bash
# Просмотр логов
docker compose -f docker-compose.prod.yml logs -f

# Перезапуск
docker compose -f docker-compose.prod.yml restart

# Создать бэкап
./backup.sh

# Восстановить из бэкапа
./restore.sh backups/ragbot_backup_YYYYMMDD_HHMMSS.sql.gz
```

## Подробная документация

См. [MIGRATION_GUIDE.md](MIGRATION_GUIDE.md) для подробных инструкций.



