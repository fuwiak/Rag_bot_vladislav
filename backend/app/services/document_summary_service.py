"""
Сервис для создания summary документов через LLM
"""
import logging
from typing import Optional
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.document import Document
from app.llm.openrouter_client import OpenRouterClient
from app.models.project import Project
from app.models.llm_model import GlobalModelSettings
from app.core.config import settings as app_settings

logger = logging.getLogger(__name__)


class DocumentSummaryService:
    """Сервис для создания summary документов"""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def generate_summary(self, document_id: UUID) -> Optional[str]:
        """
        Генерирует summary для документа через LLM
        
        Args:
            document_id: ID документа
        
        Returns:
            Summary документа или None при ошибке
        """
        try:
            # Получаем документ
            result = await self.db.execute(
                select(Document).where(Document.id == document_id)
            )
            document = result.scalar_one_or_none()
            
            if not document:
                logger.error(f"Document {document_id} not found")
                return None
            
            # Если summary уже есть, возвращаем его (проверяем безопасно)
            doc_summary = getattr(document, 'summary', None)
            if doc_summary and doc_summary.strip():
                logger.info(f"Document {document_id} already has summary")
                return doc_summary
            
            # Получаем проект для настроек LLM
            project_result = await self.db.execute(
                select(Project).where(Project.id == document.project_id)
            )
            project = project_result.scalar_one_or_none()
            
            if not project:
                logger.error(f"Project not found for document {document_id}")
                return None
            
            # Получаем текст документа
            content = document.content
            if not content or content in ["Обработка...", "Обработан", ""]:
                logger.warning(f"Document {document_id} has no content yet")
                return None
            
            # Ограничиваем длину контента для summary (первые 8000 символов)
            content_for_summary = content[:8000]
            if len(content) > 8000:
                content_for_summary += "..."
            
            # Определяем модель LLM
            primary_model = None
            fallback_model = None
            
            if project.llm_model:
                primary_model = project.llm_model
            else:
                settings_result = await self.db.execute(select(GlobalModelSettings).limit(1))
                global_settings = settings_result.scalar_one_or_none()
                if global_settings:
                    primary_model = global_settings.primary_model_id
                    fallback_model = global_settings.fallback_model_id
            
            if not primary_model:
                primary_model = app_settings.OPENROUTER_MODEL_PRIMARY
            if not fallback_model:
                fallback_model = app_settings.OPENROUTER_MODEL_FALLBACK
            
            # Создаем LLM клиент
            llm_client = OpenRouterClient(
                model_primary=primary_model,
                model_fallback=fallback_model
            )
            
            # Промпт для создания summary
            prompt = f"""Создай краткое содержание (summary) следующего документа на русском языке.

Название файла: {document.filename}
Тип файла: {document.file_type}

Содержимое документа:
{content_for_summary}

Требования к summary:
1. Краткое содержание должно быть на русском языке
2. Длина: 200-500 символов
3. Должно отражать основные темы и ключевую информацию документа
4. Будь конкретным и информативным
5. Не используй маркеры или нумерацию

Создай только summary, без дополнительных комментариев:"""
            
            messages = [
                {
                    "role": "system",
                    "content": "Ты помощник, который создает краткие содержания документов. Отвечай только summary, без дополнительных комментариев."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ]
            
            logger.info(f"Generating summary for document {document_id} ({document.filename})")
            summary = await llm_client.chat_completion(
                messages=messages,
                max_tokens=300,
                temperature=0.3
            )
            
            # Очищаем summary от лишних символов
            summary = summary.strip()
            if summary.startswith("Summary:") or summary.startswith("Краткое содержание:"):
                summary = summary.split(":", 1)[1].strip()
            
            # Сохраняем summary в БД (только если поле существует)
            if hasattr(document, 'summary'):
                document.summary = summary
                await self.db.commit()
                await self.db.refresh(document)
            else:
                logger.warning(f"Summary field does not exist in database, cannot save summary for document {document_id}")
            
            logger.info(f"Summary generated for document {document_id}, length: {len(summary)}")
            return summary
            
        except Exception as e:
            logger.error(f"Error generating summary for document {document_id}: {e}", exc_info=True)
            return None
    
    async def generate_summaries_for_project(self, project_id: UUID) -> int:
        """
        Генерирует summaries для всех документов проекта без summary
        
        Args:
            project_id: ID проекта
        
        Returns:
            Количество созданных summaries
        """
        try:
            # Получаем все документы проекта без summary
            result = await self.db.execute(
                select(Document)
                .where(Document.project_id == project_id)
                .where((Document.summary == None) | (Document.summary == ""))
            )
            documents = result.scalars().all()
            
            count = 0
            for doc in documents:
                summary = await self.generate_summary(doc.id)
                if summary:
                    count += 1
            
            logger.info(f"Generated {count} summaries for project {project_id}")
            return count
            
        except Exception as e:
            logger.error(f"Error generating summaries for project {project_id}: {e}", exc_info=True)
            return 0

