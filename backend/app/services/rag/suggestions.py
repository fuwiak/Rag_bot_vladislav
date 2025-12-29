"""
Suggested questions generation for RAG service
"""
from typing import List
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession

from app.vector_db.vector_store import VectorStore
from app.llm.openrouter_client import OpenRouterClient
from app.observability.structured_logging import get_logger

logger = get_logger(__name__)


class RAGSuggestions:
    """Suggested questions generation for RAG service"""
    
    def __init__(self, db: AsyncSession, vector_store: VectorStore):
        self.db = db
        self.vector_store = vector_store
    
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
                        logger.info(f"[RAG SUGGESTIONS] Found {len(chunk_texts)} chunks in Qdrant for project {project_id}")
                except Exception as qdrant_error:
                    logger.warning(f"[RAG SUGGESTIONS] Error reading from Qdrant: {qdrant_error}, trying DB")
            
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
                        logger.warning(f"[RAG SUGGESTIONS] Summary column not found in DB, using raw SQL query")
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
                            logger.error(f"[RAG SUGGESTIONS] Error with raw SQL query: {sql_error}")
                            documents = []
                    else:
                        # Другая ошибка - пробрасываем дальше
                        raise
                
                if not documents:
                    logger.info(f"[RAG SUGGESTIONS] No documents found for project {project_id}")
                    return []
                
                logger.info(f"[RAG SUGGESTIONS] Found {len(documents)} documents in DB for project {project_id}")
                
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
                    logger.info(f"[RAG SUGGESTIONS] No chunks in DB, using summaries or document content")
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
                logger.warning(f"[RAG SUGGESTIONS] No content found for project {project_id} - documents may still be processing")
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
                            logger.info(f"[RAG SUGGESTIONS] Using metadata context with {len(unique_keywords)} keywords")
                except Exception as metadata_error:
                    logger.warning(f"[RAG SUGGESTIONS] Error getting metadata for questions: {metadata_error}")
                
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
            
            logger.info(f"[RAG SUGGESTIONS] Generated {len(questions)} suggested questions for project {project_id}")
            return questions
            
        except Exception as e:
            logger.error(f"[RAG SUGGESTIONS] Error generating suggested questions: {e}", exc_info=True)
            return []
                            })
            
            logger.info(f"[RAG SUGGESTIONS] Retrieved {len(summaries)} document summaries for project {project_id}")
            return summaries
            
        except Exception as e:
            logger.error(f"[RAG SUGGESTIONS] Error getting document summaries: {e}", exc_info=True)
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
                        logger.info(f"[RAG SUGGESTIONS] Found {len(chunk_texts)} chunks in Qdrant for project {project_id}")
                except Exception as qdrant_error:
                    logger.warning(f"[RAG SUGGESTIONS] Error reading from Qdrant: {qdrant_error}, trying DB")
            
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
                        logger.warning(f"[RAG SUGGESTIONS] Summary column not found in DB, using raw SQL query")
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
                            logger.error(f"[RAG SUGGESTIONS] Error with raw SQL query: {sql_error}")
                            documents = []
                    else:
                        # Другая ошибка - пробрасываем дальше
                        raise
                
                if not documents:
                    logger.info(f"[RAG SUGGESTIONS] No documents found for project {project_id}")
                    return []
                
                logger.info(f"[RAG SUGGESTIONS] Found {len(documents)} documents in DB for project {project_id}")
                
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
                    logger.info(f"[RAG SUGGESTIONS] No chunks in DB, using summaries or document content")
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
                logger.warning(f"[RAG SUGGESTIONS] No content found for project {project_id} - documents may still be processing")
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
                            logger.info(f"[RAG SUGGESTIONS] Using metadata context with {len(unique_keywords)} keywords")
                except Exception as metadata_error:
                    logger.warning(f"[RAG SUGGESTIONS] Error getting metadata for questions: {metadata_error}")
                
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
            
            logger.info(f"[RAG SUGGESTIONS] Generated {len(questions)} suggested questions for project {project_id}")
            return questions
            
        except Exception as e:
            logger.error(f"[RAG SUGGESTIONS] Error generating suggested questions: {e}", exc_info=True)
            return []
