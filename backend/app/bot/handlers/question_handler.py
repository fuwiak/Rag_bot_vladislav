"""
Обработчики вопросов пользователей
Поддерживает:
- Обычные вопросы через RAG
- Q&A пары в формате "Q: ... A: ..." для добавления в базу знаний
"""
from aiogram import Dispatcher, F
from aiogram.types import Message, ChatAction
from aiogram.fsm.context import FSMContext
from uuid import UUID

from app.core.database import AsyncSessionLocal
from app.bot.handlers.auth_handler import AuthStates
from app.services.rag_service import RAGService
import asyncio


async def keep_typing_indicator(bot, chat_id: int, duration: float = 60.0):
    """
    Периодически отправляет typing indicator во время длительной обработки
    
    Args:
        bot: Экземпляр бота
        chat_id: ID чата
        duration: Продолжительность в секундах (по умолчанию 60)
    """
    try:
        end_time = asyncio.get_event_loop().time() + duration
        while asyncio.get_event_loop().time() < end_time:
            await bot.send_chat_action(chat_id, ChatAction.TYPING)
            await asyncio.sleep(3)  # Отправляем каждые 3 секунды (typing indicator живет ~5 секунд)
    except asyncio.CancelledError:
        pass
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.warning(f"Error in keep_typing_indicator: {e}")


