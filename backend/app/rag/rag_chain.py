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
        bm25_weight: float = 0.6,
        # Параметры для поиска цен/КП
        pricing_search_enabled: bool = True,
        pricing_strategy: str = "hybrid",
        pricing_top_k: int = 10,
        pricing_min_score: float = 0.5,
        pricing_dense_weight: float = 0.5,
        pricing_bm25_weight: float = 0.5
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
        
        # Параметры для поиска цен/КП
        self.pricing_search_enabled = pricing_search_enabled
        self.pricing_strategy = pricing_strategy
        self.pricing_top_k = pricing_top_k
        self.pricing_min_score = pricing_min_score
        self.pricing_dense_weight = pricing_dense_weight
        self.pricing_bm25_weight = pricing_bm25_weight
        
        # Временные параметры для переопределения (для тестирования)
        self._temp_temperature: Optional[float] = None
        self._temp_max_tokens: Optional[int] = None
        
        # Системный промпт для RAG (упрощенный, как в рабочем скрипте)
        self.system_prompt = """Ты - полезный ассистент, который отвечает на вопросы пользователей.
Отвечай на основе предоставленного контекста, если он есть.
Если в контексте нет информации, честно скажи об этом.
Отвечай на русском языке, будь дружелюбным и информативным."""
    
    def _is_pricing_query(self, query: str) -> bool:
        """Определяет, является ли запрос запросом о ценах/КП"""
        pricing_keywords = [
            'цена', 'стоимость', 'прайс', 'прайс-лист', 'прайслист',
            'коммерческое предложение', 'кп', 'коммерческое',
            'тариф', 'тарифы', 'стоимость услуг', 'цена услуги',
            'сколько стоит', 'цена за', 'стоимость за'
        ]
        query_lower = query.lower()
        return any(keyword in query_lower for keyword in pricing_keywords)
    
    def set_temp_params(self, temperature: Optional[float] = None, max_tokens: Optional[int] = None):
        """Устанавливает временные параметры для следующего запроса"""
        self._temp_temperature = temperature
        self._temp_max_tokens = max_tokens
    
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
            logger.info(f"🔍 [RAG] Начало поиска в RAG для запроса: '{user_query}'")
            
            # Определяем стратегию поиска
            # Для запросов о ценах/КП - используем более точный поиск
            is_pricing_query = self._is_pricing_query(user_query)
            logger.info(f"🔍 [RAG] Тип запроса: {'pricing/commercial proposal' if is_pricing_query else 'general'}")
            
            if is_pricing_query and self.pricing_search_enabled:
                # Используем параметры для поиска цен/КП
                search_strategy = self.pricing_strategy
                search_top_k = self.pricing_top_k
                search_min_score = self.pricing_min_score
                search_dense_weight = self.pricing_dense_weight
                search_bm25_weight = self.pricing_bm25_weight
                logger.info(f"🔍 [RAG] Используется стратегия поиска цен/КП: {search_strategy}")
                logger.info(f"🔍 [RAG] Параметры поиска: top_k={search_top_k}, min_score={search_min_score}, dense_weight={search_dense_weight}, bm25_weight={search_bm25_weight}")
            else:
                # Используем обычные параметры
                search_strategy = self.search_strategy
                search_top_k = top_k or self.top_k
                search_min_score = min_score or self.min_score
                search_dense_weight = self.dense_weight
                search_bm25_weight = self.bm25_weight
                logger.info(f"🔍 [RAG] Используется обычная стратегия поиска: {search_strategy}")
                logger.info(f"🔍 [RAG] Параметры поиска: top_k={search_top_k}, min_score={search_min_score}, dense_weight={search_dense_weight}, bm25_weight={search_bm25_weight}")
            
            context_docs = await self.qdrant_loader.search(
                query=user_query,
                top_k=search_top_k,
                score_threshold=search_min_score,
                search_strategy=search_strategy,
                dense_weight=search_dense_weight,
                bm25_weight=search_bm25_weight,
                project_id=project_id
            )
            
            logger.info(f"🔍 [RAG] Найдено документов: {len(context_docs)}")
            
            # Логируем найденные документы
            for idx, doc in enumerate(context_docs[:5], 1):  # Логируем первые 5
                score = doc.get("score", 0)
                source = doc.get("source_url", "unknown")
                title = doc.get("title", doc.get("text", "")[:50])
                logger.info(f"🔍 [RAG] Документ {idx}: score={score:.3f}, source={source}, title={title[:100]}")
            
            # Если нет результатов, пробуем без фильтра whitelist и с низким порогом
            if len(context_docs) == 0 and use_rag:
                logger.warning("⚠️ [RAG] Документы не найдены, повторный поиск с низким порогом...")
                context_docs = await self.qdrant_loader.search(
                    query=user_query,
                    top_k=search_top_k * 2,
                    score_threshold=0.2,  # Очень низкий порог
                    search_strategy=search_strategy,
                    dense_weight=search_dense_weight,
                    bm25_weight=search_bm25_weight,
                    project_id=project_id
                )
                logger.info(f"🔍 [RAG] Повторный поиск нашел документов: {len(context_docs)}")
            
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
            logger.info(f"📝 [RAG] Формирование промпта с контекстом из {len(context_docs)} документов")
            logger.info(f"📝 [RAG] Размер контекста: {len(context_text)} символов")
            logger.info(f"📝 [RAG] Контекст (первые 500 символов): {context_text[:500]}...")
            
            enhanced_prompt = f"""Контекст из базы знаний HR консультанта:
{context_text}
Вопрос пользователя: {user_query}
Ответь на вопрос, используя предоставленный контекст. Если в контексте нет информации,
честно скажи об этом."""
        else:
            # Если нет контекста, но это общий вопрос - отвечаем на основе знаний
            if use_rag:
                logger.warning("⚠️ [RAG] Контекстные документы не найдены, отвечаю на основе общих знаний")
            enhanced_prompt = f"""Вопрос пользователя: {user_query}
Ответь на вопрос, используя свои знания о HR консалтинге, управлении персоналом и бизнес-процессах. Будь полезным и информативным."""
        
        # Шаг 3: Генерируем ответ через LLM
        logger.info(f"🤖 [RAG] Генерация ответа через LLM")
        logger.info(f"🤖 [RAG] Промпт для LLM (первые 500 символов): {enhanced_prompt[:500]}...")
        # Используем временные параметры, если они установлены
        temperature = self._temp_temperature if self._temp_temperature is not None else 0.7
        max_tokens = self._temp_max_tokens if self._temp_max_tokens is not None else 2048
        logger.info(f"🤖 [RAG] Параметры LLM: temperature={temperature}, max_tokens={max_tokens}")
        
        llm_response = await self.llm_client.generate(
            prompt=enhanced_prompt,
            system_prompt=self.system_prompt,
            temperature=temperature,
            max_tokens=max_tokens
        )
        
        logger.info(f"✅ [RAG] Ответ от LLM получен: provider={llm_response.provider}, model={llm_response.model}, confidence={llm_response.confidence:.2f}")
        logger.info(f"✅ [RAG] Ответ (первые 500 символов): {llm_response.content[:500]}...")
        if llm_response.error:
            logger.error(f"❌ [RAG] Ошибка LLM: {llm_response.error}")
        
        # Шаг 4: Если нет источников, добавляем общие источники из whitelist
        if not sources and use_rag:
            # Если не нашли конкретные источники, показываем общие источники из whitelist
            # (если whitelist доступен)
            if hasattr(self.qdrant_loader, 'whitelist') and self.qdrant_loader.whitelist:
                allowed_urls = self.qdrant_loader.whitelist.get_allowed_urls()
                # Фильтруем только HTTP/HTTPS URL (не file://)
                web_urls = [url for url in allowed_urls if url.startswith("http")]
                if web_urls:
                    sources = web_urls
                    logger.info(f"📊 [RAG] Используются whitelist URLs как общие источники: {len(sources)} URLs")
        
        # Шаг 5: Форматируем результат
        logger.info(f"📊 [RAG] Формирование финального результата")
        logger.info(f"📊 [RAG] Источников: {len(sources)}, Контекстных документов: {len(context_docs)}")
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
            source_url = doc.get("source_url", "") or doc.get("source", "") or doc.get("filename", "") or doc.get("file_name", "")
            score = doc.get("score", 0.0)
            
            # Формат из рабочего скрипта: "Фрагмент {i} (источник: {source}, релевантность: {score:.2f}):\n{text}"
            source_name = source_url if source_url else f"Документ {i}"
            context_part = f"Фрагмент {i} (источник: {source_name}, релевантность: {score:.2f}):\n{text}"
            
            context_parts.append(context_part)
        
        return "\n\n".join(context_parts)
    
    async def close(self):
        """Закрывает ресурсы"""
        await self.llm_client.close()

