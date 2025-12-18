"""
Сервис для создания эмбеддингов
"""
from typing import List
import httpx

from app.core.config import settings


class EmbeddingService:
    """Сервис для работы с эмбеддингами"""
    
    def __init__(self):
        self.api_key = settings.OPENROUTER_API_KEY
        self.model = settings.EMBEDDING_MODEL
    
    async def create_embedding(self, text: str) -> List[float]:
        """
        Создать эмбеддинг для текста через OpenRouter
        
        Args:
            text: Текст для создания эмбеддинга
        
        Returns:
            Вектор эмбеддинга
        """
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                "https://openrouter.ai/api/v1/embeddings",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "HTTP-Referer": settings.APP_URL,
                    "Content-Type": "application/json"
                },
                json={
                    "model": self.model,
                    "input": text
                }
            )
            response.raise_for_status()
            data = response.json()
            return data["data"][0]["embedding"]
    
    async def create_embeddings_batch(self, texts: List[str]) -> List[List[float]]:
        """
        Создать эмбеддинги для списка текстов (батчинг)
        
        Args:
            texts: Список текстов
        
        Returns:
            Список векторов эмбеддингов
        """
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                "https://openrouter.ai/api/v1/embeddings",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "HTTP-Referer": settings.APP_URL,
                    "Content-Type": "application/json"
                },
                json={
                    "model": self.model,
                    "input": texts
                }
            )
            response.raise_for_status()
            data = response.json()
            return [item["embedding"] for item in data["data"]]






