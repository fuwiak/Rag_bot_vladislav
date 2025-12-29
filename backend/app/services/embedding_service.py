"""
Сервис для создания эмбеддингов
"""
from typing import List
import httpx
import time

from app.core.config import settings
from app.services.cache_service import cache_service
from app.observability.metrics import rag_metrics
from app.observability.otel_setup import get_tracer

tracer = get_tracer(__name__)


class EmbeddingService:
    """Сервис для работы с эмбеддингами"""
    
    def __init__(self):
        self.api_key = settings.OPENROUTER_API_KEY
        self.model = settings.EMBEDDING_MODEL
    
    async def create_embedding(self, text: str) -> List[float]:
        """
        Создать эмбеддинг для текста через OpenRouter (z cache)
        
        Args:
            text: Текст для создания эмбеддинга
        
        Returns:
            Вектор эмбеддинга
        """
        start_time = time.time()
        
        with tracer.start_as_current_span("embedding.create") as span:
            span.set_attribute("model", self.model)
            span.set_attribute("text_length", len(text))
            
            # Sprawdzamy cache
            cached_embedding = await cache_service.get_embedding(text)
            if cached_embedding:
                duration = time.time() - start_time
                rag_metrics.record_embedding_generation(duration, self.model)
                rag_metrics.record_cache_hit("embedding")
                span.set_attribute("cache_hit", True)
                return cached_embedding
            
            rag_metrics.record_cache_miss("embedding")
            span.set_attribute("cache_hit", False)
            
            # Generujemy embedding
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
                embedding = data["data"][0]["embedding"]
            
            # Zapisujemy do cache
            await cache_service.set_embedding(text, embedding)
            
            duration = time.time() - start_time
            rag_metrics.record_embedding_generation(duration, self.model)
            span.set_attribute("duration", duration)
            
            return embedding
    
    async def create_embeddings_batch(self, texts: List[str]) -> List[List[float]]:
        """
        Создать эмбеддинги для списка текстов (батчинг z cache)
        
        Args:
            texts: Список текстов
        
        Returns:
            Список векторов эмбеддингов
        """
        start_time = time.time()
        
        with tracer.start_as_current_span("embedding.create_batch") as span:
            span.set_attribute("model", self.model)
            span.set_attribute("batch_size", len(texts))
            
            # Pobieramy z cache
            cached_embeddings = await cache_service.get_embeddings_batch(texts)
            
            # Teksty bez cache
            texts_to_generate = [text for text, emb in zip(texts, cached_embeddings.values()) if emb is None]
            embeddings_to_return = []
            
            if texts_to_generate:
                # Generujemy brakujące embeddings
                async with httpx.AsyncClient(timeout=60.0) as client:
                    response = await client.post(
                        "https://openrouter.ai/api/v1/embeddings",
                        headers={
                            "Authorization": f"Bearer {self.api_key}",
                            "HTTP-Referer": settings.APP_URL,
                            "Content-Type": "application/json"
                        },
                        json={
                            "model": self.model,
                            "input": texts_to_generate
                        }
                    )
                    response.raise_for_status()
                    data = response.json()
                    new_embeddings = [item["embedding"] for item in data["data"]]
                
                # Zapisujemy do cache
                await cache_service.set_embeddings_batch(texts_to_generate, new_embeddings)
                
                # Łączymy z cached
                embedding_map = dict(zip(texts_to_generate, new_embeddings))
                for text in texts:
                    if text in cached_embeddings and cached_embeddings[text]:
                        embeddings_to_return.append(cached_embeddings[text])
                    else:
                        embeddings_to_return.append(embedding_map[text])
            else:
                # Wszystkie z cache
                embeddings_to_return = [cached_embeddings[text] for text in texts]
            
            duration = time.time() - start_time
            rag_metrics.record_embedding_generation(duration, self.model)
            span.set_attribute("duration", duration)
            span.set_attribute("cache_hits", len(texts) - len(texts_to_generate))
            
            return embeddings_to_return





















