"""
Главный файл FastAPI приложения
"""
import logging
import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from datetime import datetime

from app.core.config import settings
from app.core.database import init_db
from app.api import router as api_router
from app.api.middleware import RateLimitMiddleware

# Inicjalizacja Observability
from app.observability.otel_setup import setup_opentelemetry
from app.observability.structured_logging import setup_structured_logging
from app.observability.metrics import get_metrics_exporter

# Setup structured logging
setup_structured_logging(
    json_output=os.getenv("JSON_LOGGING", "true").lower() == "true",
    log_level=os.getenv("LOG_LEVEL", "INFO")
)

logger = logging.getLogger(__name__)

# Setup OpenTelemetry
if settings.ENABLE_TRACING or settings.ENABLE_METRICS:
    try:
        setup_opentelemetry(
            service_name="rag-bot-backend",
            enable_tracing=settings.ENABLE_TRACING,
            enable_metrics=settings.ENABLE_METRICS
        )
        logger.info("✅ Observability stack initialized")
    except Exception as e:
        logger.warning(f"Failed to initialize observability: {e}")

# Auto-instrumentacja FastAPI, SQLAlchemy, httpx
if settings.ENABLE_TRACING:
    try:
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
        from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
        from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
        
        # Instrumentacja będzie dodana po utworzeniu app
        _fastapi_instrumentor = FastAPIInstrumentor()
        _sqlalchemy_instrumentor = SQLAlchemyInstrumentor()
        _httpx_instrumentor = HTTPXClientInstrumentor()
        
        logger.info("✅ OpenTelemetry auto-instrumentation configured")
    except Exception as e:
        logger.warning(f"Failed to setup auto-instrumentation: {e}")
        _fastapi_instrumentor = None
        _sqlalchemy_instrumentor = None
        _httpx_instrumentor = None
else:
    _fastapi_instrumentor = None
    _sqlalchemy_instrumentor = None
    _httpx_instrumentor = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Управление жизненным циклом приложения"""
    
    # Inicjalizacja cache service
    from app.services.cache_service import cache_service
    await cache_service.connect()
    
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
        
        # Применяем миграции Alembic автоматически
        try:
            import subprocess
            import sys
            logger.info("Applying Alembic migrations...")
            # Sprawdzamy czy są multiple heads
            heads_check = subprocess.run(
                ["alembic", "heads"],
                cwd="/app" if os.path.exists("/app") else ".",
                capture_output=True,
                text=True,
                timeout=30
            )
            # Używamy "heads" zamiast "head" jeśli są multiple heads
            upgrade_command = ["alembic", "upgrade", "heads"]
            result = subprocess.run(
                upgrade_command,
                cwd="/app" if os.path.exists("/app") else ".",
                capture_output=True,
                text=True,
                timeout=60
            )
            if result.returncode == 0:
                logger.info("✅ Migrations applied successfully")
            else:
                logger.warning(f"Migration output: {result.stdout}\n{result.stderr}")
                # Пробуем применить миграции вручную для summary колонки
                try:
                    from app.core.database import AsyncSessionLocal
                    from sqlalchemy import text
                    async with AsyncSessionLocal() as db:
                        # Проверяем наличие колонки summary
                        result = await db.execute(text("""
                            SELECT column_name FROM information_schema.columns 
                            WHERE table_name = 'documents' AND column_name = 'summary'
                        """))
                        if result.first() is None:
                            # Добавляем колонку summary если её нет
                            await db.execute(text("""
                                ALTER TABLE documents 
                                ADD COLUMN summary TEXT
                            """))
                            await db.commit()
                            logger.info("✅ Summary column added manually")
                        else:
                            logger.info("Summary column already exists")
                except Exception as manual_error:
                    logger.warning(f"Manual migration failed: {manual_error}")
        except Exception as migration_error:
            logger.warning(f"Automatic migration failed: {migration_error}, trying manual migration...")
            # Fallback: ручное применение миграций
            try:
                from app.core.database import AsyncSessionLocal
                from sqlalchemy import text
                async with AsyncSessionLocal() as db:
                    # Проверяем и добавляем колонку summary если её нет
                    result = await db.execute(text("""
                        SELECT column_name FROM information_schema.columns 
                        WHERE table_name = 'documents' AND column_name = 'summary'
                    """))
                    if result.first() is None:
                        await db.execute(text("ALTER TABLE documents ADD COLUMN summary TEXT"))
                        await db.commit()
                        logger.info("✅ Summary column added via manual migration")
            except Exception as manual_error:
                logger.warning(f"Manual migration also failed: {manual_error}")
        
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
    
    # Cleanup przy zamknięciu
    await cache_service.disconnect()


app = FastAPI(
    title="Telegram RAG Bot API",
    description="API для системы Telegram-ботов с RAG для работы с документами",
    version="1.0.0",
    lifespan=lifespan
)

# Instrumentacja FastAPI dla OpenTelemetry
if _fastapi_instrumentor:
    try:
        _fastapi_instrumentor.instrument_app(app)
        logger.info("✅ FastAPI instrumented for OpenTelemetry")
    except Exception as e:
        logger.warning(f"Failed to instrument FastAPI: {e}")

# Instrumentacja SQLAlchemy
if _sqlalchemy_instrumentor:
    try:
        from app.core.database import engine
        _sqlalchemy_instrumentor.instrument(engine=engine.sync_engine)
        logger.info("✅ SQLAlchemy instrumented for OpenTelemetry")
    except Exception as e:
        logger.warning(f"Failed to instrument SQLAlchemy: {e}")

# Instrumentacja httpx
if _httpx_instrumentor:
    try:
        _httpx_instrumentor.instrument()
        logger.info("✅ HTTPX instrumented for OpenTelemetry")
    except Exception as e:
        logger.warning(f"Failed to instrument HTTPX: {e}")

# Добавляем обработчик OPTIONS запросов ПЕРЕД всеми остальными
from fastapi import Request
from fastapi.responses import Response

@app.options("/{full_path:path}")
async def options_handler(request: Request, full_path: str):
    """Обработчик OPTIONS запросов для CORS preflight"""
    return Response(
        status_code=200,
        headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, PATCH, OPTIONS",
            "Access-Control-Allow-Headers": "*",
            "Access-Control-Max-Age": "3600",
        }
    )

# Добавляем обработчик ошибок для предотвращения падения приложения
from fastapi.responses import JSONResponse

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


@app.get("/metrics")
async def metrics_endpoint():
    """Prometheus metrics endpoint"""
    if not settings.ENABLE_METRICS:
        return Response(
            content="Metrics disabled",
            status_code=503,
            media_type="text/plain"
        )
    
    try:
        from prometheus_client.openmetrics.exposition import CONTENT_TYPE_LATEST
        metrics_data = get_metrics_exporter()
        return Response(
            content=metrics_data,
            media_type=CONTENT_TYPE_LATEST
        )
    except Exception as e:
        logger.error(f"Failed to export metrics: {e}")
        return Response(
            content=f"Error: {str(e)}",
            status_code=500,
            media_type="text/plain"
        )


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

