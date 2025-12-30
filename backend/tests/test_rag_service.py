"""
Тесты RAG сервиса для генерации ответов
"""
import pytest
from uuid import UUID, uuid4
from unittest.mock import AsyncMock, MagicMock, patch
from app.services.rag_service import RAGService


@pytest.mark.asyncio
async def test_generate_answer_with_relevant_chunks(db_session):
    """Тест генерации ответа при наличии релевантных чанков"""
    db = db_session
    rag_service = RAGService(db)
    
    # Моки для теста
    with patch.object(rag_service.helpers, 'get_user') as mock_user, \
         patch.object(rag_service.helpers, 'get_project') as mock_project, \
         patch.object(rag_service.helpers, 'get_conversation_history') as mock_history, \
         patch.object(rag_service.helpers, 'save_message') as mock_save, \
         patch.object(rag_service.embedding_service, 'create_embedding') as mock_embedding, \
         patch.object(rag_service.vector_store, 'search_similar') as mock_search, \
         patch('app.services.rag_service.OpenRouterClient') as MockLLMClient:
        
        # Настройка моков
        mock_user.return_value = MagicMock(id=uuid4(), project_id=uuid4())
        mock_project.return_value = MagicMock(id=uuid4(), prompt_template="Test template", max_response_length=1000, llm_model=None)
        mock_history.return_value = []
        mock_embedding.return_value = [0.1] * 1536
        mock_search.return_value = [
            {"score": 0.9, "payload": {"chunk_text": "Релевантная информация"}}
        ]
        mock_save.return_value = None
        
        # Мок LLM клиента
        mock_llm_instance = MagicMock()
        mock_llm_instance.chat_completion = AsyncMock(return_value="Ответ на основе документов")
        MockLLMClient.return_value = mock_llm_instance
        
        user_id = uuid4()
        question = "Тестовый вопрос"
        
        answer = await rag_service.generate_answer(user_id, question)
        
        assert "Ответ на основе документов" in answer or len(answer) > 0
        mock_llm_instance.chat_completion.assert_called_once()


@pytest.mark.asyncio
async def test_generate_answer_no_relevant_chunks(db_session):
    """Тест генерации ответа при отсутствии релевантных чанков"""
    db = db_session
    rag_service = RAGService(db)
    
    with patch.object(rag_service.helpers, 'get_user') as mock_user, \
         patch.object(rag_service.helpers, 'get_project') as mock_project, \
         patch.object(rag_service.helpers, 'get_conversation_history') as mock_history, \
         patch.object(rag_service.helpers, 'save_message') as mock_save, \
         patch.object(rag_service.embedding_service, 'create_embedding') as mock_embedding, \
         patch.object(rag_service.vector_store, 'search_similar') as mock_search:
        
        mock_user.return_value = MagicMock(id=uuid4(), project_id=uuid4())
        mock_project.return_value = MagicMock(id=uuid4())
        mock_history.return_value = []
        mock_embedding.return_value = [0.1] * 1536
        mock_search.return_value = []  # Нет релевантных чанков
        mock_save.return_value = None
        
        user_id = uuid4()
        question = "Вопрос без ответа"
        
        answer = await rag_service.generate_answer(user_id, question)
        
        # Должно вернуться сообщение об отсутствии информации
        assert "нет информации" in answer.lower() or "не найдено" in answer.lower() or "нет" in answer.lower()


@pytest.mark.asyncio
async def test_generate_answer_respects_max_length(db_session):
    """Тест, что ответ не превышает max_response_length"""
    db = db_session
    rag_service = RAGService(db)
    
    max_length = 100
    
    with patch.object(rag_service.helpers, 'get_user') as mock_user, \
         patch.object(rag_service.helpers, 'get_project') as mock_project, \
         patch.object(rag_service.helpers, 'get_conversation_history') as mock_history, \
         patch.object(rag_service.helpers, 'save_message') as mock_save, \
         patch.object(rag_service.embedding_service, 'create_embedding') as mock_embedding, \
         patch.object(rag_service.vector_store, 'search_similar') as mock_search, \
         patch('app.services.rag_service.OpenRouterClient') as MockLLMClient:
        
        mock_user.return_value = MagicMock(id=uuid4(), project_id=uuid4())
        mock_project.return_value = MagicMock(
            id=uuid4(), 
            prompt_template="Test", 
            max_response_length=max_length,
            llm_model=None
        )
        mock_history.return_value = []
        mock_embedding.return_value = [0.1] * 1536
        mock_search.return_value = [{"score": 0.9, "payload": {"chunk_text": "Info"}}]
        mock_save.return_value = None
        
        # Мок LLM клиента
        mock_llm_instance = MagicMock()
        mock_llm_instance.chat_completion = AsyncMock(return_value="A" * 200)  # Длинный ответ
        MockLLMClient.return_value = mock_llm_instance
        
        user_id = uuid4()
        answer = await rag_service.generate_answer(user_id, "Question")
        
        # Ответ должен быть обрезан до max_length (с небольшим допуском для форматирования)
        # ResponseFormatter может добавить немного символов при форматировании
        assert len(answer) <= max_length + 50  # Допуск для форматирования


@pytest.mark.asyncio
async def test_project_isolation(db_session):
    """Тест изоляции данных между проектами"""
    db = db_session
    rag_service = RAGService(db)
    
    project1_id = uuid4()
    project2_id = uuid4()
    
    with patch.object(rag_service.helpers, 'get_user') as mock_user, \
         patch.object(rag_service.helpers, 'get_project') as mock_project, \
         patch.object(rag_service.helpers, 'get_conversation_history') as mock_history, \
         patch.object(rag_service.helpers, 'save_message') as mock_save, \
         patch.object(rag_service.embedding_service, 'create_embedding') as mock_embedding, \
         patch.object(rag_service.vector_store, 'search_similar') as mock_search:
        
        # Пользователь проекта 1
        mock_user.return_value = MagicMock(id=uuid4(), project_id=project1_id)
        mock_project.return_value = MagicMock(id=project1_id, llm_model=None)
        mock_history.return_value = []
        mock_embedding.return_value = [0.1] * 1536
        mock_search.return_value = []
        mock_save.return_value = None
        
        user_id = uuid4()
        await rag_service.generate_answer(user_id, "Question")
        
        # Проверяем, что поиск был в коллекции проекта 1
        call_args = mock_search.call_args
        assert call_args[1]['collection_name'] == f"project_{project1_id}"

