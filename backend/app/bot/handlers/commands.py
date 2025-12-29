"""
Обработчики команд бота (/start, /help, /documents)
"""
from aiogram import Dispatcher, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext

from app.core.database import AsyncSessionLocal
from app.models.project import Project
from app.bot.handlers.auth_handler import AuthStates
from sqlalchemy import select


async def cmd_start(message: Message, state: FSMContext, project_id: str = None):
    """Обработка команды /start"""
    import logging
    logger = logging.getLogger(__name__)
    
    # Проверяем, авторизован ли пользователь
    current_state = await state.get_state()
    
    # Проверяем, есть ли пользователь в БД по telegram_id
    async with AsyncSessionLocal() as db:
        from app.models.user import User
        from sqlalchemy import select
        
        telegram_user_id = str(message.from_user.id)
        telegram_username = message.from_user.username
        
        # Ищем пользователя по telegram_id или username
        user_result = await db.execute(
            select(User).where(
                (User.telegram_id == telegram_user_id) | 
                (User.username == telegram_username)
            )
        )
        existing_user = user_result.scalar_one_or_none()
        
        if existing_user and existing_user.status != "blocked":
            # Пользователь уже существует в БД - автоматически авторизуем
            logger.info(f"[START] User {telegram_user_id} already exists, auto-authorizing")
            
            # Получаем проект
            project_result = await db.execute(
                select(Project).where(Project.id == existing_user.project_id)
            )
            project = project_result.scalar_one_or_none()
            
            if project:
                # Сохраняем данные в состоянии
                await state.update_data(
                    project_id=str(project.id),
                    user_id=str(existing_user.id),
                    answer_mode="rag_mode"  # По умолчанию режим RAG
                )
                await state.set_state(AuthStates.authorized)
                
                welcome_text = f"👋 <b>Добро пожаловать обратно в проект «{project.name}»!</b>\n\n"
                welcome_text += "Вы уже авторизованы. Можете:\n"
                welcome_text += "• Задавать вопросы о документах (/documents - показать список документов)\n"
                welcome_text += "• Получать ответы на основе загруженных документов\n"
                welcome_text += "• Использовать /help для справки\n\n"
                
                # Показываем текущий режим
                data = await state.get_data()
                answer_mode = data.get("answer_mode", "rag_mode")
                if answer_mode == "rag_mode":
                    welcome_text += "📄 <b>Режим:</b> Ответы на основе документов\n"
                else:
                    welcome_text += "💬 <b>Режим:</b> Общие вопросы\n"
                
                welcome_text += "\n❓ <b>Задайте ваш вопрос:</b>"
                await message.answer(welcome_text)
                
                # Отправляем клавиатуру с режимами
                mode_keyboard = InlineKeyboardMarkup(inline_keyboard=[
                    [
                        InlineKeyboardButton(
                            text="📄 Режим: Документы" if answer_mode == "rag_mode" else "📄 Переключить на Документы",
                            callback_data="set_mode_rag"
                        )
                    ],
                    [
                        InlineKeyboardButton(
                            text="💬 Режим: Общие вопросы" if answer_mode == "general_mode" else "💬 Переключить на Общие вопросы",
                            callback_data="set_mode_general"
                        )
                    ],
                    [
                        InlineKeyboardButton(
                            text="💡 Предложить вопросы",
                            callback_data="suggest_questions"
                        )
                    ]
                ])
                await message.answer("🔧 <b>Управление режимом ответа:</b>", reply_markup=mode_keyboard)
                return
        
        # Если пользователь уже авторизован в текущей сессии
        if current_state == AuthStates.authorized:
            data = await state.get_data()
            project_id_from_state = data.get("project_id")
            
            if project_id_from_state:
                result = await db.execute(
                    select(Project).where(Project.id == project_id_from_state)
                )
                project = result.scalar_one_or_none()
                
                if project:
                    welcome_text = f"👋 <b>Вы уже авторизованы в проекте «{project.name}»!</b>\n\n"
                    welcome_text += "Вы можете:\n"
                    welcome_text += "• Задавать вопросы о документах (/documents - показать список документов)\n"
                    welcome_text += "• Получать ответы на основе загруженных документов\n"
                    welcome_text += "• Использовать /help для справки\n\n"
                    
                    answer_mode = data.get("answer_mode", "rag_mode")
                    if answer_mode == "rag_mode":
                        welcome_text += "📄 <b>Режим:</b> Ответы на основе документов\n"
                    else:
                        welcome_text += "💬 <b>Режим:</b> Общие вопросы\n"
                    
                    welcome_text += "\n❓ <b>Задайте ваш вопрос:</b>"
                    await message.answer(welcome_text)
                    
                    # Отправляем клавиатуру с режимами
                    mode_keyboard = InlineKeyboardMarkup(inline_keyboard=[
                        [
                            InlineKeyboardButton(
                                text="📄 Режим: Документы" if answer_mode == "rag_mode" else "📄 Переключить на Документы",
                                callback_data="set_mode_rag"
                            )
                        ],
                        [
                            InlineKeyboardButton(
                                text="💬 Режим: Общие вопросы" if answer_mode == "general_mode" else "💬 Переключить на Общие вопросы",
                                callback_data="set_mode_general"
                            )
                        ],
                        [
                            InlineKeyboardButton(
                                text="💡 Предложить вопросы",
                                callback_data="suggest_questions"
                            )
                        ]
                    ])
                    await message.answer("🔧 <b>Управление режимом ответа:</b>", reply_markup=mode_keyboard)
                    return
        
        # Если не нашли пользователя или проект, продолжаем с обычной авторизацией
        if current_state == AuthStates.authorized:
            await state.clear()
    
    # Получаем bot_token из бота
    bot_token = None
    if message.bot and hasattr(message.bot, 'token'):
        bot_token = message.bot.token
    
    async with AsyncSessionLocal() as db:
        project = None
        
        # Если project_id задан, используем его
        if project_id:
            result = await db.execute(
                select(Project).where(Project.id == project_id)
            )
            project = result.scalar_one_or_none()
        
        # Если не нашли или project_id не задан, ищем все проекты с этим bot_token
        if not project and bot_token:
            result = await db.execute(
                select(Project).where(Project.bot_token == bot_token)
            )
            projects = result.scalars().all()
            
            if len(projects) == 1:
                # Только один проект с этим токеном
                project = projects[0]
            elif len(projects) > 1:
                # Несколько проектов с одним токеном - показываем список или просто запрашиваем пароль
                welcome_text = "👋 <b>Добро пожаловать!</b>\n\n"
                welcome_text += "🤖 <b>О боте:</b>\n"
                welcome_text += "Этот бот помогает вам получать ответы на вопросы на основе документов вашего проекта.\n"
                welcome_text += "Просто задайте вопрос в свободной форме, и бот найдет релевантную информацию в загруженных документах.\n\n"
                welcome_text += "📋 <b>Как пользоваться:</b>\n"
                welcome_text += "1️⃣ Авторизуйтесь (введите пароль доступа вашего проекта)\n"
                welcome_text += "2️⃣ Задавайте вопросы о документах проекта\n"
                welcome_text += "3️⃣ Получайте точные ответы на основе документов\n\n"
                welcome_text += "💡 <b>Важно:</b>\n"
                welcome_text += "• Бот отвечает только на основе загруженных документов\n"
                welcome_text += "• Если информации нет в документах, бот честно об этом сообщит\n"
                welcome_text += "• Используйте /help для получения справки\n\n"
                welcome_text += "🔐 <b>Для начала работы введите пароль доступа вашего проекта:</b>"
                await message.answer(welcome_text)
                # Устанавливаем состояние ожидания пароля
                await state.set_state(AuthStates.waiting_password)
                return
        
        if not project:
            await message.answer("Ошибка: проект не найден")
            return
        
        # Сохраняем project_id в состоянии
        await state.update_data(project_id=str(project.id))
        
        # Формируем приветственное сообщение с описанием бота
        welcome_text = f"👋 <b>Добро пожаловать в бот проекта «{project.name}»!</b>\n\n"
        
        # Добавляем описание проекта, если есть
        if project.description:
            welcome_text += f"📄 <b>О проекте:</b>\n{project.description}\n\n"
        
        welcome_text += "🤖 <b>О боте:</b>\n"
        welcome_text += "Этот бот помогает вам получать ответы на вопросы на основе документов проекта.\n"
        welcome_text += "Просто задайте вопрос в свободной форме, и бот найдет релевантную информацию в загруженных документах.\n\n"
        
        welcome_text += "📋 <b>Как пользоваться:</b>\n"
        welcome_text += "1️⃣ Авторизуйтесь (введите пароль доступа)\n"
        welcome_text += "2️⃣ Задавайте вопросы о документах проекта\n"
        welcome_text += "3️⃣ Получайте точные ответы на основе документов\n\n"
        
        welcome_text += "💡 <b>Важно:</b>\n"
        welcome_text += "• Бот отвечает только на основе загруженных документов\n"
        welcome_text += "• Если информации нет в документах, бот честно об этом сообщит\n"
        welcome_text += "• Используйте /help для получения справки\n\n"
        
        welcome_text += "🔐 <b>Для начала работы введите пароль доступа:</b>"
        
        await message.answer(welcome_text)
        # Устанавливаем состояние ожидания пароля
        await state.set_state(AuthStates.waiting_password)


