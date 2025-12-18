"""
Настройка подключения к базе данных
"""
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy import text

from app.core.config import settings

# Создание async engine
# Jeśli używamy SQLite dla lokalnego rozwoju, użyj sqlite+aiosqlite
import logging
logger = logging.getLogger(__name__)

db_url = settings.DATABASE_URL
# Logowanie DATABASE_URL bez hasła dla debugowania
if db_url and db_url != "postgresql://postgres:postgres@localhost:5432/rag_bot_db":
    # Ukryj hasło w logach
    safe_url = db_url
    try:
        if "@" in safe_url:
            parts = safe_url.split("@")
            if "://" in parts[0] and ":" in parts[0]:
                protocol_user = parts[0].split("://")
                if len(protocol_user) == 2:
                    user_pass = protocol_user[1]
                    if ":" in user_pass:
                        user = user_pass.split(":")[0]
                        safe_url = protocol_user[0] + "://" + user + ":****@" + "@".join(parts[1:])
        logger.info(f"Using database URL: {safe_url}")
    except Exception:
        logger.info(f"Using database URL: (hidden)")
elif not db_url:
    logger.error("DATABASE_URL is not set!")
else:
    logger.warning(f"Using default DATABASE_URL (localhost) - this may not work in Railway!")
    logger.warning("Please add PostgreSQL service in Railway or set DATABASE_URL environment variable")

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
    import os
    logger = logging.getLogger(__name__)
    
    # Sprawdź czy DATABASE_URL jest ustawione
    db_url_env = os.getenv("DATABASE_URL") or os.getenv("POSTGRES_URL")
    if not db_url_env:
        logger.error("DATABASE_URL environment variable is not set!")
        logger.error("Please set DATABASE_URL in Railway environment variables or add PostgreSQL service")
        raise ValueError("DATABASE_URL environment variable is required")
    
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
                logger.error("Please check:")
                logger.error("1. DATABASE_URL is set correctly in Railway environment variables")
                logger.error("2. PostgreSQL service is running and accessible")
                logger.error("3. Database credentials are correct")
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
