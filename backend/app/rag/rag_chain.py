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
        
        # Параметры RAG
        self.top_k = top_k
        self.min_score = min_score
        
        # Параметры hybrid search
        self.search_strategy = search_strategy
        self.dense_weight = dense_weight
        self.bm25_weight = bm25_weight
        
        # Системный промпт для RAG (общий, без упоминания Kaspersky)
        self.system_prompt = """Ты - полезный ассистент, который отвечает на вопросы пользователей на основе предоставленных документов.

Твоя задача - отвечать на вопросы пользователей:
1. Используя предоставленный контекст из документов (если он есть)
2. На общие вопросы (используя свои знания, если контекст не предоставлен)

Правила:
1. Если предоставлен контекст - отвечай на основе контекста
2. Если контекста нет или он не релевантен - можешь использовать свои общие знания
3. Если в контексте нет информации - честно скажи об этом
4. Отвечай на русском языке
5. Будь дружелюбным и профессиональным
6. Если используешь контекст из документов - в конце ответа укажи источники информации"""
    
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
            
            # Если нет результатов, пробуем с низким порогом
            if len(context_docs) == 0 and use_rag:
                logger.warning("⚠️ No documents found, retrying with lower threshold...")
                context_docs = await self.qdrant_loader.search(
                    query=user_query,
                    top_k=top_k * 2,
                    score_threshold=0.2,  # Очень низкий порог
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
        
        # Шаг 2: Формируем промпт с контекстом
        if context_docs:
            context_text = self._format_context(context_docs)
            enhanced_prompt = f"""Контекст из документов:

{context_text}

Вопрос пользователя: {user_query}

Ответь на вопрос, используя предоставленный контекст. Если в контексте нет информации,
честно скажи об этом."""
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
        
        Args:
            documents: Список найденных документов
        
        Returns:
            Отформатированный текст контекста
        """
        context_parts = []
        
        for i, doc in enumerate(documents, 1):
            text = doc.get("text", "") or doc.get("chunk_text", "")
            source_url = doc.get("source_url", "")
            score = doc.get("score", 0.0)
            
            context_part = f"[Документ {i}] (релевантность: {score:.2f})\n"
            if source_url:
                context_part += f"Источник: {source_url}\n"
            context_part += f"{text}\n"
            
            context_parts.append(context_part)
        
        return "\n---\n".join(context_parts)
    
    async def close(self):
        """Закрывает ресурсы"""
        await self.llm_client.close()