async def cmd_help(message: Message, state: FSMContext):
    """Обработка команды /help"""
    current_state = await state.get_state()
    is_authorized = current_state == AuthStates.authorized
    
    help_text = "<b>Справка по использованию бота</b>\n\n"
    
    help_text += "📋 <b>Основные команды:</b>\n"
    help_text += "/start - Начать работу с ботом или продолжить сессию\n"
    help_text += "/help - Показать эту справку\n"
    
    if is_authorized:
        help_text += "\n📄 <b>Команды для работы с документами:</b>\n"
        help_text += "/documents - Показать список документов проекта\n"
        help_text += "/документы - Показать список документов (альтернатива)\n"
        help_text += "/показать_документы - Показать список документов (альтернатива)\n"
        help_text += "/files - Показать список документов (английский вариант)\n"
        help_text += "/файлы - Показать список документов (русский вариант)\n"
        help_text += "/suggest_questions - Предложить вопросы на основе документов\n"
        help_text += "/вопросы - Предложить вопросы (альтернатива)\n"
    
    help_text += "\n❓ <b>Как задать вопрос:</b>\n"
    help_text += "Просто напишите ваш вопрос в свободной форме, и бот найдет ответ в документах проекта.\n"
    help_text += "Бот помнит контекст последних 10 сообщений для более точных ответов.\n\n"
    
    if not is_authorized:
        help_text += "\n🔐 <b>Авторизация:</b>\n"
        help_text += "Для начала работы введите пароль доступа вашего проекта после команды /start.\n"
        help_text += "После успешной авторизации вам не потребуется вводить пароль повторно.\n"
    
    help_text += "\n💡 <b>Советы:</b>\n"
    help_text += "• Задавайте конкретные вопросы\n"
    help_text += "• Используйте ключевые слова из документов\n"
    help_text += "• Бот отвечает только на основе загруженных документов\n"
    help_text += "• Если информации нет в документах, бот честно об этом сообщит\n"
    if is_authorized:
        help_text += "• Используйте /documents для просмотра доступных документов\n"
        help_text += "• Используйте /suggest_questions для получения предложенных вопросов\n"
        help_text += "• Переключайте режим ответа через кнопки (Документы / Общие вопросы)\n"
    
    help_text += "\nЕсли у вас возникли вопросы, обратитесь к администратору проекта."
    
    await message.answer(help_text)


