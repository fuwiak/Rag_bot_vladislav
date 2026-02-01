"""
Redis Cache Service dla embeddings i odpowiedzi RAG
"""
import json
import hashlib
import logging
from typing import Optional, List, Any, Dict
from datetime import timedelta
import redis.asyncio as redis
from redis.asyncio import Redis

from app.core.config import settings

logger = logging.getLogger(__name__)


class CacheService:
    """Serwis do zarządzania cache w Redis"""
    
    def __init__(self):
        self.redis_client: Optional[Redis] = None
        self.enabled = settings.ENABLE_RAG_CACHE
        self._connection_pool = None
    
    async def connect(self):
        """Nawiązuje połączenie z Redis"""
        if not self.enabled:
            logger.info("Cache disabled, skipping Redis connection")
            return
        
        try:
            # Budujemy URL Redis
            redis_url = settings.REDIS_URL
            if not redis_url:
                # Próbujemy zbudować z komponentów
                redis_host = settings.REDIS_HOST or "localhost"
                redis_port = settings.REDIS_PORT
                redis_password = settings.REDIS_PASSWORD
                redis_db = settings.REDIS_DB
                
                if redis_password:
                    redis_url = f"redis://:{redis_password}@{redis_host}:{redis_port}/{redis_db}"
                else:
                    redis_url = f"redis://{redis_host}:{redis_port}/{redis_db}"
            
            self._connection_pool = redis.ConnectionPool.from_url(
                redis_url,
                decode_responses=True,
                max_connections=10
            )
            self.redis_client = Redis(connection_pool=self._connection_pool)
            
            # Test połączenia
            await self.redis_client.ping()
            logger.info("✅ Redis cache connected")
            
        except Exception as e:
            logger.warning(f"Failed to connect to Redis: {e}. Cache will be disabled.")
            self.enabled = False
            self.redis_client = None
    
    async def disconnect(self):
        """Zamyka połączenie z Redis"""
        if self.redis_client:
            await self.redis_client.close()
            if self._connection_pool:
                await self._connection_pool.disconnect()
            logger.info("Redis cache disconnected")
    
    def _make_key(self, prefix: str, key: str) -> str:
        """Tworzy klucz cache z prefixem"""
        return f"rag:{prefix}:{key}"
    
    def _hash_text(self, text: str) -> str:
        """Tworzy hash z tekstu dla klucza cache"""
        return hashlib.sha256(text.encode('utf-8')).hexdigest()
    
    async def get_embedding(self, text: str) -> Optional[List[float]]:
        """
        Pobiera embedding z cache
        
        Args:
            text: Tekst do wyszukania w cache
        
        Returns:
            Embedding vector lub None jeśli nie ma w cache
        """
        if not self.enabled or not self.redis_client:
            return None
        
        try:
            key = self._make_key("embedding", self._hash_text(text))
            cached = await self.redis_client.get(key)
            
            if cached:
                embedding = json.loads(cached)
                logger.debug(f"Cache hit for embedding: {key[:16]}...")
                return embedding
            
            return None
            
        except Exception as e:
            logger.warning(f"Error getting embedding from cache: {e}")
            return None
    
    async def set_embedding(self, text: str, embedding: List[float], ttl: Optional[int] = None):
        """
        Zapisuje embedding do cache
        
        Args:
            text: Tekst
            embedding: Embedding vector
            ttl: Time to live w sekundach (domyślnie z settings)
        """
        if not self.enabled or not self.redis_client:
            return
        
        try:
            key = self._make_key("embedding", self._hash_text(text))
            ttl = ttl or settings.EMBEDDING_CACHE_TTL
            
            await self.redis_client.setex(
                key,
                ttl,
                json.dumps(embedding)
            )
            logger.debug(f"Cached embedding: {key[:16]}... (TTL: {ttl}s)")
            
        except Exception as e:
            logger.warning(f"Error setting embedding in cache: {e}")
    
    async def get_embeddings_batch(self, texts: List[str]) -> Dict[str, Optional[List[float]]]:
        """
        Pobiera wiele embeddings z cache
        
        Args:
            texts: Lista tekstów
        
        Returns:
            Dict {text: embedding} - None dla tekstów nie w cache
        """
        if not self.enabled or not self.redis_client:
            return {text: None for text in texts}
        
        try:
            keys = [self._make_key("embedding", self._hash_text(text)) for text in texts]
            cached = await self.redis_client.mget(keys)
            
            result = {}
            for text, cached_value in zip(texts, cached):
                if cached_value:
                    result[text] = json.loads(cached_value)
                else:
                    result[text] = None
            
            hits = sum(1 for v in result.values() if v is not None)
            logger.debug(f"Batch cache: {hits}/{len(texts)} hits")
            
            return result
            
        except Exception as e:
            logger.warning(f"Error getting embeddings batch from cache: {e}")
            return {text: None for text in texts}
    
    async def set_embeddings_batch(self, texts: List[str], embeddings: List[List[float]], ttl: Optional[int] = None):
        """
        Zapisuje wiele embeddings do cache
        
        Args:
            texts: Lista tekstów
            embeddings: Lista embedding vectors
            ttl: Time to live w sekundach
        """
        if not self.enabled or not self.redis_client:
            return
        
        try:
            ttl = ttl or settings.EMBEDDING_CACHE_TTL
            pipe = self.redis_client.pipeline()
            
            for text, embedding in zip(texts, embeddings):
                key = self._make_key("embedding", self._hash_text(text))
                pipe.setex(key, ttl, json.dumps(embedding))
            
            await pipe.execute()
            logger.debug(f"Cached {len(texts)} embeddings (TTL: {ttl}s)")
            
        except Exception as e:
            logger.warning(f"Error setting embeddings batch in cache: {e}")
    
    async def get_rag_response(
        self,
        question: str,
        project_id: str,
        similarity_threshold: float = 0.9
    ) -> Optional[str]:
        """
        Pobiera odpowiedź RAG z cache na podstawie podobieństwa semantycznego
        
        Args:
            question: Pytanie
            project_id: ID projektu
            similarity_threshold: Próg podobieństwa (0-1)
        
        Returns:
            Odpowiedź lub None
        """
        if not self.enabled or not self.redis_client:
            return None
        
        try:
            # Szukamy w cache wszystkich odpowiedzi dla projektu
            pattern = self._make_key("response", f"{project_id}:*")
            keys = []
            async for key in self.redis_client.scan_iter(match=pattern):
                keys.append(key)
            
            if not keys:
                return None
            
            # Pobieramy wszystkie odpowiedzi
            cached_responses = await self.redis_client.mget(keys)
            
            # Porównujemy pytania (uproszczone - w produkcji użyj embedding similarity)
            question_lower = question.lower().strip()
            for key, cached_value in zip(keys, cached_responses):
                if not cached_value:
                    continue
                
                cached_data = json.loads(cached_value)
                cached_question = cached_data.get("question", "").lower().strip()
                
                # Proste porównanie (można ulepszyć używając embedding similarity)
                if cached_question == question_lower:
                    logger.debug(f"Cache hit for RAG response: {key[:32]}...")
                    return cached_data.get("answer")
            
            return None
            
        except Exception as e:
            logger.warning(f"Error getting RAG response from cache: {e}")
            return None
    
    async def set_rag_response(
        self,
        question: str,
        answer: str,
        project_id: str,
        ttl: Optional[int] = None
    ):
        """
        Zapisuje odpowiedź RAG do cache
        
        Args:
            question: Pytanie
            answer: Odpowiedź
            project_id: ID projektu
            ttl: Time to live w sekundach
        """
        if not self.enabled or not self.redis_client:
            return
        
        try:
            key = self._make_key("response", f"{project_id}:{self._hash_text(question)}")
            ttl = ttl or settings.RAG_CACHE_TTL
            
            data = {
                "question": question,
                "answer": answer,
                "project_id": project_id
            }
            
            await self.redis_client.setex(
                key,
                ttl,
                json.dumps(data)
            )
            logger.debug(f"Cached RAG response: {key[:32]}... (TTL: {ttl}s)")
            
        except Exception as e:
            logger.warning(f"Error setting RAG response in cache: {e}")
    
    async def invalidate_project_cache(self, project_id: str):
        """
        Usuwa wszystkie cache dla projektu (np. po aktualizacji dokumentów)
        
        Args:
            project_id: ID projektu
        """
        if not self.enabled or not self.redis_client:
            return
        
        try:
            pattern = self._make_key("*", f"{project_id}:*")
            keys = []
            async for key in self.redis_client.scan_iter(match=pattern):
                keys.append(key)
            
            if keys:
                await self.redis_client.delete(*keys)
                logger.info(f"Invalidated {len(keys)} cache entries for project {project_id}")
            
        except Exception as e:
            logger.warning(f"Error invalidating project cache: {e}")
    
    async def set_document_content(
        self,
        document_id: str,
        content: str,
        ttl: Optional[int] = None
    ):
        """
        Zapisuje контент документа в Redis для быстрого доступа
        
        Args:
            document_id: ID документа
            content: Контент документа
            ttl: Time to live в секундах (по умолчанию 1 час)
        """
        if not self.enabled or not self.redis_client:
            return
        
        try:
            key = self._make_key("document_content", document_id)
            ttl = ttl or 3600  # 1 час по умолчанию
            
            await self.redis_client.setex(
                key,
                ttl,
                content
            )
            logger.debug(f"Cached document content: {document_id} (TTL: {ttl}s, size: {len(content)} chars)")
            
        except Exception as e:
            logger.warning(f"Error setting document content in cache: {e}")
    
    async def get_document_content(
        self,
        document_id: str
    ) -> Optional[str]:
        """
        Получает контент документа из Redis
        
        Args:
            document_id: ID документа
        
        Returns:
            Контент документа или None если не найден
        """
        if not self.enabled or not self.redis_client:
            return None
        
        try:
            key = self._make_key("document_content", document_id)
            content = await self.redis_client.get(key)
            
            if content:
                logger.debug(f"Retrieved document content from cache: {document_id} ({len(content)} chars)")
                return content
            
            return None
            
        except Exception as e:
            logger.warning(f"Error getting document content from cache: {e}")
            return None
    
    async def get_cache_stats(self) -> Dict[str, Any]:
        """Zwraca statystyki cache"""
        if not self.enabled or not self.redis_client:
            return {"enabled": False}
        
        try:
            info = await self.redis_client.info("stats")
            return {
                "enabled": True,
                "keys": await self.redis_client.dbsize(),
                "hits": info.get("keyspace_hits", 0),
                "misses": info.get("keyspace_misses", 0),
            }
        except Exception as e:
            logger.warning(f"Error getting cache stats: {e}")
            return {"enabled": False, "error": str(e)}


# Globalna instancja cache service
cache_service = CacheService()

