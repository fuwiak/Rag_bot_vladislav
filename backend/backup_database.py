#!/usr/bin/env python3
"""
Скрипт для создания бэкапа базы данных (PostgreSQL или SQLite)
Согласно ТЗ п. 6.2.3 - резервное копирование
"""
import os
import sys
import subprocess
import shutil
import gzip
from datetime import datetime
from pathlib import Path
from app.core.config import settings
import urllib.parse


def create_backup(backup_dir: str = "backups"):
    """
    Создать бэкап базы данных (PostgreSQL или SQLite)
    
    Args:
        backup_dir: Директория для сохранения бэкапов
    """
    # Парсинг DATABASE_URL
    db_url = settings.DATABASE_URL
    
    # Создаем директорию для бэкапов
    backup_path = Path(backup_dir)
    backup_path.mkdir(exist_ok=True)
    
    # Генерируем имя файла бэкапа
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # Проверяем тип базы данных
    if db_url.startswith("sqlite"):
        # SQLite backup
        # Извлекаем путь к файлу из URL
        # Формат: sqlite+aiosqlite:////path/to/db или sqlite+aiosqlite:///./db
        db_path = db_url.replace("sqlite+aiosqlite:///", "").replace("sqlite:///", "")
        
        # Обработка двойного слеша (абсолютный путь) и одинарного (относительный)
        if db_path.startswith("//"):
            # Абсолютный путь: //data/rag_bot.db -> /data/rag_bot.db
            db_path = "/" + db_path[2:]
        elif db_path.startswith("./"):
            # Относительный путь: ./rag_bot.db -> rag_bot.db
            db_path = db_path[2:]
        elif not db_path.startswith("/"):
            # Относительный путь без ./
            pass
        
        db_file = Path(db_path)
        
        if not db_file.exists():
            print(f"❌ Файл базы данных не найден: {db_file}")
            sys.exit(1)
        
        # Создаем копию файла
        backup_filename = f"rag_bot_backup_{timestamp}.db"
        backup_filepath = backup_path / backup_filename
        
        try:
            print(f"📦 Создание бэкапа SQLite базы данных {db_file}...")
            shutil.copy2(db_file, backup_filepath)
            
            # Создаем сжатый архив
            compressed_filename = f"rag_bot_backup_{timestamp}.db.gz"
            compressed_filepath = backup_path / compressed_filename
            
            with open(backup_filepath, 'rb') as f_in:
                with gzip.open(compressed_filepath, 'wb') as f_out:
                    shutil.copyfileobj(f_in, f_out)
            
            # Удаляем несжатый файл
            backup_filepath.unlink()
            
            # Получаем размер файла
            file_size = compressed_filepath.stat().st_size / (1024 * 1024)  # MB
            
            print(f"✅ Бэкап успешно создан: {compressed_filepath}")
            print(f"📊 Размер файла: {file_size:.2f} MB")
            print(f"💾 Для восстановления используйте:")
            print(f"   python backup_database.py restore {compressed_filepath}")
            
            return str(compressed_filepath)
            
        except Exception as e:
            print(f"❌ Ошибка при создании бэкапа SQLite:")
            print(f"   {e}")
            sys.exit(1)
    
    elif db_url.startswith("postgresql://"):
        # PostgreSQL backup
        parsed = urllib.parse.urlparse(db_url)
        db_user = parsed.username
        db_password = parsed.password
        db_host = parsed.hostname
        db_port = parsed.port or 5432
        db_name = parsed.path.lstrip('/')
        
        backup_filename = f"rag_bot_backup_{timestamp}.sql"
        backup_filepath = backup_path / backup_filename
        
        # Команда pg_dump
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
            print(f"📦 Создание бэкапа базы данных PostgreSQL {db_name}...")
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
            print(f"   python backup_database.py restore {backup_filepath}")
            
            return str(backup_filepath)
            
        except subprocess.CalledProcessError as e:
            print(f"❌ Ошибка при создании бэкапа:")
            print(f"   {e.stderr}")
            sys.exit(1)
        except FileNotFoundError:
            print("❌ pg_dump не найден. Убедитесь, что PostgreSQL client tools установлены.")
            sys.exit(1)
    else:
        print(f"❌ Неподдерживаемый формат DATABASE_URL: {db_url}")
        print("Поддерживаются: sqlite+aiosqlite:///... или postgresql://...")
        sys.exit(1)


def restore_backup(backup_filepath: str, target_db: str = None):
    """
    Восстановить базу данных из бэкапа
    
    Args:
        backup_filepath: Путь к файлу бэкапа
        target_db: Имя целевой базы данных или путь (по умолчанию из DATABASE_URL)
    """
    db_url = settings.DATABASE_URL
    
    if not Path(backup_filepath).exists():
        print(f"❌ Файл бэкапа не найден: {backup_filepath}")
        sys.exit(1)
    
    print("⚠️  ВНИМАНИЕ: Это перезапишет существующие данные!")
    response = input("Продолжить? (yes/no): ")
    if response.lower() != 'yes':
        print("❌ Операция отменена")
        sys.exit(0)
    
    if db_url.startswith("sqlite"):
        # SQLite restore
        # Извлекаем путь к файлу из URL
        db_path = db_url.replace("sqlite+aiosqlite:///", "").replace("sqlite:///", "")
        
        if db_path.startswith("//"):
            db_path = "/" + db_path[2:]
        elif db_path.startswith("./"):
            db_path = db_path[2:]
        
        # Если указан target_db, используем его
        if target_db:
            db_path = target_db
        
        db_file = Path(db_path)
        
        try:
            print(f"🔄 Восстановление SQLite базы данных из {backup_filepath}...")
            
            # Распаковываем если это .gz файл
            if backup_filepath.endswith('.gz'):
                temp_file = backup_filepath[:-3]  # Убираем .gz
                with gzip.open(backup_filepath, 'rb') as f_in:
                    with open(temp_file, 'wb') as f_out:
                        shutil.copyfileobj(f_in, f_out)
                source_file = temp_file
            else:
                source_file = backup_filepath
            
            # Копируем файл
            shutil.copy2(source_file, db_file)
            
            # Удаляем временный файл если был
            if backup_filepath.endswith('.gz') and Path(temp_file).exists():
                Path(temp_file).unlink()
            
            print(f"✅ База данных успешно восстановлена в {db_file}")
            
        except Exception as e:
            print(f"❌ Ошибка при восстановлении SQLite:")
            print(f"   {e}")
            sys.exit(1)
    
    elif db_url.startswith("postgresql://"):
        # PostgreSQL restore
        parsed = urllib.parse.urlparse(db_url)
        db_user = parsed.username
        db_password = parsed.password
        db_host = parsed.hostname
        db_port = parsed.port or 5432
        db_name = target_db or parsed.path.lstrip('/')
        
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
            print(f"🔄 Восстановление базы данных PostgreSQL {db_name} из {backup_filepath}...")
            
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
    else:
        print(f"❌ Неподдерживаемый формат DATABASE_URL: {db_url}")
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









