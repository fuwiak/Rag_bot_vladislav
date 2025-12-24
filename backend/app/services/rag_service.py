"""
RAG сервис - поиск релевантных фрагментов и генерация ответа
"""
from typing import List, Dict, Optional
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc

from app.models.project import Project
from app.models.user import User
from app.models.message import Message
from app.vector_db.vector_store import VectorStore
from app.services.embedding_service import EmbeddingService
from app.llm.openrouter_client import OpenRouterClient
from app.llm.prompt_builder import PromptBuilder
from app.llm.response_formatter import ResponseFormatter


class RAGService:
    """RAG сервис для генерации ответов на основе документов"""
    
    def __init__(self, db: AsyncSession):
        self.db = db
        self.vector_store = VectorStore()
        self.embedding_service = EmbeddingService()
        self.llm_client = None  # Будет создан с учетом модели проекта
        self.prompt_builder = PromptBuilder()
        self.response_formatter = ResponseFormatter()
    
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
        
        # Создание эмбеддинга вопроса
        question_embedding = await self.embedding_service.create_embedding(question)
        
        # Поиск релевантных чанков в Qdrant
        collection_name = f"project_{project.id}"
        similar_chunks = await self.vector_store.search_similar(
            collection_name=collection_name,
            query_vector=question_embedding,
            limit=top_k,
            score_threshold=0.5
        )
        
        # Извлечение текстов чанков (может быть пустым)
        chunk_texts = []
        if similar_chunks and len(similar_chunks) > 0:
            chunk_texts = [chunk["payload"]["chunk_text"] for chunk in similar_chunks]
        
        # ВСЕГДА используем промпт проекта, даже если документов нет
        # Это позволяет боту отвечать на основе общих знаний, но с учетом настроек проекта
        # Построение промпта с контекстом (может быть пустым)
        messages = self.prompt_builder.build_prompt(
            question=question,
            chunks=chunk_texts,  # Может быть пустым списком
            prompt_template=project.prompt_template,
            max_length=project.max_response_length,
            conversation_history=conversation_history
        )
        
        # Генерация ответа через LLM
        # Получаем глобальные настройки моделей из БД
        from app.models.llm_model import GlobalModelSettings
        from sqlalchemy import select
        import logging
        logger = logging.getLogger(__name__)
        
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
        raw_answer = await llm_client.chat_completion(
            messages=messages,
            max_tokens=max_tokens,
            temperature=0.7
        )
        
        # Форматирование ответа с добавлением цитат (согласно ТЗ п. 5.3.4)
        answer = self.response_formatter.format_response(
            response=raw_answer,
            max_length=project.max_response_length,
            chunks=similar_chunks
        )
        
        # Сохранение сообщений в историю
        await self._save_message(user_id, question, "user")
        await self._save_message(user_id, answer, "assistant")
        
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
        
        # Если релевантных чанков нет
        if not similar_chunks or len(similar_chunks) == 0:
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


