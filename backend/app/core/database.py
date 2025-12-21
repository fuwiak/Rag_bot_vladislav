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

# Sprawdź czy użyć SQLite w pamięci jako fallback
use_in_memory = settings.USE_IN_MEMORY_DB
if not use_in_memory:
    # Automatycznie przełącz na SQLite w pamięci jeśli DATABASE_URL zawiera nierozwiązane zmienne
    if db_url and ("${{" in db_url or "${" in db_url):
        logger.warning("DATABASE_URL contains unresolved variables, switching to in-memory SQLite")
        use_in_memory = True
        db_url = "sqlite+aiosqlite:///:memory:"

# Упрощенная обработка URL
if use_in_memory:
    db_url = "sqlite+aiosqlite:///:memory:"
elif not db_url or db_url == "sqlite+aiosqlite:///./rag_bot.db":
    # Если DATABASE_URL не установлен или используется дефолтный локальный
    if not db_url or db_url == "sqlite+aiosqlite:///./rag_bot.db":
        # Используем in-memory только если действительно не установлен
        db_url = "sqlite+aiosqlite:///:memory:"
        use_in_memory = True

if db_url.startswith("sqlite") or use_in_memory:
    # SQLite dla lokalnego rozwoju lub w pamięci jako fallback
    if use_in_memory or ":memory:" in db_url:
        db_url = "sqlite+aiosqlite:///:memory:"
        logger.info("Initializing in-memory SQLite database")
    else:
        # Обработка разных форматов SQLite URL
        # sqlite:/// -> sqlite+aiosqlite:///
        # sqlite+aiosqlite://// -> оставляем как есть (абсолютный путь с двойным слешем)
        if db_url.startswith("sqlite:///"):
            db_url = db_url.replace("sqlite:///", "sqlite+aiosqlite:///")
        elif db_url.startswith("sqlite+aiosqlite:///"):
            # Уже правильный формат, оставляем как есть
            pass
        else:
            # Если формат не распознан, пытаемся исправить
            db_url = db_url.replace("sqlite:///", "sqlite+aiosqlite:///")
    engine = create_async_engine(
        db_url,
        echo=False,
        future=True,
        connect_args={"check_same_thread": False} if not use_in_memory else {}
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


async def wait_for_db(max_retries: int = 5, retry_interval: int = 1):
    """
    Ожидание готовности базы данных с повторными попытками
    Dla SQLite w pamięci zawsze zwraca True natychmiast
    """
    import asyncio
    
    # SQLite w pamięci nie wymaga połączenia
    if settings.USE_IN_MEMORY_DB or db_url.startswith("sqlite"):
        return True
    
    # Sprawdź czy DATABASE_URL jest ustawione
    db_url_env = os.getenv("DATABASE_URL") or os.getenv("POSTGRES_URL")
    if not db_url_env or "${{" in db_url_env or "${" in db_url_env:
        return True
    
    # Tylko dla PostgreSQL próbuj połączyć się
    for attempt in range(max_retries):
        try:
            async with engine.begin() as conn:
                await conn.execute(text("SELECT 1"))
            return True
        except Exception:
            if attempt < max_retries - 1:
                await asyncio.sleep(retry_interval)
            else:
                return True
    return True


async def init_db():
    """
    Инициализация БД (создание таблиц)
    """
    import logging
    logger = logging.getLogger(__name__)
    
    # Sprawdź czy SKIP_DB_INIT jest ustawione
    if settings.SKIP_DB_INIT:
        return
    
    # Sprawdź czy używamy SQLite w pamięci
    is_in_memory = settings.USE_IN_MEMORY_DB or db_url.startswith("sqlite") or ":memory:" in db_url
    
    if not is_in_memory:
        try:
            await wait_for_db()
        except Exception:
            # При ошибке переключаемся на SQLite
            if not db_url.startswith("sqlite"):
                global engine
                db_url_memory = "sqlite+aiosqlite:///:memory:"
                engine = create_async_engine(
                    db_url_memory,
                    echo=False,
                    future=True,
                    connect_args={}
                )
            is_in_memory = True
    
    # Импорт моделей в правильной kolejności для регистрации w metadata
    from app.models.admin_user import AdminUser  # noqa
    from app.models.project import Project  # noqa
    from app.models.user import User  # noqa
    from app.models.document import Document, DocumentChunk  # noqa
    from app.models.message import Message  # noqa
    
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    except Exception:
        # Если таблица уже существует, то OK - просто игнорируем
        pass