async def cmd_documents(message: Message, state: FSMContext):
    """Обработка команды /documents или /показать_документы - показать список документов проекта"""
    # Проверка авторизации
    current_state = await state.get_state()
    if current_state != AuthStates.authorized:
        await message.answer("❌ Сначала авторизуйтесь через /start")
        return
    
    # Получаем project_id из состояния
    data = await state.get_data()
    project_id_str = data.get("project_id")
    
    if not project_id_str:
        await message.answer("❌ Ошибка: проект не найден. Используйте /start")
        return
    
    from uuid import UUID
    from app.models.document import Document
    
    try:
        project_id = UUID(project_id_str)
    except ValueError:
        await message.answer("❌ Ошибка: неверный ID проекта")
        return
    
    async with AsyncSessionLocal() as db:
        # Получаем список документов проекта
        # Используем load_only для загрузки только нужных полей, исключая summary
        # чтобы избежать ошибки если summary колонка не существует в БД
        from sqlalchemy.orm import load_only
        import logging
        logger = logging.getLogger(__name__)
        
        try:
            result = await db.execute(
                select(Document)
                .options(load_only(Document.id, Document.project_id, Document.filename, Document.content, Document.file_type, Document.created_at))
                .where(Document.project_id == project_id)
                .order_by(Document.created_at.desc())
                .limit(50)
            )
            documents = result.scalars().all()
        except Exception as e:
            # Если ошибка из-за summary в модели, используем raw SQL
            logger.warning(f"Error loading documents: {e}, using raw SQL query")
            from sqlalchemy import text
            result = await db.execute(
                text("""
                    SELECT id, project_id, filename, content, file_type, created_at 
                    FROM documents 
                    WHERE project_id = :project_id 
                    ORDER BY created_at DESC 
                    LIMIT 50
                """),
                {"project_id": project_id}
            )
            rows = result.all()
            documents = []
            for row in rows:
                doc = Document()
                doc.id = row[0]
                doc.project_id = row[1]
                doc.filename = row[2]
                doc.content = row[3]
                doc.file_type = row[4]
                doc.created_at = row[5]
                documents.append(doc)
        
        if not documents:
            await message.answer("📄 <b>Документы проекта</b>\n\n"
                               "В проекте пока нет загруженных документов.\n"
                               "Обратитесь к администратору для загрузки документов.")
            return
        
        # Формируем список документов
        docs_text = f"📄 <b>Документы проекта ({len(documents)}):</b>\n\n"
        
        for i, doc in enumerate(documents, 1):
            # Определяем тип файла
            file_type_emoji = "📄"
            if doc.file_type == "pdf":
                file_type_emoji = "📕"
            elif doc.file_type == "docx":
                file_type_emoji = "📘"
            elif doc.file_type == "txt":
                file_type_emoji = "📝"
            
            docs_text += f"{i}. {file_type_emoji} <b>{doc.filename}</b>\n"
            if doc.content and doc.content != "Обработка..." and doc.content != "Обработан":
                # Показываем первые 50 символов содержимого
                preview = doc.content[:50].replace('\n', ' ')
                if len(doc.content) > 50:
                    preview += "..."
                docs_text += f"   <i>{preview}</i>\n"
            docs_text += "\n"
        
        docs_text += "\n💡 <b>Совет:</b> Задавайте вопросы о содержании этих документов!"
        
        # Разбиваем на части, если слишком длинное
        max_length = 4096
        if len(docs_text) > max_length:
            parts = [docs_text[i:i+max_length] for i in range(0, len(docs_text), max_length)]
            for part in parts:
                await message.answer(part)
        else:
            await message.answer(docs_text)


