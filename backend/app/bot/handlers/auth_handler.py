"""
Обработчики авторизации пользователей
"""
from aiogram import Dispatcher, F
from aiogram.types import Message, ReplyKeyboardRemove
from aiogram.enums import ChatAction
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage

from app.core.database import AsyncSessionLocal
from app.models.project import Project
from app.models.user import User
from app.services.user_service import UserService
from sqlalchemy import select
from datetime import datetime


# FSM состояния для авторизации
class AuthStates(StatesGroup):
    waiting_password = State()
    waiting_phone = State()
    authorized = State()
    # Режим ответа: rag_mode (на основе документов) или general_mode (общие вопросы)
    # По умолчанию rag_mode


# Хранилище состояний (в production использовать Redis)
storage = MemoryStorage()


async def handle_password(message: Message, state: FSMContext, project_id: str = None):
    """Обработка ввода пароля
    
    Если несколько проектов используют один bot_token, ищем проект по паролю среди всех проектов с этим токеном.
    """
    import logging
    logger = logging.getLogger(__name__)
    
    # Показываем typing indicator
    try:
        await message.bot.send_chat_action(message.chat.id, ChatAction.TYPING)
    except Exception as e:
        logger.warning(f"Failed to send typing indicator: {e}")
    
    async with AsyncSessionLocal() as db:
        password = message.text
        
        # Получаем bot_token из бота
        bot_token = None
        if message.bot and hasattr(message.bot, 'token'):
            bot_token = message.bot.token
        
        project = None
        
        # Ищем проект: сначала по project_id (если задан), затем по паролю и bot_token
        if project_id:
            result = await db.execute(
                select(Project).where(Project.id == project_id)
            )
            project = result.scalar_one_or_none()
            # Проверяем, что пароль правильный
            if project and project.access_password != password:
                project = None
        
        # Если не нашли по project_id или project_id не задан, ищем по паролю и bot_token
        if not project and bot_token:
            result = await db.execute(
                select(Project).where(
                    Project.bot_token == bot_token,
                    Project.access_password == password
                )
            )
            project = result.scalar_one_or_none()
        
        if not project:
            await message.answer("❌ Неверный пароль. Попробуйте снова или используйте /start")
            return
        
        # Сохраняем найденный project_id в состоянии
        await state.update_data(project_id=str(project.id))
        
        # Пароль правильный, запрашиваем телефон
        await state.set_state(AuthStates.waiting_phone)
        
        await message.answer(
            "Пароль верный! Теперь введите ваш номер телефона (например: +79001234567):",
            reply_markup=ReplyKeyboardRemove()
        )


async def handle_contact(message: Message, state: FSMContext, project_id: str = None):
    """Обработка получения контакта или ручного ввода телефона"""
    import logging
    logger = logging.getLogger(__name__)
    
    # Показываем typing indicator
    try:
        await message.bot.send_chat_action(message.chat.id, ChatAction.TYPING)
    except Exception as e:
        logger.warning(f"Failed to send typing indicator: {e}")
    
    # Получаем project_id из состояния (был сохранен при вводе пароля)
    data = await state.get_data()
    project_id_from_state = data.get("project_id")
    
    if not project_id_from_state:
        # Если project_id не в состоянии, пытаемся использовать переданный
        if not project_id:
            await message.answer("❌ Ошибка: проект не определен. Используйте /start")
            return
        project_id_from_state = project_id
    
    phone = None
    
    if message.contact:
        phone = message.contact.phone_number
    elif message.text:
        # Ручной ввод телефона
        phone = message.text.strip()
        # Простая валидация
        if not phone.startswith('+') and not phone.isdigit():
            await message.answer("❌ Пожалуйста, введите корректный номер телефона (например: +79001234567)")
            return
    
    if not phone:
        await message.answer("❌ Не удалось получить номер телефона. Попробуйте снова.")
        return
    
    async with AsyncSessionLocal() as db:
        user_service = UserService(db)
        
        # Получаем telegram_id для сохранения
        telegram_user_id = str(message.from_user.id)
        telegram_username = message.from_user.username
        
        # Проверка существования пользователя по телефону
        user = await user_service.get_user_by_phone(project_id_from_state, phone)
        
        if not user:
            # Создание нового пользователя с telegram_id
            user = await user_service.create_user(
                project_id_from_state, 
                phone, 
                telegram_username,
                telegram_id=telegram_user_id
            )
            
            # Обновление first_login_at
            user.first_login_at = datetime.utcnow()
            await db.commit()
            logger.info(f"[AUTH] Created new user {user.id} with telegram_id {telegram_user_id}")
        elif user.status == "blocked":
            await message.answer("❌ Ваш доступ заблокирован. Обратитесь к администратору.")
            return
        else:
            # Обновление telegram_id и username если изменились
            if user.telegram_id != telegram_user_id:
                user.telegram_id = telegram_user_id
            if telegram_username and user.username != telegram_username:
                user.username = telegram_username
            await db.commit()
            logger.info(f"[AUTH] Updated user {user.id} with telegram_id {telegram_user_id}")
        
        # Сохранение user_id в состоянии
        await state.update_data(user_id=str(user.id))
        await state.set_state(AuthStates.authorized)
        
        # Получаем информацию о проекте для приветствия
        result = await db.execute(
            select(Project).where(Project.id == project_id_from_state)
        )
        project = result.scalar_one_or_none()
        
        welcome_authorized = "✅ <b>Авторизация успешна!</b>\n\n"
        
        if project:
            welcome_authorized += f"👋 Добро пожаловать в бот проекта <b>«{project.name}»</b>!\n\n"
        
        welcome_authorized += "🤖 <b>Как использовать:</b>\n"
        welcome_authorized += "• Отправьте файл для загрузки\n"
        welcome_authorized += "• Задавайте вопросы о загруженных документах\n"
        welcome_authorized += "• Используйте /documents для просмотра и удаления файлов\n\n"
        
        welcome_authorized += "💡 <b>Советы:</b>\n"
        welcome_authorized += "• Задавайте конкретные вопросы\n"
        welcome_authorized += "• Бот отвечает на основе загруженных документов\n\n"
        
        welcome_authorized += "❓ <b>Задайте ваш первый вопрос или отправьте файл:</b>"
        
        await message.answer(
            welcome_authorized,
            reply_markup=ReplyKeyboardRemove()
        )


