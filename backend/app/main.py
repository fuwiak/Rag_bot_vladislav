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
    # Инициализация при запуске
    if not settings.SKIP_DB_INIT:
        try:
            await init_db()
            # Автоматически создаем администратора если его нет (только для Railway)
            try:
                from app.core.database import AsyncSessionLocal
                from app.models.admin_user import AdminUser
                from app.services.auth_service import AuthService
                from sqlalchemy import select
                
                async with AsyncSessionLocal() as db:
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
            except Exception:
                pass  # Игнорируем ошибки создания администратора
        except Exception:
            pass  # Игнорируем ошибки инициализации
    
    yield


app = FastAPI(
    title="Telegram RAG Bot API",
    description="API для системы Telegram-ботов с RAG для работы с документами",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
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

