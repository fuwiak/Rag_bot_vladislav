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
        self.llm_client = OpenRouterClient()
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
        
        # Получение истории диалога
        conversation_history = await self._get_conversation_history(user_id, limit=6)
        
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
        
        # Если релевантных чанков нет, возвращаем стандартный ответ
        if not similar_chunks or len(similar_chunks) == 0:
            answer = "В загруженных документах нет информации по этому вопросу."
        else:
            # Извлечение текстов чанков
            chunk_texts = [chunk["payload"]["chunk_text"] for chunk in similar_chunks]
            
            # Построение промпта
            messages = self.prompt_builder.build_prompt(
                question=question,
                chunks=chunk_texts,
                prompt_template=project.prompt_template,
                max_length=project.max_response_length,
                conversation_history=conversation_history
            )
            
            # Генерация ответа через LLM
            max_tokens = project.max_response_length // 4  # Приблизительная оценка токенов
            raw_answer = await self.llm_client.chat_completion(
                messages=messages,
                max_tokens=max_tokens,
                temperature=0.7
            )
            
            # Форматирование ответа
            answer = self.response_formatter.format_response(
                response=raw_answer,
                max_length=project.max_response_length,
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

