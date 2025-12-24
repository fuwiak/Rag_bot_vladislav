"""
Главный файл FastAPI приложения
"""
import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from app.core.config import settings
from app.core.database import init_db
from app.api import router as api_router
from app.api.middleware import RateLimitMiddleware

# Настройка логирования - только важные сообщения
logging.basicConfig(
    level=logging.WARNING,
    format='%(levelname)s: %(message)s'
)
# Отключаем лишние логи
logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
logging.getLogger("pydantic").setLevel(logging.ERROR)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Управление жизненным циклом приложения"""
    import logging
    logger = logging.getLogger(__name__)
    
    # Инициализация при запуске
    if not settings.SKIP_DB_INIT:
        # Сначала создаем таблицы
        try:
            await init_db()
            # Ждем немного чтобы таблицы точно создались
            import asyncio
            await asyncio.sleep(0.5)
        except Exception as e:
            logger.warning(f"Database initialization failed: {e}")
        
        # Потом создаем администратора - игнорируем все ошибки
        try:
            from app.core.database import AsyncSessionLocal
            from app.models.admin_user import AdminUser
            from app.services.auth_service import AuthService
            from sqlalchemy import select
            
            async with AsyncSessionLocal() as db:
                try:
                    result = await db.execute(select(AdminUser))
                    existing = result.scalars().first()
                    if not existing:
                        auth_service = AuthService(db)
                        admin = AdminUser(
                            username="admin",
                            password_hash=auth_service.get_password_hash("admin")
                        )
                        db.add(admin)
                        await db.commit()
                        logger.warning("Admin user 'admin' created")
                except Exception as e:
                    # Если ошибка - пробуем еще раз
                    try:
                        await db.rollback()
                        result = await db.execute(select(AdminUser))
                        existing = result.scalars().first()
                        if not existing:
                            auth_service = AuthService(db)
                            admin = AdminUser(
                                username="admin",
                                password_hash=auth_service.get_password_hash("admin")
                            )
                            db.add(admin)
                            await db.commit()
                            logger.warning("Admin user 'admin' created (retry)")
                    except:
                        pass
        except Exception as e:
            logger.warning(f"Admin creation skipped: {e}")
    
    yield


app = FastAPI(
    title="Telegram RAG Bot API",
    description="API для системы Telegram-ботов с RAG для работы с документами",
    version="1.0.0",
    lifespan=lifespan
)

# Добавляем обработчик ошибок для предотвращения падения приложения
from fastapi.responses import JSONResponse
from fastapi import Request

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Глобальный обработчик ошибок для предотвращения падения приложения"""
    import traceback
    logger = logging.getLogger(__name__)
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    
    # Возвращаем ошибку с CORS заголовками
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"},
        headers={
            "Access-Control-Allow-Origin": "*",  # Разрешаем все origins при ошибке
            "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, PATCH, OPTIONS",
            "Access-Control-Allow-Headers": "*",
        }
    )

# CORS middleware
# Логируем CORS origins для отладки
cors_origins = settings.CORS_ORIGINS
if not isinstance(cors_origins, list):
    if isinstance(cors_origins, str):
        # Разбиваем строку по запятой
        cors_origins = [origin.strip() for origin in cors_origins.split(',') if origin.strip()]
    else:
        cors_origins = [cors_origins] if cors_origins else []

# Добавляем дефолтные origins если список пустой
if not cors_origins:
    cors_origins = ["https://ragbotvladislav-test.up.railway.app", "http://localhost:3000"]

logging.info(f"CORS origins configured: {cors_origins}")

# Добавляем CORS middleware ПЕРЕД rate limiting для правильной обработки preflight
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["*"],
    max_age=3600,  # Кэшируем preflight на 1 час
)

# Rate limiting middleware
app.add_middleware(RateLimitMiddleware, requests_per_minute=60)

# Подключение роутеров
app.include_router(api_router, prefix="/api")


@app.get("/health")
async def health_check():
    """Health check endpoint для мониторинга"""
    return {"status": "healthy"}


@app.get("/ready")
async def readiness_check():
    """Readiness check endpoint"""
    # Можно добавить проверку подключения к БД и другим сервисам
    return {"status": "ready"}


@app.get("/api/test-cors")
async def test_cors():
    """Тестовый endpoint для проверки CORS"""
    from datetime import datetime
    return {
        "status": "ok",
        "message": "CORS работает правильно",
        "timestamp": datetime.utcnow().isoformat()
    }


@app.get("/api/test-connection")
async def test_connection():
    """Тестовый endpoint для проверки подключения"""
    from datetime import datetime
    return {
        "status": "ok",
        "message": "Backend доступен",
        "backend_url": str(settings.BACKEND_URL),
        "cors_origins": settings.CORS_ORIGINS,
        "timestamp": datetime.utcnow().isoformat()
    }


@app.get("/api/test-cors")
async def test_cors():
    """Тестовый endpoint для проверки CORS"""
    return {
        "status": "ok",
        "message": "CORS работает правильно",
        "timestamp": datetime.utcnow().isoformat()
    }


@app.get("/api/test-connection")
async def test_connection():
    """Тестовый endpoint для проверки подключения"""
    return {
        "status": "ok",
        "message": "Backend доступен",
        "backend_url": str(settings.BACKEND_URL),
        "cors_origins": settings.CORS_ORIGINS,
        "timestamp": datetime.utcnow().isoformat()
    }

