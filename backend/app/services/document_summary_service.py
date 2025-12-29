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
from app.core.prompt_config import get_prompt

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
            # Получаем документ (безопасно, даже если поле summary отсутствует)
            try:
                result = await self.db.execute(
                    select(Document).where(Document.id == document_id)
                )
                document = result.scalar_one_or_none()
            except Exception as db_error:
                # Если ошибка из-за отсутствия поля summary, используем raw SQL
                error_str = str(db_error).lower()
                if "summary" in error_str or "column" in error_str:
                    logger.warning(f"Summary column not found in DB, using raw SQL query")
                    from sqlalchemy import text
                    result = await self.db.execute(
                        text("SELECT id, project_id, filename, content, file_type, created_at FROM documents WHERE id = :doc_id"),
                        {"doc_id": str(document_id)}
                    )
                    row = result.first()
                    if not row:
                        logger.error(f"Document {document_id} not found")
                        return None
                    # Создаем объект Document вручную
                    document = Document()
                    document.id = row[0]
                    document.project_id = row[1]
                    document.filename = row[2]
                    document.content = row[3] if row[3] else ""
                    document.file_type = row[4]
                    document.created_at = row[5]
                    # Поле summary отсутствует
                    try:
                        setattr(document, 'summary', None)
                    except:
                        pass
                else:
                    raise
            
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
            
            # ✅ ОПТИМИЗАЦИЯ: Анализируем весь документ с умным подходом
            # Для очень длинных документов используем стратегию анализа по частям
            content_length = len(content)
            max_context_length = 100000  # Максимальная длина для одного запроса (100k символов)
            
            if content_length <= max_context_length:
                # Документ помещается в один запрос - анализируем целиком
                content_for_summary = content
                logger.info(f"Document {document_id} fits in one request ({content_length} chars), analyzing full content")
            else:
                # Документ слишком длинный - используем стратегию анализа по частям
                logger.info(f"Document {document_id} is very long ({content_length} chars), using multi-part analysis")
                # Берем начало, середину и конец документа для полного понимания
                part_size = max_context_length // 3
                beginning = content[:part_size]
                middle_start = content_length // 2 - part_size // 2
                middle = content[middle_start:middle_start + part_size]
                end = content[-part_size:]
                
                content_for_summary = f"""НАЧАЛО ДОКУМЕНТА:
{beginning}

СЕРЕДИНА ДОКУМЕНТА:
{middle}

КОНЕЦ ДОКУМЕНТА:
{end}

ПРИМЕЧАНИЕ: Документ содержит {content_length} символов. Проанализируй все три части для создания полного summary."""
                logger.info(f"Using multi-part analysis: beginning ({len(beginning)}), middle ({len(middle)}), end ({len(end)})")
            
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
            
            # ✅ УЛУЧШЕННЫЙ ПРОМПТ для создания summary с минимальными искажениями
            prompt = f"""Проанализируй весь документ и создай точное краткое содержание (summary) на русском языке.

Название файла: {document.filename}
Тип файла: {document.file_type}
Общая длина документа: {content_length} символов

СОДЕРЖИМОЕ ДОКУМЕНТА:
{content_for_summary}

КРИТИЧЕСКИ ВАЖНЫЕ ТРЕБОВАНИЯ К SUMMARY:
1. Язык: ТОЛЬКО русский язык
2. Длина: 300-600 символов (достаточно для полного описания)
3. Точность: Отрази ВСЕ основные темы и ключевую информацию из документа
4. Минимальные искажения: Сохрани точность фактов, цифр, дат, имен собственных
5. Структура: Начни с главной темы, затем ключевые пункты
6. Полнота: Упомяни все важные аспекты документа
7. Формат: Сплошной текст без маркеров, нумерации или заголовков
8. Стиль: Информативный, профессиональный, без лишних слов

ВАЖНО: 
- Если документ содержит специфические термины, используй их точно
- Если есть важные цифры или даты, включи их в summary
- Сохрани логическую структуру документа
- Не добавляй информацию, которой нет в документе

Создай только summary, без дополнительных комментариев или предисловий:"""
            
            messages = [
                {
                    "role": "system",
                    "content": get_prompt("prompts.system.summary_generator")
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ]
            
            logger.info(f"Generating summary for document {document_id} ({document.filename}), content length: {content_length}")
            # ✅ Увеличиваем max_tokens для более подробного summary (300->500)
            # ✅ Низкая temperature (0.2) для максимальной точности и минимальных искажений
            summary = await llm_client.chat_completion(
                messages=messages,
                max_tokens=500,  # Увеличено для более полного summary
                temperature=0.2  # Снижено для максимальной точности
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

