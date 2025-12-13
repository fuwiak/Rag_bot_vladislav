"""
Настройка подключения к базе данных
"""
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase

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
    # PostgreSQL
    engine = create_async_engine(
        db_url.replace("postgresql://", "postgresql+asyncpg://"),
        echo=False,
        future=True
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


async def init_db():
    """
    Инициализация БД (создание таблиц)
    """
    # Импорт моделей в правильной kolejności для регистрации w metadata
    from app.models.admin_user import AdminUser  # noqa
    from app.models.project import Project  # noqa
    from app.models.user import User  # noqa
    from app.models.document import Document, DocumentChunk  # noqa
    from app.models.message import Message  # noqa
    
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    except Exception as e:
        # Если таблица уже существует, то OK
        import logging
        logger = logging.getLogger(__name__)
        logger.warning(f"Błąd podczas tworzenia tabel (możliwe, że już istnieją): {e}")
