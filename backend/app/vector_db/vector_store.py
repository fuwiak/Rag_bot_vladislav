"""
Сохранение и поиск векторов в Qdrant
"""
from typing import List, Dict, Any, Optional
from uuid import UUID, uuid4
from qdrant_client.models import PointStruct, Filter, FieldCondition, MatchValue

from app.vector_db.qdrant_client import qdrant_client


class VectorStore:
    """Хранилище векторов в Qdrant"""
    
    def __init__(self):
        self.client = qdrant_client.get_client()
    
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
        point_id = uuid4()
        
        point = PointStruct(
            id=point_id,
            vector=vector,
            payload=payload
        )
        
        self.client.upsert(
            collection_name=collection_name,
            points=[point]
        )
        
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
        
        return results
    
    async def delete_vector(self, collection_name: str, point_id: UUID):
        """Удалить вектор по ID"""
        self.client.delete(
            collection_name=collection_name,
            points_selector=[point_id]
        )







