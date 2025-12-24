"""
Обработчики для Telegram бота
"""
from aiogram import Dispatcher

from app.bot.handlers.commands import register_commands
from app.bot.handlers.auth_handler import register_auth_handlers
from app.bot.handlers.question_handler import register_question_handlers


def register_handlers(dp: Dispatcher, project_id: str):
    """Регистрация всех обработчиков
    
    Порядок регистрации важен:
    1. Команды (имеют наивысший приоритет)
    2. Обработчики авторизации (с фильтрами состояний)
    3. Обработчики вопросов (для авторизованных пользователей)
    """
    # Сначала регистрируем команды (они имеют наивысший приоритет)
    register_commands(dp, project_id)
    # Затем обработчики авторизации (с фильтрами состояний)
    register_auth_handlers(dp, project_id)
    # В конце обработчики вопросов (для авторизованных пользователей)
    register_question_handlers(dp, project_id)















