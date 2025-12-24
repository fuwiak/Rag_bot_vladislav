# Установка Git на сервере REG.RU

Краткая инструкция по установке Git на Ubuntu/Debian сервере.

## Быстрая установка

```bash
# Обновить список пакетов
apt update

# Установить Git
apt install -y git

# Проверить установку
git --version
```

## Настройка Git (опционально)

```bash
# Настроить имя пользователя
git config --global user.name "Your Name"

# Настроить email
git config --global user.email "your.email@example.com"

# Проверить настройки
git config --list
```

## Проверка

После установки проверьте:

```bash
git --version
# Должно показать: git version 2.x.x или выше
```

## Использование

После установки Git вы можете клонировать репозиторий:

```bash
# Клонировать репозиторий
git clone https://github.com/fuwiak/Rag_bot_vladislav.git

# Или через SSH (если настроен SSH ключ)
git clone git@github.com:fuwiak/Rag_bot_vladislav.git
```

## Решение проблем

### Если apt update не работает

```bash
# Обновить список пакетов с принудительным обновлением
apt update --allow-releaseinfo-change
apt install -y git
```

### Если нужна более новая версия Git

```bash
# Добавить PPA для более новой версии Git
add-apt-repository ppa:git-core/ppa -y
apt update
apt install -y git
```

## Дополнительная информация

- Официальная документация: https://git-scm.com/doc
- GitHub руководство: https://docs.github.com/en/get-started

