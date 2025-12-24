"""
Тесты авторизации в Telegram-боте
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from aiogram.types import Message, User as TelegramUser, Contact
from aiogram.fsm.context import FSMContext
from app.bot.handlers.auth_handler import handle_password, handle_contact, AuthStates
from app.core.database import AsyncSessionLocal
from app.models.project import Project
from app.models.user import User
from uuid import uuid4


@pytest.mark.asyncio
async def test_password_verification_correct():
    """Тест проверки правильного пароля"""
    project_id = uuid4()
    correct_password = "test123"
    
    # Создаем тестовый проект
    async with AsyncSessionLocal() as db:
        project = Project(
            id=project_id,
            name="Test Project",
            access_password=correct_password,
            prompt_template="Test",
            max_response_length=1000
        )
        db.add(project)
        await db.commit()
    
    # Мок сообщения
    message = MagicMock(spec=Message)
    message.text = correct_password
    message.bot.token = "test_token"
    message.answer = AsyncMock()
    
    state = MagicMock(spec=FSMContext)
    state.update_data = AsyncMock()
    state.set_state = AsyncMock()
    
    await handle_password(message, state, str(project_id))
    
    # Проверяем, что состояние изменилось на waiting_phone
    state.set_state.assert_called_with(AuthStates.waiting_phone)
    message.answer.assert_called_once()


@pytest.mark.asyncio
async def test_password_verification_incorrect():
    """Тест проверки неправильного пароля"""
    project_id = uuid4()
    correct_password = "test123"
    wrong_password = "wrong"
    
    async with AsyncSessionLocal() as db:
        project = Project(
            id=project_id,
            name="Test Project",
            access_password=correct_password,
            prompt_template="Test",
            max_response_length=1000
        )
        db.add(project)
        await db.commit()
    
    message = MagicMock(spec=Message)
    message.text = wrong_password
    message.bot.token = "test_token"
    message.answer = AsyncMock()
    
    state = MagicMock(spec=FSMContext)
    
    await handle_password(message, state, str(project_id))
    
    # Проверяем, что отправлено сообщение об ошибке
    message.answer.assert_called()
    assert "неверный" in message.answer.call_args[0][0].lower() or "ошибка" in message.answer.call_args[0][0].lower()


@pytest.mark.asyncio
async def test_phone_collection_and_user_creation():
    """Тест сбора номера телефона и создания пользователя"""
    project_id = uuid4()
    
    async with AsyncSessionLocal() as db:
        project = Project(
            id=project_id,
            name="Test Project",
            access_password="test123",
            prompt_template="Test",
            max_response_length=1000
        )
        db.add(project)
        await db.commit()
    
    # Мок контакта
    contact = MagicMock(spec=Contact)
    contact.phone_number = "+1234567890"
    
    message = MagicMock(spec=Message)
    message.contact = contact
    message.from_user = MagicMock(spec=TelegramUser)
    message.from_user.username = "testuser"
    message.answer = AsyncMock()
    
    state = MagicMock(spec=FSMContext)
    state.get_data = AsyncMock(return_value={"project_id": str(project_id)})
    state.update_data = AsyncMock()
    state.set_state = AsyncMock()
    
    await handle_contact(message, state, str(project_id))
    
    # Проверяем, что пользователь создан
    async with AsyncSessionLocal() as db:
        from app.services.user_service import UserService
        user_service = UserService(db)
        user = await user_service.get_user_by_phone(project_id, contact.phone_number)
        assert user is not None
        assert user.phone == contact.phone_number
    
    # Проверяем, что состояние изменилось на authorized
    state.set_state.assert_called_with(AuthStates.authorized)

