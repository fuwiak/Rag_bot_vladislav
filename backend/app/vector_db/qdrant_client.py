"""
Клиент для работы с Qdrant (локальный RAM или Cloud)
Использует конфигурацию из config/qdrant.yaml с fallback на settings
"""
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams
import logging
import os
from pathlib import Path

from app.core.config import settings

# Импортируем загрузчик конфигурации
try:
    from config.config_loader import get_qdrant_config_value
except ImportError:
    # Fallback если config_loader не доступен
    def get_qdrant_config_value(key: str, default=None, base_path=None):
        return default

logger = logging.getLogger(__name__)


class QdrantClientWrapper:
    """Обертка над Qdrant клиентом"""
    
    def __init__(self):
        # Определяем базовый путь для загрузки конфига
        backend_dir = Path(__file__).parent.parent.parent
        
        # Загружаем конфигурацию из config/qdrant.yaml с fallback на settings
        qdrant_url = get_qdrant_config_value("url", default=None, base_path=backend_dir)
        
        # Если URL не задан в конфиге, пробуем собрать из host и port
        if not qdrant_url:
            qdrant_host = get_qdrant_config_value("host", default=os.getenv("QDRANT_HOST", ""), base_path=backend_dir)
            qdrant_port = get_qdrant_config_value("port", default=os.getenv("QDRANT_PORT", "6333"), base_path=backend_dir)
            
            # Формируем URL из host и port, если они заданы
            if qdrant_host:
                qdrant_url = f"http://{qdrant_host}:{qdrant_port}" if not qdrant_host.startswith("http") else qdrant_host
            else:
                # Fallback на settings.QDRANT_URL или переменную окружения
                qdrant_url = settings.QDRANT_URL if hasattr(settings, 'QDRANT_URL') and settings.QDRANT_URL else os.getenv("QDRANT_URL")
        
        # Если все еще нет URL, используем Railway URL по умолчанию
        if not qdrant_url or qdrant_url.strip() == "":
            qdrant_url = "https://qdrant-production-ad0b.up.railway.app"
            logger.info(f"QDRANT_URL not set, using default Railway URL: {qdrant_url}")
        
        # Если QDRANT_URL не указан или пустой, используем локальный Qdrant в RAM
        if not qdrant_url or qdrant_url.strip() == "":
            logger.info("QDRANT_URL not set, using local Qdrant in RAM mode")
            # Локальный Qdrant в RAM (in-memory)
            self.client = QdrantClient(
                location=":memory:",  # In-memory режим
                prefer_grpc=False
            )
            logger.info("✅ Initialized Qdrant client in RAM mode")
        else:
            # Используем Qdrant Cloud или удаленный сервер
            logger.info(f"🔗 Connecting to Qdrant: {qdrant_url}")
            # API key из конфига или settings
            qdrant_api_key = get_qdrant_config_value("api_key", default=settings.QDRANT_API_KEY, base_path=backend_dir)
            if qdrant_api_key:
                logger.info("🔑 Using Qdrant API key")
            else:
                logger.info("🔓 No API key provided (public access)")
            
            self.client = QdrantClient(
                url=qdrant_url,
                api_key=qdrant_api_key if qdrant_api_key else None,
                prefer_grpc=False,  # Используем HTTP API вместо gRPC
                timeout=60.0,  # Увеличенный timeout для стабильности (60 секунд)
            )
            logger.info("✅ Initialized Qdrant client for Cloud/Remote with timeout=60s")
    
    def get_client(self) -> QdrantClient:
        """Получить клиент Qdrant"""
        return self.client


# Глобальный экземпляр клиента
qdrant_client = QdrantClientWrapper()

