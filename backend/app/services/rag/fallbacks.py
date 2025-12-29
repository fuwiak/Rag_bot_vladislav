"""
Fallback methods for RAG service - alternative answer generation strategies
"""
from typing import List, Dict, Optional
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.project import Project
from app.services.embedding_service import EmbeddingService
from app.llm.openrouter_client import OpenRouterClient
from app.observability.structured_logging import get_logger

logger = get_logger(__name__)


class RAGFallbacks:
    """Fallback methods for RAG service"""
    
    def __init__(self, db: AsyncSession, embedding_service: EmbeddingService):
        self.db = db
        self.embedding_service = embedding_service
    
    async def generate_document_summary_fallback(
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
                logger.warning(f"[RAG FALLBACKS] Error extracting additional content: {content_error}")
            
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
            
            logger.info(f"[RAG FALLBACKS] Generated document summary fallback (length: {len(response)})")
            return response.strip()
            
        except Exception as e:
            logger.error(f"[RAG FALLBACKS] Error generating document summary fallback: {e}", exc_info=True)
            # В крайнем случае возвращаем базовую информацию из метаданных
            return f"На основе доступной информации о документах:\n\n{metadata_context}\n\nК сожалению, полное содержимое документов еще обрабатывается, но вы можете задать вопросы о конкретных файлах по их названиям."
    

    
    async def generate_ai_agent_fallback(
        self,
        question: str,
        project,
        llm_client,
        max_tokens: int,
        conversation_history: List[Dict[str, str]] = None
    ) -> str:
        """
        Генерирует ответ через AI агента как fallback механизм
        
        Args:
            question: Вопрос пользователя
            project: Объект проекта
            llm_client: Клиент LLM
            max_tokens: Максимальное количество токенов
            conversation_history: История диалога
            
        Returns:
            Ответ от AI агента
        """
        try:
            from app.services.rag_agent import RAGAgent
            rag_agent = RAGAgent(llm_client)
            
            # Используем агента для генерации ответа на основе общих знаний
            agent_prompt = f"""Вопрос пользователя: {question}

Используй свои знания и контекст проекта '{project.name}' для ответа на вопрос.
Будь полезным и информативным, даже если у тебя нет доступа к конкретным документам.

Ответ:"""
            
            messages = [
                {"role": "system", "content": f"{project.prompt_template}\n\nТы - полезный ассистент, который отвечает на вопросы пользователей."},
                {"role": "user", "content": agent_prompt}
            ]
            
            if conversation_history:
                recent_history = conversation_history[-4:]
                messages = [messages[0]] + recent_history + [messages[1]]
            
            response = await llm_client.chat_completion(
                messages=messages,
                max_tokens=max_tokens,
                temperature=0.7
            )
            
            logger.info(f"[RAG FALLBACKS] Generated AI agent fallback (length: {len(response)})")
            return response.strip()
            
        except Exception as e:
            logger.warning(f"[RAG FALLBACKS] AI agent fallback failed: {e}")
            return None
    

    
    async def generate_basic_fallback(
        self,
        question: str,
        project
    ) -> str:
        """
        Генерирует базовый ответ на основе названия проекта
        
        Args:
            question: Вопрос пользователя
            project: Объект проекта
            
        Returns:
            Базовый ответ
        """
        try:
            # Пытаемся получить хотя бы список документов
            from app.models.document import Document
            from sqlalchemy import select
            
            result = await self.db.execute(
                select(Document)
                .where(Document.project_id == project.id)
                .limit(5)
            )
            documents = result.scalars().all()
            
            if documents:
                doc_names = [doc.filename for doc in documents if doc.filename]
                doc_list = "\n".join([f"- {name}" for name in doc_names[:5]])
                
                return f"""В проекте '{project.name}' загружены следующие документы:

{doc_list}

Документы могут быть еще в процессе обработки. Попробуйте задать вопрос о конкретном документе по его названию."""
            else:
                return f"""В проекте '{project.name}' пока нет загруженных документов. 
Пожалуйста, загрузите документы, чтобы я мог ответить на ваши вопросы."""
                
        except Exception as e:
            logger.warning(f"[RAG FALLBACKS] Basic fallback failed: {e}")
            return f"Извините, произошла ошибка при обработке вашего вопроса в проекте '{project.name}'. Пожалуйста, попробуйте переформулировать вопрос."
    

    
    async def process_full_documents_with_subagent(
        self,
        question: str,
        project,
        llm_client=None,
        max_tokens: int = 500
    ) -> Optional[str]:
        """
        Sub-agent для обработки целых документов как fallback механизм
        
        Args:
            question: Вопрос пользователя
            project: Объект проекта
            llm_client: Клиент LLM (если None, создается новый)
            max_tokens: Максимальное количество токенов
            
        Returns:
            Ответ на основе целых документов или None
        """
        try:
            from app.models.document import Document
            from sqlalchemy import select
            
            # Получаем документы проекта
            result = await self.db.execute(
                select(Document)
                .where(Document.project_id == project.id)
                .where(Document.content.isnot(None))
                .where(Document.content != "")
                .where(Document.content.notin_(["Обработка...", "Обработан"]))
                .limit(3)  # Обрабатываем максимум 3 документа
            )
            documents = result.scalars().all()
            
            if not documents:
                return None
            
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
            
            # Обрабатываем каждый документ отдельно (sub-agent подход)
            document_responses = []
            for doc in documents:
                if doc.content and len(doc.content) > 100:
                    # Берем первые 4000 символов из каждого документа (для экономии токенов)
                    doc_content = doc.content[:4000]
                    if len(doc.content) > 4000:
                        doc_content += "..."
                    
                    subagent_prompt = f"""Вопрос пользователя: {question}

Полный документ '{doc.filename}':
{doc_content}

Ответь на вопрос на основе этого документа. Если информации нет, так и скажи."""
                    
                    messages = [
                        {"role": "system", "content": "Ты - sub-agent, который анализирует целые документы для ответа на вопросы. Отвечай кратко и по делу."},
                        {"role": "user", "content": subagent_prompt}
                    ]
                    
                    try:
                        response = await llm_client.chat_completion(
                            messages=messages,
                            max_tokens=max_tokens // len(documents),  # Делим токены между документами
                            temperature=0.7
                        )
                        
                        # Проверяем, не является ли ответ отказом
                        response_lower = response.strip().lower()
                        refusal_phrases = ["нет информации", "не могу ответить", "не нашел", "не найдено"]
                        if not any(phrase in response_lower for phrase in refusal_phrases):
                            document_responses.append(f"Из документа '{doc.filename}': {response.strip()}")
                    except Exception as doc_error:
                        logger.debug(f"[RAG FALLBACKS] Sub-agent failed for doc {doc.filename}: {doc_error}")
                        continue
            
            if document_responses:
                combined_response = "\n\n".join(document_responses)
                logger.info(f"[RAG FALLBACKS] Sub-agent processed {len(document_responses)} documents")
                return combined_response
            
            return None
            
        except Exception as e:
            logger.warning(f"[RAG FALLBACKS] Sub-agent fallback failed: {e}")
            return None
    

    
    async def late_chunking_fallback(
        self,
        question: str,
        project,
        llm_client=None,
        max_tokens: int = 500
    ) -> Optional[str]:
        """
        Late Chunking fallback - обработка через long-context embedding
        
        Args:
            question: Вопрос пользователя
            project: Объект проекта
            llm_client: Клиент LLM (если None, создается новый)
            max_tokens: Максимальное количество токенов
            
        Returns:
            Ответ на основе late chunking или None
        """
        try:
            from app.models.document import Document
            from sqlalchemy import select
            import numpy as np
            
            # Получаем документы проекта
            result = await self.db.execute(
                select(Document)
                .where(Document.project_id == project.id)
                .where(Document.content.isnot(None))
                .where(Document.content != "")
                .where(Document.content.notin_(["Обработка...", "Обработан"]))
                .limit(2)  # Обрабатываем максимум 2 документа
            )
            documents = result.scalars().all()
            
            if not documents:
                return None
            
            # Создаем эмбеддинг вопроса
            question_embedding = await self.embedding_service.create_embedding(question)
            
            # Для каждого документа создаем эмбеддинг всего документа (late chunking)
            best_doc = None
            best_score = 0.0
            
            for doc in documents:
                if doc.content and len(doc.content) > 100:
                    # Создаем эмбеддинг всего документа (первые 8000 символов для экономии)
                    doc_content = doc.content[:8000]
                    doc_embedding = await self.embedding_service.create_embedding(doc_content)
                    
                    # Вычисляем косинусное сходство
                    similarity = np.dot(question_embedding, doc_embedding) / (
                        np.linalg.norm(question_embedding) * np.linalg.norm(doc_embedding)
                    )
                    
                    if similarity > best_score:
                        best_score = similarity
                        best_doc = doc
            
            # Если нашли релевантный документ, используем его
            if best_doc and best_score > 0.3:
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
                
                # Используем первые 5000 символов документа
                doc_content = best_doc.content[:5000]
                if len(best_doc.content) > 5000:
                    doc_content += "..."
                
                late_chunking_prompt = f"""Вопрос пользователя: {question}

Документ '{best_doc.filename}' (релевантность: {best_score:.2f}):
{doc_content}

Ответь на вопрос на основе этого документа."""
                
                messages = [
                    {"role": "system", "content": "Ты - ассистент, который отвечает на вопросы на основе документов. Отвечай кратко и информативно."},
                    {"role": "user", "content": late_chunking_prompt}
                ]
                
                response = await llm_client.chat_completion(
                    messages=messages,
                    max_tokens=max_tokens,
                    temperature=0.7
                )
                
                logger.info(f"[RAG FALLBACKS] Late chunking found relevant document with score {best_score:.2f}")
                return response.strip()
            
            return None
            
        except Exception as e:
            logger.warning(f"[RAG FALLBACKS] Late chunking fallback failed: {e}")
            return None
    
