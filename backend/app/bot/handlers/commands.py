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
                
                # Отправляем клавиатуру с режимами и типовыми запросами (LangGraph)
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
                    ],
                    [
                        InlineKeyboardButton(
                            text="📋 Резюме документа",
                            callback_data="get_summary"
                        ),
                        InlineKeyboardButton(
                            text="📝 Описание",
                            callback_data="get_description"
                        )
                    ],
                    [
                        InlineKeyboardButton(
                            text="🔍 Глубокий анализ",
                            callback_data="get_analysis"
                        )
                    ]
                ])
                await message.answer("🔧 <b>Управление режимом и типовые запросы (LangGraph):</b>", reply_markup=mode_keyboard)
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
    
    help_text = "<b>📚 Справка по использованию бота</b>\n\n"
    
    help_text += "📋 <b>Основные команды:</b>\n"
    help_text += "/start - Начать работу с ботом или продолжить сессию\n"
    help_text += "/help - Показать эту справку\n"
    
    if is_authorized:
        help_text += "\n📄 <b>Работа с документами:</b>\n"
        help_text += "/upload или /загрузить - Загрузить файл (PDF, Excel, Word, TXT)\n"
        help_text += "/documents - Показать список документов проекта\n"
        help_text += "/suggest_questions - Предложить вопросы на основе документов\n"
        
        help_text += "\n📋 <b>Типовые запросы (LangGraph):</b>\n"
        help_text += "/summary или /резюме - <b>Резюме документа</b>\n"
        help_text += "  • Точное краткое содержание с минимальными искажениями\n"
        help_text += "  • Map-Reduce для больших документов (>500KB)\n"
        help_text += "/describe или /описание - <b>Описание содержания</b>\n"
        help_text += "  • Тип и назначение документа\n"
        help_text += "  • Основные темы и ключевые сущности\n"
        help_text += "/analyze или /анализ - <b>Глубокий анализ</b>\n"
        help_text += "  • Ключевые факты и данные\n"
        help_text += "  • Структура и логика документа\n"
        help_text += "  • Выводы на основе содержимого\n"
        
        help_text += "\n❓ <b>Ответ на вопрос:</b>\n"
        help_text += "Просто напишите вопрос - бот найдет ответ в документах\n"
    
    help_text += "\n💡 <b>Как задать вопрос:</b>\n"
    help_text += "• Напишите вопрос в свободной форме\n"
    help_text += "• Бот ищет ответ в загруженных документах\n"
    help_text += "• Помнит контекст последних 10 сообщений\n"
    
    if not is_authorized:
        help_text += "\n🔐 <b>Авторизация:</b>\n"
        help_text += "Введите пароль доступа после команды /start.\n"
    
    if is_authorized:
        help_text += "\n📊 <b>Рекомендации по использованию:</b>\n"
        help_text += "• Для конкретных фактов - задайте вопрос\n"
        help_text += "• Для обзора документа - используйте /summary\n"
        help_text += "• Для структуры и тем - используйте /describe\n"
        help_text += "• Для глубокого понимания - используйте /analyze\n"
    
    help_text += "\n🤖 <i>Бот использует LangGraph RAG для точных ответов</i>"
    
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