async def handle_text_before_auth(message: Message, state: FSMContext):
    """Обработка текста до авторизации (запрос пароля)
    
    Этот обработчик срабатывает для всех текстовых сообщений, которые не обрабатываются
    более специфичными обработчиками (с фильтрами состояний).
    Если пользователь вводит текст, а состояние не установлено, проверяем существование пользователя в БД.
    Если пользователь существует - автоматически авторизуем, иначе запрашиваем пароль.
    
    ВАЖНО: Этот обработчик НЕ должен перехватывать сообщения авторизованных пользователей!
    """
    import logging
    logger = logging.getLogger(__name__)
    
    # Показываем typing indicator
    try:
        await message.bot.send_chat_action(message.chat.id, ChatAction.TYPING)
    except Exception as e:
        logger.warning(f"Failed to send typing indicator: {e}")
    
    current_state = await state.get_state()
    logger.info(f"[AUTH HANDLER] handle_text_before_auth called, state: {current_state}, text: {message.text[:50] if message.text else 'None'}")
    
    # КРИТИЧНО: Если пользователь авторизован, НЕ обрабатываем здесь - пусть обрабатывает question_handler
    if current_state == AuthStates.authorized:
        logger.debug(f"[AUTH HANDLER] User is authorized, skipping handle_text_before_auth")
        return  # Пропускаем, чтобы вопрос обработал question_handler
    
    # Если состояние не установлено, проверяем существование пользователя в БД
    if current_state is None:
        logger.info(f"[AUTH HANDLER] No state set, checking if user exists in DB")
        
        async with AsyncSessionLocal() as db:
            from app.models.user import User
            from app.models.project import Project
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
                # Пользователь существует - автоматически авторизуем
                logger.info(f"[AUTH HANDLER] User {telegram_user_id} already exists, auto-authorizing")
                
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
                    logger.info(f"[AUTH HANDLER] User auto-authorized, state set to authorized")
                    # Возвращаемся, чтобы вопрос обработал question_handler
                    return
                else:
                    logger.warning(f"[AUTH HANDLER] User exists but project not found")
        
        # Если пользователь не найден, запрашиваем пароль
        logger.info(f"[AUTH HANDLER] User not found, setting waiting_password and processing as password")
        await state.set_state(AuthStates.waiting_password)
        # Рекурсивно вызываем handle_password
        await handle_password(message, state)
        return
    
    # Если не авторизован и не в процессе авторизации, показываем сообщение
    if current_state != AuthStates.authorized:
        logger.info(f"[AUTH HANDLER] User not authorized (state: {current_state}), asking for password")
        await message.answer("Для начала работы введите пароль доступа или используйте /start")


def register_auth_handlers(dp: Dispatcher, project_id: str):
    """Регистрация обработчиков авторизации"""
    import logging
    logger = logging.getLogger(__name__)
    
    # Команда /start уже обрабатывается в commands.py
    # Обработка пароля
    dp.message.register(handle_password, AuthStates.waiting_password, F.text)
    
    # Обработка контакта или телефона
    dp.message.register(handle_contact, AuthStates.waiting_phone, F.contact | F.text)
    
    # ВАЖНО: НЕ регистрируем handle_text_before_auth для авторизованных пользователей!
    # Вместо этого регистрируем его только для состояний, когда пользователь НЕ авторизован
    # Это предотвращает перехват сообщений авторизованных пользователей
    # Используем фильтр состояния, чтобы он не срабатывал для authorized
    from aiogram.filters import StateFilter
    from aiogram.fsm.state import State
    
    # Регистрируем handle_text_before_auth только для состояний, когда пользователь НЕ авторизован
    # Это означает, что он будет срабатывать только если состояние None или waiting_password/waiting_phone
    # НО НЕ для authorized - для этого есть question_handler
    dp.message.register(handle_text_before_auth, ~StateFilter(AuthStates.authorized), F.text)
    logger.info(f"[REGISTER HANDLERS] Auth handlers registered for project {project_id} (handle_text_before_auth excluded for authorized users)")

