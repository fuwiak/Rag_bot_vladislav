"""
Конфигурация приложения через переменные окружения
"""
import os
import re
from pathlib import Path
from pydantic_settings import BaseSettings
from pydantic import field_validator
from typing import List, Union


def resolve_env_vars_in_string(value: str) -> str:
    """
    Rozwiązuje zmienne środowiskowe w formacie ${{VAR_NAME}} lub ${VAR_NAME}
    Railway używa formatu ${{VAR_NAME}} dla zmiennych środowiskowych
    """
    if not isinstance(value, str):
        return value
    
    # Railway format: ${{VAR_NAME}}
    def replace_railway_var(match):
        var_name = match.group(1)
        return os.getenv(var_name, match.group(0))
    
    # Standard format: ${VAR_NAME}
    def replace_standard_var(match):
        var_name = match.group(1)
        return os.getenv(var_name, match.group(0))
    
    # Najpierw rozwiązuj Railway format ${{VAR}}
    value = re.sub(r'\$\{\{(\w+)\}\}', replace_railway_var, value)
    # Potem standardowy format ${VAR}
    value = re.sub(r'\$\{(\w+)\}', replace_standard_var, value)
    
    return value


class Settings(BaseSettings):
    """Настройки приложения"""
    
    # Database
    # По умолчанию используется SQLite для легкого развертывания
    # Для Railway: sqlite+aiosqlite:////data/rag_bot.db (где /data - mounted volume)
    # Для локальной разработки: sqlite+aiosqlite:///./rag_bot.db
    DATABASE_URL: str = "sqlite+aiosqlite:///./rag_bot.db"
    
    # Temporary: Skip database initialization (for fast startup)
    SKIP_DB_INIT: bool = False
    
    # Use in-memory SQLite as fallback if PostgreSQL is not available
    USE_IN_MEMORY_DB: bool = False
    
    # Disable password check (for Railway/debugging)
    DISABLE_PASSWORD_CHECK: bool = False
    
    @field_validator('DATABASE_URL', mode='before')
    @classmethod
    def resolve_database_url(cls, v):
        """Rozwiązuje zmienne środowiskowe w DATABASE_URL"""
        if isinstance(v, str):
            resolved = resolve_env_vars_in_string(v)
            # Sprawdź czy nadal zawiera nierozwiązane zmienne
            if "${{" in resolved or "${" in resolved:
                import logging
                logger = logging.getLogger(__name__)
                logger.warning(f"DATABASE_URL contains unresolved variables: {resolved}")
                logger.warning("This may cause connection errors. Make sure all variables are set in Railway.")
            return resolved
        return v
    
    # Qdrant Cloud
    QDRANT_URL: str = "https://your-cluster-id.us-east4-0.gcp.cloud.qdrant.io"
    QDRANT_API_KEY: str = "your_qdrant_api_key_here"
    
    # OpenRouter
    OPENROUTER_API_KEY: str = "your_openrouter_api_key_here"
    OPENROUTER_MODEL_PRIMARY: str = "x-ai/grok-4.1-fast"
    OPENROUTER_MODEL_FALLBACK: str = "openai/gpt-oss-120b:free"
    OPENROUTER_TIMEOUT_PRIMARY: int = 30
    OPENROUTER_TIMEOUT_FALLBACK: int = 60
    
    # Embeddings
    EMBEDDING_MODEL: str = "text-embedding-3-small"
    EMBEDDING_DIMENSION: int = 1536
    
    # Admin Panel
    ADMIN_SECRET_KEY: str = "dev-secret-key-change-in-production"
    ADMIN_SESSION_SECRET: str = "dev-session-secret-change-in-production"
    
    # Application
    APP_URL: str = "http://localhost:3000"
    BACKEND_URL: str = "http://localhost:8000"
    
    # Redis for Celery broker
    # Railway provides REDIS_URL automatically, or use REDIS_PASSWORD + private networking
    # No localhost defaults - all values must be set via environment variables
    REDIS_URL: str = ""  # Railway provides this automatically
    REDIS_PASSWORD: str = ""  # Railway Redis password (required for private networking)
    REDIS_HOST: str = ""  # Use 'redis.railway.internal' for private networking
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0
    
    # Celery configuration
    CELERY_BROKER_URL: str = ""
    CELERY_RESULT_BACKEND: str = ""
    
    @field_validator('CELERY_BROKER_URL', mode='before')
    @classmethod
    def resolve_celery_broker_url(cls, v):
        """Resolve CELERY_BROKER_URL from REDIS_URL or build from components"""
        if isinstance(v, str) and v:
            return resolve_env_vars_in_string(v)
        
        # Try REDIS_URL first (Railway provides this automatically)
        redis_url = os.getenv('REDIS_URL', '')
        if redis_url:
            return resolve_env_vars_in_string(redis_url)
        
        # Build from components (for private networking with password)
        redis_password = os.getenv('REDIS_PASSWORD', '')
        redis_host = os.getenv('REDIS_HOST', '')
        redis_port = os.getenv('REDIS_PORT', '6379')
        redis_db = os.getenv('REDIS_DB', '0')
        
        # Require REDIS_HOST to be set (no localhost fallback)
        if not redis_host:
            raise ValueError(
                "REDIS_HOST must be set via environment variable. "
                "For Railway private networking, set REDIS_HOST=redis.railway.internal"
            )
        
        if redis_password:
            # Format: redis://:password@host:port/db
            return f"redis://:{redis_password}@{redis_host}:{redis_port}/{redis_db}"
        else:
            return f"redis://{redis_host}:{redis_port}/{redis_db}"
    
    @field_validator('CELERY_RESULT_BACKEND', mode='before')
    @classmethod
    def resolve_celery_result_backend(cls, v):
        """Resolve CELERY_RESULT_BACKEND from REDIS_URL or build from components"""
        if isinstance(v, str) and v:
            return resolve_env_vars_in_string(v)
        
        # Try REDIS_URL first (Railway provides this automatically)
        redis_url = os.getenv('REDIS_URL', '')
        if redis_url:
            return resolve_env_vars_in_string(redis_url)
        
        # Build from components (for private networking with password)
        redis_password = os.getenv('REDIS_PASSWORD', '')
        redis_host = os.getenv('REDIS_HOST', '')
        redis_port = os.getenv('REDIS_PORT', '6379')
        redis_db = os.getenv('REDIS_DB', '0')
        
        # Require REDIS_HOST to be set (no localhost fallback)
        if not redis_host:
            raise ValueError(
                "REDIS_HOST must be set via environment variable. "
                "For Railway private networking, set REDIS_HOST=redis.railway.internal"
            )
        
        if redis_password:
            # Format: redis://:password@host:port/db
            return f"redis://:{redis_password}@{redis_host}:{redis_port}/{redis_db}"
        else:
            return f"redis://{redis_host}:{redis_port}/{redis_db}"
    
    # CORS - can be set as comma-separated string in environment variables
    CORS_ORIGINS: Union[str, List[str]] = "http://localhost:3000,http://localhost:3001"
    
    @field_validator('CORS_ORIGINS', mode='before')
    @classmethod
    def parse_cors_origins(cls, v):
        """Parse CORS_ORIGINS from comma-separated string or list"""
        if isinstance(v, str):
            # Split by comma and strip whitespace
            origins = [origin.strip() for origin in v.split(',') if origin.strip()]
            # Логируем для отладки
            import logging
            logger = logging.getLogger(__name__)
            logger.info(f"Parsed CORS origins: {origins}")
            return origins
        return v
    
    class Config:
        # Use environment variables only (no .env file required)
        # Railway and Docker will provide all variables via environment
        # For local development, .env file is optional and will be loaded if exists
        env_file = (
            Path(__file__).parent.parent.parent / ".env"
            if (Path(__file__).parent.parent.parent / ".env").exists()
            else Path(__file__).parent.parent.parent.parent / ".env"
            if (Path(__file__).parent.parent.parent.parent / ".env").exists()
            else None
        )
        env_file_encoding = "utf-8"
        case_sensitive = True
        # Allow reading from environment variables even if env_file is None
        env_ignore_empty = True


settings = Settings()

