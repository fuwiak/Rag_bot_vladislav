"""
Тесты изоляции данных между проектами
"""
import pytest
from uuid import uuid4
from app.core.database import AsyncSessionLocal
from app.models.project import Project
from app.models.user import User
from app.models.document import Document
from app.services.project_service import ProjectService
from app.services.user_service import UserService
from app.services.document_service import DocumentService


@pytest.mark.asyncio
async def test_project_data_isolation():
    """Тест изоляции данных между проектами"""
    async with AsyncSessionLocal() as db:
        # Создаем два проекта
        project1 = Project(
            name="Project 1",
            access_password="pass1",
            prompt_template="Template 1",
            max_response_length=1000
        )
        project2 = Project(
            name="Project 2",
            access_password="pass2",
            prompt_template="Template 2",
            max_response_length=2000
        )
        db.add(project1)
        db.add(project2)
        await db.commit()
        await db.refresh(project1)
        await db.refresh(project2)
        
        # Создаем пользователей в разных проектах
        user_service = UserService(db)
        user1 = await user_service.create_user(project1.id, "+1111111111", "user1")
        user2 = await user_service.create_user(project2.id, "+2222222222", "user2")
        
        # Проверяем изоляцию
        users_project1 = await user_service.get_project_users(project1.id)
        users_project2 = await user_service.get_project_users(project2.id)
        
        assert len(users_project1) == 1
        assert len(users_project2) == 1
        assert users_project1[0].id == user1.id
        assert users_project2[0].id == user2.id
        
        # Пользователь проекта 1 не должен быть в проекте 2
        user1_in_project2 = await user_service.get_user_by_phone(project2.id, user1.phone)
        assert user1_in_project2 is None


@pytest.mark.asyncio
async def test_vector_search_isolation():
    """Тест изоляции векторного поиска между проектами"""
    from app.vector_db.vector_store import VectorStore
    from app.services.embedding_service import EmbeddingService
    
    project1_id = uuid4()
    project2_id = uuid4()
    
    embedding_service = EmbeddingService()
    vector_store = VectorStore()
    
    # Создаем эмбеддинги для разных проектов
    embedding1 = await embedding_service.create_embedding("Документ проекта 1")
    embedding2 = await embedding_service.create_embedding("Документ проекта 2")
    
    # Сохраняем в разные коллекции
    await vector_store.store_vector(
        collection_name=f"project_{project1_id}",
        vector=embedding1,
        payload={"text": "Проект 1"}
    )
    
    await vector_store.store_vector(
        collection_name=f"project_{project2_id}",
        vector=embedding2,
        payload={"text": "Проект 2"}
    )
    
    # Ищем в коллекции проекта 1
    results1 = await vector_store.search_similar(
        collection_name=f"project_{project1_id}",
        query_vector=embedding1,
        limit=5
    )
    
    # Ищем в коллекции проекта 2
    results2 = await vector_store.search_similar(
        collection_name=f"project_{project2_id}",
        query_vector=embedding2,
        limit=5
    )
    
    # Проверяем изоляцию
    assert len(results1) > 0
    assert len(results2) > 0
    # Результаты из проекта 1 не должны быть в проекте 2
    assert all(r["payload"]["text"] == "Проект 1" for r in results1)
    assert all(r["payload"]["text"] == "Проект 2" for r in results2)