async def cmd_suggest_questions(message: Message, state: FSMContext):
    """Обработка команды /suggest_questions - предложить вопросы на основе документов"""
    import logging
    logger = logging.getLogger(__name__)
    
    current_state = await state.get_state()
    if current_state != AuthStates.authorized:
        await message.answer("Пожалуйста, сначала авторизуйтесь через /start")
        return
    
    data = await state.get_data()
    project_id_from_state = data.get("project_id")
    
    if not project_id_from_state:
        await message.answer("Ошибка: проект не определен. Используйте /start.")
        return
    
    from uuid import UUID
    from app.core.database import AsyncSessionLocal
    from app.services.rag_service import RAGService
    
    processing_msg = await message.answer("⏳ Анализирую документы и генерирую вопросы...")
    
    try:
        async with AsyncSessionLocal() as db:
            rag_service = RAGService(db)
            questions = await rag_service.suggestions.generate_suggested_questions(UUID(project_id_from_state), limit=5)
            
            await processing_msg.delete()
            
            if not questions:
                await message.answer(
                    "📄 В этом проекте пока нет загруженных документов или они еще обрабатываются.\n\n"
                    "Загрузите документы через веб-интерфейс, чтобы получить предложенные вопросы."
                )
                return
            
            questions_text = "💡 <b>Предложенные вопросы на основе ваших документов:</b>\n\n"
            for i, q in enumerate(questions, 1):
                questions_text += f"{i}. {q}\n"
            
            questions_text += "\n💬 <b>Совет:</b> Скопируйте любой вопрос и отправьте его боту для получения ответа!"
            
            await message.answer(questions_text)
            
    except Exception as e:
        logger.error(f"Error generating suggested questions: {e}", exc_info=True)
        await processing_msg.delete()
        await message.answer("❌ Произошла ошибка при генерации вопросов. Попробуйте позже.")


