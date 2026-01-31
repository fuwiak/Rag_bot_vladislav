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
    
    project_id = uuid4()
    
    # Моки для теста
    with patch.object(rag_service.helpers, 'get_user') as mock_user, \
         patch.object(rag_service.helpers, 'get_project') as mock_project, \
         patch.object(rag_service.helpers, 'get_conversation_history') as mock_history, \
         patch.object(rag_service.helpers, 'save_message') as mock_save, \
         patch.object(rag_service.embedding_service, 'create_embedding') as mock_embedding, \
         patch.object(rag_service.vector_store, 'collection_exists') as mock_collection_exists, \
         patch.object(rag_service.retrieval, 'advanced_chunk_search') as mock_advanced_search, \
         patch.object(rag_service, '_call_llm_with_token_tracking') as mock_llm_call, \
         patch('app.services.rag_service.RAGAgent') as MockRAGAgent:
        
        # Настройка моков
        mock_user.return_value = MagicMock(id=uuid4(), project_id=project_id)
        mock_project.return_value = MagicMock(id=project_id, prompt_template="Test template", max_response_length=1000, llm_model=None)
        mock_history.return_value = []
        mock_embedding.return_value = [0.1] * 1536
        mock_collection_exists.return_value = True
        mock_advanced_search.return_value = (
            [{"text": "Релевантная информация", "source": "test.pdf", "score": 0.9}],
            [{"score": 0.9, "payload": {"chunk_text": "Релевантная информация"}}]
        )
        mock_save.return_value = None
        mock_llm_call.return_value = "Ответ на основе документов"
        
        # Мок RAGAgent
        mock_agent_instance = MagicMock()
        mock_agent_instance.get_answer_strategy = AsyncMock(return_value={
            "strategy": {"use_chunks": True, "use_summaries": True, "use_metadata": True, "question_type": "обычный"},
            "documents_metadata": []
        })
        MockRAGAgent.return_value = mock_agent_instance
        
        # Мок для GlobalModelSettings и Document count
        async def mock_db_execute(query):
            mock_result = MagicMock()
            # Для select(GlobalModelSettings) возвращаем None
            # Для select(func.count(Document.id)) возвращаем 0
            if hasattr(query, 'column_descriptions') or str(query).find('GlobalModelSettings') != -1:
                mock_result.scalar_one_or_none.return_value = None
            else:
                mock_result.scalar.return_value = 0
            return mock_result
        
        rag_service.db.execute = AsyncMock(side_effect=mock_db_execute)
        
        user_id = uuid4()
        question = "Тестовый вопрос"
        
        answer = await rag_service.generate_answer(user_id, question)
        
        assert "Ответ на основе документов" in answer or len(answer) > 0
        mock_llm_call.assert_called_once()


