"""
Настройка подключения к базе данных
"""
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy import text

from app.core.config import settings

# Создание async engine
# Jeśli używamy SQLite dla lokalnego rozwoju, użyj sqlite+aiosqlite
db_url = settings.DATABASE_URL
if db_url.startswith("sqlite"):
    # SQLite dla lokalnego rozwoju
    engine = create_async_engine(
        db_url.replace("sqlite:///", "sqlite+aiosqlite:///"),
        echo=False,
        future=True,
        connect_args={"check_same_thread": False}
    )
else:
    # PostgreSQL - добавление pool_pre_ping для автоматического переподключения
    engine = create_async_engine(
        db_url.replace("postgresql://", "postgresql+asyncpg://"),
        echo=False,
        future=True,
        pool_pre_ping=True,  # Автоматическая проверка соединения перед использованием
        pool_recycle=300,  # Переподключение каждые 5 минут
    )

# Создание session factory
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


class Base(DeclarativeBase):
    """Базовый класс для моделей"""
    pass


async def get_db() -> AsyncSession:
    """
    Dependency для получения сессии БД
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


async def wait_for_db(max_retries: int = 30, retry_interval: int = 2):
    """
    Ожидание готовности базы данных с повторными попытками
    """
    import asyncio
    import logging
    logger = logging.getLogger(__name__)
    
    for attempt in range(max_retries):
        try:
            # Пробуем подключиться к базе данных
            async with engine.begin() as conn:
                await conn.execute(text("SELECT 1"))
            logger.info("Database connection successful")
            return True
        except Exception as e:
            if attempt < max_retries - 1:
                logger.warning(f"Database connection attempt {attempt + 1}/{max_retries} failed: {e}. Retrying in {retry_interval}s...")
                await asyncio.sleep(retry_interval)
            else:
                logger.error(f"Failed to connect to database after {max_retries} attempts: {e}")
                raise
    return False


async def init_db():
    """
    Инициализация БД (создание таблиц)
    """
    import logging
    logger = logging.getLogger(__name__)
    
    # Ожидание готовности базы данных
    logger.info("Waiting for database to be ready...")
    await wait_for_db()
    
    # Импорт моделей в правильной kolejności для регистрации w metadata
    from app.models.admin_user import AdminUser  # noqa
    from app.models.project import Project  # noqa
    from app.models.user import User  # noqa
    from app.models.document import Document, DocumentChunk  # noqa
    from app.models.message import Message  # noqa
    
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("Database tables initialized successfully")
    except Exception as e:
        # Если таблица уже существует, то OK
        logger.warning(f"Błąd podczas tworzenia tabel (możliwe, że już istnieją): {e}")
