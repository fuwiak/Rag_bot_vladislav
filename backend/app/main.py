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

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Управление жизненным циклом приложения"""
    # Инициализация при запуске
    if not settings.SKIP_DB_INIT:
        try:
            await init_db()
        except Exception as e:
            logger = logging.getLogger(__name__)
            logger.error(f"Database initialization failed: {e}")
            logger.warning("Application will continue without database. Some features may not work.")
            logger.warning("Set SKIP_DB_INIT=true to skip database initialization on startup")
    else:
        logger = logging.getLogger(__name__)
        logger.info("Skipping database initialization (SKIP_DB_INIT=true)")
    
    # Боты теперь управляются отдельным сервисом telegram-bots
    logger = logging.getLogger(__name__)
    logger.info("Bots are managed by separate telegram-bots service")
    
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

