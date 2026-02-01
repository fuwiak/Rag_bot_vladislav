"""
Helper methods for RAG service - database operations and utilities
"""
from typing import List, Dict, Optional
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc, text

from app.models.user import User
from app.models.project import Project
from app.models.message import Message
from app.models.document import Document
from app.observability.structured_logging import get_logger

logger = get_logger(__name__)


class RAGHelpers:
    """Helper methods for RAG service"""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def get_user(self, user_id: UUID) -> Optional[User]:
        """Получить пользователя"""
        result = await self.db.execute(select(User).where(User.id == user_id))
        return result.scalar_one_or_none()
    
    async def get_project(self, project_id: UUID) -> Optional[Project]:
        """Получить проект"""
        result = await self.db.execute(select(Project).where(Project.id == project_id))
        return result.scalar_one_or_none()
    
    async def get_conversation_history(self, user_id: UUID, limit: int = 10) -> List[Dict[str, str]]:
        """Получить историю диалога (последние 10 сообщений по умолчанию)"""
        result = await self.db.execute(
            select(Message)
            .where(Message.user_id == user_id)
            .order_by(desc(Message.created_at))
            .limit(limit)
        )
        messages = list(result.scalars().all())
        
        # Преобразование в обратный порядок - от старых к новым
        history = []
        for msg in reversed(messages):
            history.append({
                "role": msg.role,
                "content": msg.content
            })
        
        return history
    
    async def save_message(self, user_id: UUID, content: str, role: str):
        """Сохранить сообщение в историю"""
        message = Message(
            user_id=user_id,
            content=content,
            role=role
        )
        self.db.add(message)
        await self.db.commit()
    
    async def get_document_summaries(self, project_id: UUID, limit: int = 5) -> List[Dict[str, any]]:
        """
        Получает summaries документов проекта для использования в RAG
        
        Args:
            project_id: ID проекта
            limit: Максимальное количество summaries
        
        Returns:
            Список summaries документов в формате [{"text": "...", "source": "...", "score": ...}]
        """
        try:
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
                    logger.warning(f"[RAG HELPERS] Summary column not found in DB, using raw SQL query")
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
                        logger.error(f"[RAG HELPERS] Error with raw SQL query: {sql_error}")
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
                    continue
                
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
            
            logger.info(f"[RAG HELPERS] Retrieved {len(summaries)} document summaries for project {project_id}")
            return summaries
        except Exception as e:
            logger.error(f"[RAG HELPERS] Error getting document summaries: {e}", exc_info=True)
            return []
