"""
Сервис для создания summary документов через LLM
Поддерживает анализ больших PDF документов с использованием LangGraph
"""
import logging
from typing import Optional, List, Dict, Any
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


# === РЕКОМЕНДАЦИИ ПО ИСПОЛЬЗОВАНИЮ МОДЕЛЕЙ ДЛЯ SUMMARY ===
"""
РЕКОМЕНДАЦИИ ПО ОБЪЕМУ ТЕКСТА:

1. Для документов до 50 страниц (~100K символов):
   - Анализируем весь документ целиком
   - chunk_size: 1500 символов
   - max_context: 100K символов
   - Рекомендуемые модели: Claude 3.5 Sonnet, GPT-4 Turbo

2. Для документов 50-200 страниц (~100-400K символов):
   - Используем стратегию "начало + середина + конец"
   - Каждая часть ~30K символов
   - Рекомендуемые модели: Claude 3.5 Sonnet (128K контекст)

3. Для документов 200+ страниц (>400K символов):
   - Используем иерархическое резюме (Map-Reduce)
   - Разбиваем на секции, резюмируем каждую, объединяем
   - Рекомендуемые модели: GPT-4 Turbo, Claude 3.5 Sonnet

ФОРМАТ ПРОМПТОВ ДЛЯ МИНИМАЛЬНЫХ ИСКАЖЕНИЙ:

1. Точность фактов:
   - "Сохрани точность: цифры, даты, имена собственные"
   - "Не добавляй информацию, которой нет в документе"

2. Структура:
   - "Начни с главной темы документа"
   - "Перечисли ключевые пункты"
   - "Сделай выводы на основе документа"

3. Параметры генерации:
   - temperature: 0.1-0.2 (низкая для точности)
   - max_tokens: 500-1000 (достаточно для полного summary)
"""


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
            content_length = len(content) if content else 0
            
            logger.info(f"[SUMMARY] 🔍 Проверка контента документа {document_id} ({document.filename}):")
            logger.info(f"[SUMMARY]   - Content length: {content_length} символов")
            logger.info(f"[SUMMARY]   - Content status: {content[:100] if content else 'EMPTY'}...")
            logger.info(f"[SUMMARY]   - Content is 'Обработка...': {content == 'Обработка...'}")
            logger.info(f"[SUMMARY]   - Content is empty: {not content or content == ''}")
            
            if not content or content in ["Обработка...", "Обработан", ""]:
                logger.warning(f"[SUMMARY] ⚠️ Document {document_id} ({document.filename}) has no content yet!")
                logger.warning(f"[SUMMARY] ⚠️ Content value: '{content}'")
                logger.warning(f"[SUMMARY] ⚠️ Это означает, что документ еще не обработан или обработка не завершена")
                logger.warning(f"[SUMMARY] ⚠️ Summary будет создан только на основе метаданных (название файла)")
                # Возвращаем None, чтобы использовались метаданные
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
    
    async def generate_summary_with_langgraph(self, document_id: UUID) -> Optional[str]:
        """
        Генерирует summary документа с использованием LangGraph workflow
        Оптимизировано для больших документов
        
        Args:
            document_id: ID документа
        
        Returns:
            Summary документа или None при ошибке
        """
        try:
            from app.services.langgraph_rag_workflow import (
                LangGraphRAGWorkflow, 
                QueryType,
                RAGConfig
            )
            
            # Получаем документ
            result = await self.db.execute(
                select(Document).where(Document.id == document_id)
            )
            document = result.scalar_one_or_none()
            
            if not document:
                logger.error(f"Document {document_id} not found")
                return None
            
            # Конфигурация для создания summary с минимальными искажениями
            config = RAGConfig(
                max_context_tokens=100000,
                max_output_tokens=1000,
                chunk_size=2000,
                chunk_overlap=400,
                top_k_retrieval=20,
                temperature=0.1  # Очень низкая для точности
            )
            
            # Запускаем LangGraph workflow
            rag_workflow = LangGraphRAGWorkflow(self.db, config)
            result = await rag_workflow.run(
                query=f"Создай точное резюме документа {document.filename}",
                query_type=QueryType.SUMMARY,
                project_id=str(document.project_id),
                document_id=str(document_id)
            )
            
            summary = result.get('answer', '')
            
            if summary:
                # Сохраняем summary в БД
                if hasattr(document, 'summary'):
                    document.summary = summary
                    await self.db.commit()
                    await self.db.refresh(document)
                
                logger.info(f"LangGraph summary generated for document {document_id}, length: {len(summary)}")
                return summary
            
            return None
            
        except Exception as e:
            logger.error(f"Error generating LangGraph summary for document {document_id}: {e}", exc_info=True)
            return None
    
    async def generate_map_reduce_summary(
        self, 
        document_id: UUID,
        max_chunk_size: int = 30000
    ) -> Optional[str]:
        """
        Генерирует summary очень длинного документа методом Map-Reduce
        
        Стратегия:
        1. Разбиваем документ на большие секции
        2. Создаем summary для каждой секции (Map)
        3. Объединяем секционные summaries в финальное (Reduce)
        
        Args:
            document_id: ID документа
            max_chunk_size: Максимальный размер секции (символов)
        
        Returns:
            Summary документа или None при ошибке
        """
        try:
            # Получаем документ
            result = await self.db.execute(
                select(Document).where(Document.id == document_id)
            )
            document = result.scalar_one_or_none()
            
            if not document or not document.content:
                logger.error(f"Document {document_id} not found or empty")
                return None
            
            content = document.content
            content_length = len(content)
            
            logger.info(f"[Map-Reduce] Starting for document {document_id}, length: {content_length}")
            
            # Если документ небольшой - используем обычный метод
            if content_length <= max_chunk_size:
                return await self.generate_summary(document_id)
            
            # Разбиваем на секции
            sections = []
            for i in range(0, content_length, max_chunk_size):
                section = content[i:i + max_chunk_size]
                sections.append(section)
            
            logger.info(f"[Map-Reduce] Document split into {len(sections)} sections")
            
            # Получаем настройки LLM
            primary_model, fallback_model = await self._get_llm_models(document.project_id)
            llm_client = OpenRouterClient(
                model_primary=primary_model,
                model_fallback=fallback_model
            )
            
            # Map: Создаем summary для каждой секции
            section_summaries = []
            for i, section in enumerate(sections):
                logger.info(f"[Map-Reduce] Processing section {i+1}/{len(sections)}")
                
                map_prompt = f"""Создай краткое резюме следующей части документа ({i+1}/{len(sections)}):

СОДЕРЖИМОЕ:
{section}

РЕЗЮМЕ ЧАСТИ (100-200 слов):"""
                
                messages = [
                    {"role": "system", "content": "Ты эксперт по созданию точных резюме. Сохраняй все ключевые факты."},
                    {"role": "user", "content": map_prompt}
                ]
                
                try:
                    section_summary = await llm_client.chat_completion(
                        messages=messages,
                        max_tokens=400,
                        temperature=0.1
                    )
                    section_summaries.append(f"Часть {i+1}: {section_summary.strip()}")
                except Exception as e:
                    logger.warning(f"[Map-Reduce] Error summarizing section {i+1}: {e}")
                    continue
            
            if not section_summaries:
                logger.error("[Map-Reduce] No section summaries generated")
                return None
            
            # Reduce: Объединяем в финальное summary
            combined_summaries = "\n\n".join(section_summaries)
            
            reduce_prompt = f"""На основе резюме частей документа "{document.filename}" создай единое итоговое резюме.

РЕЗЮМЕ ЧАСТЕЙ:
{combined_summaries}

ТРЕБОВАНИЯ К ИТОГОВОМУ РЕЗЮМЕ:
1. Длина: 500-1000 символов
2. Включи ВСЕ ключевые темы из всех частей
3. Сохрани точность: цифры, даты, имена
4. Структура: главная тема → ключевые пункты → выводы
5. Язык: русский

ИТОГОВОЕ РЕЗЮМЕ:"""
            
            messages = [
                {"role": "system", "content": get_prompt("prompts.system.summary_generator")},
                {"role": "user", "content": reduce_prompt}
            ]
            
            final_summary = await llm_client.chat_completion(
                messages=messages,
                max_tokens=800,
                temperature=0.1
            )
            
            final_summary = final_summary.strip()
            
            # Сохраняем в БД
            if hasattr(document, 'summary'):
                document.summary = final_summary
                await self.db.commit()
                await self.db.refresh(document)
            
            logger.info(f"[Map-Reduce] Final summary generated, length: {len(final_summary)}")
            return final_summary
            
        except Exception as e:
            logger.error(f"[Map-Reduce] Error: {e}", exc_info=True)
            return None
    
    async def _get_llm_models(self, project_id: UUID) -> tuple:
        """Получает настройки LLM моделей для проекта"""
        primary_model = None
        fallback_model = None
        
        try:
            # Получаем проект
            project_result = await self.db.execute(
                select(Project).where(Project.id == project_id)
            )
            project = project_result.scalar_one_or_none()
            
            if project and project.llm_model:
                primary_model = project.llm_model
            else:
                # Глобальные настройки
                settings_result = await self.db.execute(select(GlobalModelSettings).limit(1))
                global_settings = settings_result.scalar_one_or_none()
                if global_settings:
                    primary_model = global_settings.primary_model_id
                    fallback_model = global_settings.fallback_model_id
        except Exception as e:
            logger.warning(f"Error getting LLM models: {e}")
        
        if not primary_model:
            primary_model = app_settings.OPENROUTER_MODEL_PRIMARY
        if not fallback_model:
            fallback_model = app_settings.OPENROUTER_MODEL_FALLBACK
        
        return primary_model, fallback_model
    
    async def describe_document_content(self, document_id: UUID) -> Optional[str]:
        """
        Создает описание содержания документа
        
        Args:
            document_id: ID документа
        
        Returns:
            Описание содержания или None при ошибке
        """
        try:
            from app.services.langgraph_rag_workflow import (
                LangGraphRAGWorkflow, 
                QueryType
            )
            
            # Получаем документ
            result = await self.db.execute(
                select(Document).where(Document.id == document_id)
            )
            document = result.scalar_one_or_none()
            
            if not document:
                return None
            
            # Запускаем LangGraph workflow
            rag_workflow = LangGraphRAGWorkflow(self.db)
            result = await rag_workflow.run(
                query=f"Опиши содержание документа {document.filename}",
                query_type=QueryType.DESCRIPTION,
                project_id=str(document.project_id),
                document_id=str(document_id)
            )
            
            return result.get('answer', '')
            
        except Exception as e:
            logger.error(f"Error describing document {document_id}: {e}", exc_info=True)
            return None
    
    async def analyze_document(self, document_id: UUID) -> Optional[Dict[str, Any]]:
        """
        Проводит глубокий анализ документа
        
        Args:
            document_id: ID документа
        
        Returns:
            Словарь с анализом: тип, темы, ключевые сущности, структура
        """
        try:
            from app.services.langgraph_rag_workflow import (
                LangGraphRAGWorkflow, 
                QueryType
            )
            
            # Получаем документ
            result = await self.db.execute(
                select(Document).where(Document.id == document_id)
            )
            document = result.scalar_one_or_none()
            
            if not document:
                return None
            
            # Запускаем LangGraph workflow
            rag_workflow = LangGraphRAGWorkflow(self.db)
            result = await rag_workflow.run(
                query=f"Проанализируй документ {document.filename}",
                query_type=QueryType.ANALYSIS,
                project_id=str(document.project_id),
                document_id=str(document_id)
            )
            
            return {
                'document_id': str(document_id),
                'filename': document.filename,
                'analysis': result.get('answer', ''),
                'sources': result.get('sources', []),
                'metadata': result.get('metadata', {})
            }
            
        except Exception as e:
            logger.error(f"Error analyzing document {document_id}: {e}", exc_info=True)
            return None

