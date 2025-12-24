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
    import logging
    logger = logging.getLogger(__name__)
    
    # Проверка авторизации
    current_state = await state.get_state()
    logger.info(f"[QUESTION HANDLER] Current state: {current_state}, Message text: {message.text[:50] if message.text else 'None'}")
    
    if current_state != AuthStates.authorized:
        await message.answer("Пожалуйста, сначала авторизуйтесь через /start")
        return
    
    # Получение user_id из состояния
    data = await state.get_data()
    user_id_str = data.get("user_id")
    
    if not user_id_str:
        logger.warning(f"[QUESTION HANDLER] User ID not found in state data: {data}")
        await message.answer("Ошибка: пользователь не найден. Используйте /start")
        return
    
    user_id = UUID(user_id_str)
    question = message.text
    
    logger.info(f"[QUESTION HANDLER] Processing question for user {user_id}: {question[:100]}")
    
    # Отправка сообщения о том, что идет обработка
    processing_msg = await message.answer("⏳ Обрабатываю ваш вопрос...")
    
    try:
        # Генерация ответа через RAG сервис с ограничением времени (5-7 секунд согласно ТЗ п. 6.3)
        import asyncio
        async with AsyncSessionLocal() as db:
            rag_service = RAGService(db)
            
            # Сохраняем вопрос в историю перед генерацией ответа
            from app.models.message import Message as MessageModel
            from datetime import datetime
            question_message = MessageModel(
                user_id=user_id,
                content=question,
                role="user",
                created_at=datetime.utcnow()
            )
            db.add(question_message)
            await db.flush()  # Получаем ID сообщения
            
            # Создаем задачу с таймаутом
            try:
                answer = await asyncio.wait_for(
                    rag_service.generate_answer(user_id, question),
                    timeout=7.0  # Максимум 7 секунд
                )
            except asyncio.TimeoutError:
                logger.warning(f"[QUESTION HANDLER] Timeout for user {user_id}, using fast answer")
                # Если превышено время, генерируем короткий ответ
                answer = await rag_service.generate_answer_fast(user_id, question)
            
            # Сохраняем ответ в историю
            answer_message = MessageModel(
                user_id=user_id,
                content=answer,
                role="assistant",
                created_at=datetime.utcnow()
            )
            db.add(answer_message)
            await db.commit()
            
            logger.info(f"[QUESTION HANDLER] Answer generated and saved for user {user_id}")
        
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
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"[QUESTION HANDLER] Error processing question for user {user_id}: {e}", exc_info=True)
        
        await processing_msg.delete()
        
        # Улучшенная обработка ошибок согласно ТЗ (п. 5.2.8)
        error_message = str(e).lower()
        error_str = str(e)
        
        if 'timeout' in error_message or 'timed out' in error_message:
            await message.answer(
                "⏱️ Сервис обработки временно недоступен (превышено время ожидания).\n"
                "Попробуйте позже."
            )
        elif 'rate limit' in error_message or '429' in error_message or 'quota' in error_message or 'limit' in error_message:
            await message.answer(
                "🚫 Превышен лимит запросов.\n"
                "Пожалуйста, подождите немного и попробуйте снова."
            )
        elif 'connection' in error_message or 'network' in error_message or 'unreachable' in error_message:
            await message.answer(
                "🌐 Ошибка подключения к сервису.\n"
                "Проверьте подключение к интернету и попробуйте позже."
            )
        elif 'unauthorized' in error_message or '401' in error_message or '403' in error_message:
            await message.answer(
                "🔐 Ошибка авторизации сервиса.\n"
                "Обратитесь к администратору."
            )
        elif 'не сработали' in error_str or 'fallback' in error_message:
            await message.answer(
                "❌ Сервис обработки недоступен.\n"
                "Попробуйте позже или обратитесь к администратору."
            )
        else:
            # Общая ошибка
            await message.answer(
                "❌ Произошла ошибка при обработке вашего вопроса.\n"
                "Попробуйте позже или обратитесь к администратору."
            )


def register_question_handlers(dp: Dispatcher, project_id: str):
    """Регистрация обработчиков вопросов"""
    dp.message.register(handle_question, AuthStates.authorized, F.text)

