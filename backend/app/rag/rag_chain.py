"""
RAG цепочка для генерации ответов на основе поиска в векторной БД.
Интеграция с Qdrant и LLM.
"""

import logging
from typing import List, Dict, Any, Optional
from app.rag.qdrant_loader import QdrantLoader
from app.rag.llm_client import LLMClient, LLMResponse

logger = logging.getLogger(__name__)


class RAGChain:
    """RAG цепочка для генерации ответов"""
    
    def __init__(
        self,
        qdrant_loader: Optional[QdrantLoader] = None,
        llm_client: Optional[LLMClient] = None,
        collection_name: str = "rag_docs",
        top_k: int = 5,
        min_score: float = 0.7,
        search_strategy: str = "hybrid",
        dense_weight: float = 0.4,
        bm25_weight: float = 0.6
    ):
        # Используем переданный loader или создаем новый
        self.qdrant_loader = qdrant_loader or QdrantLoader(collection_name=collection_name)
        
        # Инициализируем LLM клиент
        if llm_client is None:
            self.llm_client = LLMClient()
        else:
            self.llm_client = llm_client
        
        # Параметры RAG (по умолчанию более низкий порог для лучшего поиска)
        self.top_k = top_k
        self.min_score = min_score if min_score is not None else 0.2  # Более низкий порог по умолчанию
        
        # Параметры hybrid search
        self.search_strategy = search_strategy
        self.dense_weight = dense_weight
        self.bm25_weight = bm25_weight
        
        # Системный промпт для RAG (упрощенный, как в рабочем скрипте)
        self.system_prompt = """Ты - полезный ассистент, который отвечает на вопросы пользователей.
Отвечай на основе предоставленного контекста, если он есть.
Если в контексте нет информации, честно скажи об этом.
Отвечай на русском языке, будь дружелюбным и информативным."""
    
    async def query(
        self,
        user_query: str,
        use_rag: bool = True,
        top_k: Optional[int] = None,
        min_score: Optional[float] = None,
        project_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Обрабатывает пользовательский запрос с использованием RAG.
        
        Args:
            user_query: Вопрос пользователя
            use_rag: Использовать ли RAG поиск
            top_k: Количество результатов поиска
            min_score: Минимальный score для результатов
            project_id: ID проекта для фильтрации
        
        Returns:
            Словарь с ответом, источниками и метаданными
        """
        top_k = top_k or self.top_k
        min_score = min_score or self.min_score
        
        # Шаг 1: Поиск релевантных документов
        context_docs = []
        sources = []
        
        if use_rag:
            logger.info(f"Searching RAG for query: {user_query}")
            
            context_docs = await self.qdrant_loader.search(
                query=user_query,
                top_k=top_k,
                score_threshold=min_score,
                search_strategy=self.search_strategy,
                dense_weight=self.dense_weight,
                bm25_weight=self.bm25_weight,
                project_id=project_id
            )
            
            logger.info(f"Found {len(context_docs)} relevant documents")
            
            # Если нет результатов, пробуем с еще более низким порогом (как в рабочем скрипте)
            if len(context_docs) == 0 and use_rag:
                logger.warning("⚠️ No documents found, retrying with very low threshold...")
                context_docs = await self.qdrant_loader.search(
                    query=user_query,
                    top_k=top_k * 2,
                    score_threshold=0.0,  # Минимальный порог для поиска любых релевантных документов
                    search_strategy=self.search_strategy,
                    dense_weight=self.dense_weight,
                    bm25_weight=self.bm25_weight,
                    project_id=project_id
                )
                logger.info(f"Retry found {len(context_docs)} documents")
            
            # Извлекаем уникальные источники
            seen_urls = set()
            for doc in context_docs:
                url = doc.get("source_url", "")
                if url and url not in seen_urls:
                    sources.append(url)
                    seen_urls.add(url)
        
        # Шаг 2: Формируем промпт с контекстом (как в рабочем скрипте)
        if context_docs:
            context_text = self._format_context(context_docs)
            # Используем простой и эффективный промпт из рабочего скрипта
            enhanced_prompt = f"""На основе следующих фрагментов документов ответь на вопрос пользователя.
Если ответа нет в контексте, так и скажи.

КОНТЕКСТ:
{context_text}

ВОПРОС: {user_query}

ОТВЕТ:"""
        else:
            # Если нет контекста, но это общий вопрос - отвечаем на основе знаний
            if use_rag:
                logger.info("No context documents found, answering based on general knowledge")
            enhanced_prompt = f"""Вопрос пользователя: {user_query}

Ответь на вопрос, используя свои знания. Будь полезным и информативным."""
        
        # Шаг 3: Генерируем ответ через LLM
        logger.info("Generating response with LLM")
        llm_response = await self.llm_client.generate(
            prompt=enhanced_prompt,
            system_prompt=self.system_prompt,
            temperature=0.7,
            max_tokens=2048
        )
        
        # Шаг 4: Форматируем результат
        result = {
            "answer": llm_response.content,
            "sources": sources,
            "provider": llm_response.provider,
            "model": llm_response.model,
            "confidence": llm_response.confidence,
            "context_count": len(context_docs),
            "tokens_used": llm_response.tokens_used,
            "error": llm_response.error
        }
        
        return result
    
    def _format_context(self, documents: List[Dict[str, Any]]) -> str:
        """
        Форматирует найденные документы в контекст для промпта.
        Использует формат из рабочего скрипта для лучшей работы RAG.
        
        Args:
            documents: Список найденных документов
        
        Returns:
            Отформатированный текст контекста
        """
        context_parts = []
        
        for i, doc in enumerate(documents, 1):
            text = doc.get("text", "") or doc.get("chunk_text", "")
            source_url = doc.get("source_url", "") or doc.get("source", "") or doc.get("filename", "")
            score = doc.get("score", 0.0)
            
            # Формат из рабочего скрипта: "Фрагмент {i+1} (источник: {source}, релевантность: {score:.2f}):\n{text}"
            source_name = source_url if source_url else f"Документ {i}"
            context_part = f"Фрагмент {i} (источник: {source_name}, релевантность: {score:.2f}):\n{text}"
            
            context_parts.append(context_part)
        
        return "\n\n".join(context_parts)
    
    async def close(self):
        """Закрывает ресурсы"""
        await self.llm_client.close()

