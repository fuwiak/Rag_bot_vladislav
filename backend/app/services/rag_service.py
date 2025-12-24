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

logger = logging.getLogger(__name__)


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
        # Получение пользователя и проекта
        user = await self._get_user(user_id)
        if not user:
            raise ValueError("Пользователь не найден")
        
        project = await self._get_project(user.project_id)
        if not project:
            raise ValueError("Проект не найден")
        
        # Получение истории диалога (минимум 10 сообщений согласно требованиям)
        conversation_history = await self._get_conversation_history(user_id, limit=10)
        
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
        
        chunk_texts = []
        metadata_context = ""
        
        # Определяем стратегию поиска на основе анализа агента
        collection_name = f"project_{project.id}"
        collection_exists = await self.vector_store.collection_exists(collection_name)
        
        # Если агент рекомендует использовать чанки и они доступны
        if strategy.get("use_chunks", True) and collection_exists:
            logger.info(f"[RAG SERVICE] Using chunks strategy (AI Agent recommendation)")
            question_embedding = await self.embedding_service.create_embedding(question)
            similar_chunks = await self.vector_store.search_similar(
                collection_name=collection_name,
                query_vector=question_embedding,
                limit=top_k,
                score_threshold=0.5
            )
            
            if similar_chunks and len(similar_chunks) > 0:
                chunk_texts = [chunk.get("payload", {}).get("chunk_text", "") for chunk in similar_chunks if chunk.get("payload", {}).get("chunk_text")]
                logger.info(f"[RAG SERVICE] Found {len(chunk_texts)} chunks from vector search")
        
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
            
            summaries = await self._get_document_summaries(project.id, top_k * 2)  # Берем больше summaries для содержания
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
        if not chunk_texts:
            logger.info(f"[RAG SERVICE] No chunks found, trying to extract content directly from documents using multiple techniques")
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
                            .where(Document.content.notin_(["Обработка...", "Обработан"]))
                            .limit(10)
                        )
                        documents = result.scalars().all()
                    except Exception:
                        # Fallback на raw SQL
                        result = await self.db.execute(
                            text("""
                                SELECT id, filename, content, file_type 
                                FROM documents 
                                WHERE project_id = :project_id 
                                AND content IS NOT NULL 
                                AND content != '' 
                                AND content NOT IN ('Обработка...', 'Обработан')
                                LIMIT 10
                            """),
                            {"project_id": str(project.id)}
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
                    
                    # Используем DocumentChunker для разбивки на чанки
                    chunker = DocumentChunker(chunk_size=1000, chunk_overlap=200)
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
                
            except Exception as extract_error:
                logger.warning(f"[RAG SERVICE] Error extracting content from documents: {extract_error}")
        
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
                context = f"""Информация о загруженных документах:

{metadata_context}

ИНСТРУКЦИЯ: На основе этой информации ответь на вопрос пользователя. 
- Если вопрос о summary каждого файла, создай краткое описание каждого файла на основе его названия и ключевых слов
- Используй названия файлов и ключевые слова для понимания содержания
- Будь конкретным и информативным"""
                
                enhanced_prompt = f"""Вопрос пользователя: {question}

Используй информацию о документах выше для ответа. Если вопрос о summary каждого файла, предоставь краткое описание каждого файла на основе его названия и ключевых слов.

Ответ:"""
                
                messages = [
                    {"role": "system", "content": "Ты - полезный ассистент, который отвечает на вопросы пользователей на основе информации о загруженных документах. Отвечай на русском языке, будь дружелюбным и информативным. Используй названия файлов и ключевые слова для создания описаний."},
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
                
                enhanced_prompt = f"""На основе следующих фрагментов документов ответь на вопрос пользователя.
Если ответа нет в контексте, так и скажи.

КОНТЕКСТ:
{context}

ВОПРОС: {question}

ОТВЕТ:"""
                
                messages = [
                    {"role": "system", "content": "Ты - полезный ассистент, который отвечает на вопросы пользователей на основе предоставленных документов. Отвечай на русском языке, будь дружелюбным и информативным."},
                    {"role": "user", "content": enhanced_prompt}
                ]
            elif metadata_context:
                # Нет summaries, но есть метаданные - используем их
                context = f"""Метаданные документов:

{metadata_context}

ВАЖНО: Используй эту информацию для ответа на вопрос. Если вопрос касается конкретного файла, используй название файла и ключевые слова из метаданных."""
                
                enhanced_prompt = f"""Вопрос пользователя: {question}

Используй информацию о документах выше для ответа.

Ответ:"""
                
                messages = [
                    {"role": "system", "content": "Ты - полезный ассистент, который отвечает на вопросы пользователей на основе информации о загруженных документах. Отвечай на русском языке, будь дружелюбным и информативным."},
                    {"role": "user", "content": enhanced_prompt}
                ]
            else:
                # Нет ни summaries, ни метаданных
                context = "Документы еще обрабатываются. Доступна только информация о загруженных файлах."
                enhanced_prompt = f"""Вопрос: {question}

Контекст: {context}

Ответ:"""
                
                messages = [
                    {"role": "system", "content": "Ты - полезный ассистент, который отвечает на вопросы пользователей. Отвечай на русском языке, будь дружелюбным и информативным."},
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
            refusal_phrases = [
                "нет информации", "не могу ответить", "не нашел", 
                "не найдено", "нет данных", "недостаточно информации",
                "нет релевантной информации", "не удалось найти"
            ]
            
            # Если ответ содержит отказ и у нас есть метаданные - генерируем сводку
            if any(phrase in answer_text for phrase in refusal_phrases) and metadata_context:
                logger.info(f"[RAG SERVICE] Answer contains refusal, generating document summary as fallback")
                answer = await self._generate_document_summary_fallback(
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
            logger.warning(f"[RAG SERVICE] LLM error: {llm_error}, trying document summary fallback")
            # Если ошибка LLM, пытаемся сгенерировать сводку
            if metadata_context:
                answer = await self._generate_document_summary_fallback(
                    question=question,
                    metadata_context=metadata_context,
                    project=project,
                    llm_client=llm_client,
                    max_tokens=max_tokens
                )
            else:
                raise
        
        # Сохранение сообщений в историю
        await self._save_message(user_id, question, "user")
        await self._save_message(user_id, answer, "assistant")
        
        return answer
    
    async def _generate_document_summary_fallback(
        self,
        question: str,
        metadata_context: str,
        project,
        llm_client=None,
        max_tokens: int = 1000
    ) -> str:
        """
        Генерирует сводку документов на основе метаданных как fallback,
        когда RAG не находит релевантной информации
        
        Args:
            question: Вопрос пользователя
            metadata_context: Контекст из метаданных документов
            project: Объект проекта
            llm_client: Клиент LLM (если None, создается новый)
            max_tokens: Максимальное количество токенов
            
        Returns:
            Сводка документов на основе метаданных
        """
        try:
            # Создаем клиент LLM если не передан
            if llm_client is None:
                from app.llm.openrouter_client import OpenRouterClient
                from app.models.llm_model import GlobalModelSettings
                from sqlalchemy import select
                
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
            
            # Пытаемся извлечь дополнительный контент из документов
            additional_content = ""
            try:
                from app.models.document import Document
                from sqlalchemy import select, text
                
                try:
                    result = await self.db.execute(
                        select(Document)
                        .where(Document.project_id == project.id)
                        .where(Document.content.isnot(None))
                        .where(Document.content != "")
                        .where(Document.content.notin_(["Обработка...", "Обработан"]))
                        .limit(5)
                    )
                    documents = result.scalars().all()
                except Exception:
                    result = await self.db.execute(
                        text("""
                            SELECT filename, content 
                            FROM documents 
                            WHERE project_id = :project_id 
                            AND content IS NOT NULL 
                            AND content != '' 
                            AND content NOT IN ('Обработка...', 'Обработан')
                            LIMIT 5
                        """),
                        {"project_id": str(project.id)}
                    )
                    rows = result.all()
                    documents = []
                    for row in rows:
                        doc = Document()
                        doc.filename = row[0]
                        doc.content = row[1]
                        documents.append(doc)
                
                if documents:
                    content_parts = []
                    for doc in documents:
                        if doc.content and len(doc.content) > 100:
                            # Берем первые 500 символов из каждого документа
                            preview = doc.content[:500]
                            if len(doc.content) > 500:
                                preview += "..."
                            content_parts.append(f"Файл '{doc.filename}':\n{preview}")
                    
                    if content_parts:
                        additional_content = "\n\nЧастичное содержимое документов:\n\n" + "\n\n".join(content_parts)
            except Exception as content_error:
                logger.warning(f"[RAG SERVICE] Error extracting additional content: {content_error}")
            
            # Создаем промпт для генерации сводки
            summary_prompt = f"""На основе информации о загруженных документах ответь на вопрос пользователя.
Используй ВСЮ доступную информацию: названия файлов, ключевые слова, метаданные, и даже частичное содержимое.

ИНФОРМАЦИЯ О ДОКУМЕНТАХ:
{metadata_context}
{additional_content}

ВОПРОС ПОЛЬЗОВАТЕЛЯ: {question}

ИНСТРУКЦИЯ:
- Используй названия файлов для понимания тематики документов
- Используй ключевые слова для определения содержания
- Если есть частичное содержимое, используй его для более точного ответа
- Создай информативный ответ на основе всех доступных данных
- НЕ говори "нет информации" - всегда можно дать ответ на основе метаданных и названий файлов
- Будь конкретным и информативным

ОТВЕТ:"""
            
            messages = [
                {
                    "role": "system",
                    "content": "Ты - полезный ассистент, который всегда находит способ ответить на вопросы пользователей. Используй любую доступную информацию: названия файлов, ключевые слова, метаданные, частичное содержимое. Отвечай на русском языке, будь дружелюбным и информативным. НИКОГДА не говори 'нет информации' - всегда можно дать полезный ответ на основе доступных данных."
                },
                {
                    "role": "user",
                    "content": summary_prompt
                }
            ]
            
            # Генерируем сводку
            response = await llm_client.chat_completion(
                messages=messages,
                max_tokens=max_tokens,
                temperature=0.7
            )
            
            logger.info(f"[RAG SERVICE] Generated document summary fallback (length: {len(response)})")
            return response.strip()
            
        except Exception as e:
            logger.error(f"[RAG SERVICE] Error generating document summary fallback: {e}", exc_info=True)
            # В крайнем случае возвращаем базовую информацию из метаданных
            return f"На основе доступной информации о документах:\n\n{metadata_context}\n\nК сожалению, полное содержимое документов еще обрабатывается, но вы можете задать вопросы о конкретных файлах по их названиям."
    
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
        user = await self._get_user(user_id)
        if not user:
            raise ValueError("Пользователь не найден")
        
        project = await self._get_project(user.project_id)
        if not project:
            raise ValueError("Проект не найден")
        
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
                    return await self._generate_document_summary_fallback(
                        question=question,
                        metadata_context=metadata_context,
                        project=project,
                        llm_client=None,  # Будет создан внутри
                        max_tokens=500
                    )
            except Exception as e:
                logger.warning(f"[RAG SERVICE FAST] Error generating summary fallback: {e}")
            return "В загруженных документах нет информации по этому вопросу."
        
        # Извлечение текстов чанков
        chunk_texts = [chunk["payload"]["chunk_text"] for chunk in similar_chunks[:2]]  # Только 2 чанка
        
        # Построение упрощенного промпта
        messages = [
            {
                "role": "system",
                "content": f"{project.prompt_template}\n\nОтвечай кратко, не более 500 символов."
            },
            {
                "role": "user",
                "content": f"Вопрос: {question}\n\nКонтекст:\n" + "\n\n".join(chunk_texts)
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
        await self._save_message(user_id, question, "user")
        await self._save_message(user_id, answer, "assistant")
        
        return answer
    
    async def _get_user(self, user_id: UUID) -> Optional[User]:
        """Получить пользователя"""
        result = await self.db.execute(select(User).where(User.id == user_id))
        return result.scalar_one_or_none()
    
    async def _get_project(self, project_id: UUID) -> Optional[Project]:
        """Получить проект"""
        result = await self.db.execute(select(Project).where(Project.id == project_id))
        return result.scalar_one_or_none()
    
    async def _get_conversation_history(self, user_id: UUID, limit: int = 6) -> List[Dict[str, str]]:
        """Получить историю диалога"""
        result = await self.db.execute(
            select(Message)
            .where(Message.user_id == user_id)
            .order_by(desc(Message.created_at))
            .limit(limit)
        )
        messages = list(result.scalars().all())
        
        # Преобразование в формат для LLM (обратный порядок - от старых к новым)
        history = []
        for msg in reversed(messages):
            history.append({
                "role": msg.role,
                "content": msg.content
            })
        
        return history
    
    async def _save_message(self, user_id: UUID, content: str, role: str):
        """Сохранить сообщение в историю"""
        message = Message(
            user_id=user_id,
            content=content,
            role=role
        )
        self.db.add(message)
        await self.db.commit()
    
    async def _get_document_summaries(self, project_id: UUID, limit: int = 5) -> List[str]:
        """
        Получает summaries документов проекта для использования в RAG
        
        Args:
            project_id: ID проекта
            limit: Максимальное количество summaries
        
        Returns:
            Список summaries документов
        """
        try:
            from app.models.document import Document
            from app.services.document_summary_service import DocumentSummaryService
            
            # Получаем документы проекта (безопасно, даже если поле summary отсутствует)
            try:
                # Пробуем обычный запрос
                result = await self.db.execute(
                    select(Document)
                    .where(Document.project_id == project_id)
                    .limit(limit * 2)  # Берем больше, чтобы выбрать те, у которых есть summary
                )
                documents = result.scalars().all()
            except Exception as db_error:
                # Если ошибка из-за отсутствия поля summary, используем raw SQL
                error_str = str(db_error).lower()
                if "summary" in error_str or "column" in error_str:
                    logger.warning(f"[RAG SERVICE] Summary column not found in DB, using raw SQL query")
                    from sqlalchemy import text
                    try:
                        result = await self.db.execute(
                            text("SELECT id, project_id, filename, content, file_type, created_at FROM documents WHERE project_id = :project_id LIMIT :limit"),
                            {"project_id": str(project_id), "limit": limit * 2}
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
                return []
            
            summary_service = DocumentSummaryService(self.db)
            summaries = []
            
            for doc in documents[:limit]:
                # Приоритет 1: используем существующий summary (проверяем безопасно)
                doc_summary = getattr(doc, 'summary', None)
                if doc_summary and doc_summary.strip():
                    # Форматируем как в рабочем скрипте: "Фрагмент X (источник: filename): summary"
                    summaries.append({
                        "text": doc_summary,
                        "source": doc.filename,
                        "score": 1.0
                    })
                else:
                    # Приоритет 2: пытаемся создать summary (только если поле существует в БД)
                    try:
                        # Проверяем, существует ли поле summary в модели
                        if hasattr(Document, 'summary'):
                            summary = await summary_service.generate_summary(doc.id)
                            if summary and summary.strip():
                                summaries.append({
                                    "text": summary,
                                    "source": doc.filename,
                                    "score": 1.0
                                })
                                continue
                    except Exception as e:
                        logger.warning(f"Error generating summary for doc {doc.id}: {e}")
                    
                    # Приоритет 3: используем содержимое (первые 500 символов)
                    if doc.content and doc.content not in ["Обработка...", "Обработан", ""]:
                        content = doc.content[:500]
                        if content.strip():
                            summaries.append({
                                "text": content,
                                "source": doc.filename,
                                "score": 0.8
                            })
            
            logger.info(f"[RAG SERVICE] Retrieved {len(summaries)} document summaries for project {project_id}")
            return summaries
            
        except Exception as e:
            logger.error(f"[RAG SERVICE] Error getting document summaries: {e}", exc_info=True)
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
                        if doc.content and doc.content not in ["Обработка...", "Обработан", ""]:
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
            prompt = f"""На основе следующего контекста из документов, сгенерируй {limit} интересных и полезных вопросов, которые можно задать об этом содержимом.

Контекст из документов:
{context[:2000]}

Требования к вопросам:
1. Вопросы должны быть конкретными и релевантными содержимому
2. Вопросы должны быть на русском языке
3. Вопросы должны быть разными по тематике
4. Каждый вопрос должен быть на отдельной строке
5. Не используй нумерацию или маркеры

Сгенерируй только вопросы, без дополнительных комментариев:"""
            
            messages = [
                {"role": "system", "content": "Ты помощник, который генерирует вопросы на основе документов."},
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


