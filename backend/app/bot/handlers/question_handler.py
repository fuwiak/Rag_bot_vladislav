"""
Обработчики вопросов пользователей
"""
from aiogram import Dispatcher, F
from aiogram.types import Message
from aiogram.fsm.context import FSMContext
from uuid import UUID

from app.core.database import AsyncSessionLocal
from app.bot.handlers.auth_handler import AuthStates
from app.services.rag_service import RAGService


async def handle_question(message: Message, state: FSMContext, project_id: str = None):
    """Обработка вопроса пользователя"""
    # Проверка авторизации
    current_state = await state.get_state()
    if current_state != AuthStates.authorized:
        await message.answer("Пожалуйста, сначала авторизуйтесь через /start")
        return
    
    # Получение user_id из состояния
    data = await state.get_data()
    user_id_str = data.get("user_id")
    
    if not user_id_str:
        await message.answer("Ошибка: пользователь не найден. Используйте /start")
        return
    
    user_id = UUID(user_id_str)
    question = message.text
    
    # Отправка сообщения о том, что идет обработка
    processing_msg = await message.answer("⏳ Обрабатываю ваш вопрос...")
    
    try:
        # Генерация ответа через RAG сервис
        async with AsyncSessionLocal() as db:
            rag_service = RAGService(db)
            answer = await rag_service.generate_answer(user_id, question)
        
        # Удаление сообщения об обработке
        await processing_msg.delete()
        
        # Отправка ответа (разбиваем на части если длинный)
        max_length = 4096  # Максимальная длина сообщения Telegram
        if len(answer) > max_length:
            # Разбиваем на части
            parts = [answer[i:i+max_length] for i in range(0, len(answer), max_length)]
            for part in parts:
                await message.answer(part)
        else:
            await message.answer(answer)
    
    except Exception as e:
        await processing_msg.delete()
        await message.answer(
            f"❌ Произошла ошибка при обработке вашего вопроса.\n"
            f"Попробуйте позже или обратитесь к администратору.\n\n"
            f"Ошибка: {str(e)}"
        )


def register_question_handlers(dp: Dispatcher, project_id: str):
    """Регистрация обработчиков вопросов"""
    dp.message.register(handle_question, AuthStates.authorized, F.text)