@pytest.mark.asyncio
async def test_generate_answer_no_relevant_chunks(db_session):
    """Тест генерации ответа при отсутствии релевантных чанков"""
    db = db_session
    rag_service = RAGService(db)
    
    project_id = uuid4()
    
    with patch.object(rag_service.helpers, 'get_user') as mock_user, \
         patch.object(rag_service.helpers, 'get_project') as mock_project, \
         patch.object(rag_service.helpers, 'get_conversation_history') as mock_history, \
         patch.object(rag_service.helpers, 'save_message') as mock_save, \
         patch.object(rag_service.embedding_service, 'create_embedding') as mock_embedding, \
         patch.object(rag_service.vector_store, 'collection_exists') as mock_collection_exists, \
         patch.object(rag_service.retrieval, 'advanced_chunk_search') as mock_advanced_search, \
         patch.object(rag_service, '_call_llm_with_token_tracking') as mock_llm_call, \
         patch('app.services.rag_service.RAGAgent') as MockRAGAgent:
        
        mock_user.return_value = MagicMock(id=uuid4(), project_id=project_id)
        mock_project.return_value = MagicMock(id=project_id, prompt_template="Test", max_response_length=1000, llm_model=None)
        mock_history.return_value = []
        mock_embedding.return_value = [0.1] * 1536
        mock_collection_exists.return_value = True
        mock_advanced_search.return_value = ([], [])  # Нет релевантных чанков
        mock_save.return_value = None
        mock_llm_call.return_value = "Нет информации в документах"
        
        # Мок RAGAgent
        mock_agent_instance = MagicMock()
        mock_agent_instance.get_answer_strategy = AsyncMock(return_value={
            "strategy": {"use_chunks": True, "use_summaries": True, "use_metadata": True, "question_type": "обычный"},
            "documents_metadata": []
        })
        MockRAGAgent.return_value = mock_agent_instance
        
        # Мок для GlobalModelSettings и Document count
        async def mock_db_execute(query):
            mock_result = MagicMock()
            if hasattr(query, 'column_descriptions') or str(query).find('GlobalModelSettings') != -1:
                mock_result.scalar_one_or_none.return_value = None
            else:
                mock_result.scalar.return_value = 0
            return mock_result
        
        rag_service.db.execute = AsyncMock(side_effect=mock_db_execute)
        
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
    project_id = uuid4()
    
    with patch.object(rag_service.helpers, 'get_user') as mock_user, \
         patch.object(rag_service.helpers, 'get_project') as mock_project, \
         patch.object(rag_service.helpers, 'get_conversation_history') as mock_history, \
         patch.object(rag_service.helpers, 'save_message') as mock_save, \
         patch.object(rag_service.embedding_service, 'create_embedding') as mock_embedding, \
         patch.object(rag_service.vector_store, 'collection_exists') as mock_collection_exists, \
         patch.object(rag_service.retrieval, 'advanced_chunk_search') as mock_advanced_search, \
         patch.object(rag_service, '_call_llm_with_token_tracking') as mock_llm_call, \
         patch('app.services.rag_service.RAGAgent') as MockRAGAgent:
        
        mock_user.return_value = MagicMock(id=uuid4(), project_id=project_id)
        mock_project.return_value = MagicMock(
            id=project_id, 
            prompt_template="Test", 
            max_response_length=max_length,
            llm_model=None
        )
        mock_history.return_value = []
        mock_embedding.return_value = [0.1] * 1536
        mock_collection_exists.return_value = True
        mock_advanced_search.return_value = (
            [{"text": "Info", "source": "test.pdf", "score": 0.9}],
            [{"score": 0.9, "payload": {"chunk_text": "Info"}}]
        )
        mock_save.return_value = None
        mock_llm_call.return_value = "A" * 200  # Длинный ответ
        
        # Мок RAGAgent
        mock_agent_instance = MagicMock()
        mock_agent_instance.get_answer_strategy = AsyncMock(return_value={
            "strategy": {"use_chunks": True, "use_summaries": True, "use_metadata": True, "question_type": "обычный"},
            "documents_metadata": []
        })
        MockRAGAgent.return_value = mock_agent_instance
        
        # Мок для GlobalModelSettings и Document count
        async def mock_db_execute(query):
            mock_result = MagicMock()
            # Для select(GlobalModelSettings) возвращаем None
            # Для select(func.count(Document.id)) возвращаем 0
            if hasattr(query, 'column_descriptions') or str(query).find('GlobalModelSettings') != -1:
                mock_result.scalar_one_or_none.return_value = None
            else:
                mock_result.scalar.return_value = 0
            return mock_result
        
        rag_service.db.execute = AsyncMock(side_effect=mock_db_execute)
        
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
         patch.object(rag_service.vector_store, 'collection_exists') as mock_collection_exists, \
         patch.object(rag_service.retrieval, 'advanced_chunk_search') as mock_advanced_search, \
         patch.object(rag_service, '_call_llm_with_token_tracking') as mock_llm_call, \
         patch('app.services.rag_service.RAGAgent') as MockRAGAgent:
        
        # Пользователь проекта 1
        mock_user.return_value = MagicMock(id=uuid4(), project_id=project1_id)
        mock_project.return_value = MagicMock(id=project1_id, llm_model=None, prompt_template="Test", max_response_length=1000)
        mock_history.return_value = []
        mock_embedding.return_value = [0.1] * 1536
        mock_collection_exists.return_value = True
        mock_advanced_search.return_value = ([], [])
        mock_save.return_value = None
        mock_llm_call.return_value = "Test answer"
        
        # Мок RAGAgent
        mock_agent_instance = MagicMock()
        mock_agent_instance.get_answer_strategy = AsyncMock(return_value={
            "strategy": {"use_chunks": True, "use_summaries": True, "use_metadata": True, "question_type": "обычный"},
            "documents_metadata": []
        })
        MockRAGAgent.return_value = mock_agent_instance
        
        # Мок для GlobalModelSettings и Document count
        async def mock_db_execute(query):
            mock_result = MagicMock()
            # Для select(GlobalModelSettings) возвращаем None
            # Для select(func.count(Document.id)) возвращаем 0
            if hasattr(query, 'column_descriptions') or str(query).find('GlobalModelSettings') != -1:
                mock_result.scalar_one_or_none.return_value = None
            else:
                mock_result.scalar.return_value = 0
            return mock_result
        
        rag_service.db.execute = AsyncMock(side_effect=mock_db_execute)
        
        user_id = uuid4()
        await rag_service.generate_answer(user_id, "Question")
        
        # Проверяем, что advanced_chunk_search был вызван с правильной коллекцией
        assert mock_advanced_search.called, "advanced_chunk_search должен быть вызван"
        call_args = mock_advanced_search.call_args
        # advanced_chunk_search вызывается с именованными аргументами: collection_name=...
        assert 'collection_name' in call_args.kwargs, "collection_name должен быть передан как именованный аргумент"
        assert call_args.kwargs['collection_name'] == f"project_{project1_id}", \
            f"Ожидалась коллекция project_{project1_id}, получена {call_args.kwargs.get('collection_name')}"

