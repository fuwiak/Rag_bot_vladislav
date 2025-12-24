"""Проверка наличия колонки summary в таблице documents"""
import asyncio
from sqlalchemy import text
from app.core.database import AsyncSessionLocal


async def check_summary_column():
    """Проверяет наличие колонки summary"""
    async with AsyncSessionLocal() as db:
        try:
            result = await db.execute(
                text("""
                    SELECT column_name 
                    FROM information_schema.columns 
                    WHERE table_name = 'documents' 
                    AND column_name = 'summary'
                """)
            )
            row = result.first()
            if row:
                print("✅ Колонка summary существует в таблице documents")
                return True
            else:
                print("❌ Колонка summary НЕ найдена в таблице documents")
                return False
        except Exception as e:
            print(f"❌ Ошибка при проверке: {e}")
            return False


if __name__ == "__main__":
    asyncio.run(check_summary_column())

