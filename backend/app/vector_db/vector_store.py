"""
Сохранение и поиск векторов в Qdrant
"""
from typing import List, Dict, Any, Optional
from uuid import UUID, uuid4
import logging
from qdrant_client.models import PointStruct, Filter, FieldCondition, MatchValue, VectorParams, Distance

from app.vector_db.qdrant_client import qdrant_client
from app.core.config import settings

logger = logging.getLogger(__name__)


class VectorStore:
    """Хранилище векторов в Qdrant"""
    
    def __init__(self):
        self.client = qdrant_client.get_client()
    
    async def collection_exists(self, collection_name: str) -> bool:
        """Проверить существование коллекции"""
        try:
            collections = self.client.get_collections().collections
            collection_names = [col.name for col in collections]
            exists = collection_name in collection_names
            logger.debug(f"Collection {collection_name} exists: {exists}")
            return exists
        except Exception as e:
            logger.error(f"Error checking collection existence {collection_name}: {e}", exc_info=True)
            return False
    
    async def ensure_collection(self, collection_name: str, vector_size: int = 1536) -> bool:
        """Убедиться, что коллекция существует, создать если нет"""
        try:
            if await self.collection_exists(collection_name):
                logger.debug(f"Collection {collection_name} already exists")
                return True
            
            # Создаем коллекцию
            logger.info(f"Creating collection {collection_name} with vector size {vector_size}")
            self.client.create_collection(
                collection_name=collection_name,
                vectors_config=VectorParams(
                    size=vector_size,
                    distance=Distance.COSINE
                )
            )
            logger.info(f"✅ Created collection {collection_name}")
            return True
        except Exception as e:
            logger.error(f"Error creating collection {collection_name}: {e}", exc_info=True)
            return False
    
    async def store_vector(
        self,
        collection_name: str,
        vector: List[float],
        payload: Dict[str, Any]
    ) -> UUID:
        """
        Сохранить вектор в Qdrant
        
        Args:
            collection_name: Имя коллекции
            vector: Вектор для сохранения
            payload: Метаданные (document_id, chunk_id и т.д.)
        
        Returns:
            ID точки в Qdrant
        """
        # Убеждаемся, что коллекция существует
        vector_size = len(vector)
        if not await self.ensure_collection(collection_name, vector_size):
            raise ValueError(f"Failed to create or verify collection {collection_name}")
        
        point_id = uuid4()
        
        point = PointStruct(
            id=point_id,
            vector=vector,
            payload=payload
        )
        
        try:
            self.client.upsert(
                collection_name=collection_name,
                points=[point]
            )
            logger.debug(f"Stored vector in {collection_name}, point_id: {point_id}, payload keys: {list(payload.keys())}")
        except Exception as e:
            logger.error(f"Error storing vector in {collection_name}: {e}", exc_info=True)
            raise
        
        return point_id
    
    async def search_similar(
        self,
        collection_name: str,
        query_vector: List[float],
        limit: int = 5,
        score_threshold: float = 0.5,
        project_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Поиск похожих векторов
        
        Args:
            collection_name: Имя коллекции
            query_vector: Вектор запроса
            limit: Количество результатов
            score_threshold: Минимальный score
            project_id: ID проекта для дополнительной фильтрации
        
        Returns:
            Список результатов с payload и score
        """
        # Проверяем существование коллекции перед поиском
        if not await self.collection_exists(collection_name):
            logger.warning(f"Collection {collection_name} does not exist, returning empty results")
            return []
        
        try:
            # Поиск похожих векторов
            search_result = self.client.search(
                collection_name=collection_name,
                query_vector=query_vector,
                limit=limit,
                score_threshold=score_threshold
            )
            
            results = []
            for point in search_result:
                results.append({
                    "point_id": point.id,
                    "score": point.score,
                    "payload": point.payload
                })
            
            logger.debug(f"Search in {collection_name} returned {len(results)} results")
            return results
        except Exception as e:
            logger.error(f"Error searching vectors in {collection_name}: {e}", exc_info=True)
            return []
    
    async def delete_vector(self, collection_name: str, point_id: UUID):
        """Удалить вектор по ID"""
        self.client.delete(
            collection_name=collection_name,
            points_selector=[point_id]
        )