async def handle_qa_indexing(message: Message, state: FSMContext) -> bool:
    """
    Проверяет и обрабатывает сообщение в формате Q&A
    
    Поддерживаемые форматы:
    - Q: вопрос A: ответ
    - Q: вопрос\nA: ответ
    - В: вопрос О: ответ (русский)
    - Вопрос: ... Ответ: ...
    
    Returns:
        True если сообщение было Q&A и успешно обработано, False иначе
    """
    import logging
    logger = logging.getLogger(__name__)
    
    text = message.text
    if not text:
        return False
    
    try:
        from app.services.rag.qdrant_helper import parse_qa_message, index_qa_to_qdrant_async
        
        # Проверяем, является ли сообщение Q&A парой
        qa_data = parse_qa_message(text)
        
        if not qa_data:
            return False
        
        question = qa_data["question"]
        answer = qa_data["answer"]
        
        logger.info(f"📝 Обнаружена Q&A пара для добавления в RAG: Q='{question[:50]}...', A='{answer[:50]}...'")
        
        # Получаем данные пользователя
        user_id = message.from_user.id
        username = message.from_user.username or "unknown"
        
        # Получаем project_id из состояния
        data = await state.get_data()
        project_id = data.get("project_id")
        
        # Показываем индикатор печати
        await message.bot.send_chat_action(message.chat.id, ChatAction.TYPING)
        
        # Отправляем статус обработки
        status_msg = await message.answer("⏳ Добавляю Q&A пару в базу знаний...")
        
        # Индексируем Q&A пару в Qdrant
        success = await index_qa_to_qdrant_async(
            question=question,
            answer=answer,
            metadata={
                "user_id": str(user_id),
                "username": username,
                "added_via": "telegram_bot",
                "project_id": project_id
            }
        )
        
        # Удаляем статус сообщение
        try:
            await status_msg.delete()
        except:
            pass
        
        if success:
            response = (
                f"✅ Q&A пара добавлена в базу знаний!\n\n"
                f"❓ **Вопрос:** {question}\n\n"
                f"💡 **Ответ:** {answer}"
            )
            await message.answer(response, parse_mode="Markdown")
            logger.info(f"✅ Q&A пара успешно индексирована от пользователя {username}")
        else:
            await message.answer("❌ Ошибка при добавлении Q&A пары в базу знаний. Попробуйте позже.")
            logger.error(f"❌ Не удалось индексировать Q&A пару от пользователя {username}")
        
        return True
        
    except ImportError as e:
        logger.error(f"❌ Ошибка импорта qdrant_helper: {e}")
        return False
    except Exception as e:
        logger.error(f"❌ Ошибка обработки Q&A пары: {e}")
        import traceback
        logger.error(traceback.format_exc())
        await message.answer(f"❌ Ошибка: {str(e)}")
        return True  # Возвращаем True чтобы не обрабатывать как обычный вопрос


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
    
    # Проверяем, является ли сообщение Q&A парой для индексации
    if await handle_qa_indexing(message, state):
        logger.info(f"[QUESTION HANDLER] Message was Q&A pair, skipping RAG processing")
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
    
    # Показываем индикатор печати (как в мессенджерах)
    try:
        await message.bot.send_chat_action(message.chat.id, ChatAction.TYPING)
        logger.debug(f"[QUESTION HANDLER] Typing indicator sent to user {user_id}")
    except Exception as e:
        logger.warning(f"[QUESTION HANDLER] Failed to send typing indicator: {e}")
    
    # Отправка сообщения о том, что идет обработка
    processing_msg = None
    try:
        processing_msg = await message.answer("⏳ Обрабатываю ваш вопрос...")
        logger.info(f"[QUESTION HANDLER] Processing message sent to user {user_id}")
    except Exception as e:
        logger.error(f"[QUESTION HANDLER] Failed to send processing message: {e}")
    
    # Запускаем фоновую задачу для периодической отправки typing indicator
    typing_task = None
    try:
        typing_task = asyncio.create_task(
            keep_typing_indicator(message.bot, message.chat.id, duration=60.0)
        )
    except Exception as e:
        logger.warning(f"[QUESTION HANDLER] Failed to start typing task: {e}")
    
    answer = None
    use_fallback = False
    
    # Проверяем режим ответа
    answer_mode = data.get("answer_mode", "rag_mode")
    logger.info(f"[QUESTION HANDLER] Answer mode for user {user_id}: {answer_mode}")
    
    try:
        # Генерация ответа через RAG сервис с ограничением времени (5-7 секунд согласно ТЗ п. 6.3)
        import asyncio
        async with AsyncSessionLocal() as db:
            rag_service = RAGService(db)
            
            # Сохраняем вопрос в историю перед генерацией ответа
            from app.models.message import Message as MessageModel
            from datetime import datetime
            try:
                question_message = MessageModel(
                    user_id=user_id,
                    content=question,
                    role="user",
                    created_at=datetime.utcnow()
                )
                db.add(question_message)
                await db.flush()  # Получаем ID сообщения
                logger.info(f"[QUESTION HANDLER] Question saved to history for user {user_id}")
            except Exception as e:
                logger.warning(f"[QUESTION HANDLER] Failed to save question to history: {e}")
            
            if answer_mode == "general_mode":
                # Режим общих вопросов - используем RAGChain с use_rag=False для правильного выбора модели
                logger.info(f"[QUESTION HANDLER] General mode: using RAGChain with use_rag=False for user {user_id}")
                try:
                    # Получаем проект для использования его настроек
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
                    
                    # Определяем модель LLM (та же логика, что и в rag_service.py)
                    # Приоритет: 1) модель проекта, 2) глобальные настройки из БД, 3) дефолты из .env
                    from app.models.llm_model import GlobalModelSettings
                    settings_result = await db.execute(select(GlobalModelSettings).limit(1))
                    global_settings = settings_result.scalar_one_or_none()
                    
                    logger.info(f"[QUESTION HANDLER] GENERAL MODE: Global settings from DB: primary={global_settings.primary_model_id if global_settings else 'None'}, fallback={global_settings.fallback_model_id if global_settings else 'None'}")
                    
                    primary_model = None
                    fallback_model = None
                    
                    if project.llm_model:
                        # Приоритет 1: модель проекта
                        primary_model = project.llm_model
                        logger.info(f"[QUESTION HANDLER] GENERAL MODE: Using project model: {primary_model}")
                        # Fallback из глобальных настроек БД
                        if global_settings and global_settings.fallback_model_id:
                            fallback_model = global_settings.fallback_model_id
                            logger.info(f"[QUESTION HANDLER] GENERAL MODE: Using global fallback from DB: {fallback_model}")
                        else:
                            from app.core.config import settings as app_settings
                            fallback_model = app_settings.OPENROUTER_MODEL_FALLBACK
                            logger.info(f"[QUESTION HANDLER] GENERAL MODE: Using default fallback from .env: {fallback_model}")
                    elif global_settings:
                        # Приоритет 2: глобальные настройки из БД
                        primary_model = global_settings.primary_model_id
                        fallback_model = global_settings.fallback_model_id
                        logger.info(f"[QUESTION HANDLER] GENERAL MODE: Using global models from DB: primary={primary_model}, fallback={fallback_model}")
                    
                    # Приоритет 3: дефолты из .env
                    from app.core.config import settings as app_settings
                    if not primary_model:
                        primary_model = app_settings.OPENROUTER_MODEL_PRIMARY
                        logger.info(f"[QUESTION HANDLER] GENERAL MODE: Using default primary from .env: {primary_model}")
                    if not fallback_model:
                        fallback_model = app_settings.OPENROUTER_MODEL_FALLBACK
                        logger.info(f"[QUESTION HANDLER] GENERAL MODE: Using default fallback from .env: {fallback_model}")
                    
                    logger.info(f"[QUESTION HANDLER] GENERAL MODE: Final models - primary={primary_model}, fallback={fallback_model}")
                    
                    # Используем LLMClient напрямую БЕЗ RAG (как в веб-интерфейсе для тестирования моделей)
                    from app.rag.llm_client import LLMClient
                    
                    # Создаем LLMClient с выбранными моделями
                    llm_client = LLMClient(
                        primary_model=primary_model,
                        fallback_chain=[{"model": fallback_model}] if fallback_model else None
                    )
                    
                    # Получаем историю диалога
                    conversation_history = await rag_service._get_conversation_history(user_id, limit=10)
                    
                    # Формируем системный промпт для общих вопросов (БЕЗ упоминания документов)
                    system_prompt = "Ты дружелюбный помощник. Отвечай на вопросы пользователя естественно и полезно."
                    if project.prompt_template and project.prompt_template.strip():
                        # Используем промпт проекта, но полностью убираем упоминания о документах
                        system_prompt = project.prompt_template
                        # Убираем все упоминания о документах из промпта
                        system_prompt = system_prompt.replace("на основе документов", "")
                        system_prompt = system_prompt.replace("из документов", "")
                        system_prompt = system_prompt.replace("в документах", "")
                        system_prompt = system_prompt.replace("загруженных документов", "")
                        system_prompt = system_prompt.replace("документах", "")
                        system_prompt = system_prompt.replace("документов", "")
                        system_prompt = system_prompt.replace("документ", "")
                        system_prompt = system_prompt.strip()
                    
                    # Формируем сообщения для LLM (как в веб-интерфейсе для тестирования моделей)
                    messages = []
                    messages.append({"role": "system", "content": system_prompt})
                    
                    # Добавляем историю диалога (последние 5 сообщений)
                    for hist_msg in conversation_history[-5:]:
                        messages.append(hist_msg)
                    
                    # Добавляем текущий вопрос
                    messages.append({"role": "user", "content": question})
                    
                    # Используем LLM напрямую через _call_api (как в веб-интерфейсе для тестирования)
                    logger.info(f"[QUESTION HANDLER] GENERAL MODE: Sending request directly to LLM (no RAG, no documents)")
                    llm_response = await llm_client._call_api(
                        model=primary_model,
                        messages=messages,
                        temperature=0.7,
                        max_tokens=min(project.max_response_length, 2048)
                    )
                    
                    # Если основная модель не сработала, пробуем fallback
                    if llm_response.error and fallback_model:
                        logger.warning(f"[QUESTION HANDLER] GENERAL MODE: Primary model failed, trying fallback: {fallback_model}")
                        llm_response = await llm_client._call_api(
                            model=fallback_model,
                            messages=messages,
                            temperature=0.7,
                            max_tokens=min(project.max_response_length, 2048)
                        )
                    
                    if llm_response.error:
                        logger.error(f"[QUESTION HANDLER] GENERAL MODE: LLM error: {llm_response.error}")
                        answer = "Извините, произошла ошибка при генерации ответа. Попробуйте позже."
                    else:
                        answer = llm_response.content.strip()
                    
                    if not answer:
                        answer = "Извините, не удалось сгенерировать ответ. Попробуйте переформулировать вопрос."
                    
                    logger.info(f"[QUESTION HANDLER] GENERAL MODE: Response received directly from LLM, length: {len(answer)}, model: {llm_response.model}")
                    
                except Exception as general_error:
                    logger.error(f"[QUESTION HANDLER] GENERAL MODE: Error for user {user_id}: {general_error}", exc_info=True)
                    answer = "Извините, произошла ошибка при обработке вашего вопроса. Попробуйте позже."
            else:
                # Режим RAG - сначала пробуем простой режим (jak prosty kod)
                # Если не работает, пробуем полный RAG
                try:
                    logger.info(f"[QUESTION HANDLER] Trying simple RAG mode first for user {user_id}")
                    answer = await asyncio.wait_for(
                        rag_service.generate_answer_simple(user_id, question, top_k=5, use_local_embeddings=True),
                        timeout=15.0
                    )
                    logger.info(f"[QUESTION HANDLER] Simple RAG answer generated successfully for user {user_id}")
                except asyncio.TimeoutError:
                    logger.warning(f"[QUESTION HANDLER] Simple RAG timeout for user {user_id}, trying full RAG")
                    try:
                        answer = await asyncio.wait_for(
                            rag_service.generate_answer(user_id, question),
                            timeout=10.0
                        )
                        logger.info(f"[QUESTION HANDLER] Full RAG answer generated successfully for user {user_id}")
                    except asyncio.TimeoutError:
                        logger.warning(f"[QUESTION HANDLER] Full RAG timeout for user {user_id}, trying fast answer")
                        try:
                            answer = await rag_service.generate_answer_fast(user_id, question)
                            logger.info(f"[QUESTION HANDLER] Fast RAG answer generated for user {user_id}")
                        except Exception as fast_error:
                            logger.warning(f"[QUESTION HANDLER] Fast RAG also failed for user {user_id}: {fast_error}, using LLM fallback")
                            use_fallback = True
                    except Exception as rag_error:
                        logger.error(f"[QUESTION HANDLER] Full RAG error for user {user_id}: {rag_error}, trying fast", exc_info=True)
                        try:
                            answer = await rag_service.generate_answer_fast(user_id, question)
                            logger.info(f"[QUESTION HANDLER] Fast RAG answer generated after full RAG error for user {user_id}")
                        except Exception as fast_error2:
                            logger.error(f"[QUESTION HANDLER] Fast RAG also failed: {fast_error2}, using LLM fallback")
                            use_fallback = True
                except Exception as simple_error:
                    logger.warning(f"[QUESTION HANDLER] Simple RAG failed for user {user_id}: {simple_error}, trying full RAG")
                    try:
                        answer = await asyncio.wait_for(
                            rag_service.generate_answer(user_id, question),
                            timeout=10.0
                        )
                        logger.info(f"[QUESTION HANDLER] Full RAG answer generated after simple RAG error for user {user_id}")
                    except Exception as rag_error:
                        logger.error(f"[QUESTION HANDLER] Full RAG also failed for user {user_id}: {rag_error}, using LLM fallback", exc_info=True)
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
            
            # Проверяем, что ответ не пустой
            if not answer or not answer.strip():
                logger.error(f"[QUESTION HANDLER] ❌ Empty answer generated for user {user_id}")
                answer = "Извините, не удалось сгенерировать ответ. Попробуйте переформулировать вопрос."
            
            # Сохраняем ответ в историю
            try:
                answer_message = MessageModel(
                    user_id=user_id,
                    content=answer,
                    role="assistant",
                    created_at=datetime.utcnow()
                )
                db.add(answer_message)
                await db.commit()
                logger.info(f"[QUESTION HANDLER] Answer saved to history for user {user_id}, length: {len(answer)}")
            except Exception as e:
                logger.warning(f"[QUESTION HANDLER] Failed to save answer to history: {e}")
            
            if use_fallback:
                logger.warning(f"[QUESTION HANDLER] ⚠️ FALLBACK MODE: Answer saved for user {user_id} (used direct LLM without RAG)")
            else:
                logger.info(f"[QUESTION HANDLER] ✅ Answer generated and saved for user {user_id}")
        
        # Останавливаем фоновую задачу typing indicator
        if typing_task and not typing_task.done():
            try:
                typing_task.cancel()
                try:
                    await typing_task
                except asyncio.CancelledError:
                    pass
                logger.debug(f"[QUESTION HANDLER] Typing task cancelled")
            except Exception as e:
                logger.warning(f"[QUESTION HANDLER] Failed to cancel typing task: {e}")
        
        # Удаление сообщения об обработке
        if processing_msg:
            try:
                await processing_msg.delete()
                logger.debug(f"[QUESTION HANDLER] Processing message deleted")
            except Exception as e:
                logger.warning(f"[QUESTION HANDLER] Failed to delete processing message: {e}")
        
        # Отправка ответа (разбиваем на части если длинный)
        if not answer:
            logger.error(f"[QUESTION HANDLER] ❌ Answer is None, cannot send to user {user_id}")
            answer = "Извините, произошла ошибка при обработке вашего вопроса. Попробуйте позже."
        
        # Показываем typing indicator перед отправкой ответа
        try:
            await message.bot.send_chat_action(message.chat.id, ChatAction.TYPING)
        except Exception as e:
            logger.warning(f"[QUESTION HANDLER] Failed to send typing before answer: {e}")
        
        max_length = 4096  # Максимальная длина сообщения Telegram
        logger.info(f"[QUESTION HANDLER] Sending answer to user {user_id}, length: {len(answer)}")
        try:
            if len(answer) > max_length:
                # Разбиваем на части
                parts = [answer[i:i+max_length] for i in range(0, len(answer), max_length)]
                logger.info(f"[QUESTION HANDLER] Splitting answer into {len(parts)} parts")
                for i, part in enumerate(parts):
                    # Показываем typing перед каждой частью
                    try:
                        await message.bot.send_chat_action(message.chat.id, ChatAction.TYPING)
                    except:
                        pass
                    await message.answer(part)
                    logger.debug(f"[QUESTION HANDLER] Sent part {i+1}/{len(parts)}")
            else:
                await message.answer(answer)
                logger.info(f"[QUESTION HANDLER] ✅ Answer sent successfully to user {user_id}")
        except Exception as e:
            logger.error(f"[QUESTION HANDLER] ❌ Failed to send answer to user {user_id}: {e}", exc_info=True)
            await message.answer("❌ Произошла ошибка при отправке ответа. Попробуйте позже.")
    
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"[QUESTION HANDLER] ❌ Critical error processing question for user {user_id}: {e}", exc_info=True)
        
        # Останавливаем typing task при ошибке
        if 'typing_task' in locals() and typing_task and not typing_task.done():
            try:
                typing_task.cancel()
                try:
                    await typing_task
                except asyncio.CancelledError:
                    pass
            except:
                pass
        
        if processing_msg:
            try:
                await processing_msg.delete()
            except:
                pass
        
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
    # Проверка на команды выполняется внутри обработчика (message.text.startswith('/'))
    # Это более надежно, чем фильтр ~Command(), который может работать неправильно
    dp.message.register(handle_question, AuthStates.authorized, F.text)
    logger.info(f"[REGISTER HANDLERS] Question handler registered for project {project_id}")

