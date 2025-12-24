"""
Клиент для работы с Qdrant (локальный RAM или Cloud)
"""
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams
import logging

from app.core.config import settings

logger = logging.getLogger(__name__)


class QdrantClientWrapper:
    """Обертка над Qdrant клиентом"""
    
    def __init__(self):
        # Если QDRANT_URL не указан или пустой, используем локальный Qdrant в RAM
        if not settings.QDRANT_URL or settings.QDRANT_URL.strip() == "":
            logger.info("QDRANT_URL not set, using local Qdrant in RAM mode")
            # Локальный Qdrant в RAM (in-memory)
            self.client = QdrantClient(
                location=":memory:",  # In-memory режим
                prefer_grpc=False
            )
            logger.info("✅ Initialized Qdrant client in RAM mode")
        else:
            # Используем Qdrant Cloud или удаленный сервер
            logger.info(f"Using Qdrant Cloud/Remote: {settings.QDRANT_URL}")
            self.client = QdrantClient(
                url=settings.QDRANT_URL,
                api_key=settings.QDRANT_API_KEY if settings.QDRANT_API_KEY else None,
                prefer_grpc=False,  # Используем HTTP API вместо gRPC
            )
            logger.info("✅ Initialized Qdrant client for Cloud/Remote")
    
    def get_client(self) -> QdrantClient:
        """Получить клиент Qdrant"""
        return self.client


# Глобальный экземпляр клиента
qdrant_client = QdrantClientWrapper()

