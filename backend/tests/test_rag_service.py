"""
Тесты RAG сервиса для генерации ответов
"""
import pytest
from uuid import UUID, uuid4
from unittest.mock import AsyncMock, MagicMock, patch
from app.services.rag_service import RAGService
from app.core.database import AsyncSessionLocal


@pytest.mark.asyncio
async def test_generate_answer_with_relevant_chunks():
    """Тест генерации ответа при наличии релевантных чанков"""
    async with AsyncSessionLocal() as db:
        rag_service = RAGService(db)
        
        # Моки для теста
        with patch.object(rag_service, '_get_user') as mock_user, \
             patch.object(rag_service, '_get_project') as mock_project, \
             patch.object(rag_service, '_get_conversation_history') as mock_history, \
             patch.object(rag_service.embedding_service, 'create_embedding') as mock_embedding, \
             patch.object(rag_service.vector_store, 'search_similar') as mock_search, \
             patch.object(rag_service.llm_client, 'generate_response') as mock_llm:
            
            # Настройка моков
            mock_user.return_value = MagicMock(id=uuid4(), project_id=uuid4())
            mock_project.return_value = MagicMock(id=uuid4(), prompt_template="Test template", max_response_length=1000)
            mock_history.return_value = []
            mock_embedding.return_value = [0.1] * 1536
            mock_search.return_value = [
                {"score": 0.9, "payload": {"chunk_text": "Релевантная информация"}}
            ]
            mock_llm.return_value = "Ответ на основе документов"
            
            user_id = uuid4()
            question = "Тестовый вопрос"
            
            answer = await rag_service.generate_answer(user_id, question)
            
            assert answer == "Ответ на основе документов"
            mock_llm.assert_called_once()


@pytest.mark.asyncio
async def test_generate_answer_no_relevant_chunks():
    """Тест генерации ответа при отсутствии релевантных чанков"""
    async with AsyncSessionLocal() as db:
        rag_service = RAGService(db)
        
        with patch.object(rag_service, '_get_user') as mock_user, \
             patch.object(rag_service, '_get_project') as mock_project, \
             patch.object(rag_service, '_get_conversation_history') as mock_history, \
             patch.object(rag_service.embedding_service, 'create_embedding') as mock_embedding, \
             patch.object(rag_service.vector_store, 'search_similar') as mock_search:
            
            mock_user.return_value = MagicMock(id=uuid4(), project_id=uuid4())
            mock_project.return_value = MagicMock(id=uuid4())
            mock_history.return_value = []
            mock_embedding.return_value = [0.1] * 1536
            mock_search.return_value = []  # Нет релевантных чанков
            
            user_id = uuid4()
            question = "Вопрос без ответа"
            
            answer = await rag_service.generate_answer(user_id, question)
            
            # Должно вернуться сообщение об отсутствии информации
            assert "нет информации" in answer.lower() or "не найдено" in answer.lower()


@pytest.mark.asyncio
async def test_generate_answer_respects_max_length():
    """Тест, что ответ не превышает max_response_length"""
    async with AsyncSessionLocal() as db:
        rag_service = RAGService(db)
        
        max_length = 100
        
        with patch.object(rag_service, '_get_user') as mock_user, \
             patch.object(rag_service, '_get_project') as mock_project, \
             patch.object(rag_service, '_get_conversation_history') as mock_history, \
             patch.object(rag_service.embedding_service, 'create_embedding') as mock_embedding, \
             patch.object(rag_service.vector_store, 'search_similar') as mock_search, \
             patch.object(rag_service.llm_client, 'generate_response') as mock_llm:
            
            mock_user.return_value = MagicMock(id=uuid4(), project_id=uuid4())
            mock_project.return_value = MagicMock(
                id=uuid4(), 
                prompt_template="Test", 
                max_response_length=max_length
            )
            mock_history.return_value = []
            mock_embedding.return_value = [0.1] * 1536
            mock_search.return_value = [{"score": 0.9, "payload": {"chunk_text": "Info"}}]
            mock_llm.return_value = "A" * 200  # Длинный ответ
            
            user_id = uuid4()
            answer = await rag_service.generate_answer(user_id, "Question")
            
            # Ответ должен быть обрезан до max_length
            assert len(answer) <= max_length


@pytest.mark.asyncio
async def test_project_isolation():
    """Тест изоляции данных между проектами"""
    async with AsyncSessionLocal() as db:
        rag_service = RAGService(db)
        
        project1_id = uuid4()
        project2_id = uuid4()
        
        with patch.object(rag_service, '_get_user') as mock_user, \
             patch.object(rag_service, '_get_project') as mock_project, \
             patch.object(rag_service.vector_store, 'search_similar') as mock_search:
            
            # Пользователь проекта 1
            mock_user.return_value = MagicMock(id=uuid4(), project_id=project1_id)
            mock_project.return_value = MagicMock(id=project1_id)
            mock_search.return_value = []
            
            user_id = uuid4()
            await rag_service.generate_answer(user_id, "Question")
            
            # Проверяем, что поиск был в коллекции проекта 1
            call_args = mock_search.call_args
            assert call_args[1]['collection_name'] == f"project_{project1_id}"

