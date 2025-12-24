#!/usr/bin/env python3
"""
Скрипт для ручного применения миграции bot_is_active
Используйте этот скрипт, если миграция не применяется автоматически
"""
import asyncio
import sys
from pathlib import Path

# Добавляем путь к app
sys.path.insert(0, str(Path(__file__).parent))

from sqlalchemy import text
from app.core.database import AsyncSessionLocal
from app.core.config import settings

async def apply_migration():
    """Применить миграцию вручную"""
    print("Connecting to database...")
    print(f"Database URL: {settings.DATABASE_URL[:50]}...")
    
    async with AsyncSessionLocal() as db:
        try:
            # Проверяем, существует ли колонка
            result = await db.execute(
                text("""
                    SELECT column_name 
                    FROM information_schema.columns 
                    WHERE table_name = 'projects' AND column_name = 'bot_is_active'
                """)
            )
            exists = result.first() is not None
            
            if exists:
                print("Column bot_is_active already exists, skipping migration")
                return
            
            print("Adding bot_is_active column...")
            # Добавляем колонку
            await db.execute(
                text("""
                    ALTER TABLE projects 
                    ADD COLUMN bot_is_active VARCHAR(10) DEFAULT 'false' NOT NULL
                """)
            )
            await db.commit()
            print("✅ Migration applied successfully!")
            
            # Обновляем существующие проекты с токенами - делаем их активными
            print("Updating existing projects with bot_token to bot_is_active='true'...")
            await db.execute(
                text("""
                    UPDATE projects 
                    SET bot_is_active = 'true' 
                    WHERE bot_token IS NOT NULL
                """)
            )
            await db.commit()
            print("✅ Existing bots activated!")
            
        except Exception as e:
            await db.rollback()
            print(f"❌ Error applying migration: {e}")
            raise

if __name__ == "__main__":
    try:
        asyncio.run(apply_migration())
        print("\n✅ Migration completed successfully!")
    except Exception as e:
        print(f"\n❌ Migration failed: {e}")
        sys.exit(1)

