#!/usr/bin/env python3
"""
Скрипт для создания бэкапа базы данных PostgreSQL
Согласно ТЗ п. 6.2.3 - резервное копирование
"""
import os
import sys
import subprocess
from datetime import datetime
from pathlib import Path
from app.core.config import settings
import urllib.parse


def create_backup(backup_dir: str = "backups"):
    """
    Создать бэкап базы данных PostgreSQL
    
    Args:
        backup_dir: Директория для сохранения бэкапов
    """
    # Парсинг DATABASE_URL
    db_url = settings.DATABASE_URL
    
    # Извлекаем параметры из URL
    # Формат: postgresql://user:password@host:port/dbname
    if db_url.startswith("postgresql://"):
        parsed = urllib.parse.urlparse(db_url)
        db_user = parsed.username
        db_password = parsed.password
        db_host = parsed.hostname
        db_port = parsed.port or 5432
        db_name = parsed.path.lstrip('/')
    else:
        print("❌ Неверный формат DATABASE_URL")
        sys.exit(1)
    
    # Создаем директорию для бэкапов
    backup_path = Path(backup_dir)
    backup_path.mkdir(exist_ok=True)
    
    # Генерируем имя файла бэкапа
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_filename = f"rag_bot_backup_{timestamp}.sql"
    backup_filepath = backup_path / backup_filename
    
    # Команда pg_dump
    # Используем PGPASSWORD для передачи пароля
    env = os.environ.copy()
    if db_password:
        env['PGPASSWORD'] = db_password
    
    pg_dump_cmd = [
        'pg_dump',
        '-h', db_host,
        '-p', str(db_port),
        '-U', db_user,
        '-d', db_name,
        '-F', 'c',  # Custom format (сжатый)
        '-f', str(backup_filepath)
    ]
    
    try:
        print(f"📦 Создание бэкапа базы данных {db_name}...")
        result = subprocess.run(
            pg_dump_cmd,
            env=env,
            capture_output=True,
            text=True,
            check=True
        )
        
        # Получаем размер файла
        file_size = backup_filepath.stat().st_size / (1024 * 1024)  # MB
        
        print(f"✅ Бэкап успешно создан: {backup_filepath}")
        print(f"📊 Размер файла: {file_size:.2f} MB")
        print(f"💾 Для восстановления используйте:")
        print(f"   pg_restore -h {db_host} -p {db_port} -U {db_user} -d {db_name} {backup_filepath}")
        
        return str(backup_filepath)
        
    except subprocess.CalledProcessError as e:
        print(f"❌ Ошибка при создании бэкапа:")
        print(f"   {e.stderr}")
        sys.exit(1)
    except FileNotFoundError:
        print("❌ pg_dump не найден. Убедитесь, что PostgreSQL client tools установлены.")
        sys.exit(1)


def restore_backup(backup_filepath: str, target_db: str = None):
    """
    Восстановить базу данных из бэкапа
    
    Args:
        backup_filepath: Путь к файлу бэкапа
        target_db: Имя целевой базы данных (по умолчанию из DATABASE_URL)
    """
    db_url = settings.DATABASE_URL
    
    if db_url.startswith("postgresql://"):
        parsed = urllib.parse.urlparse(db_url)
        db_user = parsed.username
        db_password = parsed.password
        db_host = parsed.hostname
        db_port = parsed.port or 5432
        db_name = target_db or parsed.path.lstrip('/')
    else:
        print("❌ Неверный формат DATABASE_URL")
        sys.exit(1)
    
    if not Path(backup_filepath).exists():
        print(f"❌ Файл бэкапа не найден: {backup_filepath}")
        sys.exit(1)
    
    env = os.environ.copy()
    if db_password:
        env['PGPASSWORD'] = db_password
    
    pg_restore_cmd = [
        'pg_restore',
        '-h', db_host,
        '-p', str(db_port),
        '-U', db_user,
        '-d', db_name,
        '--clean',  # Очистить существующие объекты
        '--if-exists',  # Не выдавать ошибки если объект не существует
        backup_filepath
    ]
    
    try:
        print(f"🔄 Восстановление базы данных {db_name} из {backup_filepath}...")
        print("⚠️  ВНИМАНИЕ: Это перезапишет существующие данные!")
        
        response = input("Продолжить? (yes/no): ")
        if response.lower() != 'yes':
            print("❌ Операция отменена")
            sys.exit(0)
        
        result = subprocess.run(
            pg_restore_cmd,
            env=env,
            capture_output=True,
            text=True,
            check=True
        )
        
        print(f"✅ База данных успешно восстановлена из {backup_filepath}")
        
    except subprocess.CalledProcessError as e:
        print(f"❌ Ошибка при восстановлении:")
        print(f"   {e.stderr}")
        sys.exit(1)
    except FileNotFoundError:
        print("❌ pg_restore не найден. Убедитесь, что PostgreSQL client tools установлены.")
        sys.exit(1)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Использование:")
        print("  python backup_database.py backup [backup_dir]")
        print("  python backup_database.py restore <backup_filepath> [target_db]")
        sys.exit(1)
    
    command = sys.argv[1]
    
    if command == "backup":
        backup_dir = sys.argv[2] if len(sys.argv) > 2 else "backups"
        create_backup(backup_dir)
    elif command == "restore":
        if len(sys.argv) < 3:
            print("❌ Укажите путь к файлу бэкапа")
            sys.exit(1)
        backup_filepath = sys.argv[2]
        target_db = sys.argv[3] if len(sys.argv) > 3 else None
        restore_backup(backup_filepath, target_db)
    else:
        print(f"❌ Неизвестная команда: {command}")
        sys.exit(1)




