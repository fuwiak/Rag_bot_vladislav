"""
Клиент для работы с Qdrant Cloud
"""
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams

from app.core.config import settings


class QdrantClientWrapper:
    """Обертка над Qdrant клиентом"""
    
    def __init__(self):
        # Używamy prefer_grpc=False, aby używać HTTP zamiast gRPC (szybsza instalacja)
        self.client = QdrantClient(
            url=settings.QDRANT_URL,
            api_key=settings.QDRANT_API_KEY,
            prefer_grpc=False,  # Używamy HTTP API zamiast gRPC
        )
    
    def get_client(self) -> QdrantClient:
        """Получить клиент Qdrant"""
        return self.client


# Глобальный экземпляр клиента
qdrant_client = QdrantClientWrapper()