async def cmd_summary(message: Message, state: FSMContext):
    """
    Обработка команды /summary или /резюме - получить резюме документа или блока
    
    Использует LangGraph для создания резюме с минимальными искажениями.
    Для больших документов (>500KB) используется Map-Reduce стратегия.
    """
    import logging
    logger = logging.getLogger(__name__)
    
    current_state = await state.get_state()
    if current_state != AuthStates.authorized:
        await message.answer("Пожалуйста, сначала авторизуйтесь через /start")
        return
    
    data = await state.get_data()
    user_id_str = data.get("user_id")
    if not user_id_str:
        await message.answer("Ошибка: пользователь не найден. Используйте /start")
        return
    
    from uuid import UUID
    try:
        user_id = UUID(user_id_str)
    except ValueError:
        await message.answer("Ошибка: неверный формат ID пользователя. Используйте /start")
        return
    
    async with AsyncSessionLocal() as db:
        from app.models.user import User
        from app.models.document import Document
        from sqlalchemy import select
        from app.services.document_summary_service import DocumentSummaryService
        
        user_result = await db.execute(select(User).where(User.id == user_id))
        user = user_result.scalar_one_or_none()
        
        if not user:
            await message.answer("Ошибка: пользователь не найден")
            return
        
        project_id = user.project_id
        
        # Получаем документы проекта
        result = await db.execute(
            select(Document)
            .where(Document.project_id == project_id)
            .order_by(Document.created_at.desc())
            .limit(10)
        )
        documents = result.scalars().all()
        
        if not documents:
            await message.answer("📄 В проекте пока нет документов для анализа.")
            return
        
        processing_msg = await message.answer(
            "⏳ Анализирую документы и создаю резюме...\n"
            "💡 Для больших документов это может занять 1-2 минуты."
        )
        
        try:
            summary_service = DocumentSummaryService(db)
            
            # Если один документ - резюме этого документа
            if len(documents) == 1:
                doc = documents[0]
                content_length = len(doc.content) if doc.content else 0
                
                # Выбираем стратегию в зависимости от размера
                if content_length > 500000:  # Большой документ
                    logger.info(f"[Summary] Using Map-Reduce for large document {doc.id}")
                    summary = await summary_service.generate_map_reduce_summary(doc.id)
                else:
                    # Пробуем LangGraph, fallback на обычный метод
                    try:
                        summary = await summary_service.generate_summary_with_langgraph(doc.id)
                    except Exception as e:
                        logger.warning(f"LangGraph summary failed, using standard method: {e}")
                summary = await summary_service.generate_summary(doc.id)
                
                if summary:
                    await processing_msg.delete()
                    response_text = f"📄 <b>Резюме документа «{doc.filename}»:</b>\n\n{summary}"
                    
                    # Добавляем информацию о размере документа
                    if content_length > 100000:
                        pages_estimate = content_length // 3000  # Примерно 3000 символов на страницу
                        response_text += f"\n\n📊 <i>Документ: ~{pages_estimate} страниц, {content_length:,} символов</i>"
                    
                    if len(response_text) > 4096:
                        parts = [response_text[i:i+4096] for i in range(0, len(response_text), 4096)]
                        for part in parts:
                            await message.answer(part)
                    else:
                        await message.answer(response_text)
                else:
                    await processing_msg.delete()
                    await message.answer(f"❌ Не удалось создать резюме для документа «{doc.filename}»")
            else:
                # Несколько документов - создаем общее резюме
                summaries = []
                for doc in documents[:5]:  # Максимум 5 документов
                    doc_summary = getattr(doc, 'summary', None)
                    if not doc_summary:
                        try:
                            doc_summary = await summary_service.generate_summary_with_langgraph(doc.id)
                        except:
                            doc_summary = await summary_service.generate_summary(doc.id)
                    if doc_summary:
                        summaries.append(f"<b>{doc.filename}:</b> {doc_summary}")
                
                if summaries:
                    await processing_msg.delete()
                    summary_text = "📄 <b>Резюме документов проекта:</b>\n\n" + "\n\n".join(summaries)
                    max_length = 4096
                    if len(summary_text) > max_length:
                        parts = [summary_text[i:i+max_length] for i in range(0, len(summary_text), max_length)]
                        for part in parts:
                            await message.answer(part)
                    else:
                        await message.answer(summary_text)
                else:
                    await processing_msg.delete()
                    await message.answer("❌ Не удалось создать резюме документов")
        except Exception as e:
            logger.error(f"Error generating summary: {e}", exc_info=True)
            await processing_msg.delete()
            await message.answer("❌ Произошла ошибка при создании резюме. Попробуйте позже.")


