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
    # Railway automatically provides DATABASE_URL when PostgreSQL service is added
    # Railway may use template format: postgresql://${{PGUSER}}:${{POSTGRES_PASSWORD}}@${{RAILWAY_PRIVATE_DOMAIN}}:5432/${{PGDATABASE}}
    # For local development, defaults to localhost
    DATABASE_URL: str = "postgresql://postgres:postgres@localhost:5432/rag_bot_db"
    
    # Temporary: Skip database initialization (for fast startup)
    SKIP_DB_INIT: bool = False
    
    # Use in-memory SQLite as fallback if PostgreSQL is not available
    USE_IN_MEMORY_DB: bool = False
    
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
    QDRANT_URL: str = "https://239a4026-d673-4b8b-bfab-a99c7044e6b1.us-east4-0.gcp.cloud.qdrant.io"
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
    
    # CORS - can be set as comma-separated string in environment variables
    CORS_ORIGINS: Union[str, List[str]] = "http://localhost:3000,http://localhost:3001"
    
    @field_validator('CORS_ORIGINS', mode='before')
    @classmethod
    def parse_cors_origins(cls, v):
        """Parse CORS_ORIGINS from comma-separated string or list"""
        if isinstance(v, str):
            # Split by comma and strip whitespace
            return [origin.strip() for origin in v.split(',') if origin.strip()]
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

