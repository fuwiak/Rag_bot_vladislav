"""
RAG цепочка для генерации ответов на основе поиска в векторной БД.
Интеграция Langchain с Qdrant и LLM.
"""

import logging
from typing import List, Dict, Any, Optional
from qdrant_loader import QdrantLoader
from llm_api import LLMClient, LLMResponse
import yaml

logger = logging.getLogger(__name__)


class RAGChain:
    """RAG цепочка для генерации ответов (Singleton)"""
    
    _instance: Optional['RAGChain'] = None
    _lock = None
    
    def __new__(
        cls,
        qdrant_loader: Optional[QdrantLoader] = None,
        llm_client: Optional[LLMClient] = None,
        config_path: str = "config.yaml",
        force_new: bool = False
    ):
        """
        Singleton паттерн - возвращает существующий экземпляр или создает новый.
        
        Args:
            force_new: Если True, создает новый экземпляр (для тестирования)
        """
        if cls._instance is None or force_new:
            if cls._lock is None:
                import threading
                cls._lock = threading.Lock()
            
            with cls._lock:
                if cls._instance is None or force_new:
                    instance = super(RAGChain, cls).__new__(cls)
                    instance._initialized = False
                    if not force_new:
                        cls._instance = instance
                    return instance
        return cls._instance
    
    def __init__(
        self,
        qdrant_loader: Optional[QdrantLoader] = None,
        llm_client: Optional[LLMClient] = None,
        config_path: str = "config.yaml",
        force_new: bool = False
    ):
        # Если уже инициализирован - не инициализируем снова
        if hasattr(self, '_initialized') and self._initialized:
            return
        
        # Загружаем конфигурацию
        self.config = self._load_config(config_path)
        
        # Используем переданный loader или получаем singleton экземпляр
        self.qdrant_loader = qdrant_loader or QdrantLoader()
        
        # Инициализируем LLM клиент с конфигурацией из config.yaml
        if llm_client is None:
            llm_config = self.config.get("llm", {})
            primary_config = llm_config.get("primary", {})
            fallback_chain_config = llm_config.get("fallback_chain", [])
            
            # Преобразуем fallback_chain из конфига в нужный формат
            fallback_chain = [
                {
                    "provider": fb.get("provider", "openrouter"),
                    "model": fb.get("model", "llama-3.3-70b-versatile")
                }
                for fb in fallback_chain_config
            ] if fallback_chain_config else None
            
            self.llm_client = LLMClient(
                primary_provider=primary_config.get("provider", "groq"),
                primary_model=primary_config.get("model", "openai/gpt-oss-120b"),
                fallback_chain=fallback_chain,
                confidence_threshold=llm_config.get("confidence_threshold", 0.7),
                timeout=primary_config.get("timeout", 30)
            )
        else:
            self.llm_client = llm_client
        
        # Параметры RAG из конфига
        rag_config = self.config.get("rag", {})
        self.top_k = rag_config.get("top_k", 5)
        self.min_score = rag_config.get("min_score", 0.7)
        
        # Параметры hybrid search
        self.search_strategy = rag_config.get("search_strategy", "hybrid")
        hybrid_weights = rag_config.get("hybrid_weights", {})
        self.dense_weight = hybrid_weights.get("dense", 0.4)
        self.bm25_weight = hybrid_weights.get("bm25", 0.6)
        
        # Параметры для поиска цен
        pricing_search = rag_config.get("pricing_search", {})
        self.pricing_search_enabled = pricing_search.get("enabled", True)
        self.pricing_strategy = pricing_search.get("strategy", "hybrid")
        self.pricing_bm25_weight = pricing_search.get("bm25_weight", 0.7)
        self.pricing_dense_weight = pricing_search.get("dense_weight", 0.3)
        self.pricing_min_score = pricing_search.get("min_score", 0.8)
        self.pricing_top_k = pricing_search.get("top_k", 10)
        
        # Системный промпт для RAG
        self.system_prompt = """Ты - полезный ассистент службы поддержки Kaspersky.
Твоя задача - отвечать на вопросы пользователей:
1. О продуктах и услугах Kaspersky (используя предоставленный контекст из официальных источников)
2. На общие вопросы (используя свои знания, если контекст не предоставлен)

Правила:
1. Если предоставлен контекст - отвечай на основе контекста
2. Если контекста нет или он не релевантен - можешь использовать свои общие знания
3. Для вопросов о Kaspersky - обязательно используй только официальные источники из контекста
4. Для общих вопросов - можешь отвечать на основе своих знаний
5. Если в контексте нет информации - честно скажи об этом
6. Отвечай на русском языке
7. Будь дружелюбным и профессиональным
8. Для вопросов о Kaspersky - в конце ответа укажи источники информации
9. Для общих вопросов - источники не нужны в ответе"""
        
        # Временные параметры для экспериментов (не сохраняются в config.yaml)
        self._temp_temperature: Optional[float] = None
        self._temp_max_tokens: Optional[int] = None
        
        # Помечаем как инициализированный (для singleton)
        self._initialized = True
    
    def _load_config(self, config_path: str) -> Dict[str, Any]:
        """Загружает конфигурацию из YAML"""
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                return yaml.safe_load(f) or {}
        except Exception as e:
            logger.error(f"Error loading config: {str(e)}")
            return {}
    
    async def query(
        self,
        user_query: str,
        use_rag: bool = True,
        top_k: Optional[int] = None,
        min_score: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Обрабатывает пользовательский запрос с использованием RAG.
        
        Args:
            user_query: Вопрос пользователя
            use_rag: Использовать ли RAG поиск
            top_k: Количество результатов поиска
            min_score: Минимальный score для результатов
        
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
            
            # Определяем стратегию поиска
            # Для запросов о ценах/прайс-листах - используем более точный поиск
            is_pricing_query = self._is_pricing_query(user_query)
            
            if is_pricing_query and self.pricing_search_enabled:
                # Используем параметры для поиска цен
                search_strategy = self.pricing_strategy
                search_top_k = self.pricing_top_k
                search_min_score = self.pricing_min_score
                search_dense_weight = self.pricing_dense_weight
                search_bm25_weight = self.pricing_bm25_weight
                logger.info(f"Using pricing search strategy: {search_strategy}")
            else:
                # Используем обычные параметры
                search_strategy = self.search_strategy
                search_top_k = top_k or self.top_k
                search_min_score = min_score or self.min_score
                search_dense_weight = self.dense_weight
                search_bm25_weight = self.bm25_weight
            
            context_docs = self.qdrant_loader.search(
                query=user_query,
                top_k=search_top_k,
                score_threshold=search_min_score,
                filter_by_whitelist=True,
                search_strategy=search_strategy,
                dense_weight=search_dense_weight,
                bm25_weight=search_bm25_weight
            )
            
            logger.info(f"Found {len(context_docs)} relevant documents")
            
            # Если нет результатов, пробуем без фильтра whitelist и с низким порогом
            if len(context_docs) == 0 and use_rag:
                logger.warning("⚠️ No documents found, retrying with lower threshold and no whitelist filter...")
                context_docs = self.qdrant_loader.search(
                    query=user_query,
                    top_k=search_top_k * 2,
                    score_threshold=0.2,  # Очень низкий порог
                    filter_by_whitelist=False,  # Без фильтра
                    search_strategy=search_strategy,
                    dense_weight=search_dense_weight,
                    bm25_weight=search_bm25_weight
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
            enhanced_prompt = f"""Контекст из официальных источников Kaspersky:

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
        # Используем временные параметры, если они установлены
        temperature = self._temp_temperature if self._temp_temperature is not None else 0.7
        max_tokens = self._temp_max_tokens if self._temp_max_tokens is not None else 2048
        llm_response = await self.llm_client.generate(
            prompt=enhanced_prompt,
            system_prompt=self.system_prompt,
            temperature=temperature,
            max_tokens=max_tokens
        )
        
        # Шаг 4: Если нет источников, добавляем общие источники из whitelist
        if not sources and use_rag:
            # Если не нашли конкретные источники, показываем общие источники из whitelist
            allowed_urls = self.qdrant_loader.whitelist.get_allowed_urls()
            # Фильтруем только HTTP/HTTPS URL (не file://)
            web_urls = [url for url in allowed_urls if url.startswith("http")]
            if web_urls:
                sources = web_urls
                logger.info(f"Using whitelist URLs as general sources: {len(sources)} URLs")
        
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
            text = doc.get("text", "")
            source_url = doc.get("source_url", "")
            score = doc.get("score", 0.0)
            
            context_part = f"[Документ {i}] (релевантность: {score:.2f})\n"
            if source_url:
                context_part += f"Источник: {source_url}\n"
            context_part += f"{text}\n"
            
            context_parts.append(context_part)
        
        return "\n---\n".join(context_parts)
    
    def _is_pricing_query(self, query: str) -> bool:
        """Определяет, является ли запрос запросом о ценах/прайс-листе"""
        pricing_keywords = [
            "цена", "стоимость", "стоит", "рублей", "руб", "прайс", "price", "cost",
            "сколько", "купить", "продажа", "прайс-лист", "pricelist"
        ]
        query_lower = query.lower()
        return any(keyword in query_lower for keyword in pricing_keywords)
    
    async def close(self):
        """Закрывает ресурсы"""
        await self.llm_client.close()