async def cmd_describe(message: Message, state: FSMContext):
    """
    Обработка команды /describe или /описание - описание содержания документа
    
    Использует LangGraph workflow для создания детального описания:
    - Тип и назначение документа
    - Основные темы и разделы
    - Ключевые сущности (компании, люди, даты, суммы)
    - Структура документа
    """
    import logging
    logger = logging.getLogger(__name__)
    
    current_state = await state.get_state()
    if current_state != AuthStates.authorized:
        await message.answer("Пожалуйста, сначала авторизуйтесь через /start")
        return
    
    data = await state.get_data()
    user_id_str = data.get("user_id")
    if not user_id_str:
        await message.answer("Ошибка: пользователь не найден. Используйте /start")
        return
    
    from uuid import UUID
    try:
        user_id = UUID(user_id_str)
    except ValueError:
        await message.answer("Ошибка: неверный формат ID пользователя. Используйте /start")
        return
    
    async with AsyncSessionLocal() as db:
        from app.models.user import User
        from app.models.document import Document
        from sqlalchemy import select
        
        user_result = await db.execute(select(User).where(User.id == user_id))
        user = user_result.scalar_one_or_none()
        
        if not user:
            await message.answer("Ошибка: пользователь не найден")
            return
        
        project_id = user.project_id
        
        # Получаем документы проекта
        result = await db.execute(
            select(Document)
            .where(Document.project_id == project_id)
            .order_by(Document.created_at.desc())
            .limit(10)
        )
        documents = result.scalars().all()
        
        if not documents:
            await message.answer("📄 В проекте пока нет документов для описания.")
            return
        
        processing_msg = await message.answer(
            "⏳ Анализирую содержание документов...\n"
            "📝 Определяю тип, темы и ключевые сущности."
        )
        
        try:
            description_text = None
            # Пробуем использовать LangGraph workflow
            try:
                from app.services.langgraph_rag_workflow import (
                    LangGraphRAGWorkflow, 
                    QueryType
                )
                
                rag_workflow = LangGraphRAGWorkflow(db)
                
                if len(documents) == 1:
                    # Описание одного документа
                    doc = documents[0]
                    result = await rag_workflow.run(
                        query=f"Опиши содержание документа {doc.filename}",
                        query_type=QueryType.DESCRIPTION,
                        project_id=str(project_id),
                        document_id=str(doc.id)
                    )
                    answer = result.get('answer', '')
                    
                    if answer:
                        await processing_msg.delete()
                        description_text = f"📄 <b>Описание документа «{doc.filename}»:</b>\n\n{answer}"
                    else:
                        raise Exception("Empty answer from LangGraph")
                else:
                    # Описание нескольких документов
                    result = await rag_workflow.run(
                        query="Опиши содержание всех документов проекта. Какие темы они охватывают? Какая структура?",
                        query_type=QueryType.DESCRIPTION,
                        project_id=str(project_id)
                    )
                    answer = result.get('answer', '')
                    
                    if answer:
                        await processing_msg.delete()
                        # Добавляем список документов
                        doc_list = "\n".join([f"• {doc.filename}" for doc in documents[:5]])
                        description_text = (
                            f"📄 <b>Описание документов проекта ({len(documents)} шт.):</b>\n\n"
                            f"<b>Документы:</b>\n{doc_list}\n\n"
                            f"<b>Содержание:</b>\n{answer}"
                        )
                    else:
                        raise Exception("Empty answer from LangGraph")
                        
            except Exception as langgraph_error:
                logger.warning(f"LangGraph describe failed: {langgraph_error}, using fallback")
                # Fallback на обычный RAG
                from app.services.rag_service import RAGService
                rag_service = RAGService(db)
                
                question = "Опиши кратко содержание всех документов проекта. Что в них содержится? Какие основные темы?"
                answer = await rag_service.generate_answer(user_id, question)
                
                await processing_msg.delete()
                description_text = f"📄 <b>Описание содержания документов проекта:</b>\n\n{answer}"
            
            if description_text:
                max_length = 4096
                if len(description_text) > max_length:
                    parts = [description_text[i:i+max_length] for i in range(0, len(description_text), max_length)]
                    for part in parts:
                        await message.answer(part)
                else:
                    await message.answer(description_text)
            else:
                await message.answer("❌ Не удалось создать описание содержания документов")
                
        except Exception as e:
            logger.error(f"Error generating description: {e}", exc_info=True)
            await processing_msg.delete()
            await message.answer("❌ Произошла ошибка при создании описания. Попробуйте позже.")


async def cmd_analyze(message: Message, state: FSMContext):
    """
    Обработка команды /analyze или /анализ - глубокий анализ документа
    
    Проводит детальный анализ документа:
    - Определяет тип и назначение документа
    - Выделяет ключевые факты и данные
    - Анализирует структуру и логику документа
    - Выявляет важные связи между частями
    - Делает выводы на основе содержимого
    """
    import logging
    logger = logging.getLogger(__name__)
    
    current_state = await state.get_state()
    if current_state != AuthStates.authorized:
        await message.answer("Пожалуйста, сначала авторизуйтесь через /start")
        return
    
    data = await state.get_data()
    user_id_str = data.get("user_id")
    project_id_str = data.get("project_id")
    
    if not user_id_str or not project_id_str:
        await message.answer("Ошибка: данные сессии не найдены. Используйте /start")
        return
    
    from uuid import UUID
    try:
        user_id = UUID(user_id_str)
        project_id = UUID(project_id_str)
    except ValueError:
        await message.answer("Ошибка: неверный формат ID. Используйте /start")
        return
    
    async with AsyncSessionLocal() as db:
        from app.models.document import Document
        from sqlalchemy import select
        
        # Получаем документы проекта
        result = await db.execute(
            select(Document)
            .where(Document.project_id == project_id)
            .order_by(Document.created_at.desc())
            .limit(5)
        )
        documents = result.scalars().all()
        
        if not documents:
            await message.answer("📄 В проекте пока нет документов для анализа.")
            return
        
        processing_msg = await message.answer(
            "🔍 Провожу глубокий анализ документов...\n"
            "📊 Это может занять 1-3 минуты для больших документов."
        )
        
        try:
            from app.services.langgraph_rag_workflow import (
                LangGraphRAGWorkflow, 
                QueryType
            )
            
            rag_workflow = LangGraphRAGWorkflow(db)
            
            analyses = []
            for doc in documents[:3]:  # Анализируем максимум 3 документа
                result = await rag_workflow.run(
                    query=f"Проведи глубокий анализ документа {doc.filename}",
                    query_type=QueryType.ANALYSIS,
                    project_id=str(project_id),
                    document_id=str(doc.id)
                )
                
                if result.get('answer'):
                    analyses.append(f"📊 <b>{doc.filename}</b>\n{result['answer']}")
            
            await processing_msg.delete()
            
            if analyses:
                analysis_text = "🔍 <b>Глубокий анализ документов:</b>\n\n" + "\n\n---\n\n".join(analyses)
                
                max_length = 4096
                if len(analysis_text) > max_length:
                    parts = [analysis_text[i:i+max_length] for i in range(0, len(analysis_text), max_length)]
                    for part in parts:
                        await message.answer(part)
                else:
                    await message.answer(analysis_text)
            else:
                await message.answer("❌ Не удалось провести анализ документов")
                
        except Exception as e:
            logger.error(f"Error analyzing documents: {e}", exc_info=True)
            await processing_msg.delete()
            await message.answer("❌ Произошла ошибка при анализе. Попробуйте позже.")


