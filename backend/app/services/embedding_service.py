"""
Сервис для создания эмбеддингов
Использует конфигурацию из config/llm.yaml с fallback на settings
"""
from typing import List, Optional
import httpx
import time
import logging
import os
from pathlib import Path

from app.core.config import settings
from app.services.cache_service import cache_service
from app.observability.metrics import rag_metrics
from app.observability.otel_setup import get_tracer

# Импортируем загрузчик конфигурации
try:
    from config.config_loader import get_llm_config_value
except ImportError:
    # Fallback если config_loader не доступен
    def get_llm_config_value(key: str, default=None, base_path=None):
        return default

tracer = get_tracer(__name__)
logger = logging.getLogger(__name__)

# Попытка импортировать SentenceTransformer для локальных embeddings
try:
    from sentence_transformers import SentenceTransformer
    SENTENCE_TRANSFORMERS_AVAILABLE = True
except ImportError:
    SENTENCE_TRANSFORMERS_AVAILABLE = False
    logger.info("sentence-transformers не установлен. Локальные embeddings недоступны. Используются API embeddings. Для локальных embeddings установите: pip install sentence-transformers")


class EmbeddingService:
    """Сервис для работы с эмбеддингами"""
    
    def __init__(self, use_local: bool = False):
        """
        Args:
            use_local: Если True, использует локальные embeddings (SentenceTransformer) вместо API
        """
        # Определяем базовый путь для загрузки конфига
        backend_dir = Path(__file__).parent.parent.parent
        
        # Загружаем конфигурацию из config/llm.yaml с fallback на settings
        self.api_key = get_llm_config_value(
            "embeddings.api_key",
            default=settings.OPENROUTER_API_KEY,
            base_path=backend_dir
        )
        self.model = get_llm_config_value(
            "embeddings.model",
            default=settings.EMBEDDING_MODEL,
            base_path=backend_dir
        )
        self.api_url = get_llm_config_value(
            "embeddings.api_url",
            default=os.getenv("EMBEDDING_API_URL", "https://openrouter.ai/api/v1/embeddings"),
            base_path=backend_dir
        )
        self.use_local = use_local
        self._local_model: Optional[SentenceTransformer] = None
        
        if use_local and SENTENCE_TRANSFORMERS_AVAILABLE:
            try:
                # Используем ту же модель что в prostym kodzie
                logger.info("Loading local embedding model: paraphrase-multilingual-MiniLM-L12-v2")
                self._local_model = SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')
                logger.info("Local embedding model loaded successfully")
            except Exception as e:
                logger.error(f"Failed to load local embedding model: {e}, falling back to API")
                self.use_local = False
        elif use_local and not SENTENCE_TRANSFORMERS_AVAILABLE:
            logger.warning("Local embeddings requested but sentence-transformers not available, using API")
            self.use_local = False
    
    async def create_embedding(self, text: str) -> List[float]:
        """
        Создать эмбеддинг для текста (локально или через OpenRouter)
        
        Args:
            text: Текст для создания эмбеддинга
        
        Returns:
            Вектор эмбеддинга
        """
        start_time = time.time()
        
        with tracer.start_as_current_span("embedding.create") as span:
            span.set_attribute("model", self.model if not self.use_local else "local-sentence-transformer")
            span.set_attribute("text_length", len(text))
            span.set_attribute("use_local", self.use_local)
            
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
            
            # Локальные embeddings (jak w prostym kodzie)
            if self.use_local and self._local_model:
                try:
                    # SentenceTransformer работает синхронnie, więc używamy run_in_executor
                    import asyncio
                    loop = asyncio.get_event_loop()
                    embedding = await loop.run_in_executor(
                        None,
                        lambda: self._local_model.encode(text, normalize_embeddings=True).tolist()
                    )
                    
                    # Zapisujemy do cache
                    await cache_service.set_embedding(text, embedding)
                    
                    duration = time.time() - start_time
                    rag_metrics.record_embedding_generation(duration, "local-sentence-transformer")
                    span.set_attribute("duration", duration)
                    
                    return embedding
                except Exception as e:
                    logger.warning(f"Local embedding failed: {e}, falling back to API")
                    # Fallback do API
            
            # Generujemy embedding przez API
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    self.api_url,
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
            span.set_attribute("model", self.model if not self.use_local else "local-sentence-transformer")
            span.set_attribute("batch_size", len(texts))
            span.set_attribute("use_local", self.use_local)
            
            # Pobieramy z cache
            cached_embeddings = await cache_service.get_embeddings_batch(texts)
            
            # Teksty bez cache
            texts_to_generate = [text for text, emb in zip(texts, cached_embeddings.values()) if emb is None]
            embeddings_to_return = []
            
            if texts_to_generate:
                # Локальные embeddings (jak w prostym kodzie)
                if self.use_local and self._local_model:
                    try:
                        import asyncio
                        loop = asyncio.get_event_loop()
                        new_embeddings = await loop.run_in_executor(
                            None,
                            lambda: self._local_model.encode(texts_to_generate, normalize_embeddings=True).tolist()
                        )
                        
                        # Zapisujemy do cache
                        await cache_service.set_embeddings_batch(texts_to_generate, new_embeddings)
                        
                        # Łączymy z cached
                        embedding_map = dict(zip(texts_to_generate, new_embeddings))
                        for text in texts:
                            if text in cached_embeddings and cached_embeddings[text]:
                                embeddings_to_return.append(cached_embeddings[text])
                            else:
                                embeddings_to_return.append(embedding_map[text])
                        
                        duration = time.time() - start_time
                        rag_metrics.record_embedding_generation(duration, "local-sentence-transformer")
                        span.set_attribute("duration", duration)
                        span.set_attribute("cache_hits", len(texts) - len(texts_to_generate))
                        
                        return embeddings_to_return
                    except Exception as e:
                        logger.warning(f"Local batch embedding failed: {e}, falling back to API")
                        # Fallback do API
                
                # Generujemy brakujące embeddings przez API
                async with httpx.AsyncClient(timeout=60.0) as client:
                    response = await client.post(
                        self.api_url,
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





















