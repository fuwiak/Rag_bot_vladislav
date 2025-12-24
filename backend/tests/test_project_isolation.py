"""
Тесты изоляции данных между проектами
"""
import pytest
from uuid import uuid4
from app.models.project import Project
from app.models.user import User
from app.models.document import Document
from app.services.project_service import ProjectService
from app.services.user_service import UserService
from app.services.document_service import DocumentService


@pytest.mark.asyncio
async def test_project_data_isolation(db_session):
    """Тест изоляции данных между проектами"""
    db = db_session
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
    pytest.skip("Требует подключения к Qdrant - пропускаем в unit тестах")
    # Этот тест должен быть в integration тестах с реальным Qdrant

