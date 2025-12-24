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
    from aiogram.filters import Command
    logger = logging.getLogger(__name__)
    
    logger.info(f"[QUESTION HANDLER] ===== HANDLER CALLED =====")
    logger.info(f"[QUESTION HANDLER] Message text: {message.text[:100] if message.text else 'None'}")
    logger.info(f"[QUESTION HANDLER] Message from user: {message.from_user.id}, username: {message.from_user.username}")
    
    # Проверка авторизации
    current_state = await state.get_state()
    logger.info(f"[QUESTION HANDLER] Current state: {current_state}, AuthStates.authorized: {AuthStates.authorized}")
    
    if current_state != AuthStates.authorized:
        logger.warning(f"[QUESTION HANDLER] User not authorized! State: {current_state}, expected: {AuthStates.authorized}")
        await message.answer("Пожалуйста, сначала авторизуйтесь через /start")
        return
    
    # Проверяем, что это не команда (команды должны обрабатываться отдельными обработчиками)
    if message.text and message.text.startswith('/'):
        # Это команда, пропускаем обработку
        logger.info(f"[QUESTION HANDLER] Skipping command: {message.text}")
        return
    
    # Получение user_id из состояния
    data = await state.get_data()
    logger.info(f"[QUESTION HANDLER] State data: {data}")
    user_id_str = data.get("user_id")
    
    if not user_id_str:
        logger.error(f"[QUESTION HANDLER] ❌ User ID not found in state data: {data}")
        await message.answer("Ошибка: пользователь не найден. Используйте /start")
        return
    
    try:
        user_id = UUID(user_id_str)
    except ValueError as e:
        logger.error(f"[QUESTION HANDLER] ❌ Invalid user_id format: {user_id_str}, error: {e}")
        await message.answer("Ошибка: неверный формат ID пользователя. Используйте /start")
        return
    
    question = message.text
    
    if not question or not question.strip():
        logger.warning(f"[QUESTION HANDLER] Empty question from user {user_id}")
        return
    
    logger.info(f"[QUESTION HANDLER] ✅ Processing question for user {user_id}: {question[:100]}")
    
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
            
            answer = None
            use_fallback = False
            
            # Создаем задачу с таймаутом
            try:
                answer = await asyncio.wait_for(
                    rag_service.generate_answer(user_id, question),
                    timeout=7.0  # Максимум 7 секунд
                )
                logger.info(f"[QUESTION HANDLER] RAG answer generated successfully for user {user_id}")
            except asyncio.TimeoutError:
                logger.warning(f"[QUESTION HANDLER] Timeout for user {user_id}, trying fast answer")
                try:
                    answer = await rag_service.generate_answer_fast(user_id, question)
                    logger.info(f"[QUESTION HANDLER] Fast RAG answer generated for user {user_id}")
                except Exception as fast_error:
                    logger.warning(f"[QUESTION HANDLER] Fast RAG also failed for user {user_id}: {fast_error}, using LLM fallback")
                    use_fallback = True
            except Exception as rag_error:
                logger.error(f"[QUESTION HANDLER] RAG error for user {user_id}: {rag_error}, using LLM fallback", exc_info=True)
                use_fallback = True
            
            # Fallback: используем прямой LLM, но ВСЕГДА с настройками проекта и промптом
            if use_fallback or not answer:
                logger.warning(f"[QUESTION HANDLER] ⚠️ FALLBACK MODE: RAG failed, using LLM with project settings for user {user_id}, question: {question[:100]}")
                
                try:
                    # Получаем проект для использования его настроек и промпта
                    from app.models.user import User
                    from app.models.project import Project
                    from sqlalchemy import select
                    
                    user_result = await db.execute(select(User).where(User.id == user_id))
                    user = user_result.scalar_one_or_none()
                    
                    if not user:
                        raise ValueError("User not found")
                    
                    project_result = await db.execute(select(Project).where(Project.id == user.project_id))
                    project = project_result.scalar_one_or_none()
                    
                    if not project:
                        raise ValueError("Project not found")
                    
                    # Определяем модель LLM (приоритет: модель проекта > глобальная настройка из БД > дефолт из .env)
                    from app.models.llm_model import GlobalModelSettings
                    settings_result = await db.execute(select(GlobalModelSettings).limit(1))
                    global_settings = settings_result.scalar_one_or_none()
                    
                    logger.info(f"[QUESTION HANDLER] FALLBACK: Global settings from DB: primary={global_settings.primary_model_id if global_settings else 'None'}, fallback={global_settings.fallback_model_id if global_settings else 'None'}")
                    
                    primary_model = None
                    fallback_model = None
                    
                    if project.llm_model:
                        # Приоритет 1: модель проекта
                        primary_model = project.llm_model
                        logger.info(f"[QUESTION HANDLER] FALLBACK: Using project model: {primary_model}")
                        # Fallback из глобальных настроек БД
                        if global_settings and global_settings.fallback_model_id:
                            fallback_model = global_settings.fallback_model_id
                            logger.info(f"[QUESTION HANDLER] FALLBACK: Using global fallback from DB: {fallback_model}")
                        else:
                            from app.core.config import settings as app_settings
                            fallback_model = app_settings.OPENROUTER_MODEL_FALLBACK
                            logger.info(f"[QUESTION HANDLER] FALLBACK: Using default fallback from .env: {fallback_model}")
                    elif global_settings:
                        # Приоритет 2: глобальные настройки из БД
                        primary_model = global_settings.primary_model_id
                        fallback_model = global_settings.fallback_model_id
                        logger.info(f"[QUESTION HANDLER] FALLBACK: Using global models from DB: primary={primary_model}, fallback={fallback_model}")
                    
                    # Приоритет 3: дефолты из .env
                    from app.core.config import settings as app_settings
                    if not primary_model:
                        primary_model = app_settings.OPENROUTER_MODEL_PRIMARY
                        logger.info(f"[QUESTION HANDLER] FALLBACK: Using default primary from .env: {primary_model}")
                    if not fallback_model:
                        fallback_model = app_settings.OPENROUTER_MODEL_FALLBACK
                        logger.info(f"[QUESTION HANDLER] FALLBACK: Using default fallback from .env: {fallback_model}")
                    
                    logger.info(f"[QUESTION HANDLER] FALLBACK: Final models - primary={primary_model}, fallback={fallback_model}")
                    
                    # Получаем историю диалога
                    conversation_history = await rag_service._get_conversation_history(user_id, limit=10)
                    
                    # ВАЖНО: Используем промпт проекта даже в fallback режиме
                    # Создаем промпт с пустым контекстом (документы недоступны), но с настройками проекта
                    from app.llm.prompt_builder import PromptBuilder
                    prompt_builder = PromptBuilder()
                    
                    # Используем промпт проекта с пустым контекстом
                    messages = prompt_builder.build_prompt(
                        question=question,
                        chunks=[],  # Пустой список - документы недоступны
                        prompt_template=project.prompt_template,
                        max_length=project.max_response_length,
                        conversation_history=conversation_history
                    )
                    
                    logger.info(f"[QUESTION HANDLER] FALLBACK: Using project prompt template, max_length={project.max_response_length}, messages={len(messages)}")
                    
                    # Используем LLM с настройками проекта
                    from app.llm.openrouter_client import OpenRouterClient
                    llm_client = OpenRouterClient(
                        model_primary=primary_model,
                        model_fallback=fallback_model
                    )
                    
                    logger.info(f"[QUESTION HANDLER] FALLBACK: Sending request to LLM with project settings")
                    raw_answer = await llm_client.chat_completion(
                        messages=messages,
                        max_tokens=min(project.max_response_length // 4, 1000),  # Примерно 1 токен = 4 символа
                        temperature=0.7
                    )
                    
                    # Форматируем ответ с учетом max_response_length проекта
                    from app.llm.response_formatter import ResponseFormatter
                    formatter = ResponseFormatter()
                    answer = formatter.format_response(
                        response=raw_answer.strip(),
                        max_length=project.max_response_length,
                        chunks=None  # Нет чанков в fallback режиме
                    )
                    
                    if not answer:
                        answer = "Извините, не удалось сгенерировать ответ. Попробуйте переформулировать вопрос."
                    
                    logger.info(f"[QUESTION HANDLER] FALLBACK: LLM response received, length: {len(answer)}, max_length: {project.max_response_length}")
                    
                except Exception as fallback_error:
                    logger.error(f"[QUESTION HANDLER] FALLBACK also failed for user {user_id}: {fallback_error}", exc_info=True)
                    answer = "Извините, произошла ошибка при обработке вашего вопроса. Попробуйте позже или обратитесь к администратору."
            
            # Сохраняем ответ в историю
            answer_message = MessageModel(
                user_id=user_id,
                content=answer,
                role="assistant",
                created_at=datetime.utcnow()
            )
            db.add(answer_message)
            await db.commit()
            
            if use_fallback:
                logger.warning(f"[QUESTION HANDLER] ⚠️ FALLBACK MODE: Answer saved for user {user_id} (used direct LLM without RAG)")
            else:
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
    """Регистрация обработчиков вопросов
    
    Важно: этот обработчик должен регистрироваться ПОСЛЕ команд,
    чтобы команды не перехватывали текстовые сообщения.
    Фильтр AuthStates.authorized гарантирует, что обработчик
    сработает только для авторизованных пользователей.
    """
    import logging
    logger = logging.getLogger(__name__)
    
    # Регистрируем обработчик для текстовых сообщений авторизованных пользователей
    # F.text фильтрует только текстовые сообщения
    # Проверяем, что это не команда внутри обработчика, так как ~F.command может не работать правильно
    dp.message.register(handle_question, AuthStates.authorized, F.text)
    logger.info(f"[REGISTER HANDLERS] Question handler registered for project {project_id}")

