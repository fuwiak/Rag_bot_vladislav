#!/usr/bin/env python3
"""
Скрипт для добавления колонки fast_mode в таблицу documents на продакшн
Запуск: python add_fast_mode_production.py
"""
import asyncio
import sys
from sqlalchemy import text
from app.core.database import engine
from app.core.config import settings
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def add_fast_mode_column():
    """Добавляет колонку fast_mode если её нет"""
    try:
        async with engine.begin() as conn:
            # Проверяем, существует ли колонка
            if "postgresql" in settings.DATABASE_URL.lower():
                # PostgreSQL
                result = await conn.execute(text("""
                    SELECT column_name 
                    FROM information_schema.columns 
                    WHERE table_name = 'documents' AND column_name = 'fast_mode'
                """))
                exists = result.fetchone() is not None
                
                if not exists:
                    logger.info("Добавляем колонку fast_mode в таблицу documents...")
                    await conn.execute(text("""
                        ALTER TABLE documents 
                        ADD COLUMN fast_mode BOOLEAN DEFAULT FALSE
                    """))
                    logger.info("✅ Колонка fast_mode успешно добавлена")
                else:
                    logger.info("✅ Колонка fast_mode уже существует")
            else:
                # SQLite
                result = await conn.execute(text("""
                    PRAGMA table_info(documents)
                """))
                columns = [row[1] for row in result.fetchall()]
                
                if 'fast_mode' not in columns:
                    logger.info("Добавляем колонку fast_mode в таблицу documents...")
                    await conn.execute(text("""
                        ALTER TABLE documents 
                        ADD COLUMN fast_mode BOOLEAN DEFAULT 0
                    """))
                    logger.info("✅ Колонка fast_mode успешно добавлена")
                else:
                    logger.info("✅ Колонка fast_mode уже существует")
                    
        logger.info("Готово!")
        return 0
                    
    except Exception as e:
        logger.error(f"❌ Ошибка при добавлении колонки fast_mode: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(add_fast_mode_column())
    sys.exit(exit_code)
