"""
RAG сервис - поиск релевантных фрагментов и генерация ответа
"""
from typing import List, Dict, Optional
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
import logging

from app.models.project import Project
from app.models.user import User
from app.models.message import Message
from app.vector_db.vector_store import VectorStore
from app.services.embedding_service import EmbeddingService
from app.llm.openrouter_client import OpenRouterClient
from app.llm.prompt_builder import PromptBuilder
from app.llm.response_formatter import ResponseFormatter
from app.rag.rag_chain import RAGChain
from app.rag.qdrant_loader import QdrantLoader
from app.services.reranker_service import RerankerService
from app.observability.otel_setup import get_tracer
from app.observability.metrics import rag_metrics
from app.observability.structured_logging import get_logger, set_correlation_id, set_user_id, set_project_id
from app.services.cache_service import cache_service
from app.services.rag.retrieval import RAGRetrieval
from app.services.rag.fallbacks import RAGFallbacks
from app.services.rag.helpers import RAGHelpers
from app.services.rag.suggestions import RAGSuggestions
from app.core.prompt_config import get_prompt, get_constant, get_default

logger = get_logger(__name__)


class RAGService:
    """RAG сервис для генерации ответов на основе документов"""
    
    def __init__(self, db: AsyncSession):
        self.db = db
        self.vector_store = VectorStore()
        self.embedding_service = EmbeddingService()
        self.llm_client = None  # Будет создан с учетом модели проекта
        self.prompt_builder = PromptBuilder()
        self.response_formatter = ResponseFormatter()
        # Новая RAG цепочка (будет создана при необходимости)
        self._rag_chain: Optional[RAGChain] = None
        # Reranker для улучшения релевантности чанков
        self.reranker = RerankerService()
        # Refactored modules
        self.retrieval = RAGRetrieval(db, self.vector_store, self.embedding_service, self.reranker)
        self.fallbacks = RAGFallbacks(db, self.embedding_service)
        self.helpers = RAGHelpers(db)
        self.suggestions = RAGSuggestions(db, self.vector_store)
        # logger уже определен на уровне модуля
    
    async def generate_answer(
        self,
        user_id: UUID,
        question: str,
        top_k: int = 5
    ) -> str:
        """
        Сгенерировать ответ на вопрос пользователя
        
        Args:
            user_id: ID пользователя
            question: Вопрос пользователя
            top_k: Количество релевантных чанков для поиска
        
        Returns:
            Ответ на вопрос
        """
        import time
        import uuid as uuid_lib
        from app.observability.otel_setup import get_tracer
        
        # Ustawiamy kontekst dla logowania
        set_user_id(str(user_id))
        correlation_id = str(uuid_lib.uuid4())
        set_correlation_id(correlation_id)
        
        tracer = get_tracer(__name__)
        start_time = time.time()
        
        # Główny span dla całego zapytania RAG
        with tracer.start_as_current_span("rag.generate_answer") as span:
            span.set_attribute("user_id", str(user_id))
            span.set_attribute("question", question[:200])  # Ograniczamy długość
            span.set_attribute("top_k", top_k)
            
        # КРИТИЧНО: Инициализируем все переменные в самом начале функции для избежания UnboundLocalError
        chunk_texts = []
        similar_chunks = []
        metadata_context = ""
        answer = None
        user = None
        project = None
        
        try:
            # Получение пользователя и проекта
            with tracer.start_as_current_span("rag.get_user_and_project"):
                user = await self.helpers.get_user(user_id)
            if not user:
                raise ValueError(get_constant("constants.errors.user_not_found", "Пользователь не найден"))
            
            project = await self.helpers.get_project(user.project_id)
            if not project:
                raise ValueError(get_constant("constants.errors.project_not_found", "Проект не найден"))
            
            set_project_id(str(project.id))
            span.set_attribute("project_id", str(project.id))
            
            # Проверяем количество документов в проекте
            # Если документ только один, используем NLP-enhanced summarization вместо RAG
            from app.models.document import Document
            from sqlalchemy import func, select
            docs_count_result = await self.db.execute(
                select(func.count(Document.id))
                .where(Document.project_id == project.id)
            )
            documents_count = docs_count_result.scalar() or 0
            
            # Если документ только один, используем NLP-enhanced summarization
            if documents_count == 1:
                logger.info(f"[RAG SERVICE] Single document detected ({documents_count}), using NLP-enhanced summarization instead of RAG")
                return await self._generate_answer_with_nlp_summarization(
                    user_id=user_id,
                    question=question,
                    project=project
                )
            
            # Получение истории диалога (минимум 10 сообщений согласно требованиям)
            conversation_history = await self.helpers.get_conversation_history(user_id, limit=10)
            
            # Используем AI агента для определения стратегии ответа
            from app.services.rag_agent import RAGAgent
            from app.llm.openrouter_client import OpenRouterClient
            from app.models.llm_model import GlobalModelSettings
            from sqlalchemy import select
            
            # Получаем модель для агента
            settings_result = await self.db.execute(select(GlobalModelSettings).limit(1))
            global_settings = settings_result.scalar_one_or_none()
            
            primary_model = project.llm_model or (global_settings.primary_model_id if global_settings else None)
            fallback_model = global_settings.fallback_model_id if global_settings else None
            
            if not primary_model:
                from app.core.config import settings as app_settings
                primary_model = app_settings.OPENROUTER_MODEL_PRIMARY
                fallback_model = fallback_model or app_settings.OPENROUTER_MODEL_FALLBACK
            
            agent_llm = OpenRouterClient(
                model_primary=primary_model,
                model_fallback=fallback_model
            )
            rag_agent = RAGAgent(agent_llm)
            
            # Анализируем вопрос и получаем стратегию
            try:
                strategy_info = await rag_agent.get_answer_strategy(question, project.id, self.db)
                strategy = strategy_info["strategy"]
                logger.info(f"[RAG SERVICE] AI Agent strategy: {strategy.get('question_type')} - {strategy.get('recommendation')}")
            except Exception as agent_error:
                logger.warning(f"[RAG SERVICE] AI Agent failed: {agent_error}, using default strategy")
                strategy = {"use_chunks": True, "use_summaries": True, "use_metadata": True, "use_general_knowledge": True}
                strategy_info = {"documents_metadata": []}
            
            # Инициализируем переменные в начале (до всех блоков) - КРИТИЧНО для избежания UnboundLocalError
            chunk_texts = []
            similar_chunks = []
            metadata_context = ""
            
            # Определяем стратегию поиска на основе анализа агента
            collection_name = f"project_{project.id}"
            collection_exists = await self.vector_store.collection_exists(collection_name)
        
            # РАСШИРЕННЫЙ ПОИСК ЧАНКОВ - используем все техники перед fallback
            if strategy.get("use_chunks", True) and collection_exists:
                logger.info(f"[RAG SERVICE] Starting advanced chunk search with multiple techniques")
                with tracer.start_as_current_span("rag.advanced_chunk_search") as search_span:
                    search_span.set_attribute("collection_name", collection_name)
                    search_span.set_attribute("top_k", top_k)
                    
                    found_chunks, found_similar = await self.retrieval.advanced_chunk_search(
                        question=question,
                        collection_name=collection_name,
                        project_id=project.id,
                        top_k=top_k,
                        strategy=strategy
                    )
                    
                    if found_chunks:
                        chunk_texts = found_chunks
                        similar_chunks = found_similar
                        logger.info(f"[RAG SERVICE] Found {len(chunk_texts)} chunks using advanced search techniques")
                        
                        # Metryki dla retrieved chunks
                        rag_metrics.record_chunks_retrieved(
                            count=len(chunk_texts),
                            project_id=str(project.id)
                        )
                        search_span.set_attribute("chunks_found", len(chunk_texts))
            
            # Для вопросов о содержании - приоритет summaries (не используем чанки)
            question_type = strategy.get("question_type", "")
            question_lower = question.lower()
            is_content_question = (
                question_type == "содержание" or 
                any(word in question_lower for word in [
                    "содержание", "содержание документов", "обзор документов", 
                    "summary", "summary of", "summary of each", "summary of each file",
                    "обзор", "обзор файлов", "что в файлах", "список файлов"
                ])
            )
            
            # Если агент рекомендует использовать summaries или это вопрос о содержании
            if (strategy.get("use_summaries", True) and not chunk_texts) or is_content_question:
                if is_content_question:
                    logger.info(f"[RAG SERVICE] Content question detected, using summaries strategy")
                    # Для вопросов о содержании не используем чанки, только summaries
                    chunk_texts = []
                else:
                    logger.info(f"[RAG SERVICE] Using summaries strategy (AI Agent recommendation)")
                
                    summaries = await self.helpers.get_document_summaries(project.id, top_k * 2)  # Берем больше summaries для содержания
                if summaries:
                    chunk_texts = summaries  # summaries в формате dict с text, source, score
                    logger.info(f"[RAG SERVICE] Found {len(chunk_texts)} summaries")
            
            # ВСЕГДА получаем метаданные для использования в промпте (даже если есть чанки)
            # Это позволяет отвечать на вопросы о файлах и ключевых словах
            if not metadata_context:
                logger.info(f"[RAG SERVICE] Getting metadata for context")
                try:
                    from app.services.document_metadata_service import DocumentMetadataService
                    metadata_service = DocumentMetadataService()
                    documents_metadata = strategy_info.get("documents_metadata", [])
                    if not documents_metadata:
                        documents_metadata = await metadata_service.get_documents_metadata(project.id, self.db)
                    if documents_metadata:
                        metadata_context = metadata_service.create_metadata_context(documents_metadata)
                        logger.info(f"[RAG SERVICE] Created metadata context from {len(documents_metadata)} documents")
                except Exception as metadata_error:
                    logger.warning(f"[RAG SERVICE] Error getting metadata: {metadata_error}")
            
            # Логируем стратегию использования метаданных
            if metadata_context:
                if not chunk_texts:
                    logger.info(f"[RAG SERVICE] Using metadata as primary source (no chunks available)")
                else:
                    logger.info(f"[RAG SERVICE] Using metadata as additional context (chunks available)")
            
            # Если нет чанков, пытаемся извлечь контент напрямую из документов разными способами
            # Используем все стратегии fallback: Late Chunking, Sub-agents, Overlapping Chunks
            if not chunk_texts:
                logger.info(f"[RAG SERVICE] No chunks found, trying all fallback strategies: Late Chunking, Sub-agents, Overlapping Chunks")
                try:
                    from app.models.document import Document, DocumentChunk
                    from app.documents.chunker import DocumentChunker
                    from sqlalchemy import select, text
                    import re
                    
                    # Техника 1: Пытаемся получить чанки из БД (DocumentChunk)
                    try:
                        result = await self.db.execute(
                            select(DocumentChunk)
                            .join(Document)
                            .where(Document.project_id == project.id)
                            .where(DocumentChunk.chunk_text.isnot(None))
                            .where(DocumentChunk.chunk_text != "")
                            .limit(top_k * 2)
                        )
                        db_chunks = result.scalars().all()
                        
                        if db_chunks:
                            # Извлекаем ключевые слова из вопроса для релевантности
                            question_keywords = set(re.findall(r'\b\w+\b', question.lower()))
                            question_keywords = {w for w in question_keywords if len(w) > 3}  # Слова длиннее 3 символов
                            
                            for chunk in db_chunks:
                                chunk_text_lower = chunk.chunk_text.lower()
                                # Вычисляем релевантность по количеству совпадающих ключевых слов
                                relevance = sum(1 for kw in question_keywords if kw in chunk_text_lower)
                                score = min(0.9, 0.5 + (relevance * 0.1))
                                
                                chunk_texts.append({
                                    "text": chunk.chunk_text,
                                    "source": chunk.document.filename if chunk.document else "Документ",
                                    "score": score
                                })
                            
                            if chunk_texts:
                                logger.info(f"[RAG SERVICE] Extracted {len(chunk_texts)} chunks from DocumentChunk table")
                    except Exception as chunk_error:
                        logger.warning(f"[RAG SERVICE] Error getting chunks from DB: {chunk_error}")
                    
                    # Техника 2: Если нет чанков в БД, получаем документы и используем chunking
                    if not chunk_texts:
                        try:
                            result = await self.db.execute(
                                select(Document)
                                .where(Document.project_id == project.id)
                                .where(Document.content.isnot(None))
                                .where(Document.content != "")
                                .where(Document.content.notin_([
                                    get_constant("constants.document_status.processing", "Обработка..."),
                                    get_constant("constants.document_status.processed", "Обработан")
                                ]))
                                .limit(10)
                            )
                            documents = result.scalars().all()
                        except Exception:
                            # Fallback на raw SQL
                            processing_status = get_constant("constants.document_status.processing", "Обработка...")
                            processed_status = get_constant("constants.document_status.processed", "Обработан")
                            result = await self.db.execute(
                                text("""
                                    SELECT id, filename, content, file_type 
                                    FROM documents 
                                    WHERE project_id = :project_id 
                                    AND content IS NOT NULL 
                                    AND content != '' 
                                    AND content NOT IN (:processing_status, :processed_status)
                                    LIMIT 10
                                """),
                                {
                                    "project_id": str(project.id),
                                    "processing_status": processing_status,
                                    "processed_status": processed_status
                                }
                            )
                            rows = result.all()
                            documents = []
                            for row in rows:
                                doc = Document()
                                doc.id = row[0]
                                doc.filename = row[1]
                                doc.content = row[2]
                                doc.file_type = row[3]
                                documents.append(doc)
                    
                    # Используем DocumentChunker для разбивки на чанки с большим overlap (50-75%)
                    # Overlapping Chunks z kontekstem - улучшенный chunking
                    chunker = DocumentChunker(chunk_size=1000, chunk_overlap=500)  # 50% overlap
                    question_keywords = set(re.findall(r'\b\w+\b', question.lower()))
                    question_keywords = {w for w in question_keywords if len(w) > 3}
                    
                    for doc in documents:
                        if doc.content and len(doc.content) > 50:
                            # Разбиваем на чанки
                            doc_chunks = chunker.chunk_text(doc.content)
                            
                            # Если вопрос содержит название файла, используем все чанки
                            is_relevant_file = doc.filename.lower() in question.lower()
                            
                            for chunk_text in doc_chunks[:5]:  # Максимум 5 чанков из каждого документа
                                # Вычисляем релевантность
                                chunk_lower = chunk_text.lower()
                                relevance = sum(1 for kw in question_keywords if kw in chunk_lower)
                                score = 0.9 if is_relevant_file else min(0.8, 0.5 + (relevance * 0.1))
                                
                                chunk_texts.append({
                                    "text": chunk_text,
                                    "source": doc.filename,
                                    "score": score
                                })
                            
                            logger.info(f"[RAG SERVICE] Extracted {len(doc_chunks)} chunks from document {doc.filename} using chunker")
                    
                    if chunk_texts:
                        logger.info(f"[RAG SERVICE] Extracted {len(chunk_texts)} content chunks using DocumentChunker")
                    
                    # Техника 3: Если все еще нет чанков, используем простой preview
                    if not chunk_texts:
                        try:
                            result = await self.db.execute(
                                select(Document)
                                .where(Document.project_id == project.id)
                                .limit(5)
                            )
                            documents = result.scalars().all()
                            
                            for doc in documents:
                                if doc.content and len(doc.content) > 50:
                                    # Простой preview - первые 1000 символов
                                    content_preview = doc.content[:1000]
                                    if len(doc.content) > 1000:
                                        content_preview += "..."
                                    
                                    is_relevant = doc.filename.lower() in question.lower()
                                    chunk_texts.append({
                                        "text": f"Документ '{doc.filename}':\n{content_preview}",
                                        "source": doc.filename,
                                        "score": 0.7 if is_relevant else 0.4
                                    })
                            
                            if chunk_texts:
                                logger.info(f"[RAG SERVICE] Extracted {len(chunk_texts)} content previews")
                        except Exception as preview_error:
                            logger.warning(f"[RAG SERVICE] Error extracting previews: {preview_error}")
                except Exception as fallback_error:
                    logger.warning(f"[RAG SERVICE] Fallback strategies failed: {fallback_error}")
                
                # Если все еще нет чанков после всех техник, пробуем Late Chunking
                    if not chunk_texts:
                        logger.info(f"[RAG SERVICE] Still no chunks after extraction techniques, trying Late Chunking")
                        try:
                            # Late Chunking - создаем embedding всего документа
                            from app.models.document import Document
                            from sqlalchemy import select
                            import numpy as np
                            
                            result = await self.db.execute(
                                select(Document)
                                .where(Document.project_id == project.id)
                                .where(Document.content.isnot(None))
                                .where(Document.content != "")
                                .where(Document.content.notin_([
                                    get_constant("constants.document_status.processing", "Обработка..."),
                                    get_constant("constants.document_status.processed", "Обработан")
                                ]))
                                .limit(2)
                            )
                            documents = result.scalars().all()
                            
                            if documents:
                                # Создаем эмбеддинг вопроса
                                question_embedding = await self.embedding_service.create_embedding(question)
                                
                                # Для каждого документа создаем эмбеддинг всего документа
                                best_doc = None
                                best_score = 0.0
                                
                                for doc in documents:
                                    if doc.content and len(doc.content) > 100:
                                        # Создаем эмбеддинг всего документа (первые 8000 символов)
                                        doc_content = doc.content[:8000]
                                        doc_embedding = await self.embedding_service.create_embedding(doc_content)
                                        
                                        # Вычисляем косинусное сходство
                                        similarity = np.dot(question_embedding, doc_embedding) / (
                                            np.linalg.norm(question_embedding) * np.linalg.norm(doc_embedding)
                                        )
                                        
                                        if similarity > best_score:
                                            best_score = similarity
                                            best_doc = doc
                            
                            # Если нашли релевантный документ, используем его первые 5000 символов как чанк
                            if best_doc and best_score > 0.3:
                                doc_content = best_doc.content[:5000]
                                if len(best_doc.content) > 5000:
                                    doc_content += "..."
                                
                                chunk_texts.append({
                                    "text": doc_content,
                                    "source": best_doc.filename,
                                    "score": best_score
                                })
                                logger.info(f"[RAG SERVICE] Late chunking found relevant document '{best_doc.filename}' with score {best_score:.2f}")
                        except Exception as late_error:
                            logger.warning(f"[RAG SERVICE] Late chunking failed: {late_error}")
            
            # Инициализируем chunks_for_prompt для использования в блоке else
            chunks_for_prompt = []
            for chunk in chunk_texts:
                if isinstance(chunk, dict):
                    chunks_for_prompt.append(chunk.get("text", str(chunk)))
                else:
                    chunks_for_prompt.append(chunk)
            
            # Для вопросов о содержании используем простой промпт из рабочего скрипта
            if is_content_question:
                # Для вопросов типа "summary of each file" - используем метаданные напрямую
                if metadata_context and not chunk_texts:
                    # Просто используем метаданные - это работает как предложенные вопросы
                    logger.info(f"[RAG SERVICE] Content question with metadata only - using direct metadata approach")
                    context = get_prompt("prompts.content_question.metadata_only", metadata_context=metadata_context)
                    
                    enhanced_prompt = f"""Вопрос пользователя: {question}

Используй информацию о документах выше для ответа. Если вопрос о summary каждого файла, предоставь краткое описание каждого файла на основе его названия и ключевых слов.

Ответ:"""
                    
                    messages = [
                        {"role": "system", "content": get_prompt("prompts.system.metadata_assistant")},
                        {"role": "user", "content": enhanced_prompt}
                    ]
                elif chunk_texts:
                    # Есть summaries или извлеченный контент - используем их
                    context_parts = []
                    for i, doc in enumerate(chunk_texts, 1):
                        if isinstance(doc, dict):
                            source = doc.get("source", "Документ")
                            text = doc.get("text", "")
                            score = doc.get("score", 1.0)
                            context_parts.append(f"Фрагмент {i} (источник: {source}, релевантность: {score:.2f}):\n{text}")
                        else:
                            context_parts.append(f"Фрагмент {i}:\n{doc}")
                    
                    context = "\n\n".join(context_parts)
                    
                    # Добавляем метаданные для дополнительного контекста
                    if metadata_context:
                        context += f"\n\nДополнительная информация о документах:\n{metadata_context}"
                    
                    enhanced_prompt = get_prompt("prompts.content_question.with_chunks", context=context, question=question)
                    
                    messages = [
                        {"role": "system", "content": get_prompt("prompts.system.document_assistant")},
                        {"role": "user", "content": enhanced_prompt}
                    ]
            elif metadata_context:
                # Нет summaries, но есть метаданные - используем их
                context = get_prompt("prompts.metadata.prompt", metadata_context=metadata_context)
                
                enhanced_prompt = get_prompt("prompts.metadata.user_prompt", question=question)
                
                messages = [
                    {"role": "system", "content": get_prompt("prompts.system.metadata_assistant")},
                    {"role": "user", "content": enhanced_prompt}
                ]
            else:
                # Нет ни summaries, ни метаданных
                context = get_constant("constants.errors.documents_processing", "Документы еще обрабатываются. Доступна только информация о загруженных файлах.")
                enhanced_prompt = f"""Вопрос: {question}

Контекст: {context}

Ответ:"""
                
                messages = [
                    {"role": "system", "content": get_prompt("prompts.system.basic_assistant")},
                    {"role": "user", "content": enhanced_prompt}
                ]
            
            # Добавляем историю диалога
            if conversation_history:
                recent_history = conversation_history[-4:]  # Последние 2 пары вопрос-ответ
                # Вставляем историю перед финальным вопросом
                messages = [messages[0]] + recent_history + [messages[1]]
            else:
                # ВСЕГДА используем промпт проекта, даже если документов нет
                # Это позволяет боту отвечать на основе общих знаний, но с учетом настроек проекта
                # Построение промпта с контекстом (может быть пустым)
                # chunks_for_prompt уже определен выше
                
                messages = self.prompt_builder.build_prompt(
                    question=question,
                    chunks=chunks_for_prompt,  # Может быть пустым списком
                    prompt_template=project.prompt_template,
                    max_length=project.max_response_length,
                    conversation_history=conversation_history,
                    metadata_context=metadata_context  # Добавляем метаданные если есть
                )
            
            # Генерация ответа через LLM
            # Получаем глобальные настройки моделей из БД
            from app.models.llm_model import GlobalModelSettings
            from sqlalchemy import select
            # logger уже определен на уровне модуля
            
            settings_result = await self.db.execute(select(GlobalModelSettings).limit(1))
            global_settings = settings_result.scalar_one_or_none()
            
            logger.info(f"[RAG SERVICE] Global settings from DB: primary={global_settings.primary_model_id if global_settings else 'None'}, fallback={global_settings.fallback_model_id if global_settings else 'None'}")
            
            # Определяем primary и fallback модели
            # Приоритет: 1) модель проекта, 2) глобальные настройки из БД, 3) дефолты из .env
            primary_model = None
            fallback_model = None
            
            if project.llm_model:
                # Если у проекта есть своя модель, используем её как primary
                primary_model = project.llm_model
                logger.info(f"[RAG SERVICE] Using project model: {primary_model}")
                # Fallback берем из глобальных настроек БД
                if global_settings and global_settings.fallback_model_id:
                    fallback_model = global_settings.fallback_model_id
                    logger.info(f"[RAG SERVICE] Using global fallback from DB: {fallback_model}")
                else:
                    # Если в БД нет fallback, используем дефолт из .env
                    from app.core.config import settings as app_settings
                    fallback_model = app_settings.OPENROUTER_MODEL_FALLBACK
                    logger.info(f"[RAG SERVICE] Using default fallback from .env: {fallback_model}")
            else:
                # Используем глобальные настройки из БД
                if global_settings:
                    primary_model = global_settings.primary_model_id
                    fallback_model = global_settings.fallback_model_id
                    logger.info(f"[RAG SERVICE] Using global models from DB: primary={primary_model}, fallback={fallback_model}")
                
                # Если глобальных настроек нет или модели не установлены, используем дефолтные из .env
                from app.core.config import settings as app_settings
                if not primary_model:
                    primary_model = app_settings.OPENROUTER_MODEL_PRIMARY
                    logger.info(f"[RAG SERVICE] Using default primary from .env: {primary_model}")
                if not fallback_model:
                    fallback_model = app_settings.OPENROUTER_MODEL_FALLBACK
                    logger.info(f"[RAG SERVICE] Using default fallback from .env: {fallback_model}")
            
            # Создаем клиент с моделями
            llm_client = OpenRouterClient(
                model_primary=primary_model,
                model_fallback=fallback_model
            )
            max_tokens = project.max_response_length // 4  # Приблизительная оценка токенов
            
            # Генерируем ответ
            try:
                raw_answer = await llm_client.chat_completion(
                    messages=messages,
                    max_tokens=max_tokens,
                    temperature=0.7
                )
                
                # Проверяем, не является ли ответ отказом
                answer_text = raw_answer.strip().lower()
                refusal_phrases = get_constant("constants.refusal_phrases", [
                    "нет информации", "не могу ответить", "не нашел", 
                    "не найдено", "нет данных", "недостаточно информации",
                    "нет релевантной информации", "не удалось найти"
                ])
                
                # Если ответ содержит отказ и у нас есть метаданные - генерируем сводку
                if any(phrase in answer_text for phrase in refusal_phrases) and metadata_context:
                    logger.info(f"[RAG SERVICE] Answer contains refusal, generating document summary as fallback")
                    answer = await self.fallbacks.generate_document_summary_fallback(
                        question=question,
                        metadata_context=metadata_context,
                        project=project,
                        llm_client=llm_client,
                        max_tokens=max_tokens
                    )
                else:
                    # Форматирование ответа с добавлением цитат (согласно ТЗ п. 5.3.4)
                    answer = self.response_formatter.format_response(
                        response=raw_answer,
                        max_length=project.max_response_length,
                        chunks=similar_chunks if 'similar_chunks' in locals() else []
                    )
            except Exception as llm_error:
                logger.warning(f"[RAG SERVICE] LLM error: {llm_error}, trying aggressive fallback with all techniques")
                # АГРЕССИВНЫЙ FALLBACK - используем все техники перед отказом
                answer = None
                
                # Fallback 1: Пытаемся получить метаданные и сгенерировать сводку
                if not metadata_context:
                    try:
                        from app.services.document_metadata_service import DocumentMetadataService
                        metadata_service = DocumentMetadataService()
                        documents_metadata = await metadata_service.get_documents_metadata(project.id, self.db)
                        if documents_metadata:
                            metadata_context = metadata_service.create_metadata_context(documents_metadata)
                    except Exception as meta_error:
                        logger.warning(f"[RAG SERVICE] Error getting metadata for fallback: {meta_error}")
                
                if metadata_context:
                    try:
                        answer = await self.fallbacks.generate_document_summary_fallback(
                            question=question,
                            metadata_context=metadata_context,
                            project=project,
                            llm_client=llm_client,
                            max_tokens=max_tokens
                        )
                    except Exception as fallback_error:
                        logger.warning(f"[RAG SERVICE] Document summary fallback failed: {fallback_error}")
                
                # Fallback 2: Sub-agents для целых документов - обработка целых документов
                if not answer:
                    logger.info(f"[RAG SERVICE] Trying sub-agent for full document processing")
                    try:
                        answer = await self.fallbacks.process_full_documents_with_subagent(
                            question=question,
                            project=project,
                            llm_client=llm_client,
                            max_tokens=max_tokens
                        )
                    except Exception as subagent_error:
                        logger.warning(f"[RAG SERVICE] Sub-agent fallback failed: {subagent_error}")
                
                # Fallback 3: Late Chunking - обработка через long-context embedding
                if not answer:
                    logger.info(f"[RAG SERVICE] Trying late chunking approach")
                    try:
                        answer = await self.fallbacks.late_chunking_fallback(
                            question=question,
                            project=project,
                            llm_client=llm_client,
                            max_tokens=max_tokens
                        )
                    except Exception as late_chunking_error:
                        logger.warning(f"[RAG SERVICE] Late chunking fallback failed: {late_chunking_error}")
                
                # Fallback 4: Если все еще нет ответа, используем AI агента для генерации ответа
                if not answer:
                    try:
                        answer = await self.fallbacks.generate_ai_agent_fallback(
                            question=question,
                            project=project,
                            llm_client=llm_client,
                            max_tokens=max_tokens,
                            conversation_history=conversation_history
                        )
                    except Exception as ai_error:
                        logger.warning(f"[RAG SERVICE] AI agent fallback failed: {ai_error}")
                
                # Fallback 5: Базовый ответ на основе названия проекта
                if not answer:
                    answer = await self.fallbacks.generate_basic_fallback(
                        question=question,
                        project=project
                    )
                
            # Только в самом крайнем случае возвращаем сообщение об ошибке
            if not answer:
                logger.error(f"[RAG SERVICE] All fallback mechanisms failed for question: {question}")
                answer = get_constant("constants.errors.processing_error", "Извините, произошла ошибка при обработке вашего вопроса. Пожалуйста, попробуйте переформулировать вопрос или обратитесь к администратору.")
            
            # Сохранение сообщений в историю
            await self.helpers.save_message(user_id, question, "user")
            await self.helpers.save_message(user_id, answer, "assistant")
            
            # Zapisujemy odpowiedź do cache
            if project:
                await cache_service.set_rag_response(question, answer, str(project.id))
            
            # Zapisujemy metryki
            duration = time.time() - start_time
            rag_metrics.record_query_duration(
                duration=duration,
                project_id=str(project.id) if project else None,
                status="success"
            )
            rag_metrics.increment_query(
                project_id=str(project.id) if project else None,
                status="success"
            )
            span.set_attribute("duration", duration)
            span.set_attribute("status", "success")
            
            return answer
        except Exception as e:
            duration = time.time() - start_time
            logger.error(f"[RAG SERVICE] Error in generate_answer: {e}", exc_info=True)
            span.record_exception(e)
            span.set_attribute("status", "error")
            span.set_attribute("error.message", str(e))
            
            # Metryki dla błędu
            rag_metrics.record_query_duration(
                duration=duration,
                project_id=str(project.id) if project else None,
                status="error"
            )
            rag_metrics.increment_query(
                project_id=str(project.id) if project else None,
                status="error"
            )
            
            # В случае критической ошибки возвращаем базовый ответ
            if not answer:
                answer = get_constant("constants.errors.processing_error", "Извините, произошла ошибка при обработке вашего вопроса. Пожалуйста, попробуйте переформулировать вопрос или обратитесь к администратору.")
            # Сохраняем сообщения даже при ошибке
            try:
                await self.helpers.save_message(user_id, question, "user")
                await self.helpers.save_message(user_id, answer, "assistant")
            except:
                pass
            return answer
    
    
    
    
    
    
    
    
    async def generate_answer_fast(
        self,
        user_id: UUID,
        question: str,
        top_k: int = 3
    ) -> str:
        """
        Быстрая генерация ответа с ограниченным размером (для случаев превышения таймаута)
        
        Args:
            user_id: ID пользователя
            question: Вопрос пользователя
            top_k: Количество релевантных чанков (уменьшено для скорости)
        
        Returns:
            Короткий ответ на вопрос
        """
        # Получение пользователя и проекта
        user = await self.helpers.get_user(user_id)
        if not user:
            raise ValueError(get_constant("constants.errors.user_not_found", "Пользователь не найден"))
        
        project = await self.helpers.get_project(user.project_id)
        if not project:
            raise ValueError(get_constant("constants.errors.project_not_found", "Проект не найден"))
        
        # Создание эмбеддинга вопроса
        question_embedding = await self.embedding_service.create_embedding(question)
        
        # Поиск релевантных чанков (меньше чанков для скорости)
        collection_name = f"project_{project.id}"
        similar_chunks = await self.vector_store.search_similar(
            collection_name=collection_name,
            query_vector=question_embedding,
            limit=top_k,
            score_threshold=0.5
        )
        
        # Если релевантных чанков нет - генерируем сводку документов
        if not similar_chunks or len(similar_chunks) == 0:
            logger.info(f"[RAG SERVICE FAST] No chunks found, generating document summary")
            try:
                from app.services.document_metadata_service import DocumentMetadataService
                metadata_service = DocumentMetadataService()
                documents_metadata = await metadata_service.get_documents_metadata(project.id, self.db)
                if documents_metadata:
                    metadata_context = metadata_service.create_metadata_context(documents_metadata)
                    return await self.fallbacks.generate_document_summary_fallback(
                        question=question,
                        metadata_context=metadata_context,
                        project=project,
                        llm_client=None,  # Будет создан внутри
                        max_tokens=500
                    )
            except Exception as e:
                logger.warning(f"[RAG SERVICE FAST] Error generating summary fallback: {e}")
            
            # АГРЕССИВНЫЙ FALLBACK - используем все техники перед отказом
            logger.warning(f"[RAG SERVICE FAST] All techniques failed, trying aggressive fallback")
            try:
                # Пытаемся получить хотя бы метаданные и сгенерировать ответ
                from app.services.document_metadata_service import DocumentMetadataService
                metadata_service = DocumentMetadataService()
                documents_metadata = await metadata_service.get_documents_metadata(project.id, self.db)
                if documents_metadata:
                    metadata_context = metadata_service.create_metadata_context(documents_metadata)
                    return await self.fallbacks.generate_document_summary_fallback(
                        question=question,
                        metadata_context=metadata_context,
                        project=project,
                        llm_client=None,
                        max_tokens=500
                    )
            except Exception as e2:
                logger.warning(f"[RAG SERVICE FAST] Aggressive fallback failed: {e2}")
            
            # Fallback 4: Sub-agents dla całych документов - обработка целых документов
            if not answer:
                logger.info(f"[RAG SERVICE FAST] Trying sub-agent for full document processing")
                try:
                    answer = await self.fallbacks.process_full_documents_with_subagent(
                        question=question,
                        project=project,
                        llm_client=None,
                        max_tokens=500
                    )
                except Exception as subagent_error:
                    logger.warning(f"[RAG SERVICE FAST] Sub-agent fallback failed: {subagent_error}")
            
            # Fallback 5: Late Chunking - обработка через long-context embedding
            if not answer:
                logger.info(f"[RAG SERVICE FAST] Trying late chunking approach")
                try:
                    answer = await self.fallbacks.late_chunking_fallback(
                        question=question,
                        project=project,
                        llm_client=None,
                        max_tokens=500
                    )
                except Exception as late_chunking_error:
                    logger.warning(f"[RAG SERVICE FAST] Late chunking fallback failed: {late_chunking_error}")
            
            # Только в самом крайнем случае возвращаем финальное сообщение
            if not answer:
                return get_constant("constants.errors.no_information", "В загруженных документах нет информации по этому вопросу.")
            
            return answer
        
        # Извлечение текстов чанков
        chunk_texts = [chunk["payload"]["chunk_text"] for chunk in similar_chunks[:2]]  # Только 2 чанка
        
        # Построение упрощенного промпта
        short_answer = get_constant("constants.fast_response.short_answer", "Отвечай кратко, не более 500 символов.")
        question_prefix = get_constant("constants.fast_response.question_prefix", "Вопрос: {question}\n\nКонтекст:\n")
        messages = [
            {
                "role": "system",
                "content": f"{project.prompt_template}\n\n{short_answer}"
            },
            {
                "role": "user",
                "content": question_prefix.format(question=question) + "\n\n".join(chunk_texts)
            }
        ]
        
        # Быстрая генерация с ограниченным размером
        from app.models.llm_model import GlobalModelSettings
        from sqlalchemy import select
        # logger уже определен на уровне модуля
        
        settings_result = await self.db.execute(select(GlobalModelSettings).limit(1))
        global_settings = settings_result.scalar_one_or_none()
        
        logger.info(f"[RAG SERVICE FAST] Global settings from DB: primary={global_settings.primary_model_id if global_settings else 'None'}, fallback={global_settings.fallback_model_id if global_settings else 'None'}")
        
        primary_model = None
        fallback_model = None
        
        # Приоритет: 1) модель проекта, 2) глобальные настройки из БД, 3) дефолты из .env
        if project.llm_model:
            primary_model = project.llm_model
            logger.info(f"[RAG SERVICE FAST] Using project model: {primary_model}")
            if global_settings and global_settings.fallback_model_id:
                fallback_model = global_settings.fallback_model_id
                logger.info(f"[RAG SERVICE FAST] Using global fallback from DB: {fallback_model}")
            else:
                from app.core.config import settings as app_settings
                fallback_model = app_settings.OPENROUTER_MODEL_FALLBACK
                logger.info(f"[RAG SERVICE FAST] Using default fallback from .env: {fallback_model}")
        elif global_settings:
            primary_model = global_settings.primary_model_id
            fallback_model = global_settings.fallback_model_id
            logger.info(f"[RAG SERVICE FAST] Using global models from DB: primary={primary_model}, fallback={fallback_model}")
        
        from app.core.config import settings as app_settings
        if not primary_model:
            primary_model = app_settings.OPENROUTER_MODEL_PRIMARY
            logger.info(f"[RAG SERVICE FAST] Using default primary from .env: {primary_model}")
        if not fallback_model:
            fallback_model = app_settings.OPENROUTER_MODEL_FALLBACK
            logger.info(f"[RAG SERVICE FAST] Using default fallback from .env: {fallback_model}")
        
        logger.info(f"[RAG SERVICE FAST] Final models - primary={primary_model}, fallback={fallback_model}")
        
        from app.llm.openrouter_client import OpenRouterClient
        llm_client = OpenRouterClient(
            model_primary=primary_model,
            model_fallback=fallback_model
        )
        
        # Ограничиваем max_tokens для быстрого ответа
        raw_answer = await llm_client.chat_completion(
            messages=messages,
            max_tokens=200,  # Очень ограниченный размер
            temperature=0.7
        )
        
        # Форматирование ответа с ограничением длины
        answer = self.response_formatter.format_response(
            response=raw_answer,
            max_length=min(project.max_response_length, 500),  # Максимум 500 символов
            chunks=similar_chunks
        )
        
        # Сохранение сообщений в историю
        await self.helpers.save_message(user_id, question, "user")
        await self.helpers.save_message(user_id, answer, "assistant")
        
        return answer
    
    
    
    
    
    
    
    
    
    async def generate_suggested_questions(
        self,
        project_id: UUID,
        limit: int = 5
    ) -> List[str]:
        """
        Генерировать предложенные вопросы на основе загруженных документов
        
        Args:
            project_id: ID проекта
            limit: Количество предложенных вопросов
        
        Returns:
            Список предложенных вопросов
        """
        collection_name = f"project_{project_id}"
        
        try:
            # Сначала пытаемся получить чанки из Qdrant (если документы уже проиндексированы)
            chunk_texts = []
            collection_exists = await self.vector_store.collection_exists(collection_name)
            
            if collection_exists:
                # Пытаемся получить несколько случайных точек из коллекции Qdrant
                try:
                    # Получаем клиент Qdrant через wrapper
                    from app.vector_db.qdrant_client import QdrantClientWrapper
                    qdrant_wrapper = QdrantClientWrapper()
                    qdrant_client = qdrant_wrapper.get_client()
                    
                    # Получаем несколько случайных точек из коллекции через scroll
                    scroll_result = qdrant_client.scroll(
                        collection_name=collection_name,
                        limit=10,
                        with_payload=True,
                        with_vectors=False
                    )
                    
                    if scroll_result and len(scroll_result[0]) > 0:
                        for point in scroll_result[0][:10]:
                            if point.payload and 'chunk_text' in point.payload:
                                chunk_text = point.payload['chunk_text']
                                if chunk_text:
                                    chunk_texts.append(chunk_text[:500])
                        logger.info(f"[RAG SERVICE] Found {len(chunk_texts)} chunks in Qdrant for project {project_id}")
                except Exception as qdrant_error:
                    logger.warning(f"[RAG SERVICE] Error reading from Qdrant: {qdrant_error}, trying DB")
            
            # Если не нашли в Qdrant, пытаемся из БД
            if not chunk_texts:
                from app.models.document import Document, DocumentChunk
                from app.services.document_summary_service import DocumentSummaryService
                
                # Получаем документы проекта (безопасно, даже если поле summary отсутствует)
                try:
                    # Пробуем обычный запрос
                    result = await self.db.execute(
                        select(Document)
                        .where(Document.project_id == project_id)
                        .limit(10)
                    )
                    documents = result.scalars().all()
                except Exception as db_error:
                    # Если ошибка из-за отсутствия поля summary, используем raw SQL
                    error_str = str(db_error).lower()
                    if "summary" in error_str or "column" in error_str:
                        logger.warning(f"[RAG SERVICE] Summary column not found in DB, using raw SQL query")
                        # Используем raw SQL для получения документов без summary
                        from sqlalchemy import text
                        try:
                            result = await self.db.execute(
                                text("SELECT id, project_id, filename, content, file_type, created_at FROM documents WHERE project_id = :project_id LIMIT 10"),
                                {"project_id": str(project_id)}
                            )
                            # Преобразуем результаты в объекты Document вручную
                            documents = []
                            for row in result:
                                doc = Document()
                                doc.id = row[0]
                                doc.project_id = row[1]
                                doc.filename = row[2]
                                doc.content = row[3] if row[3] else ""
                                doc.file_type = row[4]
                                doc.created_at = row[5]
                                # Поле summary отсутствует - устанавливаем None через setattr
                                try:
                                    setattr(doc, 'summary', None)
                                except:
                                    pass
                                documents.append(doc)
                        except Exception as sql_error:
                            logger.error(f"[RAG SERVICE] Error with raw SQL query: {sql_error}")
                            documents = []
                    else:
                        # Другая ошибка - пробрасываем дальше
                        raise
                
                if not documents:
                    logger.info(f"[RAG SERVICE] No documents found for project {project_id}")
                    return []
                
                logger.info(f"[RAG SERVICE] Found {len(documents)} documents in DB for project {project_id}")
                
                # Получаем несколько чанков из разных документов
                for doc in documents[:5]:  # Берем максимум 5 документов
                    chunks_result = await self.db.execute(
                        select(DocumentChunk)
                        .where(DocumentChunk.document_id == doc.id)
                        .limit(3)  # По 3 чанка из каждого документа
                    )
                    chunks = chunks_result.scalars().all()
                    for chunk in chunks:
                        if chunk.chunk_text:
                            chunk_texts.append(chunk.chunk_text[:500])  # Ограничиваем длину
                
                # Если чанков нет в БД, используем summaries или содержимое документов
                if not chunk_texts:
                    logger.info(f"[RAG SERVICE] No chunks in DB, using summaries or document content")
                    summary_service = DocumentSummaryService(self.db)
                    
                    for doc in documents[:5]:
                        # Приоритет 1: используем summary если есть (проверяем безопасно)
                        doc_summary = getattr(doc, 'summary', None)
                        if doc_summary and doc_summary.strip():
                            chunk_texts.append(f"Документ '{doc.filename}': {doc_summary}")
                        else:
                            # Приоритет 2: пытаемся создать summary (только если поле существует в БД)
                            try:
                                # Проверяем, существует ли поле summary в модели
                                if hasattr(Document, 'summary'):
                                    summary = await summary_service.generate_summary(doc.id)
                                    if summary and summary.strip():
                                        chunk_texts.append(f"Документ '{doc.filename}': {summary}")
                                        continue
                            except Exception as e:
                                logger.warning(f"Error generating summary for doc {doc.id}: {e}")
                            
                        # Приоритет 3: используем содержимое напрямую
                        processing_status = get_constant("constants.document_status.processing", "Обработка...")
                        processed_status = get_constant("constants.document_status.processed", "Обработан")
                        if doc.content and doc.content not in [processing_status, processed_status, ""]:
                            # Берем первые 1000 символов из содержимого
                            content = doc.content[:1000]
                            if content.strip():
                                chunk_texts.append(f"Документ '{doc.filename}': {content}")
            
            if not chunk_texts:
                logger.warning(f"[RAG SERVICE] No content found for project {project_id} - documents may still be processing")
                # Используем метаданные документов для генерации вопросов
                try:
                    from app.services.document_metadata_service import DocumentMetadataService
                    metadata_service = DocumentMetadataService()
                    documents_metadata = await metadata_service.get_documents_metadata(project_id, self.db)
                    if documents_metadata:
                        # Создаем контекст из метаданных
                        metadata_context = metadata_service.create_metadata_context(documents_metadata)
                        # Извлекаем ключевые слова из всех документов
                        all_keywords = []
                        for doc_meta in documents_metadata:
                            all_keywords.extend(doc_meta.get("keywords", []))
                        # Используем уникальные ключевые слова как контекст
                        unique_keywords = list(set(all_keywords))[:20]
                        if unique_keywords:
                            chunk_texts = [f"Доступные документы: {metadata_context}\nКлючевые слова: {', '.join(unique_keywords)}"]
                            logger.info(f"[RAG SERVICE] Using metadata context with {len(unique_keywords)} keywords")
                except Exception as metadata_error:
                    logger.warning(f"[RAG SERVICE] Error getting metadata for questions: {metadata_error}")
                
                if not chunk_texts:
                    return []
            
            # Объединяем чанки в контекст
            context = "\n\n".join(chunk_texts[:10])  # Максимум 10 чанков
            
            # Используем LLM для генерации вопросов на основе контекста
            project_result = await self.db.execute(
                select(Project).where(Project.id == project_id)
            )
            project = project_result.scalar_one_or_none()
            
            if not project:
                return []
            
            # Получаем настройки моделей
            from app.models.llm_model import GlobalModelSettings
            settings_result = await self.db.execute(select(GlobalModelSettings).limit(1))
            global_settings = settings_result.scalar_one_or_none()
            
            primary_model = None
            fallback_model = None
            
            if project.llm_model:
                primary_model = project.llm_model
            elif global_settings:
                primary_model = global_settings.primary_model_id
                fallback_model = global_settings.fallback_model_id
            
            from app.core.config import settings as app_settings
            if not primary_model:
                primary_model = app_settings.OPENROUTER_MODEL_PRIMARY
            if not fallback_model:
                fallback_model = app_settings.OPENROUTER_MODEL_FALLBACK
            
            llm_client = OpenRouterClient(
                model_primary=primary_model,
                model_fallback=fallback_model
            )
            
            # Промпт для генерации вопросов
            prompt = get_prompt("prompts.suggested_questions.prompt", limit=limit, context=context[:2000])
            
            messages = [
                {"role": "system", "content": get_prompt("prompts.system.question_generator")},
                {"role": "user", "content": prompt}
            ]
            
            response = await llm_client.chat_completion(
                messages=messages,
                max_tokens=500,
                temperature=0.8
            )
            
            # Парсим вопросы из ответа
            questions = []
            for line in response.strip().split('\n'):
                line = line.strip()
                # Убираем нумерацию и маркеры
                line = line.lstrip('1234567890.-•* ')
                if line and line.endswith('?'):
                    questions.append(line)
            
            # Ограничиваем количество
            questions = questions[:limit]
            
            logger.info(f"[RAG SERVICE] Generated {len(questions)} suggested questions for project {project_id}")
            return questions
            
        except Exception as e:
            logger.error(f"[RAG SERVICE] Error generating suggested questions: {e}", exc_info=True)
            return []
    
    async def generate_suggested_questions(
        self,
        project_id: UUID,
        limit: int = 5
    ) -> List[str]:
        """
        Генерировать предложенные вопросы на основе загруженных документов
        
        Args:
            project_id: ID проекта
            limit: Количество предложенных вопросов
        
        Returns:
            Список предложенных вопросов
        """
        return await self.suggestions.generate_suggested_questions(project_id, limit)
    
    async def _generate_answer_with_nlp_summarization(
        self,
        user_id: UUID,
        question: str,
        project
    ) -> str:
        """
        Генерирует ответ используя NLP-enhanced summarization для одного документа
        Вместо RAG используется полный документ с улучшенной summarization
        
        Args:
            user_id: ID пользователя
            question: Вопрос пользователя
            project: Объект проекта
        
        Returns:
            Ответ на основе NLP-enhanced summarization
        """
        try:
            from app.models.document import Document
            from sqlalchemy import select
            from app.services.document_summary_service import DocumentSummaryService
            from app.llm.openrouter_client import OpenRouterClient
            from app.models.llm_model import GlobalModelSettings
            
            # Получаем единственный документ проекта
            result = await self.db.execute(
                select(Document)
                .where(Document.project_id == project.id)
                .limit(1)
            )
            document = result.scalar_one_or_none()
            
            if not document:
                return get_constant("constants.errors.no_documents", "В проекте нет документов для анализа.")
            
            # Получаем историю диалога
            conversation_history = await self.helpers.get_conversation_history(user_id, limit=10)
            
            # Получаем настройки моделей
            settings_result = await self.db.execute(select(GlobalModelSettings).limit(1))
            global_settings = settings_result.scalar_one_or_none()
            
            primary_model = project.llm_model or (global_settings.primary_model_id if global_settings else None)
            fallback_model = global_settings.fallback_model_id if global_settings else None
            
            if not primary_model:
                from app.core.config import settings as app_settings
                primary_model = app_settings.OPENROUTER_MODEL_PRIMARY
                fallback_model = fallback_model or app_settings.OPENROUTER_MODEL_FALLBACK
            
            llm_client = OpenRouterClient(
                model_primary=primary_model,
                model_fallback=fallback_model
            )
            
            # NLP-Enhanced Summarization: используем несколько техник
            # 1. Извлекаем ключевые фразы и сущности из вопроса
            # 2. Создаем структурированное summary с выделением важных частей
            # 3. Используем весь документ с контекстным пониманием
            
            # Получаем или генерируем summary документа
            summary_service = DocumentSummaryService(self.db)
            doc_summary = getattr(document, 'summary', None)
            
            if not doc_summary or not doc_summary.strip():
                # Генерируем summary если его нет
                try:
                    doc_summary = await summary_service.generate_summary(document.id)
                except Exception as summary_error:
                    logger.warning(f"[RAG SERVICE] Error generating summary: {summary_error}")
                    doc_summary = None
            
            # Получаем содержимое документа
            document_content = document.content
            
            # Логируем подробную информацию о документе для отладки
            content_length = len(document_content) if document_content else 0
            content_preview = ""
            if document_content and len(document_content) > 0:
                content_preview = document_content[:500]  # Первые 500 символов для логирования
                if len(document_content) > 500:
                    content_preview += "..."
            else:
                content_preview = "EMPTY"
            
            logger.info(f"[RAG SERVICE] Document info for NLP summarization:")
            logger.info(f"  - Document ID: {document.id}")
            logger.info(f"  - Filename: {document.filename}")
            logger.info(f"  - File type: {document.file_type}")
            logger.info(f"  - Content length: {content_length} characters")
            processing_status = get_constant("constants.document_status.processing", "Обработка...")
            processed_status = get_constant("constants.document_status.processed", "Обработан")
            logger.info(f"  - Content status: {'READY' if document_content and document_content not in [processing_status, processed_status, ''] else 'NOT_READY'}")
            logger.info(f"  - Content preview (first 500 chars): {content_preview}")
            
            # Логируем полное содержимое для Railway/Telegram bot (если не слишком большое)
            processing_status = get_constant("constants.document_status.processing", "Обработка...")
            processed_status = get_constant("constants.document_status.processed", "Обработан")
            if document_content and len(document_content) > 0 and document_content not in [processing_status, processed_status, ""]:
                if len(document_content) <= 5000:
                    logger.info(f"[RAG SERVICE] Full document content:\n{document_content}")
                else:
                    logger.info(f"[RAG SERVICE] Document content (first 5000 chars):\n{document_content[:5000]}...")
                    logger.info(f"[RAG SERVICE] Document content (last 5000 chars):\n...{document_content[-5000:]}")
            
            # FALLBACK СТРАТЕГИИ: если контента нет, используем несколько техник
            if not document_content or document_content in ["Обработка...", "Обработан", ""]:
                logger.warning(f"[RAG SERVICE] Document content not ready, trying fallback strategies for document {document.id}")
                
                # Fallback 1: Пытаемся получить чанки из DocumentChunk таблицы
                try:
                    from app.models.document import DocumentChunk
                    chunks_result = await self.db.execute(
                        select(DocumentChunk)
                        .where(DocumentChunk.document_id == document.id)
                        .where(DocumentChunk.chunk_text.isnot(None))
                        .where(DocumentChunk.chunk_text != "")
                        .limit(10)
                    )
                    db_chunks = chunks_result.scalars().all()
                    
                    if db_chunks:
                        # Объединяем чанки в контент
                        chunk_texts = [chunk.chunk_text for chunk in db_chunks if chunk.chunk_text]
                        document_content = "\n\n".join(chunk_texts)
                        logger.info(f"[RAG SERVICE] Fallback 1 SUCCESS: Extracted {len(chunk_texts)} chunks from DocumentChunk table")
                    else:
                        logger.warning(f"[RAG SERVICE] Fallback 1 FAILED: No chunks found in DocumentChunk table")
                except Exception as chunk_error:
                    logger.warning(f"[RAG SERVICE] Fallback 1 ERROR: {chunk_error}")
                
                # Fallback 2: Если чанков нет, пытаемся получить метаданные и использовать их
                processing_status = get_constant("constants.document_status.processing", "Обработка...")
                processed_status = get_constant("constants.document_status.processed", "Обработан")
                if not document_content or document_content in [processing_status, processed_status, ""]:
                    try:
                        from app.services.document_metadata_service import DocumentMetadataService
                        metadata_service = DocumentMetadataService()
                        documents_metadata = await metadata_service.get_documents_metadata(project.id, self.db)
                        
                        if documents_metadata:
                            # Находим метаданные для нашего документа
                            doc_metadata = next((m for m in documents_metadata if m.get("id") == str(document.id)), None)
                            
                            if doc_metadata:
                                # Формируем контент из метаданных
                                metadata_parts = []
                                if doc_metadata.get("filename"):
                                    metadata_parts.append(f"Название файла: {doc_metadata.get('filename')}")
                                if doc_metadata.get("keywords"):
                                    keywords = doc_metadata.get("keywords", [])
                                    if keywords:
                                        metadata_parts.append(f"Ключевые слова: {', '.join(keywords[:20])}")
                                if doc_metadata.get("file_type"):
                                    metadata_parts.append(f"Тип файла: {doc_metadata.get('file_type')}")
                                
                                if metadata_parts:
                                    document_content = "\n".join(metadata_parts)
                                    logger.info(f"[RAG SERVICE] Fallback 2 SUCCESS: Using metadata for document")
                                else:
                                    logger.warning(f"[RAG SERVICE] Fallback 2 FAILED: Metadata exists but empty")
                            else:
                                logger.warning(f"[RAG SERVICE] Fallback 2 FAILED: No metadata found for document {document.id}")
                    except Exception as metadata_error:
                        logger.warning(f"[RAG SERVICE] Fallback 2 ERROR: {metadata_error}")
                
                # Fallback 3: Используем summary если есть
                processing_status = get_constant("constants.document_status.processing", "Обработка...")
                processed_status = get_constant("constants.document_status.processed", "Обработан")
                if not document_content or document_content in [processing_status, processed_status, ""]:
                    if doc_summary:
                        document_content = doc_summary
                        logger.info(f"[RAG SERVICE] Fallback 3 SUCCESS: Using document summary")
                    else:
                        logger.warning(f"[RAG SERVICE] Fallback 3 FAILED: No summary available")
                
                # Fallback 4: Используем название файла и общие знания LLM
                processing_status = get_constant("constants.document_status.processing", "Обработка...")
                processed_status = get_constant("constants.document_status.processed", "Обработан")
                if not document_content or document_content in [processing_status, processed_status, ""]:
                    logger.info(f"[RAG SERVICE] Fallback 4: Using filename and general knowledge")
                    # Создаем контекст на основе названия файла
                    filename_context = f"Документ '{document.filename}'"
                    if document.file_type:
                        filename_context += f" (тип: {document.file_type})"
                    
                    # Используем LLM для генерации ответа на основе названия файла и вопроса
                    try:
                        general_knowledge_prompt = get_prompt(
                            "prompts.fallback.general_knowledge",
                            filename=document.filename,
                            question=question
                        )
                        
                        general_messages = [
                            {
                                "role": "system",
                                "content": f"""{project.prompt_template}

{get_prompt("prompts.system.nlp_minimal_context")}"""
                            },
                            {
                                "role": "user",
                                "content": general_knowledge_prompt
                            }
                        ]
                        
                        if conversation_history:
                            recent_history = conversation_history[-4:]
                            general_messages = [general_messages[0]] + recent_history + [general_messages[1]]
                        
                        answer = await llm_client.chat_completion(
                            messages=general_messages,
                            max_tokens=project.max_response_length // 4,
                            temperature=0.7
                        )
                        
                        answer = self.response_formatter.format_response(
                            response=answer,
                            max_length=project.max_response_length,
                            chunks=[]
                        )
                        
                        await self.helpers.save_message(user_id, question, "user")
                        await self.helpers.save_message(user_id, answer, "assistant")
                        
                        logger.info(f"[RAG SERVICE] Fallback 4 SUCCESS: Generated answer using filename and general knowledge")
                        return answer
                    except Exception as general_error:
                        logger.warning(f"[RAG SERVICE] Fallback 4 ERROR: {general_error}")
                
                # Fallback 5: Последний резерв - используем хотя бы название файла
                processing_status = get_constant("constants.document_status.processing", "Обработка...")
                processed_status = get_constant("constants.document_status.processed", "Обработан")
                if not document_content or document_content in [processing_status, processed_status, ""]:
                    document_content = f"Документ '{document.filename}'"
                    if document.file_type:
                        document_content += f" (тип: {document.file_type})"
                    logger.info(f"[RAG SERVICE] Fallback 5: Using minimal context (filename only)")
            
            # NLP-Enhanced подход: создаем структурированный контекст
            # Извлекаем ключевые слова из вопроса для фокусировки
            import re
            question_keywords = set(re.findall(r'\b\w+\b', question.lower()))
            question_keywords = {w for w in question_keywords if len(w) > 3}  # Слова длиннее 3 символов
            
            # Если документ большой, используем первые 12000 символов (для long-context моделей)
            max_content_length = get_default("defaults.document_max_length", 12000)
            if len(document_content) > max_content_length:
                # Берем начало и конец документа для лучшего контекста
                content_start = document_content[:max_content_length // 2]
                content_end = document_content[-max_content_length // 2:]
                document_content = f"{content_start}\n\n[...пропущена средняя часть...]\n\n{content_end}"
                logger.info(f"[RAG SERVICE] Document too long ({len(document_content)} chars), using first and last parts")
            
            # Создаем NLP-enhanced промпт с структурированием
            # Формируем часть с резюме отдельно, чтобы избежать проблемы с обратными слешами в f-string
            summary_part = ""
            if doc_summary:
                summary_part = f"КРАТКОЕ РЕЗЮМЕ ДОКУМЕНТА:\n{doc_summary}\n\n"
            
            keywords_str = ', '.join(list(question_keywords)[:10]) if question_keywords else 'общие'
            
            # Определяем, есть ли у нас полный контент или только минимальный
            processing_status = get_constant("constants.document_status.processing", "Обработка...")
            processed_status = get_constant("constants.document_status.processed", "Обработан")
            has_full_content = document_content and len(document_content) > 100 and document_content not in [processing_status, processed_status, ""] and not document_content.startswith("Документ '")
            
            if has_full_content:
                # Полный контент доступен - используем стандартный NLP-enhanced промпт
                nlp_prompt = get_prompt(
                    "prompts.nlp_summarization.full_content",
                    filename=document.filename,
                    content=document_content,
                    summary_part=summary_part,
                    question=question,
                    keywords=keywords_str
                )
            else:
                # Минимальный контент - используем специальный промпт с общими знаниями
                logger.info(f"[RAG SERVICE] Using minimal context mode (filename/metadata only)")
                nlp_prompt = get_prompt(
                    "prompts.nlp_summarization.minimal_context",
                    content=document_content,
                    summary_part=summary_part if summary_part else '',
                    question=question
                )
            
            nlp_system_prompt = get_prompt("prompts.system.nlp_expert")
            messages = [
                {
                    "role": "system",
                    "content": f"""{project.prompt_template}

{nlp_system_prompt}"""
                },
                {
                    "role": "user",
                    "content": nlp_prompt
                }
            ]
            
            # Добавляем историю диалога
            if conversation_history:
                recent_history = conversation_history[-4:]  # Последние 2 пары вопрос-ответ
                messages = [messages[0]] + recent_history + [messages[1]]
            
            # Генерируем ответ
            max_tokens = project.max_response_length // 4
            answer = await llm_client.chat_completion(
                messages=messages,
                max_tokens=max_tokens,
                temperature=0.7
            )
            
            # Форматируем ответ
            answer = self.response_formatter.format_response(
                response=answer,
                max_length=project.max_response_length,
                chunks=[]  # Нет чанков для single document
            )
            
            # Сохраняем сообщения в историю
            await self.helpers.save_message(user_id, question, "user")
            await self.helpers.save_message(user_id, answer, "assistant")
            
            logger.info(f"[RAG SERVICE] NLP-enhanced summarization answer generated for single document")
            return answer
            
        except Exception as e:
            logger.error(f"[RAG SERVICE] Error in NLP-enhanced summarization: {e}", exc_info=True)
            # Fallback на обычный ответ
            return get_constant("constants.errors.analysis_error", "Извините, произошла ошибка при анализе документа. Пожалуйста, попробуйте переформулировать вопрос.")