async def handle_mode_callback(callback: CallbackQuery, state: FSMContext):
    """Обработка callback для переключения режима ответа"""
    import logging
    logger = logging.getLogger(__name__)
    
    current_state = await state.get_state()
    if current_state != AuthStates.authorized:
        await callback.answer("Пожалуйста, сначала авторизуйтесь через /start", show_alert=True)
        return
    
    data = await state.get_data()
    mode = callback.data
    
    if mode == "set_mode_rag":
        await state.update_data(answer_mode="rag_mode")
        await callback.answer("✅ Режим изменен: Ответы на основе документов", show_alert=False)
        
        # Обновляем клавиатуру
        mode_keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📄 Режим: Документы",
                    callback_data="set_mode_rag"
                )
            ],
            [
                InlineKeyboardButton(
                    text="💬 Переключить на Общие вопросы",
                    callback_data="set_mode_general"
                )
            ],
            [
                InlineKeyboardButton(
                    text="💡 Предложить вопросы",
                    callback_data="suggest_questions"
                )
            ]
        ])
        try:
            await callback.message.edit_text(
                "🔧 <b>Режим ответа:</b> 📄 Документы\n\n"
                "Бот будет отвечать на основе загруженных документов проекта.",
                reply_markup=mode_keyboard
            )
        except Exception as e:
            # Игнорируем ошибку если сообщение не изменилось
            if "message is not modified" not in str(e):
                logger.warning(f"Error editing message: {e}")
    elif mode == "set_mode_general":
        await state.update_data(answer_mode="general_mode")
        await callback.answer("✅ Режим изменен: Общие вопросы", show_alert=False)
        
        # Обновляем клавиатуру
        mode_keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📄 Переключить на Документы",
                    callback_data="set_mode_rag"
                )
            ],
            [
                InlineKeyboardButton(
                    text="💬 Режим: Общие вопросы",
                    callback_data="set_mode_general"
                )
            ],
            [
                InlineKeyboardButton(
                    text="💡 Предложить вопросы",
                    callback_data="suggest_questions"
                )
            ]
        ])
        try:
            await callback.message.edit_text(
                "🔧 <b>Режим ответа:</b> 💬 Общие вопросы\n\n"
                "Бот будет отвечать на общие вопросы без использования документов.",
                reply_markup=mode_keyboard
            )
        except Exception as e:
            # Игнорируем ошибку если сообщение не изменилось
            if "message is not modified" not in str(e):
                logger.warning(f"Error editing message: {e}")
    elif mode == "suggest_questions":
        # Вызываем команду предложения вопросов напрямую
        await callback.answer()
        # Вызываем логику напрямую, используя callback.message
        import logging
        logger = logging.getLogger(__name__)
        
        current_state = await state.get_state()
        if current_state != AuthStates.authorized:
            await callback.message.answer("Пожалуйста, сначала авторизуйтесь через /start")
            return
        
        data = await state.get_data()
        project_id_from_state = data.get("project_id")
        
        if not project_id_from_state:
            await callback.message.answer("Ошибка: проект не определен. Используйте /start.")
            return
        
        from uuid import UUID
        from app.core.database import AsyncSessionLocal
        from app.services.rag_service import RAGService
        
        processing_msg = await callback.message.answer("⏳ Анализирую документы и генерирую вопросы...")
        
        try:
            async with AsyncSessionLocal() as db:
                rag_service = RAGService(db)
                questions = await rag_service.suggestions.generate_suggested_questions(UUID(project_id_from_state), limit=5)
                
                await processing_msg.delete()
                
                if not questions:
                    await callback.message.answer(
                        "📄 В этом проекте пока нет загруженных документов или они еще обрабатываются.\n\n"
                        "Загрузите документы через веб-интерфейс, чтобы получить предложенные вопросы."
                    )
                    return
                
                questions_text = "💡 <b>Предложенные вопросы на основе ваших документов:</b>\n\n"
                for i, q in enumerate(questions, 1):
                    questions_text += f"{i}. {q}\n"
                
                questions_text += "\n💬 <b>Совет:</b> Скопируйте любой вопрос и отправьте его боту для получения ответа!"
                
                await callback.message.answer(questions_text)
                
        except Exception as e:
            logger.error(f"Error generating suggested questions: {e}", exc_info=True)
            await processing_msg.delete()
            await callback.message.answer("❌ Произошла ошибка при генерации вопросов. Попробуйте позже.")


def register_commands(dp: Dispatcher, project_id: str):
    """Регистрация команд"""
    dp.message.register(cmd_start, Command("start"))
    dp.message.register(cmd_help, Command("help"))
    # Регистрируем команду /documents и альтернативные варианты
    dp.message.register(cmd_documents, Command("documents"))
    dp.message.register(cmd_documents, Command("показать_документы"))
    dp.message.register(cmd_documents, Command("документы"))
    dp.message.register(cmd_documents, Command("files"))
    dp.message.register(cmd_documents, Command("файлы"))
    # Регистрируем команду для предложения вопросов
    dp.message.register(cmd_suggest_questions, Command("suggest_questions", "предложить_вопросы", "вопросы", "questions"))
    # Регистрируем обработчик callback для переключения режимов
    dp.callback_query.register(handle_mode_callback)
