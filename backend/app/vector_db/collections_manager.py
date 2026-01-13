"""
Управление коллекциями Qdrant
Использует конфигурацию из config/qdrant.yaml с fallback на settings
"""
from qdrant_client.models import Distance, VectorParams
from pathlib import Path

from app.vector_db.qdrant_client import qdrant_client
from app.core.config import settings

# Импортируем загрузчик конфигурации
try:
    from config.config_loader import get_qdrant_config_value
except ImportError:
    # Fallback если config_loader не доступен
    def get_qdrant_config_value(key: str, default=None, base_path=None):
        return default


class CollectionsManager:
    """Менеджер коллекций Qdrant"""
    
    def __init__(self):
        self.client = qdrant_client.get_client()
    
    async def create_collection(self, project_id: str):
        """
        Создать коллекцию для проекта
        
        Args:
            project_id: ID проекта
        """
        collection_name = f"project_{project_id}"
        
        # Проверка существования коллекции
        collections = self.client.get_collections().collections
        existing_names = [col.name for col in collections]
        
        if collection_name in existing_names:
            return  # Коллекция уже существует
        
        # Определяем базовый путь для загрузки конфига
        backend_dir = Path(__file__).parent.parent.parent
        
        # Получаем dimension из конфига с fallback на settings
        vector_size = get_qdrant_config_value(
            "target_dimension",
            default=settings.EMBEDDING_DIMENSION,
            base_path=backend_dir
        )
        
        # Создание коллекции
        self.client.create_collection(
            collection_name=collection_name,
            vectors_config=VectorParams(
                size=vector_size,
                distance=Distance.COSINE
            )
        )
    
    async def delete_collection(self, project_id: str):
        """
        Удалить коллекцию проекта
        
        Args:
            project_id: ID проекта
        """
        collection_name = f"project_{project_id}"
        self.client.delete_collection(collection_name=collection_name)
    
    def collection_exists(self, project_id: str) -> bool:
        """Проверить существование коллекции"""
        collection_name = f"project_{project_id}"
        collections = self.client.get_collections().collections
        existing_names = [col.name for col in collections]
        return collection_name in existing_names
