async def cmd_upload(message: Message, state: FSMContext):
    """Обработка команды /upload - напоминание о загрузке файла"""
    import logging
    logger = logging.getLogger(__name__)
    
    # Проверка авторизации
    current_state = await state.get_state()
    if current_state != AuthStates.authorized:
        await message.answer("❌ Сначала авторизуйтесь через /start")
        return
    
    help_text = (
        "📤 <b>Загрузка файлов</b>\n\n"
        "Отправьте файл в этот чат, и он будет автоматически обработан и добавлен в базу знаний.\n\n"
        "📄 <b>Поддерживаемые форматы:</b>\n"
        "• PDF (.pdf)\n"
        "• Excel (.xlsx, .xls)\n"
        "• Word (.docx)\n"
        "• Текстовые файлы (.txt)\n\n"
        "💡 <b>Как использовать:</b>\n"
        "1. Просто отправьте файл в чат\n"
        "2. Бот автоматически обработает его\n"
        "3. Файл будет индексирован в RAG для поиска\n\n"
        "⚠️ <b>Ограничения:</b>\n"
        "• Максимальный размер файла: 50 МБ\n"
        "• Обработка может занять некоторое время для больших файлов\n\n"
        "📚 После загрузки файл будет доступен для поиска через RAG."
    )
    
    await message.answer(help_text, parse_mode="HTML")


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
            ],
            [
                InlineKeyboardButton(
                    text="📋 Резюме",
                    callback_data="get_summary"
                ),
                InlineKeyboardButton(
                    text="📝 Описание",
                    callback_data="get_description"
                )
            ],
            [
                InlineKeyboardButton(
                    text="🔍 Глубокий анализ",
                    callback_data="get_analysis"
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
            ],
            [
                InlineKeyboardButton(
                    text="📋 Резюме",
                    callback_data="get_summary"
                ),
                InlineKeyboardButton(
                    text="📝 Описание",
                    callback_data="get_description"
                )
            ],
            [
                InlineKeyboardButton(
                    text="🔍 Глубокий анализ",
                    callback_data="get_analysis"
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
    elif mode == "get_summary":
        # Вызываем команду summary напрямую
        await callback.answer()
        await cmd_summary(callback.message, state)
    elif mode == "get_description":
        # Вызываем команду describe напрямую
        await callback.answer()
        await cmd_describe(callback.message, state)
    elif mode == "get_analysis":
        # Вызываем команду analyze напрямую
        await callback.answer()
        await cmd_analyze(callback.message, state)


def register_commands(dp: Dispatcher, project_id: str):
    """Регистрация команд"""
    dp.message.register(cmd_start, Command("start"))
    dp.message.register(cmd_help, Command("help"))
    # Регистрируем команду /upload для загрузки файлов
    dp.message.register(cmd_upload, Command("upload", "загрузить", "загрузка", "файл"))
    # Регистрируем команду /documents и альтернативные варианты
    dp.message.register(cmd_documents, Command("documents"))
    dp.message.register(cmd_documents, Command("показать_документы"))
    dp.message.register(cmd_documents, Command("документы"))
    dp.message.register(cmd_documents, Command("files"))
    dp.message.register(cmd_documents, Command("файлы"))
    # Регистрируем команду для предложения вопросов
    dp.message.register(cmd_suggest_questions, Command("suggest_questions", "предложить_вопросы", "вопросы", "questions"))
    # Регистрируем команды для типовых запросов (LangGraph)
    dp.message.register(cmd_summary, Command("summary", "резюме", "summary_doc", "резюме_документа"))
    dp.message.register(cmd_describe, Command("describe", "описание", "describe_doc", "описание_документа"))
    dp.message.register(cmd_analyze, Command("analyze", "анализ", "analysis", "анализ_документа"))
    # Регистрируем обработчик callback для переключения режимов и типовых запросов
    dp.callback_query.register(handle_mode_callback)
